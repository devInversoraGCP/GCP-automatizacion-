"""Tests de los handlers RRHH y Tickets: que ahora SÍ avisan al asesor en todo
fallo conocido (antes fallaban en silencio) — Fase 1.1."""
from unittest.mock import patch
import notion_client as nc
import email_sender as es
import alertas
import handlers.rrhh as rrhh
import handlers.tickets as tickets


def _page_rrhh(email="cliente@x.com", nombre="CLIENTE X", asistente="seba"):
    return {
        "properties": {
            rrhh.CLIENTE: {"type": "title", "title": [{"plain_text": nombre}]},
            rrhh.MONTO: {"type": "number", "number": 1000},
            rrhh.RUT: {"type": "rich_text", "rich_text": []},
            rrhh.EMAIL_CLIENTE: {"type": "email", "email": email},
            rrhh.ASISTENTE: {"type": "select", "select": {"name": asistente}},
            rrhh.ADJUNTOS: {"type": "files", "files": []},
            rrhh.MSG_ADJUNTOS: {"type": "rich_text", "rich_text": []},
        },
        "parent": {}, "last_edited_time": "2026-07-12T00:00:00.000Z",
    }


def _page_tickets(email="cliente@x.com", tarea="CLIENTE Y", asignado="Carlos Cereceda"):
    return {
        "properties": {
            tickets.TAREA: {"type": "title", "title": [{"plain_text": tarea}]},
            tickets.TIPO: {"type": "multi_select", "multi_select": [{"name": "Certificado"}]},
            tickets.ESTADO: {"type": "status", "status": {"name": "En curso"}},
            tickets.ASIGNADO: {"type": "people", "people": [{"name": asignado}]},
            tickets.EMAIL_CLIENTE: {"type": "email", "email": email},
            tickets.MENSAJE: {"type": "rich_text", "rich_text": []},
            tickets.MONTO: {"type": "number", "number": None},
            tickets.FECHA_PROM: {},
            tickets.ADJUNTOS: {"type": "files", "files": []},
            tickets.FECHA_LIMITE: {},
            tickets.ASUNTO_COL: {"type": "rich_text", "rich_text": []},
        }
    }


class TestRRHHAvisa:
    def test_sin_email_avisa_al_asesor_resuelto_por_alias(self):
        with patch.object(nc, "get_page", return_value=_page_rrhh(email="")), \
             patch.object(alertas, "avisar_fallo_asesor") as m:
            r = rrhh.procesar("p1")
        assert r["ok"] is False and "Email" in r["motivo"]
        assert m.call_args[0][0] == "Sebastián Robles"  # alias "seba" resuelto

    def test_fallo_de_envio_avisa_con_motivo(self):
        with patch.object(nc, "get_page", return_value=_page_rrhh()), \
             patch.object(nc, "derivar_month_desde_base", return_value="Junio 2026"), \
             patch.object(es, "enviar", side_effect=ValueError("SendGrid HTTP 403")), \
             patch.object(alertas, "avisar_fallo_asesor") as m:
            r = rrhh.procesar("p2")
        assert r["ok"] is False and "403" in r["motivo"]
        assert m.called and "403" in m.call_args[0][3]


class TestTicketsAvisa:
    def test_sin_email_avisa_al_asignado(self):
        with patch.object(nc, "get_page", return_value=_page_tickets(email="")), \
             patch.object(alertas, "avisar_fallo_asesor") as m:
            r = tickets.procesar("p3", "avance")
        assert r["ok"] is False and "Email" in r["motivo"]
        assert m.call_args[0][0] == "Carlos Cereceda"

    def test_excepcion_en_envio_avisa(self):
        with patch.object(nc, "get_page", return_value=_page_tickets()), \
             patch.object(es, "enviar", side_effect=RuntimeError("timeout SMTP")), \
             patch.object(alertas, "avisar_fallo_asesor") as m:
            r = tickets.procesar("p4", "cobranza")
        assert r["ok"] is False and "timeout SMTP" in r["motivo"]
        assert m.called

    def test_tipo_desconocido(self):
        r = tickets.procesar("p5", "tipo_inexistente")
        assert r["ok"] is False and "desconocido" in r["motivo"]
