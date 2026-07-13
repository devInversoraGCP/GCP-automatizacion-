"""Compone y envía el correo del F29.

Envío: API HTTPS de SendGrid si hay SENDGRID_API_KEY (nube/Render, que bloquea
SMTP); si no, SMTP de Gmail con App Password (local, ver asesores_smtp.json).

Carga la plantilla de email_templates/ y reemplaza {{marcadores}}.
Contenido: monto (Impuestos) + fecha límite + honorarios (con datos de
transferencia) + info adicional opcional.

El remitente es el asesor asignado al cliente (columna Adviser Accounting),
que debe estar verificado en SendGrid (Single Sender o dominio).
"""
from __future__ import annotations
import os
import smtplib
import ssl
import datetime
import json
import re
import base64
import mimetypes
import requests
from http_util import request_con_reintentos
from html import escape as _escape
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

LOGO_PATH = Path(__file__).parent.parent / "LOGO-GCP.png"

TEMPLATES = Path(__file__).parent / "email_templates"
ASESORES_JSON = Path(__file__).parent / "asesores_smtp.json"
# Copia local CON credenciales (gitignored). El versionado va SIN passwords (Fase 0, doc 27).
ASESORES_JSON_LOCAL = Path(__file__).parent / "asesores_smtp.local.json"
ASUNTO_BASE = "Resumen impuestos"   # el asunto se completa con el mes: "Resumen impuestos Junio"

_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11,
    "diciembre": 12,
}
_MI = {v: k for k, v in _MESES.items()}
_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

FERIADOS_CL = {
    2026: {
        "2026-01-01", "2026-04-03", "2026-04-04", "2026-05-01", "2026-05-21",
        "2026-06-21", "2026-06-29", "2026-07-16", "2026-08-15", "2026-09-18",
        "2026-09-19", "2026-10-12", "2026-10-31", "2026-11-01", "2026-12-08",
        "2026-12-25",
    },
}

BCC_EXTRA = [
    "carloscereceda@inversoragcp.com",
]

PREVIRED_URL = "https://www.previred.com/wPortal/login/login.jsp"

BANCO_GCP_HTML = (
    "Banco Santander · Cuenta Corriente<br>N° 0-000-8577678-9<br>"
    "RUT: 76.976.672-3<br>Razón Social: Inversora GCP Ltda"
)
BANCO_GCP_TXT = (
    "Banco Santander, Cuenta Corriente N° 0-000-8577678-9, "
    "RUT 76.976.672-3, Razón Social Inversora GCP Ltda"
)


def _norm(s: str) -> str:
    """Normaliza un nombre para matching: minúsculas, sin tildes, sin espacios extra."""
    import unicodedata
    s = (s or "").lower().strip()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return " ".join(s.split())


def _cargar_asesores() -> dict:
    """Carga el directorio de asesores (y sus credenciales SMTP si las hay).

    Orden de prioridad (Fase 0 del plan de robustez, doc 27):
    1. Env var ASESORES_SMTP_JSON (Render/Cloud Run) — el JSON completo como string.
    2. asesores_smtp.local.json (gitignored) — copia local CON passwords, solo dev.
    3. asesores_smtp.json (versionado) — SIN passwords; en la nube basta porque
       el envío va por SendGrid API (no usa SMTP).
    Así el repo nunca lleva credenciales y el fallback SMTP local sigue funcionando.
    """
    raw = os.environ.get("ASESORES_SMTP_JSON")
    if raw:
        return json.loads(raw)
    if ASESORES_JSON_LOCAL.is_file():
        with open(ASESORES_JSON_LOCAL, encoding="utf-8") as f:
            return json.load(f)
    with open(ASESORES_JSON, encoding="utf-8") as f:
        return json.load(f)


def _buscar_asesor_por_nombre(nombre_asesor: str) -> dict | None:
    """Busca el asesor en asesores_smtp.json por nombre normalizado.
    Devuelve el dict del asesor o None si no lo encuentra."""
    data = _cargar_asesores()
    norm = _norm(nombre_asesor)
    for email, info in data.items():
        if email.startswith("_"):
            continue
        if info.get("nombre_norm") == norm:
            return {"email": email, **info}
    return None


def clp(monto: str | int | float) -> str:
    try:
        n = int(round(float(monto)))
        return "$" + f"{n:,}".replace(",", ".")
    except (ValueError, TypeError):
        return "$0"


_MONEY_RE = re.compile(r"\$\s?\d[\d.]*")
_VARS_RE = re.compile(
    r"(remanente|saldo a favor|crédito fiscal|débito fiscal|impuesto único|"
    r"retención|reajuste|multa|interés|PPM)",
    re.IGNORECASE,
)


def _resaltar(texto: str) -> str:
    """Escapa HTML y pone en negrita los montos ($…) y las variables clave
    (remanente, saldo a favor, etc.) del texto libre de 'Info Adicional'."""
    t = _escape(texto)
    t = _MONEY_RE.sub(lambda m: f"<b>{m.group(0)}</b>", t)
    t = _VARS_RE.sub(lambda m: f"<b>{m.group(0)}</b>", t)
    return t


def _es_habil(d: datetime.date) -> bool:
    return d.weekday() < 5 and d.isoformat() not in FERIADOS_CL.get(d.year, set())


def fecha_limite(periodo: str) -> datetime.date | None:
    p = periodo.strip().lower().split()
    mes = next((_MESES[x] for x in p if x in _MESES), None)
    anio = next((int(x) for x in p if x.isdigit() and len(x) == 4), None)
    if not mes or not anio:
        return None
    m2, a2 = (mes + 1, anio) if mes < 12 else (1, anio + 1)
    d = datetime.date(a2, m2, 20)
    while not _es_habil(d):
        d += datetime.timedelta(days=1)
    return d


def fecha_limite_rrhh(periodo: str) -> datetime.date | None:
    """'Junio 2026' → día 13 del mes SIGUIENTE; si no es hábil,
    se traslada al siguiente día hábil. Siempre a las 13:45."""
    p = periodo.strip().lower().split()
    mes = next((_MESES[x] for x in p if x in _MESES), None)
    anio = next((int(x) for x in p if x.isdigit() and len(x) == 4), None)
    if not mes or not anio:
        return None
    m2, a2 = (mes + 1, anio) if mes < 12 else (1, anio + 1)
    d = datetime.date(a2, m2, 13)
    while not _es_habil(d):
        d += datetime.timedelta(days=1)
    return d


def fecha_larga(d: datetime.date) -> str:
    return f"{_DIAS[d.weekday()]} {d.day} de {_MI[d.month]} de {d.year}"


def _mes_nombre(periodo: str) -> str:
    """Nombre del mes (capitalizado) del periodo. 'Junio 2026' -> 'Junio'. '' si no se reconoce."""
    for p in (periodo or "").strip().lower().split():
        if p in _MESES:
            return p.capitalize()
    return ""


def _variantes(monto_str: str, periodo: str) -> tuple[str, str]:
    try:
        n = float(monto_str)
    except (ValueError, TypeError):
        n = 0.0
    if n > 0:
        return "Impuesto a pagar", ""
    if n < 0:
        return "Saldo a favor", "Este mes no paga IVA: el saldo queda a su favor y se arrastra al próximo período."
    return "Sin pago este mes", f"Su Formulario 29 del período {periodo} se declara sin movimiento; este mes no paga IVA."


def _bloque_fecha(d: datetime.date) -> tuple[str, str]:
    f = fecha_larga(d)
    html = (
        f'<p style="margin:0 0 18px 0;font-size:14px;line-height:1.6;color:#3a4658;">'
        f'<b>Fecha límite de pago:</b> {f}.</p>'
    )
    txt = f"Fecha límite de pago: {f}."
    return html, txt


def _bloque_fecha_rrhh(d: datetime.date) -> tuple[str, str]:
    f = fecha_larga(d)
    html = (
        f'<p style="margin:0 0 8px 0;font-size:14px;line-height:1.6;color:#3a4658;">'
        f'<b>Plazo hasta</b> {f} a las 13.45 horas.</p>'
        f'<p style="margin:0 0 18px 0;font-size:14px;line-height:1.6;color:#3a4658;">'
        f'Puede pagar directamente en la página de '
        f'<a href="{PREVIRED_URL}" style="color:#0B1F3A;font-weight:700;">Previred</a>.</p>'
    )
    txt = (
        f"Plazo hasta {f} a las 13.45 horas.\n"
        f"Puede pagar directamente en la pagina de Previred: {PREVIRED_URL}"
    )
    return html, txt


def _bloque_honorarios(monto_h: str) -> tuple[str, str]:
    try:
        h = float(monto_h)
    except (ValueError, TypeError):
        h = 0.0
    if h <= 0:
        return "", ""
    m = clp(h)
    html = (
        '<div style="margin:0 0 18px 0;background:#fff8ec;border:1px solid #f2e2bf;'
        'border-left:4px solid #E7A100;border-radius:12px;padding:18px 22px;">'
        '<div style="font-size:12px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;'
        'color:#9a7400;margin-bottom:6px;">Honorarios de la asesoría</div>'
        f'<div style="font-size:26px;font-weight:800;color:#9a7400;'
        f'font-variant-numeric:tabular-nums;line-height:1.05;">{m}</div>'
        '<div style="margin-top:12px;padding:12px 14px;background:#fff;border:1px solid #e6d9b8;'
        'border-radius:8px;font-size:13px;color:#3a4658;line-height:1.7;">'
        f'<div style="font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;'
        f'color:#9a7400;margin-bottom:6px;">Datos para la transferencia</div>'
        f'{BANCO_GCP_HTML}</div></div>'
    )
    txt = (
        f"Honorarios de la asesoría: {m}. "
        f"Datos para la transferencia: {BANCO_GCP_TXT}."
    )
    return html, txt


def _combinar_info(valor: str, motivo: str) -> str:
    """Combina valor (numero) + motivo (select) en un texto natural.
    - ambos: 'Remanente: $417.798'
    - solo valor: '$417.798'
    - solo motivo: 'Remanente'
    - ninguno: ''"""
    v = (valor or "").strip()
    m = (motivo or "").strip()
    if v and m:
        return f"{m}: {clp(v)}"
    if v:
        return clp(v)
    if m:
        return m
    return ""


def _bloque_info(valor: str, motivo: str) -> tuple[str, str]:
    """Bloque de informacion adicional. Recibe valor (numero) + motivo (select).
    Si ambos vacios, no se inyecta (devuelve ('', ''))."""
    t = _combinar_info(valor, motivo)
    if not t:
        return "", ""
    t_html = _resaltar(t)
    html = (
        '<div style="margin:0 0 18px 0;background:#f4f6fa;border:1px solid #dfe5ee;'
        'border-radius:10px;padding:14px 18px;">'
        '<div style="font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;'
        'color:#5a6b82;margin-bottom:3px;">Información adicional</div>'
        f'<div style="font-size:14px;color:#3a4658;line-height:1.55;">{t_html}</div></div>'
    )
    txt = f"Información adicional: {t}"
    return html, txt


def _bloque_adjuntos(mensaje: str) -> tuple[str, str]:
    """Nota/mensaje del asesor sobre los archivos adjuntos. Vacio -> ('', '')."""
    t = (mensaje or "").strip()
    if not t:
        return "", ""
    t_html = _escape(t).replace("\n", "<br>")
    html = (
        '<div style="margin:0 0 18px 0;background:#eef4ff;border:1px solid #d3e0f5;'
        'border-left:4px solid #0B1F3A;border-radius:10px;padding:14px 18px;">'
        '<div style="font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;'
        'color:#3a5a8c;margin-bottom:3px;">Archivos adjuntos</div>'
        f'<div style="font-size:14px;color:#3a4658;line-height:1.55;">{t_html}</div></div>'
    )
    txt = f"Archivos adjuntos: {t}"
    return html, txt


def render(
    nombre: str, periodo: str, monto: str, asesor: str, contacto: str,
    logo_url: str, honorarios: str = "", info_valor: str = "", info_motivo: str = "",
    msg_adjuntos: str = "", firma_html: str = "",
    template: str = "f29_email",
    titulo_override: str = "", mensaje_override: str = "",
    bloque_fecha_override: str = "", linea_fecha_override: str = "",
    extra_vars: dict | None = None,
) -> tuple[str, str]:
    """Carga la plantilla y reemplaza los marcadores. Devuelve (html, txt)."""
    if titulo_override:
        titulo, msg = titulo_override, mensaje_override
    else:
        titulo, msg = _variantes(monto, periodo)
    try:
        n = float(monto)
    except (ValueError, TypeError):
        n = 0.0

    if bloque_fecha_override:
        b_fecha = (bloque_fecha_override, linea_fecha_override)
    else:
        b_fecha = ("", "")
        if n > 0:
            d = fecha_limite(periodo)
            if d:
                b_fecha = _bloque_fecha(d)
    b_hono = _bloque_honorarios(honorarios)
    b_info = _bloque_info(info_valor, info_motivo)
    b_adj = _bloque_adjuntos(msg_adjuntos)
    info_texto = _combinar_info(info_valor, info_motivo)

    vars_ = {
        "logo_url": "cid:logo-gcp",
        "bloque_firma": firma_html,
        "nombre_cliente": nombre,
        "periodo": periodo,
        "monto": clp(monto),
        "titulo_resultado": titulo,
        "mensaje_resultado": mensaje_override if mensaje_override else msg,
        "bloque_mensaje_resultado": (
            f'<div style="font-size:14px;color:#c9d6ea;margin-top:10px;line-height:1.5;">{mensaje_override if mensaje_override else msg}</div>'
            if (mensaje_override or msg) else ""
        ),
        "asesor": asesor,
        "contacto_email": contacto,
        "bloque_fecha_limite": b_fecha[0],
        "linea_fecha_limite": b_fecha[1],
        "bloque_honorarios": b_hono[0],
        "linea_honorarios": b_hono[1],
        "bloque_info_adicional": b_info[0],
        "linea_info_adicional": b_info[1],
        "info_adicional_texto": info_texto,
        "bloque_adjuntos": b_adj[0],
        "linea_adjuntos": b_adj[1],
    }
    html_path = TEMPLATES / f"{template}.html"
    txt_path = TEMPLATES / f"{template}.txt"
    if not html_path.is_file():
        html_path = TEMPLATES / "f29_email.html"
    if not txt_path.is_file():
        txt_path = TEMPLATES / "f29_email.txt"
    html = html_path.read_text(encoding="utf-8")
    txt = txt_path.read_text(encoding="utf-8")
    if extra_vars:
        vars_.update({k: (v if isinstance(v, str) else str(v)) for k, v in extra_vars.items()})
    for k, v in vars_.items():
        html = html.replace("{{" + k + "}}", v)
        txt = txt.replace("{{" + k + "}}", v)
    return html, txt


MAX_ADJUNTOS_MB = 15   # tope total de adjuntos (los correos rebotan pasados ~25 MB)


def _descargar_adjuntos(adjuntos):
    """Descarga los archivos de la columna 'Adjuntos' de Notion (URLs firmadas
    temporales) -> [(nombre, bytes, mime)]. Respeta un tope total de tamano;
    si se excede, deja de agregar. No loguea contenido."""
    out, total = [], 0
    tope = MAX_ADJUNTOS_MB * 1024 * 1024
    for a in (adjuntos or []):
        url = (a or {}).get("url")
        nombre = (a or {}).get("name") or "adjunto"
        if not url:
            continue
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
        except Exception:
            continue
        data = r.content
        if total + len(data) > tope:
            break
        total += len(data)
        mime = mimetypes.guess_type(nombre)[0] or "application/octet-stream"
        out.append((nombre, data, mime))
    return out


def enviar(
    destinatario: str,
    nombre: str,
    mes: str,
    monto: str,
    nombre_asesor: str = "",
    honorarios: str = "",
    info_valor: str = "",
    info_motivo: str = "",
    msg_adjuntos: str = "",
    adjuntos: list | None = None,
    contacto: str | None = None,
    logo_url: str | None = None,
    template: str = "f29_email",
    asunto: str | None = None,
    extra_vars: dict | None = None,
) -> str:
    """Envía el correo por SMTP de Gmail. El remitente es el asesor del cliente.
    Devuelve el email del remitente usado (para log sin PII del destinatario)."""
    contacto = contacto or os.environ.get("EMAIL_CONTACTO", "contacto@gcp.cl")
    logo_url = logo_url or os.environ.get("LOGO_URL", "https://gcp.cl/logo.png")

    # Determinar remitente: el asesor del cliente, o fallback a EMAIL_FROM
    remitente_email = os.environ.get("EMAIL_FROM", "notificaciones@inversoragcp.com")
    remitente_pass = None
    asesor_firma = nombre_asesor or "Equipo GCP"
    asesor_info = None

    if nombre_asesor:
        asesor_info = _buscar_asesor_por_nombre(nombre_asesor)
        if asesor_info and asesor_info.get("pendiente"):
            raise ValueError(
                f"Asesor '{nombre_asesor}' ({asesor_info['email']}) marcado como pendiente. "
                f"No se puede enviar desde su cuenta todavía."
            )
        if asesor_info:
            remitente_email = asesor_info["email"]
            asesor_firma = asesor_info.get("nombre", nombre_asesor)
            remitente_pass = asesor_info.get("password")   # solo lo usa el fallback SMTP local

    # Firma del asesor: imagen inline (CID) si tiene firma_png; si no, texto simple con su nombre.
    # firma_png puede ser ruta absoluta o relativa al paquete notion_automation/ (cloud-ready).
    firma_png = None
    if asesor_info and asesor_info.get("firma_png"):
        p = Path(asesor_info["firma_png"])
        if not p.is_absolute():
            p = Path(__file__).parent / p
        if p.is_file():
            firma_png = str(p)
    if firma_png:
        firma_html = (
            f'<img src="cid:firma-asesor" alt="{asesor_firma}" border="0" '
            f'style="width:600px;max-width:100%;height:auto;display:block;border:none;outline:none;margin:6px 0 8px;">'
        )
    else:
        firma_html = (
            f'<p style="margin:0 0 24px 0;font-size:14px;line-height:1.5;">'
            f'<b>{asesor_firma}</b><br/>'
            f'<span style="color:#5a6b82;">GCP · Asesoría Contable</span></p>'
        )

    if template == "rrhh_email":
        d_rrhh = fecha_limite_rrhh(mes)
        b_fecha_rrhh = _bloque_fecha_rrhh(d_rrhh) if d_rrhh else ("", "")
        html, txt = render(
            nombre, mes, monto, asesor_firma, contacto, logo_url,
            honorarios, info_valor, info_motivo, msg_adjuntos, firma_html,
            template=template,
            titulo_override="Imposiciones a pagar",
            bloque_fecha_override=b_fecha_rrhh[0],
            linea_fecha_override=b_fecha_rrhh[1],
        )
    else:
        html, txt = render(
            nombre, mes, monto, asesor_firma, contacto, logo_url,
            honorarios, info_valor, info_motivo, msg_adjuntos, firma_html,
            template=template,
            extra_vars=extra_vars,
        )

    # Asunto: si se pasa explícito, usarlo; si no, dinámico por mes (F29).
    if asunto:
        asunto_final = asunto
    else:
        mes_nombre = _mes_nombre(mes)
        asunto_final = f"{ASUNTO_BASE} {mes_nombre}" if mes_nombre else ASUNTO_BASE

    # Descargar adjuntos (PDFs de la columna "Adjuntos" de Notion), con tope de tamano.
    adjuntos_bin = _descargar_adjuntos(adjuntos)

    # === Envío ===
    # En la nube (Render BLOQUEA SMTP) se usa la API HTTPS de SendGrid si hay SENDGRID_API_KEY.
    # En local, si no hay key, cae al SMTP de Gmail (requiere App Password del asesor).
    if os.environ.get("SENDGRID_API_KEY"):
        _enviar_via_sendgrid(
            os.environ["SENDGRID_API_KEY"],
            remitente_email, asesor_firma, destinatario, asunto_final, html, txt, firma_png,
            adjuntos_bin,
        )
        return remitente_email

    # --- Fallback local: SMTP Gmail (puerto 465, SSL) ---
    if not remitente_pass:
        raise ValueError(
            f"No hay SENDGRID_API_KEY ni App Password SMTP para {remitente_email}. "
            f"Configura SendGrid (nube) o el App Password en asesores_smtp.json (local)."
        )

    # Mensaje "related" para que las imágenes inline (logo + firma) se vean en el cuerpo.
    msg = MIMEMultipart("related")
    msg["Subject"] = asunto_final
    msg["From"] = f"{asesor_firma} · GCP <{remitente_email}>"
    msg["To"] = destinatario
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(txt, "plain", "utf-8"))
    alt.attach(MIMEText(html, "html", "utf-8"))
    msg.attach(alt)

    if LOGO_PATH.is_file():
        with open(LOGO_PATH, "rb") as fh:
            _logo = MIMEImage(fh.read(), _subtype="png")
        _logo.add_header("Content-ID", "<logo-gcp>")
        _logo.add_header("Content-Disposition", "inline", filename="logo-gcp.png")
        msg.attach(_logo)

    if firma_png:
        _sub = "jpeg" if firma_png.lower().endswith((".jpg", ".jpeg")) else "png"
        with open(firma_png, "rb") as fh:
            _firma = MIMEImage(fh.read(), _subtype=_sub)
        _firma.add_header("Content-ID", "<firma-asesor>")
        _firma.add_header("Content-Disposition", "inline", filename=f"firma-asesor.{_sub}")
        msg.attach(_firma)

    # Adjuntos (PDFs) descargados de Notion
    for _name, _data, _mime in adjuntos_bin:
        _maintype, _, _subt = _mime.partition("/")
        _part = MIMEBase(_maintype or "application", _subt or "octet-stream")
        _part.set_payload(_data)
        encoders.encode_base64(_part)
        _part.add_header("Content-Disposition", "attachment", filename=_name)
        msg.attach(_part)

    pass_clean = remitente_pass.replace(" ", "")
    # BCC al asesor + extra (BCC_EXTRA) sin header visible.
    rcpt = [destinatario]
    if remitente_email.lower() != destinatario.lower():
        rcpt.append(remitente_email)
    for _bcc in BCC_EXTRA:
        if _bcc.lower() != destinatario.lower():
            rcpt.append(_bcc)
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=30) as server:
        server.login(remitente_email, pass_clean)
        server.sendmail(remitente_email, rcpt, msg.as_string())

    return remitente_email


def _enviar_via_sendgrid(api_key, remitente_email, asesor_firma, destinatario,
                         asunto, html, txt, firma_png, adjuntos_bin=None):
    """Envía el correo por la API HTTPS de SendGrid (Render bloquea SMTP).
    Logo + firma van como adjuntos inline (content_id) para verse en el cuerpo.
    El remitente (remitente_email) DEBE estar verificado en SendGrid (Single
    Sender o dominio), si no SendGrid responde 403."""
    attachments = []

    def _inline(path, cid, filename, ctype):
        with open(path, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode("ascii")
        attachments.append({
            "content": b64, "type": ctype, "filename": filename,
            "disposition": "inline", "content_id": cid,
        })

    if LOGO_PATH.is_file():
        _inline(LOGO_PATH, "logo-gcp", "logo-gcp.png", "image/png")
    if firma_png:
        ctype = "image/jpeg" if firma_png.lower().endswith((".jpg", ".jpeg")) else "image/png"
        _inline(firma_png, "firma-asesor", "firma-asesor", ctype)

    # Adjuntos (PDFs) — disposition "attachment" (no inline)
    for _name, _data, _mime in (adjuntos_bin or []):
        attachments.append({
            "content": base64.b64encode(_data).decode("ascii"),
            "type": _mime, "filename": _name, "disposition": "attachment",
        })

    # BCC al asesor + extra (BCC_EXTRA): copia exacta.
    # SendGrid exige que to/cc/bcc no se repitan, por eso el guard con set.
    bcc_set = set()
    if remitente_email.lower() != destinatario.lower():
        bcc_set.add(remitente_email.lower())
    for _bcc in BCC_EXTRA:
        bcc_set.add(_bcc.lower())
    bcc_set.discard(destinatario.lower())
    personalization = {"to": [{"email": destinatario}]}
    if bcc_set:
        personalization["bcc"] = [{"email": e} for e in sorted(bcc_set)]

    payload = {
        "personalizations": [personalization],
        "from": {"email": remitente_email, "name": f"{asesor_firma} · GCP"},
        "subject": asunto,
        "content": [
            {"type": "text/plain", "value": txt},
            {"type": "text/html", "value": html},
        ],
    }
    if attachments:
        payload["attachments"] = attachments

    # Reintentos ante 5xx/429/timeout transitorios de SendGrid (Fase 2, H6): un
    # hipo no debe perder el correo. El 403 (remitente no verificado) NO se
    # reintenta (es 4xx definitivo) -> cae directo al ValueError de abajo.
    r = request_con_reintentos(
        "POST",
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload, timeout=30,
    )
    if r.status_code not in (200, 202):
        raise ValueError(f"SendGrid rechazo el envio (HTTP {r.status_code}): {r.text[:300]}")


def admin_emails() -> list[str]:
    """Lista de correos admin desde ADMIN_ALERT_EMAIL (separados por coma).
    '' o no seteada -> lista vacia. Usado por enviar_aviso_error (cc) y por
    alertas.avisar_excepcion_admin (destinatario)."""
    raw = os.environ.get("ADMIN_ALERT_EMAIL", "")
    return [e.strip() for e in raw.split(",") if e.strip()]


def enviar_aviso_error(email_asesor: str, cliente: str, mes: str, motivo: str) -> bool:
    """Aviso automatico al asesor cuando el correo de un cliente NO se pudo enviar.
    Best-effort: nunca lanza excepcion (si el propio aviso falla, devuelve False y
    queda solo el log del backend). Requiere SENDGRID_API_KEY (nube).
    Limite conocido: si SendGrid entero esta caido, este aviso tampoco sale.

    Fase 1 (doc 27, observabilidad): copia en ADMIN_ALERT_EMAIL si esta seteada,
    para que el administrador vea TODOS los fallos (F29/RRHH/Tickets) en un solo
    buzon, no solo el asesor de cada cliente."""
    try:
        api_key = os.environ.get("SENDGRID_API_KEY")
        if not (api_key and email_asesor):
            return False
        remitente = os.environ.get("EMAIL_FROM", "notificaciones@inversoragcp.com")
        asunto = f"AVISO: no se envio el correo F29 de {cliente}"
        cuerpo = (
            f"El correo del F29 de {cliente} (periodo {mes or 'desconocido'}) NO se pudo enviar.\n\n"
            f"Motivo: {motivo}\n\n"
            "Que hacer: revisa la fila en Notion (Email, Month, Adviser Accounting, Adjuntos) "
            "y vuelve a apretar el boton. El Status de la fila NO fue cambiado.\n\n"
            "— Aviso automatico del sistema AuditAI (no responder)."
        )
        html = (
            '<div style="font-family:Arial,sans-serif;max-width:560px;">'
            '<div style="background:#fff3f3;border:1px solid #f3c2c2;border-left:4px solid #c0392b;'
            'border-radius:10px;padding:16px 20px;">'
            f'<p style="margin:0 0 10px 0;"><b>El correo del F29 de {_escape(cliente)}</b> '
            f'(periodo {_escape(mes or "desconocido")}) <b>NO se pudo enviar.</b></p>'
            f'<p style="margin:0 0 10px 0;"><b>Motivo:</b> {_escape(motivo)}</p>'
            '<p style="margin:0;"><b>Que hacer:</b> revisa la fila en Notion (Email, Month, '
            'Adviser Accounting, Adjuntos) y vuelve a apretar el boton. '
            'El Status de la fila no fue cambiado.</p></div>'
            '<p style="color:#8593a8;font-size:12px;">Aviso automatico del sistema AuditAI (no responder).</p>'
            '</div>'
        )
        personalization = {"to": [{"email": email_asesor}]}
        admins = [a for a in admin_emails() if a.lower() != email_asesor.lower()]
        if admins:
            personalization["cc"] = [{"email": a} for a in admins]
        payload = {
            "personalizations": [personalization],
            "from": {"email": remitente, "name": "AuditAI · Avisos"},
            "subject": asunto,
            "content": [
                {"type": "text/plain", "value": cuerpo},
                {"type": "text/html", "value": html},
            ],
        }
        r = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload, timeout=15,
        )
        return r.status_code in (200, 202)
    except Exception:
        return False
