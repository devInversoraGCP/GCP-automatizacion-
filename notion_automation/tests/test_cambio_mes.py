"""Tests del cambio de mes: el fallback por RUT del handler F29 itera sobre
DS_CONTABLES en orden (mas reciente primero) y devuelve el primer match.
Si no encuentra el RUT en ningun Contable, devuelve None.

Esto valida la robustez descrita en docs/dev/28-cambio-de-mes-y-rotacion-manual.md §4.
"""
from unittest.mock import patch
import notion_client as nc


def _result(page_id: str) -> list[dict]:
    """Simula la respuesta de query_data_source cuando encontro 1 fila."""
    return [{"id": page_id}]


def _rut_visto_en(ds_id_buscado: str, page_id_esperado: str):
    """Factory de un mock de query_data_source que solo 'tiene' el RUT en
    el data source ds_id_buscado. Otros DS responden vacio."""
    def _fake(ds_id, body=None):
        return [results_id for ds, results_id in [(ds_id_buscado, page_id_esperado)] if ds == ds_id]
    return _fake


class TestFindPageByRutItera:
    def test_encuentra_en_uno_de_varios_contables(self):
        """Si hay 2 Contables en la lista y el RUT solo esta en el segundo,
        find_page_by_rut itera y lo encuentra."""
        contables = [
            ("Contable Julio", "ds-julio"),
            ("Contable Junio", "ds-junio"),
        ]
        page_id_esperado = "page-junio-123"
        fake = lambda ds, body=None: _result(page_id_esperado) if ds == "ds-junio" else []
        with patch.object(nc, "query_data_source", side_effect=fake), \
             patch.object(nc, "DS_CONTABLES", contables):
            r = nc.find_page_by_rut("12.345.678-9")
        assert r == page_id_esperado

    def test_busca_en_orden_mas_reciente_primero(self):
        """Si el RUT esta en varios Contables (ej. historico duplicado),
        devuelve el del Contable mas reciente (el primero de la lista)."""
        contables = [
            ("Contable Julio", "ds-julio"),
            ("Contable Junio", "ds-junio"),
        ]
        fake = lambda ds, body=None: _result(f"page-{ds}")
        with patch.object(nc, "query_data_source", side_effect=fake), \
             patch.object(nc, "DS_CONTABLES", contables):
            r = nc.find_page_by_rut("12.345.678-9")
        assert r == "page-ds-julio"   # Julio es el mas reciente (1ro en la lista)

    def test_no_encontrado_si_no_esta_en_ninguno(self):
        """Si el RUT no esta en ningun Contable conocido, devuelve None."""
        contables = [
            ("Contable Julio", "ds-julio"),
            ("Contable Junio", "ds-junio"),
        ]
        fake = lambda ds, body=None: []
        with patch.object(nc, "query_data_source", side_effect=fake), \
             patch.object(nc, "DS_CONTABLES", contables):
            r = nc.find_page_by_rut("99.999.999-9")
        assert r is None

    def test_lista_con_un_solo_contable(self):
        """Compatibilidad con un solo Contable (situacion previa al cambio de mes)."""
        contables = [("Contable Junio", "ds-junio")]
        page_id_esperado = "page-junio-xyz"
        fake = lambda ds, body=None: _result(page_id_esperado) if ds == "ds-junio" else []
        with patch.object(nc, "query_data_source", side_effect=fake), \
             patch.object(nc, "DS_CONTABLES", contables):
            r = nc.find_page_by_rut("12.345.678-9")
        assert r == page_id_esperado

    def test_lista_vacia_devuelve_none(self):
        """Caso borde: la lista vacia (no deberia pasar, pero validamos)."""
        with patch.object(nc, "DS_CONTABLES", []):
            r = nc.find_page_by_rut("12.345.678-9")
        assert r is None

    def test_alias_legacy_ds_contable_junio_apunta_al_primer_contable(self):
        """El alias DS_CONTABLE_JUNIO (legacy) apunta al primer Contable de la
        lista, para no romper imports viejos. Ver doc 28 §4."""
        # Sin patchear DS_CONTABLES: usar la config real del repo. Hoy es Junio.
        assert nc.DS_CONTABLE_JUNIO == nc.DS_CONTABLES[0][1]
        assert isinstance(nc.DS_CONTABLES, list)
        assert all(isinstance(t, tuple) and len(t) == 2 for t in nc.DS_CONTABLES)

class TestLaVigenteVaPrimero:
    """19-ago-2026 (doc 28 §19). La lista estática es el histórico, no la verdad:
    el día que aparece una planilla nueva (o alguien trabaja sobre una copia en
    vez de renombrar), buscar solo en la lista devuelve la fila del mes ANTERIOR
    — el correo sale con el monto y el mes viejos y marca como enviada la fila
    equivocada. Es el bug que RRHH tuvo el 31-jul; Contable lo arrastraba igual."""

    def test_la_vigente_gana_aunque_el_rut_este_en_las_dos(self):
        contables = [("Contable Julio", "ds-viejo")]
        fake = lambda ds, body=None: _result(f"page-en-{ds}")
        with patch.object(nc, "query_data_source", side_effect=fake), \
             patch.object(nc, "DS_CONTABLES", contables):
            assert nc.find_page_by_rut("12.345.678-9", "ds-agosto") == "page-en-ds-agosto"

    def test_si_no_esta_en_la_vigente_cae_al_historico(self):
        """Un clic en una fila de un mes cerrado sigue resolviendo (el guard R4
        decide después si se manda o no)."""
        contables = [("Contable Julio", "ds-viejo")]
        fake = lambda ds, body=None: _result("page-vieja") if ds == "ds-viejo" else []
        with patch.object(nc, "query_data_source", side_effect=fake), \
             patch.object(nc, "DS_CONTABLES", contables):
            assert nc.find_page_by_rut("12.345.678-9", "ds-agosto") == "page-vieja"

    def test_no_consulta_dos_veces_el_mismo_ds(self):
        """Cuando la vigente ya está en la lista (el caso normal: la planilla se
        renombra en sitio y el id no cambia) no se paga la query dos veces."""
        contables = [("Contable Julio", "ds-mismo")]
        vistos = []
        def fake(ds, body=None):
            vistos.append(ds)
            return []
        with patch.object(nc, "query_data_source", side_effect=fake), \
             patch.object(nc, "DS_CONTABLES", contables):
            nc.find_page_by_rut("12.345.678-9", "ds-mismo")
        assert vistos == ["ds-mismo"]

    def test_sin_vigente_se_comporta_como_antes(self):
        contables = [("Contable Julio", "ds-julio")]
        fake = lambda ds, body=None: _result("page-julio") if ds == "ds-julio" else []
        with patch.object(nc, "query_data_source", side_effect=fake), \
             patch.object(nc, "DS_CONTABLES", contables):
            assert nc.find_page_by_rut("12.345.678-9") == "page-julio"
