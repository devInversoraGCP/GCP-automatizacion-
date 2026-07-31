"""Helpers REST para Notion. Reutiliza el patron de spike_f29/notion_lookup.py.
Credenciales solo en memoria (R3): nunca imprime Clave SII, Rut ni Email."""
from __future__ import annotations
import os
import logging
import requests
from http_util import request_con_reintentos

log = logging.getLogger("auditai")

API = "https://api.notion.com/v1"
VER = "2025-09-03"

# Base madre (General Customers Data - AuditAI): fuente de correos por RUT
# cuando la fila del Contable no trae Email. SOLO LECTURA (base sagrada).
DS_CENTRAL = "4ff12147-b3ea-82f4-98dd-072067524cdc"

_MESES_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11,
    "diciembre": 12,
}


def _headers() -> dict:
    tok = os.environ["NOTION_TOKEN"]
    return {
        "Authorization": f"Bearer {tok}",
        "Notion-Version": VER,
        "Content-Type": "application/json",
    }


def get_page(page_id: str) -> dict:
    r = request_con_reintentos("GET", f"{API}/pages/{page_id}", headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def plain(prop: dict) -> str:
    """Texto plano de title/rich_text/email/number/status/people."""
    t = prop.get("type")
    if t in ("title", "rich_text"):
        return "".join(x.get("plain_text", "") for x in prop.get(t, [])).strip()
    if t == "email":
        return (prop.get("email") or "").strip()
    if t == "number":
        n = prop.get("number")
        return "" if n is None else str(n)
    if t in ("status", "select"):
        s = prop.get(t)
        return (s or {}).get("name", "")
    if t == "people":
        names = [x.get("name", "") for x in prop.get("people", [])]
        return "; ".join(names)
    if t == "unique_id":
        u = prop.get("unique_id") or {}
        num = u.get("number")
        if num is None:
            return ""
        pre = u.get("prefix")
        return f"{pre}-{num}" if pre else str(num)
    return ""


def unique_id_number(prop: dict) -> int | None:
    """Número crudo de una propiedad unique_id (la PK estable del sandbox), o None."""
    if prop.get("type") != "unique_id":
        return None
    return (prop.get("unique_id") or {}).get("number")


def relation_ids(prop: dict) -> list[str]:
    """page_ids referenciados por una propiedad relation (vacío si no aplica)."""
    return [r.get("id", "") for r in prop.get("relation", []) if r.get("id")]


def people_names(prop: dict) -> list[str]:
    """Lista de nombres de un campo people (para asesor)."""
    return [x.get("name", "").strip() for x in prop.get("people", [])]


def files(prop: dict) -> list[dict]:
    """Lista de archivos de una propiedad 'files & media' de Notion.
    Devuelve [{'name':..., 'url':...}]. Maneja archivos subidos a Notion
    (URL firmada temporal ~1h) y externos. No loguea nada."""
    out = []
    for f in prop.get("files", []) or []:
        if not isinstance(f, dict):
            continue
        nombre = f.get("name") or "adjunto"
        t = f.get("type")
        if t == "file":
            url = (f.get("file") or {}).get("url", "")
        elif t == "external":
            url = (f.get("external") or {}).get("url", "")
        else:
            url = ""
        if url:
            out.append({"name": nombre, "url": url})
    return out


def update_props(page_id: str, properties: dict) -> None:
    r = request_con_reintentos(
        "PATCH",
        f"{API}/pages/{page_id}",
        headers=_headers(),
        json={"properties": properties},
        timeout=30,
    )
    r.raise_for_status()


def get_data_source_schema(ds_id: str) -> dict:
    """Esquema (dict de columnas) de un data source: GET /v1/data_sources/{id}.
    Solo lectura. Útil para saber si una columna ya existe antes de crearla."""
    r = request_con_reintentos(
        "GET", f"{API}/data_sources/{ds_id}", headers=_headers(), timeout=30
    )
    r.raise_for_status()
    return r.json().get("properties", {})


def update_data_source(ds_id: str, properties: dict) -> dict:
    """Modifica el ESQUEMA de un data source (agrega/edita columnas) vía
    PATCH /v1/data_sources/{id} (API 2025-09-03). `properties` es el patch de
    columnas (relation, rollup, etc.). Devuelve el JSON del data source.

    ⚠️ Regla de oro: sobre el sandbox, libre. Sobre las 4 tablas de los asesores
    la ÚNICA columna que se puede crear es `ID Central` (llave primaria compartida,
    enmienda del 29-jul-2026; ver AGENTS.md y id_central.py). Nada más se toca."""
    r = request_con_reintentos(
        "PATCH", f"{API}/data_sources/{ds_id}", headers=_headers(),
        json={"properties": properties}, timeout=30,
    )
    r.raise_for_status()
    return r.json()


def create_page(ds_id: str, properties: dict) -> dict:
    """Crea una fila en un data source (API 2025-09-03: parent por data_source_id).
    Devuelve el JSON de la página creada (incluye 'id' y sus propiedades, con el
    unique_id ya asignado). No loguea `properties` (PII).

    ⚠️ Regla de oro del proyecto: usar SOLO sobre el sandbox. Las 4 tablas de los
    asesores JAMÁS se escriben (ver AGENTS.md y el plan de reconciliación)."""
    body = {
        "parent": {"type": "data_source_id", "data_source_id": ds_id},
        "properties": properties,
    }
    r = request_con_reintentos(
        "POST", f"{API}/pages", headers=_headers(), json=body, timeout=30
    )
    r.raise_for_status()
    return r.json()


def query_data_source(ds_id: str, body: dict | None = None) -> list[dict]:
    """Query paginado de un data source (API nueva)."""
    out, cursor = [], None
    while True:
        payload = dict(body or {})
        if cursor:
            payload["start_cursor"] = cursor
        r = request_con_reintentos(
            "POST",
            f"{API}/data_sources/{ds_id}/query",
            headers=_headers(),
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        out += data.get("results", [])
        if not data.get("has_more"):
            return out
        cursor = data["next_cursor"]


# Contables conocidos para el fallback por RUT del handler F29.
# MAS RECIENTE PRIMERO. Cuando Carlos duplique un mes nuevo, agregar la entrada
# arriba de la lista (1 linea). No borrar meses anteriores (historico).
# El flujo PRINCIPAL usa source.page_id (Notion lo envia solo); este fallback solo
# se activa en edge cases donde el webhook llega sin page_id. Ver doc 28 §4.
DS_CONTABLES: list[tuple[str, str]] = [
    # ("Contable Julio",  "<nuevo_data_source_id>"),   # descomentar cuando exista
    ("Contable Junio", "09b12147-b3ea-8337-a218-87538eab23fc"),
]

# Alias legacy: compatibilidad con imports viejos que referencien la constante
# anterior (DS_CONTABLE_JUNIO). Apunta al primer Contable de la lista.
DS_CONTABLE_JUNIO = DS_CONTABLES[0][1]


def find_page_by_rut(rut: str) -> str | None:
    """Busca el page_id por RUT en los Contables conocidos, en orden (mas
    reciente primero). Devuelve None si no hay match en ninguno. No loguea el
    RUT (PII). Asume RUT unico por cliente (un cliente no aparece en dos
    Contables a la vez, salvo que se aprete el boton en un mes historico).
    Ver doc 28 §4."""
    for _nombre, ds_id in DS_CONTABLES:
        body = {
            "filter": {
                "property": "Rut",
                "rich_text": {"equals": rut},
            },
            "page_size": 5,
        }
        results = query_data_source(ds_id, body)
        if results:
            return results[0]["id"]
    return None


def find_page_by_rut_generico(rut: str, ds_id: str, prop_rut: str = "Rut") -> str | None:
    """Busca el page_id por RUT en un data source genérico.
    ds_id: data source ID de la base.
    prop_rut: nombre de la propiedad que contiene el RUT (title o rich_text)."""
    body = {
        "filter": {
            "property": prop_rut,
            "rich_text": {"equals": rut},
        },
        "page_size": 5,
    }
    results = query_data_source(ds_id, body)
    if not results:
        return None
    return results[0]["id"]


def find_page_by_title_generico(titulo: str, ds_id: str, prop_title: str) -> str | None:
    """Busca el page_id por el valor de una propiedad TITLE en un data source.
    A diferencia de find_page_by_rut_generico (filtro rich_text), Notion exige el
    filtro 'title' para las columnas title (un rich_text sobre un title da 400).
    Usado por CRM Comercial, cuyo identificador es 'Sw' (title). Ver doc 32."""
    body = {
        "filter": {
            "property": prop_title,
            "title": {"equals": titulo},
        },
        "page_size": 5,
    }
    results = query_data_source(ds_id, body)
    if not results:
        return None
    return results[0]["id"]


def buscar_email_en_central(rut: str) -> str | None:
    """Busca el Email de un cliente por RUT en la base madre (SOLO LECTURA).
    Fallback cuando la fila del Contable llega con la columna Email vacia:
    muchos clientes tienen el correo cargado en la base central aunque falte
    en el Contable del mes. Devuelve el primer valor no vacio de las columnas
    email/Email/e-mail, o None. Nunca lanza: si el lookup falla, el caller
    sigue sin email (R5). NO valida el formato — de eso se encarga
    email_sender._validar_destinatario antes de enviar (asi un valor basura de
    la central, ej. 'SOLO WATHSAPP', se corta igual con un motivo claro)."""
    if not rut:
        return None
    try:
        body = {"filter": {"property": "RUT", "rich_text": {"equals": rut}}, "page_size": 3}
        results = query_data_source(DS_CENTRAL, body)
        if not results:
            return None
        props = results[0].get("properties", {})
        for col in ("email", "Email", "e-mail"):
            val = plain(props.get(col, {}))
            if val:
                return val
        return None
    except Exception as exc:
        log.warning("lookup email en base central fallo (se sigue sin email): %s", exc)
        return None


def buscar_data_sources(query: str) -> list[dict]:
    """Busca data sources por título (POST /v1/search, filtro data_source).
    Devuelve los results crudos (traen id, title/name y last_edited_time). Paginado.
    Usado para resolver dinámicamente la base del mes vigente (Contable/RRHH)."""
    out: list[dict] = []
    cursor = None
    while True:
        body: dict = {"query": query, "filter": {"property": "object", "value": "data_source"}}
        if cursor:
            body["start_cursor"] = cursor
        r = request_con_reintentos("POST", f"{API}/search", headers=_headers(), json=body, timeout=30)
        r.raise_for_status()
        data = r.json()
        out += data.get("results", [])
        if not data.get("has_more"):
            return out
        cursor = data["next_cursor"]


def get_database_title(database_id: str) -> str:
    """Obtiene el titulo plano de una base Notion (de su data source / database).
    'Contable Junio' -> 'Contable Junio'. Devuelve '' si falla."""
    r = request_con_reintentos("GET", f"{API}/databases/{database_id}", headers=_headers(), timeout=30)
    r.raise_for_status()
    data = r.json()
    titulo = data.get("title", [])
    if isinstance(titulo, list):
        return "".join(x.get("plain_text", "") for x in titulo).strip()
    return ""


def get_data_source_id(database_id: str) -> str:
    """Resuelve el data source id de una base a partir de su database_id
    (API 2025-09-03: son IDs DISTINTOS, ver doc 28 §16 — el botón de Notion
    manda el database_id, pero query_data_source necesita el data source id).
    Si la base tiene varios data sources usa el primero. Si el GET falla o no
    trae data_sources (p. ej. el id ya ERA un data source id), devuelve el id
    tal cual, como fallback."""
    try:
        r = request_con_reintentos(
            "GET", f"{API}/databases/{database_id}", headers=_headers(), timeout=30
        )
        r.raise_for_status()
        ds = r.json().get("data_sources") or []
        if ds and isinstance(ds[0], dict) and ds[0].get("id"):
            return ds[0]["id"]
    except Exception:
        pass
    return database_id


def derivar_month_desde_base(page: dict) -> str:
    """Fallback C: si una fila llega con Month vacio, deriva el periodo del F29
    desde el titulo de la base parent. 'Contable Junio' + ultima_edicion en
    jul-2026 -> 'Junio 2026'. Logica de anio: mes del titulo + anio de
    last_edited_time, con correccion si mes=diciembre y edicion en enero
    (el F29 de diciembre se hace en enero del anio siguiente).

    Limitacion conocida: si se edita mucho tiempo despues del periodo, el anio
    podria desfasarse. Es un fallback de emergencia; el bulk-set (Opcion A)
    fija Month correctamente en la mayoria de los casos."""
    parent = page.get("parent") or {}
    db_id = parent.get("database_id")
    if not db_id:
        return ""
    titulo = ""
    try:
        titulo = get_database_title(db_id)
    except Exception:
        return ""
    # 'Contable Junio' -> 'Junio'
    partes = titulo.split()
    if len(partes) < 2 or partes[0].lower() not in ("contable", "rrhh"):
        return ""
    nombre_mes = partes[1]
    mes_lc = nombre_mes.lower()
    if mes_lc not in _MESES_ES:
        return ""
    # Anio desde last_edited_time (formato '2026-07-07T19:39:00.000Z')
    anio = 0
    le = page.get("last_edited_time", "")
    if le and len(le) >= 4 and le[:4].isdigit():
        anio = int(le[:4])
    if not anio:
        return ""
    # Correccion diciembre/enero: F29 de diciembre se hace en enero del anio siguiente
    if mes_lc == "diciembre":
        mes_ed = (le[5:7] if len(le) >= 7 else "")
        if mes_ed == "01":
            anio -= 1
    # Capitalizar mes
    mes_cap = nombre_mes[0].upper() + nombre_mes[1:].lower()
    return f"{mes_cap} {anio}"
