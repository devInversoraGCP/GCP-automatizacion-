"""Tests de las funciones puras de email_sender (lógica tributaria y de formato).
Cero mocks: son deterministas. Un error acá manda fechas o montos incorrectos
a los clientes, así que son de los tests de mayor valor."""
import datetime
import email_sender as es


class TestFechaLimiteF29:
    """F29: día 20 del mes SIGUIENTE, trasladado al siguiente día hábil."""

    def test_dia_habil_normal(self):
        # 20-jul-2026 es lunes hábil
        assert es.fecha_limite("Junio 2026") == datetime.date(2026, 7, 20)

    def test_traslado_fin_de_semana(self):
        # 20-jun-2026 cae sábado -> se traslada a lunes 22
        assert es.fecha_limite("Mayo 2026") == datetime.date(2026, 6, 22)

    def test_cruce_de_anio(self):
        # Diciembre -> enero del año siguiente
        assert es.fecha_limite("Diciembre 2026") == datetime.date(2027, 1, 20)

    def test_periodo_sin_anio_devuelve_none(self):
        assert es.fecha_limite("Junio") is None

    def test_periodo_basura_devuelve_none(self):
        assert es.fecha_limite("no es un periodo") is None


class TestFechaLimiteRRHH:
    """RRHH: día 13 del mes SIGUIENTE, trasladado al siguiente día hábil."""

    def test_dia_habil_normal(self):
        assert es.fecha_limite_rrhh("Junio 2026") == datetime.date(2026, 7, 13)

    def test_traslado_fin_de_semana(self):
        # 13-jun-2026 cae sábado -> lunes 15
        assert es.fecha_limite_rrhh("Mayo 2026") == datetime.date(2026, 6, 15)

    def test_invalido(self):
        assert es.fecha_limite_rrhh("xxx") is None


class TestClp:
    def test_entero(self):
        assert es.clp(462) == "$462"

    def test_miles_con_punto(self):
        assert es.clp(1234567) == "$1.234.567"

    def test_negativo(self):
        assert es.clp(-158117) == "$-158.117"

    def test_string_numerico(self):
        assert es.clp("1000") == "$1.000"

    def test_no_numerico_devuelve_cero(self):
        assert es.clp("abc") == "$0"

    def test_cero(self):
        assert es.clp(0) == "$0"


class TestVariantes:
    def test_positivo_paga(self):
        assert es._variantes("462", "Junio 2026")[0] == "Impuesto a pagar"

    def test_negativo_saldo_a_favor(self):
        assert es._variantes("-100", "Junio 2026")[0] == "Saldo a favor"

    def test_cero_sin_pago(self):
        assert es._variantes("0", "Junio 2026")[0] == "Sin pago este mes"


class TestCombinarInfo:
    def test_valor_y_motivo(self):
        assert es._combinar_info("417798", "Remanente") == "Remanente: $417.798"

    def test_solo_valor(self):
        assert es._combinar_info("100", "") == "$100"

    def test_solo_motivo(self):
        assert es._combinar_info("", "Saldo a favor") == "Saldo a favor"

    def test_vacio(self):
        assert es._combinar_info("", "") == ""


class TestMesNombre:
    def test_reconoce_mes(self):
        assert es._mes_nombre("Junio 2026") == "Junio"

    def test_no_reconoce(self):
        assert es._mes_nombre("xxx") == ""


class TestNorm:
    def test_quita_tildes_y_baja(self):
        assert es._norm("Sebastián Robles") == "sebastian robles"

    def test_espacios_extra(self):
        assert es._norm("  Carlos   Cereceda  ") == "carlos cereceda"


class TestEsHabil:
    def test_sabado_no_habil(self):
        assert es._es_habil(datetime.date(2026, 6, 20)) is False  # sábado

    def test_lunes_habil(self):
        assert es._es_habil(datetime.date(2026, 7, 20)) is True

    def test_feriado_no_habil(self):
        # 2026-07-16 está en FERIADOS_CL
        assert es._es_habil(datetime.date(2026, 7, 16)) is False
