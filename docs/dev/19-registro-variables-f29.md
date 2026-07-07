# 19 · Registro maestro de variables del F29 (extraído de `F29.pdf`)

> **El registro total de todas las variables, parámetros y métricas** que el motor puede tener que mapear por cliente, extraído **literalmente** del [`F29.pdf`](../../F29.pdf) (formulario oficial SII, V 1.10 Internet — la fuente de verdad madre, D24). Solicitud del usuario (05-jul-2026): tener en una tabla nuestra el universo completo de casillas para el mapeo por cliente de GCP.

## 1 · El archivo de datos

**📄 [`data/f29-registro-variables.csv`](data/f29-registro-variables.csv)** — separador `;`, UTF-8 con BOM (abre directo en Excel).

| Columna | Qué contiene |
|---|---|
| `pagina` | Página del PDF (1–3). |
| `linea_f29` | Nº de línea del formulario (1–144; `cab` = cabecera de identificación). |
| `codigo` | **Nº de la casilla** (el "código" del SII). |
| `glosa_literal_pdf` | Etiqueta **textual** de esa línea en el PDF. |
| `columna_rol` | Qué columna/rol ocupa la casilla dentro de su línea (cantidad de documentos, débito, crédito, base imponible, tasa, remanente, total…). |
| `signo` | `+` / `-` / `=` según el propio formulario (cómo opera en la suma de su bloque). |
| `seccion` | Bloque del F29 (Genera débito, Con derecho a crédito, PPM, ILA, Cambio de sujeto, Créditos especiales, Totales…). |
| `relevancia_motor_gcp` | **Para qué la usa el motor**: `P1…P6` (núcleo, con las casillas ancla marcadas), `identificación`, `informativo`, o `caso especial · <cuál>`. |

## 2 · Los números

- **260 variables** en total, cubriendo **las 144 líneas** del F29 (verificado: todos los números de casilla presentes en el PDF están en el CSV, sin faltantes ni inventados).
- **59 variables del núcleo** que el motor toca en el caso típico:

| Grupo | Nº | Casillas ancla |
|---|---|---|
| Identificación | 6 | `15` período · `3` RUT · `7` folio · `1`/`2`/`5` nombre |
| P1 · Débito (ventas) | 23 | `502`/`503` facturas · `509`/`510` NC (−) · **`538` = TOTAL DÉBITOS** |
| P2 · Crédito (compras) | 17 | `519`/`520` facturas · `527`/`528` NC (−) · `534`/`535` DIN · **`537` = TOTAL CRÉDITOS** |
| P3 · Remanente que entra | 1 | **`504`** (de la propuesta; puede no estar ⇒ 0) |
| P4 · IVA determinado | 2 | **`89`** (paga) / **`77`** (remanente que sale) |
| P5 · PPM y retenciones | 11 | **`563` = BI** · **`115` = TASA** · **`62` = PPM** · **`151`** honorarios · **`48`** imp. único · **`595`** subtotal |
| P6 · Totales | 5 | **`91` = TOTAL A PAGAR EN PLAZO** · `92`/`93` recargos · `94` con recargo · `547` total determinado |
| Informativo (exentos/sin derecho) | 18 | `585`/`20` exportaciones · `586`/`142` exentos del giro (el **Monto Exento entra a la BI del PPM**) |

- **176 variables de casos especiales**, agrupadas por régimen — se activan **solo si el perfil del cliente lo tiene**: postergación de IVA (~30), ILA bebidas Art. 42 (~27), cambio de sujeto (~18), créditos especiales y sus remanentes (~24), diésel Leyes 18.502/19.764/20.765 (12), Impuesto Adicional Art. 37 (9), mineros/royalty (15), tributación simplificada (3), 27 bis / 27 ter, Zona Franca, condonación, etc.

## 3 · Cómo se usa para el mapeo por cliente

1. **Todos los clientes** mapean: identificación + P1 + P2 + P3 + P4 + P6 (el núcleo IVA) — datos que salen del RCV y la propuesta ([`17`](17-especificacion-literal-calculo-f29.md) §4).
2. **Según perfil** (la matriz de selección de [`17`](17-especificacion-literal-calculo-f29.md) §2): PPM (`563`/`115`/`62`), honorarios (`151`), trabajadores (`48`), y cada **caso especial** activa su grupo de casillas del CSV (filtrar por `seccion`).
3. El **diccionario definitivo** (tarea 1.4 del [`11`](11-checklist-maestro.md)) se construye **sobre este registro**: este CSV es el "qué existe"; falta enriquecerlo con el contraste contra las [instrucciones oficiales del F29](https://www.sii.cl/servicios_online/instrucciones_f29_20241112.pdf).

## 4 · Método de extracción (trazable)

Extracción por **coordenadas** (pypdf, `visitor_text`): cada etiqueta se asoció a su Nº de línea por posición vertical, y las casillas por el **orden de los campos del formulario** (que sigue el orden de las líneas). Verificación cruzada contra los pantallazos reales del F29 web aportados por el usuario (líneas 1–18 coinciden 1:1). Script: reproducible desde `F29.pdf`.

## 5 · ⚠️ Flags a verificar con Carlos (6 casillas)

Pareos que el PDF no deja 100% inequívocos — marcados con ⚠️ en el CSV:

- **`50` (línea 59):** el PDF repite la glosa "Certificado Imputación Art. 27 ter inc. 1º" en las líneas 58 y 59 — confirmar la glosa real de la 59.
- **`755`/`756` (línea 50):** pareo exacto de las dos casillas de "Postergación pago del IVA".
- **`750` (línea 69):** su columna exacta dentro de la línea del PPM.
- **`548` (línea 88) y `541` (línea 90):** signos según el PDF parecen invertidos respecto de la intuición (reintegro −, devolución +) — confirmar.

## 6 · Pendientes

- [ ] Contrastar glosas/códigos contra las instrucciones oficiales del SII (enriquecer el CSV con columna `verificado_oficial`).
- [ ] Resolver los 6 flags de §5 con Carlos.
- [ ] Cuando exista el modelo de datos (Fase 2), este CSV se convierte en la **tabla de referencia** `f29_codigos` del motor.

---

**Anterior:** [`18-integracion-impuesto-unico-imposiciones.md`](18-integracion-impuesto-unico-imposiciones.md) · **Volver al** [`README`](README.md)
