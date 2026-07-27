"""Fase 3 — Capa analítica: exporta el sandbox consolidado a SQLite + CSV.

Baja las 340 fichas del sandbox (identidad + rollups operativos de F29/RRHH/CRM/
Tickets) a una tabla plana `clientes` con el `ID` como llave primaria, para correr
SQL, métricas, gráficos e insights (Notion no hace JOIN entre data sources; aquí sí).

Solo LECTURA de Notion. Genera:
  backups/general-customers-data/clientes.sqlite   (consulta con cualquier cliente SQL)
  backups/general-customers-data/clientes.csv      (portátil; abre en Excel)
Ambos llevan PII → backups/ está gitignored.

Uso:  python exportar_dataset.py
"""
from __future__ import annotations
import os
import csv
import sqlite3
import logging
from dotenv import load_dotenv
import notion_client as nc

log = logging.getLogger("auditai")

SANDBOX = nc.DS_CENTRAL
_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(_RAIZ, "backups", "general-customers-data")

# (columna en el sandbox, columna en SQLite, tipo SQLite). El valor se aplana con
# _scalar() sea cual sea el tipo Notion (rollup incluido).
COLUMNAS = [
    ("ID", "id", "INTEGER"),
    ("w", "nombre", "TEXT"),
    ("RUT", "rut", "TEXT"),
    ("Origen", "origen", "TEXT"),
    ("email", "email", "TEXT"),
    ("Adviser Accounting", "adviser_contable", "TEXT"),
    ("Adviser RR.HH", "adviser_rrhh", "TEXT"),
    ("Ciudad", "ciudad", "TEXT"),
    ("Segmentación", "segmentacion", "TEXT"),
    ("Rubro", "rubro", "TEXT"),
    ("CRM", "crm", "TEXT"),
    # --- F29 / Contable (rollups) ---
    ("F29 Impuestos", "f29_impuestos", "REAL"),
    ("F29 Honorarios Pend", "f29_honorarios", "REAL"),
    ("F29 Status", "f29_status", "TEXT"),
    ("F29 ARec", "f29_arec", "TEXT"),
    ("F29 Boletas", "f29_boletas", "TEXT"),
    ("F29 Actividad Econ", "f29_actividad", "TEXT"),
    # --- RRHH (rollups) ---
    ("IMPUESTO ÚNICO", "rrhh_impuesto_unico", "REAL"),
    ("MONTO IMPOSICIONES|", "rrhh_monto_imposiciones", "REAL"),
    ("RRHH Nº Trab", "rrhh_n_trab", "REAL"),
    ("RRHH Previred", "rrhh_previred", "TEXT"),
    ("RRHH Liquidaciones", "rrhh_liquidaciones", "TEXT"),
    ("RRHH Asistente", "rrhh_asistente", "TEXT"),
    # --- CRM (rollups) ---
    ("CRM Cobros", "crm_cobros", "TEXT"),
    ("CRM Facturado", "crm_facturado", "TEXT"),
    ("CRM Fac Anual", "crm_fac_anual", "TEXT"),
    ("CRM Estado", "crm_estado", "TEXT"),
    ("CRM Politica Fact", "crm_politica_fact", "TEXT"),
    ("CRM Rubro", "crm_rubro", "TEXT"),
    ("CRM Acc UF", "crm_acc_uf", "REAL"),
    ("CRM Honorario mes", "crm_honorario_mes", "REAL"),
    ("CRM Tarifa", "crm_tarifa", "REAL"),
    # --- Tickets (rollups) ---
    ("Tickets Tipo", "tickets_tipo", "TEXT"),
    ("Tickets Estado", "tickets_estado", "TEXT"),
    ("Tickets Fecha prom", "tickets_fecha_prom", "TEXT"),
    ("Tickets Monto", "tickets_monto", "REAL"),
    ("Tickets IVA recup", "tickets_iva_recup", "REAL"),
    # --- Cobertura: nº de filas operativas ligadas ---
    ("Contable Origen", "n_contable", "INTEGER"),
    ("RRHH Origen", "n_rrhh", "INTEGER"),
    ("CRM Origen", "n_crm", "INTEGER"),
    ("Tickets Origen", "n_tickets", "INTEGER"),
]


def _scalar(prop: dict):
    """Aplana cualquier propiedad Notion a un escalar (str/num/int/None) para SQL."""
    t = prop.get("type")
    if t is None:
        return None
    if t in ("title", "rich_text"):
        return nc.plain(prop) or None
    if t == "email":
        return prop.get("email") or None
    if t == "phone_number":
        return prop.get("phone_number") or None
    if t == "url":
        return prop.get("url") or None
    if t == "number":
        return prop.get("number")
    if t in ("select", "status"):
        v = prop.get(t)
        return v.get("name") if v else None
    if t == "multi_select":
        return ", ".join(x.get("name", "") for x in prop.get("multi_select", [])) or None
    if t == "people":
        return "; ".join(x.get("name", "") for x in prop.get("people", [])) or None
    if t == "date":
        d = prop.get("date")
        return d.get("start") if d else None
    if t == "checkbox":
        return 1 if prop.get("checkbox") else 0
    if t == "unique_id":
        return nc.unique_id_number(prop)
    if t == "relation":
        return len(prop.get("relation", []))
    if t == "rollup":
        return _scalar_rollup(prop)
    return None


def _scalar_rollup(prop: dict):
    r = prop.get("rollup", {})
    if r.get("type") == "number":
        return r.get("number")
    if r.get("type") == "date":
        d = r.get("date")
        return d.get("start") if d else None
    vals = []
    for item in r.get("array", []):
        v = _scalar(item)
        if v not in (None, ""):
            vals.append(v)
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    # dedup preservando orden (varias filas ligadas → varios valores)
    vistos, uniq = set(), []
    for v in vals:
        if v not in vistos:
            vistos.add(v); uniq.append(v)
    return ", ".join(str(v) for v in uniq)


def construir_filas() -> list[dict]:
    filas = nc.query_data_source(SANDBOX, {"page_size": 100})
    out = []
    for f in filas:
        props = f.get("properties", {})
        fila = {}
        for prop_notion, col_sql, _tipo in COLUMNAS:
            fila[col_sql] = _scalar(props.get(prop_notion, {}))
        out.append(fila)
    return out


def escribir_sqlite(filas: list[dict], ruta: str):
    cols_sql = ", ".join(f'"{c}" {t}' + (" PRIMARY KEY" if c == "id" else "")
                         for _n, c, t in COLUMNAS)
    con = sqlite3.connect(ruta)
    try:
        cur = con.cursor()
        cur.execute("DROP TABLE IF EXISTS clientes")
        cur.execute(f"CREATE TABLE clientes ({cols_sql})")
        nombres = [c for _n, c, _t in COLUMNAS]
        placeholders = ", ".join("?" for _ in nombres)
        cur.executemany(
            f'INSERT OR REPLACE INTO clientes ({", ".join(nombres)}) VALUES ({placeholders})',
            [tuple(f.get(c) for c in nombres) for f in filas],
        )
        con.commit()
    finally:
        con.close()


def escribir_csv(filas: list[dict], ruta: str):
    nombres = [c for _n, c, _t in COLUMNAS]
    with open(ruta, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=nombres)
        w.writeheader()
        w.writerows(filas)


def _metricas_demo(ruta_sqlite: str):
    """Corre unas consultas SQL de ejemplo para validar el JOIN por ID y dar insights."""
    con = sqlite3.connect(ruta_sqlite)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    def q(sql):
        return cur.execute(sql).fetchall()
    print("\n--- Métricas de ejemplo (SQL sobre clientes.sqlite) ---")
    print("Total clientes:", q("SELECT COUNT(*) n FROM clientes")[0]["n"])
    cob = q("""SELECT
                 SUM(n_contable>0) con_f29, SUM(n_rrhh>0) con_rrhh,
                 SUM(n_crm>0) con_crm, SUM(n_tickets>0) con_tickets
               FROM clientes""")[0]
    print(f"Cobertura: F29={cob['con_f29']} · RRHH={cob['con_rrhh']} · "
          f"CRM={cob['con_crm']} · Tickets={cob['con_tickets']}")
    print("Clientes por adviser contable (top 5):")
    for r in q("""SELECT COALESCE(adviser_contable,'(sin asignar)') adv, COUNT(*) n
                  FROM clientes GROUP BY adv ORDER BY n DESC LIMIT 5"""):
        print(f"  {r['n']:>4}  {r['adv']}")
    imp = q("SELECT ROUND(SUM(f29_impuestos),0) s FROM clientes")[0]["s"]
    print(f"Suma F29 Impuestos (mes vigente, en llenado): {imp}")
    con.close()


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        import sys; sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    load_dotenv()
    if not os.environ.get("NOTION_TOKEN"):
        raise SystemExit("Falta NOTION_TOKEN.")
    os.makedirs(OUT_DIR, exist_ok=True)
    filas = construir_filas()
    ruta_db = os.path.join(OUT_DIR, "clientes.sqlite")
    ruta_csv = os.path.join(OUT_DIR, "clientes.csv")
    escribir_sqlite(filas, ruta_db)
    escribir_csv(filas, ruta_csv)
    print(f"Exportadas {len(filas)} fichas.")
    print(f"  SQLite: {ruta_db}")
    print(f"  CSV:    {ruta_csv}")
    _metricas_demo(ruta_db)


if __name__ == "__main__":
    main()
