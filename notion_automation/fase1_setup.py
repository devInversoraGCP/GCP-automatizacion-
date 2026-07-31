"""Fase 1 — Crea en el SANDBOX las relaciones una-vía y los rollups de la ficha.

Deja el sandbox `General Customers Data - AuditAI` listo como hub maestro: una
relación una-vía (single_property) hacia cada tabla operativa + rollups que traen
los datos operativos a la ficha del cliente. Es IDEMPOTENTE: salta lo que ya existe.

🔒 Regla de oro: SOLO escribe en el sandbox. Las 4 tablas de los asesores se leen
(para resolver el nombre exacto de sus columnas) pero JAMÁS se escriben. Las
relaciones son single_property → no agregan columna a producción.

Uso:  python fase1_setup.py          # crea lo que falte
      python fase1_setup.py --dry    # solo muestra qué crearía
"""
from __future__ import annotations
import os
import sys
import argparse
from dotenv import load_dotenv
import notion_client as nc

SANDBOX = "4ff12147-b3ea-82f4-98dd-072067524cdc"

# Relación en el sandbox -> data source operativo (mes vigente para Contable/RRHH).
RELACIONES = {
    "Contable Origen": "09b12147-b3ea-8337-a218-87538eab23fc",
    # RRHH estrena base cada mes: este id es solo el arranque. Una vez creada, el
    # cron la mantiene apuntando al mes vigente (reconciliar.sincronizar_relacion).
    "RRHH Origen":     "89a12147-b3ea-830e-adee-07cbca823fb6",  # ya existe (se salta)
    "CRM Origen":      "2961d0d2-de59-4fd5-b340-8930f6275101",
    "Tickets Origen":  "9d312147-b3ea-83bf-b111-877c7b24db75",
}

# Rollups de la ficha: (nombre en sandbox, relación, columna origen, función).
# La columna origen se da "limpia"; el script la resuelve al nombre EXACTO del
# esquema (algunas traen espacios finales). Números → sum; el resto → show_original.
ROLLUPS = [
    # --- F29 / Contable ---
    ("F29 Impuestos",        "Contable Origen", "Impuestos",            "sum"),
    ("F29 Honorarios Pend",  "Contable Origen", "Honorarios Pendientes","sum"),
    ("F29 Status",           "Contable Origen", "Status",               "show_original"),
    ("F29 ARec",             "Contable Origen", "ARec",                 "show_original"),
    ("F29 Boletas",          "Contable Origen", "emision de boletas",   "show_original"),
    ("F29 Actividad Econ",   "Contable Origen", "Actividad Econ",       "show_original"),
    # --- RRHH (IMPUESTO ÚNICO y MONTO IMPOSICIONES| ya existen) ---
    ("RRHH Nº Trab",         "RRHH Origen",     "Nº. Trab.",            "sum"),
    ("RRHH Previred",        "RRHH Origen",     "Previred",             "show_original"),
    ("RRHH Liquidaciones",   "RRHH Origen",     "Liquidaciones",        "show_original"),
    ("RRHH Asistente",       "RRHH Origen",     "ASISTENTE",            "show_original"),
    # --- CRM Comercial ---
    ("CRM Cobros",           "CRM Origen",      "Cobros",               "show_original"),
    ("CRM Facturado",        "CRM Origen",      "Facturado",            "show_original"),
    ("CRM Fac Anual",        "CRM Origen",      "Fac Anual",            "show_original"),
    ("CRM Estado",           "CRM Origen",      "Estado",               "show_original"),
    ("CRM Politica Fact",    "CRM Origen",      "Polity Facturation",   "show_original"),
    ("CRM Rubro",            "CRM Origen",      "Rubro",                "show_original"),
    ("CRM Acc UF",           "CRM Origen",      "Acc UF",               "sum"),
    ("CRM Honorario mes",    "CRM Origen",      "Honorario del mes",    "sum"),
    ("CRM Tarifa",           "CRM Origen",      "Tarifa de cobro mensual","sum"),
    # --- Tickets - Servicios ---
    ("Tickets Tipo",         "Tickets Origen",  "Tipo",                 "show_original"),
    ("Tickets Estado",       "Tickets Origen",  "Estado",               "show_original"),
    ("Tickets Fecha prom",   "Tickets Origen",  "Fecha prometida",      "show_original"),
    ("Tickets Monto",        "Tickets Origen",  "Monto a cobrar",       "sum"),
    ("Tickets IVA recup",    "Tickets Origen",  "IVA recuperado",       "sum"),
]


def _schema(ds_id: str) -> dict:
    r = nc.request_con_reintentos("GET", f"{nc.API}/data_sources/{ds_id}",
                                  headers=nc._headers(), timeout=30)
    r.raise_for_status()
    return r.json().get("properties", {})


def _exacto(nombre_limpio: str, props: dict) -> str | None:
    """Nombre EXACTO de la columna en el esquema (tolera espacios/caso)."""
    objetivo = nombre_limpio.strip().lower()
    for k in props:
        if k.strip().lower() == objetivo:
            return k
    return None


def main():
    load_dotenv()
    if not os.environ.get("NOTION_TOKEN"):
        raise SystemExit("Falta NOTION_TOKEN.")
    dry = "--dry" in sys.argv

    sb = _schema(SANDBOX)
    print(f"Sandbox tiene {len(sb)} columnas.\n")

    # 1) Relaciones (idempotente)
    nuevas_rel = {}
    for nombre, ds in RELACIONES.items():
        if nombre in sb:
            print(f"= relación '{nombre}' ya existe, se salta.")
            continue
        nuevas_rel[nombre] = {"relation": {"data_source_id": ds, "single_property": {}}}
        print(f"+ relación '{nombre}' -> {ds}")
    if nuevas_rel and not dry:
        nc.update_data_source(SANDBOX, nuevas_rel)
        sb = _schema(SANDBOX)  # refrescar
    print()

    # 2) Rollups (idempotente). Resolver nombre exacto de la columna origen.
    esquemas = {rel: _schema(ds) for rel, ds in RELACIONES.items()}
    nuevos_roll = {}
    for nombre, rel, col_limpia, func in ROLLUPS:
        if nombre in sb:
            print(f"= rollup '{nombre}' ya existe, se salta.")
            continue
        col_exacta = _exacto(col_limpia, esquemas[rel])
        if not col_exacta:
            print(f"! rollup '{nombre}': NO encontré la columna '{col_limpia}' en {rel} — se salta.")
            continue
        nuevos_roll[nombre] = {"rollup": {
            "relation_property_name": rel,
            "rollup_property_name": col_exacta,
            "function": func,
        }}
        print(f"+ rollup '{nombre}' = {rel} -> '{col_exacta}' ({func})")
    if nuevos_roll and not dry:
        nc.update_data_source(SANDBOX, nuevos_roll)

    print(f"\n{'(DRY) ' if dry else ''}Relaciones nuevas: {len(nuevas_rel)} · Rollups nuevos: {len(nuevos_roll)}")


if __name__ == "__main__":
    main()
