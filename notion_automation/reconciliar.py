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
import re
import json
import logging
import argparse
from collections import defaultdict
from dataclasses import dataclass, replace
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
    ds_id: str           # data source (se LEE, nunca se escribe); fallback si el prefijo no resuelve
    col_rut: str | None  # columna con el RUT (None si la tabla no tiene RUT)
    col_nombre: str      # columna con el nombre del cliente (title)
    rel_sandbox: str     # nombre de la relación una-vía en el SANDBOX
    origen: str          # valor para la columna select `Origen` al crear ficha nueva
    prefijo: str | None = None  # si la base cambia por mes, prefijo del título ("Contable"/"RRHH")


# Contable/RRHH tienen base por MES: se resuelven en runtime al data source del período
# más nuevo (prefijo). CRM/Tickets son estables (sin prefijo → usan su ds_id fijo). El
# ds_id de Contable/RRHH queda como FALLBACK por si el search falla.
FUENTES: list[Fuente] = [
    Fuente("Contable", "09b12147-b3ea-8337-a218-87538eab23fc", "Rut", "Customers", "Contable Origen", "Contable", prefijo="Contable"),
    Fuente("RRHH", "9c512147-b3ea-8256-a570-871254c13b3d", "RUT", "CLIENTE", "RRHH Origen", "RRHH JUNIO 2026", prefijo="RRHH"),
    Fuente("CRM", "2961d0d2-de59-4fd5-b340-8930f6275101", "RUT", "Sw", "CRM Origen", "CRM Comercial"),
    Fuente("Tickets", "9d312147-b3ea-83bf-b111-877c7b24db75", None, "Tarea", "Tickets Origen", "Tickets"),
]


def _titulo_result(it: dict) -> str:
    """Título de un result de búsqueda de data source (título rich_text o `name`)."""
    t = it.get("title")
    if isinstance(t, list):
        s = "".join(x.get("plain_text", "") for x in t).strip()
        if s:
            return s
    return (it.get("name") or "").strip()


def _periodo_de_titulo(titulo: str, last_edited: str = "") -> tuple[int, int] | None:
    """(año, mes) del título de una base mensual, o None si no trae mes.
    'RRHH JUNIO 2026' -> (2026, 6); 'Contable Julio' -> (año de last_edited, 7).
    El año explícito en el título manda; si no hay, se usa el de last_edited."""
    mes = None
    for tok in re.split(r"[^a-záéíóúñ]+", titulo.lower()):
        if tok in nc._MESES_ES:
            mes = nc._MESES_ES[tok]
            break
    if not mes:
        return None
    m = re.search(r"(20\d{2})", titulo)
    if m:
        anio = int(m.group(1))
    elif last_edited[:4].isdigit():
        anio = int(last_edited[:4])
    else:
        anio = 0
    return (anio, mes)


def resolver_ds_actual(prefijo: str, fallback_id: str) -> str:
    """Data source de la base '<prefijo> <mes>' del PERÍODO MÁS NUEVO. Robusto al
    cambio de mes: cuando aparece p. ej. 'RRHH JULIO 2026', se elige solo. Elige por
    período parseado del título (NO por last_edited: hay copias viejas re-editadas).
    Si el search falla o no hay candidatos, devuelve `fallback_id`."""
    try:
        results = nc.buscar_data_sources(prefijo)
    except Exception as exc:
        log.warning("search de '%s' falló, uso fallback: %s", prefijo, exc)
        return fallback_id
    mejor = None  # (anio, mes, ds_id, titulo)
    for it in results:
        titulo = _titulo_result(it)
        if not titulo.lower().startswith(prefijo.lower()):
            continue
        per = _periodo_de_titulo(titulo, it.get("last_edited_time", ""))
        if not per:
            continue
        cand = (per[0], per[1], it["id"], titulo)
        if mejor is None or cand[:2] > mejor[:2]:
            mejor = cand
    if mejor:
        log.info("fuente '%s' -> '%s' (%s)", prefijo, mejor[3], mejor[2][:8])
        return mejor[2]
    log.warning("no encontré base para '%s', uso fallback %s", prefijo, fallback_id[:8])
    return fallback_id


def nombre_base_actual(prefijo: str, fallback: str = "") -> str:
    """Título de la base '<prefijo> <mes>' del período más nuevo — la que está
    CONECTADA al servidor hoy. Para mostrársela a los asesores en el aviso de
    cambio de mes (así saben qué página renombrar y no se equivocan). '' si no hay."""
    try:
        results = nc.buscar_data_sources(prefijo)
    except Exception:
        return fallback
    mejor = None
    for it in results:
        titulo = _titulo_result(it)
        if not titulo.lower().startswith(prefijo.lower()):
            continue
        per = _periodo_de_titulo(titulo, it.get("last_edited_time", ""))
        if not per:
            continue
        cand = (per[0], per[1], titulo.strip())
        if mejor is None or cand[:2] > mejor[:2]:
            mejor = cand
    return mejor[2] if mejor else fallback


def fuentes_resueltas(fuentes: list[Fuente]) -> list[Fuente]:
    """Devuelve las fuentes con el ds_id del mes vigente resuelto (para las que
    tienen prefijo). Las estables (CRM/Tickets) quedan igual."""
    out = []
    for f in fuentes:
        if f.prefijo:
            ds = resolver_ds_actual(f.prefijo, f.ds_id)
            out.append(f if ds == f.ds_id else replace(f, ds_id=ds))
        else:
            out.append(f)
    return out

# Clasificación de cada fila operativa frente al sandbox.
# --- Auto-ligar a ficha existente (sin pasar por Carlos) ---
MATCH_RUT = "MATCH_RUT"        # RUT idéntico (llave fuerte)
MATCH_NOMBRE = "MATCH_NOMBRE"  # nombre normalizado idéntico
MATCH_FUZZY = "MATCH_FUZZY"    # nombre MUY parecido (>= AUTO_UMBRAL) — Carlos autorizó confiar
# --- Crear ficha nueva (sin pasar por Carlos) ---
NUEVO = "NUEVO"                # RUT válido sin ficha → crear con RUT
PROBABLE_NUEVO = "PROBABLE_NUEVO"  # sin RUT y sin parecido → cliente nuevo claro → crear
# --- A revisión de Carlos (la lista CORTA) ---
A_CARLOS = "A_CARLOS"          # parecido medio, empate, o enumerador distinto (I/II) → confuso
AMBIGUO = "AMBIGUO"            # 2+ fichas exactas → revisión humana
# --- Se ignoran ---
VACIA = "VACIA"                # fila sin RUT ni nombre
RUIDO = "RUIDO"                # control/test/basura (RESET_MES, ZZ_TEST, RUT suelto)

# Umbrales de parecido de nombre (token_sort_ratio, 0–100). Carlos (dueño del dato,
# 27-jul) pidió confiar en los muy parecidos y mandarle solo los confusos.
AUTO_UMBRAL = 88     # >= AUTO → auto-ligar, SALVO enumerador distinto o empate
CARLOS_UMBRAL = 72   # [CARLOS, AUTO) → a Carlos; < CARLOS → cliente nuevo


@dataclass
class Indice:
    fichas: dict            # sandbox page_id -> {"id", "nombre_norm", "rut", …}
    por_rut: dict           # rut_llave -> [page_id, …]
    por_nombre: dict        # nombre_norm -> [page_id, …]
    universo: list          # lista de nombres normalizados (para el fuzzy)


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
    return Indice(fichas, por_rut, por_nombre, list(por_nombre.keys()))


def clasificar(rutk: str | None, nomk: str, idx: Indice) -> tuple[str, str | None]:
    """Devuelve (clasificación, sandbox_page_id|None) para una fila operativa.
    `rutk` ya viene validado (o None); `nomk` ya viene normalizado.

    Orden: RUT exacto → nombre exacto → fuzzy (auto-liga solo si es MUY parecido y
    seguro; medio/empate/enumerador → Carlos) → nuevo (con o sin RUT)."""
    if rutk and rutk in idx.por_rut:
        pids = idx.por_rut[rutk]
        return (MATCH_RUT, pids[0]) if len(pids) == 1 else (AMBIGUO, None)
    if nomk and nomk in idx.por_nombre:
        pids = idx.por_nombre[nomk]
        return (MATCH_NOMBRE, pids[0]) if len(pids) == 1 else (AMBIGUO, None)
    if nomk:
        cands = mm.candidatos_fuzzy(nomk, idx.universo, limite=2, umbral=CARLOS_UMBRAL)
        if cands:
            mejor_nom, mejor_score = cands[0]
            pids = idx.por_nombre.get(mejor_nom, [])
            empate = len(cands) >= 2 and (mejor_score - cands[1][1]) <= 3
            seguro = (mejor_score >= AUTO_UMBRAL and len(pids) == 1
                      and not empate and not mm.enumerador_distinto(nomk, mejor_nom))
            if seguro:
                return (MATCH_FUZZY, pids[0])   # muy parecido y sin trampa → confiar
            return (A_CARLOS, None)             # medio / empate / enumerador → Carlos
    if rutk:
        return (NUEVO, None)                    # RUT válido sin ficha → crear con RUT
    if nomk:
        return (PROBABLE_NUEVO, None)           # sin parecido y sin RUT → cliente nuevo
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
    encabezado = f"{'Fuente':<9} {'filas':>6} {'exactos':>8} {'fuzzy':>6} {'nuevos':>7} {'aCarlos':>8} {'descarte':>9}"
    print(encabezado)
    print("-" * len(encabezado))
    for fuente in fuentes:
        res = procesar_fuente(fuente, idx)
        s = _resumen(res)
        reporte["fuentes"][fuente.nombre] = {"filas": len(res), **s}
        detalle[fuente.nombre] = res
        exactos = s.get(MATCH_RUT, 0) + s.get(MATCH_NOMBRE, 0)
        nuevos = s.get(NUEVO, 0) + s.get(PROBABLE_NUEVO, 0)
        acarlos = s.get(A_CARLOS, 0) + s.get(AMBIGUO, 0)
        descarte = s.get(VACIA, 0) + s.get(RUIDO, 0)
        print(f"{fuente.nombre:<9} {len(res):>6} {exactos:>8} {s.get(MATCH_FUZZY,0):>6} "
              f"{nuevos:>7} {acarlos:>8} {descarte:>9}")

    fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ruta = os.path.join(BACKUPS_DIR, f"{fecha}_dry-run-reconciliacion.json")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(detalle, fh, ensure_ascii=False, indent=2)
    print(f"\nDetalle (con nombres/RUT) guardado en: {ruta}")
    print("⚠️  Ese archivo tiene PII — no commitear (backups/ está en .gitignore).\n")
    return reporte


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


def _motivo_carlos(clase: str, nomk: str, cands: list) -> str:
    """Por qué este caso necesita el ojo de Carlos (para la columna 'Motivo')."""
    if clase == AMBIGUO:
        return "nombre duplicado en la base"
    if not cands:
        return "revisar"
    mejor_nom, score = cands[0]
    if mm.enumerador_distinto(nomk, mejor_nom):
        return "difiere en número (I/II, 1/2)"
    if len(cands) >= 2 and (score - cands[1][1]) <= 3:
        return "dos fichas casi igual de parecidas"
    return "parecido medio"


def _render_pdf(partes_fuente, idx, total, fecha, ruta_pdf):
    """Renderiza la lista corta (solo dudosos) a PDF (fpdf2, sin deps nativas)."""
    from fpdf import FPDF
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()

    def linea(texto, h=5, size=10, style=""):
        # new_x=LMARGIN devuelve el cursor al margen izq. (si no, la sig. celda
        # arranca a la derecha y fpdf2 se queda sin ancho horizontal).
        pdf.set_font("Helvetica", style, size)
        pdf.multi_cell(0, h, _sanitizar_latin1(texto), new_x="LMARGIN", new_y="NEXT")

    linea("Clientes a confirmar — Carlos", h=8, size=15, style="B")
    linea(f"Fecha: {fecha}  ·  Total a revisar: {total}", size=10)
    linea("Ya centralizamos automáticamente los que coinciden por RUT, por nombre igual o por "
          "nombre MUY parecido. Abajo quedan SOLO los dudosos (parecido medio, empatados, o que "
          "difieren en un número tipo I/II). Marca con una X en [ ]: Mismo = es la ficha "
          "sugerida; Nuevo = es un cliente distinto.", size=9)
    pdf.ln(2)
    for nombre_fuente, casos in partes_fuente:
        linea(nombre_fuente, h=7, size=12, style="B")
        pdf.set_font("Helvetica", "", 8)
        if not casos:
            linea("Sin casos pendientes.", size=8)
            pdf.ln(1)
            continue
        with pdf.table(col_widths=(7, 33, 33, 9, 24, 8, 8), first_row_as_headings=True,
                       text_align=("CENTER", "LEFT", "LEFT", "CENTER", "LEFT", "CENTER", "CENTER")) as t:
            t.row(["#", "Cliente en planilla", "Ficha parecida (ID)", "Par.", "Motivo", "Mismo", "Nuevo"])
            for n, info in enumerate(casos, 1):
                if info["cands"]:
                    disp, idnum = _ficha_por_nombre(idx, info["cands"][0][0])
                    disp += f" (ID {idnum})" if idnum is not None else ""
                    score = f"{info['cands'][0][1]}%"
                else:
                    disp, score = "—", ""
                veces = f" ({info['veces']} reg.)" if info["veces"] > 1 else ""
                t.row([str(n), _sanitizar_latin1(info["display"] + veces),
                       _sanitizar_latin1(disp), score, _sanitizar_latin1(info["motivo"]),
                       "[  ]", "[  ]"])
        pdf.ln(2)
    pdf.output(ruta_pdf)


def reporte_carlos(fuentes: list[Fuente], hacer_pdf: bool = False) -> str:
    """Genera la LISTA CORTA de clientes dudosos para que Carlos confirme: solo los
    A_CARLOS (parecido medio / empate / enumerador distinto) y AMBIGUO (nombre
    duplicado). Los muy parecidos ya se auto-ligaron y los sin parecido ya se
    crearon (Carlos, 27-jul). Si hacer_pdf, escribe también el .pdf."""
    idx = cargar_sandbox()
    fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    partes_fuente = []   # (nombre_fuente, casos)
    total = 0
    for fuente in fuentes:
        res = procesar_fuente(fuente, idx)
        vistos: dict = {}
        for r in res:
            if r["clasificacion"] not in (A_CARLOS, AMBIGUO):
                continue
            nomk = mm.normalizar_nombre(r["nombre"])
            if not nomk:
                continue
            if nomk in vistos:
                vistos[nomk]["veces"] += 1
                continue
            cands = mm.candidatos_fuzzy(nomk, idx.universo, limite=2, umbral=CARLOS_UMBRAL)
            vistos[nomk] = {"display": r["nombre"], "cands": cands, "veces": 1,
                            "motivo": _motivo_carlos(r["clasificacion"], nomk, cands)}
        casos = sorted(vistos.values(), key=lambda i: -(i["cands"][0][1] if i["cands"] else 0))
        partes_fuente.append((fuente.nombre, casos))
        total += len(casos)

    L = []
    L.append("# Clientes a confirmar — Carlos")
    L.append("")
    L.append(f"**Fecha:** {fecha}  ·  **Total a revisar:** {total}")
    L.append("")
    L.append("**Contexto.** Ya centralizamos **automáticamente** los clientes que coinciden por "
             "RUT, por nombre igual, o por nombre **muy parecido**. Abajo quedan **solo los "
             "dudosos**: parecido medio, empatados entre dos fichas, o que difieren en un número "
             "(tipo I/II, 1/2). Solo necesitamos tu ojo en estos.")
    L.append("")
    L.append("**Cómo responder:** marca con una **X** en ☐. *Mismo* = es el mismo cliente que la "
             "ficha sugerida; *Nuevo* = es un cliente distinto (se crea aparte).")
    L.append("")
    for nombre_fuente, casos in partes_fuente:
        L.append(f"## {nombre_fuente}")
        L.append("")
        if not casos:
            L.append("_Sin casos pendientes._")
            L.append("")
            continue
        L.append("| # | Cliente en la planilla | Ficha parecida (ID) | Parecido | Motivo | Mismo | Nuevo |")
        L.append("|--:|---|---|--:|---|:--:|:--:|")
        for n, info in enumerate(casos, 1):
            if info["cands"]:
                disp, idnum = _ficha_por_nombre(idx, info["cands"][0][0])
                idtxt = f" (ID {idnum})" if idnum is not None else ""
                score = f"{info['cands'][0][1]}%"
            else:
                disp, idtxt, score = "—", "", ""
            veces = f" ({info['veces']} reg.)" if info["veces"] > 1 else ""
            L.append(f"| {n} | {_celda(info['display'])}{veces} | {_celda(disp)}{idtxt} | "
                     f"{score} | {_celda(info['motivo'])} | ☐ | ☐ |")
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
            _render_pdf(partes_fuente, idx, total, fecha, ruta_pdf)
            print(f"PDF: {ruta_pdf}")
        except Exception as exc:  # el .md ya quedó guardado; el PDF es un extra
            log.warning("no se pudo generar el PDF (queda el .md): %s", exc)
    print(f"  {total} casos dudosos a confirmar (los claros ya se auto-ligaron/crearon).")
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
            if clase in (MATCH_RUT, MATCH_NOMBRE, MATCH_FUZZY):
                add_por_ficha[pid][fuente.rel_sandbox].add(op_id)
                por_tabla[fuente.nombre]["link"] += 1
            elif clase in (NUEVO, PROBABLE_NUEVO):
                nuevos.append((fuente, op_id, nombre, rutk))
                por_tabla[fuente.nombre]["nuevo"] += 1

    claves_nuevas = {("rut", r) if r else ("nom", mm.normalizar_nombre(n))
                     for _f, _op, n, r in nuevos}
    print("\n=== PLAN de reconciliación (Fase 2) ===")
    for nombre_f, c in por_tabla.items():
        print(f"  {nombre_f:<9} enlaces a agregar: {c['link']:>4} · fichas nuevas: {c['nuevo']:>3}")
    print(f"  Fichas maestras a CREAR (únicas): {len(claves_nuevas)}")
    print(f"  Fichas del sandbox a ACTUALIZAR: {len(add_por_ficha)}")
    if dry:
        print("  (DRY-RUN: no se escribió nada)\n")
        return {"nuevos": len(claves_nuevas), "fichas_update": len(add_por_ficha)}

    # 1) Crear fichas nuevas y ligarlas. Dedup en el mismo run: por RUT si lo hay,
    # si no por nombre normalizado (dos tickets del mismo cliente → 1 ficha).
    creados_rut: dict = {}
    creados_nom: dict = {}
    for fuente, op_id, nombre, rut in nuevos:
        if rut:
            if rut in creados_rut:
                add_por_ficha[creados_rut[rut]][fuente.rel_sandbox].add(op_id)
                continue
            page = nc.create_page(SANDBOX_DS, {
                COL_TITULO: {"title": [{"text": {"content": nombre or rut}}]},
                COL_RUT: {"rich_text": [{"text": {"content": rut}}]},
                "Origen": {"select": {"name": fuente.origen}},
                fuente.rel_sandbox: {"relation": [{"id": op_id}]},
            })
            creados_rut[rut] = page["id"]
        else:
            nk = mm.normalizar_nombre(nombre)
            if not nk:
                continue
            if nk in creados_nom:
                add_por_ficha[creados_nom[nk]][fuente.rel_sandbox].add(op_id)
                continue
            page = nc.create_page(SANDBOX_DS, {   # sin RUT: solo nombre + origen + relación
                COL_TITULO: {"title": [{"text": {"content": nombre}}]},
                "Origen": {"select": {"name": fuente.origen}},
                fuente.rel_sandbox: {"relation": [{"id": op_id}]},
            })
            creados_nom[nk] = page["id"]
    print(f"  Fichas nuevas creadas: {len(creados_rut) + len(creados_nom)}")

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
    return {"creados": len(creados_rut) + len(creados_nom),
            "fichas_tocadas": fichas_tocadas, "links_add": links_add}


def reporte_duplicados(umbral: int = 88) -> str:
    """Lista posibles fichas duplicadas en el sandbox: por RUT idéntico, por nombre
    idéntico, y por nombre MUY parecido (fuzzy). Solo LECTURA. Escribe un .md en
    backups/ para revisión (higiene de datos tras auto-crear fichas)."""
    idx = cargar_sandbox()
    fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    L = ["# Posibles duplicados en el sandbox", "",
         f"**Fecha:** {fecha} · **Fichas:** {len(idx.fichas)}", ""]

    def _grupo(pids):
        return " · ".join(
            f"ID {idx.fichas[p]['id']} — {idx.fichas[p]['nombre_display']}" for p in pids)

    rut_dups = {k: v for k, v in idx.por_rut.items() if len(v) > 1}
    L.append(f"## Por RUT idéntico ({len(rut_dups)})")
    L.append("")
    if rut_dups:
        L.append("| RUT | Fichas |\n|---|---|")
        for rut, pids in sorted(rut_dups.items()):
            L.append(f"| {rut} | {_celda(_grupo(pids))} |")
    else:
        L.append("_Ninguno._")
    L.append("")

    nom_dups = {k: v for k, v in idx.por_nombre.items() if len(v) > 1}
    L.append(f"## Por nombre idéntico ({len(nom_dups)})")
    L.append("")
    if nom_dups:
        L.append("| Nombre | Fichas |\n|---|---|")
        for nom, pids in sorted(nom_dups.items()):
            L.append(f"| {_celda(nom)} | {_celda(_grupo(pids))} |")
    else:
        L.append("_Ninguno._")
    L.append("")

    # Nombre muy parecido (fuzzy), sin contar iguales ni enumeradores distintos (I/II).
    vistos, pares = set(), []
    for nom in idx.universo:
        for cand, score in mm.candidatos_fuzzy(nom, idx.universo, limite=4, umbral=umbral):
            if cand == nom or mm.enumerador_distinto(nom, cand):
                continue
            par = tuple(sorted((nom, cand)))
            if par not in vistos:
                vistos.add(par)
                pares.append((score, par[0], par[1]))
    pares.sort(key=lambda x: -x[0])
    L.append(f"## Por nombre muy parecido (≥{umbral}%) ({len(pares)})")
    L.append("")
    if pares:
        L.append("| Parecido | Ficha A | Ficha B |\n|--:|---|---|")
        for score, a, b in pares:
            fa, ia = _ficha_por_nombre(idx, a)
            fb, ib = _ficha_por_nombre(idx, b)
            L.append(f"| {score}% | {_celda(fa)} (ID {ia}) | {_celda(fb)} (ID {ib}) |")
    else:
        L.append("_Ninguno._")
    L.append("")

    ruta = os.path.join(BACKUPS_DIR, f"{fecha}_posibles-duplicados.md")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    print(f"Reporte de duplicados: {ruta}")
    print(f"  RUT idéntico: {len(rut_dups)} · nombre idéntico: {len(nom_dups)} · "
          f"parecido ≥{umbral}%: {len(pares)} pares")
    return ruta


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
    ap.add_argument("--duplicados", action="store_true",
                    help="Reporte de posibles fichas duplicadas del sandbox (solo lectura).")
    args = ap.parse_args()
    fuentes = FUENTES
    if args.fuente:
        fuentes = [f for f in FUENTES if f.nombre.lower() == args.fuente.lower()]
        if not fuentes:
            raise SystemExit(f"Fuente desconocida: {args.fuente}")
    # Resolver Contable/RRHH al data source del mes vigente (robusto al cambio de mes).
    fuentes = fuentes_resueltas(fuentes)
    if args.duplicados:
        reporte_duplicados()
        return
    if args.reporte_carlos:
        reporte_carlos(fuentes, hacer_pdf=args.pdf)
    elif args.aplicar:
        try:
            res = aplicar(fuentes, dry=False)
        except Exception as exc:
            # El cron falló: avisar al admin (best-effort) y propagar para que
            # Render marque el job como fallido.
            try:
                import alertas
                alertas.avisar_excepcion_admin("reconciliacion-cron", "", exc)
            except Exception:
                log.exception("además, falló el aviso de excepción del cron")
            raise
        # Éxito: resumen semanal al admin (así se sabe que SÍ corrió).
        try:
            import alertas
            alertas.avisar_resumen_reconciliacion(res)
        except Exception:
            log.exception("no se pudo enviar el resumen de éxito del cron")
    else:
        dry_run(fuentes)


if __name__ == "__main__":
    main()
