"""id_central.py — La llave primaria compartida `ID Central` en las 5 tablas.

El sandbox maestro `General Customers Data - AuditAI` tiene una columna `ID`
(unique_id) que es la PK estable de cada cliente, pero esa llave SOLO vive ahí.
Este módulo la **estampa** en las 4 planillas operativas (Contable <Mes>, RRHH
<Mes>, CRM Comercial, Tickets - Servicios) como una columna `ID Central` (number),
para poder unir las 5 tablas por igualdad de llave (join determinista en SQL),
sin depender de cruces por nombre/parecido.

De dónde sale el mapeo: de las **relaciones ya pobladas** del sandbox
(`Contable Origen`, `RRHH Origen`, `CRM Origen`, `Tickets Origen`). Aquí NO se
re-cruza nada por RUT/nombre/fuzzy — eso ya lo hizo (y lo sigue haciendo cada
semana) `reconciliar.py`; este módulo solo propaga el resultado.

🔒 Regla de oro ENMENDADA (dueño, 29-jul-2026): en las 4 planillas de los asesores
la ÚNICA escritura permitida por este módulo es la columna `ID Central` (crearla y
rellenarla). Ninguna otra columna, valor o dato de esas tablas se toca. Ver AGENTS.md.

Modo por defecto: DRY-RUN (no escribe nada; imprime el plan sin PII).

Uso:
    python id_central.py                 # dry-run: esquema + plan de estampado
    python id_central.py --esquema       # SOLO crea la columna (aditivo y seguro)
    python id_central.py --aplicar       # crea columna + estampa (ESCRIBE)
    python id_central.py --verificar     # cobertura y consistencia (solo lectura)
    python id_central.py --fuente CRM    # acotar a una planilla
"""
from __future__ import annotations
import os
import json
import time
import logging
import argparse
from collections import defaultdict
from datetime import datetime, timezone

from dotenv import load_dotenv
import notion_client as nc
import reconciliar as rec

log = logging.getLogger("auditai")

# Nombre IDÉNTICO en las 4 planillas (para que el join sea uniforme).
COL = "ID Central"
# Definición de la columna en el esquema de Notion (number liso, sin formato de moneda).
DEF_COL = {"number": {"format": "number"}}

# Pausa entre escrituras: Notion tolera ~3 req/s en promedio. Con 0.34s vamos
# justo por debajo y no gatillamos 429 (http_util igual reintenta si pasa).
PAUSA_ESCRITURA = 0.34

# Estados de `asegurar_columna`.
CREADA = "creada"
EXISTIA = "existía"
CONFLICTO = "conflicto"


def candidatos_ds(fuente: rec.Fuente, sb_schema: dict | None = None) -> list[str]:
    """Data sources donde pueden vivir las filas ligadas de esta fuente, sin repetir.

    Normalmente es uno solo, pero en el cambio de mes pueden diferir: el mes
    vigente (a donde apunta el cron hoy), el data source al que apunta la relación
    del sandbox (donde viven los enlaces ya guardados) y el fallback de `FUENTES`.
    Estampar hay que estamparlo donde de verdad está la fila."""
    vistos: list[str] = []
    for ds in (rec.resolver_ds_actual(fuente.prefijo, fuente.ds_id) if fuente.prefijo else fuente.ds_id,
               ((sb_schema or {}).get(fuente.rel_sandbox, {}).get("relation") or {}).get("data_source_id", ""),
               fuente.ds_id):
        if ds and ds not in vistos:
            vistos.append(ds)
    return vistos


def asegurar_columna(ds_id: str, dry: bool = False) -> str:
    """Crea `ID Central` (number) en un data source si no está. Idempotente.

    Devuelve CREADA / EXISTIA / CONFLICTO (ya hay una columna con ese nombre pero
    de otro tipo → no se toca, hay que resolverlo a mano). Solo agrega esta
    columna: jamás modifica ni borra ninguna otra."""
    props = nc.get_data_source_schema(ds_id)
    actual = props.get(COL)
    if actual is not None:
        return EXISTIA if actual.get("type") == "number" else CONFLICTO
    if not dry:
        nc.update_data_source(ds_id, {COL: DEF_COL})
    return CREADA


def leer_valores(ds_id: str) -> dict[str, int | None]:
    """`op_page_id -> valor actual de ID Central` (None si vacío o si no existe la
    columna). Una sola query paginada por planilla, en vez de un GET por fila."""
    out: dict[str, int | None] = {}
    for f in nc.query_data_source(ds_id, {"page_size": 100}):
        p = f.get("properties", {}).get(COL, {})
        out[f["id"]] = p.get("number") if p.get("type") == "number" else None
    return out


def plan_estampado(idx: rec.Indice, fuentes: list[rec.Fuente]) -> tuple[dict, dict]:
    """Qué ID le toca a cada fila operativa, leyendo las relaciones YA pobladas.

    Devuelve (`destinos`, `conflictos`):
      - destinos: op_page_id -> (nombre_fuente, id_central)
      - conflictos: op_page_id -> [ids en disputa] (la misma fila colgando de dos
        fichas maestras distintas → NO se estampa, se reporta).

    Si un cliente tiene varias filas en la misma planilla, todas reciben el mismo
    ID (es el mismo cliente). Las filas sin relación no aparecen: quedan sin
    `ID Central` a propósito (son los casos pendientes de revisión)."""
    destinos: dict[str, tuple[str, int]] = {}
    conflictos: dict[str, set] = defaultdict(set)
    for ficha in idx.fichas.values():
        idnum = ficha.get("id")
        if idnum is None:
            continue
        for f in fuentes:
            for op_id in ficha.get("rel", {}).get(f.rel_sandbox, []):
                previo = destinos.get(op_id)
                if previo is not None and previo[1] != idnum:
                    conflictos[op_id] |= {previo[1], idnum}
                    continue
                destinos[op_id] = (f.nombre, idnum)
    for op_id in conflictos:
        destinos.pop(op_id, None)
    return destinos, {k: sorted(v) for k, v in conflictos.items()}


def respaldar(mapa_ds: dict) -> str:
    """Respaldo previo al backfill: page_id + valor actual de `ID Central` de cada
    fila, por planilla. Va a backups/ (gitignored). Agregar una columna no es
    destructivo, pero el respaldo permite revertir el estampado si hiciera falta.
    No guarda nombres ni RUT: solo page_ids y el número (sin PII)."""
    fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    detalle = {
        "fecha": datetime.now(timezone.utc).isoformat(),
        "columna": COL,
        "planillas": {ds: {"fuente": meta["fuente"], "valores": meta["valores"]}
                      for ds, meta in mapa_ds.items()},
    }
    ruta = os.path.join(rec.BACKUPS_DIR, f"{fecha}_pre-id-central.json")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(detalle, fh, ensure_ascii=False, indent=2)
    return ruta


def _cargar_planillas(fuentes: list[rec.Fuente], dry: bool) -> tuple[dict, dict]:
    """Prepara las planillas: asegura la columna y lee los valores actuales.

    Devuelve (`mapa_ds`, `ubicacion`):
      - mapa_ds: ds_id -> {"fuente", "estado", "valores": {page_id: valor|None}}
      - ubicacion: op_page_id -> ds_id (dónde vive cada fila)"""
    sb_schema = nc.get_data_source_schema(rec.SANDBOX_DS)
    mapa_ds: dict = {}
    ubicacion: dict = {}
    for f in fuentes:
        for ds in candidatos_ds(f, sb_schema):
            if ds in mapa_ds:
                continue
            estado = asegurar_columna(ds, dry=dry)
            if estado == CONFLICTO:
                log.warning("%s: ya existe una columna '%s' que NO es number en %s — se salta",
                            f.nombre, COL, ds[:8])
            valores = leer_valores(ds)
            mapa_ds[ds] = {"fuente": f.nombre, "estado": estado, "valores": valores}
            for page_id in valores:
                ubicacion.setdefault(page_id, ds)
    return mapa_ds, ubicacion


def backfill(fuentes: list[rec.Fuente], dry: bool = True) -> dict:
    """Estampa `ID Central` en las filas operativas ya ligadas al sandbox.

    IDEMPOTENTE: escribe una fila solo si su valor difiere del que le toca. Las
    filas no ligadas se dejan intactas (sin ID Central). dry=True: solo imprime
    el plan (no crea la columna ni escribe valores)."""
    idx = rec.cargar_sandbox()
    mapa_ds, ubicacion = _cargar_planillas(fuentes, dry)
    destinos, conflictos = plan_estampado(idx, fuentes)

    # Clasificar cada destino: falta / ya está / hay que corregir / no ubicado.
    pendientes: list[tuple[str, int]] = []          # (op_page_id, id_central)
    stats: dict = defaultdict(lambda: defaultdict(int))
    for op_id, (nombre_f, idnum) in destinos.items():
        ds = ubicacion.get(op_id)
        if ds is None or mapa_ds.get(ds, {}).get("estado") == CONFLICTO:
            stats[nombre_f]["sin_ubicar"] += 1
            continue
        actual = mapa_ds[ds]["valores"].get(op_id)
        stats[nombre_f]["ligadas"] += 1
        if actual == idnum:
            stats[nombre_f]["ya_ok"] += 1
        else:
            stats[nombre_f]["corregir" if actual is not None else "escribir"] += 1
            pendientes.append((op_id, idnum))

    print(f"\n=== PLAN de estampado de '{COL}' ({'DRY-RUN' if dry else 'APLICAR'}) ===")
    for ds, meta in mapa_ds.items():
        print(f"  {meta['fuente']:<9} ds {ds[:8]} · columna: {meta['estado']:<8} · filas: {len(meta['valores'])}")
    print()
    enc = f"  {'Fuente':<9} {'ligadas':>8} {'ya ok':>7} {'a escribir':>11} {'a corregir':>11} {'sin ubicar':>11}"
    print(enc)
    print("  " + "-" * (len(enc) - 2))
    for f in fuentes:
        s = stats[f.nombre]
        print(f"  {f.nombre:<9} {s['ligadas']:>8} {s['ya_ok']:>7} {s['escribir']:>11} "
              f"{s['corregir']:>11} {s['sin_ubicar']:>11}")
    print(f"\n  Filas a escribir en total: {len(pendientes)}")
    if conflictos:
        print(f"  ⚠️  {len(conflictos)} fila(s) ligadas a DOS fichas maestras distintas — "
              f"no se estampan: {list(conflictos)[:3]}")

    if dry:
        print("  (DRY-RUN: no se creó ninguna columna ni se escribió ningún valor)\n")
        return {"pendientes": len(pendientes), "conflictos": len(conflictos),
                "stats": {k: dict(v) for k, v in stats.items()}}

    ruta = respaldar(mapa_ds)
    print(f"  Respaldo previo: {ruta}")

    escritas = 0
    for op_id, idnum in pendientes:
        nc.update_props(op_id, {COL: {"number": idnum}})
        escritas += 1
        if escritas % 50 == 0:
            print(f"  … {escritas}/{len(pendientes)} filas estampadas")
        time.sleep(PAUSA_ESCRITURA)
    print(f"  ✅ Filas estampadas: {escritas}\n")
    return {"escritas": escritas, "conflictos": len(conflictos),
            "stats": {k: dict(v) for k, v in stats.items()}}


def verificar(fuentes: list[rec.Fuente]) -> dict:
    """Verificación (solo lectura): la columna existe, cuántas filas tienen
    `ID Central`, y si coincide con el `ID` de la ficha maestra que la liga."""
    idx = rec.cargar_sandbox()
    mapa_ds, ubicacion = _cargar_planillas(fuentes, dry=True)
    destinos, conflictos = plan_estampado(idx, fuentes)

    ids_maestra = {ficha["id"] for ficha in idx.fichas.values() if ficha.get("id") is not None}
    reporte: dict = {}
    print(f"\n=== VERIFICACIÓN de '{COL}' ===")
    enc = (f"  {'Fuente':<9} {'columna':>8} {'filas':>6} {'con ID':>7} {'ligadas':>8} "
           f"{'coinciden':>10} {'discrepan':>10} {'huérfanos':>10}")
    print(enc)
    print("  " + "-" * (len(enc) - 2))
    for f in fuentes:
        dss = [ds for ds, meta in mapa_ds.items() if meta["fuente"] == f.nombre]
        filas = con_id = coinciden = discrepan = huerfanos = 0
        columna = "no"
        for ds in dss:
            meta = mapa_ds[ds]
            # En verificación se lee en dry: CREADA significa "todavía no existe".
            columna = {EXISTIA: "sí", CREADA: "FALTA"}.get(meta["estado"], meta["estado"])
            for page_id, val in meta["valores"].items():
                filas += 1
                if val is None:
                    continue
                con_id += 1
                if val not in ids_maestra:
                    huerfanos += 1
                esperado = destinos.get(page_id)
                if esperado is not None:
                    coinciden += 1 if esperado[1] == val else 0
                    discrepan += 0 if esperado[1] == val else 1
        ligadas = sum(1 for op, (nf, _) in destinos.items() if nf == f.nombre and op in ubicacion)
        reporte[f.nombre] = {"columna": columna, "filas": filas, "con_id": con_id,
                             "ligadas": ligadas, "coinciden": coinciden,
                             "discrepan": discrepan, "huerfanos": huerfanos}
        print(f"  {f.nombre:<9} {columna:>8} {filas:>6} {con_id:>7} {ligadas:>8} "
              f"{coinciden:>10} {discrepan:>10} {huerfanos:>10}")
    total_ok = all(v["discrepan"] == 0 and v["huerfanos"] == 0 for v in reporte.values())
    print(f"\n  Consistencia: {'✅ OK' if total_ok else '⚠️ revisar discrepancias'} · "
          f"conflictos de doble ficha: {len(conflictos)}\n")
    return reporte


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        import sys
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    load_dotenv()
    if not os.environ.get("NOTION_TOKEN"):
        raise SystemExit("Falta NOTION_TOKEN (poner en notion_automation/.env o en el entorno).")
    ap = argparse.ArgumentParser(
        description=f"Estampa la llave '{COL}' en las 4 planillas (dry-run por defecto).")
    ap.add_argument("--fuente", help="Solo una planilla (Contable/RRHH/CRM/Tickets).")
    ap.add_argument("--esquema", action="store_true",
                    help=f"Solo crea la columna '{COL}' donde falte (ESCRIBE esquema).")
    ap.add_argument("--aplicar", action="store_true",
                    help="Crea la columna y estampa los valores (ESCRIBE).")
    ap.add_argument("--verificar", action="store_true", help="Cobertura y consistencia (solo lectura).")
    args = ap.parse_args()

    fuentes = rec.FUENTES
    if args.fuente:
        fuentes = [f for f in rec.FUENTES if f.nombre.lower() == args.fuente.lower()]
        if not fuentes:
            raise SystemExit(f"Fuente desconocida: {args.fuente}")
    fuentes = rec.fuentes_resueltas(fuentes)

    if args.verificar:
        verificar(fuentes)
    elif args.esquema:
        sb_schema = nc.get_data_source_schema(rec.SANDBOX_DS)
        for f in fuentes:
            for ds in candidatos_ds(f, sb_schema):
                print(f"  {f.nombre:<9} ds {ds[:8]} → {asegurar_columna(ds)}")
    else:
        backfill(fuentes, dry=not args.aplicar)


if __name__ == "__main__":
    main()
