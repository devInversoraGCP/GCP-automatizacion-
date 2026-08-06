"""Tests de la columna de aviso `⚠️ Falta monto` en la planilla RRHH (sin red).

Lo que cuidan: que la fórmula que ve el asesor use el MISMO criterio que el gate
del backend (vacío no se envía, 0 explícito sí), y que el setup sea idempotente y
no toque ninguna otra columna.
"""
from unittest.mock import patch
import pytest
import falta_monto as fm


def _schema(**cols):
    base = {fm.MONTO: {"type": "number"}}
    base.update(cols)
    return base


class TestExpresion:
    def test_no_usa_empty_porque_empty_cero_es_true_en_notion(self):
        # Verificado por API el 05-ago-2026: empty(0) == true. Usar empty() marcaría
        # los ceros explícitos, justo al revés de la regla de negocio.
        assert "empty(" not in fm.EXPRESION
        assert 'format(prop("' + fm.MONTO + '")) == ""' in fm.EXPRESION

    def test_excluye_las_filas_de_servicio(self):
        for fila in fm._FILAS_SERVICIO:
            assert fila in fm.EXPRESION

    def test_marca_con_el_texto_visible(self):
        assert "Falta monto" in fm.EXPRESION


class TestAsegurarColumna:
    def test_crea_si_no_existe(self):
        with patch.object(fm.nc, "get_data_source_schema", return_value=_schema()), \
             patch.object(fm.nc, "update_data_source") as upd:
            assert fm.asegurar_columna("ds-1") == fm.CREADA
        # solo escribe ESA columna, ninguna otra
        assert upd.call_args[0][1] == {fm.COL: fm.DEF_COL}

    def test_idempotente_si_ya_esta_igual(self):
        ya = _schema(**{fm.COL: {"type": "formula", "formula": {"expression": fm.EXPRESION}}})
        with patch.object(fm.nc, "get_data_source_schema", return_value=ya), \
             patch.object(fm.nc, "update_data_source") as upd:
            assert fm.asegurar_columna("ds-1") == fm.EXISTIA
        assert not upd.called

    def test_repara_una_expresion_vieja(self):
        # p.ej. la primera versión, que usaba empty() y marcaba los ceros
        vieja = _schema(**{fm.COL: {"type": "formula",
                                    "formula": {"expression": 'if(empty(prop("x")), "a", "")'}}})
        with patch.object(fm.nc, "get_data_source_schema", return_value=vieja), \
             patch.object(fm.nc, "update_data_source") as upd:
            assert fm.asegurar_columna("ds-1") == fm.ACTUALIZADA
        assert upd.call_args[0][1] == {fm.COL: fm.DEF_COL}

    def test_no_pisa_una_columna_de_otro_tipo(self):
        choque = _schema(**{fm.COL: {"type": "rich_text"}})
        with patch.object(fm.nc, "get_data_source_schema", return_value=choque), \
             patch.object(fm.nc, "update_data_source") as upd:
            assert fm.asegurar_columna("ds-1") == fm.CONFLICTO
        assert not upd.called

    def test_dry_no_escribe(self):
        with patch.object(fm.nc, "get_data_source_schema", return_value=_schema()), \
             patch.object(fm.nc, "update_data_source") as upd:
            assert fm.asegurar_columna("ds-1", dry=True) == fm.CREADA
        assert not upd.called

    def test_falla_si_la_base_no_es_rrhh(self):
        with patch.object(fm.nc, "get_data_source_schema", return_value={"Otra": {"type": "number"}}), \
             patch.object(fm.nc, "update_data_source") as upd:
            with pytest.raises(RuntimeError):
                fm.asegurar_columna("ds-1")
        assert not upd.called


class TestContarSinMonto:
    def _fila(self, titulo, monto):
        return {"properties": {
            "RUT": {"type": "title", "title": [{"plain_text": titulo}]},
            fm.MONTO: {"type": "number", "number": monto},
        }}

    def test_cuenta_vacias_y_no_los_ceros(self):
        filas = [self._fila("C1", None), self._fila("C2", 0), self._fila("C3", 500)]
        with patch.object(fm.nc, "query_data_source", return_value=filas):
            assert fm.contar_sin_monto("ds-1") == (1, 3)   # el 0 NO cuenta como faltante

    def test_ignora_las_filas_de_servicio(self):
        filas = [self._fila("RESET_MES", None), self._fila("C1", None)]
        with patch.object(fm.nc, "query_data_source", return_value=filas):
            assert fm.contar_sin_monto("ds-1") == (1, 1)
