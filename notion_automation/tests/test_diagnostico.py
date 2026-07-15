"""Tests del clasificador de fallos (diagnostico.py). Puros, sin mocks.

Verifican que cada motivo real del backend caiga en la categoría correcta, que
la clasificación de 'quién lo resuelve' sea coherente, y que la query para el
LLM y la causa raíz lleven el contexto necesario (page_id, flujo).
"""
import diagnostico as dg


def _d(motivo, **kw):
    return dg.diagnosticar(motivo, cliente="ACME SPA", page_id="pid-1", flujo="f29", **kw)


class TestCategorias:
    def test_email_invalido(self):
        # motivo real de email_sender._validar_destinatarios
        d = _d("La columna Email de la fila contiene un valor que no es una direccion de correo valida")
        assert d.categoria == "email_invalido" and d.puede_asesor is True

    def test_sin_email(self):
        d = _d("fila sin Email (ni en la fila ni en la base central)")
        assert d.categoria == "sin_email" and d.puede_asesor is True

    def test_bounce_por_motivo(self):
        d = _d("El correo fue ACEPTADO por SendGrid pero NO llegó al cliente (evento: bounce).")
        assert d.categoria == "bounce"

    def test_bounce_por_extra_reason(self):
        d = _d("cualquier cosa", extra={"bounce_reason": "550 mailbox does not exist"})
        assert d.categoria == "bounce"
        assert "hard bounce" in d.causa_raiz.lower()

    def test_bounce_transitorio_dns(self):
        d = _d("no llegó", extra={"bounce_reason": "unable to get mx info: failed to get IPs from PTR"})
        assert d.categoria == "bounce"
        assert "transitorio" in d.causa_raiz.lower()

    def test_remitente_no_verificado(self):
        d = _d("SendGrid rechazo el envio (HTTP 403): remitente no verificado")
        assert d.categoria == "remitente_no_verificado" and d.puede_asesor is False

    def test_asesor_pendiente(self):
        d = _d("Asesor 'X' marcado como pendiente. No se puede enviar desde su cuenta todavía.")
        assert d.categoria == "asesor_pendiente" and d.puede_asesor is False

    def test_sin_mes(self):
        d = _d("fila sin mes (ni Month ni título parseable), necesario para fecha límite")
        assert d.categoria == "sin_mes" and d.puede_asesor is True

    def test_config(self):
        d = _d("No hay SENDGRID_API_KEY ni App Password SMTP para x")
        assert d.categoria == "config" and d.puede_asesor is False

    def test_sin_titulo(self):
        d = _d("fila sin CLIENTE (necesario para el asunto y cuerpo)")
        assert d.categoria == "sin_titulo"

    def test_desconocido(self):
        d = _d("algo totalmente inesperado 12345")
        assert d.categoria == "desconocido" and d.puede_asesor is False


class TestContenido:
    def test_asesor_siempre_tiene_titulo_explicacion_y_pasos(self):
        for motivo in [
            "La columna Email no es una direccion de correo valida",
            "fila sin Email",
            "fila sin mes",
            "Asesor 'X' marcado como pendiente",
            "HTTP 403 no verificado",
            "cualquiera",
        ]:
            d = _d(motivo)
            assert d.titulo and d.explicacion_asesor and d.pasos_asesor

    def test_query_llm_lleva_el_page_id(self):
        d = _d("La columna Email no es una direccion de correo valida")
        assert "pid-1" in d.query_llm

    def test_causa_raiz_presente_para_el_dev(self):
        d = _d("fila sin Email")
        assert d.causa_raiz and d.detalle_dev

    def test_no_lanza_con_motivo_vacio(self):
        d = dg.diagnosticar("")
        assert d.categoria  # devuelve algo (desconocido), sin excepción
