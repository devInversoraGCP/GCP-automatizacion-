"""Tests de la prioridad del mes en el handler F29: el título de la base parent
("Contable Julio" -> "Julio 2026") es la FUENTE PRINCIPAL del mes, y el Month de
la fila queda como fallback solo si el título no se puede parsear.

Esto valida la robustez del cambio de mes (Carlos duplica + renombra la base;
las filas conservan Month del mes viejo, pero el correo debe salir con el mes
nuevo, el del título). Ver docs/dev/28-cambio-de-mes-y-rotacion-manual.md §4.
"""
from unittest.mock import patch
import app as A
import notion_client as nc
import email_sender as es


PID = "12345678-1234-1234-1234-123456789012"
DB_ID = "abcdef12-1234-1234-1234-123456789abc"


def _page(month_fila="Junio 2026", email="cliente@x.com", nombre="CLIENTE X"):
    """Página simulada de un Contable. El parent.database_id permite que
    derivar_month_desde_base lo llame; lo mockeamos en cada test."""
    return {
        "id": PID,
        "parent": {"database_id": DB_ID},
        "last_edited_time": "2026-07-13T12:00:00.000Z",
        "properties": {
            A.P_NOMBRE:          {"type": "title", "title": [{"plain_text": nombre}]},
            A.P_EMAIL:           {"type": "email", "email": email},
            A.P_MES:             {"type": "rich_text",
                                  "rich_text": [{"plain_text": month_fila}] if month_fila else []},
            A.P_MONTO:           {"type": "number", "number": 12345},
            "Status":            {"type": "status", "status": {"name": "Not started"}},
            A.P_FECHA_ENVIO:    {"type": "date", "date": None},
            A.P_HONORARIOS:      {"type": "number", "number": 0},
            A.P_INFO_VALOR:      {"type": "number", "number": None},
            A.P_INFO_MOTIVO:     {"type": "rich_text", "rich_text": []},
            A.P_ADVISER:         {"type": "people", "people": []},
            A.P_ADJUNTOS:        {"type": "files", "files": []},
            A.P_MSG_ADJUNTOS:    {"type": "rich_text", "rich_text": []},
        },
    }


class TestPrioridadTituloBase:
    def test_titulo_prevalece_sobre_month_fila(self):
        """Caso real de cambio de mes: Carlos duplica Contable Junio, renombra
        a 'Contable Julio'. Las filas conservan Month='Junio 2026' pero el
        título de la base parent dice 'Julio'. El correo debe usar Julio."""
        with patch.object(nc, "get_page", return_value=_page(month_fila="Junio 2026")), \
             patch.object(nc, "derivar_month_desde_base", return_value="Julio 2026"), \
             patch.object(es, "enviar", return_value="asesor@gcp.com") as m_enviar, \
             patch.object(nc, "update_props"), \
             patch.object(A.alertas, "avisar_fallo_asesor"):
            r = A._procesar_page(PID)
        assert r["ok"] is True
        # El argumento `mes` que llega a enviar es el del título, no el de la fila
        kwargs = m_enviar.call_args.kwargs
        assert kwargs["mes"] == "Julio 2026"

    def test_sin_titulo_usa_month_fila(self):
        """Si el título de la base parent no se puede parsear (ej. base sin el
        patrón 'Contable <Mes>'), usar el Month de la fila como fallback."""
        with patch.object(nc, "get_page", return_value=_page(month_fila="Junio 2026")), \
             patch.object(nc, "derivar_month_desde_base", return_value=""), \
             patch.object(es, "enviar", return_value="asesor@gcp.com") as m_enviar, \
             patch.object(nc, "update_props"), \
             patch.object(A.alertas, "avisar_fallo_asesor"):
            r = A._procesar_page(PID)
        assert r["ok"] is True
        kwargs = m_enviar.call_args.kwargs
        assert kwargs["mes"] == "Junio 2026"

    def test_mes_vacio_y_titulo_parseable_funciona(self):
        """Caso donde el asesor no tipeó Month y el título sí define el mes."""
        with patch.object(nc, "get_page", return_value=_page(month_fila="")), \
             patch.object(nc, "derivar_month_desde_base", return_value="Julio 2026"), \
             patch.object(es, "enviar", return_value="asesor@gcp.com") as m_enviar, \
             patch.object(nc, "update_props"), \
             patch.object(A.alertas, "avisar_fallo_asesor"):
            r = A._procesar_page(PID)
        assert r["ok"] is True
        kwargs = m_enviar.call_args.kwargs
        assert kwargs["mes"] == "Julio 2026"

    def test_mes_y_titulo_vacios_rechaza(self):
        """Sin Month en la fila y título no parseable: sin mes, no se puede
        calcular fecha límite. Equivale a un 404 anterior."""
        with patch.object(nc, "get_page", return_value=_page(month_fila="", email="c@x.com")), \
             patch.object(nc, "derivar_month_desde_base", return_value=""), \
             patch.object(es, "enviar") as m_enviar, \
             patch.object(nc, "update_props"), \
             patch.object(A.alertas, "avisar_fallo_asesor") as m_alerta:
            r = A._procesar_page(PID)
        assert r["ok"] is False and "mes" in r["motivo"]
        assert not m_enviar.called   # no se envió correo
        assert m_alerta.called       # se avisó al asesor del error

    def test_discrepancia_cambia_los_meses(self):
        """Sanity check triple: Julio vs Agosto vs Septiembre — el sistema
        refleja el título sin importar el mes, así queda preparado para
        cualquier temporada del año (feedback del usuario)."""
        for mes_titulo in ["Agosto 2026", "Septiembre 2026", "Enero 2027"]:
            with patch.object(nc, "get_page", return_value=_page(month_fila="Junio 2026")), \
                 patch.object(nc, "derivar_month_desde_base", return_value=mes_titulo), \
                 patch.object(es, "enviar", return_value="asesor@gcp.com") as m_enviar, \
                 patch.object(nc, "update_props"), \
                 patch.object(A.alertas, "avisar_fallo_asesor"):
                A._procesar_page(PID)
            assert m_enviar.call_args.kwargs["mes"] == mes_titulo, (
                f"el correo debe usar el mes del título ({mes_titulo}), "
                f"no el Month de la fila ('Junio 2026')"
            )