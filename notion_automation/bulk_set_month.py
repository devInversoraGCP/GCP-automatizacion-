"""Bulk-set Month en Contable Junio. Opcion A (doc 23):
fija Month = 'Junio 2026' en todas las filas para que el asesor no lo tipee.

Uso:
  python bulk_set_month.py             # dry-run: reporta, no escribe
  python bulk_set_month.py --apply     # aplica el bulk-set

No loguea PII. Backup previo a backups/contable-junio/.
"""
from __future__ import annotations
import os
import sys
import csv
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import notion_client as nc

load_dotenv()

DS_CONTABLE_JUNIO = "09b12147-b3ea-8337-a218-87538eab23fc"
MONTH_OBJETIVO = "Junio 2026"
BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups" / "contable-junio"


def main(aplicar: bool) -> None:
    print(f"=== bulk_set_month · {'APLICAR' if aplicar else 'DRY-RUN'} ===")
    print(f"Month objetivo: {MONTH_OBJETIVO!r}")
    print()

    # 1. Leer todas las filas de Contable Junio
    print("Leyendo Contable Junio (data source)...")
    filas = nc.query_data_source(DS_CONTABLE_JUNIO)
    print(f"  total filas: {len(filas)}")

    # 2. Extraer (page_id, Customers, Month actual)
    registros = []
    for f in filas:
        props = f.get("properties", {})
        pid = f["id"]
        nombre = nc.plain(props.get("Customers", {}))
        month_actual = nc.plain(props.get("Month", {}))
        registros.append({"page_id": pid, "Customers": nombre, "Month_actual": month_actual})

    # 3. Backup previo (siempre, antes de escribir)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    backup_path = BACKUP_DIR / f"{ts}_pre-month-bulk.csv"
    with backup_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["page_id", "Customers", "Month_actual"])
        w.writeheader()
        w.writerows(registros)
    print(f"  backup previo: {backup_path}")

    # 4. Reporte (dry-run)
    llenos = [r for r in registros if r["Month_actual"]]
    vacios = [r for r in registros if not r["Month_actual"]]
    ya_ok = [r for r in llenos if r["Month_actual"] == MONTH_OBJETIVO]
    distintos = [r for r in llenos if r["Month_actual"] != MONTH_OBJETIVO]
    print()
    print("=== reporte ===")
    print(f"  filas con Month ya = {MONTH_OBJETIVO!r}: {len(ya_ok)}")
    print(f"  filas con Month != {MONTH_OBJETIVO!r} (se sobreescriben): {len(distintos)}")
    print(f"  filas con Month vacio (se llenan): {len(vacios)}")
    print(f"  total a modificar: {len(distintos) + len(vacios)}")
    if distintos:
        print("  valores distintos actuales (muestra):")
        for r in distintos[:10]:
            print(f"    {r['Customers']!r}: {r['Month_actual']!r}")

    if not aplicar:
        print()
        print("DRY-RUN: no se escribio nada. Correr con --apply para aplicar.")
        return

    # 5. Aplicar bulk-set
    print()
    print(f"=== aplicando Month = {MONTH_OBJETIVO!r} a {len(registros)} filas ===")
    ok, err = 0, 0
    for i, r in enumerate(registros, 1):
        try:
            nc.update_props(r["page_id"], {
                "Month": {"rich_text": [{"text": {"content": MONTH_OBJETIVO}}]}
            })
            ok += 1
            if i % 50 == 0:
                print(f"  progreso: {i}/{len(registros)} (ok={ok})")
        except Exception as exc:
            err += 1
            print(f"  ERROR fila {i} (no se loguea PII): {type(exc).__name__}: {exc}")
    print()
    print(f"=== resultado: ok={ok} errores={err} total={len(registros)} ===")


if __name__ == "__main__":
    aplicar = "--apply" in sys.argv
    main(aplicar)
