# 17 · Especificación literal del cálculo del F29 — selección de variables + ejemplo trabajado

> **Documento de planificación profunda del Frente B.** Aterriza el motor de cálculo al **nivel literal**: qué códigos del F29 existen, **cómo se eligen según el caso** de cada cliente, y un **ejemplo real trabajado de punta a punta** (datos → extracción → cálculo → código). Es la etapa más crítica: aquí se define que el cálculo sea **correcto, exacto y trazable**.
>
> **Fuente de verdad:** `F29.pdf` (formulario oficial SII, extraído literalmente — ver §1). D24. 🧮 = determinista · 🔒 = credenciales/PII.
> **Estado:** ✅ **VALIDADA POR LOS EXPERTOS DE GCP** (feedback P1–P6 recibido vía el usuario, 04/05-jul-2026) · **no se calcula en producción todavía**. Este documento es la **referencia operativa del motor**: las rutas de extracción del §3 ("Cómo se obtiene") son las reales del SII, corregidas por los expertos, y el **§4 contiene el ALGORITMO LITERAL completo P1 → P6, clic a clic**. Correcciones clave incorporadas: pestañas **«VENTA»/«COMPRA»** del RCV (no "IEV/IEC" como sección) · remanente = casilla **504** de la propuesta (no 77, que es el de salida) · **BI del PPM = neto + exento** (no `débito ÷ 0,19`) · **tasa PPM = casilla 115** de la propuesta · honorarios = informe anual, columna «Retención de terceros» · **notas de crédito restan en ambos lados**.

---

## 1 · La tabla madre: estructura real del F29 (extraída del `F29.pdf`)

El F29 tiene **144 líneas** numeradas; cada línea tiene una o más **casillas (códigos)**. Extraído del PDF oficial, se organiza en bloques. **No todos aplican a todos los clientes** — de ahí la "elección de variables" (§2).

| Bloque | Líneas F29 | Códigos ancla (confirmados en el PDF) | Qué contiene |
|---|---|---|---|
| **A · Débitos (ventas)** | 7 – 23 | `503`/`502` (cant/débito facturas emitidas) · `509`/`510` (notas de crédito emitidas, −) · **`538` = TOTAL DÉBITOS** | IVA que la empresa cobró en sus ventas. |
| **B · Créditos (compras)** | 24 – 49 | `519`/`520` (cant/crédito facturas recibidas del giro) · `504` (**remanente crédito fiscal mes anterior**) · DIN importaciones (doc 914) · **`537` = TOTAL CRÉDITOS** | IVA que la empresa pagó en compras + remanente arrastrado. |
| **C · IVA determinado** | 50 | `89` (**IVA determinado**, si débitos > créditos) · `77` (**remanente para el período siguiente**, si créditos > débitos) | Resultado del IVA del mes. |
| **D · PPM y retenciones** | 59 – 79 | `62` (**PPM neto determinado**) · `151` (retención honorarios) ⚠️ · `48` (ret. impuesto único trabajadores) ⚠️ · `595` (subtotal impuesto determinado) | Otros impuestos ajenos al IVA. |
| **E · Impuestos adicionales / especiales** | 21, 44–48, 68–79, 92–140 | ILA (bebidas), específico diésel, cambio de sujeto, 27 bis, etc. | **Solo si el cliente los tiene.** La gran mayoría quedan en cero. |
| **F · Totales** | 141 – 144 | **`91` = TOTAL A PAGAR EN PLAZO LEGAL** · `92` (+IPC) · `93` (+intereses/multas) · `94` (total con recargo) | Lo que finalmente se paga. |

> 📌 **Hallazgo al leer el F29 literal:** el remanente usa **dos códigos distintos**: `504` (el que viene del mes anterior, **entra** en créditos) y `77` (el que **sale** al mes siguiente, si quedó saldo a favor). Nuestra doc previa los trataba como uno solo (`77`). **Corrección aplicada aquí.**

---

## 2 · El proceso de elección de variables (por caso) 🧮

El F29 tiene ~140 casillas, pero **un cliente típico usa 8–12**. El motor **no llena todo**: por cada bloque, decide si aplica según los **datos y el perfil del cliente**. La regla es determinista:

```text
# A-SELECCIÓN · qué códigos activa cada cliente-período

entrada: perfil_cliente (Notion) + documentos del período (SII) + RRHH (Notion)

# ── Bloque A · Débitos ──────────────────────────────────────
si hay documentos de venta en el RCV:
    activar 502/503 (y 509/510 si hay notas de crédito) → 538
sino:
    538 = 0   # cliente sin ventas del mes

# ── Bloque B · Créditos ─────────────────────────────────────
si hay documentos de compra en el RCV:
    activar 519/520 (y DIN 914 si hay importaciones) → 537
si la propuesta del F29 trae la casilla 504:        # puede no estar
    activar 504 (remanente del mes anterior, entra como crédito)

# ── Bloque C · IVA determinado ──────────────────────────────
iva_det = débitos(538) − créditos(537)          # incluye 504
si iva_det > 0:  activar 89  (paga IVA)
sino:            activar 77  (arrastra |iva_det| al mes siguiente)

# ── Bloque D · PPM y retenciones ────────────────────────────
si perfil_cliente.tiene_ppm:
    BI = Σ(Monto Neto + Monto Exento) de VENTA    # NC restan
    activar 62 = BI × tasa_ppm                    # tasa = casilla 115 de la propuesta
si hay boletas de honorarios RECIBIDAS:           # empresa que paga profesionales
    activar 151 = «Retención de terceros» (informe anual, fila del mes anterior)
si RRHH[cliente].impuesto_único > 0:              # empresa con trabajadores
    activar 48 = monto de impuesto único (de Notion)

# ── Bloque E · Adicionales/especiales ───────────────────────
por cada régimen especial marcado en el perfil (27 bis, ILA, diésel, cambio sujeto…):
    activar sus códigos con la regla específica
# la inmensa mayoría NO aplica → quedan en cero

# ── Bloque F · Totales ──────────────────────────────────────
subtotal(595) = suma del bloque D
91 = (89 si iva_det>0 sino 0) + 595              # regla condicional P6
salida: {códigos_activos: valor}, remanente_siguiente(77)
```

**El "perfil del cliente"** (qué régimen tiene, si paga honorarios, si tiene trabajadores, tasa de PPM, casos especiales) vive en la **base central de Notion** y es lo que parametriza la selección. Por eso el Frente A (base robusta) es prerrequisito del Frente B.

---

## 3 · Datos que se requieren (checklist completo por fuente) 🔒

Para calcular el F29 de un cliente-período se necesita **exactamente** esto:

### 3.1 · SII — RCV Ventas (IEV) → bloque A
| Dato | Campo | Uso |
|---|---|---|
| Tipo de documento | `TpoDoc` | Clasificar (factura 33, comprobante 48, NC 61…) |
| Folio | `NroDoc` | Identificar/trazar cada documento |
| Fecha | `FchDoc` | Filtrar por período |
| Monto neto | `MntNeto` | **BI del PPM** (columna «Monto Neto», junto con el exento) |
| Monto IVA | `MntIVA` | **Débito fiscal (P1 → 502/538)** |
| Monto exento | `MntExe` | No suma débito, pero **SÍ suma a la BI del PPM** (columna «Monto Exento») |

> **📍 Cómo se obtiene — ruta real en el SII (validado con los expertos de GCP, jul-2026).**
> Iniciar sesión con las credenciales del cliente → **Servicios online → Impuestos mensuales → Registro de Compras y Ventas** → abrir el RCV (`https://www4.sii.cl/consdcvinternetui/#/index`) → fijar el **período = el mes anterior al actual** (declaración de julio 2026 ⇒ período **junio 2026**) → botón **Consultar** → pestaña **«VENTA»** → sumar la columna **«Monto IVA»** de **todas las filas** = **P1** (débito).
> ⚠️ La sección correcta es la pestaña **«VENTA»**, **no** "Información Electrónica de Ventas" (corrige una hipótesis previa errónea). En la descarga, la columna «Monto IVA» corresponde al campo `MntIVA`.
> 🔻 **Notas de crédito:** las filas de nota de crédito (devoluciones/anulaciones) **se restan** del total de P1. *(Regla simétrica en compras: ver §3.2.)*

### 3.2 · SII — RCV Compras (IEC) → bloque B
| Dato | Campo | Uso |
|---|---|---|
| `TpoDoc`, `NroDoc`, `FchDoc` | | Clasificar/trazar/filtrar |
| RUT proveedor | `RUTDoc` | Trazabilidad |
| Monto IVA recuperable | `MntIVA` | **Crédito fiscal (P2 → 520/537)** |
| Monto IVA **no** recuperable | `MntIVANoRec` (+`CodIVANoRec` 1–9) | **NO** suma al crédito |
| IVA uso común | `IVAUsoComun` | Proporcionalidad (caso avanzado) |

> **📍 Cómo se obtiene — ruta real en el SII (validado con los expertos de GCP, jul-2026).**
> **Mismo camino que P1** (Servicios online → Impuestos mensuales → Registro de Compras y Ventas → abrir el RCV → período = el mes anterior al actual → **Consultar**), pero se entra a la pestaña **«COMPRA»** y se suma la columna **«IVA Recuperable»** de **todas las filas** = **P2** (crédito).
> ⚠️ La sección es la pestaña **«COMPRA»** (no "Información Electrónica de Compras") y la columna clave es **«IVA Recuperable»** (campo `MntIVA` recuperable). El **no recuperable** (`MntIVANoRec`) **no** suma al crédito.
>
> 🔻 **Notas de crédito:** igual que en ventas (§3.1), las filas de nota de crédito recibidas de proveedores **se restan** del total de P2 (crédito). La regla de notas de crédito es **simétrica**: restan en P1 (ventas) y en P2 (compras).

### 3.3 · SII — Boletas de honorarios → bloque D (casilla 151)
Boletas **recibidas** (la empresa retiene al pagar profesionales), Ley 21.133. Boletas **emitidas** solo si el cliente es el profesional (su propio PPM).

> **📍 Cómo se obtiene — ruta real en el SII (validado con los expertos de GCP, jul-2026).**
> Servicios online → **Boleta de honorarios electrónica** → Emitir boleta → **Consulta sobre la boleta electrónica** → **Consultar boletas recibidas** → consulta en modo **año** (p. ej. 2026). Aparece el **«Informe anual de boletas de honorarios electrónicas recibidas»** (una fila por mes: emisiones vigentes/anuladas, honorario bruto, retención de terceros, total líquido). Se toma la **fila del mes anterior al actual** (declarando en julio 2026 ⇒ fila **JUNIO**) y se extrae el valor de la columna **«Retención de terceros»** = `ret_honorarios` → casilla **151**.
> ℹ️ Los totales del informe **no** consideran los montos de boletas anuladas.

### 3.4 · SII — Remanente → casilla 504
Remanente crédito fiscal del **mes anterior**, ya **reajustado por UTM** por el propio SII. Es P3 (entra en negativo). Control anti-anomalía D9/D13.

> **📍 Cómo se obtiene — ruta real en el SII (validado con los expertos de GCP, jul-2026).**
> Se lee de la **propuesta del F29 del período que se declara**: Servicios online → Impuestos mensuales → **Declaración mensual (F29)** → **Declarar IVA (F29)** → dejar el mes **predeterminado** y **Aceptar** → **Continuar** → marcar **«Confirmar que no hay información adicional a incorporar»** → **«Confirmar que no debo completar»** → aparece la pantalla de **propuesta** → botón **«Ingresar aquí»** → se abre el **F29 propuesto** y se lee la casilla **504**.
> ⚠️ **La casilla 504 puede aparecer o no.** Si trae valor ⇒ la empresa **arrastra remanente** (P3 = ese valor, negativo). Si **no** aparece ⇒ **no hay remanente** y **P3 = 0**.
> 🔁 Equivalencia: la 504 de este período corresponde a la 77 (remanente al período siguiente) del período anterior, ya reajustada — por eso se lee directamente de la propuesta y no se recalcula.

### 3.5 · Notion — RRHH (`RRHH <Mes>`) → casilla 48 🔒
El **único dato fuera del SII**. Columnas: **`IMPUESTO ÚNICO`** (monto a declarar) y **`MONTO IMPOSICIONES|`** (referencia). Se **transcribe**, no se calcula.

> 🚨 **Brecha detectada (02-jul-2026, reportada por el usuario):** la base central `General Customers Data - AuditAI` **no tiene** las columnas `IMPUESTO ÚNICO` ni `MONTO IMPOSICIONES|`. Hay que **integrarlas con urgencia** para las 331 filas, rescatándolas desde Notion (pista: `Contable Mayo` y las bases `RRHH <Mes>` de todos los meses tienen la mayoría de estos datos). Plan de integración: ver [`18-integracion-impuesto-unico-imposiciones.md`](18-integracion-impuesto-unico-imposiciones.md).

### 3.6 · Config / Notion — parámetros por cliente
- **Tasa de PPM (casilla 115):** es **distinta por cliente**. Se extrae del **F29 propuesto** (misma ruta que el remanente 504, ver §3.4): en la subsección **PPM**, columna **«Tasa»**, casilla **115**.
- **Régimen** y casos especiales (27 bis, exportador, IVA postergado, sin movimiento).
- **Tasas vigentes** (IVA 19%, honorarios Ley 21.133 del período) → en config, no hardcodeadas.

---

## 4 · ALGORITMO LITERAL del cálculo, paso a paso (P1 → P6) 🧮

> Transcripción **literal y operativa** del procedimiento dictado por los expertos de GCP (jul-2026), clic a clic. Esto es exactamente lo que el motor (o un humano) ejecuta para calcular el F29 de un cliente.
> **Convención de período:** siempre se trabaja con el **mes anterior al actual** (x−1). Ejemplo: declarando en **julio 2026**, el período es **junio 2026**.

### Paso 0 · Entrar al SII
1. Ir a `www.sii.cl` e **iniciar sesión** con las credenciales del cliente (`RUT` + `CLAVE SII`, desde la base central 🔒).
2. Ir a **Servicios online**.

### P1 · Débito fiscal (IVA de las ventas) → casillas `502`/`503`/`538`
1. Servicios online → **Impuestos mensuales**.
2. Botón **«Registro de compras y ventas»** → ingresar al Registro de Compras y Ventas (`https://www4.sii.cl/consdcvinternetui/#/index`).
3. Fijar el **período = mes anterior al actual** (x−1; ej. junio 2026).
4. Presionar el botón **«Consultar»**.
5. Ir a la sección **«VENTA»**.
6. **Sumar la columna «Monto IVA» de todas las filas.** Si una fila es **nota de crédito, se resta**.
7. Esa sumatoria es **P1** (≥ 0).

### P2 · Crédito fiscal (IVA de las compras) → casillas `519`/`520`/`537`
1. **Mismo algoritmo que P1** (mismo RCV, mismo período, ya consultado).
2. Ir a la sección **«COMPRA»**.
3. **Sumar la columna «IVA Recuperable» de todas las filas.** Si una fila es **nota de crédito, se resta**.
4. Esa sumatoria es el crédito del mes; entra al cálculo como **P2 = −(sumatoria)** (≤ 0).

### P3 · Remanente del mes anterior (de la propuesta del SII) → casilla `504`
1. Servicios online → **Impuestos mensuales** → **Declaración mensual (F29)** → **Declarar IVA (F29)**.
2. **Seleccionar el mes que sale predeterminado** y presionar **Aceptar**.
3. Presionar el botón **Continuar**.
4. Marcar la celda **«Confirmar que no hay información adicional a incorporar»**.
5. Presionar el botón **«Confirmar que no debo completar»**.
6. Aparece la pantalla **«PROPUESTA DE DECLARACIÓN FORMULARIO 29»** (texto tipo: *"Estimado(a) [razón social], [RUT], tienes una declaración con pago de impuestos por $[monto] correspondiente al periodo tributario [MM-AAAA]. Revisa el detalle de tu propuesta…"*).
7. Presionar el botón **«Ingresar aquí»** → se abre la **Declaración de Formulario 29 (F29)** propuesta (la tabla con las casillas).
8. Buscar la casilla **`504` «Remanente Crédito Fiscal mes anterior»**:
   - **Si tiene valor** ⇒ la empresa **sigue arrastrando remanente** ⇒ `remanente_anterior` = ese valor ⇒ **P3 = −remanente_anterior**.
   - **Si no aparece** ⇒ **no tiene remanente** ⇒ **P3 = 0**.
9. El valor ya viene **reajustado por UTM** por el SII: se usa directo, **no se recalcula** (el control anti-anomalía D9/D13 corre aparte).

### P4 · IVA determinado (cálculo puro, sin fuente)
1. **`P4 = P1 + P2 + P3`** (P2 y P3 entran en negativo).
2. Lectura del signo:
   - **P4 > 0** ⇒ hay **IVA a pagar** este mes → casilla `89`.
   - **P4 ≤ 0** ⇒ hay **IVA remanente que queda para el próximo mes, a favor de la empresa** → casilla `77` = |P4|.

### P5 · Otros impuestos = `PPM + ret_honorarios + ret_impuesto_unico` → subtotal `595`

**P5.a · PPM = BI (base imponible) × TASA → casilla `62`**
- **Sacar la BI:** ir a **Impuestos mensuales** → **Registro de compras y ventas** → ingresar al RCV → período = **mes anterior al actual** → sección **«VENTA»** → **sumar las columnas «Monto Exento» y «Monto Neto» de todas las filas, restando las filas que son notas de crédito**. **Toda esa sumatoria es la base imponible.** *(Es la misma pantalla de P1: las tres columnas —Monto IVA, Monto Neto, Monto Exento— se leen en una sola pasada.)*
- **Sacar la TASA:** ⚠️ **no todos los clientes tienen la misma tasa.** Hacer el **mismo proceso que para el remanente (P3)** hasta abrir el F29 propuesto y, en esa misma tabla, en vez de la 504, **extraer la casilla `115`** — está en la **subsección PPM, columna «Tasa»**.
- **`PPM = BI × tasa`**, redondeado a peso entero.

**P5.b · ret_honorarios → casilla `151`**
1. Servicios online → **Boleta de honorarios electrónica** → **Emitir boleta** → **Consulta sobre la boleta electrónica** → **Consultar boletas recibidas**.
2. Consultar en modo **año** (ej. 2026).
3. Aparece el **«Informe anual de boletas de honorarios electrónicas recibidas»** (una fila por mes: emisiones vigentes/anuladas, honorario bruto, retención de terceros, retención contribuyente, total líquido).
4. Tomar la **fila del mes anterior al actual** (ej. **JUNIO** si estamos en julio 2026) y extraer el valor de la columna **«Retención de terceros»** = `ret_honorarios`.
5. ℹ️ Los totales del informe **no** consideran los montos de boletas anuladas.

**P5.c · ret_impuesto_unico → casilla `48`** 🔒
- **Se obtiene SOLAMENTE de Notion** (es el único dato fuera del SII): página **`RRHH <Mes>`** (ej. `RRHH JUNIO`), columnas **«IMPUESTO ÚNICO»** (el monto a declarar) y **«MONTO IMPOSICIONES|»** (referencia). Se **transcribe**, no se calcula.
- Integradas a la base central como rollups de `RRHH Origen` — ver [`18`](18-integracion-impuesto-unico-imposiciones.md).

**Cierre de P5:** `P5 = PPM + ret_honorarios + ret_impuesto_unico` (≥ 0).

### P6 · Total a pagar (regla condicional) → casilla `91`
- **Si P4 > 0:** `P6 = P4 + P5` — paga el IVA **más** los otros impuestos.
- **Si P4 ≤ 0:** `P6 = P5` — **no se paga IVA**; el saldo |P4| **se arrastra como remanente** al mes siguiente (casilla `77`), pero **PPM y retenciones se pagan igual** (nunca se anulan por el saldo a favor).

> 💡 **Nota de eficiencia para el motor:** P1, P2 y la BI del PPM salen de **una sola consulta al RCV** (pestañas VENTA y COMPRA); la 504 (remanente) y la 115 (tasa) salen del **mismo F29 propuesto**. En total son **3 visitas al SII** por cliente-período — RCV, propuesta del F29 e informe de boletas — más **1 lectura de Notion RRHH**.

---

## 5 · Ejemplo trabajado LITERAL: `CLIENTE1` · abril 2026 ✅

Caso real ya validado contra la propuesta del SII (*golden test*). Aquí, **variable por variable**: qué dato, de dónde sale, cómo se extrae y cómo se calcula, hasta el código F29.

### Paso 0 · Selección de variables (según §2)
Perfil de CLIENTE1: empresa con ventas afectas · con PPM (tasa 0,125%) · **sin** honorarios · **sin** trabajadores · con remanente arrastrado. → **Códigos que activan:** `502/503`, `538`, `519/520`, `537`, `504`, `89`/`77`, `62`, `595`, `91`. Todo el resto del F29 queda en **cero**.

### Paso 1 · Débito fiscal (bloque A → 502/538)
| | |
|---|---|
| **Dato** | IVA de las ventas del mes |
| **Fuente** | SII · RCV Ventas |
| **Extracción** | Abrir el RCV (Servicios online → Impuestos mensuales → Registro de Compras y Ventas), período = abril, pestaña **VENTA**; sumar la columna **Monto IVA** (`MntIVA`) de **todas las filas** |
| **Cálculo** | `P1 = Σ MntIVA = $462` (3 comprobantes de pago electrónicos, doc tipo 48) |
| **Código F29** | `503` = 3 (cantidad) · `502` = $462 · **`538` (total débitos) = $462** |

### Paso 2 · Crédito fiscal (bloque B → 520/537)
| | |
|---|---|
| **Dato** | IVA recuperable de las compras |
| **Fuente** | SII · RCV Compras |
| **Extracción** | Abrir el RCV, período = abril, pestaña **COMPRA**; sumar la columna **IVA Recuperable** (`MntIVA` recuperable; excluir `MntIVANoRec`) de las 11 filas |
| **Cálculo** | `P2 = −Σ MntIVA = −$260.143` |
| **Código F29** | `519` = 11 · `520` = $260.143 · **`537` (total créditos) = $260.143** |

### Paso 3 · Remanente mes anterior (bloque B → 504)
| | |
|---|---|
| **Dato** | Saldo a favor arrastrado desde marzo |
| **Fuente** | SII (remanente reajustado UTM) / F29 de marzo en la base |
| **Extracción** | Leer la casilla **504** de la **propuesta** del F29 de abril (Declarar IVA F29 → … → «Ingresar aquí»); ya viene reajustada por UTM. Puede no existir (⇒ P3 = 0) |
| **Cálculo** | `P3 = −$158.117` (entra en negativo, engrosa el crédito) |
| **Código F29** | **`504` = $158.117** (remanente mes anterior) |

> ⚠️ **Nota de mapeo (a validar con Carlos):** en la planilla `PRUEBA1.xlsx`, el $158.117 aparece rotulado como código `77`. En el F29 **literal**, el remanente *que entra* (mes anterior) es código **`504`**; el `77` es el que *sale* al mes siguiente. Aquí usamos el mapeo literal del F29.

### Paso 4 · IVA determinado (bloque C → 89 / 77)
| | |
|---|---|
| **Dato** | Resultado del IVA del mes |
| **Fuente** | Cálculo puro (no se lee de ninguna parte) |
| **Cálculo** | `P4 = 538 − 537 − 504 = 462 − 260.143 − 158.117 = −$417.798` |
| **Decisión** | P4 < 0 → **no se paga IVA**; el saldo se arrastra |
| **Código F29** | `89` = 0 (no aplica) · **`77` (remanente período siguiente) = $417.798** |

### Paso 5 · Otros impuestos — PPM (bloque D → 62)
| | |
|---|---|
| **Dato** | Pago provisional mensual (anticipo de renta) |
| **Fuente** | BI = RCV ventas (columnas «Monto Neto» + «Monto Exento»); tasa = casilla **115** del F29 propuesto (subsección PPM, columna «Tasa») |
| **Extracción** | `BI = Σ(Monto Neto + Monto Exento) de la pestaña VENTA = $2.432` (sin exentos en este caso; las NC restarían) · `tasa (115) = 0,125%` |
| **Cálculo** | `PPM = 2.432 × 0,00125 = $3,04 → $3` (redondeo a peso) |
| **Código F29** | **`62` (PPM neto determinado) = $3** |

Honorarios (`151`) = **$0** (no aplica: sin boletas) · Impuesto único (`48`) = **$0** (no aplica: sin trabajadores). → `P5 = 595 = $3`.

### Paso 6 · Total a pagar (bloque F → 91) — regla condicional 🧮
| | |
|---|---|
| **Cálculo** | P4 ≤ 0 ⟹ **P6 = P5** (el saldo a favor NO reduce PPM/retenciones) |
| **Resultado** | `91 = $3` |
| **Código F29** | **`91` (total a pagar en plazo) = $3** · `92`/`93` = 0 (sin recargo) |

### El F29 de CLIENTE1, casillas con valor (lo demás en cero)
```
502 = 462        503 = 3          538 = 462     (débitos)
520 = 260.143    519 = 11         537 = 260.143 (créditos)
504 = 158.117                                   (remanente mes anterior)
89  = 0          77  = 417.798                  (IVA determinado / arrastre)
62  = 3          595 = 3                         (PPM / subtotal otros)
91  = 3                                          (TOTAL A PAGAR)
```
✅ **Golden test:** total **$3**, remanente que se arrastra **$417.798**. Verificado contra la propuesta del SII.

---

## 6 · Segundo caso (ilustrativo) — cómo cambia la selección

Empresa hipotética con **ventas afectas + honorarios pagados a profesionales + trabajadores**, y con IVA a pagar:
- Bloque A/B/C igual, pero P4 > 0 → activa **`89`** (paga IVA) en vez de `77`.
- **`151`** activa: Σ retención de las boletas de honorarios recibidas (SII).
- **`48`** activa: impuesto único de los trabajadores (Notion RRHH).
- `595` = PPM + 151 + 48; y `91 = 89 + 595` (aquí sí se suman, porque P4 > 0).

> Muestra la esencia: **misma máquina, distintos códigos activos** según el caso. El motor no cambia; cambian los datos y el perfil.

---

## 7 · Códigos pendientes de verificación oficial ⚠️

Antes de producción, confirmar contra las [instrucciones oficiales del F29](https://www.sii.cl/servicios_online/instrucciones_f29_20241112.pdf):
- **`504` vs `77`** (remanente mes anterior vs período siguiente) — mapeo literal aplicado aquí; validar con Carlos contra la planilla.
- **`62`** (PPM neto) — confirmar la línea/columna exacta (el F29 tiene varias sublíneas de PPM por tipo de contribuyente).
- **`151`** (retención honorarios) y **`48`** (retención impuesto único) — confirmar el código exacto en el bloque de retenciones (líneas 59–79); el PDF los lista pero el pareo código↔etiqueta debe verificarse.
- **`91`** (total a pagar en plazo) vs `90`/`94` (con recargo) — confirmar cuál es el "total" que se declara.

> Estos son los **3 sistemas de códigos** que no hay que confundir (ver [`12`](12-fase1-plan-detallado.md) §B0): tipo de documento (DTE) · código de impuesto · **casilla del F29**. Este documento trabaja el tercero.

---

## 8 · Qué le pedimos a Carlos/GCP para cerrar esta especificación

1. Validar el **mapeo de códigos** (§5 y §7), en especial `504`/`77`, `62`, `151`, `48`.
2. Una **descarga real** del RCV (ventas + compras) y de boletas de honorarios de 1–2 clientes → fijar el parser (§3).
3. Confirmar el **perfil por cliente** (PPM sí/no + tasa, honorarios, trabajadores, casos especiales) que parametriza la selección (§2).
4. Confirmar que el **impuesto único** se declara directo desde `IMPUESTO ÚNICO` (Notion RRHH).

---

**Anterior:** [`16-frente-b-plan-calculo-f29.md`](16-frente-b-plan-calculo-f29.md) · **Volver al** [`README`](README.md)
