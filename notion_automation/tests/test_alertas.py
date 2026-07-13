"""Tests del módulo de alertas (Fase 1) y del cc al admin en email_sender.
Todo mockeado: nunca se manda un correo de verdad."""
import os
from unittest.mock import patch, MagicMock
import alertas
import email_sender as es


class TestAdminEmails:
    def test_dos_correos_con_espacios(self, monkeypatch):
        monkeypatch.setenv("ADMIN_ALERT_EMAIL", " a@x.com , b@y.com ,")
        assert es.admin_emails() == ["a@x.com", "b@y.com"]

    def test_vacio(self, monkeypatch):
        monkeypatch.delenv("ADMIN_ALERT_EMAIL", raising=False)
        assert es.admin_emails() == []


class TestAvisarFalloAsesor:
    def test_resuelve_email_del_asesor(self):
        with patch.object(es, "enviar_aviso_error", return_value=True) as m:
            alertas.avisar_fallo_asesor("Sebastián Robles", "CLIENTE X", "Junio 2026", "sin Email")
        args = m.call_args[0]
        assert args[0] == "sebastianrobles@inversoragcp.com"
        assert args[1] == "CLIENTE X" and args[2] == "Junio 2026" and args[3] == "sin Email"

    def test_asesor_desconocido_usa_email_from(self):
        with patch.object(es, "enviar_aviso_error", return_value=True) as m:
            alertas.avisar_fallo_asesor("", "CLIENTE X", "", "motivo")
        assert m.call_args[0][0] == os.environ.get("EMAIL_FROM", "notificaciones@inversoragcp.com")

    def test_nunca_propaga_excepcion(self):
        # best-effort: si el envío del aviso revienta, no debe propagarse
        with patch.object(es, "enviar_aviso_error", side_effect=RuntimeError("caído")):
            alertas.avisar_fallo_asesor("Carlos Cereceda", "X", "Y", "Z")  # no debe lanzar


class TestAvisarExcepcionAdmin:
    def test_sin_config_no_llama_a_sendgrid(self, monkeypatch):
        monkeypatch.delenv("ADMIN_ALERT_EMAIL", raising=False)
        monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
        with patch("alertas.requests.post") as m:
            alertas.avisar_excepcion_admin("F29", "p1", ValueError("boom"))
        assert not m.called

    def test_con_config_manda_a_los_admins_con_traceback(self, monkeypatch):
        monkeypatch.setenv("ADMIN_ALERT_EMAIL", "a@x.com,b@y.com")
        monkeypatch.setenv("SENDGRID_API_KEY", "fake")
        with patch("alertas.requests.post") as m:
            m.return_value = MagicMock(status_code=202)
            try:
                raise ValueError("error real")
            except ValueError as exc:
                alertas.avisar_excepcion_admin("RRHH", "p2", exc)
        payload = m.call_args.kwargs["json"]
        to = {t["email"] for t in payload["personalizations"][0]["to"]}
        assert to == {"a@x.com", "b@y.com"}
        cuerpo = payload["content"][0]["value"]
        assert "RRHH" in payload["subject"] and "p2" in cuerpo and "Traceback" in cuerpo

    def test_best_effort_ante_fallo_de_red(self, monkeypatch):
        monkeypatch.setenv("ADMIN_ALERT_EMAIL", "a@x.com")
        monkeypatch.setenv("SENDGRID_API_KEY", "fake")
        with patch("alertas.requests.post", side_effect=RuntimeError("red caída")):
            alertas.avisar_excepcion_admin("F29", "p3", ValueError("x"))  # no debe lanzar


class TestCcAdminEnAvisoError:
    def test_cc_a_los_dos_admins(self, monkeypatch):
        monkeypatch.setenv("SENDGRID_API_KEY", "fake")
        monkeypatch.setenv("ADMIN_ALERT_EMAIL", "a@x.com,b@y.com")
        with patch.object(es.requests, "post") as m:
            m.return_value = MagicMock(status_code=202)
            es.enviar_aviso_error("sebastianrobles@inversoragcp.com", "X", "Junio 2026", "m")
        cc = {c["email"] for c in m.call_args.kwargs["json"]["personalizations"][0]["cc"]}
        assert cc == {"a@x.com", "b@y.com"}

    def test_no_duplica_si_asesor_es_admin(self, monkeypatch):
        monkeypatch.setenv("SENDGRID_API_KEY", "fake")
        monkeypatch.setenv("ADMIN_ALERT_EMAIL", "a@x.com,carlos@z.com")
        with patch.object(es.requests, "post") as m:
            m.return_value = MagicMock(status_code=202)
            es.enviar_aviso_error("carlos@z.com", "X", "Junio 2026", "m")
        cc = [c["email"] for c in m.call_args.kwargs["json"]["personalizations"][0]["cc"]]
        assert cc == ["a@x.com"]  # carlos (destinatario) no se duplica en cc
