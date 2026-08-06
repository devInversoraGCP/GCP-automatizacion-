"""Tests de la resolución dinámica de mes y la clasificación fuzzy (sin red)."""
import pytest
import notion_client as nc
import reconciliar as r


def _idx_con(nombre_norm, pid="p1"):
    """Índice mínimo del sandbox con una sola ficha del nombre dado."""
    fichas = {pid: {"id": 1, "nombre_norm": nombre_norm, "nombre_display": nombre_norm,
                    "rut": None, "rel": {}}}
    return r.Indice(fichas, {}, {nombre_norm: [pid]}, [nombre_norm])


class TestClasificarFuzzy:
    def test_muy_parecido_autoliga(self, monkeypatch):
        idx = _idx_con("comercial los andes")
        monkeypatch.setattr(r.mm, "candidatos_fuzzy", lambda *a, **k: [("comercial los andes", 94)])
        assert r.clasificar(None, "comercail los andes", idx) == (r.MATCH_FUZZY, "p1")

    def test_parecido_medio_a_carlos(self, monkeypatch):
        idx = _idx_con("comercial los andes")
        monkeypatch.setattr(r.mm, "candidatos_fuzzy", lambda *a, **k: [("comercial los andes", 78)])
        assert r.clasificar(None, "algo parecido", idx) == (r.A_CARLOS, None)

    def test_enumerador_distinto_no_autoliga(self, monkeypatch):
        # 95% de parecido pero SPV I vs II → a Carlos (no auto-liga).
        idx = _idx_con("social up spv ii")
        monkeypatch.setattr(r.mm, "candidatos_fuzzy", lambda *a, **k: [("social up spv ii", 95)])
        assert r.clasificar(None, "social up spv i", idx) == (r.A_CARLOS, None)

    def test_empate_entre_dos_fichas_a_carlos(self, monkeypatch):
        idx = _idx_con("banco del sur")
        monkeypatch.setattr(r.mm, "candidatos_fuzzy",
                            lambda *a, **k: [("banco del sur", 90), ("banco del sol", 89)])
        assert r.clasificar(None, "banco de sur", idx) == (r.A_CARLOS, None)

    def test_sin_parecido_sin_rut_es_probable_nuevo(self, monkeypatch):
        idx = _idx_con("comercial los andes")
        monkeypatch.setattr(r.mm, "candidatos_fuzzy", lambda *a, **k: [])
        assert r.clasificar(None, "zeta digital", idx) == (r.PROBABLE_NUEVO, None)

    def test_rut_valido_sin_ficha_es_nuevo(self, monkeypatch):
        idx = _idx_con("cualquiera")
        monkeypatch.setattr(r.mm, "candidatos_fuzzy", lambda *a, **k: [])
        assert r.clasificar("12345678-5", "otro nombre", idx) == (r.NUEVO, None)


class TestSincronizarRelacion:
    """Cambio de mes de RRHH: la relación debe seguir a la base nueva. Notion
    ignora en silencio los enlaces a otro data source, así que una relación
    desalineada no liga nada (31-jul-2026)."""

    def _fuente(self, ds="ds-julio"):
        return r.Fuente("RRHH", ds, "RUT", "CLIENTE", "RRHH Origen", "RRHH", prefijo="RRHH")

    def _schema(self, ds):
        return {"RRHH Origen": {"type": "relation", "relation": {"data_source_id": ds}}}

    def test_si_ya_apunta_al_mes_vigente_no_toca_nada(self, monkeypatch):
        monkeypatch.setattr(nc, "update_data_source", _explota)
        assert r.sincronizar_relacion(self._fuente(), self._schema("ds-julio"), dry=False) == r.ALINEADA

    def test_dry_no_reapunta_pero_lo_reporta(self, monkeypatch):
        monkeypatch.setattr(nc, "update_data_source", _explota)
        assert r.sincronizar_relacion(self._fuente(), self._schema("ds-junio"), dry=True) == r.PENDIENTE

    def test_reapunta_al_data_source_nuevo(self, monkeypatch):
        llamadas = []
        monkeypatch.setattr(nc, "update_data_source", lambda ds, props: llamadas.append(props))
        monkeypatch.setattr(r, "_respaldar_relacion", lambda *a: "(respaldo)")
        assert r.sincronizar_relacion(self._fuente(), self._schema("ds-junio"), dry=False) == r.REAPUNTADA
        assert llamadas[0]["RRHH Origen"]["relation"]["data_source_id"] == "ds-julio"

    def test_respalda_antes_de_borrar_los_enlaces(self, monkeypatch):
        respaldos = []
        monkeypatch.setattr(nc, "update_data_source", lambda ds, props: None)
        monkeypatch.setattr(r, "_respaldar_relacion", lambda rel, viejo, idx: respaldos.append(viejo) or "(r)")
        r.sincronizar_relacion(self._fuente(), self._schema("ds-junio"), dry=False)
        assert respaldos == ["ds-junio"]

    def test_relacion_inexistente_es_error(self):
        assert r.sincronizar_relacion(self._fuente(), {}, dry=False) == r.ERROR_REL

    def test_si_falla_el_patch_devuelve_error(self, monkeypatch):
        monkeypatch.setattr(r, "_respaldar_relacion", lambda *a: "(r)")
        monkeypatch.setattr(nc, "update_data_source", _explota)
        assert r.sincronizar_relacion(self._fuente(), self._schema("ds-junio"), dry=False) == r.ERROR_REL


def _explota(*a, **k):
    raise AssertionError("no debía llamarse / API caída")


class TestPeriodoDeTitulo:
    def test_con_anio_explicito(self):
        assert r._periodo_de_titulo("RRHH JUNIO 2026") == (2026, 6)
        assert r._periodo_de_titulo("RRHH JULIO 2026 ") == (2026, 7)

    def test_sin_anio_usa_last_edited(self):
        assert r._periodo_de_titulo("Contable Julio ", "2026-07-24T00:00:00Z") == (2026, 7)

    def test_sin_mes_devuelve_none(self):
        assert r._periodo_de_titulo("CRM Comercial") is None
        assert r._periodo_de_titulo("cualquier cosa") is None


class TestResolverDsActual:
    def _fake(self, filas):
        return lambda q: filas

    def test_gana_el_periodo_mas_nuevo_no_el_mas_editado(self, monkeypatch):
        # 'Contable Junio (1)' se editó DESPUÉS que Julio, pero Julio es más nuevo por período.
        filas = [
            {"id": "julio-ds", "title": [{"plain_text": "Contable Julio "}], "last_edited_time": "2026-07-24"},
            {"id": "junio-ds", "title": [{"plain_text": "Contable Junio (1)"}], "last_edited_time": "2026-07-27"},
            {"id": "feb-ds", "title": [{"plain_text": "Contable Febrero (1)"}], "last_edited_time": "2026-07-20"},
        ]
        monkeypatch.setattr(nc, "buscar_data_sources", self._fake(filas))
        assert r.resolver_ds_actual("Contable", "fallback") == "julio-ds"

    def test_elige_rrhh_del_anio_mes_mayor(self, monkeypatch):
        filas = [
            {"id": "mayo", "title": [{"plain_text": "RRHH MAYO 2026"}], "last_edited_time": "2026-06-30"},
            {"id": "junio", "title": [{"plain_text": "RRHH JUNIO 2026"}], "last_edited_time": "2026-07-15"},
            {"id": "julio", "title": [{"plain_text": "RRHH JULIO 2026"}], "last_edited_time": "2026-08-01"},
        ]
        monkeypatch.setattr(nc, "buscar_data_sources", self._fake(filas))
        assert r.resolver_ds_actual("RRHH", "fb") == "julio"

    @pytest.mark.parametrize("orden", [(0, 1), (1, 0)])
    def test_la_copia_del_mismo_mes_nunca_le_gana_a_la_operativa(self, monkeypatch, orden):
        """06-ago-2026: el respaldo se crea con el MISMO período que la operativa
        ('Contable Julio' / 'Contable Julio (1)'). Antes el desempate lo decidía
        el orden del search — o sea, el azar. Gana la que no tiene sufijo, venga
        como venga."""
        filas = [
            {"id": "operativa", "title": [{"plain_text": "Contable Julio "}], "last_edited_time": "2026-08-06"},
            {"id": "copia", "title": [{"plain_text": "Contable Julio (1)"}], "last_edited_time": "2026-08-06"},
        ]
        monkeypatch.setattr(nc, "buscar_data_sources", self._fake([filas[i] for i in orden]))
        assert r.resolver_ds_actual("Contable", "fallback") == "operativa"

    def test_una_copia_sola_igual_sirve(self, monkeypatch):
        """Si SOLO existe la copia, es mejor usarla que caer al fallback ciego."""
        filas = [{"id": "copia", "title": [{"plain_text": "Contable Julio (1)"}],
                  "last_edited_time": "2026-08-06"}]
        monkeypatch.setattr(nc, "buscar_data_sources", self._fake(filas))
        assert r.resolver_ds_actual("Contable", "fallback") == "copia"

    def test_fallback_si_no_hay_candidatos(self, monkeypatch):
        monkeypatch.setattr(nc, "buscar_data_sources", self._fake([]))
        assert r.resolver_ds_actual("RRHH", "FALLBACK") == "FALLBACK"

    def test_fallback_si_search_revienta(self, monkeypatch):
        def boom(q):
            raise RuntimeError("api caída")
        monkeypatch.setattr(nc, "buscar_data_sources", boom)
        assert r.resolver_ds_actual("Contable", "FB") == "FB"

    def test_ignora_titulos_de_otro_prefijo(self, monkeypatch):
        filas = [
            {"id": "otro", "title": [{"plain_text": "Reporte Julio 2026"}], "last_edited_time": "2026-08-01"},
            {"id": "bueno", "title": [{"plain_text": "Contable Marzo"}], "last_edited_time": "2026-03-01"},
        ]
        monkeypatch.setattr(nc, "buscar_data_sources", self._fake(filas))
        assert r.resolver_ds_actual("Contable", "fb") == "bueno"
