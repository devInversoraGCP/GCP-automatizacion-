"""Handler del botón "Enviar Correo RRHH" para la página RRHH JUNIO 2026.
Sigue el patrón de handlers/f29.py pero con su propia lógica de composición
y fecha límite (13 del mes siguiente, no 20)."""
from __future__ import annotations
import os
import sys
import logging
from datetime import datetime, timezone
import notion_client as nc
import email_sender as es

log = logging.getLogger("auditai")

DS_ID = "9c512147-b3ea-8256-a570-871254c13b3d"
DS_CENTRAL = "4ff12147-b3ea-82f4-98dd-072067524cdc"

CLIENTE = "CLIENTE"
ASISTENTE = "ASISTENTE"
MONTO = "MONTO IMPOSICIONES|"
RUT = "RUT"
EMAIL_CLIENTE = "Email"

STATUS_COL = "Estado Correo"
# Opciones reales del status en RRHH: "Sin empezar" / "En curso" / "Listo".
# "Enviado" no existe y la API no puede crear opciones de status.
STATUS_ENVIADO = "Listo"
FECHA_COL = "Fecha Envío"

TEMPLATE = "rrhh_email"

# El select ASISTENTE usa nombres cortos ("Seba", "Carlos"...) pero
# asesores_smtp.json matchea por nombre completo normalizado.
ALIAS_ASESOR = {
    "seba": "Sebastián Robles",
    "carlos": "Carlos Cereceda",
    "andrea": "Andrea González",
    "matilde": "Matilde Mateluna",
    "constanza": "Constanza Gaggero",
}


def _buscar_email_en_central(rut: str) -> str | None:
    body = {
        "filter": {
            "property": "RUT",
            "rich_text": {"equals": rut},
        },
        "page_size": 3,
    }
    results = nc.query_data_source(DS_CENTRAL, body)
    if not results:
        return None
    props = results[0].get("properties", {})
    for col in ("email", "Email", "e-mail"):
        prop = props.get(col, {})
        val = nc.plain(prop)
        if val:
            return val
    return None


def procesar(page_id: str) -> dict:
    page = nc.get_page(page_id)
    props = page["properties"]

    nombre = nc.plain(props.get(CLIENTE, {}))
    monto_str = nc.plain(props.get(MONTO, {}))
    rut = nc.plain(props.get(RUT, {}))
    email = nc.plain(props.get(EMAIL_CLIENTE, {}))
    asistente_raw = nc.plain(props.get(ASISTENTE, {}))

    log.info("page_id=%s cliente=%r asistente=%r monto_present=%s email_propio=%s rut_present=%s",
             page_id, nombre, asistente_raw, bool(monto_str), bool(email), bool(rut))

    if not email and rut:
        encontrado = _buscar_email_en_central(rut)
        if encontrado:
            email = encontrado
            log.info("email recuperado desde base central · page_id=%s", page_id)

    if not email:
        return {"ok": False, "motivo": "fila sin Email (ni columna Email Cliente ni lookup por RUT)"}

    if not nombre:
        return {"ok": False, "motivo": "fila sin CLIENTE (necesario para el asunto y cuerpo)"}

    mes = nc.derivar_month_desde_base(page)
    if not mes:
        mes = "Junio 2026"

    asunto = f"Imposiciones {mes}- {nombre}"

    nombre_asesor = ALIAS_ASESOR.get(es._norm(asistente_raw), asistente_raw)

    try:
        remitente = es.enviar(
            destinatario=email,
            nombre=nombre,
            mes=mes,
            monto=monto_str or "0",
            nombre_asesor=nombre_asesor,
            honorarios="",
            info_valor="",
            info_motivo="",
            msg_adjuntos="",
            adjuntos=None,
            template=TEMPLATE,
            asunto=asunto,
        )
        log.info("correo RRHH enviado OK · page_id=%s remitente=%s", page_id, remitente)
    except ValueError as exc:
        log.error("error envio RRHH · page_id=%s · %s", page_id, exc)
        return {"ok": False, "motivo": str(exc)}
    except Exception as exc:
        log.error("error SMTP RRHH · page_id=%s · %s", page_id, exc)
        return {"ok": False, "motivo": f"error SMTP: {exc}"}

    # Write-back: solo columnas que existen en la fila (si falta una, no
    # aborta la otra; un PATCH con propiedad inexistente falla completo).
    now_iso = datetime.now(timezone.utc).isoformat()
    updates = {}
    if STATUS_COL in props:
        updates[STATUS_COL] = {"status": {"name": STATUS_ENVIADO}}
    else:
        log.warning("columna %r no existe en RRHH; no se escribe status", STATUS_COL)
    if FECHA_COL in props:
        updates[FECHA_COL] = {"date": {"start": now_iso}}
    else:
        log.warning("columna %r no existe en RRHH; no se escribe fecha", FECHA_COL)
    if updates:
        try:
            nc.update_props(page_id, updates)
            log.info("write-back OK (%s) · page_id=%s", ", ".join(updates), page_id)
        except Exception as exc:
            log.warning("no se pudo actualizar status/fecha · page_id=%s · %s", page_id, exc)

    return {"ok": True, "remitente": remitente}
