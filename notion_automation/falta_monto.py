"""Columna de aviso `⚠️ Falta monto` en las planillas del mes vigente (RRHH y Contable).

Problema que resuelve (05-ago-2026): el monto es el contenido del correo, pero el
asesor no se entera de que la celda está vacía hasta que aprieta el botón. En RRHH
eso derivó en una avalancha de correos de error (26 de 50 filas sin cargar). Esta
columna se lo muestra en la planilla, donde trabaja, ANTES de apretar nada.

Es una FÓRMULA: no guarda datos, no se puede editar a mano y se recalcula sola.
Borrarla no pierde información.

Diferencia entre las dos planillas — el gate del backend NO es igual:

- **RRHH**: celda vacía NO se envía (regla de Carlos). La columna avisa de algo
  que además bloquea.
- **Contable/F29**: la celda vacía SÍ se envía y sale como "declara sin
  movimiento" (`monto or "0"` en app.py). Decisión del usuario (05-ago-2026):
  no bloquear, solo avisar. Acá la columna es la ÚNICA red: si la fila se manda
  vacía, el cliente recibe una afirmación tributaria que nadie cargó.

⚠️ Excepción explícita a la regla de oro del proyecto (sobre las tablas de los
asesores solo se crea `ID Central`): autorizada por el usuario el 05-ago-2026
para esta columna puntual. Ninguna otra columna se toca.

Uso:
  python falta_monto.py --dry           # qué haría en ambas, sin escribir
  python falta_monto.py                 # aplica en ambas planillas
  python falta_monto.py contable        # solo una
"""
from __future__ import annotations
import sys
import logging
from dataclasses import dataclass
from dotenv import load_dotenv
import notion_client as nc

log = logging.getLogger("auditai")

COL = "⚠️ Falta monto"
MARCA = "⚠️ Falta monto"

# Filas de servicio que NO son clientes: la de control del reset y las de prueba.
# Se matchean por `contains`, así que "ZZ_TEST AuditAI" también entra.
_FILAS_SERVICIO = ("RESET_MES", "ZZ_TEST")


@dataclass(frozen=True)
class Planilla:
    """Una planilla mensual con su columna de monto y su columna de título."""
    clave: str        # nombre corto para el CLI
    prefijo: str      # prefijo del título de la base, para resolverla en runtime
    monto: str        # columna number que no debería quedar vacía
    titulo: str       # columna title (se usa para excluir las filas de servicio)


PLANILLAS: dict[str, Planilla] = {
    "rrhh": Planilla("rrhh", "RRHH", "MONTO IMPOSICIONES|", "RUT"),
    "contable": Planilla("contable", "Contable", "Impuestos", "Customers"),
}


def expresion(p: Planilla) -> str:
    """Fórmula 2.0 de Notion: marca la fila solo si el monto está VACÍO.

    Un 0 escrito a mano NO se marca — es la distinción del negocio (vacío =
    olvido, 0 = dato; en Contable el 0 además significa "declarado sin
    movimiento", que son 62 filas reales de junio).

    ⚠️ NO usar empty(): en Notion `empty(0)` devuelve TRUE (verificado por API el
    05-ago-2026), o sea que marcaría los ceros explícitos, justo al revés de la
    regla. `format()` sí distingue: format(0)="0" y format(vacío)="". Es además
    el mismo criterio que nc.plain() en Python, así que la planilla y el backend
    coinciden siempre."""
    excluir = " ".join(
        f'contains(prop("{p.titulo}"), "{s}"),' for s in _FILAS_SERVICIO
    ).rstrip(",")
    return (
        f'if(and(format(prop("{p.monto}")) == "", '
        f'not(or({excluir}))), '
        f'"{MARCA}", "")'
    )


def def_col(p: Planilla) -> dict:
    return {"formula": {"expression": expresion(p)}}


CREADA, EXISTIA, ACTUALIZADA, CONFLICTO = "CREADA", "EXISTIA", "ACTUALIZADA", "CONFLICTO"


def ya_es_la_nuestra(expr: str, props: dict, p: Planilla) -> bool:
    """True si la fórmula YA guardada es esta versión y apunta a la columna correcta.

    No se puede comparar contra `expresion(p)` como texto: al guardar, Notion
    NORMALIZA la expresión — reescribe `prop("X")` como una referencia interna por
    id (`{{notion:block_property:<id>:...}}`) y `not(...)` como `!` (verificado por
    API el 05-ago-2026). Una comparación textual daría siempre distinto y
    reescribiría la columna en cada corrida.

    Por eso se chequea por partes: que apunte al id real de la columna de monto,
    que lleve nuestra marca, y que use `format(` y NO `empty(` — así la primera
    versión (la que marcaba los ceros explícitos) se detecta como vieja y se repara."""
    if MARCA not in expr:
        return False
    pid = (props.get(p.monto) or {}).get("id") or ""
    if not pid or pid not in expr:
        return False
    return "format(" in expr and "empty(" not in expr


def asegurar_columna(p: Planilla, ds_id: str, dry: bool = False) -> str:
    """Crea `⚠️ Falta monto` (formula) en el data source si no está. Idempotente.

    Devuelve CREADA / EXISTIA / ACTUALIZADA (estaba pero con otra expresión, se
    corrige) / CONFLICTO (hay una columna con ese nombre y otro tipo → no se toca,
    se resuelve a mano). Solo toca esta columna: jamás modifica ni borra otra."""
    props = nc.get_data_source_schema(ds_id)
    if p.monto not in props:
        raise RuntimeError(f"la base no tiene la columna {p.monto!r}; no es una planilla {p.prefijo}")
    actual = props.get(COL)
    if actual is not None:
        if actual.get("type") != "formula":
            return CONFLICTO
        if ya_es_la_nuestra((actual.get("formula") or {}).get("expression") or "", props, p):
            return EXISTIA
        # Expresión distinta (versión vieja o editada a mano): se repara.
        if not dry:
            nc.update_data_source(ds_id, {COL: def_col(p)})
        return ACTUALIZADA
    if not dry:
        nc.update_data_source(ds_id, {COL: def_col(p)})
    return CREADA


def contar_sin_monto(p: Planilla, ds_id: str) -> tuple[int, int]:
    """(filas_sin_monto, filas_totales) de la base, ignorando filas de servicio.
    Solo lectura; no expone montos ni PII."""
    sin, total = 0, 0
    for f in nc.query_data_source(ds_id, {"page_size": 100}):
        props = f.get("properties", {})
        titulo = nc.plain(props.get(p.titulo, {}))
        if any(s in titulo.upper() for s in _FILAS_SERVICIO):
            continue
        total += 1
        if not nc.plain(props.get(p.monto, {})):
            sin += 1
    return sin, total


def resolver_ds(p: Planilla) -> tuple[str, str]:
    """(data_source_id, titulo) de la base vigente de esa planilla.
    Se resuelve por título en runtime: RRHH estrena base cada mes y Contable se
    renombra en sitio, así que ninguna de las dos puede estar fija en el código."""
    import reconciliar
    if p.clave == "rrhh":
        from handlers.rrhh import DS_ID as fallback
    else:
        fallback = nc.DS_CONTABLE_JUNIO
    ds_id = reconciliar.resolver_ds_actual(p.prefijo, fallback)
    titulo = ""
    for r in nc.buscar_data_sources(p.prefijo):
        if r.get("id") == ds_id:
            t = r.get("title") or []
            titulo = "".join(x.get("plain_text", "") for x in t) if isinstance(t, list) else str(t)
            break
    return ds_id, titulo


def main(argv: list[str]) -> int:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    dry = "--dry" in argv
    pedidas = [a for a in argv if not a.startswith("-")]
    claves = pedidas or list(PLANILLAS)
    for c in claves:
        if c not in PLANILLAS:
            print(f"planilla desconocida: {c!r} (opciones: {', '.join(PLANILLAS)})")
            return 2

    for c in claves:
        p = PLANILLAS[c]
        ds_id, titulo = resolver_ds(p)
        sin, total = contar_sin_monto(p, ds_id)
        estado = asegurar_columna(p, ds_id, dry=dry)
        print(f"[{p.prefijo}] {titulo or '(sin título)'}  [{ds_id}]")
        print(f"    columna {p.monto!r}: {sin} de {total} filas sin cargar")
        print(f"    {COL!r}: {estado}{'  (dry-run, no se escribió)' if dry else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
