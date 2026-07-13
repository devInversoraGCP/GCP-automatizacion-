"""Backend AuditAI. Recibe el webhook del botón "Enviar F29", lee la fila
de Contable Junio en memoria, envía el correo desde la cuenta del asesor
asignado, y escribe de vuelta el Status. R3/R4.

Uso:
  python app.py                # arranca el servidor Flask en puerto 8000

Sin Notion (prueba local directa):
  python app.py --test <page_id>   # lee la fila y envía el correo sin webhook
"""
from __future__ import annotations
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, request, abort
from werkzeug.exceptions import HTTPException
from dotenv import load_dotenv
import datetime
import notion_client as nc
import email_sender as es
import alertas
import handlers.rrhh as rrhh_handler
import handlers.tickets as tickets_handler

load_dotenv()

# Configurar logging SIN PII (no loguear email, monto, RUT).
# FileHandler escribe directo a archivo (sin buffering de stdout/stderr).
_fh = RotatingFileHandler("auditai.log", maxBytes=200000, backupCount=3)
_fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[_fh, logging.StreamHandler()],
)
log = logging.getLogger("auditai")

app = Flask(__name__)

# Fase 0.2 (doc 27, H9): el WEBHOOK_SECRET es OBLIGATORIO. Sin él, cualquiera
# que conozca la URL podría disparar correos a los clientes. Si falta, los
# webhooks responden 503 (y /health lo delata) en vez de aceptar requests.
if not os.environ.get("WEBHOOK_SECRET"):
    logging.getLogger("auditai").critical(
        "WEBHOOK_SECRET NO esta configurado: los webhooks responderan 503 "
        "hasta que se defina la env var (Render -> Environment)."
    )


def _validar_secreto():
    """Valida X-AuditAI-Secret. 503 si el servidor no tiene secreto configurado
    (config incompleta, fail-safe); 401 si el header no coincide."""
    secreto_esperado = os.environ.get("WEBHOOK_SECRET", "")
    if not secreto_esperado:
        log.error("WEBHOOK_SECRET ausente en el servidor · path=%s · 503", request.path)
        abort(503, "backend sin WEBHOOK_SECRET configurado; avisar al administrador")
    if request.headers.get("X-AuditAI-Secret") != secreto_esperado:
        log.warning("secreto invalido o ausente · path=%s · 401", request.path)
        abort(401)

# Nombres EXACTOS de las propiedades en Contable Junio (ver esquema confirmado)
P_NOMBRE = "Customers"
P_EMAIL = "Email"
P_MES = "Month"
P_MONTO = "Impuestos"
P_STATUS = "Status"
P_HONORARIOS = "Honorarios Pendientes"
P_INFO_VALOR = "Valor-Info adicional"     # number — valor de la info adicional
P_INFO_MOTIVO = "Motivo-Info adicional"   # rich_text — motivo (Remanente, Saldo a favor, Pago adicional, Otro, o libre)
P_ADVISER = "Adviser Accounting"
P_ADJUNTOS = "Adjuntos"   # files & media — PDFs que se adjuntan al correo
P_MSG_ADJUNTOS = "Mensaje Adjuntos"   # rich_text — nota del asesor sobre los adjuntos
P_FECHA_ENVIO = "Fecha Envío"   # date — fecha y hora en la que se envió el correo
STATUS_ENVIADO = "1) Enviado y Pendiente"


def _procesar_page(page_id: str) -> dict:
    """Lee la fila, envía el correo, actualiza Status. Devuelve {ok, ...}.
    No loguea PII (email, monto, RUT)."""
    page = nc.get_page(page_id)
    props = page["properties"]

    email = nc.plain(props.get(P_EMAIL, {}))
    nombre = nc.plain(props.get(P_NOMBRE, {}))
    mes = nc.plain(props.get(P_MES, {}))
    monto = nc.plain(props.get(P_MONTO, {}))
    honorarios = nc.plain(props.get(P_HONORARIOS, {}))
    info_valor = nc.plain(props.get(P_INFO_VALOR, {}))
    info_motivo = nc.plain(props.get(P_INFO_MOTIVO, {}))
    asesor_nombres = nc.people_names(props.get(P_ADVISER, {}))
    nombre_asesor = asesor_nombres[0] if asesor_nombres else ""
    adjuntos = nc.files(props.get(P_ADJUNTOS, {}))
    msg_adjuntos = nc.plain(props.get(P_MSG_ADJUNTOS, {}))

    # Fallback C: si Month esta vacio, derivarlo del titulo de la base parent
    # ("Contable Junio" -> "Junio 2026"). El asesor no debe tipear Month (Opcion A
    # bulk-set + este fallback de emergencia). Ver doc 23 §5.2.c.
    mes_derivado = False
    if not mes:
        mes = nc.derivar_month_desde_base(page)
        mes_derivado = bool(mes)
        if mes_derivado:
            log.info("Month vacio -> derivado de la base parent (no se loguea el valor)")

    # Log sin PII
    log.info(
        "page_id=%s cliente=%r asesor=%r mes_present=%s mes_derivado=%s hono_present=%s info_valor_present=%s info_motivo_present=%s msg_adj_present=%s adjuntos_n=%d",
        page_id, nombre, nombre_asesor, bool(mes), mes_derivado,
        bool(honorarios), bool(info_valor), bool(info_motivo), bool(msg_adjuntos), len(adjuntos),
    )

    def _alertar_error(motivo: str):
        alertas.avisar_fallo_asesor(nombre_asesor, nombre, mes, motivo)

    if not email:
        _alertar_error("Fila sin correo electrónico (Email).")
        return {"ok": False, "motivo": "fila sin Email"}

    if not mes:
        _alertar_error("Fila sin mes (Month), necesario para calcular la fecha límite.")
        return {"ok": False, "motivo": "fila sin Month (necesario para fecha límite)"}

    try:
        remitente = es.enviar(
            destinatario=email,
            nombre=nombre,
            mes=mes,
            monto=monto or "0",
            nombre_asesor=nombre_asesor,
            honorarios=honorarios,
            info_valor=info_valor,
            info_motivo=info_motivo,
            msg_adjuntos=msg_adjuntos,
            adjuntos=adjuntos,
        )
        log.info("correo enviado OK · page_id=%s remitente=%s", page_id, remitente)
    except ValueError as exc:
        log.error("error envio · page_id=%s · %s", page_id, exc)
        _alertar_error(str(exc))
        return {"ok": False, "motivo": str(exc)}
    except Exception as exc:
        log.error("error SMTP · page_id=%s · %s", page_id, exc)
        _alertar_error(f"Error de envío: {exc}")
        return {"ok": False, "motivo": f"error SMTP: {exc}"}

    # Write-back del Status y Fecha Envío. Tolerante: escribe solo las columnas
    # que existen en la fila. Un PATCH con una propiedad inexistente falla
    # completo, y antes eso tumbaba tambien el Status en silencio (la columna
    # date se llamaba "Fecha", no "Fecha Envío"). Ver doc 24 §5.1.
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    updates = {}
    if P_STATUS in props:
        updates[P_STATUS] = {"status": {"name": STATUS_ENVIADO}}
    else:
        log.warning("columna %r no existe en Contable; no se escribe status", P_STATUS)
    if P_FECHA_ENVIO in props:
        updates[P_FECHA_ENVIO] = {"date": {"start": now_iso}}
    else:
        log.warning("columna %r no existe en Contable; no se escribe fecha", P_FECHA_ENVIO)
    if updates:
        try:
            nc.update_props(page_id, updates)
            log.info("write-back OK (%s) · page_id=%s -> %s", ", ".join(updates), page_id, STATUS_ENVIADO)
        except Exception as exc:
            log.warning("no se pudo actualizar status/fecha · page_id=%s · %s", page_id, exc)

    return {"ok": True, "remitente": remitente}


def _estructura(d, profundidad=0):
    """Devuelve un dict anidado con solo keys y tipos (sin valores = sin PII)."""
    if profundidad > 4 or not isinstance(d, dict):
        return type(d).__name__
    return {k: _estructura(v, profundidad + 1) for k, v in d.items()}


def _extraer_plano_notion(v: dict) -> str:
    """Extrae un valor plano de un objeto propiedad Notion, con o sin campo
    `type` explicito. Prueba rich_text, title, email, url, number, phone_number,
    select, status, people. Devuelve '' si no encuentra nada."""
    if not isinstance(v, dict):
        return ""
    t = v.get("type")
    # Si tiene type, usar la via estandar
    if t:
        try:
            p = nc.plain(v)
            if p:
                return p
        except Exception:
            pass
    # Fallbacks sin type: buscar campos conocidos directamente
    for campo in ("rich_text", "title"):
        arr = v.get(campo)
        if isinstance(arr, list):
            txt = "".join(x.get("plain_text", "") for x in arr if isinstance(x, dict)).strip()
            if txt:
                return txt
    for campo in ("email", "url", "phone_number", "number"):
        val = v.get(campo)
        if isinstance(val, str) and val.strip():
            return val.strip()
        if isinstance(val, (int, float)):
            return str(val)
    sel = v.get("select") or v.get("status")
    if isinstance(sel, dict) and sel.get("name"):
        return sel["name"]
    return ""


def _buscar_clave(d, claves, profundidad=0, _ruta=""):
    """Busca recursivamente la primera clave cuyo nombre este en `claves`
    (case-insensitive). Devuelve (valor, ruta) o (None, ""). Profundidad
    limitada. Maneja 3 formatos: string plano, objeto propiedad Notion
    (con o sin `type`), y dict anidado. No loguea valores (PII)."""
    if profundidad > 6 or not isinstance(d, dict):
        return None, ""
    claves_lc = {k.lower() for k in claves}
    for k, v in d.items():
        ruta_n = f"{_ruta}.{k}" if _ruta else k
        if k.lower() in claves_lc:
            if isinstance(v, (str, int, float)):
                return str(v), ruta_n
            if isinstance(v, dict):
                plano = _extraer_plano_notion(v)
                if plano:
                    return plano, ruta_n
        if isinstance(v, dict):
            val, r = _buscar_clave(v, claves, profundidad + 1, ruta_n)
            if val is not None:
                return val, r
    return None, ""


def _es_uuid(s: str) -> bool:
    return (
        len(s) == 36
        and s.count("-") == 4
        and all(c in "0123456789abcdef-" for c in s.lower())
    )


def _procesar_webhook_generico(handler, nombre_handler: str):
    """Lógica común para todos los webhooks de botones Notion.
    - Valida X-AuditAI-Secret
    - Extrae page_id o RUT del payload
    - Llama al handler específico con el page_id
    handler: función que recibe (page_id) -> dict
    """
    tiene_secreto = bool(request.headers.get("X-AuditAI-Secret"))
    log.info("request recibida · path=%s · tiene_secreto=%s", request.path, tiene_secreto)

    _validar_secreto()   # 503 si el server no tiene secreto; 401 si no coincide (H9)

    data = request.get_json(force=True, silent=True) or {}
    log.info("estructura payload %s: %s", nombre_handler, _estructura(data))

    # Fase 1.1 (doc 27, H7): TODO lo de aca abajo va envuelto en captura de
    # excepciones no previstas (bug, 500 de Notion, timeout raro). abort()
    # lanza HTTPException (400/401/404/503) y esos SI deben propagar tal cual
    # (son respuestas intencionales, no errores). page_id arranca vacio: si
    # la excepcion ocurre antes de identificar la fila, no hay nada que
    # loguear como identificador (evita filtrar un RUT si `ident` era PII).
    page_id = ""
    try:
        ident, ruta = _buscar_clave(data, ["page_id"])
        if not ident:
            # Payload tipo page-object (automations nuevas): data.id / entity.id
            for k in ("data", "entity"):
                v = data.get(k)
                pid = v.get("id") if isinstance(v, dict) else None
                if isinstance(pid, str) and _es_uuid(pid):
                    ident, ruta = pid, f"{k}.id"
                    break
        if not ident:
            ident, ruta = _buscar_clave(data, ["Rut", "rut", "RUT"])
        # Fallback RRHH: muchas filas tienen el RUT (title) vacio -> identificar
        # por CLIENTE (contingencia doc 25 §9). Solo si no hubo page_id ni RUT.
        prop_busqueda = "RUT"
        if not ident and nombre_handler == "RRHH":
            ident, ruta = _buscar_clave(data, ["CLIENTE", "Cliente", "cliente"])
            prop_busqueda = "CLIENTE"
        if not ident and nombre_handler == "TICKETS":
            ident, ruta = _buscar_clave(data, ["Tarea", "tarea", "Nombre"])
            prop_busqueda = "Tarea"
        log.info("identificador en ruta=%r (valor no se loguea)", ruta)

        if not ident:
            abort(400, f"no se encontro page_id, Rut ni CLIENTE en el payload ({nombre_handler})")

        if _es_uuid(ident):
            page_id = ident
            log.info("usando page_id directo · %s", nombre_handler)
        else:
            if nombre_handler == "RRHH":
                from handlers.rrhh import DS_ID as DS
                page_id = nc.find_page_by_rut_generico(ident, DS, prop_busqueda)
            elif nombre_handler == "TICKETS":
                from handlers.tickets import DS_ID as DS
                page_id = nc.find_page_by_rut_generico(ident, DS, prop_busqueda)
            else:
                page_id = nc.find_page_by_rut(ident)
            if not page_id:
                log.warning("%s no encontrado · %s", prop_busqueda, nombre_handler)
                abort(404, f"no se encontro fila con ese {prop_busqueda} en {nombre_handler}")

        resultado = handler(page_id)
    except HTTPException:
        raise
    except Exception as exc:
        alertas.avisar_excepcion_admin(nombre_handler, page_id or "", exc)
        return {"ok": False, "motivo": "error interno del servidor; administrador notificado"}, 500

    return resultado, 200


@app.post("/webhook/rrhh")
def webhook_rrhh():
    """Webhook del botón 'Enviar Correo RRHH' en RRHH JUNIO 2026."""
    return _procesar_webhook_generico(rrhh_handler.procesar, "RRHH")


_TICKETS_TIPOS = {"avance", "completado", "cobranza"}


@app.post("/webhook/tickets/<tipo>")
def webhook_tickets(tipo):
    """Webhook de los botones de Tickets - Servicios. <tipo> elige la plantilla."""
    if tipo not in _TICKETS_TIPOS:
        abort(404, f"tipo de correo tickets desconocido: {tipo}")
    return _procesar_webhook_generico(
        lambda page_id: tickets_handler.procesar(page_id, tipo), "TICKETS"
    )


@app.post("/enviar-f29")
def enviar_f29():
    # Log al inicio: la request llego (sin PII). Antes del check del secreto.
    tiene_secreto = bool(request.headers.get("X-AuditAI-Secret"))
    log.info("request recibida · path=/enviar-f29 · tiene_secreto=%s", tiene_secreto)

    # R4 + H9: secreto compartido OBLIGATORIO (503 si el server no lo tiene)
    _validar_secreto()

    data = request.get_json(force=True, silent=True) or {}
    # Dump estructural completo (solo keys y tipos, sin valores = sin PII)
    log.info("estructura payload: %s", _estructura(data))

    # Fase 1.1 (doc 27, H7): captura de excepciones no previstas, igual que en
    # _procesar_webhook_generico. abort() (HTTPException) propaga tal cual.
    page_id = ""
    try:
        # Identificador: priorizar page_id (de source), luego Rut en cualquier nivel
        ident, ruta = _buscar_clave(data, ["page_id"])
        if not ident:
            ident, ruta = _buscar_clave(data, ["Rut", "rut", "RUT"])
        log.info("identificador en ruta=%r (valor no se loguea)", ruta)

        if not ident:
            abort(400, "no se encontro page_id ni Rut en el payload")

        if _es_uuid(ident):
            page_id = ident
            log.info("usando page_id directo (sin query Notion)")
        else:
            page_id = nc.find_page_by_rut(ident) or ""
            if not page_id:
                log.warning("RUT no encontrado en Contable Junio (RUT no se loguea)")
                abort(404, "no se encontro fila con ese Rut")

        resultado = _procesar_page(page_id)
    except HTTPException:
        raise
    except Exception as exc:
        alertas.avisar_excepcion_admin("F29", page_id, exc)
        return {"ok": False, "motivo": "error interno del servidor; administrador notificado"}, 500

    return resultado, 200


@app.get("/health")
def health():
    # Solo booleanos/conteos, nunca valores (sin PII). Permite diagnosticar
    # desde afuera un deploy con env vars faltantes (H9) o el canal de alertas
    # del admin sin configurar (Fase 1.2). admin_alerts_configurados = cuantos
    # correos quedaron en ADMIN_ALERT_EMAIL (separados por coma).
    return {
        "ok": True,
        "service": "auditai-f29",
        "webhook_secret_configurado": bool(os.environ.get("WEBHOOK_SECRET")),
        "admin_alerts_configurados": len(es.admin_emails()),
    }, 200


def _run_test(page_id: str):
    """Modo prueba local: lee la fila y envía el correo sin webhook."""
    log.info("MODO TEST · page_id=%s", page_id)
    resultado = _procesar_page(page_id)
    print(f"\nResultado: {resultado}")


def _run_test_rut(rut: str):
    """Modo prueba por RUT: busca la fila en Contable Junio y envía el correo."""
    log.info("MODO TEST-RUT (RUT no se loguea)")
    page_id = nc.find_page_by_rut(rut)
    if not page_id:
        print("No se encontro fila con ese Rut en Contable Junio")
        sys.exit(1)
    log.info("fila encontrada · page_id=%s", page_id)
    resultado = _procesar_page(page_id)
    print(f"\nResultado: {resultado}")


if __name__ == "__main__":
    if "--test-rut" in sys.argv:
        idx = sys.argv.index("--test-rut")
        if idx + 1 < len(sys.argv):
            _run_test_rut(sys.argv[idx + 1])
        else:
            print("Uso: python app.py --test-rut <rut>")
        sys.exit(0)

    if "--test" in sys.argv:
        idx = sys.argv.index("--test")
        if idx + 1 < len(sys.argv):
            _run_test(sys.argv[idx + 1])
        else:
            print("Uso: python app.py --test <page_id>")
        sys.exit(0)

    port = int(os.environ.get("PORT", "8000"))
    # host="0.0.0.0" es obligatorio en la nube (Render/Railway/Cloud Run) para que el tráfico
    # del balanceador llegue al contenedor. En local no afecta (sigue accesible en localhost:8000).
    log.info("arrancando backend en 0.0.0.0:%d", port)
    app.run(host="0.0.0.0", port=port, debug=False)
