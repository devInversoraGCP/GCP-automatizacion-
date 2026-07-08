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
from dotenv import load_dotenv
import notion_client as nc
import email_sender as es

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

# Nombres EXACTOS de las propiedades en Contable Junio (ver esquema confirmado)
P_NOMBRE = "Customers"
P_EMAIL = "Email"
P_MES = "Month"
P_MONTO = "Impuestos"
P_STATUS = "Status"
P_HONORARIOS = "Honorarios Pendientes"
P_INFO_VALOR = "Valor-Info adicional"     # number — valor de la info adicional
P_INFO_MOTIVO = "Motivo-Info adicional"   # select — motivo (Remanente, Saldo a favor, Pago adicional, Otro)
P_ADVISER = "Adviser Accounting"
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
        "page_id=%s cliente=%r asesor=%r mes_present=%s mes_derivado=%s hono_present=%s info_valor_present=%s info_motivo_present=%s",
        page_id, nombre, nombre_asesor, bool(mes), mes_derivado,
        bool(honorarios), bool(info_valor), bool(info_motivo),
    )

    if not email:
        return {"ok": False, "motivo": "fila sin Email"}

    if not mes:
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
        )
        log.info("correo enviado OK · page_id=%s remitente=%s", page_id, remitente)
    except ValueError as exc:
        log.error("error envio · page_id=%s · %s", page_id, exc)
        return {"ok": False, "motivo": str(exc)}
    except Exception as exc:
        log.error("error SMTP · page_id=%s · %s", page_id, exc)
        return {"ok": False, "motivo": f"error SMTP: {exc}"}

    # Write-back del Status
    try:
        nc.update_props(page_id, {P_STATUS: {"status": {"name": STATUS_ENVIADO}}})
        log.info("status actualizado · page_id=%s -> %s", page_id, STATUS_ENVIADO)
    except Exception as exc:
        log.warning("no se pudo actualizar status · page_id=%s · %s", page_id, exc)

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


@app.post("/enviar-f29")
def enviar_f29():
    # Log al inicio: la request llego (sin PII). Antes del check del secreto.
    tiene_secreto = bool(request.headers.get("X-AuditAI-Secret"))
    log.info("request recibida · path=/enviar-f29 · tiene_secreto=%s", tiene_secreto)

    # R4: validar secreto compartido
    secreto_esperado = os.environ.get("WEBHOOK_SECRET", "")
    if secreto_esperado:
        if request.headers.get("X-AuditAI-Secret") != secreto_esperado:
            log.warning("secreto invalido o ausente · respondiendo 401")
            abort(401)

    data = request.get_json(force=True, silent=True) or {}
    # Dump estructural completo (solo keys y tipos, sin valores = sin PII)
    log.info("estructura payload: %s", _estructura(data))

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
        page_id = nc.find_page_by_rut(ident)
        if not page_id:
            log.warning("RUT no encontrado en Contable Junio (RUT no se loguea)")
            abort(404, "no se encontro fila con ese Rut")

    resultado = _procesar_page(page_id)
    return resultado, 200


@app.get("/health")
def health():
    return {"ok": True, "service": "auditai-f29"}, 200


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
