"""La suite NUNCA puede mandar un correo real. Test de regresión del incidente
del 06-ago-2026.

Durante horas llegaron avisos de "un asesor apretó el botón y el backend lo
rechazó con 400". No era ningún asesor: era esta misma suite. El `conftest`
BORRABA `SENDGRID_API_KEY` con `pop()`, y `load_dotenv(override=False)` —que
corre al importar `app`— solo respeta lo que YA existe en el entorno, así que
rellenaba la variable borrada con la credencial real del `.env`. Corriendo
`pytest` desde `notion_automation/` (donde vive el `.env`), cada corrida mandaba
un correo de verdad a dev@, porque `admin_emails()` incluye ese buzón SIEMPRE,
haya o no `ADMIN_ALERT_EMAIL`.

La huella en el aviso era inconfundible y es lo que permitió cerrarlo:
`IP 127.0.0.1 · User-Agent: Werkzeug/… · body JSON de 2 bytes`.
"""
import os
from unittest.mock import patch

import pytest

import alertas
import app as A
import email_sender as es
from conftest import EnvioBloqueadoEnTests


H = {"X-AuditAI-Secret": "test-secret"}


class TestCredencialesNeutralizadas:
    def test_no_hay_api_key_de_sendgrid(self):
        """Presente pero vacía: falsy para el código y a la vez le cierra la
        puerta a load_dotenv(). Si algún día vuelve a estar ausente, el `.env`
        real la rellena y se reabre el incidente."""
        assert "SENDGRID_API_KEY" in os.environ, "ausente => load_dotenv la rellena del .env"
        assert not os.environ["SENDGRID_API_KEY"]

    def test_no_hay_admin_alert_email(self):
        assert "ADMIN_ALERT_EMAIL" in os.environ
        assert not os.environ["ADMIN_ALERT_EMAIL"]

    def test_el_buzon_dev_sigue_estando_siempre(self):
        """No es un bug: dev@ es el buzón de monitoreo total. Por eso la única
        barrera real es la credencial, y por eso tiene que estar vacía sí o sí."""
        assert es.admin_emails() == ["dev@inversoragcp.com"]


class TestLaRedEstaCortada:
    def test_un_envio_real_revienta_en_vez_de_salir(self):
        with pytest.raises(EnvioBloqueadoEnTests):
            alertas.requests.post("https://api.sendgrid.com/v3/mail/send", json={})

    def test_el_400_sin_parche_no_manda_nada(self):
        """El caso exacto del incidente: un 400 en /enviar-f29 sin parchear el
        aviso. Antes salía un correo; ahora no sale nada y el test pasa igual."""
        A._dedupe.clear()
        alertas._ultimo_aviso.clear()
        client = A.app.test_client()
        with patch.object(alertas.requests, "post") as m_post:
            r = client.post("/enviar-f29", json={}, headers=H)
        assert r.status_code == 400
        # sin credencial, avisar_boton_rechazado corta ANTES de llegar a la red
        assert not m_post.called
        alertas._ultimo_aviso.clear()

    def test_avisar_boton_rechazado_nunca_propaga(self, monkeypatch):
        """Best-effort de verdad: aunque la red esté cortada, un fallo del aviso
        no puede tumbar la respuesta al asesor."""
        monkeypatch.setenv("ADMIN_ALERT_EMAIL", "a@x.com")
        monkeypatch.setenv("SENDGRID_API_KEY", "fake")
        alertas._ultimo_aviso.clear()
        alertas.avisar_boton_rechazado("F29", 400, "x")   # no debe lanzar
        alertas._ultimo_aviso.clear()
