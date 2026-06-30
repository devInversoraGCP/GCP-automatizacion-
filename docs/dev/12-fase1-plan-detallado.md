# 12 · Fase 1 — Plan detallado (centralizar la data + formalizar las reglas)

> **Documento de trabajo de la Fase 1.** Profundiza el ítem "Fase 1" del [checklist maestro](11-checklist-maestro.md) con investigación, mapeo de elementos y sub-checklists ejecutables. La Fase 1 tiene **dos frentes que se ejecutan en SECUENCIA, no en paralelo (D18):**
> - **1º — Frente A — Centralización de la data** en Notion ("General Customers Data"), Etapa 1 de D11. **Prioridad total: se completa al 100% y se verifica primero.**
> - **2º — Frente B — Formalización de las reglas** del F29 (diccionario de códigos, catálogo de documentos, especificación de las 6 partes). **Arranca solo cuando el Frente A esté terminado.**
>
> ⛔ **Regla de oro de esta fase (D18):** la base de datos central es la prioridad. Todo el esfuerzo va al **Frente A** hasta tener una base **final y robusta**; nada de hacer las cosas a medias ni dividir el potencial. El Frente B espera.
>
> **Criterio de aceptación de la Fase 1:** (A) la data faltante está recuperada en la **sandbox** con trazabilidad de origen, y (B) un desarrollador puede implementar el motor de cálculo (Fase 2) **sin abrir el Excel**, leyendo solo esta especificación.
>
> **Última actualización:** 30-jun-2026. Reglas no negociables y datos duros: ver [`11`](11-checklist-maestro.md). 🔒 = toca credenciales/PII · 🧮 = lógica determinista.

## Cómo se relaciona con el resto

- El **qué** y el **orden macro** están en [`11`](11-checklist-maestro.md) (tareas 1.1–1.6). Aquí está el **cómo** detallado.
- El destino de toda escritura es la **sandbox** `General Customers Data - AuditAI`, nunca el original (ver [`09`](09-seguridad-y-respaldo.md)).
- Lo que se formalice aquí alimenta directamente el **motor de cálculo** (Fase 2, [`11`](11-checklist-maestro.md) §2.4 y algoritmo A1).

---

# Frente A — Centralización de la data en Notion *(1º · prioridad total)*

**Meta:** que "General Customers Data" deje de estar "dejada estar" y se vuelva la fuente única de la verdad de clientes, con la data faltante recuperada desde las 3 fuentes auxiliares (D16), validada y trazable.

## A1 · Mapear el esquema de las 3 fuentes auxiliares 🔒

> ⚠️ **Restricción operativa:** la API/MCP de Notion requiere sesión autorizada (OAuth). En una sesión no interactiva no se puede consultar en vivo; este mapeo se ejecuta en una sesión Claude/opencode con Notion conectado.

- [ ] `Contable Mayo` (ds `fdb12147-…`) → `query-data-source` con `page_size=1` → listar propiedades (nombre, tipo).
- [ ] `RRHH JUNIO 2026` (ds `9c512147-…`) → idem.
- [ ] `Tickets - Servicios` (ds `9d312147-…`) → idem.
- [ ] Por cada fuente, construir una **tabla de aporte**: qué columna de la fuente llena cada campo faltante de la sandbox.

**Campos objetivo a recuperar** (medición jun-2026, ver [`08`](08-notion-general-customers-data.md)):

| Campo faltante | Cuántos faltan | Fuente auxiliar candidata (D16) |
|---|---|---|
| `CLAVE SII` 🔒 | 20 (~12%) | Contable Mayo · Tickets - Servicios |
| `RUT` 🔒 | 10 (~6%) | Contable Mayo · Tickets - Servicios |
| `email` 🔒 | ~100 (~58%) | RRHH JUNIO 2026 |
| `Whatsapp` 🔒 | (medir) | RRHH JUNIO 2026 |
| `Adviser Accounting` / `Adviser RR.HH` | (medir) | Contable Mayo / RRHH JUNIO 2026 |

## A2 · Llave de cruce: normalización de `RUT` y nombre 🔒🧮

El cruce fuente↔sandbox se hace **primero por `RUT`** (clave fuerte) y, en su defecto, por **nombre normalizado** (`w`).

### A2.1 · `RUT` como clave canónica (validable con dígito verificador)
El RUT chileno trae un **dígito verificador** calculable por **módulo 11**: permite validar y normalizar de forma determinista (atrapa typos en la fuente).

- [ ] Normalizar: quitar puntos y espacios, mayúscula la `K`, separar cuerpo y DV (`12345678-5`).
- [ ] Validar DV con módulo 11 (algoritmo A-RUT abajo); marcar `RUT_INVALIDO` los que no cuadren.
- [ ] Usar el RUT normalizado (`cuerpo-DV`) como clave de join.

```text
# Algoritmo A-RUT · dígito verificador (módulo 11)
entrada: cuerpo (dígitos del RUT sin DV)
s = 2; suma = 0
para cada dígito d de cuerpo, de derecha a izquierda:
    suma += d * s
    s = 3 si s == 7 sino s + 1          # ciclo 2,3,4,5,6,7,2,3,...
resto = 11 - (suma mod 11)
DV = "0" si resto == 11 ; "K" si resto == 10 ; str(resto) en otro caso
```

### A2.2 · Nombre (`w`) como clave de respaldo
- [ ] `norm(s)` = trim · minúsculas · sin tildes · colapsar espacios · quitar sufijos societarios (`SPA`, `SA`, `LTDA`, `EIRL`, `SPA.`).
- [ ] Para residuales sin RUT, **fuzzy match** sobre el nombre normalizado (ver A3).

## A3 · Entity resolution / deduplicación (investigación) 🧮

**Hallazgo de investigación.** El problema es *record linkage* clásico (cruzar registros que describen la misma entidad). Herramientas Python maduras:

| Herramienta | Enfoque | ¿Encaja en AuditAI? |
|---|---|---|
| **RapidFuzz** | Fuzzy string matching (Levenshtein, token_sort), rápido, sin entrenamiento | ✅ **Sí** — ideal para el residual por nombre |
| Python Record Linkage Toolkit | Reglas + comparadores, indexación/blocking | Opcional si crece el volumen |
| **Splink** | Linkage probabilístico (Fellegi-Sunter), backends SQL, sin training data | Overkill para 171 filas |
| **dedupe** | ML con etiquetado humano (active learning) | Overkill; requiere labeling |

**Recomendación (madura, proporcional al tamaño):** con solo **171 registros** y `RUT` como clave fuerte, **no se necesita ML**. Estrategia en dos pasos:
1. **Match determinista** por `RUT` normalizado y validado (A2.1) → cubre la mayoría.
2. **Fuzzy match** del residual por nombre con **RapidFuzz** (`token_sort_ratio`), con umbral alto (p. ej. ≥ 90) y **revisión humana** de los ambiguos. Nada se escribe automáticamente sobre un match dudoso.

- [ ] Implementar match determinista por RUT.
- [ ] Implementar fuzzy por nombre (RapidFuzz) para el residual, con umbral + cola de revisión.
- [ ] Reportar: `MATCH`, `AMBIGUO` (revisión humana), `SIN_FUENTE`.

## A4 · Protocolo de volcado a la sandbox (dry-run → confirmación → escritura) 🔒

> Reafirma [`09`](09-seguridad-y-respaldo.md): nunca al original; backup fechado previo; apuntar por clave estable; log de auditoría.

```text
# Algoritmo A-VOLCADO · idempotente y no destructivo
precondición: backup CSV de hoy guardado de forma segura
para cada (cliente, campo_faltante) detectado por el match:
    valor ← fuente_auxiliar[cliente][campo]
    si sandbox[cliente][campo] ya tiene valor:  SKIP   # no sobreescribir (salvo decisión caso a caso del usuario)
    si match es AMBIGUO:                          SKIP → cola de revisión humana
    registrar en diff: (userDefined:ID | RUT, campo, "" → valor, fuente, score)
mostrar diff COMPLETO al usuario        # DRY-RUN, no aplica nada
esperar confirmación explícita
aplicar escritura por clave estable (userDefined:ID o RUT; nunca por posición)
escribir log de auditoría: (id, columna, antes → después, timestamp, fuente, score)
```

- [ ] Generar el diff (dry-run) y mostrarlo sin aplicar.
- [ ] Confirmación del usuario por lote/columna.
- [ ] Escritura idempotente por clave estable + log de auditoría.
- [ ] Re-medir completitud post-volcado (cuántos `CLAVE SII`/`RUT`/`email` se recuperaron).

## A5 · Capa de acceso a datos + límites reales de la API de Notion 🔒

**Recomendación (D11):** encapsular Notion tras una **capa de abstracción** (interfaz `RepositorioClientes` con `leer/listar/escribir`) para que el salto Etapa 1 → Etapa 2 (BD especializada) **no obligue a reescribir** el resto.

**Límites reales de la API de Notion** (investigación, [developers.notion.com](https://developers.notion.com/reference/request-limits)) — el código debe respetarlos:

| Límite | Valor | Implicación de diseño |
|---|---|---|
| Rate limit por integración | ~**3 req/s** promedio (con ráfagas) | throttling/cola; no disparar en paralelo sin control |
| Rate limit por workspace | adicional, escala con el plan | idem |
| Respuesta a exceso | HTTP **429** (`rate_limited`) y **529** | reintentar respetando el header **`Retry-After`** (segundos) |
| Paginación | `page_size` máx **100**; cursor-based (`start_cursor`, `has_more`, `next_cursor`) | iterar por cursor para leer los 171 |
| Profundidad de query | máx **10.000** resultados; campo `request_status` si queda incompleta | suficiente para esta base |

> Esto explica el rate-limit 429 que dejó pendiente el conteo exacto de "listos para SII" en [`08`](08-notion-general-customers-data.md): se resuelve con reintento + `Retry-After`.

- [ ] Definir interfaz `RepositorioClientes` (abstracción).
- [ ] Implementación Notion con manejo de 429/529 + `Retry-After` + paginación por cursor.
- [ ] Throttling a ≤ 3 req/s.

## A6 · Validación de esquema (Pandera/Pydantic) = el contrato de la base 🧮

Notion **no valida esquema**; por eso la validación es crítica (D11) y es además el **control de anomalías** (D9).

- [ ] Modelo Pydantic `Cliente` (tipos, formatos: RUT válido, email válido, etc.).
- [ ] Esquema Pandera del DataFrame de clientes (columnas obligatorias, nulos permitidos/no, dominios de `Segmentación`/`Ciudad`/…).
- [ ] Regla: marcar como **dato faltante/anomalía** lo que no cumpla el contrato (insumo del reporte de completitud).

---

# ⛔ Gate — el Frente B no arranca hasta cerrar el Frente A (D18)

El Frente B queda **en pausa** hasta que el Frente A esté **verdaderamente terminado**. **Criterio de término del Frente A:**

- [ ] Las 3 fuentes auxiliares mapeadas y cruzadas con la sandbox.
- [ ] Data faltante recuperada en la sandbox (`CLAVE SII`, `RUT`, `email`, `Whatsapp`, advisers) y **completitud re-medida**.
- [ ] Sin duplicados; matches ambiguos resueltos por revisión humana.
- [ ] Validación de esquema (Pandera/Pydantic) **en verde**.
- [ ] Base **verificada** contra las fuentes y **trazable** (log de auditoría completo).

> El catálogo oficial de documentos (B1) se capturó como **adelanto** durante la investigación, pero el trabajo activo del Frente B **no avanza** hasta cumplir el gate de arriba.

---

# Frente B — Formalización de las reglas del F29 *(2º · solo tras cerrar el Frente A)*

**Meta:** dejar la especificación tan explícita que la Fase 2 se implemente sin abrir el Excel.

## B0 · ⚠️ Tres sistemas de códigos distintos (no confundir) — hallazgo clave

La investigación dejó claro que en este dominio conviven **tres numeraciones independientes**. Confundirlas es un error grave (y la planilla `CLIENTE1` ya mezcla dos "48"):

| Sistema | Qué numera | Ejemplos | Fuente oficial |
|---|---|---|---|
| **Tipo de documento (DTE)** | Qué documento es | 33 Factura Electrónica · **48 Comprobante de Pago Electrónico** · 61 NC electrónica · 914 DIN | IECV §4 |
| **Código de impuesto/recargo** (`CodImp`, Tabla 7) | Impuesto adicional/retención dentro de un documento | 15 IVA retenido total · 27/271 ILA · 28 imp. específico diésel | IECV §7 |
| **Código de casilla del F29** | Casilla del formulario mensual | **48 Ret. imp. único** · 62 PPM · 77 remanente · 538 total débitos | Instrucciones F29 (SII) |

> 🔑 **Caso `CLIENTE1`:** su débito ($462) proviene de **3 "Comprobantes pago electrónicos" = documento tipo 48**. En la **misma planilla**, la columna "CODIGO F29" usa **48 = Ret. Imp. Único Trabajadores** (otra cosa). El diccionario debe mantener estos universos separados para no mapear mal.

## B1 · Catálogo de tipos de documento (oficial SII) → mapeo a parte del F29 🧮

Extraído del **Formato IECV v3.0** del SII ([formato_iecv.pdf](https://www.sii.cl/factura_electronica/factura_mercado/formato_iecv.pdf), §4.1/§4.2). Subconjunto relevante para el cálculo; **"R" = solo se informa totalizado en el resumen** (no va al detalle uno-a-uno):

**Ventas (IEV) → Débito fiscal (P1):**
| Cód | Documento | R | Efecto |
|---|---|:--:|---|
| 33 | Factura Electrónica | | + débito |
| 34 | Factura No Afecta o Exenta Electrónica | | exento (sin IVA) |
| 39 | Boleta electrónica | R | + débito |
| 41 | Boleta no afecta/exenta electrónica | R | exento |
| 43 | Liquidación-Factura Electrónica | | + débito |
| 46 | Factura de Compra electrónica (emitida) | | retención (cambio de sujeto) |
| **48** | **Comprobante de Pago Electrónico** | R | **+ débito ← `CLIENTE1`** |
| 56 | Nota de Débito Electrónica | | + débito (aumenta) |
| 61 | Nota de Crédito Electrónica | | − débito (rebaja/anula) |
| 110/111/112 | Exportación electrónica (fact/ND/NC) | | exportación |

**Compras (IEC) → Crédito fiscal (P2):**
| Cód | Documento | Efecto |
|---|---|---|
| 33 | Factura Electrónica (recibida) | + crédito |
| 34 | Factura No Afecta/Exenta Electrónica | exento |
| 46 | Factura de Compra electrónica | + crédito / IVA retenido |
| 56 | Nota de Débito Electrónica | + crédito (aumenta) |
| 61 | Nota de Crédito Electrónica | − crédito (rebaja) |
| 914 | Declaración de Ingreso (DIN) | + crédito (importación) |

- [ ] Cargar el catálogo completo (IEV §4.1 / IEC §4.2) como tabla de referencia del proyecto.
- [ ] Fijar el **mapeo documento → parte del F29** (débito P1 / crédito P2 / exento / retención).
- [ ] Marcar los "solo resumen" (35, 38, 39, 41, 47, 48, 105, 919, 920, 922, 924) — entran agregados, no uno a uno.

## B2 · Diccionario de códigos del F29 (arranque verificado + pendiente) 🧮

Confirmados contra instrucciones oficiales del SII ([reso/instrucciones F29](https://www.sii.cl/servicios_online/instrucciones_f29_20241112.pdf)) y la planilla `CLIENTE1`:

| Código | Significado | Origen |
|---|---|---|
| 503 | Cantidad de facturas emitidas | Ventas |
| 502 | Débito fiscal de las facturas emitidas (cód. 503) | Ventas |
| 519 | Cantidad de facturas recibidas (con derecho a crédito) | Compras |
| 520 | Crédito recuperable de facturas recibidas | Compras |
| 538 | **TOTAL DÉBITOS** (suma de la línea) | Cálculo |
| 537 | **TOTAL CRÉDITOS** (suma de la línea) | Cálculo |
| 89 | Impuesto determinado IVA (si débitos > créditos) | Cálculo |
| 77 | Remanente de crédito fiscal para el período siguiente (si créditos > débitos) | Cálculo |
| 62 | PPM neto determinado | Otros (P5) |
| 48 | Retención impuesto único a trabajadores | Otros (P5) — *según planilla, verificar* |
| 151 | Retención honorarios (Ley 21.133) | Otros (P5) — *verificar* |

- [ ] Verificar 48/151/62 contra el formulario y normativa vigentes (la planilla es la fuente, falta contraste oficial).
- [ ] Extender al resto de los ~140 códigos (códigos 91 "total a pagar dentro del plazo", 595 subtotales, etc. — **marcar `verificar`** hasta contrastar).
- [ ] Para cada código: significado + de qué documento/parte se alimenta + si es entrada o calculado.

## B3 · Estructura del RCV (campos del detalle) — alimenta el modelo de datos 🧮

Del IECV (detalle ventas §2.4 / compras §3.4). Campos mínimos que el modelo de datos (Fase 2) y el parser (Fase 3) deben contemplar:

**Detalle Ventas (IEV):** `TpoDoc`, `NroDoc` (folio), `FchDoc` (AAAA-MM-DD), `TasaImp`, `RUTDoc` (receptor), `RznSoc`, `MntExe`, `MntNeto`, `MntIVA`, `MntTotal`, más `IVAFueraPlazo`, `IVARetTotal/Parcial`, tabla `OtrosImp` (CodImp/TasaImp/MntImp).

**Detalle Compras (IEC):** `TpoDoc`, `NroDoc`, `FchDoc`, `TpoImp` (1=IVA, 2=Ley 18.211), `TasaImp`, `RUTDoc` (proveedor), `MntExe`, `MntNeto`, `MntIVA` (recuperable), `MntIVANoRec` (+`CodIVANoRec` 1–9), `IVAUsoComun`, `MntTotal`, tabla `OtrosImp`.

- [ ] Definir el modelo `DocumentoVenta` / `DocumentoCompra` con estos campos.
- [ ] Nota para Fase 2: el débito de una factura sale de `MntIVA`; el crédito, de `MntIVA` (recuperable). El IVA **no recuperable** y el **uso común** (proporcionalidad) son casos que el motor debe contemplar más adelante.

## B4 · Especificación formal de las 6 partes 🧮

Reescribe el algoritmo A1 de [`11`](11-checklist-maestro.md) como contrato implementable (entrada → fórmula → salida → código F29):

- [ ] **P1 Débito** = Σ `MntIVA` de docs emitidos afectos → cód. 538 (total débitos). Para `CLIENTE1`: doc 48 → $462.
- [ ] **P2 Crédito** = Σ `MntIVA` recuperable de docs recibidos → cód. 537 (total créditos). `CLIENTE1`: 11 facturas → $260.143.
- [ ] **P3 Remanente** = remanente del período anterior (cód. 77), arrastrado en negativo. `CLIENTE1`: $158.117.
- [ ] **P4 IVA determinado** = P1 + P2 + P3 → si > 0 cód. 89; si < 0 cód. 77 (arrastra). `CLIENTE1`: −$417.798.
- [ ] **P5 Otros** = PPM (cód. 62) + ret. honorarios (151) + ret. imp. único (48). PPM = `ventas_netas × tasa`, `ventas_netas = débito / 0,19`. `CLIENTE1`: base $2.432 × 0,125% = $3.
- [ ] **P6 Total** = **si P4 > 0:** P4 + P5; **si P4 ≤ 0:** solo P5 (el remanente se arrastra, los otros impuestos se pagan igual). `CLIENTE1`: $3.
- [ ] Aritmética en `Decimal`, redondeo a peso entero (CLP sin centavos).

## B5 · Catálogo de tasas vigentes (parametrizable) 🧮

Las tasas cambian con la ley (riesgo conocido); deben vivir en config, no hardcodeadas:

- [ ] IVA **19%**.
- [ ] PPM: tasa por contribuyente (caso `CLIENTE1`: **0,125%**).
- [ ] Retención honorarios (Ley 21.133): **gradual**, verificar tasa del período (la planilla usa 14,5%).
- [ ] ILA y otros impuestos adicionales (Tabla 7 IECV): solo si el cliente los tiene; tasas a verificar en sii.cl.

---

## Dependencias y preguntas abiertas de la Fase 1

- Esquema real de las 3 fuentes auxiliares (A1) → requiere sesión Notion autorizada (Preguntas #6/#7 de [`05`](05-decisiones-y-preguntas.md)).
- Verificación oficial del diccionario F29 completo (B2) → contrastar con normativa.
- Muestra real del XLSX que descarga el cliente del SII (para fijar el parser de Fase 3) → Pregunta #5.

## Glosario de siglas nuevas

- **RCV** — Registro de Compras y Ventas (repositorio del SII).
- **IECV / IEV / IEC** — Información Electrónica de Compras y Ventas / de Ventas / de Compras (formato XML del SII).
- **DTE** — Documento Tributario Electrónico.
- **DJ 3327 / 3328** — Declaraciones Juradas de compras / ventas.
- **DIN** — Declaración de Ingreso (importación), doc tipo 914.
- **ILA** — Impuesto a bebidas (Ley de IVA art. 42).
- **DV** — Dígito Verificador del RUT (módulo 11).

## Fuentes oficiales y de investigación

- SII — Formato Información Electrónica de Compras y Ventas (códigos de documentos e impuestos): https://www.sii.cl/factura_electronica/factura_mercado/formato_iecv.pdf
- SII — Instrucciones del Formulario 29: https://www.sii.cl/servicios_online/instrucciones_f29_20241112.pdf
- SII — Formulario 29 (anverso, layout de códigos): https://www.sii.cl/formularios/anverso_f29.pdf
- Notion — Request limits (rate limit, paginación): https://developers.notion.com/reference/request-limits
- RapidFuzz (fuzzy matching): https://github.com/rapidfuzz/RapidFuzz · Splink: https://github.com/moj-analytical-services/splink · dedupe: https://github.com/dedupeio/dedupe

---

**Anterior:** [`11-checklist-maestro.md`](11-checklist-maestro.md) · **Volver al** [`README`](README.md)
