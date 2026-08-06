"""Tests del guard R4: el botón solo manda correos desde el Contable VIGENTE.

Incidente 06-ago-2026. Al cambiar de mes, la planilla operativa se duplica como
respaldo ('Contable Junio (1)') y después la original se resetea y se renombra
('Contable Julio'). El respaldo se lleva la columna botón, que sigue apuntando
al mismo backend, y sus filas siguen clicables.

Lo que se vio fue un 400 (una fila en blanco del respaldo, sin Rut ni nombre),
pero eso era la versión RUIDOSA del problema: las 99 filas del respaldo que sí
tenían Email habrían mandado un correo real al cliente con datos del mes viejo,
con 200 OK y sin que nadie se enterara. Ahora `_procesar_page` valida la base de
origen antes de componer nada.
"""
import time
from unittest.mock import patch
import pytest
from werkzeug.exceptions import Forbidden
import app as A
import notion_client as nc
import email_sender as es


PID = "12345678-1234-1234-1234-123456789012"
DB_OPERATIVA = "39612147-b3ea-80e7-98e6-dbe3de45b76e"   # 'Contable Julio'
DS_OPERATIVA = nc.DS_CONTABLE_JUNIO                      # 09b12147… (renombrada en sitio)
DS_RESPALDO = "27a12147-b3ea-8293-b889-075f3542d11d"     # 'Contable Junio (1)'


def _page(ds=DS_OPERATIVA, db=DB_OPERATIVA, con_email=True):
    """Fila mínima viable para llegar hasta el envío del correo."""
    parent = {"type": "data_source_id", "database_id": db}
    if ds:
        parent["data_source_id"] = ds
    return {
        "id": PID,
        "parent": parent,
        "last_edited_time": "2026-08-06T12:00:00.000Z",
        "properties": {
            A.P_NOMBRE:       {"type": "title", "title": [{"plain_text": "CLIENTE X"}]},
            A.P_EMAIL:        {"type": "email", "email": "cliente@x.com" if con_email else None},
            A.P_MES:          {"type": "rich_text", "rich_text": [{"plain_text": "Julio 2026"}]},
            A.P_MONTO:        {"type": "number", "number": 12345},
            "Status":         {"type": "status", "status": {"name": "Not started"}},
            A.P_FECHA_ENVIO:  {"type": "date", "date": None},
            A.P_HONORARIOS:   {"type": "number", "number": 0},
            A.P_INFO_VALOR:   {"type": "number", "number": None},
            A.P_INFO_MOTIVO:  {"type": "rich_text", "rich_text": []},
            A.P_ADVISER:      {"type": "people", "people": []},
            A.P_ADJUNTOS:     {"type": "files", "files": []},
            A.P_MSG_ADJUNTOS: {"type": "rich_text", "rich_text": []},
        },
    }


class TestValidacionDeBase:
    def test_la_planilla_operativa_pasa(self):
        with patch.object(A, "_ds_contable_vigente", return_value=DS_OPERATIVA):
            A._validar_contable_vigente(_page())   # no debe lanzar

    def test_el_respaldo_duplicado_se_rechaza(self):
        with patch.object(A, "_ds_contable_vigente", return_value=DS_OPERATIVA), \
             patch.object(nc, "get_database_title", return_value="Contable Junio (1)"), \
             pytest.raises(Forbidden) as exc:
            A._validar_contable_vigente(_page(ds=DS_RESPALDO))
        # el mensaje es lo que ve el asesor en Notion: tiene que decirle qué hacer
        assert "Contable Junio (1)" in exc.value.description

    def test_los_guiones_no_cambian_el_veredicto(self):
        """El data_source_id viene con guiones del page object y sin guiones de
        otras vías; comparar en crudo daría un falso rechazo."""
        with patch.object(A, "_ds_contable_vigente", return_value=DS_OPERATIVA.replace("-", "")):
            A._validar_contable_vigente(_page(ds=DS_OPERATIVA))

    def test_la_planilla_de_ayer_deja_de_estar_autorizada(self):
        """DS_CONTABLES NO es allowlist. El día que se trabaje sobre una copia
        nueva en vez de resetear en sitio, la base de esa lista pasa a ser el
        respaldo: si siguiera autorizada, volveríamos al correo con datos
        viejos, que es justo lo que este guard existe para evitar."""
        with patch.object(A, "_ds_contable_vigente", return_value="ds-septiembre-nuevo"), \
             patch.object(nc, "get_database_title", return_value="Contable Agosto"), \
             pytest.raises(Forbidden):
            A._validar_contable_vigente(_page(ds=DS_OPERATIVA))

    def test_si_el_search_falla_la_planilla_conocida_sigue_enviando(self, monkeypatch):
        """El cinturón vive dentro de _ds_contable_vigente: si el search de Notion
        se cae, cae al DS conocido y los asesores siguen pudiendo enviar."""
        import reconciliar
        monkeypatch.setattr(A, "_ds_vigente_cache", (0.0, ""))
        monkeypatch.setattr(reconciliar, "resolver_ds_actual",
                            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("api caida")))
        A._validar_contable_vigente(_page(ds=DS_OPERATIVA))   # no debe lanzar

    def test_el_mensaje_nombra_la_planilla_correcta(self):
        """El error que ve el asesor tiene que decirle a dónde ir, no solo que
        se equivocó."""
        import reconciliar
        with patch.object(A, "_ds_contable_vigente", return_value=DS_OPERATIVA), \
             patch.object(nc, "get_database_title", return_value="Contable Junio (1)"), \
             patch.object(reconciliar, "nombre_base_actual", return_value="Contable Agosto"), \
             pytest.raises(Forbidden) as exc:
            A._validar_contable_vigente(_page(ds=DS_RESPALDO))
        assert "Contable Junio (1)" in exc.value.description
        assert "Contable Agosto" in exc.value.description

    def test_sin_data_source_resuelve_por_database_id(self):
        with patch.object(A, "_ds_contable_vigente", return_value=DS_OPERATIVA), \
             patch.object(nc, "get_data_source_id", return_value=DS_OPERATIVA) as m:
            A._validar_contable_vigente(_page(ds=None))
        assert m.call_args[0][0] == DB_OPERATIVA

    def test_base_indeterminable_deja_pasar(self):
        """Fail-open a propósito: si Notion cambia la forma del page object,
        cortar TODOS los envíos sería peor que el riesgo que cubre el guard."""
        with patch.object(A, "_ds_contable_vigente", return_value=DS_OPERATIVA):
            A._validar_contable_vigente({"id": PID, "parent": {}})


class TestCacheDeLaVigente:
    """El guard consulta la vigente en CADA clic; sin caché, cada clic paga un
    search a Notion. El TTL corto (5 min) hace que un cambio de mes se note solo,
    sin reiniciar el servicio."""

    @pytest.fixture(autouse=True)
    def _limpiar(self, monkeypatch):
        monkeypatch.setattr(A, "_ds_vigente_cache", (0.0, ""))

    def test_el_segundo_clic_no_vuelve_a_consultar(self, monkeypatch):
        import reconciliar
        llamadas = []
        monkeypatch.setattr(reconciliar, "resolver_ds_actual",
                            lambda *a, **k: (llamadas.append(1), "ds-vigente")[1])
        assert A._ds_contable_vigente() == "ds-vigente"
        assert A._ds_contable_vigente() == "ds-vigente"
        assert len(llamadas) == 1

    def test_vencido_el_ttl_vuelve_a_consultar(self, monkeypatch):
        import reconciliar
        llamadas = []
        monkeypatch.setattr(reconciliar, "resolver_ds_actual",
                            lambda *a, **k: (llamadas.append(1), "ds-vigente")[1])
        A._ds_contable_vigente()
        # simula que pasó el TTL: el cambio de mes tiene que verse sin reiniciar
        monkeypatch.setattr(A, "_ds_vigente_cache",
                            (time.time() - A._DS_VIGENTE_TTL_S - 1, "ds-viejo"))
        assert A._ds_contable_vigente() == "ds-vigente"
        assert len(llamadas) == 2


class TestGuardEnElFlujoCompleto:
    def test_un_clic_en_el_respaldo_no_manda_correo(self):
        with patch.object(nc, "get_page", return_value=_page(ds=DS_RESPALDO)), \
             patch.object(A, "_ds_contable_vigente", return_value=DS_OPERATIVA), \
             patch.object(nc, "get_database_title", return_value="Contable Junio (1)"), \
             patch.object(es, "enviar") as m_enviar, \
             patch.object(nc, "update_props") as m_update, \
             pytest.raises(Forbidden):
            A._procesar_page(PID)
        assert not m_enviar.called and not m_update.called

    def test_un_clic_en_la_operativa_si_manda(self):
        with patch.object(nc, "get_page", return_value=_page()), \
             patch.object(A, "_ds_contable_vigente", return_value=DS_OPERATIVA), \
             patch.object(nc, "derivar_month_desde_base", return_value="Julio 2026"), \
             patch.object(es, "enviar", return_value="asesor@gcp.com") as m_enviar, \
             patch.object(nc, "update_props"), \
             patch.object(A.alertas, "avisar_fallo_asesor"):
            r = A._procesar_page(PID)
        assert r["ok"] is True and m_enviar.called

    def test_el_403_avisa_al_admin_por_el_endpoint(self):
        """El asesor ve el error en Notion; el admin tiene que enterarse de que
        alguien está apretando el botón en una planilla vieja."""
        A._dedupe.clear()
        client = A.app.test_client()
        with patch.object(nc, "get_page", return_value=_page(ds=DS_RESPALDO)), \
             patch.object(A, "_ds_contable_vigente", return_value=DS_OPERATIVA), \
             patch.object(nc, "get_database_title", return_value="Contable Junio (1)"), \
             patch.object(es, "enviar") as m_enviar, \
             patch.object(A.alertas, "avisar_boton_rechazado") as m_aviso:
            r = client.post("/enviar-f29", json={"data": {"id": PID}},
                            headers={"X-AuditAI-Secret": "test-secret"})
        assert r.status_code == 403 and not m_enviar.called
        assert m_aviso.call_args[0][0] == "F29" and m_aviso.call_args[0][1] == 403
