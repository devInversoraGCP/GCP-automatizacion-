"""Normalización de RUT y de nombre para el cruce cliente ↔ ficha maestra.

Funciones PURAS (sin red, sin estado) que implementan la metodología de match ya
definida en docs/dev/12 §A2:

- `normalizar_rut` / `rut_valido`: RUT chileno canónico `cuerpo-DV`, validado con
  el dígito verificador módulo 11 (algoritmo A-RUT). La llave FUERTE del cruce solo
  usa RUTs válidos; los inválidos caen al respaldo por nombre.
- `normalizar_nombre`: nombre normalizado (sin tildes, minúsculas, sin sufijos
  societarios) para el match de respaldo, SOLO exacto/inequívoco. Jamás asociar por
  similitud difusa (lección Zsabesky, docs/dev/18).

Este módulo no toca Notion; lo consume `reconciliar.py`.
"""
from __future__ import annotations
import re
import unicodedata

try:
    from rapidfuzz import fuzz, process
    TIENE_RAPIDFUZZ = True
except ImportError:                      # el backend puede correr sin fuzzy
    TIENE_RAPIDFUZZ = False

# Sufijos de forma legal que se recortan del final del nombre para el match.
# Se comparan tras quitar puntos (S.A. -> sa, E.I.R.L -> eirl). NO incluir
# palabras que son parte del nombre (p. ej. "inversiones", "servicios").
_SUFIJOS_LEGALES = frozenset({"spa", "sa", "ltda", "limitada", "eirl"})


def normalizar_rut(raw: str | None) -> str | None:
    """Devuelve el RUT como `cuerpo-DV` (cuerpo sin ceros a la izquierda, DV en
    mayúscula), o `None` si la entrada no tiene forma de RUT. NO valida el DV
    (eso lo hace `rut_valido`). No loguea (PII)."""
    if not raw:
        return None
    s = re.sub(r"[^0-9kK]", "", raw).upper()
    if len(s) < 2:
        return None
    cuerpo, dv = s[:-1], s[-1]
    if not cuerpo.isdigit():
        return None
    cuerpo = cuerpo.lstrip("0") or "0"
    # Cuerpo plausible de RUT chileno: 6–9 dígitos. Fuera de rango = basura.
    if not (6 <= len(cuerpo) <= 9):
        return None
    return f"{cuerpo}-{dv}"


def _dv_modulo_11(cuerpo: str) -> str:
    """Dígito verificador de un cuerpo de RUT (solo dígitos), por módulo 11.
    Ciclo de multiplicadores 2,3,4,5,6,7,2,3,… de derecha a izquierda."""
    s, suma = 2, 0
    for d in reversed(cuerpo):
        suma += int(d) * s
        s = 2 if s == 7 else s + 1
    resto = 11 - (suma % 11)
    if resto == 11:
        return "0"
    if resto == 10:
        return "K"
    return str(resto)


def rut_valido(rut_norm: str | None) -> bool:
    """True si `rut_norm` (formato `cuerpo-DV` de `normalizar_rut`) tiene un DV
    correcto por módulo 11."""
    if not rut_norm or "-" not in rut_norm:
        return False
    cuerpo, _, dv = rut_norm.partition("-")
    if not cuerpo.isdigit():
        return False
    return _dv_modulo_11(cuerpo) == dv.upper()


def rut_llave(raw: str | None) -> str | None:
    """Conveniencia: normaliza y devuelve el RUT SOLO si es válido; si no, `None`.
    Es la llave fuerte del cruce (nunca se matchea por un RUT con DV inválido)."""
    norm = normalizar_rut(raw)
    return norm if rut_valido(norm) else None


def normalizar_nombre(raw: str | None) -> str:
    """Nombre normalizado para match exacto de respaldo: sin tildes, minúsculas,
    sin puntuación, espacios colapsados y sin sufijo societario final
    (SPA/SA/LTDA/LIMITADA/EIRL). Devuelve '' si la entrada es vacía."""
    if not raw:
        return ""
    # Descomponer y quitar diacríticos (á->a, ñ->n).
    s = unicodedata.normalize("NFKD", raw)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace(".", "")
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    tokens = s.split()
    while tokens and tokens[-1] in _SUFIJOS_LEGALES:
        tokens.pop()
    return " ".join(tokens)


_NOMBRES_CONTROL = frozenset({"reset_mes", "reset mes"})


def es_ruido(nombre: str | None) -> bool:
    """True si el 'nombre' es una fila de control/test/basura, no un cliente real:
    vacío, fila RESET_MES, fila de prueba ZZ_TEST, o un valor que es solo un RUT
    (sin ninguna letra). Estas filas se excluyen del reporte y de crear fichas."""
    n = (nombre or "").strip()
    if not n:
        return True
    low = n.lower()
    if low in _NOMBRES_CONTROL or low.startswith("zz_test") or low.startswith("zz test"):
        return True
    # Valor que es puramente un RUT/número (sin letras) → no es nombre de cliente.
    if not re.search(r"[a-zA-ZñÑ]", n) and normalizar_rut(n):
        return True
    return False


def candidatos_fuzzy(nombre_norm: str, universo: list[str], limite: int = 3,
                     umbral: int = 65) -> list[tuple[str, int]]:
    """Top candidatos de `universo` (nombres normalizados) más parecidos a
    `nombre_norm`, por `token_sort_ratio` (tolera orden de palabras y typos).
    Devuelve [(nombre_candidato, score 0–100), …] descendente, solo score ≥ umbral.
    Es SOLO para SUGERIR; jamás liga solo (lo confirma un humano). Si rapidfuzz no
    está instalado devuelve [] (el flujo cae a la cola de revisión manual)."""
    if not TIENE_RAPIDFUZZ or not nombre_norm or not universo:
        return []
    res = process.extract(nombre_norm, universo, scorer=fuzz.token_sort_ratio, limit=limite)
    return [(cand, int(score)) for cand, score, _ in res if score >= umbral]
