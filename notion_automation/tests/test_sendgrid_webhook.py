"""Tests del Event Webhook de SendGrid (doc 30 — confirmación de entrega real).

Cubre: guard del token, delivered/bounce escriben 'Entrega Correo', filtro
anti-BCC, eventos sin page_id ignorados, tolerancia a columna faltante y a
eventos corruptos, aviso al asesor en bounce, y custom_args en el payload de
envío. Todo mockeado.
"""
from unittest.mock import patch
import pytest
import app as A
import notion_client as nc
import email_sender as es

PID = "b4112147-b3ea-8348-a8f3-81b571ef224a"
URL_OK = "/webhook/sendgrid?token=test-sg-token"
EMAIL_CLIENTE = "cliente@test.com"


def _page(con_entrega: bool = True, email: str = EMAIL_CLIENTE) -> dict:
    props = {
        "Customers": {"type": "title", "title": [{"plain_text": "Cliente Test"}]},
        "Email": {"type": "email", "email": email},
        "Month": {"type": "rich_text", "rich_text": [{"plain_text": "Junio 2026"}]},
        "Adviser Accounting": {"type": "people", "people": [{"name": "Sebastián Robles"}]},
    }
    if con_entrega:
        props["Entrega Correo"] = {"type": "rich_text", "rich_text": []}
    return {"id": PID, "properties": props}


def _evento(tipo: str, email: str = EMAIL_CLIENTE, **extra) -> dict:
    ev = {"event": tipo, "email": email, "timestamp": 1784140800,
          "page_id": PID, "flujo": "f29"}
    ev.update(extra)
    return ev


@pytest.fixture()
def client():
    return A.app.test_client()


@pytest.fixture(autouse=True)
def _limpiar_reintentos():
    """El registro de reintentos post-bounce es estado del proceso: cada test
    parte limpio para no contaminarse entre sí."""
    A._reintentos_hechos.clear()
    yield
    A._reintentos_hechos.clear()


class TestGuardToken:
    def test_sin_token_en_servidor_da_503(self, client, monkeypatch):
        monkeypatch.delenv("SENDGRID_WEBHOOK_TOKEN", raising=False)
        r = client.post("/webhook/sendgrid?token=x", json=[])
        assert r.status_code == 503

    def test_token_incorrecto_da_401(self, client):
        r = client.post("/webhook/sendgrid?token=MALO", json=[])
        assert r.status_code == 401

    def test_sin_token_en_query_da_401(self, client):
        r = client.post("/webhook/sendgrid", json=[])
        assert r.status_code == 401


class TestEventos:
    def test_delivered_escribe_entrega(self, client):
        with patch.object(nc, "get_page", return_value=_page()), \
             patch.object(nc, "update_props") as m:
            r = client.post(URL_OK, json=[_evento("delivered")])
        assert r.status_code == 200
        assert r.get_json()["filas_actualizadas"] == 1
        page_id, updates = m.call_args[0]
        assert page_id == PID
        texto = updates["Entrega Correo"]["rich_text"][0]["text"]["content"]
        assert texto.startswith("✅ Entregado")

    def test_primer_bounce_agenda_reintento_sin_alarma(self, client):
        # Caso Mockenau (15-jul): un hipo DNS no debe alarmar al asesor de una;
        # se agenda UN reintento automático y la columna lo deja visible.
        ev = _evento("bounce", reason="unable to get mx info")
        with patch.object(nc, "get_page", return_value=_page()), \
             patch.object(nc, "update_props") as m, \
             patch.object(A.threading, "Timer") as timer, \
             patch.object(A.alertas, "avisar_fallo_asesor") as alerta:
            r = client.post(URL_OK, json=[ev])
        assert r.status_code == 200
        texto = m.call_args[0][1]["Entrega Correo"]["rich_text"][0]["text"]["content"]
        assert texto.startswith("❌ No entregado (bounce)")
        assert "reintento automático" in texto
        assert "unable to get mx info" in texto
        assert not alerta.called
        delay, _fn = timer.call_args[0]
        assert delay == A.REINTENTO_BOUNCE_S
        assert PID in A._reintentos_hechos

    def test_segundo_bounce_avisa_asesor_con_status_correcto(self, client):
        # La fila ya tuvo su reintento: el segundo bounce sí alarma, y el aviso
        # NO dice "el Status no fue cambiado" (acá el Status sí quedó en Enviado).
        A._reintentos_hechos.add(PID)
        ev = _evento("bounce", reason="550 mailbox does not exist")
        with patch.object(nc, "get_page", return_value=_page()), \
             patch.object(nc, "update_props") as m, \
             patch.object(A.threading, "Timer") as timer, \
             patch.object(A.alertas, "avisar_fallo_asesor") as alerta:
            r = client.post(URL_OK, json=[ev])
        assert r.status_code == 200
        texto = m.call_args[0][1]["Entrega Correo"]["rich_text"][0]["text"]["content"]
        assert texto.startswith("❌ No entregado (bounce)")
        assert "reintento automático" not in texto
        assert not timer.called
        assert alerta.called
        asesor, cliente, mes, motivo = alerta.call_args[0]
        assert asesor == "Sebastián Robles" and cliente == "Cliente Test"
        assert "bounce" in motivo.lower()
        # el contexto del rebote viaja en kwargs para que el diagnostico lo use
        kw = alerta.call_args[1]
        assert kw["flujo"] == "f29" and kw["page_id"] == PID
        assert kw["extra"]["ya_reintentado"] is True
        assert "550 mailbox" in kw["extra"]["bounce_reason"]

    def test_dropped_avisa_de_inmediato_sin_reintento(self, client):
        # dropped = SendGrid suprimió el envío; reintentar da lo mismo.
        ev = _evento("dropped", reason="Bounced Address")
        with patch.object(nc, "get_page", return_value=_page()), \
             patch.object(nc, "update_props"), \
             patch.object(A.threading, "Timer") as timer, \
             patch.object(A.alertas, "avisar_fallo_asesor") as alerta:
            client.post(URL_OK, json=[ev])
        assert not timer.called
        assert alerta.called

    def test_bounce_con_flujo_desconocido_avisa_de_inmediato(self, client):
        # Sin flujo reconocible no hay handler de reenvío: alarma como siempre.
        ev = _evento("bounce", flujo="", reason="x")
        with patch.object(nc, "get_page", return_value=_page()), \
             patch.object(nc, "update_props"), \
             patch.object(A.threading, "Timer") as timer, \
             patch.object(A.alertas, "avisar_fallo_asesor") as alerta:
            client.post(URL_OK, json=[ev])
        assert not timer.called
        assert alerta.called

    def test_reintento_ejecuta_el_handler_del_flujo(self, client):
        # La función agendada en el Timer reenvía usando el handler del flujo.
        ev = _evento("bounce", reason="mx")
        with patch.object(nc, "get_page", return_value=_page()), \
             patch.object(nc, "update_props"), \
             patch.object(A.threading, "Timer") as timer, \
             patch.object(A, "_procesar_page", return_value={"ok": True}) as proc:
            client.post(URL_OK, json=[ev])
            _delay, fn = timer.call_args[0]
            fn()   # ejecutar el reintento "10 min después", sincrónicamente
        assert proc.call_args[0] == (PID,)

    def test_delivered_no_avisa_fallo(self, client):
        # delivered nunca dispara el aviso de FALLO (ese es solo para rebotes)
        with patch.object(nc, "get_page", return_value=_page()), \
             patch.object(nc, "update_props"), \
             patch.object(A.alertas, "avisar_fallo_asesor") as alerta, \
             patch.object(A.alertas, "avisar_entrega_ok_asesor"):
            client.post(URL_OK, json=[_evento("delivered")])
        assert not alerta.called

    def test_delivered_confirma_entrega_al_remitente(self, client):
        # la mejora pedida: en delivered, el asesor recibe la confirmación "llegó"
        ev = _evento("delivered", remitente="matildemateluna@inversoragcp.com")
        with patch.object(nc, "get_page", return_value=_page()), \
             patch.object(nc, "update_props"), \
             patch.object(A.alertas, "avisar_entrega_ok_asesor") as conf:
            r = client.post(URL_OK, json=[ev])
        assert r.status_code == 200
        assert conf.called
        args = conf.call_args[0]
        assert args[0] == "matildemateluna@inversoragcp.com"   # remitente
        assert args[1] == "Cliente Test"                        # cliente (título)
        assert args[2] == "Junio 2026"                          # período (Month)

    def test_delivered_confirmacion_desactivable_por_env(self, client, monkeypatch):
        monkeypatch.setenv("AVISAR_ENTREGA_OK", "0")
        ev = _evento("delivered", remitente="matildemateluna@inversoragcp.com")
        with patch.object(nc, "get_page", return_value=_page()), \
             patch.object(nc, "update_props"), \
             patch.object(A.alertas, "avisar_entrega_ok_asesor") as conf:
            client.post(URL_OK, json=[ev])
        assert not conf.called

    def test_bounce_no_confirma_entrega(self, client):
        # un rebote NO manda confirmación de "llegó" (va por el camino de fallo)
        ev = _evento("bounce", reason="550 mailbox does not exist",
                     remitente="matildemateluna@inversoragcp.com")
        A._reintentos_hechos.add(PID)   # segundo bounce: no reintenta
        with patch.object(nc, "get_page", return_value=_page()), \
             patch.object(nc, "update_props"), \
             patch.object(A.threading, "Timer"), \
             patch.object(A.alertas, "avisar_fallo_asesor"), \
             patch.object(A.alertas, "avisar_entrega_ok_asesor") as conf:
            client.post(URL_OK, json=[ev])
        assert not conf.called

    def test_evento_de_copia_bcc_se_ignora(self, client):
        # delivered de la copia del asesor NO debe pisar el estado del cliente
        ev = _evento("delivered", email="sebastianrobles@inversoragcp.com")
        with patch.object(nc, "get_page", return_value=_page()), \
             patch.object(nc, "update_props") as m:
            r = client.post(URL_OK, json=[ev])
        assert r.get_json()["filas_actualizadas"] == 0
        assert not m.called

    def test_delivered_a_una_direccion_cc_del_cliente_cuenta(self, client):
        # Celda Email con varias direcciones (Hydroming): un delivered a la 2da
        # (que viajó en CC) es un evento legítimo del cliente, no una copia BCC.
        page = _page()
        page["properties"]["Email"] = {
            "type": "email", "email": "cliente@test.com, segundo@test.com"}
        ev = _evento("delivered", email="segundo@test.com")
        with patch.object(nc, "get_page", return_value=page), \
             patch.object(nc, "update_props") as m:
            r = client.post(URL_OK, json=[ev])
        assert r.get_json()["filas_actualizadas"] == 1
        assert m.called

    def test_evento_sin_page_id_se_ignora(self, client):
        ev = {"event": "delivered", "email": EMAIL_CLIENTE, "timestamp": 1784140800}
        with patch.object(nc, "get_page") as g, patch.object(nc, "update_props") as m:
            r = client.post(URL_OK, json=[ev])
        assert r.get_json()["filas_actualizadas"] == 0
        assert not g.called and not m.called

    def test_evento_irrelevante_se_ignora(self, client):
        # open/click/processed no interesan (no están suscritos, pero por si acaso)
        with patch.object(nc, "get_page") as g:
            r = client.post(URL_OK, json=[_evento("open"), _evento("processed")])
        assert r.get_json()["filas_actualizadas"] == 0
        assert not g.called

    def test_columna_entrega_faltante_no_rompe(self, client):
        with patch.object(nc, "get_page", return_value=_page(con_entrega=False)), \
             patch.object(nc, "update_props") as m:
            r = client.post(URL_OK, json=[_evento("delivered")])
        assert r.status_code == 200
        assert not m.called  # sin columna no hay PATCH, pero el batch sigue OK

    def test_evento_que_lanza_excepcion_no_tumba_el_batch(self, client):
        # el primero explota (Notion caído), el segundo se procesa igual
        with patch.object(nc, "get_page", side_effect=[RuntimeError("boom"), _page()]), \
             patch.object(nc, "update_props") as m:
            r = client.post(URL_OK, json=[_evento("delivered"), _evento("delivered")])
        assert r.status_code == 200
        assert r.get_json()["filas_actualizadas"] == 1
        assert m.call_count == 1

    def test_payload_dict_solo_tambien_se_procesa(self, client):
        with patch.object(nc, "get_page", return_value=_page()), \
             patch.object(nc, "update_props"):
            r = client.post(URL_OK, json=_evento("delivered"))
        assert r.get_json()["filas_actualizadas"] == 1


class TestHandlerPorFlujo:
    """El custom_arg 'flujo' de cada correo debe mapear a su handler de reenvío."""

    def test_f29(self):
        assert A._handler_por_flujo("f29") is A._procesar_page

    def test_rrhh(self):
        import handlers.rrhh as rrhh
        assert A._handler_por_flujo("rrhh") is rrhh.procesar

    def test_tickets_pasa_el_tipo(self):
        with patch.object(A.tickets_handler, "procesar", return_value={"ok": True}) as p:
            A._handler_por_flujo("tickets-avance")("pid-x")
        assert p.call_args[0] == ("pid-x", "avance")

    def test_desconocidos_devuelven_none(self):
        assert A._handler_por_flujo("") is None
        assert A._handler_por_flujo("tickets-inexistente") is None


class TestCustomArgs:
    def test_payload_sendgrid_lleva_custom_args(self):
        capturado = {}

        def _fake(metodo, url, **kw):
            capturado.update(kw.get("json") or {})
            class R:  # respuesta 202 mínima
                status_code = 202
                text = ""
            return R()

        with patch.object(es, "request_con_reintentos", side_effect=_fake):
            es._enviar_via_sendgrid(
                "SG.key", "asesor@gcp.cl", "Asesor", "cliente@test.com",
                "Asunto", "<p>html</p>", "txt", None, None,
                {"page_id": PID, "flujo": "f29"},
            )
        assert capturado["custom_args"] == {"page_id": PID, "flujo": "f29"}

    def test_enviar_inyecta_remitente_en_custom_args(self):
        # es.enviar debe meter el remitente en custom_args para que el Event
        # Webhook sepa a quién confirmarle la entrega.
        import os as _os
        capt = {}
        with patch.dict(_os.environ, {"SENDGRID_API_KEY": "SG.k"}), \
             patch.object(es, "_enviar_via_sendgrid",
                          side_effect=lambda *a, **k: capt.update({"custom_args": a[9]})):
            es.enviar(destinatario="cliente@test.com", nombre="X", mes="Junio 2026",
                      monto="0", nombre_asesor="Sebastián Robles",
                      custom_args={"page_id": PID, "flujo": "f29"})
        assert capt["custom_args"]["page_id"] == PID
        assert capt["custom_args"]["remitente"] == "sebastianrobles@inversoragcp.com"

    def test_sin_custom_args_no_agrega_la_clave(self):
        capturado = {}

        def _fake(metodo, url, **kw):
            capturado.update(kw.get("json") or {})
            class R:
                status_code = 202
                text = ""
            return R()

        with patch.object(es, "request_con_reintentos", side_effect=_fake):
            es._enviar_via_sendgrid(
                "SG.key", "asesor@gcp.cl", "Asesor", "cliente@test.com",
                "Asunto", "<p>html</p>", "txt", None, None,
            )
        assert "custom_args" not in capturado


class TestCC:
    """La celda Email con varias direcciones (Hydroming): 1ra = to, resto = CC.
    SendGrid exige que to/cc/bcc no compartan direcciones."""

    def _capturar_payload(self, cc):
        capturado = {}

        def _fake(metodo, url, **kw):
            capturado.update(kw.get("json") or {})
            class R:
                status_code = 202
                text = ""
            return R()

        with patch.object(es, "request_con_reintentos", side_effect=_fake):
            es._enviar_via_sendgrid(
                "SG.key", "asesor@gcp.cl", "Asesor", "cliente@test.com",
                "Asunto", "<p>html</p>", "txt", None, None, None, cc,
            )
        return capturado["personalizations"][0]

    def test_cc_va_en_el_payload(self):
        p = self._capturar_payload(["dos@test.com", "tres@test.com"])
        assert p["to"] == [{"email": "cliente@test.com"}]
        assert p["cc"] == [{"email": "dos@test.com"}, {"email": "tres@test.com"}]

    def test_sin_cc_no_agrega_la_clave(self):
        p = self._capturar_payload(None)
        assert "cc" not in p

    def test_cc_no_repite_ni_al_destinatario_ni_al_bcc(self):
        # CC que coincide con el destinatario o con una copia BCC no debe
        # duplicarse (SendGrid rechazaria to/cc/bcc con la misma direccion).
        p = self._capturar_payload(["cliente@test.com", es.BCC_EXTRA[0]])
        assert "cc" not in p or all(
            c["email"].lower() != "cliente@test.com" for c in p.get("cc", [])
        )
        bcc = {b["email"].lower() for b in p.get("bcc", [])}
        cc = {c["email"].lower() for c in p.get("cc", [])}
        assert bcc.isdisjoint(cc)   # ninguna direccion en cc y bcc a la vez
