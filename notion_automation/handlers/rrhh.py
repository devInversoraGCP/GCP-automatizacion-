"""Handler del botón "Enviar Correo RRHH" para la página RRHH del mes vigente.
Sigue el patrón del handler F29 (en app.py) pero con su propia lógica de
composición y fecha límite (13 del mes siguiente, no 20).

⚠️ Ni el data source ni el mes pueden estar fijos en el código: se resuelven en
runtime desde el título de la planilla vigente. Hasta julio-2026 RRHH estrenaba
una base NUEVA cada mes; desde el cambio de mes del 18-ago rota como Contable
(duplicar respaldo + renombrar la original en sitio, doc 28 §19), así que el id
se mantiene. Las dos formas funcionan: `ds_vigente()` resuelve por título."""
from __future__ import annotations
import os
import sys
import logging
from datetime import datetime, timezone
import notion_client as nc
import email_sender as es
import alertas

log = logging.getLogger("auditai")

# Bases RRHH conocidas, MÁS RECIENTE PRIMERO (fallback estático, mismo patrón que
# DS_CONTABLES en notion_client.py — doc 28). Normalmente NO hay que editar esto:
# ds_vigente() resuelve la base del mes por su título.
DS_RRHH: list[tuple[str, str]] = [
    # Misma base renombrada mes a mes desde ago-2026: el id NO cambia, el nombre sí.
    ("RRHH AGOSTO 2026", "89a12147-b3ea-830e-adee-07cbca823fb6"),
    ("RRHH JUNIO 2026", "9c512147-b3ea-8256-a570-871254c13b3d"),   # en la papelera
]
DS_ID = DS_RRHH[0][1]   # alias legacy: el más reciente conocido


def ds_vigente() -> str:
    """Data source de la base `RRHH <Mes>` del período MÁS NUEVO.

    Solo se usa en el fallback de identificación por RUT (cuando el webhook del
    botón llega sin `page_id`). Esto era una constante fija apuntando a JUNIO:
    al aparecer `RRHH JULIO 2026` ese fallback seguía encontrando la fila del mes
    ANTERIOR, y el correo salía con el **monto y el mes equivocados**, además de
    marcar como enviada la fila del mes viejo (detectado el 31-jul-2026).

    Se resuelve por título en runtime; si el search falla, cae al más reciente
    de `DS_RRHH`."""
    try:
        import reconciliar
        return reconciliar.resolver_ds_actual("RRHH", DS_ID)
    except Exception as exc:
        log.warning("no se pudo resolver la base RRHH vigente, uso %s: %s", DS_RRHH[0][0], exc)
        return DS_ID

CLIENTE = "CLIENTE"
ASISTENTE = "ASISTENTE"
MONTO = "MONTO IMPOSICIONES|"
RUT = "RUT"
EMAIL_CLIENTE = "Email"
ADJUNTOS = "Adjuntos"                 # files & media
MSG_ADJUNTOS = "Comentario-Adjuntos"  # rich_text

STATUS_COL = "Estado Correo"
# Opciones reales del status en RRHH: "Sin empezar" / "En curso" / "Listo".
# "Enviado" no existe y la API no puede crear opciones de status.
STATUS_ENVIADO = "Listo"
# 'envío' en minuscula: es el nombre EXACTO de la columna en Notion (verificado
# por API 09-jul). "Fecha Envío" (con E mayuscula) NO existe y falla en silencio.
FECHA_COL = "Fecha envío"

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


def procesar(page_id: str) -> dict:
    page = nc.get_page(page_id)
    props = page["properties"]

    nombre = nc.plain(props.get(CLIENTE, {}))
    monto_str = nc.plain(props.get(MONTO, {}))
    rut = nc.plain(props.get(RUT, {}))
    email = nc.plain(props.get(EMAIL_CLIENTE, {}))
    asistente_raw = nc.plain(props.get(ASISTENTE, {}))
    nombre_asesor = ALIAS_ASESOR.get(es._norm(asistente_raw), asistente_raw)
    adjuntos = nc.files(props.get(ADJUNTOS, {}))
    msg_adjuntos = nc.plain(props.get(MSG_ADJUNTOS, {}))

    log.info("page_id=%s cliente=%r asistente=%r monto_present=%s email_propio=%s rut_present=%s adjuntos_n=%d msg_adj_present=%s",
             page_id, nombre, asistente_raw, bool(monto_str), bool(email), bool(rut), len(adjuntos), bool(msg_adjuntos))

    if not email and rut:
        encontrado = nc.buscar_email_en_central(rut)
        if encontrado:
            email = encontrado
            log.info("email recuperado desde base central · page_id=%s", page_id)

    if not email:
        motivo = "fila sin Email (ni columna Email Cliente ni lookup por RUT)"
        alertas.avisar_fallo_asesor(nombre_asesor, nombre, "", motivo, flujo="rrhh", page_id=page_id)
        return {"ok": False, "motivo": motivo}

    if not nombre:
        motivo = "fila sin CLIENTE (necesario para el asunto y cuerpo)"
        alertas.avisar_fallo_asesor(nombre_asesor, nombre, "", motivo, flujo="rrhh", page_id=page_id)
        return {"ok": False, "motivo": motivo}

    # El monto ES el contenido del correo. Vacío ≠ cero: antes salía "0" y el
    # cliente recibía un aviso diciendo que no debe nada (visto 31-jul: 7 de las
    # 9 filas de un asesor estaban sin cargar). Un 0 explícito en la columna sí
    # se envía — es un dato, no un olvido.
    if not monto_str:
        motivo = ("fila sin MONTO IMPOSICIONES| — es el dato principal del correo. "
                  "Cárgalo en la planilla y vuelve a apretar el botón.")
        alertas.avisar_fallo_asesor(nombre_asesor, nombre, "", motivo, flujo="rrhh", page_id=page_id)
        return {"ok": False, "motivo": motivo}

    # El mes sale del TÍTULO de la base ("RRHH JULIO 2026" -> "Julio 2026"): RRHH
    # no tiene columna de mes en la fila. Antes, si el título no se podía leer,
    # caía a un "Junio 2026" fijo en el código — o sea, mandaba un mes incorrecto
    # en silencio para siempre. Ahora falla en voz alta y avisa al asesor, igual
    # que hace el flujo F29 (app.py §mes).
    mes = nc.derivar_month_desde_base(page)
    db_id = (page.get("parent") or {}).get("database_id", "")
    log.info("diagnostico mes RRHH · page_id=%s db_id=%s mes=%r", page_id, db_id, mes)
    if not mes:
        motivo = ("No se pudo determinar el mes desde el título de la base "
                  "(se espera el patrón 'RRHH <Mes> <Año>'), necesario para el "
                  "asunto y el plazo del correo.")
        alertas.avisar_fallo_asesor(nombre_asesor, nombre, "", motivo, flujo="rrhh", page_id=page_id)
        return {"ok": False, "motivo": motivo}

    asunto = f"Imposiciones {mes}- {nombre}"

    try:
        remitente = es.enviar(
            destinatario=email,
            nombre=nombre,
            mes=mes,
            monto=monto_str,
            nombre_asesor=nombre_asesor,
            honorarios="",
            info_valor="",
            info_motivo="",
            msg_adjuntos=msg_adjuntos,
            adjuntos=adjuntos,
            template=TEMPLATE,
            asunto=asunto,
            custom_args={"page_id": page_id, "flujo": "rrhh"},
        )
        log.info("correo RRHH enviado OK · page_id=%s remitente=%s", page_id, remitente)
    except ValueError as exc:
        log.error("error envio RRHH · page_id=%s · %s", page_id, exc)
        alertas.avisar_fallo_asesor(nombre_asesor, nombre, mes, str(exc), flujo="rrhh", page_id=page_id)
        return {"ok": False, "motivo": str(exc)}
    except Exception as exc:
        log.error("error SMTP RRHH · page_id=%s · %s", page_id, exc)
        motivo = f"error SMTP: {exc}"
        alertas.avisar_fallo_asesor(nombre_asesor, nombre, mes, motivo, flujo="rrhh", page_id=page_id)
        return {"ok": False, "motivo": motivo}

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
