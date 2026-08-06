"""enviar_aviso_cambio_mes.py — envía a los asesores el instructivo de cambio de mes.

Remitente FIJO: dev@inversoragcp.com. Pensado para un cron mensual (Render), como
recordatorio al abrir el mes nuevo. Reusa el HTML de `correo-cambio-mes.html` (raíz
del repo): le quita la barra de previsualización y adjunta el logo GCP inline (CID),
porque Gmail suele bloquear imágenes embebidas en base64.

Best-effort: si falta SENDGRID_API_KEY, no envía (solo log), sin romper el cron.

Uso:  python enviar_aviso_cambio_mes.py            # envía
      python enviar_aviso_cambio_mes.py --dry      # arma el correo pero NO envía
"""
from __future__ import annotations
import os
import re
import sys
import logging
import requests
from dotenv import load_dotenv

log = logging.getLogger("auditai")

REMITENTE = "dev@inversoragcp.com"       # remitente fijo pedido por el usuario
ASUNTO = "Cambio de mes en NOTION (Contable y RRHH)"
DESTINATARIOS = [
    "carloscereceda@inversoragcp.com",
    "sebastianrobles@inversoragcp.com",
]
# Inactivos (31-jul-2026): re-agregar a la lista si vuelven a rotar planillas:
#   "constanzagaggero@inversoragcp.com",
#   "andreagonzalez@inversoragcp.com",
#   "matildemateluna@inversoragcp.com",

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(_RAIZ, "correo-cambio-mes.html")


def preparar_html() -> tuple[str, str | None]:
    """(html_para_email, logo_base64|None): quita la barra de preview y cambia el
    logo base64 por `cid:logogcp` para adjuntarlo inline."""
    with open(HTML_PATH, encoding="utf-8") as fh:
        html = fh.read()
    html = re.sub(r"<!--PREVIEW-->.*?<!--/PREVIEW-->", "", html, flags=re.DOTALL)
    # Inyectar la planilla CONECTADA hoy (dinámico, robusto al cambio de mes). Si
    # la resolución falla, se deja el nombre literal que trae el HTML.
    try:
        import reconciliar as rec
        for clave, prefijo in (("contable", "Contable"), ("rrhh", "RRHH")):
            nombre = rec.nombre_base_actual(prefijo)
            if nombre:
                html = re.sub(
                    rf'(<span data-pagina="{clave}"[^>]*>)[^<]*(</span>)',
                    lambda m, n=nombre: m.group(1) + n + m.group(2), html)
    except Exception as exc:
        log.warning("no pude resolver la planilla conectada (dejo el literal): %s", exc)
    logo_b64 = None
    m = re.search(r"data:image/png;base64,([A-Za-z0-9+/=]+)", html)
    if m:
        logo_b64 = m.group(1)
        html = html.replace(m.group(0), "cid:logogcp")
    return html, logo_b64


def enviar(dry: bool = False, destinatarios: list[str] | None = None) -> bool:
    dests = destinatarios or DESTINATARIOS
    html, logo_b64 = preparar_html()
    log.info("correo listo (%d chars, logo=%s) → %d destinatario(s): %s",
             len(html), "sí" if logo_b64 else "no", len(dests), ", ".join(dests))
    if dry:
        print("DRY: correo armado, NO enviado.")
        return True
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        log.warning("sin SENDGRID_API_KEY: no se envía el aviso de cambio de mes")
        return False
    payload = {
        "personalizations": [{"to": [{"email": e} for e in dests]}],
        "from": {"email": REMITENTE, "name": "Equipo AuditAI"},
        "subject": ASUNTO,
        "content": [{"type": "text/html", "value": html}],
    }
    if logo_b64:
        payload["attachments"] = [{
            "content": logo_b64, "type": "image/png", "filename": "logo-gcp.png",
            "disposition": "inline", "content_id": "logogcp",
        }]
    r = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload, timeout=20,
    )
    ok = 200 <= r.status_code < 300
    if ok:
        log.info("aviso de cambio de mes enviado a %d destinatario(s) (status=%s)",
                 len(dests), r.status_code)
    else:
        log.error("SendGrid rechazó el aviso: %s %s", r.status_code, r.text[:300])
    return ok


def main():
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    load_dotenv()
    ap = argparse.ArgumentParser(description="Envía el instructivo de cambio de mes.")
    ap.add_argument("--dry", action="store_true", help="Arma el correo pero NO envía.")
    ap.add_argument("--to", help="Destinatario(s) coma-separados (override; p. ej. prueba a dev@).")
    args = ap.parse_args()
    dests = [e.strip() for e in args.to.split(",")] if args.to else None
    enviar(dry=args.dry, destinatarios=dests)


if __name__ == "__main__":
    main()
