"""reconciliar.py — Feed del sandbox maestro desde las 4 tablas operativas.

Convierte el sandbox `General Customers Data - AuditAI` en el registro maestro (MDM)
que se alimenta de las tablas donde trabajan los asesores (Contable <Mes>, RRHH <Mes>,
CRM Comercial, Tickets - Servicios). Cruza cada fila operativa con su ficha maestra por
RUT (validado módulo 11) y, en su defecto, por nombre normalizado inequívoco. Pensado
para correr como cron SEMANAL en Render (100% automático, sin acción de los asesores).

🔒 REGLA DE ORO: las 4 tablas operativas se leen, JAMÁS se escriben. El 100% de las
escrituras (relaciones, fichas nuevas) ocurren solo en el sandbox (ver AGENTS.md y el
plan). El enlace es una relación UNA-VÍA sandbox → tabla: la propiedad vive solo en el
sandbox y no agrega columna a la tabla del asesor.

Modo por defecto: DRY-RUN (solo lectura, no escribe nada). Emite un resumen por consola
(sin PII) y un JSON de detalle en backups/general-customers-data/. El modo --apply (que
sí escribe en el sandbox) se habilita después de crear las relaciones (Fase 1) y de
revisar el dry-run.

Uso:
    python reconciliar.py            # dry-run, todas las fuentes
    python reconciliar.py --fuente Contable
"""
from __future__ import annotations
import os
import json
import logging
import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

from dotenv import load_dotenv
import notion_client as nc
import matching as mm

log = logging.getLogger("auditai")

# Carpeta de backups en la RAÍZ del repo (no relativa al cwd: el cron/ejecución
# puede correr desde notion_automation). backups/ está gitignored (lleva PII).
_RAIZ_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUPS_DIR = os.path.join(_RAIZ_REPO, "backups", "general-customers-data")

# --- Sandbox (destino, ÚNICO lugar que se escribe) ---
SANDBOX_DS = nc.DS_CENTRAL          # 4ff12147-…
COL_TITULO = "w"                    # title = nombre del cliente
COL_RUT = "RUT"                     # rich_text
COL_ID = "ID"                       # unique_id (PK estable)


@dataclass(frozen=True)
class Fuente:
    """Una tabla operativa de solo lectura y cómo cruza con el sandbox."""
    nombre: str          # etiqueta corta (log/reporte)
    ds_id: str           # data source (se LEE, nunca se escribe)
    col_rut: str | None  # columna con el RUT (None si la tabla no tiene RUT)
    col_nombre: str      # columna con el nombre del cliente (title)
    rel_sandbox: str     # nombre de la relación una-vía en el SANDBOX
    origen: str          # valor para la columna select `Origen` al crear ficha nueva


# El data source de Contable/RRHH es el del MES VIGENTE (se re-apunta al cambiar de mes,
# ver docs/dev/18 §4). Hoy: Contable Julio y RRHH JUNIO 2026.
FUENTES: list[Fuente] = [
    Fuente("Contable", "09b12147-b3ea-8337-a218-87538eab23fc", "Rut", "Customers", "Contable Origen", "Contable"),
    Fuente("RRHH", "9c512147-b3ea-8256-a570-871254c13b3d", "RUT", "CLIENTE", "RRHH Origen", "RRHH JUNIO 2026"),
    Fuente("CRM", "2961d0d2-de59-4fd5-b340-8930f6275101", "RUT", "Sw", "CRM Origen", "CRM Comercial"),
    Fuente("Tickets", "9d312147-b3ea-83bf-b111-877c7b24db75", None, "Tarea", "Tickets Origen", "Tickets"),
]

# Clasificación de cada fila operativa frente al sandbox.
MATCH_RUT = "MATCH_RUT"        # ligar a ficha existente (llave fuerte)
MATCH_NOMBRE = "MATCH_NOMBRE"  # ligar a ficha existente (respaldo por nombre exacto)
NUEVO = "NUEVO"                # RUT válido sin ficha → crear ficha maestra
AMBIGUO = "AMBIGUO"           # 2+ fichas candidatas → revisión humana, no ligar
SIN_FICHA = "SIN_FICHA"       # sin RUT válido y sin match por nombre → revisión
VACIA = "VACIA"               # fila sin RUT ni nombre → se ignora
RUIDO = "RUIDO"               # fila de control/test/basura (RESET_MES, ZZ_TEST, RUT suelto)


@dataclass
class Indice:
    fichas: dict            # sandbox page_id -> {"id", "nombre_norm", "rut"}
    por_rut: dict           # rut_llave -> [page_id, …]
    por_nombre: dict        # nombre_norm -> [page_id, …]


def cargar_sandbox() -> Indice:
    """Lee el sandbox e indexa por RUT (válido) y por nombre normalizado."""
    filas = nc.query_data_source(SANDBOX_DS, {"page_size": 100})
    fichas: dict = {}
    por_rut: dict = defaultdict(list)
    por_nombre: dict = defaultdict(list)
    for f in filas:
        props = f.get("properties", {})
        pid = f["id"]
        rutk = mm.rut_llave(nc.plain(props.get(COL_RUT, {})))
        nomk = mm.normalizar_nombre(nc.plain(props.get(COL_TITULO, {})))
        fichas[pid] = {
            "id": nc.unique_id_number(props.get(COL_ID, {})),
            "nombre_norm": nomk,
            "nombre_display": nc.plain(props.get(COL_TITULO, {})),
            "rut": rutk,
            # relaciones ya pobladas (para unir sin perder los enlaces curados a mano).
            "rel": {f.rel_sandbox: nc.relation_ids(props.get(f.rel_sandbox, {})) for f in FUENTES},
        }
        if rutk:
            por_rut[rutk].append(pid)
        if nomk:
            por_nombre[nomk].append(pid)
    log.info("sandbox cargado: %d fichas (%d con RUT válido, %d con nombre)",
             len(fichas), len(por_rut), len(por_nombre))
    return Indice(fichas, por_rut, por_nombre)


def clasificar(rutk: str | None, nomk: str, idx: Indice) -> tuple[str, str | None]:
    """Devuelve (clasificación, sandbox_page_id|None) para una fila operativa.
    `rutk` ya viene validado (o None); `nomk` ya viene normalizado."""
    if rutk and rutk in idx.por_rut:
        pids = idx.por_rut[rutk]
        return (MATCH_RUT, pids[0]) if len(pids) == 1 else (AMBIGUO, None)
    if nomk and nomk in idx.por_nombre:
        pids = idx.por_nombre[nomk]
        return (MATCH_NOMBRE, pids[0]) if len(pids) == 1 else (AMBIGUO, None)
    if rutk:
        return (NUEVO, None)     # identidad fuerte pero sin ficha → candidata a crear
    if nomk:
        return (SIN_FICHA, None)  # solo nombre, sin match → revisión
    return (VACIA, None)


def procesar_fuente(fuente: Fuente, idx: Indice) -> list[dict]:
    """Lee una tabla operativa (solo lectura) y clasifica cada fila."""
    filas = nc.query_data_source(fuente.ds_id, {"page_size": 100})
    resultados = []
    for f in filas:
        props = f.get("properties", {})
        nombre = nc.plain(props.get(fuente.col_nombre, {}))
        rut_raw = nc.plain(props.get(fuente.col_rut, {})) if fuente.col_rut else ""
        rutk = mm.rut_llave(rut_raw)
        nomk = mm.normalizar_nombre(nombre)
        if mm.es_ruido(nombre) and not rutk:
            clase, sandbox_pid = RUIDO, None
        else:
            clase, sandbox_pid = clasificar(rutk, nomk, idx)
        resultados.append({
            "op_page_id": f["id"],
            "nombre": nombre,
            "rut": rutk or "",
            "clasificacion": clase,
            "sandbox_page_id": sandbox_pid,
            "sandbox_id": idx.fichas.get(sandbox_pid, {}).get("id") if sandbox_pid else None,
        })
    return resultados


def _resumen(resultados: list[dict]) -> dict:
    c = defaultdict(int)
    for r in resultados:
        c[r["clasificacion"]] += 1
    return dict(c)


def dry_run(fuentes: list[Fuente]) -> dict:
    """Corre el cruce completo SIN escribir. Imprime resumen (sin PII) y guarda el
    detalle en un JSON de backups. Devuelve el dict de reporte."""
    idx = cargar_sandbox()
    # Duplicados en el sandbox (informativo: p. ej. SPV I/II comparten RUT).
    rut_dups = {k: len(v) for k, v in idx.por_rut.items() if len(v) > 1}
    nom_dups = {k: len(v) for k, v in idx.por_nombre.items() if len(v) > 1}

    reporte = {
        "fecha": datetime.now(timezone.utc).isoformat(),
        "sandbox_fichas": len(idx.fichas),
        "sandbox_rut_duplicados": len(rut_dups),
        "sandbox_nombre_duplicados": len(nom_dups),
        "fuentes": {},
    }
    detalle = {"rut_duplicados_sandbox": rut_dups, "nombre_duplicados_sandbox": nom_dups}

    print(f"\nSandbox: {len(idx.fichas)} fichas "
          f"({len(idx.por_rut)} con RUT válido, {len(idx.por_nombre)} con nombre). "
          f"Duplicados: {len(rut_dups)} por RUT, {len(nom_dups)} por nombre.\n")
    encabezado = f"{'Fuente':<10} {'filas':>6} {'MATCH_RUT':>10} {'MATCH_NOM':>10} {'NUEVO':>7} {'AMBIGUO':>8} {'SIN_FICHA':>10} {'DESCARTE':>9}"
    print(encabezado)
    print("-" * len(encabezado))
    for fuente in fuentes:
        res = procesar_fuente(fuente, idx)
        s = _resumen(res)
        reporte["fuentes"][fuente.nombre] = {"filas": len(res), **s}
        detalle[fuente.nombre] = res
        descarte = s.get(VACIA, 0) + s.get(RUIDO, 0)
        print(f"{fuente.nombre:<10} {len(res):>6} {s.get(MATCH_RUT,0):>10} "
              f"{s.get(MATCH_NOMBRE,0):>10} {s.get(NUEVO,0):>7} {s.get(AMBIGUO,0):>8} "
              f"{s.get(SIN_FICHA,0):>10} {descarte:>9}")

    fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ruta = os.path.join(BACKUPS_DIR, f"{fecha}_dry-run-reconciliacion.json")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(detalle, fh, ensure_ascii=False, indent=2)
    print(f"\nDetalle (con nombres/RUT) guardado en: {ruta}")
    print("⚠️  Ese archivo tiene PII — no commitear (backups/ está en .gitignore).\n")
    return reporte


UMBRAL_SUGERENCIA = 80   # score ≥ → "probable coincidencia" (Carlos confirma mismo/nuevo)
UMBRAL_PISTA = 65        # score en [65,80) → pista débil que se muestra en "nuevos"


def _ficha_por_nombre(idx: Indice, nombre_norm: str) -> tuple[str, int | None]:
    """(nombre_display, id) de la 1ª ficha del sandbox con ese nombre normalizado."""
    pids = idx.por_nombre.get(nombre_norm, [])
    if not pids:
        return ("", None)
    f = idx.fichas.get(pids[0], {})
    return (f.get("nombre_display", ""), f.get("id"))


def _celda(texto: str) -> str:
    """Escapa el '|' para no romper la tabla markdown."""
    return (texto or "").replace("|", "/").strip()


def _sanitizar_latin1(s: str) -> str:
    """El font core de fpdf2 (Helvetica) es latin-1; reemplaza lo que no encaje."""
    return (s or "").encode("latin-1", "replace").decode("latin-1")


def _render_pdf(partes_fuente, idx, tot_sug, tot_new, fecha, ruta_pdf):
    """Renderiza el mismo contenido del .md a PDF (fpdf2, sin dependencias nativas)."""
    from fpdf import FPDF
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()

    def linea(texto, h=5, size=10, style=""):
        # new_x=LMARGIN devuelve el cursor al margen izq. (si no, la sig. celda
        # arranca a la derecha y fpdf2 se queda sin ancho horizontal).
        pdf.set_font("Helvetica", style, size)
        pdf.multi_cell(0, h, _sanitizar_latin1(texto), new_x="LMARGIN", new_y="NEXT")

    linea("Revisión de clientes para centralizar — confirmar (Carlos)", h=8, size=15, style="B")
    linea(f"Fecha: {fecha}  ·  Total a revisar: {tot_sug + tot_new} "
          f"({tot_sug} posibles coincidencias + {tot_new} posibles nuevos)", size=10)
    linea("Contexto: armamos una ficha única por cliente juntando las 4 planillas (Contable, "
          "RRHH, CRM, Tickets). Los de abajo no se pudieron ubicar solos (sin RUT, o el nombre "
          "está escrito distinto). Marca con una X dentro de [ ]. A) mismo o nuevo. "
          "B) nuevo (o escribe la corrección al margen).", size=9)
    pdf.ln(2)
    for nombre_fuente, sugerencias, nuevos in partes_fuente:
        linea(nombre_fuente, h=7, size=12, style="B")
        linea("A) Posibles coincidencias — ¿mismo cliente que la ficha sugerida?", size=9, style="B")
        pdf.set_font("Helvetica", "", 8)
        if sugerencias:
            with pdf.table(col_widths=(8, 42, 42, 10, 11, 11), first_row_as_headings=True,
                           text_align=("CENTER", "LEFT", "LEFT", "CENTER", "CENTER", "CENTER")) as t:
                t.row(["#", "Cliente en planilla", "Ficha parecida (ID)", "Par.", "Mismo", "Nuevo"])
                for n, info in enumerate(sugerencias, 1):
                    disp, idnum = _ficha_por_nombre(idx, info["cands"][0][0])
                    idtxt = f" (ID {idnum})" if idnum is not None else ""
                    t.row([str(n), _sanitizar_latin1(info["display"]),
                           _sanitizar_latin1(disp + idtxt), f"{info['cands'][0][1]}%", "[  ]", "[  ]"])
        else:
            linea("Ninguna.", size=8)
        linea("B) Sin coincidencia clara — ¿cliente nuevo?", size=9, style="B")
        pdf.set_font("Helvetica", "", 8)
        if nuevos:
            with pdf.table(col_widths=(8, 55, 45, 12), first_row_as_headings=True,
                           text_align=("CENTER", "LEFT", "LEFT", "CENTER")) as t:
                t.row(["#", "Cliente en planilla", "Pista (parecido lejano)", "Nuevo"])
                for n, info in enumerate(nuevos, 1):
                    pista = ""
                    if info["cands"]:
                        d, _ = _ficha_por_nombre(idx, info["cands"][0][0])
                        pista = f"{d} ({info['cands'][0][1]}%)"
                    t.row([str(n), _sanitizar_latin1(info["display"]), _sanitizar_latin1(pista), "[  ]"])
        else:
            linea("Ninguno.", size=8)
        pdf.ln(2)
    pdf.output(ruta_pdf)


def reporte_carlos(fuentes: list[Fuente], hacer_pdf: bool = False) -> str:
    """Genera un .md legible con los clientes que NO se pudieron confirmar solos
    (sin RUT y sin nombre exacto), para que Carlos marque cuáles ya existen y
    cuáles son nuevos. Usa fuzzy SOLO para sugerir; nada se liga sin su OK.
    Si hacer_pdf, además escribe un .pdf con el mismo contenido."""
    idx = cargar_sandbox()
    universo = list(idx.por_nombre.keys())
    fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    partes_fuente = []   # (nombre_fuente, sugerencias, nuevos)
    tot_sug = tot_new = 0
    for fuente in fuentes:
        res = procesar_fuente(fuente, idx)
        vistos: dict = {}
        for r in res:
            if r["clasificacion"] != SIN_FICHA:
                continue
            nomk = mm.normalizar_nombre(r["nombre"])
            if not nomk:
                continue
            if nomk in vistos:
                vistos[nomk]["veces"] += 1
                continue
            cands = mm.candidatos_fuzzy(nomk, universo, limite=2, umbral=UMBRAL_PISTA)
            vistos[nomk] = {"display": r["nombre"], "cands": cands, "veces": 1}
        sugerencias, nuevos = [], []
        for info in vistos.values():
            cands = info["cands"]
            if cands and cands[0][1] >= UMBRAL_SUGERENCIA:
                sugerencias.append(info)
            else:
                nuevos.append(info)
        sugerencias.sort(key=lambda i: -i["cands"][0][1])
        nuevos.sort(key=lambda i: i["display"].lower())
        tot_sug += len(sugerencias)
        tot_new += len(nuevos)
        partes_fuente.append((fuente.nombre, sugerencias, nuevos))

    L = []
    L.append("# Revisión de clientes para centralizar — a confirmar por Carlos")
    L.append("")
    L.append(f"**Fecha:** {fecha}  ·  **Total a revisar:** {tot_sug + tot_new} "
             f"({tot_sug} posibles coincidencias + {tot_new} posibles nuevos)")
    L.append("")
    L.append("**Contexto.** Estamos armando una **ficha única por cliente** en la base maestra, "
             "juntando las 4 planillas (Contable, RRHH, CRM, Tickets). Los clientes de abajo son "
             "los únicos que el sistema **no pudo ubicar solo**: no traen RUT en la planilla, o su "
             "nombre está escrito distinto a como aparece en la base. Necesitamos tu ojo para no "
             "duplicar ni perder clientes.")
    L.append("")
    L.append("**Cómo responder:** marca con una **X** dentro del ☐.")
    L.append("- Sección **A):** si es el **mismo** cliente que la ficha sugerida, marca *Mismo*; "
             "si en realidad es otro, marca *Nuevo*.")
    L.append("- Sección **B):** si es un cliente **nuevo**, marca *Nuevo*; si sabes que ya existe "
             "en la base con otro nombre, escríbelo en *Corrección*.")
    L.append("")
    for nombre_fuente, sugerencias, nuevos in partes_fuente:
        L.append(f"## {nombre_fuente}")
        L.append("")
        if not sugerencias and not nuevos:
            L.append("_Sin casos pendientes._")
            L.append("")
            continue
        L.append("### A) Posibles coincidencias — ¿es el mismo cliente que la ficha sugerida?")
        L.append("")
        if sugerencias:
            L.append("| # | Cliente en la planilla | Ficha parecida en la base (ID) | Parecido | Mismo | Nuevo |")
            L.append("|--:|---|---|--:|:--:|:--:|")
            for n, info in enumerate(sugerencias, 1):
                disp, idnum = _ficha_por_nombre(idx, info["cands"][0][0])
                score = info["cands"][0][1]
                veces = f" ({info['veces']} reg.)" if info["veces"] > 1 else ""
                idtxt = f" (ID {idnum})" if idnum is not None else ""
                L.append(f"| {n} | {_celda(info['display'])}{veces} | {_celda(disp)}{idtxt} | {score}% | ☐ | ☐ |")
            L.append("")
        else:
            L.append("_Ninguna._")
            L.append("")
        L.append("### B) Sin coincidencia clara — ¿cliente nuevo?")
        L.append("")
        if nuevos:
            L.append("| # | Cliente en la planilla | Pista (parecido lejano) | Nuevo | Corrección |")
            L.append("|--:|---|---|:--:|---|")
            for n, info in enumerate(nuevos, 1):
                pista = ""
                if info["cands"]:
                    d, _ = _ficha_por_nombre(idx, info["cands"][0][0])
                    pista = f"{_celda(d)} ({info['cands'][0][1]}%)"
                veces = f" ({info['veces']} reg.)" if info["veces"] > 1 else ""
                L.append(f"| {n} | {_celda(info['display'])}{veces} | {pista} | ☐ | |")
            L.append("")
        else:
            L.append("_Ninguno._")
            L.append("")

    md = "\n".join(L)
    ruta = os.path.join(BACKUPS_DIR, f"{fecha}_revision-carlos.md")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(md)
    print(f"\nReporte para Carlos: {ruta}")
    if hacer_pdf:
        ruta_pdf = os.path.join(BACKUPS_DIR, f"{fecha}_revision-carlos.pdf")
        try:
            _render_pdf(partes_fuente, idx, tot_sug, tot_new, fecha, ruta_pdf)
            print(f"PDF: {ruta_pdf}")
        except Exception as exc:  # el .md ya quedó guardado; el PDF es un extra
            log.warning("no se pudo generar el PDF (queda el .md): %s", exc)
    print(f"  {tot_sug} posibles coincidencias + {tot_new} posibles nuevos = {tot_sug + tot_new} a confirmar.")
    print("  ⚠️  Tiene nombres de clientes (PII) — es para enviar a Carlos, no se commitea.\n")
    return ruta


def aplicar(fuentes: list[Fuente], dry: bool = True) -> dict:
    """Puebla las relaciones del sandbox con los matches SEGUROS y crea fichas
    para los NUEVO (RUT válido sin ficha). IDEMPOTENTE: une con lo ya ligado (no
    pierde enlaces curados a mano) y no re-crea fichas. AMBIGUO/SIN_FICHA/RUIDO se
    saltan (van al reporte de Carlos). Escribe SOLO en el sandbox.

    dry=True: calcula el plan y lo imprime, sin escribir nada."""
    idx = cargar_sandbox()
    add_por_ficha: dict = defaultdict(lambda: defaultdict(set))  # sandbox_pid -> rel -> {op_ids}
    nuevos: list = []            # (fuente, op_id, nombre, rut)
    por_tabla: dict = defaultdict(lambda: {"link": 0, "nuevo": 0})

    for fuente in fuentes:
        for f in nc.query_data_source(fuente.ds_id, {"page_size": 100}):
            props = f.get("properties", {})
            op_id = f["id"]
            nombre = nc.plain(props.get(fuente.col_nombre, {}))
            rut_raw = nc.plain(props.get(fuente.col_rut, {})) if fuente.col_rut else ""
            rutk = mm.rut_llave(rut_raw)
            nomk = mm.normalizar_nombre(nombre)
            if mm.es_ruido(nombre) and not rutk:
                continue
            clase, pid = clasificar(rutk, nomk, idx)
            if clase in (MATCH_RUT, MATCH_NOMBRE):
                add_por_ficha[pid][fuente.rel_sandbox].add(op_id)
                por_tabla[fuente.nombre]["link"] += 1
            elif clase == NUEVO:
                nuevos.append((fuente, op_id, nombre, rutk))
                por_tabla[fuente.nombre]["nuevo"] += 1

    ruts_nuevos = sorted({rut for _, _, _, rut in nuevos})
    print("\n=== PLAN de reconciliación (Fase 2) ===")
    for nombre_f, c in por_tabla.items():
        print(f"  {nombre_f:<9} enlaces a agregar: {c['link']:>4} · fichas nuevas: {c['nuevo']:>3}")
    print(f"  Fichas maestras a CREAR (RUT único): {len(ruts_nuevos)}")
    print(f"  Fichas del sandbox a ACTUALIZAR: {len(add_por_ficha)}")
    if dry:
        print("  (DRY-RUN: no se escribió nada)\n")
        return {"nuevos": len(ruts_nuevos), "fichas_update": len(add_por_ficha)}

    # 1) Crear fichas nuevas (dedup por RUT en el mismo run) y ligarlas.
    creados: dict = {}
    for fuente, op_id, nombre, rut in nuevos:
        if rut in creados:
            add_por_ficha[creados[rut]][fuente.rel_sandbox].add(op_id)
            continue
        page = nc.create_page(SANDBOX_DS, {
            COL_TITULO: {"title": [{"text": {"content": nombre or rut}}]},
            COL_RUT: {"rich_text": [{"text": {"content": rut}}]},
            "Origen": {"select": {"name": fuente.origen}},
            fuente.rel_sandbox: {"relation": [{"id": op_id}]},
        })
        creados[rut] = page["id"]
    print(f"  Fichas nuevas creadas: {len(creados)}")

    # 2) Unir relaciones por ficha (idempotente: preserva lo existente).
    fichas_tocadas = links_add = 0
    for pid, rels in add_por_ficha.items():
        updates = {}
        for rel_name, ids in rels.items():
            existentes = set(idx.fichas.get(pid, {}).get("rel", {}).get(rel_name, []))
            union = existentes | ids
            if union != existentes:
                updates[rel_name] = {"relation": [{"id": x} for x in union]}
                links_add += len(union) - len(existentes)
        if updates:
            nc.update_props(pid, updates)
            fichas_tocadas += 1
    print(f"  Fichas actualizadas: {fichas_tocadas} · enlaces nuevos agregados: {links_add}\n")
    return {"creados": len(creados), "fichas_tocadas": fichas_tocadas, "links_add": links_add}


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # La consola de Windows (cp1252) no imprime emojis/acentos; forzar UTF-8.
    try:
        import sys
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    load_dotenv()
    if not os.environ.get("NOTION_TOKEN"):
        raise SystemExit("Falta NOTION_TOKEN (poner en notion_automation/.env o en el entorno).")
    ap = argparse.ArgumentParser(description="Reconciliación sandbox ↔ tablas operativas (dry-run por defecto).")
    ap.add_argument("--fuente", help="Procesar solo una fuente (Contable/RRHH/CRM/Tickets).")
    ap.add_argument("--reporte-carlos", action="store_true",
                    help="Genera el .md de clientes sin ficha para que Carlos confirme.")
    ap.add_argument("--pdf", action="store_true", help="Además del .md, genera el .pdf.")
    ap.add_argument("--aplicar", action="store_true",
                    help="Puebla relaciones + crea fichas nuevas en el sandbox (ESCRIBE).")
    args = ap.parse_args()
    fuentes = FUENTES
    if args.fuente:
        fuentes = [f for f in FUENTES if f.nombre.lower() == args.fuente.lower()]
        if not fuentes:
            raise SystemExit(f"Fuente desconocida: {args.fuente}")
    if args.reporte_carlos:
        reporte_carlos(fuentes, hacer_pdf=args.pdf)
    elif args.aplicar:
        aplicar(fuentes, dry=False)
    else:
        dry_run(fuentes)


if __name__ == "__main__":
    main()
