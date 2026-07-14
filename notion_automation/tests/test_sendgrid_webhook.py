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

    def test_bounce_escribe_error_y_avisa_asesor(self, client):
        ev = _evento("bounce", reason="550 mailbox does not exist")
        with patch.object(nc, "get_page", return_value=_page()), \
             patch.object(nc, "update_props") as m, \
             patch.object(A.alertas, "avisar_fallo_asesor") as alerta:
            r = client.post(URL_OK, json=[ev])
        assert r.status_code == 200
        texto = m.call_args[0][1]["Entrega Correo"]["rich_text"][0]["text"]["content"]
        assert texto.startswith("❌ No entregado (bounce)")
        assert "550 mailbox" in texto
        assert alerta.called
        asesor, cliente, mes, motivo = alerta.call_args[0]
        assert asesor == "Sebastián Robles" and cliente == "Cliente Test"
        assert "bounce" in motivo

    def test_delivered_no_avisa_asesor(self, client):
        with patch.object(nc, "get_page", return_value=_page()), \
             patch.object(nc, "update_props"), \
             patch.object(A.alertas, "avisar_fallo_asesor") as alerta:
            client.post(URL_OK, json=[_evento("delivered")])
        assert not alerta.called

    def test_evento_de_copia_bcc_se_ignora(self, client):
        # delivered de la copia del asesor NO debe pisar el estado del cliente
        ev = _evento("delivered", email="sebastianrobles@inversoragcp.com")
        with patch.object(nc, "get_page", return_value=_page()), \
             patch.object(nc, "update_props") as m:
            r = client.post(URL_OK, json=[ev])
        assert r.get_json()["filas_actualizadas"] == 0
        assert not m.called

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
