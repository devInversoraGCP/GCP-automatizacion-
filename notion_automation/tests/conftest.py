"""Configuración compartida de los tests del backend AuditAI (Fase 3, doc 27).

Setea env vars de PRUEBA antes de que se importe cualquier módulo del backend.
`load_dotenv()` (que corre al importar `app`) usa `override=False`, así que NO
pisa estas variables — quedan deterministas también en local con un `.env` real.

⚠️ Ningún test puede tocar SendGrid ni SMTP de verdad, y eso se garantiza por DOS
vías independientes (ver §18 del doc 28, incidente 06-ago-2026):

  1. Las credenciales se setean VACÍAS, no se borran. Borrarlas con `pop()` era
     el bug: `load_dotenv(override=False)` solo respeta lo que YA existe en el
     entorno, así que una variable borrada la rellenaba con el valor real del
     `.env`. Corriendo la suite desde `notion_automation/` (donde vive el `.env`)
     cada `pytest` mandaba un correo de alerta REAL a dev@ — los "errores de
     asesor" del 06-ago eran esto.
  2. `_sin_red` bloquea la salida igual, por si alguna vez vuelve a entrar una
     credencial por otra puerta.
"""
import os
import smtplib

import pytest

os.environ["WEBHOOK_SECRET"] = "test-secret"
os.environ["NOTION_TOKEN"] = "test-token"
os.environ["SENDGRID_WEBHOOK_TOKEN"] = "test-sg-token"
os.environ.setdefault("EMAIL_FROM", "notificaciones@inversoragcp.com")
# VACÍAS, nunca ausentes: una var presente-pero-vacía es falsy para el código
# (`if not api_key: return`) y a la vez le cierra la puerta a load_dotenv().
os.environ["ADMIN_ALERT_EMAIL"] = ""
os.environ["SENDGRID_API_KEY"] = ""


class EnvioBloqueadoEnTests(RuntimeError):
    """Un test intentó mandar un correo de verdad. Es un bug del test, no del
    código: hay que parchear el envío (o el aviso) en ese test."""


@pytest.fixture(autouse=True)
def _sin_red(monkeypatch):
    """Corta cualquier salida real a SendGrid o SMTP en TODOS los tests.

    Los tests que quieran inspeccionar el envío siguen parcheando lo suyo con
    `patch(...)`: su parche gana dentro del `with` y después vuelve este.
    """
    def _bloquear(*a, **k):
        raise EnvioBloqueadoEnTests(
            "un test intento un envio real; parchea requests.post / es.enviar en ese test")

    import alertas
    import email_sender as es
    monkeypatch.setattr(alertas.requests, "post", _bloquear)
    monkeypatch.setattr(es.requests, "post", _bloquear, raising=False)
    monkeypatch.setattr(smtplib, "SMTP", _bloquear)
    monkeypatch.setattr(smtplib, "SMTP_SSL", _bloquear)
