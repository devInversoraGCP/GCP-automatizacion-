"""Tests de los endpoints Flask: guard del WEBHOOK_SECRET (Fase 0.2), captura
global de excepciones (Fase 1.1), dedupe anti-doble-correo (Fase 2.2) y /health."""
import os
from unittest.mock import patch
import pytest
import app as A
import notion_client as nc

H = {"X-AuditAI-Secret": "test-secret"}
PID = "12345678-1234-1234-1234-123456789012"


@pytest.fixture()
def client():
    A._dedupe.clear()
    return A.app.test_client()


class TestGuardSecreto:
    def test_sin_secreto_en_servidor_da_503(self, client, monkeypatch):
        monkeypatch.delenv("WEBHOOK_SECRET", raising=False)
        r = client.post("/enviar-f29", json={"page_id": PID})
        assert r.status_code == 503

    def test_header_incorrecto_da_401(self, client):
        r = client.post("/enviar-f29", json={}, headers={"X-AuditAI-Secret": "MALO"})
        assert r.status_code == 401

    def test_header_correcto_pasa_el_guard(self, client):
        # payload vacío -> 400 (pasó el guard, falló la identificación)
        r = client.post("/enviar-f29", json={}, headers=H)
        assert r.status_code == 400


class TestHealth:
    def test_health_expone_flags(self, client):
        body = client.get("/health").get_json()
        assert body["ok"] is True
        assert body["webhook_secret_configurado"] is True
        assert "admin_alerts_configurados" in body


class TestCapturaExcepciones:
    def test_excepcion_no_prevista_avisa_admin_y_da_500(self, client):
        with patch.object(nc, "get_page", side_effect=RuntimeError("Notion caído")), \
             patch.object(A.alertas, "avisar_excepcion_admin") as m:
            r = client.post("/enviar-f29", json={"page_id": PID}, headers=H)
        assert r.status_code == 500
        assert m.called
        flujo, pid, exc = m.call_args[0]
        assert flujo == "F29" and pid == PID and isinstance(exc, RuntimeError)

    def test_abort_no_dispara_aviso_de_excepcion(self, client):
        # un 400 por payload vacío NO debe tratarse como excepción no prevista
        with patch.object(A.alertas, "avisar_excepcion_admin") as m, \
             patch.object(A.alertas, "avisar_boton_rechazado"):
            r = client.post("/enviar-f29", json={}, headers=H)
        assert r.status_code == 400 and not m.called


class TestParidadDeIdentificacion:
    """Incidente 06-ago-2026: el fallback de payload page-object (data.id/entity.id,
    el que mandan las automatizaciones nuevas de Notion) estaba SOLO en el webhook
    generico. /enviar-f29 devolvia 400 con payloads que RRHH aceptaba sin problema.
    """

    @pytest.mark.parametrize("payload,ruta", [
        ({"data": {"id": PID, "object": "page"}}, "data.id"),
        ({"entity": {"id": PID}}, "entity.id"),
        ({"source": {"page_id": PID}}, "source.page_id"),
        ({"Rut": "76.123.456-7"}, "Rut"),
    ])
    def test_todas_las_formas_se_identifican(self, payload, ruta):
        assert A._buscar_identificador_base(payload) == (
            payload.get("Rut") or PID, ruta)

    def test_payload_sin_nada_util_no_identifica(self):
        assert A._buscar_identificador_base({"foo": "bar"}) == ("", "")

    def test_f29_acepta_el_payload_page_object(self, client):
        # el caso exacto del incidente: antes daba 400
        with patch.object(A, "_procesar_page", return_value={"ok": True}) as m:
            r = client.post("/enviar-f29", json={"data": {"id": PID}}, headers=H)
        assert r.status_code == 200 and m.call_args[0][0] == PID

    def test_f29_identifica_por_customers_si_no_hay_rut(self, client):
        with patch.object(nc, "find_page_by_title_generico", return_value=PID) as f, \
             patch.object(A, "_ds_contable_vigente", return_value="ds-contable"), \
             patch.object(A, "_procesar_page", return_value={"ok": True}):
            r = client.post("/enviar-f29", json={"Customers": "EMPRESA X"}, headers=H)
        assert r.status_code == 200
        # 'Customers' es title: debe usar el filtro title, no rich_text
        assert f.call_args[0][2] == A.P_NOMBRE

    def test_rrhh_sigue_aceptando_lo_mismo(self, client):
        with patch.object(A.rrhh_handler, "procesar", return_value={"ok": True}) as m:
            r = client.post("/webhook/rrhh", json={"entity": {"id": PID}}, headers=H)
        assert r.status_code == 200 and m.call_args[0][0] == PID


class TestAvisoDeBotonRechazado:
    """Antes, un abort() dejaba al asesor con un error en Notion y a nadie enterado."""

    def test_el_400_avisa_al_admin(self, client):
        with patch.object(A.alertas, "avisar_boton_rechazado") as m:
            r = client.post("/enviar-f29", json={}, headers=H)
        assert r.status_code == 400 and m.called
        flujo, codigo = m.call_args[0][0], m.call_args[0][1]
        assert flujo == "F29" and codigo == 400

    def test_el_404_de_un_webhook_avisa_con_su_flujo(self, client):
        with patch.object(nc, "find_page_by_rut_generico", return_value=None), \
             patch.object(A.alertas, "avisar_boton_rechazado") as m:
            r = client.post("/webhook/rrhh", json={"CLIENTE": "NO EXISTE"}, headers=H)
        assert r.status_code == 404 and m.called
        assert m.call_args[0][0] == "RRHH" and m.call_args[0][1] == 404

    def test_el_401_no_llega_a_avisar(self, client):
        # el guard del secreto corre ANTES del try; ademas alertas filtra 401/503
        with patch.object(A.alertas, "avisar_boton_rechazado") as m:
            r = client.post("/webhook/rrhh", json={}, headers={"X-AuditAI-Secret": "MALO"})
        assert r.status_code == 401 and not m.called

    def test_rut_no_se_filtra_al_alert(self, client):
        # si la excepción ocurre antes de resolver el page_id, el alert no lleva el RUT
        with patch.object(nc, "find_page_by_rut", side_effect=RuntimeError("timeout")), \
             patch.object(A.alertas, "avisar_excepcion_admin") as m:
            r = client.post("/enviar-f29", json={"Rut": "11.111.111-1"}, headers=H)
        assert r.status_code == 500
        assert m.call_args[0][1] == ""  # page_id vacío, no el RUT


class TestDedupe:
    def test_doble_click_exitoso_procesa_una_vez(self, client):
        with patch.object(A, "_procesar_page", return_value={"ok": True, "remitente": "x"}) as m:
            r1 = client.post("/enviar-f29", json={"page_id": PID}, headers=H)
            r2 = client.post("/enviar-f29", json={"page_id": PID}, headers=H)
        assert r1.get_json()["ok"] is True and "duplicado" not in r1.get_json()
        assert r2.get_json().get("duplicado") is True
        assert m.call_count == 1

    def test_fallo_libera_y_permite_reintento(self, client):
        with patch.object(A, "_procesar_page", return_value={"ok": False, "motivo": "x"}) as m:
            client.post("/enviar-f29", json={"page_id": PID}, headers=H)
            r2 = client.post("/enviar-f29", json={"page_id": PID}, headers=H)
        assert r2.get_json().get("duplicado") is not True
        assert m.call_count == 2

    def test_excepcion_libera_el_dedupe(self, client):
        with patch.object(A, "_procesar_page", side_effect=RuntimeError("boom")), \
             patch.object(A.alertas, "avisar_excepcion_admin"):
            client.post("/enviar-f29", json={"page_id": PID}, headers=H)
        assert PID not in A._dedupe


# Bucle de correos del 05-ago-2026: un fallo por dato faltante liberaba el dedupe,
# así que cada clic del asesor volvía a procesar y disparaba otro par de avisos.
MOTIVO_SIN_MONTO = ("fila sin MONTO IMPOSICIONES| — es el dato principal del correo. "
                    "Cárgalo en la planilla y vuelve a apretar el botón.")


class TestDedupeFalloPersistente:
    def test_falta_de_dato_no_libera_el_dedupe(self, client):
        with patch.object(A, "_procesar_page",
                          return_value={"ok": False, "motivo": MOTIVO_SIN_MONTO}) as m:
            client.post("/enviar-f29", json={"page_id": PID}, headers=H)
            r2 = client.post("/enviar-f29", json={"page_id": PID}, headers=H)
        # el segundo clic se ignora: sin editar la fila daría el mismo fallo
        assert r2.get_json().get("duplicado") is True
        assert m.call_count == 1

    def test_fallo_transitorio_si_permite_reintento(self, client):
        with patch.object(A, "_procesar_page",
                          return_value={"ok": False, "motivo": "error SMTP: connection timed out"}) as m:
            client.post("/enviar-f29", json={"page_id": PID}, headers=H)
            client.post("/enviar-f29", json={"page_id": PID}, headers=H)
        assert m.call_count == 2

    def test_clasificacion_de_persistentes(self):
        assert A._fallo_persistente(MOTIVO_SIN_MONTO) is True
        assert A._fallo_persistente("fila sin Email (ni en la fila ni en la base central)") is True
        assert A._fallo_persistente("fila sin CLIENTE (necesario para el asunto y cuerpo)") is True
        # transitorios / no clasificados: se liberan como siempre
        assert A._fallo_persistente("error SMTP: timeout") is False
        assert A._fallo_persistente("") is False


class TestDedupeUnidad:
    def test_reservar_liberar(self):
        A._dedupe.clear()
        assert A._dedupe_reservar(PID) is True
        assert A._dedupe_reservar(PID) is False
        A._dedupe_liberar(PID)
        assert A._dedupe_reservar(PID) is True

    def test_ventana_vencida_se_limpia(self):
        A._dedupe.clear()
        A._dedupe_reservar(PID)
        A._dedupe[PID] -= (A.DEDUPE_VENTANA_S + 1)
        assert A._dedupe_reservar(PID) is True
