"""Compone y envía el correo del F29 via SMTP de Gmail.

Carga la plantilla de email_templates/ y reemplaza {{marcadores}}.
Contenido: monto (Impuestos) + fecha límite + honorarios (con datos de
transferencia) + info adicional opcional.

El remitente es el asesor asignado al cliente (columna Adviser Accounting),
no una cuenta genérica. Cada asesor envía desde su propio Gmail con su
App Password (ver asesores_smtp.json).
"""
from __future__ import annotations
import os
import smtplib
import ssl
import datetime
import json
import re
from html import escape as _escape
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from pathlib import Path

LOGO_PATH = Path(__file__).parent.parent / "LOGO-GCP.png"

TEMPLATES = Path(__file__).parent / "email_templates"
ASESORES_JSON = Path(__file__).parent / "asesores_smtp.json"
ASUNTO = "Asesoria Honorario"

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
    """Carga las credenciales de los asesores.

    Orden de prioridad (cloud-ready):
    1. Env var ASESORES_SMTP_JSON (Render/Cloud Run) — el JSON completo como string.
    2. Archivo asesores_smtp.json local (desarrollo).
    Así el repo se clona sin credenciales y Render las inyecta por env var.
    """
    raw = os.environ.get("ASESORES_SMTP_JSON")
    if raw:
        return json.loads(raw)
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


def fecha_larga(d: datetime.date) -> str:
    return f"{_DIAS[d.weekday()]} {d.day} de {_MI[d.month]} de {d.year}"


def _variantes(monto_str: str, periodo: str) -> tuple[str, str]:
    try:
        n = float(monto_str)
    except (ValueError, TypeError):
        n = 0.0
    if n > 0:
        return "IMPUESTOS A PAGAR", ""
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


def render(
    nombre: str, periodo: str, monto: str, asesor: str, contacto: str,
    logo_url: str, honorarios: str = "", info_valor: str = "", info_motivo: str = "",
    firma_html: str = "",
) -> tuple[str, str]:
    """Carga la plantilla y reemplaza los marcadores. Devuelve (html, txt)."""
    titulo, msg = _variantes(monto, periodo)
    try:
        n = float(monto)
    except (ValueError, TypeError):
        n = 0.0

    b_fecha = ("", "")
    if n > 0:
        d = fecha_limite(periodo)
        if d:
            b_fecha = _bloque_fecha(d)
    b_hono = _bloque_honorarios(honorarios)
    b_info = _bloque_info(info_valor, info_motivo)
    info_texto = _combinar_info(info_valor, info_motivo)

    vars_ = {
        "logo_url": "cid:logo-gcp",
        "bloque_firma": firma_html,
        "nombre_cliente": nombre,
        "periodo": periodo,
        "monto": clp(monto),
        "titulo_resultado": titulo,
        "mensaje_resultado": msg,
        "bloque_mensaje_resultado": (
            f'<div style="font-size:14px;color:#c9d6ea;margin-top:10px;line-height:1.5;">{msg}</div>'
            if msg else ""
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
    }
    html = (TEMPLATES / "f29_email.html").read_text(encoding="utf-8")
    txt = (TEMPLATES / "f29_email.txt").read_text(encoding="utf-8")
    for k, v in vars_.items():
        html = html.replace("{{" + k + "}}", v)
        txt = txt.replace("{{" + k + "}}", v)
    return html, txt


def enviar(
    destinatario: str,
    nombre: str,
    mes: str,
    monto: str,
    nombre_asesor: str = "",
    honorarios: str = "",
    info_valor: str = "",
    info_motivo: str = "",
    contacto: str | None = None,
    logo_url: str | None = None,
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
        if asesor_info and asesor_info.get("password") and not asesor_info.get("pendiente"):
            remitente_email = asesor_info["email"]
            remitente_pass = asesor_info["password"]
            asesor_firma = asesor_info.get("nombre", nombre_asesor)
        elif asesor_info and asesor_info.get("pendiente"):
            raise ValueError(
                f"Asesor '{nombre_asesor}' ({asesor_info['email']}) no tiene App Password aún (pendiente). "
                f"No se puede enviar el correo desde su cuenta."
            )

    if not remitente_pass:
        raise ValueError(
            f"No se encontró contraseña SMTP para el remitente {remitente_email}. "
            f"Verifica asesores_smtp.json."
        )

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
            f'<img src="cid:firma-asesor" alt="{asesor_firma}" '
            f'style="width:600px;max-width:100%;height:auto;display:block;border:0;margin:6px 0 8px;">'
        )
    else:
        firma_html = (
            f'<p style="margin:0 0 24px 0;font-size:14px;line-height:1.5;">'
            f'<b>{asesor_firma}</b><br/>'
            f'<span style="color:#5a6b82;">GCP · Asesoría Contable</span></p>'
        )

    html, txt = render(
        nombre, mes, monto, asesor_firma, contacto, logo_url,
        honorarios, info_valor, info_motivo, firma_html,
    )

    # Mensaje "related" (no "alternative") para que las imágenes inline (logo + firma)
    # se asocien al cuerpo y Gmail las muestre en vez de tratarlas como adjuntos sueltos.
    msg = MIMEMultipart("related")
    msg["Subject"] = ASUNTO
    msg["From"] = f"{asesor_firma} · GCP <{remitente_email}>"
    msg["To"] = destinatario
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(txt, "plain", "utf-8"))
    alt.attach(MIMEText(html, "html", "utf-8"))
    msg.attach(alt)

    # Logo GCP inline (Content-ID: logo-gcp). _subtype="png" evita imghdr (removido en Python 3.13+).
    if LOGO_PATH.is_file():
        with open(LOGO_PATH, "rb") as fh:
            _logo = MIMEImage(fh.read(), _subtype="png")
        _logo.add_header("Content-ID", "<logo-gcp>")
        _logo.add_header("Content-Disposition", "inline", filename="logo-gcp.png")
        msg.attach(_logo)

    # Firma del asesor inline (Content-ID: firma-asesor)
    if firma_png:
        with open(firma_png, "rb") as fh:
            _firma = MIMEImage(fh.read(), _subtype="png")
        _firma.add_header("Content-ID", "<firma-asesor>")
        _firma.add_header("Content-Disposition", "inline", filename="firma-asesor.png")
        msg.attach(_firma)

    # SMTP Gmail — puerto 465 (SSL). App Password sin espacios.
    pass_clean = remitente_pass.replace(" ", "")
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=30) as server:
        server.login(remitente_email, pass_clean)
        server.sendmail(remitente_email, [destinatario], msg.as_string())

    return remitente_email
