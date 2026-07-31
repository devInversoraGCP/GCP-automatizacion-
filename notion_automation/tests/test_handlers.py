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


class TestRRHHCambioDeMes:
    """Regresión del 31-jul-2026: al aparecer RRHH JULIO, el handler seguía
    apuntando a JUNIO y mandaba el correo con el monto y el mes del mes anterior."""

    def test_ds_vigente_resuelve_la_base_del_mes_nuevo(self):
        import reconciliar
        with patch.object(reconciliar, "resolver_ds_actual", return_value="ds-agosto") as m:
            assert rrhh.ds_vigente() == "ds-agosto"
        assert m.call_args[0][0] == "RRHH"

    def test_ds_vigente_cae_al_mas_reciente_si_falla_el_search(self):
        import reconciliar
        with patch.object(reconciliar, "resolver_ds_actual", side_effect=RuntimeError("api caída")):
            assert rrhh.ds_vigente() == rrhh.DS_RRHH[0][1]

    def test_el_fallback_estatico_esta_ordenado_mas_reciente_primero(self):
        assert rrhh.DS_ID == rrhh.DS_RRHH[0][1]

    def test_sin_mes_no_manda_correo_y_avisa(self):
        # Antes caía a un "Junio 2026" fijo y enviaba igual, con el mes errado.
        with patch.object(nc, "get_page", return_value=_page_rrhh()), \
             patch.object(nc, "derivar_month_desde_base", return_value=""), \
             patch.object(es, "enviar") as env, \
             patch.object(alertas, "avisar_fallo_asesor") as m:
            r = rrhh.procesar("p9")
        assert r["ok"] is False and "mes" in r["motivo"].lower()
        assert not env.called          # no se envía nada con un mes inventado
        assert m.called

    def test_sin_monto_no_manda_correo_con_cero(self):
        # Antes enviaba monto="0": el cliente recibia un aviso de que no debe nada.
        page = _page_rrhh()
        page["properties"][rrhh.MONTO] = {"type": "number", "number": None}
        with patch.object(nc, "get_page", return_value=page), \
             patch.object(nc, "derivar_month_desde_base", return_value="Julio 2026"), \
             patch.object(es, "enviar") as env, \
             patch.object(alertas, "avisar_fallo_asesor") as m:
            r = rrhh.procesar("p11")
        assert r["ok"] is False and "MONTO" in r["motivo"]
        assert not env.called
        assert m.called

    def test_monto_cero_explicito_si_se_envia(self):
        # Un 0 cargado a mano es un dato valido, no un olvido.
        page = _page_rrhh()
        page["properties"][rrhh.MONTO] = {"type": "number", "number": 0}
        with patch.object(nc, "get_page", return_value=page), \
             patch.object(nc, "derivar_month_desde_base", return_value="Julio 2026"), \
             patch.object(nc, "update_props"), \
             patch.object(es, "enviar", return_value="seba@x.com") as env:
            r = rrhh.procesar("p12")
        assert r["ok"] is True and env.call_args.kwargs["monto"] == "0"

    def test_usa_el_mes_del_titulo_de_la_base(self):
        with patch.object(nc, "get_page", return_value=_page_rrhh()), \
             patch.object(nc, "derivar_month_desde_base", return_value="Julio 2026"), \
             patch.object(nc, "update_props"), \
             patch.object(es, "enviar", return_value="seba@x.com") as env:
            r = rrhh.procesar("p10")
        assert r["ok"] is True
        assert env.call_args.kwargs["mes"] == "Julio 2026"
        assert "Julio 2026" in env.call_args.kwargs["asunto"]


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


def _page_tickets_constitucion(monto=350000):
    """Fila Tickets de una Constitución completada (con honorario)."""
    p = _page_tickets(tarea="Nueva Empresa SpA")
    p["properties"][tickets.TIPO] = {"type": "multi_select", "multi_select": [{"name": "Constitución"}]}
    p["properties"][tickets.MONTO] = {"type": "number", "number": monto}
    return p


class TestTicketsConstitucion:
    """Correo Completado especial para Constitución: banner de felicitaciones +
    'Honorario a pagar' (sin fecha límite) + datos bancarios (doc 26)."""

    def test_banner_felicitaciones_solo_en_constitucion(self):
        _, pt_const = tickets._bloque_banner_completado("Constitución", True)
        _, pt_gen = tickets._bloque_banner_completado("Certificado", False)
        assert "Felicitaciones" in pt_const and "constituida" in pt_const
        assert "Felicitaciones" not in pt_gen and "completado" in pt_gen.lower()

    def test_monto_acepta_titulo_honorario(self):
        _, pt = tickets._bloque_monto("350000", "", titulo="Honorario a pagar")
        assert "Honorario a pagar" in pt and "$350.000" in pt

    def test_completado_constitucion_arma_banner_honorario_y_banco(self):
        capt = {}
        with patch.object(nc, "get_page", return_value=_page_tickets_constitucion()), \
             patch.object(es, "enviar", side_effect=lambda **kw: capt.update(kw) or "a@gcp.cl"), \
             patch.object(nc, "update_props"):
            r = tickets.procesar("pc", "completado")
        assert r["ok"] is True
        ev = capt["extra_vars"]
        assert "Felicitaciones" in ev["linea_banner"]
        assert "Honorario a pagar" in ev["linea_monto"] and "$350.000" in ev["linea_monto"]
        assert "Santander" in ev["linea_detalle"]          # datos bancarios presentes
        assert "Fecha límite" not in ev["linea_monto"]     # constitución: sin fecha límite

    def test_completado_generico_sin_honorario_ni_felicitaciones(self):
        capt = {}
        # _page_tickets tiene tipo "Certificado" y MONTO None
        with patch.object(nc, "get_page", return_value=_page_tickets()), \
             patch.object(es, "enviar", side_effect=lambda **kw: capt.update(kw) or "a@gcp.cl"), \
             patch.object(nc, "update_props"):
            r = tickets.procesar("pg", "completado")
        assert r["ok"] is True
        ev = capt["extra_vars"]
        assert "Felicitaciones" not in ev["linea_banner"] and "completado" in ev["linea_banner"].lower()
        assert ev["linea_monto"] == ""                     # completado genérico: sin tarjeta de monto

    def test_cobranza_conserva_total_a_pagar(self):
        # el refactor no debe romper Cobranza: sigue diciendo "Total a pagar"
        capt = {}
        page = _page_tickets()
        page["properties"][tickets.MONTO] = {"type": "number", "number": 50000}
        with patch.object(nc, "get_page", return_value=page), \
             patch.object(es, "enviar", side_effect=lambda **kw: capt.update(kw) or "a@gcp.cl"), \
             patch.object(nc, "update_props"):
            tickets.procesar("pcob", "cobranza")
        assert "Total a pagar" in capt["extra_vars"]["linea_monto"]
