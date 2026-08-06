"""Tests del módulo de alertas (Fase 1) y del cc al admin en email_sender.
Todo mockeado: nunca se manda un correo de verdad."""
import os
from unittest.mock import patch, MagicMock
import pytest
import alertas
import email_sender as es


class TestAdminEmails:
    def test_dos_correos_con_espacios(self, monkeypatch):
        monkeypatch.setenv("ADMIN_ALERT_EMAIL", " a@x.com , b@y.com ,")
        # dev@ (monitoreo) siempre se agrega al final.
        assert es.admin_emails() == ["a@x.com", "b@y.com", es.MONITOR_EMAIL]

    def test_vacio_incluye_monitoreo(self, monkeypatch):
        monkeypatch.delenv("ADMIN_ALERT_EMAIL", raising=False)
        assert es.admin_emails() == [es.MONITOR_EMAIL]

    def test_no_duplica_si_admin_ya_es_dev(self, monkeypatch):
        monkeypatch.setenv("ADMIN_ALERT_EMAIL", es.MONITOR_EMAIL)
        assert es.admin_emails() == [es.MONITOR_EMAIL]


class TestAvisarFalloAsesor:
    def test_resuelve_email_del_asesor(self):
        with patch.object(es, "enviar_aviso_asesor", return_value=True) as m, \
             patch.object(es, "enviar_aviso_dev", return_value=True):
            alertas.avisar_fallo_asesor("Sebastián Robles", "CLIENTE X", "Junio 2026", "sin Email")
        args = m.call_args[0]
        assert args[0] == "sebastianrobles@inversoragcp.com"
        assert args[1] == "CLIENTE X" and args[2] == "Junio 2026"
        # el 4º arg es el Diagnostico ya clasificado
        assert args[3].categoria == "sin_email"

    def test_asesor_desconocido_usa_email_from(self):
        with patch.object(es, "enviar_aviso_asesor", return_value=True) as m, \
             patch.object(es, "enviar_aviso_dev", return_value=True):
            alertas.avisar_fallo_asesor("", "CLIENTE X", "", "motivo")
        assert m.call_args[0][0] == os.environ.get("EMAIL_FROM", "notificaciones@inversoragcp.com")

    def test_manda_tecnico_al_dev_si_hay_admins(self, monkeypatch):
        monkeypatch.setenv("ADMIN_ALERT_EMAIL", "dev@x.com")
        with patch.object(es, "enviar_aviso_asesor", return_value=True), \
             patch.object(es, "enviar_aviso_dev", return_value=True) as m:
            alertas.avisar_fallo_asesor("Sebastián Robles", "X", "Junio 2026", "sin Email",
                                        flujo="f29", page_id="pid-1")
        assert m.called
        admins, cliente, mes, diag = m.call_args[0]
        # env + dev@ (monitoreo) siempre incluido
        assert admins == ["dev@x.com", es.MONITOR_EMAIL] and diag.categoria == "sin_email"
        assert m.call_args.kwargs["page_id"] == "pid-1"

    def test_sin_admins_igual_manda_a_dev(self, monkeypatch):
        # Aunque no haya ADMIN_ALERT_EMAIL, el técnico igual va a dev@ (monitoreo).
        monkeypatch.delenv("ADMIN_ALERT_EMAIL", raising=False)
        with patch.object(es, "enviar_aviso_asesor", return_value=True), \
             patch.object(es, "enviar_aviso_dev", return_value=True) as m:
            alertas.avisar_fallo_asesor("Sebastián Robles", "X", "Junio 2026", "sin Email")
        assert m.called and m.call_args[0][0] == [es.MONITOR_EMAIL]

    def test_nunca_propaga_excepcion(self):
        # best-effort: si el envío del aviso revienta, no debe propagarse
        with patch.object(es, "enviar_aviso_asesor", side_effect=RuntimeError("caído")), \
             patch.object(es, "enviar_aviso_dev", side_effect=RuntimeError("caído")):
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
        assert to == {"a@x.com", "b@y.com", es.MONITOR_EMAIL}
        cuerpo = payload["content"][0]["value"]
        assert "RRHH" in payload["subject"] and "p2" in cuerpo and "Traceback" in cuerpo

    def test_best_effort_ante_fallo_de_red(self, monkeypatch):
        monkeypatch.setenv("ADMIN_ALERT_EMAIL", "a@x.com")
        monkeypatch.setenv("SENDGRID_API_KEY", "fake")
        with patch("alertas.requests.post", side_effect=RuntimeError("red caída")):
            alertas.avisar_excepcion_admin("F29", "p3", ValueError("x"))  # no debe lanzar


class TestAvisarBotonRechazado:
    """Los abort() del webhook morian en silencio: el asesor veia el error en Notion
    y no se enteraba nadie mas (asi se perdio el caso del 02-ago)."""

    @pytest.fixture(autouse=True)
    def _limpiar_throttle(self):
        alertas._ultimo_aviso.clear()
        yield
        alertas._ultimo_aviso.clear()

    def test_avisa_a_los_admins_con_el_codigo_y_el_detalle(self, monkeypatch):
        monkeypatch.setenv("ADMIN_ALERT_EMAIL", "a@x.com")
        monkeypatch.setenv("SENDGRID_API_KEY", "fake")
        with patch("alertas.requests.post") as m:
            m.return_value = MagicMock(status_code=202)
            alertas.avisar_boton_rechazado("RRHH", 404, "no se encontro fila con ese CLIENTE", "p9")
        payload = m.call_args.kwargs["json"]
        cuerpo = payload["content"][0]["value"]
        assert "404" in payload["subject"] and "RRHH" in payload["subject"]
        assert "p9" in cuerpo and "no se encontro fila" in cuerpo

    @pytest.mark.parametrize("codigo", [401, 503])
    def test_no_avisa_los_codigos_previos_a_autenticar(self, codigo, monkeypatch):
        # ocurren antes de validar el secreto: cualquiera que golpee la URL publica
        # podria disparar correos
        monkeypatch.setenv("ADMIN_ALERT_EMAIL", "a@x.com")
        monkeypatch.setenv("SENDGRID_API_KEY", "fake")
        with patch("alertas.requests.post") as m:
            alertas.avisar_boton_rechazado("RRHH", codigo, "secreto malo")
        assert not m.called

    def test_throttle_evita_el_bucle_de_correos(self, monkeypatch):
        monkeypatch.setenv("ADMIN_ALERT_EMAIL", "a@x.com")
        monkeypatch.setenv("SENDGRID_API_KEY", "fake")
        with patch("alertas.requests.post") as m:
            m.return_value = MagicMock(status_code=202)
            for _ in range(5):
                alertas.avisar_boton_rechazado("RRHH", 400, "payload sin page_id")
        assert m.call_count == 1

    def test_el_throttle_es_por_flujo_y_codigo(self, monkeypatch):
        monkeypatch.setenv("ADMIN_ALERT_EMAIL", "a@x.com")
        monkeypatch.setenv("SENDGRID_API_KEY", "fake")
        with patch("alertas.requests.post") as m:
            m.return_value = MagicMock(status_code=202)
            alertas.avisar_boton_rechazado("RRHH", 400, "x")
            alertas.avisar_boton_rechazado("RRHH", 404, "y")
            alertas.avisar_boton_rechazado("F29", 400, "z")
        assert m.call_count == 3

    def test_best_effort_ante_fallo_de_red(self, monkeypatch):
        monkeypatch.setenv("ADMIN_ALERT_EMAIL", "a@x.com")
        monkeypatch.setenv("SENDGRID_API_KEY", "fake")
        with patch("alertas.requests.post", side_effect=RuntimeError("red caída")):
            alertas.avisar_boton_rechazado("F29", 400, "x")  # no debe lanzar


class TestEnviarAvisoAsesor:
    def _diag(self, **kw):
        import diagnostico
        return diagnostico.diagnosticar("La columna Email no es una direccion de correo valida",
                                        cliente="CLIENTE X", **kw)

    def test_va_solo_al_asesor_y_no_incluye_query_llm(self, monkeypatch):
        monkeypatch.setenv("SENDGRID_API_KEY", "fake")
        with patch.object(es.requests, "post") as m:
            m.return_value = MagicMock(status_code=202)
            es.enviar_aviso_asesor("seba@inversoragcp.com", "CLIENTE X", "Junio 2026", self._diag())
        p = m.call_args.kwargs["json"]["personalizations"][0]
        assert [t["email"] for t in p["to"]] == ["seba@inversoragcp.com"]
        assert "cc" not in p   # el asesor NO recibe copia técnica
        cuerpo = m.call_args.kwargs["json"]["content"][0]["value"]
        # el correo del asesor no debe traer la query para el LLM ni page_id crudo
        assert "QUERY PARA RESOLVER" not in cuerpo and "MCP de Notion" not in cuerpo

    def test_didactico_incluye_pasos(self, monkeypatch):
        monkeypatch.setenv("SENDGRID_API_KEY", "fake")
        with patch.object(es.requests, "post") as m:
            m.return_value = MagicMock(status_code=202)
            es.enviar_aviso_asesor("seba@inversoragcp.com", "CLIENTE X", "Junio 2026", self._diag())
        cuerpo = m.call_args.kwargs["json"]["content"][0]["value"]
        assert "Qué hacer" in cuerpo and "columna Email" in cuerpo

    def _contenidos(self, m):
        """(texto_plano, html) del payload de SendGrid."""
        partes = {c["type"]: c["value"] for c in m.call_args.kwargs["json"]["content"]}
        return partes.get("text/plain", ""), partes.get("text/html", "")

    def test_lleva_el_contacto_de_soporte_en_texto_y_html(self, monkeypatch):
        # el aviso sale de una casilla que no se responde: sin esto el asesor
        # quedaba sin a quién escribirle (pedido del 06-ago-2026)
        monkeypatch.setenv("SENDGRID_API_KEY", "fake")
        with patch.object(es.requests, "post") as m:
            m.return_value = MagicMock(status_code=202)
            es.enviar_aviso_asesor("seba@inversoragcp.com", "CLIENTE X", "Junio 2026", self._diag())
        texto, html = self._contenidos(m)
        for cuerpo in (texto, html):
            assert es.SOPORTE_EMAIL in cuerpo
            assert es.SOPORTE_WSP in cuerpo
        assert es.SOPORTE_WSP_URL in html          # WhatsApp clickeable
        assert f"mailto:{es.SOPORTE_EMAIL}" in html

    def test_el_contacto_aparece_tambien_cuando_no_lo_resuelve_el_asesor(self, monkeypatch):
        # justo el caso donde MÁS necesita saber a quién escribirle
        monkeypatch.setenv("SENDGRID_API_KEY", "fake")
        import diagnostico
        diag = diagnostico.diagnosticar("SendGrid rechazo el envio (HTTP 403): remitente no verificado",
                                        cliente="CLIENTE X")
        assert diag.puede_asesor is False
        with patch.object(es.requests, "post") as m:
            m.return_value = MagicMock(status_code=202)
            es.enviar_aviso_asesor("seba@inversoragcp.com", "CLIENTE X", "Junio 2026", diag)
        texto, html = self._contenidos(m)
        assert es.SOPORTE_WSP in texto and es.SOPORTE_WSP in html

    def test_el_wsp_url_no_lleva_espacios_ni_mas(self):
        # wa.me exige el numero pelado; un '+' o espacios rompen el link
        cola = es.SOPORTE_WSP_URL.rsplit("/", 1)[-1]
        assert cola.isdigit() and cola.startswith("56")


class TestEnviarAvisoDev:
    def _diag(self):
        import diagnostico
        return diagnostico.diagnosticar("La columna Email no es una direccion de correo valida",
                                        flujo="f29", cliente="CLIENTE X", page_id="pid-42")

    def test_va_a_los_admins_con_causa_raiz_y_query(self, monkeypatch):
        monkeypatch.setenv("SENDGRID_API_KEY", "fake")
        with patch.object(es.requests, "post") as m:
            m.return_value = MagicMock(status_code=202)
            es.enviar_aviso_dev(["a@x.com", "b@y.com"], "CLIENTE X", "Junio 2026", self._diag(),
                                motivo="motivo crudo", flujo="f29", page_id="pid-42")
        to = {t["email"] for t in m.call_args.kwargs["json"]["personalizations"][0]["to"]}
        assert to == {"a@x.com", "b@y.com"}
        cuerpo = m.call_args.kwargs["json"]["content"][0]["value"]
        assert "CAUSA RAÍZ" in cuerpo and "QUERY PARA RESOLVER" in cuerpo
        assert "pid-42" in cuerpo and "motivo crudo" in cuerpo

    def test_sin_admins_no_envia(self, monkeypatch):
        monkeypatch.setenv("SENDGRID_API_KEY", "fake")
        with patch.object(es.requests, "post") as m:
            assert es.enviar_aviso_dev([], "X", "Junio 2026", self._diag()) is False
        assert not m.called
