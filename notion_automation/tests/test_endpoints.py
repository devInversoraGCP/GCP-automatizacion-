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
        with patch.object(A.alertas, "avisar_excepcion_admin") as m:
            r = client.post("/enviar-f29", json={}, headers=H)
        assert r.status_code == 400 and not m.called

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
