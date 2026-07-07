# 06 · Stack técnico (recomendación · junio 2026)

> Documento dedicado (aplica el principio de granularidad de la decisión **D3**: un tema por archivo, sin sobrecargar). Desarrolla la decisión **D10** de [`05-decisiones-y-preguntas.md`](05-decisiones-y-preguntas.md). La recomendación está contrastada con prácticas vigentes del mercado a junio de 2026; fuentes al final.

## Criterios que el stack debe cumplir

Derivados de las decisiones ya tomadas:

- **100% data-driven y determinista** — el cálculo es matemático, no un LLM (D1).
- **Preciso y auditable** — el dinero no admite errores de redondeo.
- **Multiempresa desde el MVP** (D6).
- **Ingesta de CSV y XLSX** exportados del SII (D7).
- **Simple primero** — MVP funcional sin sobre-ingeniería (D8).
- **Mejores prácticas vigentes** (D10).

## Recomendación por capa

| Capa | Herramienta | Por qué |
|------|-------------|---------|
| Lenguaje | **Python 3.12+** | Estándar de facto para datos tabulares y cálculo; ecosistema más rico para este dominio. |
| Entorno y dependencias | **uv** | Reemplaza pip+venv+poetry; instala en ~100 ms lo que pip hacía en 30 s; lockfile reproducible; configuración única en `pyproject.toml`. |
| Lint y formato | **Ruff** | Reemplaza black+flake8+isort; lintea un repo de 100k líneas en ~200 ms; incluye reglas de seguridad (grupo `S`/Bandit). |
| Tipado | **mypy --strict** | Base correcta para producción; atrapa errores que el tipado básico no ve. (`ty`, de Astral, es la alternativa Rust 10–60× más rápida, aún en beta.) |
| DataFrames e ingesta | **Polars** (primario) | Moderno, multihilo, API explícita y tipada; tendencia 2026. **pandas** es alternativa 100% válida (ver abajo). |
| Lectura XLSX / CSV | **Polars** (motor `calamine`) u **openpyxl** | Leen los Excel del SII; CSV es nativo. |
| Validación de datos | **Pandera** + **Pydantic v2** | Pandera valida el esquema de los DataFrames; Pydantic valida modelos y configuración. Es el motor del control de anomalías (ver D9). |
| Aritmética de dinero | **`decimal.Decimal`** | Precisión exacta con redondeo controlado. **Nunca `float`** para impuestos. |
| Pruebas | **pytest** (+ pytest-cov) | *Golden test* que reproduce el resultado de `CLIENTE1` ($3, remanente −$158.117). |
| Lectura del F29 (PDF) | **pdfplumber** / **pypdf** | Solo si se necesita extraer estructura/códigos de `F29.pdf`. |

## Punto crítico: el dinero NO se calcula con `float`

Esto materializa la decisión D1 (precisión y credibilidad):

- El peso chileno (CLP) es una **moneda de pesos enteros** (sin centavos), así que los montos finales del F29 son **números enteros**.
- Pero los **cálculos intermedios** suman muchas filas y aplican porcentajes — por ejemplo: `PPM = BI × tasa` (BI = Σ neto + exento de las ventas; tasa de la casilla 115, ej. 0,125%). Hacer eso con `float` introduce errores de redondeo inaceptables en un contexto tributario.
- **Práctica recomendada:** ejecutar la aritmética tributaria con `decimal.Decimal` y redondear a peso entero con una regla de redondeo explícita. 
- **Patrón con DataFrames:** Polars/pandas trabajan en `float`/`int` por defecto. Por eso se usa el DataFrame para **ingerir, contar y agrupar** los documentos, y la **aritmética final del impuesto** se hace en Python puro con `Decimal` sobre los totales.

## La validación de datos ES el control de anomalías (liga con D9)

La decisión D9 exige "revisar que no haya fluctuaciones, anomalías o falta de datos" y que el remanente histórico se mantenga dentro de un margen pequeño respecto al del SII. Eso se implementa con validación de esquema:

- **Pandera** define el "contrato" del libro de compras/ventas: columnas obligatorias, tipos correctos, rangos válidos (montos ≥ 0), sin nulos. Si un archivo del SII llega incompleto o raro, **se detecta en la ingesta**, no en el resultado final.
- Sobre esa base se añade la **regla del remanente** (D9): comparar el valor del SII contra el histórico reajustado y marcar la diferencia si supera el margen acordado.

## pandas vs Polars: por qué Polars (con honestidad)

- **Tendencia 2026:** cerca de la mitad de los equipos de datos ya migraron a Polars o lo están evaluando; es 5–30× más rápido, multihilo por defecto y con una API más explícita.
- **Pero para AuditAI el volumen es pequeño:** un libro mensual de una pyme son cientos o miles de filas, así que el rendimiento **no es el factor decisivo** — pandas funcionaría igual de bien y es más familiar.
- **Recomendación:** como es un proyecto nuevo (sin código heredado) y buscas mejores prácticas, **Polars** es la elección moderna. Si el equipo domina pandas y prefiere ir sobre seguro, es un *fallback* perfectamente válido. **Pandera y Pydantic soportan ambos**, así que la decisión no bloquea nada.

## Forma del MVP y qué NO agregar todavía (YAGNI)

Coherente con D8 (simple primero):

- **MVP = librería de cálculo + CLI** que lee CSV/XLSX, calcula el F29 y emite el resultado + informe de auditoría. **Sin web ni base de datos al inicio.**
- **Multiempresa (D6)** se resuelve en el **modelo de datos**, no en infraestructura: cada insumo lleva un identificador de empresa y el cálculo se ejecuta por empresa-período. No requiere servidor ni base de datos en el MVP.
- Cuando se justifique persistencia o multiusuario, el estándar 2026 es **FastAPI + PostgreSQL + SQLAlchemy 2.0**. Queda **postergado** hasta que el motor determinista funcione y esté verificado.

## Resumen en una línea

> Python 3.12+ con **uv + Ruff + mypy** (tooling), **Polars + Pandera/Pydantic** (datos y validación), **`Decimal`** (dinero) y **pytest** (golden tests). Librería + CLI primero; web y base de datos después.

## Fuentes

- [Python Project Setup 2026: uv + Ruff + Ty + Polars — KDnuggets](https://www.kdnuggets.com/python-project-setup-2026-uv-ruff-ty-polars)
- [Modern Python Tooling 2026: uv, Ruff, mypy — softaims](https://softaims.com/blog/modern-python-tooling-uv-ruff-mypy-2026)
- [Polars vs Pandas in 2026 — VRLA Tech](https://vrlatech.com/polars-vs-pandas-in-2026-which-python-dataframe-library-should-you-use/)
- [Polars vs Pandas: Why Data Engineers Are Switching in 2026 — PC The Data Engineer](https://pushpjeet.com/polars-vs-pandas-data-engineers-2026/)
- [Beyond Pandas: Modern Python Data Science Stack (Pandera/Pydantic) — USDSI](https://www.usdsi.org/data-science-insights/beyond-pandas-what-next-for-modern-python-data-science-stack)

---

**Anterior:** [`05-decisiones-y-preguntas.md`](05-decisiones-y-preguntas.md) · **Volver al** [`README`](README.md)
