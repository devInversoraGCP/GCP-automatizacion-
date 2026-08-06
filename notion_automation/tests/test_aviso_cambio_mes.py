"""Tests del aviso de cambio de mes partido por planilla.

Contable y RRHH NO rotan el mismo día (Sebastián, 06-ago-2026): Contable el 1 y
RRHH el 13. El instructivo es casi todo común, así que en vez de duplicar el HTML
se marcan los bloques específicos con `<!--SOLO:destinos-->…<!--/SOLO-->` y se
recortan al armar el correo. Estos tests cubren el recorte, que es lo que puede
romperse en silencio: un correo mal filtrado sigue enviándose igual, solo que
diciéndole al asesor que renombre la planilla equivocada.
"""
import pytest

import enviar_aviso_cambio_mes as av


class TestFiltrarSecciones:
    HTML = (
        "comun-arriba"
        "<!--SOLO:contable ambas-->[C]<!--/SOLO-->"
        "<!--SOLO:rrhh ambas-->[R]<!--/SOLO-->"
        "<!--SOLO:ambas-->[AMBAS]<!--/SOLO-->"
        "<!--SOLO:rrhh-->[SOLO-R]<!--/SOLO-->"
        "comun-abajo"
    )

    def test_contable_deja_lo_suyo_y_lo_comun(self):
        out = av.filtrar_secciones(self.HTML, "contable")
        assert "[C]" in out
        assert "comun-arriba" in out and "comun-abajo" in out
        assert "[R]" not in out and "[AMBAS]" not in out and "[SOLO-R]" not in out

    def test_rrhh_deja_lo_suyo_y_lo_comun(self):
        out = av.filtrar_secciones(self.HTML, "rrhh")
        assert "[R]" in out and "[SOLO-R]" in out
        assert "comun-arriba" in out and "comun-abajo" in out
        assert "[C]" not in out and "[AMBAS]" not in out

    def test_ambas_deja_los_dos_pero_no_los_exclusivos(self):
        out = av.filtrar_secciones(self.HTML, "ambas")
        assert "[C]" in out and "[R]" in out and "[AMBAS]" in out
        assert "[SOLO-R]" not in out

    def test_no_quedan_marcas_en_el_correo_final(self):
        for planilla in av.PLANILLAS:
            out = av.filtrar_secciones(self.HTML, planilla)
            assert "<!--SOLO" not in out and "<!--/SOLO-->" not in out


class TestCorreoReal:
    """Sobre el HTML de verdad, no sobre un fixture: si alguien edita el archivo
    y desbalancea una marca, esto lo caza."""

    @pytest.mark.parametrize("planilla", ["contable", "rrhh", "ambas"])
    def test_se_arma_sin_dejar_marcas(self, planilla):
        html, logo = av.preparar_html(planilla)
        assert "<!--SOLO" not in html
        assert "<!--PREVIEW-->" not in html
        assert logo, "el logo GCP tiene que ir inline (Gmail bloquea base64)"
        # los pasos comunes sobreviven en las tres variantes
        assert "Duplica la planilla" in html
        assert "RESET_MES" in html

    def test_el_de_contable_no_habla_de_rrhh(self):
        html, _ = av.preparar_html("contable")
        assert "Contable Agosto" in html
        assert "RRHH AGOSTO 2026" not in html
        assert "En RRHH es igual" not in html

    def test_el_de_rrhh_lleva_el_formato_con_mayuscula_y_anio(self):
        html, _ = av.preparar_html("rrhh")
        assert "RRHH AGOSTO 2026" in html
        assert "Contable Agosto" not in html

    def test_cada_planilla_tiene_su_asunto(self):
        assert av.ASUNTOS["contable"] != av.ASUNTOS["rrhh"]
        for p in av.PLANILLAS:
            assert av.ASUNTOS[p]


class TestEnvio:
    def test_dry_no_manda_nada(self, monkeypatch):
        monkeypatch.setenv("SENDGRID_API_KEY", "fake")
        # _sin_red (conftest) ya bloquea la salida; el dry ni siquiera debe intentarlo
        assert av.enviar(dry=True, destinatarios=["x@y.cl"], planilla="rrhh") is True

    def test_sin_api_key_no_envia_y_no_revienta(self, monkeypatch):
        """Best-effort: el cron no puede caerse por falta de credencial."""
        monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
        assert av.enviar(destinatarios=["x@y.cl"], planilla="contable") is False
