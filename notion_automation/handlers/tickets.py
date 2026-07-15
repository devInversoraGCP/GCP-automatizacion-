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
import alertas

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
FECHA_PROM = "Fecha prometida"  # date (existente) -> Avance/Completado
# Columnas nuevas OPCIONALES de personalizacion
ADJUNTOS = "Adjuntos"           # files -> se adjuntan al correo
FECHA_LIMITE = "Fecha límite pago"  # date -> Cobranza: "pagar antes del..."
ASUNTO_COL = "Asunto"           # rich_text -> override del asunto (si vacio, asunto automatico)

# Write-back (columnas nuevas). 'Fecha envío' = nombre EXACTO en Notion (e
# minuscula, verificado por API); "Fecha Envío" con mayuscula NO existe.
STATUS_COL = "Estado Correo"
STATUS_ENVIADO = "Enviado"
FECHA_COL = "Fecha envío"

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


def _linea(texto_html: str) -> str:
    return (f'<p style="margin:0 0 8px 0;font-size:14px;color:#3a4658;line-height:1.6;">'
            f'{texto_html}</p>')


_BANCO_TABLA_HTML = (
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
    'style="margin:0 0 18px 0;"><tr><td style="background:#eef4ff;border:1px solid #d3e0f5;'
    'border-left:4px solid #0B1F3A;border-radius:10px;padding:14px 18px;font-size:14px;'
    'color:#3a4658;line-height:1.6;">{banco_html}</td></tr></table>'
).format(banco_html=es.BANCO_GCP_HTML)


def _bloque_monto(monto: str, fecha_limite: str, titulo: str = "Total a pagar") -> tuple[str, str]:
    """Tarjeta de monto (Cobranza: 'Total a pagar' + 'Fecha límite de pago'; Completado
    de Constitución: 'Honorario a pagar', sin fecha límite — pasar fecha_limite="").
    Cada parte es opcional; si el monto esta vacio no hay tarjeta (el asesor puede
    ponerlo en el mensaje libre)."""
    ph, pt = [], []
    try:
        n = float(monto)
    except (ValueError, TypeError):
        n = 0.0
    if n > 0:
        m = es.clp(monto)
        ph.append(
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            'style="margin:0 0 12px 0;"><tr><td style="background:#0B1F3A;border-radius:14px;'
            'padding:22px 26px;"><div style="font-size:12px;font-weight:700;letter-spacing:.12em;'
            f'text-transform:uppercase;color:#8fb4ee;margin-bottom:8px;">{titulo}</div>'
            f'<div style="font-size:40px;font-weight:800;color:#ffffff;line-height:1;'
            f'font-variant-numeric:tabular-nums;">{m}</div></td></tr></table>'
        )
        pt.append(f"{titulo}: {m}")
    fl = _fmt_fecha(fecha_limite)
    if fl:
        ph.append(_linea(f'<b>Fecha límite de pago:</b> {fl}.'))
        pt.append(f"Fecha límite de pago: {fl}.")
    return "".join(ph), "\n".join(pt)


def _bloque_banner_completado(tipo: str, es_constitucion: bool) -> tuple[str, str]:
    """Banner superior de Completado: felicitaciones si el trámite es Constitución
    (hito importante para el cliente), check generico para el resto de los tipos."""
    if es_constitucion:
        texto = "🎉 ¡Felicitaciones! Su empresa ha sido constituida exitosamente."
    else:
        texto = f"✓ Trámite de {tipo} completado"
    ph = (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 18px 0;">'
        '<tr><td style="background:#e8f5ee;border-left:4px solid #1c7c4a;border-radius:10px;'
        f'padding:12px 16px;font-size:14px;font-weight:700;color:#1c7c4a;">{es._escape(texto)}</td></tr></table>'
    )
    return ph, texto


def _bloque_detalle(tipo_correo: str, estado: str, fecha_prom: str, n_adjuntos: int,
                     es_constitucion: bool = False) -> tuple[str, str]:
    """Extra especifico del tipo:
    - avance: Estado actual + Fecha comprometida
    - completado: Fecha comprometida; + datos bancarios GCP si es Constitución (honorario)
    - cobranza: datos bancarios GCP
    - todos: aviso de adjuntos si los hay."""
    ph, pt = [], []
    if tipo_correo == "avance" and estado:
        ph.append(_linea(f'<b>Estado actual:</b> {es._escape(estado)}.'))
        pt.append(f"Estado actual: {estado}.")
    # La fecha comprometida no aplica en Constitución (el trámite ya se completó):
    # solo en Avance y en Completado de tipos no-especiales.
    if tipo_correo == "avance" or (tipo_correo == "completado" and not es_constitucion):
        f = _fmt_fecha(fecha_prom)
        if f:
            ph.append(_linea(f'<b>Fecha comprometida:</b> {f}.'))
            pt.append(f"Fecha comprometida: {f}.")
    if tipo_correo == "cobranza":
        ph.append(_BANCO_TABLA_HTML)
        pt.append(es.BANCO_GCP_TXT)
    if tipo_correo == "completado" and es_constitucion:
        ph.append(
            '<p style="margin:0 0 12px 0;font-size:14px;line-height:1.6;color:#3a4658;">'
            'Puede realizar la transferencia del honorario a la siguiente cuenta:</p>'
        )
        ph.append(_BANCO_TABLA_HTML)
        pt.append("Puede realizar la transferencia del honorario a la siguiente cuenta:")
        pt.append(es.BANCO_GCP_TXT)
    if n_adjuntos:
        s = "documento" if n_adjuntos == 1 else "documentos"
        ph.append(_linea(f'📎 Adjuntamos {n_adjuntos} {s} a este correo.'))
        pt.append(f"Adjuntamos {n_adjuntos} {s} a este correo.")
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
    fecha_prom = (props.get(FECHA_PROM, {}).get("date") or {}).get("start", "") or ""
    fecha_limite = (props.get(FECHA_LIMITE, {}).get("date") or {}).get("start", "") or ""
    asunto_custom = nc.plain(props.get(ASUNTO_COL, {}))
    adjuntos = nc.files(props.get(ADJUNTOS, {}))
    estado = (props.get(ESTADO, {}).get("status") or {}).get("name", "")
    tipos = [o.get("name", "") for o in (props.get(TIPO, {}).get("multi_select") or [])]
    tipo = ", ".join(t for t in tipos if t) or "trámite"
    # Constitución (completado): felicitaciones + "Honorario a pagar" (sin fecha
    # límite) + datos bancarios, en vez del check generico. Ver doc 26.
    es_constitucion = any(es._norm(t) == "constitucion" for t in tipos)
    asignados = nc.people_names(props.get(ASIGNADO, {}))
    asesor = asignados[0] if asignados else ""

    log.info("tickets tipo=%s page_id=%s cliente_present=%s email_present=%s mensaje_present=%s asunto_custom=%s adjuntos_n=%d asesor=%r",
             tipo_correo, page_id, bool(cliente), bool(email), bool(mensaje), bool(asunto_custom), len(adjuntos), asesor)

    if not email:
        motivo = "fila sin Email (columna Email vacía)"
        alertas.avisar_fallo_asesor(asesor, cliente, "", motivo)
        return {"ok": False, "motivo": motivo}
    if not cliente:
        motivo = "fila sin Tarea (nombre de cliente, necesario)"
        alertas.avisar_fallo_asesor(asesor, cliente, "", motivo)
        return {"ok": False, "motivo": motivo}

    estandar = estandar_tpl.format(tipo=tipo)
    b_msg = _bloque_mensaje(mensaje, estandar)
    b_det = _bloque_detalle(tipo_correo, estado, fecha_prom, len(adjuntos), es_constitucion)
    b_banner = _bloque_banner_completado(tipo, es_constitucion) if tipo_correo == "completado" else ("", "")
    # El monto se muestra en Cobranza ("Total a pagar" + fecha límite) y en
    # Completado de Constitución ("Honorario a pagar", SIN fecha límite: doc 26).
    if tipo_correo == "cobranza":
        b_monto = _bloque_monto(monto, fecha_limite)
    elif tipo_correo == "completado" and es_constitucion:
        b_monto = _bloque_monto(monto, "", titulo="Honorario a pagar")
    else:
        b_monto = ("", "")
    extra_vars = {
        "tipo": tipo,
        "bloque_banner": b_banner[0], "linea_banner": b_banner[1],
        "bloque_mensaje": b_msg[0], "linea_mensaje": b_msg[1],
        "bloque_monto": b_monto[0], "linea_monto": b_monto[1],
        "bloque_detalle": b_det[0], "linea_detalle": b_det[1],
    }
    # Asunto: override manual (columna Asunto) o el automatico por tipo.
    asunto = asunto_custom.strip() if asunto_custom.strip() else asunto_tpl.format(tipo=tipo)

    try:
        remitente = es.enviar(
            destinatario=email,
            nombre=cliente,
            mes="",            # Tickets no usa periodo/fecha límite
            monto="0",         # ni monto
            nombre_asesor=asesor,
            adjuntos=adjuntos,
            template=plantilla,
            asunto=asunto,
            extra_vars=extra_vars,
        )
        log.info("correo tickets/%s enviado OK · page_id=%s remitente=%s", tipo_correo, page_id, remitente)
    except ValueError as exc:
        log.error("error envio tickets · page_id=%s · %s", page_id, exc)
        alertas.avisar_fallo_asesor(asesor, cliente, "", str(exc))
        return {"ok": False, "motivo": str(exc)}
    except Exception as exc:
        log.error("error SMTP tickets · page_id=%s · %s", page_id, exc)
        motivo = f"error SMTP: {exc}"
        alertas.avisar_fallo_asesor(asesor, cliente, "", motivo)
        return {"ok": False, "motivo": motivo}

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
