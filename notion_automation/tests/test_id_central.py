"""Tests de la llave compartida `ID Central` (sin red).

Cubren el plan de estampado (qué ID le toca a cada fila operativa, leído de las
relaciones ya pobladas del sandbox), la idempotencia del backfill y el estampado
recurrente dentro de `reconciliar.aplicar()` (Fase 3, el cron semanal).
"""
import notion_client as nc
import reconciliar as rec
import id_central as idc


def _ficha(idnum, **rels):
    """Ficha del sandbox con sus relaciones ya pobladas."""
    return {"id": idnum, "nombre_norm": f"cliente {idnum}", "nombre_display": f"Cliente {idnum}",
            "rut": None, "rel": {f.rel_sandbox: list(rels.get(f.nombre.lower(), []))
                                 for f in rec.FUENTES}}


def _idx(fichas):
    return rec.Indice(fichas, {}, {}, [])


def _fuentes(*nombres):
    return [f for f in rec.FUENTES if f.nombre in nombres]


class TestPlanEstampado:
    def test_propaga_el_id_a_cada_fila_ligada(self):
        idx = _idx({"sb1": _ficha(101, contable=["c-1"], crm=["m-1"]),
                    "sb2": _ficha(202, contable=["c-2"])})
        destinos, conflictos = idc.plan_estampado(idx, _fuentes("Contable", "CRM"))
        assert destinos == {"c-1": ("Contable", 101), "m-1": ("CRM", 101),
                            "c-2": ("Contable", 202)}
        assert conflictos == {}

    def test_varias_filas_del_mismo_cliente_reciben_el_mismo_id(self):
        # Dos tickets del mismo cliente → ambos llevan su ID (es el mismo cliente).
        idx = _idx({"sb1": _ficha(7, tickets=["t-1", "t-2"])})
        destinos, _ = idc.plan_estampado(idx, _fuentes("Tickets"))
        assert destinos == {"t-1": ("Tickets", 7), "t-2": ("Tickets", 7)}

    def test_fila_no_ligada_no_recibe_nada(self):
        # Solo se estampa lo que cuelga de una relación: nada se inventa.
        idx = _idx({"sb1": _ficha(1, contable=["c-1"])})
        destinos, _ = idc.plan_estampado(idx, _fuentes("Contable"))
        assert "c-huerfana" not in destinos

    def test_ficha_sin_id_se_ignora(self):
        idx = _idx({"sb1": _ficha(None, contable=["c-1"])})
        destinos, _ = idc.plan_estampado(idx, _fuentes("Contable"))
        assert destinos == {}

    def test_fila_de_dos_fichas_es_conflicto_y_no_se_estampa(self):
        # Duplicado en la maestra: la misma fila cuelga de dos fichas → no inventar.
        idx = _idx({"sb1": _ficha(38, rrhh=["r-1"]), "sb2": _ficha(349, rrhh=["r-1"])})
        destinos, conflictos = idc.plan_estampado(idx, _fuentes("RRHH"))
        assert destinos == {}
        assert conflictos == {"r-1": [38, 349]}

    def test_solo_mira_las_fuentes_pedidas(self):
        idx = _idx({"sb1": _ficha(5, contable=["c-1"], crm=["m-1"])})
        destinos, _ = idc.plan_estampado(idx, _fuentes("Contable"))
        assert destinos == {"c-1": ("Contable", 5)}


class TestAsegurarColumna:
    def test_crea_la_columna_si_falta(self, monkeypatch):
        creadas = []
        monkeypatch.setattr(nc, "get_data_source_schema", lambda ds: {"Rut": {"type": "rich_text"}})
        monkeypatch.setattr(nc, "update_data_source", lambda ds, props: creadas.append((ds, props)))
        assert idc.asegurar_columna("ds-1") == idc.CREADA
        assert creadas == [("ds-1", {idc.COL: idc.DEF_COL})]

    def test_si_ya_existe_no_escribe(self, monkeypatch):
        monkeypatch.setattr(nc, "get_data_source_schema", lambda ds: {idc.COL: {"type": "number"}})
        monkeypatch.setattr(nc, "update_data_source", _boom)
        assert idc.asegurar_columna("ds-1") == idc.EXISTIA

    def test_dry_no_escribe(self, monkeypatch):
        monkeypatch.setattr(nc, "get_data_source_schema", lambda ds: {})
        monkeypatch.setattr(nc, "update_data_source", _boom)
        assert idc.asegurar_columna("ds-1", dry=True) == idc.CREADA

    def test_columna_de_otro_tipo_es_conflicto(self, monkeypatch):
        # Alguien creó a mano un 'ID Central' de texto: no se pisa, se reporta.
        monkeypatch.setattr(nc, "get_data_source_schema", lambda ds: {idc.COL: {"type": "rich_text"}})
        monkeypatch.setattr(nc, "update_data_source", _boom)
        assert idc.asegurar_columna("ds-1") == idc.CONFLICTO


def _boom(*a, **k):
    raise AssertionError("no debía escribir")


def _mock_notion(monkeypatch, filas_por_ds, escrituras):
    """Notion falso: esquema con la columna, filas por data source, writes a una lista."""
    monkeypatch.setattr(nc, "get_data_source_schema",
                        lambda ds: {idc.COL: {"type": "number"}} if ds != rec.SANDBOX_DS else {
                            f.rel_sandbox: {"type": "relation", "relation": {"data_source_id": f.ds_id}}
                            for f in rec.FUENTES})
    monkeypatch.setattr(nc, "query_data_source", lambda ds, body=None: filas_por_ds.get(ds, []))
    monkeypatch.setattr(nc, "update_data_source", _boom)
    monkeypatch.setattr(nc, "update_props", lambda pid, props: escrituras.append((pid, props)))
    monkeypatch.setattr(idc.time, "sleep", lambda s: None)
    monkeypatch.setattr(idc, "respaldar", lambda mapa: "(test, sin archivo)")


def _fila(page_id, id_central=None):
    prop = {"type": "number", "number": id_central} if id_central is not None else {}
    return {"id": page_id, "properties": {idc.COL: prop} if prop else {}}


class TestBackfillIdempotente:
    def _correr(self, monkeypatch, valor_actual):
        fuente = _fuentes("Tickets")[0]
        escrituras = []
        _mock_notion(monkeypatch, {fuente.ds_id: [_fila("t-1", valor_actual)]}, escrituras)
        monkeypatch.setattr(rec, "cargar_sandbox", lambda: _idx({"sb1": _ficha(42, tickets=["t-1"])}))
        res = idc.backfill([fuente], dry=False)
        return res, escrituras

    def test_escribe_la_fila_vacia(self, monkeypatch):
        res, escrituras = self._correr(monkeypatch, None)
        assert escrituras == [("t-1", {idc.COL: {"number": 42}})]
        assert res["escritas"] == 1

    def test_no_reescribe_si_ya_tiene_el_mismo_id(self, monkeypatch):
        res, escrituras = self._correr(monkeypatch, 42)
        assert escrituras == []
        assert res["escritas"] == 0

    def test_corrige_si_el_valor_difiere(self, monkeypatch):
        res, escrituras = self._correr(monkeypatch, 99)
        assert escrituras == [("t-1", {idc.COL: {"number": 42}})]

    def test_dry_run_no_escribe_nada(self, monkeypatch):
        fuente = _fuentes("Tickets")[0]
        escrituras = []
        _mock_notion(monkeypatch, {fuente.ds_id: [_fila("t-1")]}, escrituras)
        monkeypatch.setattr(nc, "update_props", _boom)
        monkeypatch.setattr(rec, "cargar_sandbox", lambda: _idx({"sb1": _ficha(42, tickets=["t-1"])}))
        res = idc.backfill([fuente], dry=True)
        assert res["pendientes"] == 1 and escrituras == []


class TestAplicarEstampa:
    """Fase 3: el cron semanal deja la llave puesta en las filas que liga."""

    def _preparar(self, monkeypatch, filas, escrituras, columna_estado=idc.EXISTIA):
        fuente = _fuentes("Tickets")[0]
        monkeypatch.setattr(nc, "query_data_source", lambda ds, body=None: filas)
        monkeypatch.setattr(nc, "update_props", lambda pid, props: escrituras.append((pid, props)))
        monkeypatch.setattr(idc, "asegurar_columna", lambda ds, dry=False: columna_estado)
        monkeypatch.setattr(rec.time, "sleep", lambda s: None)
        # Relación ya alineada con el mes vigente (el caso normal).
        monkeypatch.setattr(nc, "get_data_source_schema", lambda ds: {
            f.rel_sandbox: {"type": "relation", "relation": {"data_source_id": f.ds_id}}
            for f in rec.FUENTES})
        return fuente

    def test_estampa_la_fila_recien_ligada(self, monkeypatch):
        escrituras = []
        fila = {"id": "t-1", "properties": {"Tarea": {"type": "title",
                                                     "title": [{"plain_text": "Cliente Uno"}]}}}
        fuente = self._preparar(monkeypatch, [fila], escrituras)
        idx = _idx({"sb1": {"id": 77, "nombre_norm": "cliente uno", "nombre_display": "Cliente Uno",
                            "rut": None, "rel": {}}})
        idx.por_nombre["cliente uno"] = ["sb1"]
        monkeypatch.setattr(rec, "cargar_sandbox", lambda: idx)
        res = rec.aplicar([fuente], dry=False)
        assert ("t-1", {idc.COL: {"number": 77}}) in escrituras
        assert res["estampados"] == 1

    def test_no_reescribe_si_ya_esta_estampada(self, monkeypatch):
        escrituras = []
        fila = {"id": "t-1", "properties": {
            "Tarea": {"type": "title", "title": [{"plain_text": "Cliente Uno"}]},
            idc.COL: {"type": "number", "number": 77}}}
        fuente = self._preparar(monkeypatch, [fila], escrituras)
        idx = _idx({"sb1": {"id": 77, "nombre_norm": "cliente uno", "nombre_display": "Cliente Uno",
                            "rut": None, "rel": {"Tickets Origen": ["t-1"]}}})
        idx.por_nombre["cliente uno"] = ["sb1"]
        monkeypatch.setattr(rec, "cargar_sandbox", lambda: idx)
        res = rec.aplicar([fuente], dry=False)
        assert res["estampados"] == 0
        assert all(props.get(idc.COL) is None for _pid, props in escrituras)

    def test_ficha_nueva_estampa_su_id_recien_asignado(self, monkeypatch):
        escrituras = []
        fila = {"id": "t-9", "properties": {"Tarea": {"type": "title",
                                                     "title": [{"plain_text": "Cliente Nuevo"}]}}}
        fuente = self._preparar(monkeypatch, [fila], escrituras)
        monkeypatch.setattr(rec, "cargar_sandbox", lambda: _idx({}))
        monkeypatch.setattr(rec.mm, "candidatos_fuzzy", lambda *a, **k: [])
        monkeypatch.setattr(nc, "create_page", lambda ds, props: {
            "id": "sb-nueva", "properties": {rec.COL_ID: {"type": "unique_id",
                                                          "unique_id": {"number": 438}}}})
        res = rec.aplicar([fuente], dry=False)
        assert ("t-9", {idc.COL: {"number": 438}}) in escrituras
        assert res["creados"] == 1 and res["estampados"] == 1

    def test_dry_run_no_escribe_ni_crea_columna(self, monkeypatch):
        fila = {"id": "t-1", "properties": {"Tarea": {"type": "title",
                                                     "title": [{"plain_text": "Cliente Uno"}]}}}
        fuente = _fuentes("Tickets")[0]
        monkeypatch.setattr(nc, "query_data_source", lambda ds, body=None: [fila])
        monkeypatch.setattr(nc, "update_props", _boom)
        monkeypatch.setattr(idc, "asegurar_columna", _boom)
        monkeypatch.setattr(nc, "get_data_source_schema", lambda ds: {
            f.rel_sandbox: {"type": "relation", "relation": {"data_source_id": f.ds_id}}
            for f in rec.FUENTES})
        idx = _idx({"sb1": {"id": 77, "nombre_norm": "cliente uno", "nombre_display": "Cliente Uno",
                            "rut": None, "rel": {}}})
        idx.por_nombre["cliente uno"] = ["sb1"]
        monkeypatch.setattr(rec, "cargar_sandbox", lambda: idx)
        res = rec.aplicar([fuente], dry=True)
        assert res["estampar"] == 1
