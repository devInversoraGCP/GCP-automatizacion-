"""Motor de cálculo F29 (spike) — aritmética exacta según docs/dev/17.

Reglas duras del proyecto:
- Todo en Decimal, nunca float (regla de dinero, doc 17 §4).
- Redondeo a peso entero UNA vez por casilla, regla SII: >= 0,5 sube (ROUND_HALF_UP).
- Función determinista pura: mismas entradas -> mismas salidas. La IA no participa.
- Sin valores del golden test embebidos (regla de no-trampa del spike).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

CERO = Decimal("0")


def peso(x: Decimal) -> int:
    """Redondeo a peso entero con la regla del SII (mitad sube)."""
    return int(x.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@dataclass
class EntradasF29:
    """Variables de entrada, con la convención de signos de la spec (doc 17 §3)."""

    p1_debito: Decimal            # >= 0 · Σ Monto IVA pestaña VENTA (NC restan)
    p2_credito: Decimal           # <= 0 · −Σ IVA Recuperable pestaña COMPRA (NC restan)
    p3_remanente: Decimal         # <= 0 · −|casilla 504| (0 si no hay remanente)
    bi_ppm: Decimal               # >= 0 · Σ (Monto Neto + Monto Exento) pestaña VENTA
    tasa_ppm: Decimal             # fracción: 0,125 % => Decimal("0.00125") (casilla 115)
    ret_honorarios: Decimal = CERO    # >= 0 · casilla 151
    ret_imp_unico: Decimal = CERO     # >= 0 · casilla 48
    n_docs_venta: int = 0             # casilla 503
    n_docs_compra: int = 0            # casilla 519

    def validar(self) -> list[str]:
        """Propiedades de la spec. Devuelve advertencias (no aborta: el humano decide)."""
        avisos = []
        if self.p1_debito < 0:
            avisos.append(f"P1 negativo ({self.p1_debito}): inusual, revisar notas de crédito")
        if self.p2_credito > 0:
            avisos.append(f"P2 positivo ({self.p2_credito}): debe entrar en negativo")
        if self.p3_remanente > 0:
            avisos.append(f"P3 positivo ({self.p3_remanente}): debe entrar en negativo")
        if self.tasa_ppm < 0 or self.tasa_ppm > Decimal("0.03"):
            avisos.append(f"Tasa PPM fuera de rango típico: {self.tasa_ppm}")
        return avisos


@dataclass
class ResultadoF29:
    entradas: EntradasF29
    p4_iva_determinado: Decimal = CERO
    ppm: int = 0
    p5_otros: Decimal = CERO
    p6_total: Decimal = CERO
    casillas: dict[int, int] = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)


def calcular(e: EntradasF29) -> ResultadoF29:
    """Ejecuta P4 -> P6 y mapea a casillas del F29 (doc 17 §4, paso 6)."""
    r = ResultadoF29(entradas=e, avisos=e.validar())

    # 6.1 · P4 = P1 + P2 + P3 (aritmética exacta)
    r.p4_iva_determinado = e.p1_debito + e.p2_credito + e.p3_remanente

    # 6.2 · PPM (casilla 62) = round(BI × tasa), única vez, regla SII
    r.ppm = peso(e.bi_ppm * e.tasa_ppm)

    # 6.3 · P5 = PPM + retenciones (siempre >= 0)
    r.p5_otros = Decimal(r.ppm) + e.ret_honorarios + e.ret_imp_unico

    # 6.4 · P6: regla condicional — el remanente NUNCA rebaja los otros impuestos
    if r.p4_iva_determinado > 0:
        r.p6_total = r.p4_iva_determinado + r.p5_otros
    else:
        r.p6_total = r.p5_otros

    # Propiedad invariante: P6 >= P5 siempre
    assert r.p6_total >= r.p5_otros, "violación de invariante: P6 < P5"

    # 6.5 · Mapeo a casillas (solo las del caso núcleo)
    c: dict[int, int] = {}
    c[502] = peso(e.p1_debito)                 # débito fiscal
    c[503] = e.n_docs_venta                    # nº documentos de venta
    c[538] = c[502]                            # total débitos (caso simple)
    c[520] = peso(-e.p2_credito)               # crédito fiscal (positivo en el form)
    c[519] = e.n_docs_compra                   # nº documentos de compra
    c[504] = peso(-e.p3_remanente)             # remanente mes anterior (positivo en el form)
    c[537] = c[520] + c[504]                   # total créditos = crédito + remanente
    if r.p4_iva_determinado > 0:
        c[89] = peso(r.p4_iva_determinado)     # IVA a pagar
        c[77] = 0
    else:
        c[89] = 0
        c[77] = peso(-r.p4_iva_determinado)    # remanente al mes siguiente
    c[62] = r.ppm                              # PPM
    c[151] = peso(e.ret_honorarios)            # retención honorarios
    c[48] = peso(e.ret_imp_unico)              # retención impuesto único
    c[595] = c[62] + c[151] + c[48]            # subtotal otros impuestos
    c[91] = peso(r.p6_total)                   # total a pagar en plazo
    r.casillas = c
    return r


def formatear(r: ResultadoF29) -> str:
    """Salida legible en pesos chilenos. No imprime nada sensible."""
    def clp(n) -> str:
        s = f"{int(n):,}".replace(",", ".")
        return f"−${s[1:]}" if int(n) < 0 else f"${s}"

    e = r.entradas
    lineas = [
        "── Entradas ────────────────────────────",
        f"  P1  débito (ventas)        {clp(peso(e.p1_debito)):>14}   [{e.n_docs_venta} docs]",
        f"  P2  crédito (compras)      {clp(peso(e.p2_credito)):>14}   [{e.n_docs_compra} docs]",
        f"  P3  remanente anterior     {clp(peso(e.p3_remanente)):>14}",
        f"  BI  base imponible PPM     {clp(peso(e.bi_ppm)):>14}",
        f"  tasa PPM                   {e.tasa_ppm * 100}%",
        "── Cálculo ─────────────────────────────",
        f"  P4  IVA determinado        {clp(peso(r.p4_iva_determinado)):>14}"
        + ("   → paga IVA (casilla 89)" if r.p4_iva_determinado > 0 else "   → saldo a favor (casilla 77)"),
        f"  PPM (casilla 62)           {clp(r.ppm):>14}",
        f"  P5  otros impuestos        {clp(peso(r.p5_otros)):>14}",
        f"  P6  TOTAL A PAGAR          {clp(peso(r.p6_total)):>14}",
        "── Casillas F29 ────────────────────────",
        "  " + " · ".join(f"[{k}]={clp(v)}" for k, v in sorted(r.casillas.items())),
    ]
    if r.avisos:
        lineas += ["── ⚠ Avisos ────────────────────────────"] + [f"  {a}" for a in r.avisos]
    return "\n".join(lineas)
