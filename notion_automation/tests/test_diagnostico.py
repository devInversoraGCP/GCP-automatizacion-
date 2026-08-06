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

    def test_bounce_buzon_lleno(self):
        d = _d("no llegó", extra={"bounce_reason": "552 5.2.2 The email account that you tried to reach is over quota"})
        assert d.categoria == "bounce"
        # buzón lleno: ni hard-address ni transitorio; el asesor contacta al cliente
        assert "lleno" in d.explicacion_asesor.lower()
        assert "hard bounce" not in d.causa_raiz.lower()

    def test_bounce_bloqueo_spam(self):
        d = _d("no llegó", extra={"bounce_reason": "554 5.7.1 Message blocked due to spam content"})
        assert d.categoria == "bounce"
        assert "bloque" in d.explicacion_asesor.lower()

    def test_bounce_aclara_enviado_no_es_recibido(self):
        # la mejora clave: el asesor debe entender que "Enviado" ≠ "Recibido"
        d = _d("no llegó", extra={"bounce_reason": "550 mailbox does not exist"})
        low = d.explicacion_asesor.lower()
        assert "enviado" in low and "no que el cliente" in low
        assert "entrega correo" in low  # lo apunta a la columna de la verdad

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

    def test_sin_monto(self):
        # motivo real de handlers/rrhh.py (gate del 31-jul: vacío no se envía como $0)
        d = _d("fila sin MONTO IMPOSICIONES| — es el dato principal del correo. "
               "Cárgalo en la planilla y vuelve a apretar el botón.")
        assert d.categoria == "sin_monto" and d.puede_asesor is True

    def test_sin_monto_no_manda_a_reintentar_a_ciegas(self):
        # la regresión que generó el bucle de correos: 'desconocido' le decía al
        # asesor "vuelve a apretar el botón" sin decirle que cargue el monto
        d = _d("fila sin MONTO IMPOSICIONES| — es el dato principal del correo.")
        pasos = " ".join(d.pasos_asesor).lower()
        assert "monto" in pasos
        assert "monto" in d.explicacion_asesor.lower()

    def test_sin_monto_aclara_que_el_cero_explicito_si_se_envia(self):
        d = _d("fila sin MONTO IMPOSICIONES|")
        assert "0" in " ".join(d.pasos_asesor)

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
