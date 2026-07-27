"""Tests de matching.py (normalización RUT módulo 11 + nombre). Funciones puras."""
import matching as m


class TestNormalizarRut:
    def test_formatos_equivalentes(self):
        for raw in ("12.345.678-5", "12345678-5", "123456785", " 12345678-5 "):
            assert m.normalizar_rut(raw) == "12345678-5"

    def test_dv_k_mayuscula(self):
        assert m.normalizar_rut("12345678-k") == "12345678-K"

    def test_quita_ceros_a_la_izquierda_del_cuerpo(self):
        assert m.normalizar_rut("0012345678-5") == "12345678-5"

    def test_basura_devuelve_none(self):
        for raw in ("", None, "SOLO WHATSAPP", "cliente@correo.cl", "abc", "1"):
            assert m.normalizar_rut(raw) is None

    def test_texto_largo_con_ruido_no_se_confunde_con_rut(self):
        # "clave Fabian2025" u otro ruido no debe colar como RUT plausible.
        assert m.normalizar_rut("12345678-5 clave Fabian2025") is None


class TestRutValido:
    def test_casos_conocidos_validos(self):
        for r in ("10207640-0", "12345678-5", "16630663-9"):
            assert m.rut_valido(r) is True

    def test_dv_incorrecto(self):
        assert m.rut_valido("12345678-9") is False

    def test_none_y_vacio(self):
        assert m.rut_valido(None) is False
        assert m.rut_valido("") is False


class TestRutLlave:
    def test_valido_pasa(self):
        assert m.rut_llave("12.345.678-5") == "12345678-5"

    def test_invalido_o_basura_es_none(self):
        assert m.rut_llave("12345678-9") is None   # DV malo
        assert m.rut_llave("SOLO WHATSAPP") is None


class TestNormalizarNombre:
    def test_tildes_mayusculas_y_espacios(self):
        assert m.normalizar_nombre("  Educación   SPA ") == "educacion"

    def test_recorta_sufijo_societario(self):
        assert m.normalizar_nombre("NIKILETTERS SPA") == "nikiletters"
        assert m.normalizar_nombre("Comercial Torres LTDA") == "comercial torres"
        assert m.normalizar_nombre("Refraline S.A.") == "refraline"

    def test_no_recorta_palabra_del_nombre(self):
        # "Inversiones" NO es sufijo legal: se conserva.
        assert m.normalizar_nombre("Inversiones del Sur SpA") == "inversiones del sur"

    def test_dos_nombres_distintos_no_colisionan(self):
        assert m.normalizar_nombre("SOCIAL UP SPV I SPA") != m.normalizar_nombre("SOCIAL UP SPV II SPA")

    def test_vacio(self):
        assert m.normalizar_nombre("") == ""
        assert m.normalizar_nombre(None) == ""


class TestEsRuido:
    def test_filas_control_y_test(self):
        for n in ("RESET_MES", "reset mes", "ZZ_TEST AuditAI", "zz_test x", "", None, "  "):
            assert m.es_ruido(n) is True

    def test_rut_suelto_sin_letras(self):
        assert m.es_ruido("20083124-1") is True

    def test_cliente_real_no_es_ruido(self):
        for n in ("NIKILETTERS SPA", "Comercial Los Andes", "Refraline"):
            assert m.es_ruido(n) is False


class TestEnumeradorDistinto:
    def test_spv_i_vs_ii_es_distinto(self):
        a = m.normalizar_nombre("SOCIAL UP SPV I SPA")
        b = m.normalizar_nombre("SOCIAL UP SPV II SPA")
        assert m.enumerador_distinto(a, b) is True

    def test_numeros_distintos(self):
        assert m.enumerador_distinto("planta 1", "planta 2") is True

    def test_sin_enumerador_no_flag(self):
        assert m.enumerador_distinto("comercial los andes", "comercail los andes") is False

    def test_mismo_enumerador_no_flag(self):
        assert m.enumerador_distinto("grupo dos i", "grupo i") is False


class TestCandidatosFuzzy:
    def test_tolera_orden_y_typo(self):
        uni = ["comercial los andes", "inversiones san pedro"]
        assert m.candidatos_fuzzy("los andes comercial", uni, limite=1)[0][0] == "comercial los andes"
        assert m.candidatos_fuzzy("comercail los andes", uni, limite=1)[0][1] >= 85

    def test_sin_parecido_devuelve_vacio(self):
        assert m.candidatos_fuzzy("zeta digital", ["comercial los andes"], umbral=80) == []
