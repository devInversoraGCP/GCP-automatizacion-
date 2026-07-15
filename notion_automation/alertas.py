"""Alertas de error del backend AuditAI (Fase 1, doc 27 — observabilidad).

Dos canales, ambos best-effort (nunca lanzan excepción hacia quien los llama,
para no tumbar el flujo que estaba fallando):

- avisar_fallo_asesor: fallos "esperados" (falta un dato en la fila, SendGrid
  rechazó el envío, asesor pendiente, etc.). Va al asesor del cliente (si se
  conoce) y, en copia, al administrador (ADMIN_ALERT_EMAIL) vía
  email_sender.enviar_aviso_error.
- avisar_excepcion_admin: excepciones NO previstas (bug, timeout raro, 500 de
  una API externa). Antes de este módulo, estas morían en un log que nadie
  revisa. Van solo al administrador, con el detalle técnico (tipo, mensaje,
  traceback) — nunca al asesor, porque no hay contexto de negocio que darle.

No loguea ni envía PII (email de cliente, monto, RUT) en ningún caso. El
`page_id` sí se incluye: es un UUID interno de Notion, no dato personal.
"""
from __future__ import annotations
import os
import logging
import traceback
import requests
import email_sender as es

log = logging.getLogger("auditai")


def avisar_fallo_asesor(nombre_asesor: str, cliente: str, periodo: str, motivo: str,
                        que_hacer: str = "") -> None:
    """Avisa al asesor del cliente (con copia al admin) de un fallo esperado.
    que_hacer: instruccion opcional para el aviso (ver enviar_aviso_error)."""
    email_asesor = os.environ.get("EMAIL_FROM", "notificaciones@inversoragcp.com")
    if nombre_asesor:
        asesor_info = es._buscar_asesor_por_nombre(nombre_asesor)
        if asesor_info:
            email_asesor = asesor_info["email"]
    try:
        ok = es.enviar_aviso_error(email_asesor, cliente or "Cliente Desconocido", periodo or "", motivo,
                                   que_hacer=que_hacer)
        log.info("aviso de fallo enviado al asesor: %s (ok=%s)", email_asesor, ok)
    except Exception as exc:
        log.warning("no se pudo enviar aviso de fallo al asesor: %s", exc)


def avisar_excepcion_admin(flujo: str, page_id: str, exc: Exception) -> None:
    """Avisa a los administradores (ADMIN_ALERT_EMAIL, uno o varios separados
    por coma) de una excepción NO prevista. Siempre deja el traceback completo
    en el log (CRITICAL); el correo es un best-effort adicional — si no hay
    admins configurados o falta SENDGRID_API_KEY, solo queda el log."""
    log.critical(
        "excepcion no prevista · flujo=%s · page_id=%s · %s: %s\n%s",
        flujo, page_id or "(sin identificar)", type(exc).__name__, exc, traceback.format_exc(),
    )
    admins = es.admin_emails()
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not (admins and api_key):
        return
    try:
        detalle = traceback.format_exc()[-1500:]
        payload = {
            "personalizations": [{"to": [{"email": a} for a in admins]}],
            "from": {
                "email": os.environ.get("EMAIL_FROM", "notificaciones@inversoragcp.com"),
                "name": "AuditAI · Alertas",
            },
            "subject": f"AuditAI · ERROR no previsto en {flujo}",
            "content": [{
                "type": "text/plain",
                "value": (
                    f"Excepcion no prevista en el flujo {flujo}.\n\n"
                    f"page_id: {page_id or '(sin identificar)'}\n"
                    f"Tipo: {type(exc).__name__}\n"
                    f"Mensaje: {exc}\n\n"
                    f"Traceback:\n{detalle}"
                ),
            }],
        }
        requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload, timeout=15,
        )
    except Exception as exc2:
        log.warning("no se pudo enviar aviso de excepcion al admin: %s", exc2)
