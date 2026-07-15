"""Tests del fallback de Email por RUT en la base madre para el flujo F29.

Antes, si la fila del Contable llegaba con la columna Email vacía, el F29 se
rechazaba de inmediato — aunque el correo del cliente SÍ estuviera cargado en
la base madre (visto 15-jul: CONSTRUGLOBAL, Neurocirugia, NATALIA, ZOE). El
handler RRHH ya hacía este lookup; ahora F29 también, con el helper compartido
nc.buscar_email_en_central. La validación de formato (email_sender) sigue
cortando cualquier basura que devuelva la central.
"""
from unittest.mock import patch
import app as A
import notion_client as nc
import email_sender as es

PID = "12345678-1234-1234-1234-123456789012"
DB_ID = "abcdef12-1234-1234-1234-123456789abc"


def _page(email="", rut="11111111-1", nombre="CLIENTE DEMO SPA"):
    return {
        "id": PID,
        "parent": {"database_id": DB_ID},
        "last_edited_time": "2026-07-13T12:00:00.000Z",
        "properties": {
            A.P_NOMBRE:       {"type": "title", "title": [{"plain_text": nombre}]},
            A.P_EMAIL:        {"type": "email", "email": email or None},
            "Rut":            {"type": "rich_text",
                               "rich_text": [{"plain_text": rut}] if rut else []},
            A.P_MES:          {"type": "rich_text", "rich_text": [{"plain_text": "Junio 2026"}]},
            A.P_MONTO:        {"type": "number", "number": 12345},
            "Status":         {"type": "status", "status": {"name": "Not started"}},
            A.P_FECHA_ENVIO:  {"type": "date", "date": None},
            A.P_HONORARIOS:   {"type": "number", "number": 0},
            A.P_INFO_VALOR:   {"type": "number", "number": None},
            A.P_INFO_MOTIVO:  {"type": "rich_text", "rich_text": []},
            A.P_ADVISER:      {"type": "people", "people": [{"name": "Sebastián Robles"}]},
            A.P_ADJUNTOS:     {"type": "files", "files": []},
            A.P_MSG_ADJUNTOS: {"type": "rich_text", "rich_text": []},
        },
    }


class TestFallbackF29:
    def test_email_vacio_se_recupera_de_la_central_y_envia(self):
        recuperado = "cliente.recuperado@example.com"   # ficticio: nunca PII real en el repo
        with patch.object(nc, "get_page", return_value=_page(email="")), \
             patch.object(nc, "derivar_month_desde_base", return_value="Junio 2026"), \
             patch.object(nc, "buscar_email_en_central", return_value=recuperado) as look, \
             patch.object(es, "enviar", return_value="asesor@gcp.com") as m_enviar, \
             patch.object(nc, "update_props"), \
             patch.object(A.alertas, "avisar_fallo_asesor") as m_alerta:
            r = A._procesar_page(PID)
        assert r["ok"] is True
        assert look.called
        assert m_enviar.call_args.kwargs["destinatario"] == recuperado
        assert not m_alerta.called

    def test_email_propio_no_dispara_lookup(self):
        # Si la fila ya trae Email, no se toca la central (no override).
        with patch.object(nc, "get_page", return_value=_page(email="cliente@x.com")), \
             patch.object(nc, "derivar_month_desde_base", return_value="Junio 2026"), \
             patch.object(nc, "buscar_email_en_central") as look, \
             patch.object(es, "enviar", return_value="asesor@gcp.com") as m_enviar, \
             patch.object(nc, "update_props"), \
             patch.object(A.alertas, "avisar_fallo_asesor"):
            r = A._procesar_page(PID)
        assert r["ok"] is True
        assert not look.called
        assert m_enviar.call_args.kwargs["destinatario"] == "cliente@x.com"

    def test_sin_email_ni_en_central_avisa(self):
        with patch.object(nc, "get_page", return_value=_page(email="")), \
             patch.object(nc, "derivar_month_desde_base", return_value="Junio 2026"), \
             patch.object(nc, "buscar_email_en_central", return_value=None), \
             patch.object(es, "enviar") as m_enviar, \
             patch.object(nc, "update_props"), \
             patch.object(A.alertas, "avisar_fallo_asesor") as m_alerta:
            r = A._procesar_page(PID)
        assert r["ok"] is False and "Email" in r["motivo"]
        assert not m_enviar.called
        assert m_alerta.called

    def test_central_devuelve_basura_la_validacion_la_corta(self):
        # Ricardina: la central trae "SOLO WATHSAPP" — enviar() debe rechazarlo
        # con ValueError (validación de formato), no mandarlo a SendGrid.
        with patch.object(nc, "get_page", return_value=_page(email="")), \
             patch.object(nc, "derivar_month_desde_base", return_value="Junio 2026"), \
             patch.object(nc, "buscar_email_en_central", return_value="SOLO WATHSAPP"), \
             patch.object(nc, "update_props"), \
             patch.object(A.alertas, "avisar_fallo_asesor") as m_alerta:
            r = A._procesar_page(PID)
        assert r["ok"] is False
        assert m_alerta.called
        # el motivo es el de la validación de formato, sin filtrar el valor
        assert "valida" in m_alerta.call_args[0][3].lower()


class TestHelperBuscarEmailCentral:
    def test_rut_vacio_devuelve_none_sin_query(self):
        with patch.object(nc, "query_data_source") as q:
            assert nc.buscar_email_en_central("") is None
        assert not q.called

    def test_encuentra_email(self):
        fila = {"properties": {"email": {"type": "email", "email": "x@y.cl"}}}
        with patch.object(nc, "query_data_source", return_value=[fila]):
            assert nc.buscar_email_en_central("11111111-1") == "x@y.cl"

    def test_sin_resultados_devuelve_none(self):
        with patch.object(nc, "query_data_source", return_value=[]):
            assert nc.buscar_email_en_central("00000000-0") is None

    def test_excepcion_no_propaga(self):
        # Si la central está caída, se sigue sin email (R5), no se tumba el envío.
        with patch.object(nc, "query_data_source", side_effect=RuntimeError("500")):
            assert nc.buscar_email_en_central("11111111-1") is None
