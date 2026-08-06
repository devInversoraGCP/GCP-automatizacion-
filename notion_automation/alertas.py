"""Alertas de error del backend AuditAI (Fase 1, doc 27 — observabilidad).

Dos canales, ambos best-effort (nunca lanzan excepción hacia quien los llama,
para no tumbar el flujo que estaba fallando):

- avisar_fallo_asesor: fallos "esperados" (falta un dato en la fila, SendGrid
  rechazó el envío, asesor pendiente, etc.). Manda DOS correos a medida (doc 27):
  uno DIDÁCTICO al asesor del cliente (contador: qué pasó y pasos en Notion) y
  otro TÉCNICO al administrador (ADMIN_ALERT_EMAIL: causa raíz + query para un
  LLM). El contenido lo arma diagnostico.diagnosticar según el motivo.
- avisar_excepcion_admin: excepciones NO previstas (bug, timeout raro, 500 de
  una API externa). Antes de este módulo, estas morían en un log que nadie
  revisa. Van solo al administrador, con el detalle técnico (tipo, mensaje,
  traceback) — nunca al asesor, porque no hay contexto de negocio que darle.

No loguea ni envía PII (email de cliente, monto, RUT) en ningún caso. El
`page_id` sí se incluye: es un UUID interno de Notion, no dato personal.
"""
from __future__ import annotations
import os
import time
import logging
import threading
import traceback
import requests
import email_sender as es
import diagnostico

log = logging.getLogger("auditai")


def avisar_fallo_asesor(nombre_asesor: str, cliente: str, periodo: str, motivo: str,
                        flujo: str = "", page_id: str = "", extra: dict | None = None) -> None:
    """Avisa un fallo esperado en DOS correos a medida (doc 27):

    1. DIDÁCTICO al asesor del cliente: qué pasó en lenguaje de contador, si lo
       puede resolver solo, y pasos en Notion.
    2. TÉCNICO al administrador (ADMIN_ALERT_EMAIL): causa raíz + query para un LLM.

    El contenido lo arma diagnostico.diagnosticar. Best-effort: nunca propaga
    (si un envío revienta, queda el log). `extra` lleva contexto opcional del
    diagnóstico (ej. bounce_reason, ya_reintentado)."""
    email_asesor = os.environ.get("EMAIL_FROM", "notificaciones@inversoragcp.com")
    if nombre_asesor:
        asesor_info = es._buscar_asesor_por_nombre(nombre_asesor)
        if asesor_info:
            email_asesor = asesor_info["email"]

    cli = cliente or "Cliente Desconocido"
    mes = periodo or ""
    diag = diagnostico.diagnosticar(
        motivo, flujo=flujo, cliente=cli, periodo=mes, page_id=page_id,
        asesor=nombre_asesor, extra=extra,
    )

    # 1) Didáctico al asesor.
    try:
        ok = es.enviar_aviso_asesor(email_asesor, cli, mes, diag)
        log.info("aviso didactico enviado al asesor: %s (categoria=%s, ok=%s)",
                 email_asesor, diag.categoria, ok)
    except Exception as exc:
        log.warning("no se pudo enviar aviso didactico al asesor: %s", exc)

    # 2) Técnico al admin/dev (solo si hay ADMIN_ALERT_EMAIL). No duplica al
    # asesor: es un correo aparte, con la causa raíz y la query para el LLM.
    try:
        admins = es.admin_emails()
        if admins:
            ok_dev = es.enviar_aviso_dev(admins, cli, mes, diag,
                                         motivo=motivo, flujo=flujo, page_id=page_id)
            log.info("aviso tecnico enviado al dev (%d admins, categoria=%s, ok=%s)",
                     len(admins), diag.categoria, ok_dev)
    except Exception as exc:
        log.warning("no se pudo enviar aviso tecnico al dev: %s", exc)


def avisar_entrega_ok_asesor(remitente_o_nombre: str, cliente: str, periodo: str,
                             flujo: str = "", fecha: str = "") -> None:
    """Confirma al asesor que el correo SÍ llegó al cliente (evento 'delivered').
    Contraparte positiva de avisar_fallo_asesor: así el asesor recibe por correo
    tanto el «llegó» como el «no llegó». `remitente_o_nombre` puede ser el email
    del remitente (preferido, viaja en custom_args) o un nombre a resolver en
    asesores_smtp.json. Best-effort: nunca propaga."""
    dest = (remitente_o_nombre or "").strip()
    if not dest:
        return
    if "@" not in dest:
        info = es._buscar_asesor_por_nombre(dest)
        dest = info["email"] if info else ""
    if not dest:
        return
    try:
        ok = es.enviar_confirmacion_entrega_asesor(
            dest, cliente or "el cliente", periodo or "", flujo, fecha)
        log.info("confirmacion de entrega enviada al asesor: %s (ok=%s)", dest, ok)
    except Exception as exc:
        log.warning("no se pudo enviar confirmacion de entrega al asesor: %s", exc)


def avisar_resumen_reconciliacion(stats: dict) -> None:
    """Correo de ÉXITO del cron de reconciliación al admin (dev@ vía ADMIN_ALERT_EMAIL).
    Contraparte de avisar_excepcion_admin: así se confirma que el feed SÍ corrió, no
    solo cuando falla. Best-effort: nunca propaga; si falta config, queda en el log."""
    creados = stats.get("creados", 0)
    tocadas = stats.get("fichas_tocadas", 0)
    links = stats.get("links_add", 0)
    estampados = stats.get("estampados", 0)
    admins = es.admin_emails()
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not (admins and api_key):
        log.info("resumen reconciliacion (sin correo): creadas=%s tocadas=%s enlaces=%s estampados=%s",
                 creados, tocadas, links, estampados)
        return
    try:
        cuerpo = (
            "Reconciliacion del sandbox ejecutada correctamente.\n\n"
            f"Fichas nuevas creadas: {creados}\n"
            f"Fichas actualizadas:   {tocadas}\n"
            f"Enlaces nuevos:        {links}\n"
            f"Filas con ID Central:  {estampados}\n"
        )
        payload = {
            "personalizations": [{"to": [{"email": a} for a in admins]}],
            "from": {"email": os.environ.get("EMAIL_FROM", "notificaciones@inversoragcp.com"),
                     "name": "AuditAI · Reconciliacion"},
            "subject": f"AuditAI · Reconciliacion OK ({creados} nuevas, {links} enlaces)",
            "content": [{"type": "text/plain", "value": cuerpo}],
        }
        requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload, timeout=15,
        )
        log.info("resumen de reconciliacion enviado al admin (%d)", len(admins))
    except Exception as exc:
        log.warning("no se pudo enviar el resumen de reconciliacion: %s", exc)


# Clics del botón que el backend rechaza con un 4xx: hasta el 06-ago-2026 morían
# en silencio (Notion le mostraba el error al asesor y no se enteraba nadie más).
# Así se perdió el caso de Andrea del 02-ago.
#
# 401 y 503 NO se avisan a propósito: ocurren ANTES de validar el secreto, así que
# cualquiera que golpee la URL pública podría disparar correos. Los demás códigos
# solo los alcanza una request que ya probó venir de Notion.
_CODIGOS_SIN_AVISO = frozenset({401, 503})
# Un botón mal configurado puede repetir el mismo 4xx muchas veces seguidas; se
# avisa uno por (flujo, código) cada 10 min para no repetir el bucle de correos.
_THROTTLE_AVISO_S = 600
# El 403 del guard de base vigente es un rechazo ESPERADO y ya resuelto: el
# respaldo del mes anterior conserva su columna botón (Notion no permite borrarla
# por API) y alguien lo va a apretar de vez en cuando. El guard ya evitó el correo
# equivocado, así que un aviso por día alcanza para enterarse de que pasa; a 10
# min sería spam por algo que el sistema maneja solo. Gracias a esto NO hace falta
# borrarle el botón a cada respaldo a mano (07-ago-2026, doc 28 §18).
_THROTTLE_POR_CODIGO_S = {403: 86400}
_ultimo_aviso: dict[tuple[str, int], float] = {}
_aviso_lock = threading.Lock()


def _throttle_ok(clave: tuple[str, int], ventana: float = _THROTTLE_AVISO_S) -> bool:
    ahora = time.time()
    with _aviso_lock:
        prev = _ultimo_aviso.get(clave, 0.0)
        if ahora - prev < ventana:
            return False
        _ultimo_aviso[clave] = ahora
        return True


def avisar_boton_rechazado(flujo: str, codigo: int, detalle: str, page_id: str = "",
                           estructura: str = "", origen: str = "") -> None:
    """Avisa al admin que un clic del botón se rechazó con un 4xx (400/404/…).

    El asesor ve el error en Notion pero no puede hacer nada con él: son fallos de
    identificación de la fila o de payload, no de datos que él cargue. Por eso va
    solo al admin. Best-effort: nunca propaga.

    `estructura` es el dump de SOLO claves y tipos del payload (app._estructura,
    sin valores ⇒ sin PII, R3). `origen` es el contexto de transporte de la
    request (IP, User-Agent, forma del body — app._contexto_request). Van en el
    correo porque el 06-ago-2026 diagnosticar un 400 exigió ir a leer los logs
    de Render, y aun así no se podía distinguir un clic real de un 'Test' de la
    configuración del webhook. Con estas dos líneas el aviso se basta solo."""
    if codigo in _CODIGOS_SIN_AVISO:
        return
    if not _throttle_ok((flujo, codigo), _THROTTLE_POR_CODIGO_S.get(codigo, _THROTTLE_AVISO_S)):
        log.info("aviso de boton rechazado omitido por throttle · flujo=%s codigo=%s", flujo, codigo)
        return
    log.warning("boton rechazado · flujo=%s codigo=%s page_id=%s · %s",
                flujo, codigo, page_id or "(sin identificar)", detalle)
    admins = es.admin_emails()
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not (admins and api_key):
        return
    try:
        payload = {
            "personalizations": [{"to": [{"email": a} for a in admins]}],
            "from": {"email": os.environ.get("EMAIL_FROM", "notificaciones@inversoragcp.com"),
                     "name": "AuditAI · Alertas"},
            "subject": f"AuditAI · clic del boton rechazado ({codigo}) en {flujo}",
            "content": [{"type": "text/plain", "value": (
                f"Un asesor apreto el boton en {flujo} y el backend lo rechazo con HTTP {codigo}.\n"
                f"El asesor vio un error en Notion; el correo al cliente NO se envio.\n\n"
                f"page_id: {page_id or '(no se pudo identificar la fila)'}\n"
                f"Detalle: {detalle}\n"
                + (f"Payload recibido (solo claves y tipos): {estructura}\n" if estructura else "")
                + (f"Origen de la request: {origen}\n" if origen else "")
                + "\n"
                "Causas tipicas: el payload del boton no trae page_id/RUT/CLIENTE, o la fila "
                "no existe en la base del mes vigente (base recien duplicada, fila movida, "
                "titulo cambiado). Revisar la automatizacion del boton en esa base.\n"
                "Si el body llego VACIO no fue un asesor: es el 'Test' de la accion webhook "
                "en Notion, o un boton cuya accion quedo sin contenido configurado."
            )}],
        }
        requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload, timeout=15,
        )
    except Exception as exc:
        log.warning("no se pudo enviar el aviso de boton rechazado: %s", exc)


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
