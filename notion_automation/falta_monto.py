"""Columna de aviso `⚠️ Falta monto` en la planilla RRHH del mes vigente.

Problema que resuelve (05-ago-2026): el correo de RRHH NO se envía si
`MONTO IMPOSICIONES|` está vacío — regla de negocio confirmada por Carlos: tiene
que haber un número, aunque sea un 0. Pero el asesor no se enteraba de que la
celda estaba vacía hasta que apretaba el botón y le llegaba un correo de error
(en RRHH JULIO 2026 eran 26 de 50 filas). Esta columna se lo muestra en la
planilla, donde trabaja, ANTES de apretar nada.

Es una FÓRMULA: no guarda datos, no se puede editar a mano y se recalcula sola.
Borrarla no pierde información.

⚠️ Excepción explícita a la regla de oro del proyecto (sobre las 4 tablas de los
asesores solo se crea `ID Central`): autorizada por el usuario el 05-ago-2026
para esta columna puntual. Ninguna otra columna se toca.

Uso:
  python falta_monto.py --dry     # muestra qué haría, sin escribir
  python falta_monto.py           # crea la columna en la base RRHH vigente
"""
from __future__ import annotations
import sys
import logging
from dotenv import load_dotenv
import notion_client as nc

log = logging.getLogger("auditai")

COL = "⚠️ Falta monto"
MONTO = "MONTO IMPOSICIONES|"

# Filas de servicio que NO son clientes: la de control del reset y las de prueba.
# El título de la base RRHH es la columna `RUT`.
_FILAS_SERVICIO = ("RESET_MES", "ZZ_TEST")

# Fórmula 2.0 de Notion. Marca la fila solo si el monto está VACÍO; un 0 escrito
# a mano NO se marca — es la distinción del negocio (vacío = olvido, 0 = dato).
#
# ⚠️ NO usar empty(): en Notion `empty(0)` devuelve TRUE (verificado por API el
# 05-ago-2026), o sea que marcaría los ceros explícitos, justo al revés de la
# regla. `format()` sí distingue: format(0)="0" y format(vacío)="". Es además el
# mismo criterio que nc.plain() en Python, así que la planilla y el backend
# coinciden siempre.
EXPRESION = (
    'if(and(format(prop("' + MONTO + '")) == "", '
    'not(or(contains(prop("RUT"), "' + _FILAS_SERVICIO[0] + '"), '
    'contains(prop("RUT"), "' + _FILAS_SERVICIO[1] + '")))), '
    '"⚠️ Falta monto", "")'
)

DEF_COL = {"formula": {"expression": EXPRESION}}

CREADA, EXISTIA, ACTUALIZADA, CONFLICTO = "CREADA", "EXISTIA", "ACTUALIZADA", "CONFLICTO"


def asegurar_columna(ds_id: str, dry: bool = False) -> str:
    """Crea `⚠️ Falta monto` (formula) en el data source si no está. Idempotente.

    Devuelve CREADA / EXISTIA / ACTUALIZADA (estaba pero con otra expresión, se
    corrige) / CONFLICTO (hay una columna con ese nombre y otro tipo → no se toca,
    se resuelve a mano). Solo toca esta columna: jamás modifica ni borra otra."""
    props = nc.get_data_source_schema(ds_id)
    if MONTO not in props:
        raise RuntimeError(f"la base no tiene la columna {MONTO!r}; no es una base RRHH")
    actual = props.get(COL)
    if actual is not None:
        if actual.get("type") != "formula":
            return CONFLICTO
        if (actual.get("formula") or {}).get("expression") == EXPRESION:
            return EXISTIA
        # Expresión distinta (versión vieja o editada a mano): se repara.
        if not dry:
            nc.update_data_source(ds_id, {COL: DEF_COL})
        return ACTUALIZADA
    if not dry:
        nc.update_data_source(ds_id, {COL: DEF_COL})
    return CREADA


def contar_sin_monto(ds_id: str) -> tuple[int, int]:
    """(filas_sin_monto, filas_totales) de la base, ignorando filas de servicio.
    Solo lectura; no expone montos ni PII."""
    sin, total = 0, 0
    for f in nc.query_data_source(ds_id, {"page_size": 100}):
        props = f.get("properties", {})
        titulo = nc.plain(props.get("RUT", {}))
        if any(s in titulo for s in _FILAS_SERVICIO):
            continue
        total += 1
        if not nc.plain(props.get(MONTO, {})):
            sin += 1
    return sin, total


def main(argv: list[str]) -> int:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    dry = "--dry" in argv

    from handlers.rrhh import ds_vigente
    ds_id = ds_vigente()
    titulo = ""
    for r in nc.buscar_data_sources("RRHH"):
        if r.get("id") == ds_id:
            t = r.get("title") or []
            titulo = "".join(x.get("plain_text", "") for x in t) if isinstance(t, list) else str(t)
            break

    print(f"base RRHH vigente : {titulo or '(sin título)'}  [{ds_id}]")
    sin, total = contar_sin_monto(ds_id)
    print(f"filas sin monto   : {sin} de {total}")
    estado = asegurar_columna(ds_id, dry=dry)
    print(f"columna {COL!r}: {estado}{'  (dry-run, no se escribió)' if dry else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
