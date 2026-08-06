"""Tests de la columna de aviso `⚠️ Falta monto` en las planillas RRHH y Contable
(sin red).

Lo que cuidan: que la fórmula que ve el asesor use el MISMO criterio que el
backend (vacío se marca, 0 explícito no), que sirva para las dos planillas con
sus nombres de columna propios, y que el setup sea idempotente contra la
expresión YA NORMALIZADA por Notion.
"""
from unittest.mock import patch
import pytest
import falta_monto as fm

RRHH = fm.PLANILLAS["rrhh"]
CONTABLE = fm.PLANILLAS["contable"]


def _schema(p, monto_id="pid-monto", **cols):
    base = {p.monto: {"type": "number", "id": monto_id}}
    base.update(cols)
    return base


def _guardada(p, expr, monto_id="pid-monto"):
    """Schema con la columna ya creada, como la devolvería Notion."""
    return _schema(p, monto_id, **{fm.COL: {"type": "formula", "formula": {"expression": expr}}})


class TestExpresion:
    @pytest.mark.parametrize("p", [RRHH, CONTABLE])
    def test_no_usa_empty_porque_empty_cero_es_true_en_notion(self, p):
        # Verificado por API el 05-ago-2026: empty(0) == true. Usar empty() marcaría
        # los ceros explícitos — en Contable eso es "declarado sin movimiento".
        expr = fm.expresion(p)
        assert "empty(" not in expr
        assert f'format(prop("{p.monto}")) == ""' in expr

    @pytest.mark.parametrize("p", [RRHH, CONTABLE])
    def test_excluye_las_filas_de_servicio_por_su_columna_titulo(self, p):
        expr = fm.expresion(p)
        for fila in fm._FILAS_SERVICIO:
            assert f'contains(prop("{p.titulo}"), "{fila}")' in expr

    def test_cada_planilla_apunta_a_su_propia_columna(self):
        assert 'prop("MONTO IMPOSICIONES|")' in fm.expresion(RRHH)
        assert 'prop("Impuestos")' in fm.expresion(CONTABLE)
        assert 'prop("Impuestos")' not in fm.expresion(RRHH)


class TestYaEsLaNuestra:
    """Notion normaliza la expresión al guardarla (prop("X") -> referencia por id,
    not(...) -> !), así que la idempotencia NO puede ser comparación textual."""

    def _normalizada_ok(self, monto_id="pid-monto"):
        return (f'if(and(format({{{{notion:block_property:{monto_id}:db:v}}}}) == "", '
                f'!or(contains({{{{notion:block_property:title:db:v}}}}, "RESET_MES"))), '
                f'"{fm.MARCA}", "")')

    def test_reconoce_la_expresion_normalizada_por_notion(self):
        props = _schema(RRHH)
        assert fm.ya_es_la_nuestra(self._normalizada_ok(), props, RRHH) is True

    def test_la_comparacion_textual_directa_no_alcanzaria(self):
        # guard de regresión: la forma guardada NUNCA es igual a la generada
        assert self._normalizada_ok() != fm.expresion(RRHH)

    def test_detecta_como_vieja_la_version_con_empty(self):
        vieja = f'if(and(empty({{{{notion:block_property:pid-monto:db:v}}}}), true), "{fm.MARCA}", "")'
        assert fm.ya_es_la_nuestra(vieja, _schema(RRHH), RRHH) is False

    def test_rechaza_si_apunta_a_otra_columna(self):
        otra = self._normalizada_ok(monto_id="pid-DISTINTO")
        assert fm.ya_es_la_nuestra(otra, _schema(RRHH), RRHH) is False

    def test_rechaza_una_formula_ajena(self):
        assert fm.ya_es_la_nuestra('if(true, "otra cosa", "")', _schema(RRHH), RRHH) is False


class TestAsegurarColumna:
    def test_crea_si_no_existe(self):
        with patch.object(fm.nc, "get_data_source_schema", return_value=_schema(CONTABLE)), \
             patch.object(fm.nc, "update_data_source") as upd:
            assert fm.asegurar_columna(CONTABLE, "ds-1") == fm.CREADA
        # solo escribe ESA columna, ninguna otra
        assert upd.call_args[0][1] == {fm.COL: fm.def_col(CONTABLE)}

    def test_idempotente_si_ya_esta_bien(self):
        expr = f'format({{{{notion:block_property:pid-monto:db:v}}}}) == "" "{fm.MARCA}"'
        with patch.object(fm.nc, "get_data_source_schema", return_value=_guardada(RRHH, expr)), \
             patch.object(fm.nc, "update_data_source") as upd:
            assert fm.asegurar_columna(RRHH, "ds-1") == fm.EXISTIA
        assert not upd.called

    def test_repara_la_version_vieja_con_empty(self):
        vieja = f'empty({{{{notion:block_property:pid-monto:db:v}}}}) "{fm.MARCA}"'
        with patch.object(fm.nc, "get_data_source_schema", return_value=_guardada(RRHH, vieja)), \
             patch.object(fm.nc, "update_data_source") as upd:
            assert fm.asegurar_columna(RRHH, "ds-1") == fm.ACTUALIZADA
        assert upd.call_args[0][1] == {fm.COL: fm.def_col(RRHH)}

    def test_no_pisa_una_columna_de_otro_tipo(self):
        choque = _schema(RRHH, **{fm.COL: {"type": "rich_text"}})
        with patch.object(fm.nc, "get_data_source_schema", return_value=choque), \
             patch.object(fm.nc, "update_data_source") as upd:
            assert fm.asegurar_columna(RRHH, "ds-1") == fm.CONFLICTO
        assert not upd.called

    def test_dry_no_escribe(self):
        with patch.object(fm.nc, "get_data_source_schema", return_value=_schema(RRHH)), \
             patch.object(fm.nc, "update_data_source") as upd:
            assert fm.asegurar_columna(RRHH, "ds-1", dry=True) == fm.CREADA
        assert not upd.called

    def test_falla_si_la_base_no_tiene_la_columna_de_monto(self):
        with patch.object(fm.nc, "get_data_source_schema", return_value={"Otra": {"type": "number"}}), \
             patch.object(fm.nc, "update_data_source") as upd:
            with pytest.raises(RuntimeError):
                fm.asegurar_columna(CONTABLE, "ds-1")
        assert not upd.called


class TestContarSinMonto:
    def _fila(self, p, titulo, monto):
        return {"properties": {
            p.titulo: {"type": "title", "title": [{"plain_text": titulo}]},
            p.monto: {"type": "number", "number": monto},
        }}

    def test_el_cero_no_cuenta_como_faltante(self):
        # en Contable el 0 es "declarado sin movimiento": es un dato, no un olvido
        filas = [self._fila(CONTABLE, "C1", None), self._fila(CONTABLE, "C2", 0),
                 self._fila(CONTABLE, "C3", 500)]
        with patch.object(fm.nc, "query_data_source", return_value=filas):
            assert fm.contar_sin_monto(CONTABLE, "ds-1") == (1, 3)

    def test_el_negativo_tampoco(self):
        # saldo a favor
        filas = [self._fila(CONTABLE, "C1", -1500)]
        with patch.object(fm.nc, "query_data_source", return_value=filas):
            assert fm.contar_sin_monto(CONTABLE, "ds-1") == (0, 1)

    def test_ignora_las_filas_de_servicio(self):
        filas = [self._fila(RRHH, "RESET_MES", None),
                 self._fila(RRHH, "ZZ_TEST AuditAI", None),
                 self._fila(RRHH, "Cliente Real", None)]
        with patch.object(fm.nc, "query_data_source", return_value=filas):
            assert fm.contar_sin_monto(RRHH, "ds-1") == (1, 1)
