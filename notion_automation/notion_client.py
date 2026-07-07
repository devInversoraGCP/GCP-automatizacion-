"""Helpers REST para Notion. Reutiliza el patron de spike_f29/notion_lookup.py.
Credenciales solo en memoria (R3): nunca imprime Clave SII, Rut ni Email."""
from __future__ import annotations
import os
import requests

API = "https://api.notion.com/v1"
VER = "2025-09-03"


def _headers() -> dict:
    tok = os.environ["NOTION_TOKEN"]
    return {
        "Authorization": f"Bearer {tok}",
        "Notion-Version": VER,
        "Content-Type": "application/json",
    }


def get_page(page_id: str) -> dict:
    r = requests.get(f"{API}/pages/{page_id}", headers=_headers(), timeout=30)
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
    if t == "status":
        s = prop.get("status")
        return (s or {}).get("name", "")
    if t == "people":
        names = [x.get("name", "") for x in prop.get("people", [])]
        return "; ".join(names)
    return ""


def people_names(prop: dict) -> list[str]:
    """Lista de nombres de un campo people (para asesor)."""
    return [x.get("name", "").strip() for x in prop.get("people", [])]


def update_props(page_id: str, properties: dict) -> None:
    r = requests.patch(
        f"{API}/pages/{page_id}",
        headers=_headers(),
        json={"properties": properties},
        timeout=30,
    )
    r.raise_for_status()


def query_data_source(ds_id: str, body: dict | None = None) -> list[dict]:
    """Query paginado de un data source (API nueva)."""
    out, cursor = [], None
    while True:
        payload = dict(body or {})
        if cursor:
            payload["start_cursor"] = cursor
        r = requests.post(
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


# Data source de Contable Junio (base operativa, ver AGENTS.md)
DS_CONTABLE_JUNIO = "09b12147-b3ea-8337-a218-87538eab23fc"


def find_page_by_rut(rut: str) -> str | None:
    """Busca el page_id por RUT en Contable Junio. Devuelve None si no hay match.
    No loguea el RUT (PII). Asume RUT unico por cliente."""
    body = {
        "filter": {
            "property": "Rut",
            "rich_text": {"equals": rut},
        },
        "page_size": 5,
    }
    results = query_data_source(DS_CONTABLE_JUNIO, body)
    if not results:
        return None
    return results[0]["id"]
