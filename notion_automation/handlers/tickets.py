"""Handler de los botones Enviar Avance / Completado / Cobranza de Tickets - Servicios.
Destinatario = CLIENTE (Tarea = nombre, Email = correo). Remitente = Asignado.
El CUERPO lo escribe el asesor en la columna 'Mensaje Correo' (personalizable por ticket:
'esta listo X, nos falta Y de tu parte'); si esta vacia, se usa un texto estandar por tipo.
Un mismo handler sirve las 3 plantillas segun tipo_correo (audio de Carlos, doc 26 §0.1)."""
from __future__ import annotations
import logging
from datetime import datetime, timezone
import notion_client as nc
import email_sender as es

log = logging.getLogger("auditai")

# Data source de Tickets - Servicios
DS_ID = "9d312147-b3ea-83bf-b111-877c7b24db75"

# Columnas (nombres EXACTOS verificados por API)
TAREA = "Tarea"                 # title = nombre del cliente
TIPO = "Tipo"                   # multi_select
ESTADO = "Estado"               # status
ASIGNADO = "Asignado"           # person -> remitente/firma
EMAIL_CLIENTE = "Email"         # columna nueva
MENSAJE = "Mensaje Correo"      # columna nueva: cuerpo personalizable (rich_text)
MONTO = "Monto"                 # columna nueva (opcional): monto a cobrar (number)
FECHA_PROM = "Fecha prometida"  # date

# Write-back (columnas nuevas)
STATUS_COL = "Estado Correo"
STATUS_ENVIADO = "Enviado"
FECHA_COL = "Fecha Envío"

# tipo_correo -> (plantilla, plantilla de asunto, texto estandar si Mensaje Correo esta vacio)
CORREOS = {
    "avance": (
        "tickets_avance",
        "Avance de su trámite de {tipo} — GCP",
        "Le escribimos para informarle sobre el avance de su trámite de {tipo}.",
    ),
    "completado": (
        "tickets_completado",
        "Su trámite de {tipo} está listo — GCP",
        "Nos complace informarle que su trámite de {tipo} ha sido completado exitosamente.",
    ),
    "cobranza": (
        "tickets_cobranza",
        "Pago pendiente — trámite de {tipo} — GCP",
        "Su trámite de {tipo} se encuentra finalizado y registra un pago pendiente.",
    ),
}


def _fmt_fecha(iso: str) -> str:
    """ISO -> 'dd/mm/aaaa'. '' si no hay o no parsea."""
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except ValueError:
        return iso[:10]


def _bloque_mensaje(mensaje: str, estandar: str) -> tuple[str, str]:
    """Cuerpo principal: el texto del asesor (personalizado) o el estandar del tipo.
    Respeta saltos de linea para que el asesor pueda listar (checklist)."""
    txt = (mensaje or "").strip() or estandar
    html_txt = es._escape(txt).replace("\n", "<br>")
    html = (
        f'<p style="margin:0 0 18px 0;font-size:15px;line-height:1.6;color:#3a4658;">{html_txt}</p>'
    )
    return html, txt


def _bloque_monto(monto: str) -> tuple[str, str]:
    """Tarjeta 'Total a pagar' formateada en CLP. ('', '') si no hay monto valido (>0).
    El monto sale de la columna 'Monto' (number); si esta vacia, no se muestra tarjeta
    (el asesor puede ponerlo en el mensaje libre)."""
    try:
        n = float(monto)
    except (ValueError, TypeError):
        n = 0.0
    if n <= 0:
        return "", ""
    m = es.clp(monto)
    html = (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="margin:0 0 18px 0;"><tr><td style="background:#0B1F3A;border-radius:14px;'
        'padding:22px 26px;"><div style="font-size:12px;font-weight:700;letter-spacing:.12em;'
        'text-transform:uppercase;color:#8fb4ee;margin-bottom:8px;">Total a pagar</div>'
        f'<div style="font-size:40px;font-weight:800;color:#ffffff;line-height:1;'
        f'font-variant-numeric:tabular-nums;">{m}</div></td></tr></table>'
    )
    return html, f"Total a pagar: {m}"


def _bloque_detalle(tipo_correo: str, estado: str, fecha_prom: str) -> tuple[str, str]:
    """Extra especifico del tipo. avance: Estado + Fecha; cobranza: datos bancarios GCP."""
    ph, pt = [], []
    if tipo_correo == "avance":
        if estado:
            ph.append(
                f'<p style="margin:0 0 8px 0;font-size:14px;color:#3a4658;line-height:1.6;">'
                f'<b>Estado actual:</b> {es._escape(estado)}.</p>'
            )
            pt.append(f"Estado actual: {estado}.")
        f = _fmt_fecha(fecha_prom)
        if f:
            ph.append(
                f'<p style="margin:0 0 14px 0;font-size:14px;color:#3a4658;line-height:1.6;">'
                f'<b>Fecha comprometida:</b> {f}.</p>'
            )
            pt.append(f"Fecha comprometida: {f}.")
    elif tipo_correo == "cobranza":
        ph.append(
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            'style="margin:0 0 18px 0;"><tr><td style="background:#eef4ff;border:1px solid #d3e0f5;'
            'border-left:4px solid #0B1F3A;border-radius:10px;padding:14px 18px;font-size:14px;'
            f'color:#3a4658;line-height:1.6;">{es.BANCO_GCP_HTML}</td></tr></table>'
        )
        pt.append(es.BANCO_GCP_TXT)
    return "".join(ph), "\n".join(pt)


def procesar(page_id: str, tipo_correo: str) -> dict:
    """Lee la fila, envia el correo del tipo pedido y escribe el write-back.
    Devuelve {'ok': bool, 'remitente': str, 'motivo': str (si falla)}."""
    cfg = CORREOS.get(tipo_correo)
    if not cfg:
        return {"ok": False, "motivo": f"tipo de correo desconocido: {tipo_correo!r}"}
    plantilla, asunto_tpl, estandar_tpl = cfg

    props = nc.get_page(page_id)["properties"]
    cliente = nc.plain(props.get(TAREA, {}))
    email = nc.plain(props.get(EMAIL_CLIENTE, {}))
    mensaje = nc.plain(props.get(MENSAJE, {}))
    monto = nc.plain(props.get(MONTO, {}))
    estado = (props.get(ESTADO, {}).get("status") or {}).get("name", "")
    fecha_prom = (props.get(FECHA_PROM, {}).get("date") or {}).get("start", "") or ""
    tipos = [o.get("name", "") for o in (props.get(TIPO, {}).get("multi_select") or [])]
    tipo = ", ".join(t for t in tipos if t) or "trámite"
    asignados = nc.people_names(props.get(ASIGNADO, {}))
    asesor = asignados[0] if asignados else ""

    log.info("tickets tipo=%s page_id=%s cliente_present=%s email_present=%s mensaje_present=%s asesor=%r",
             tipo_correo, page_id, bool(cliente), bool(email), bool(mensaje), asesor)

    if not email:
        return {"ok": False, "motivo": "fila sin Email (columna Email vacía)"}
    if not cliente:
        return {"ok": False, "motivo": "fila sin Tarea (nombre de cliente, necesario)"}

    estandar = estandar_tpl.format(tipo=tipo)
    b_msg = _bloque_mensaje(mensaje, estandar)
    b_det = _bloque_detalle(tipo_correo, estado, fecha_prom)
    # El monto solo se muestra en Cobranza (decision del usuario 10-jul).
    b_monto = _bloque_monto(monto) if tipo_correo == "cobranza" else ("", "")
    extra_vars = {
        "tipo": tipo,
        "bloque_mensaje": b_msg[0], "linea_mensaje": b_msg[1],
        "bloque_monto": b_monto[0], "linea_monto": b_monto[1],
        "bloque_detalle": b_det[0], "linea_detalle": b_det[1],
    }
    asunto = asunto_tpl.format(tipo=tipo)

    try:
        remitente = es.enviar(
            destinatario=email,
            nombre=cliente,
            mes="",            # Tickets no usa periodo/fecha límite
            monto="0",         # ni monto
            nombre_asesor=asesor,
            template=plantilla,
            asunto=asunto,
            extra_vars=extra_vars,
        )
        log.info("correo tickets/%s enviado OK · page_id=%s remitente=%s", tipo_correo, page_id, remitente)
    except ValueError as exc:
        log.error("error envio tickets · page_id=%s · %s", page_id, exc)
        return {"ok": False, "motivo": str(exc)}
    except Exception as exc:
        log.error("error SMTP tickets · page_id=%s · %s", page_id, exc)
        return {"ok": False, "motivo": f"error SMTP: {exc}"}

    # Write-back tolerante: solo columnas presentes en la fila (R6)
    now_iso = datetime.now(timezone.utc).isoformat()
    updates = {}
    if STATUS_COL in props:
        updates[STATUS_COL] = {"status": {"name": STATUS_ENVIADO}}
    else:
        log.warning("columna %r no existe en Tickets; no se escribe status", STATUS_COL)
    if FECHA_COL in props:
        updates[FECHA_COL] = {"date": {"start": now_iso}}
    else:
        log.warning("columna %r no existe en Tickets; no se escribe fecha", FECHA_COL)
    if updates:
        try:
            nc.update_props(page_id, updates)
            log.info("write-back OK (%s) · page_id=%s", ", ".join(updates), page_id)
        except Exception as exc:
            log.warning("no se pudo actualizar status/fecha · page_id=%s · %s", page_id, exc)

    return {"ok": True, "remitente": remitente}
