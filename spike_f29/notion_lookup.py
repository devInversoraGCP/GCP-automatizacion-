"""Lectura de credenciales del cliente desde la base central de Notion.

Regla de oro (AGENTS.md #1/#2): las credenciales fluyen SOLO en memoria.
Este módulo NUNCA las imprime, loguea ni escribe a disco. Cualquier print
de diagnóstico debe pasar por `descripcion_segura()`.

Sin dependencias externas: usa urllib de la stdlib.
"""
from __future__ import annotations

import json
import os
import unicodedata
import urllib.request

# Sandbox "General Customers Data - AuditAI" (escritura/lectura autorizada, D19-D22)
DATA_SOURCE_ID = "4ff12147-b3ea-82f4-98dd-072067524cdc"
NOTION_VERSION = "2025-09-03"
TITULO = "w"  # propiedad título de la base (nombre del cliente)


class CredencialesError(RuntimeError):
    pass


def _normalizar(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn").strip().lower()


def _texto_plano(prop: dict) -> str:
    """Extrae el texto plano de una propiedad title/rich_text de la API."""
    frags = prop.get("title") or prop.get("rich_text") or []
    return "".join(f.get("plain_text", "") for f in frags).strip()


def _query(token: str, filtro: dict) -> list[dict]:
    url = f"https://api.notion.com/v1/data_sources/{DATA_SOURCE_ID}/query"
    req = urllib.request.Request(
        url,
        data=json.dumps({"filter": filtro, "page_size": 5}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read()).get("results", [])


def credenciales_cliente(nombre: str) -> dict:
    """Busca al cliente por nombre exacto (título) y devuelve
    {"nombre", "rut", "clave"} — para uso EN MEMORIA solamente."""
    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        raise CredencialesError("NOTION_TOKEN no está definida en el entorno")

    filas = _query(token, {"property": TITULO, "title": {"equals": nombre}})
    if not filas:  # segundo intento: contiene (por si difiere en mayúsculas/espacios)
        filas = _query(token, {"property": TITULO, "title": {"contains": nombre}})
    if not filas:
        raise CredencialesError(f"cliente '{nombre}' no encontrado en la base central")
    if len(filas) > 1:
        raise CredencialesError(
            f"'{nombre}' calza con {len(filas)} fichas — usar el nombre exacto"
        )

    props = filas[0]["properties"]
    valores = {"nombre": "", "rut": "", "clave": ""}
    for nombre_prop, prop in props.items():
        clave_norm = _normalizar(nombre_prop)
        if prop.get("type") == "title":
            valores["nombre"] = _texto_plano(prop)
        elif clave_norm == "rut":
            valores["rut"] = _texto_plano(prop)
        elif clave_norm.startswith("clave sii"):
            valores["clave"] = _texto_plano(prop)

    if not valores["rut"]:
        raise CredencialesError(f"'{valores['nombre']}' no tiene RUT en la base")
    if not valores["clave"]:
        raise CredencialesError(f"'{valores['nombre']}' no tiene CLAVE SII en la base")
    return valores


def descripcion_segura(cred: dict) -> str:
    """Lo ÚNICO imprimible sobre unas credenciales."""
    return (
        f"cliente '{cred['nombre']}': RUT ✔ ({len(cred['rut'])} chars) · "
        f"Clave SII ✔ ({len(cred['clave'])} chars)"
    )


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    # Modo verificación: comprueba que el cliente existe y tiene credenciales,
    # sin revelar nada. Uso: python notion_lookup.py "NOMBRE"
    cred = credenciales_cliente(sys.argv[1])
    print("OK ·", descripcion_segura(cred))
