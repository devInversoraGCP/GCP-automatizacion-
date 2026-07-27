"""Tests de la resolución dinámica de mes en reconciliar.py (sin red)."""
import notion_client as nc
import reconciliar as r


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
