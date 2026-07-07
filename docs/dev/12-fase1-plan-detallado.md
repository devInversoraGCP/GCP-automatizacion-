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

> **🎯 Objetivo principal (aclarado y reforzado):** el propósito de esta fase no es solo recuperar `RUT` y `CLAVE SII`. Es **completar, corregir y enriquecer toda la base de datos central** `General Customers Data`, usando como fuentes `Contable Mayo` y `RRHH JUNIO 2026`. Esto incluye: recuperar campos faltantes, corregir RUTs inválidos, eliminar duplicados, llenar advisers, completar credenciales (`Previred`), y agregar registros de clientes que existen en las fuentes pero no en la base central.

**Meta:** que "General Customers Data" deje de estar "dejada estar" y se vuelva la fuente única de la verdad de clientes, con la data faltante recuperada desde las 3 fuentes auxiliares (D16), validada y trazable.

## A1 · Mapear el esquema de las 3 fuentes auxiliares 🔒 ✅ *(ejecutado 30-jun-2026)*

> Mapeado **en vivo** vía Notion API (`retrieve-a-data-source` + `query` con paginación y throttling). Workspace **Inversora GCP SpA**. El resultado **corrige varias hipótesis de D16**.

- [x] `Contable Mayo` (ds `fdb12147-…`) — esquema obtenido y **auditoría de completitud ejecutada**
- [x] `RRHH JUNIO 2026` (ds `9c512147-…`) — esquema obtenido y **auditoría de completitud ejecutada**
- [x] `Tickets - Servicios` (ds `9d312147-…`) — esquema obtenido y **descartada como fuente de GCD**

### Qué aporta realmente cada fuente

| Fuente | ¿Completa GCD? | Columnas útiles (→ campo GCD) | Llave de cruce |
|---|---|---|---|
| **Contable Mayo** | ✅ **Sí (principal)** | `Rut`→`RUT` · `Clave SII`→`CLAVE SII` · `Email`→`email` · `Adviser Accounting`→`Adviser Accounting` · `CRM`→`CRM` | `Rut`; respaldo `Customers` (title = nombre) |
| **RRHH JUNIO 2026** | ⚠️ **Parcial** | `RUT`(title)→`RUT` · `CLIENTE`→cruce por nombre · `CLAVE`/`USUARIO`/`DTGO`→credenciales (¿Previred/DT? **verificar**, no confirmado SII) | `RUT` (title); respaldo `CLIENTE` |
| **Tickets - Servicios** | ❌ **No** | Tablero de tareas (`Tarea`, `Tipo`, `Estado`, `Asignado`, `Descripción`). **Sin** RUT, credenciales ni email | — (no cruzable por cliente) |

### ⚠️ Correcciones a D16 (hipótesis → realidad)
- ❌ **RRHH no tiene `email` ni `Whatsapp`** (D16 suponía que los aportaría). Aporta RUT, nombre y credenciales de RR.HH./Previred.
- ❌ **Tickets - Servicios queda descartada** como fuente de la base: no tiene columnas de cliente (ni RUT ni credenciales).
- ⚠️ **`Whatsapp` no está en ninguna de las 3** → no recuperable desde aquí; buscar otra fuente o descartar.
- ✅ **`email` (~100 faltantes) solo se recupera desde Contable Mayo** (`Email`); la cobertura real depende de cuántos tenga poblados.
- ✅ **Contable Mayo es la fuente primaria** para `RUT`, `CLAVE SII`, `email` y `Adviser Accounting`.

### Esquema completo capturado (referencia)
- **Contable Mayo** (contable mensual): `Customers`(title), `Rut`, `Clave SII`, `Email`, `Adviser Accounting`(person), `CRM`(select), `Impuestos`(num), `Fecha`(date), `Month`, varios `status` (`Status`, `ARec`, `Control Solicitudes`, `emision de boletas`, `solicitud/informe/boletas`), checkboxes (`Compras`, `Ventas`, `PreImp`, `Pre-Imptos`), selects (`Actividad Econ`, `Reportabilidad`, `Seleccionar`), `datos socio`(text), `Place`.
- **RRHH JUNIO 2026** (remuneraciones): `RUT`(title), `CLIENTE`, `USUARIO`, `CLAVE`, `DTGO`, `IMPUESTO ÚNICO`(num), `MONTO IMPOSICIONES`(num), `Nº. Trab.`(num), `ASISTENTE`(select), `Liquidaciones`+`Previred`(status — ojo: aquí `Previred` es **estado**, no la credencial), `Date`.
- **Tickets - Servicios** (servicios): `Tarea`(title), `Tipo`(multi_select: Constitución, F29, Renta, Recupero de IVA…), `Estado`(status), `Asignado`(person), `Descripción`, `Número`(num), `Fecha prometida`(date), `Compromiso`(formula), `Actualizado`(last_edited).

### Campos objetivo (revisado con la realidad)

| Campo faltante en GCD | Vacíos en sandbox | Recuperable | Fuente real |
|---|---|---|---|
| `CLAVE SII` 🔒 | 20 | **7** | **Contable Mayo** (`Clave SII`) |
| `RUT` 🔒 | 12 (10 vacíos + 2 DV inválido) | **4** por nombre | **Contable Mayo** (`Rut`) · **RRHH** (`RUT` title, muy parcial) |
| `email` 🔒 | 100 | **12** | **Solo Contable Mayo** (`Email`) |
| `Previred` 🔒 | 140 | **14** | **RRHH** (`USUARIO`/`CLAVE`/`DTGO`) — *pendiente confirmar mapeo* |
| `Adviser Accounting` | 12 | **9** | **Contable Mayo** (`Adviser Accounting`) |
| `Adviser RR.HH` | 141 | **3** | **RRHH** (`ASISTENTE`) |
| `Whatsapp` 🔒 | 141 | 0 | ❌ ninguna de las 3 |
| `RUT RL` 🔒 | 94 | 0 | Contable Mayo (`datos socio`) — *requiere revisión* |
| `CRM` | 47 | 0 | Contable Mayo (`CRM`) — *muy escaso* |

## A1b · Auditoría de completitud ejecutada (30-jun-2026) 🔒

> **Enfoque de esta auditoría:** como el objetivo es **completar, corregir y enriquecer toda la base**, el análisis abarca no solo `RUT`/`CLAVE SII`, sino también duplicados, registros faltantes, campos de contacto, advisers, credenciales `Previred` y cualquier dato recuperable desde las fuentes.
>
> Resultado de cruzar **Contable Mayo** (283 filas), **RRHH JUNIO 2026** (51 filas) y la **sandbox** `General Customers Data - AuditAI` (171 filas) en solo lectura. Todos los conteos salen de la API oficial de Notion; no se sintetizaron datos.

### Métricas generales de las fuentes

| Fuente | Filas | RUTs válidos | RUTs inválidos | Sin RUT |
|---|---|---|---|---|
| Contable Mayo | 283 | 281 | 0 | 2 |
| RRHH JUNIO 2026 | 51 | 18 | 3 | 30 |
| Sandbox GCD | 171 | 158 | 2 | 10 |

### Mapeo de vistas de Contable Mayo

| Vista | Agrupación / filtro | Filas observables | Notas |
|---|---|---|---|
| **default view** | Agrupada por etiquetas (`1`, `2`, `27 Bis`, `4`, `Andrea`, `Cumplimiento`, `Grupo`, `Grupo CI`, `SM`, `Sociedad Inversiones`, `Termino de Giro`, `Victoria`, + vacío) | 283 | El usuario confirmó los conteos de las 10 etiquetas principales; 7 filas residuales explican el total. |
| **lista** | Misma agrupación que default view, distinto layout | 283 | Cada grupo es una tabla con columnas: Adviser Accounting, Dinámico de grupo, RUT, Clave SII, Customers, Status, Impuesto, Actividad, Solicitud. |
| **27 bis** | Filtro `etiqueta = 27 Bis` | 87 | Sin tablas; contiene imágenes adjuntas. |
| **anual 27bis** | Filtro `etiqueta = 27 Bis` | 87 | Sin tablas. |
| **tabla** | Tabla plana sin agrupaciones | 283 | Confirmado por el usuario. |

**Propiedad de agrupación:** es el **select sin nombre** en la API (opciones `1`, `2`, `27 Bis`, etc.). En la UI de Notion probablemente se muestra como `Dinámico de grupo`. La propiedad llamada `Seleccionar` está **100% vacía** y no es la de agrupación.

### Conteos por etiqueta (vista default / lista)

| Etiqueta | Filas |
|---|---|
| 1 | 39 |
| 2 | 34 |
| 27 Bis | 87 |
| 4 | 5 |
| Andrea | 18 |
| Cumplimiento | 36 |
| Grupo | 31 |
| Grupo CI | 11 |
| SM | 5 |
| Sociedad Inversiones | 10 |
| Termino de Giro | 4 |
| Victoria | 1 |
| *(vacío)* | 2 |
| **Total** | **283** |

### Distribución por Status (Contable Mayo)

| Status | Filas |
|---|---|
| Done | 166 |
| 5 DECLARADO SIN MOVIMIENTO | 48 |
| 4 PAGADO GCP | 40 |
| Not started | 16 |
| 3 PAGA CLIENTE - VALIDAR | 5 |
| PAGADO JINSET | 3 |
| PAGADO CLIENTE Y POSTERGADO | 3 |
| PAGADO GCP - POSTERGADO | 1 |
| moroso | 1 |

### Distribución por Adviser Accounting (Contable Mayo)

| Adviser | Filas |
|---|---|
| Constanza Gaggero | 74 |
| Matilde Mateluna | 72 |
| Sebastián Robles | 60 |
| Carlos Cereceda | 39 |
| ANDREA GONZALEZ | 36 |
| (vacío) | 1 |
| Doble asignación | 1 |

### Duplicados detectados

| Base | Tipo | Cantidad |
|---|---|---|
| Sandbox GCD | RUT duplicado | 1 |
| Sandbox GCD | Nombre duplicado | 0 |
| Contable Mayo | RUT duplicado | 1 |
| RRHH JUNIO 2026 | RUT duplicado | 0 |

### Registros en fuentes que no están en la sandbox

#### Contable Mayo: 168 registros nuevos (por RUT válido)

| Etiqueta | Nuevos |
|---|---|
| 27 Bis | 84 |
| Cumplimiento | 18 |
| 1 | 16 |
| Grupo | 15 |
| 2 | 14 |
| Grupo CI | 7 |
| Sociedad Inversiones | 6 |
| Andrea | 3 |
| SM | 2 |
| Termino de Giro | 1 |
| 4 | 1 |
| Victoria | 1 |
| **Total** | **168** |

- De ellos, **167 tienen CLAVE SII** y **5 tienen email**.
- Por status: 99 Done, 27 Declarado sin movimiento, 26 Pagado GCP, 12 Not started, etc.

#### RRHH JUNIO 2026: 2 registros nuevos (por RUT válido)

Ambos tienen USUARIO + CLAVE.

### Cruce fuente ↔ sandbox (por RUT válido)

| Cruce | Coincidencias |
|---|---|
| Sandbox ↔ Contable Mayo | 112 |
| Sandbox ↔ RRHH JUNIO 2026 | 16 |
| Contable Mayo ↔ RRHH JUNIO 2026 | 16 |

### Campos recuperables en registros existentes de la sandbox

| Campo | Fuente | Recuperables | Vacíos actuales en sandbox |
|---|---|---|---|
| RUT (corrección por nombre) | Contable Mayo | **4** | 12 |
| CLAVE SII | Contable Mayo | **7** | 20 |
| email | Contable Mayo | **12** | 100 |
| Previred | RRHH (USUARIO/CLAVE) | **14** | 140 |
| Adviser Accounting | Contable Mayo | **9** | 12 |
| Adviser RR.HH | RRHH (ASISTENTE) | **3** | 141 |
| CRM | Contable Mayo | **0** | 47 |
| RUT RL | Contable Mayo (`datos socio`) | **0** | 94 |

> **Corrección a conteos anteriores:** `Adviser Accounting` no estaba al 100%; el valor real es **159/171 (93%)** y `Adviser RR.HH` es **30/171 (17,5%)**.

### Inconsistencias detectadas (no se sobrescriben automáticamente)

| Campo | Registros con valor distinto entre sandbox y fuente |
|---|---|
| Adviser Accounting (Sandbox vs Contable Mayo) | 77 |
| Adviser RR.HH (Sandbox vs RRHH) | 13 |

### Campos de GCD sin fuente identificada

- `Whatsapp`
- `Rubro`, `Segmentación`, `Ciudad`, `Municipalidad`
- `Nº`, `Column`, `Texto`
- `1ra Factura o Propuesta`
- `Drive Empresa`
- `Propuesta de Servicio`

### Población actual de columnas en la sandbox

| Columna | Poblado |
|---|---|
| `w` | 171/171 (100%) |
| `ID` | 171/171 (100%) |
| `RUT` | 161/171 (94,2%) |
| `RUT RL` | 77/171 (45,0%) |
| `CLAVE SII` | 151/171 (88,3%) |
| `Previred` | 31/171 (18,1%) |
| `email` | 71/171 (41,5%) |
| `Whatsapp` | 30/171 (17,5%) |
| `Adviser Accounting` | 159/171 (93,0%) |
| `Adviser RR.HH` | 30/171 (17,5%) |
| `CRM` | 124/171 (72,5%) |
| `Rubro` | 56/171 (32,7%) |
| `Segmentación` | 82/171 (48,0%) |
| `Ciudad` | 91/171 (53,2%) |
| `Municipalidad` | 54/171 (31,6%) |
| `Nº` | 153/171 (89,5%) |
| `Column` | 83/171 (48,5%) |
| `Texto` | 1/171 (0,6%) |
| `Drive Empresa` | 77/171 (45,0%) |
| `Propuesta de Servicio` | 7/171 (4,1%) |
| `1ra Factura o Propuesta` | 56/171 (32,7%) |
| `Respaldo Anual` | 171/171 (100%) |

### Plan de ejecución propuesto para cerrar el Frente A

#### Fase A — Limpieza (pre-volcado) — ✅ ejecutada (01-jul-2026)
1. ✅ Backup fresco de la sandbox → `backups/general-customers-data/2026-07-01_sandbox_pre-fase-A.csv` (171 filas, 24 columnas; hoy la sandbox tiene 27 columnas post-D19/D23).
2. ✅ RUT duplicado en la sandbox (`SOCIAL UP SPV I SPA` / `SPV II SPA`, mismo RUT en ambos): **decisión del usuario** — se mantienen como 2 clientes separados (no se fusionan/borran), RUT sin modificar en ninguno hasta que el usuario consulte a su cliente cuál es el correcto de cada uno.
3. ✅ RUTs problemáticos corregidos: **7 de 12** recuperados desde Contable Mayo por coincidencia de nombre (5 alta confianza + 2 confianza media, todos con dígito verificador válido confirmado). Log completo en `backups/general-customers-data/log-auditoria-volcado.csv`. **5 quedan pendientes** (nombres genéricos/placeholder sin candidato confiable: `Sergio ??`, `Zsabesky Servicios`, `XIT`, `Patricia`, `Steven`) — el usuario debe consultarlos con su cliente.
4. ✅ RUT duplicado en Contable Mayo (`ADMINISTRADORES CHILE SPA`/`SpA`, mismo RUT): **decisión del usuario** — no se toca Contable Mayo (sigue solo lectura); se deduplica al momento de importar en la Fase C (solo 1 copia entra a la sandbox).

#### Fase B — Enriquecimiento de registros existentes
Escribir en sandbox **solo campos vacíos**, sin sobrescribir:
- 4 RUTs
- 7 CLAVE SII
- 12 emails
- 14 Previred (si se confirma mapeo RRHH)
- 9 Adviser Accounting
- 3 Adviser RR.HH

#### Fase C — Agregar registros nuevos *(plan detallado en [`13-fase-c-volcado-nuevos-registros.md`](13-fase-c-volcado-nuevos-registros.md))*
Agregar a la sandbox los **168 registros de Contable Mayo** y los **2 de RRHH** con RUT válido que no estaban. Esto llevaría la base de 171 a **341 registros**. Ver algoritmo completo, mapeo de campos, validaciones, dry-run y log de auditoría en [`13-fase-c-volcado-nuevos-registros.md`](13-fase-c-volcado-nuevos-registros.md).

#### Fase D — Verificación final
- Re-medir completitud.
- Validar esquema con Pandera/Pydantic.
- Generar log de auditoría completo.

### Decisiones del usuario — ✅ resueltas (01-jul-2026, ver D19–D22 en [`05`](05-decisiones-y-preguntas.md))

1. ✅ **Mapeo `USUARIO`/`CLAVE` de RRHH → `USUARIO-Previred`/`CLAVE-Previred` (nuevas, text) + `RRHH Origen` (relation); `Previred` → status igual que RRHH.** `DTGO` queda sin mapear (D19). **Ejecutado en la sandbox** (esquema 22→27 columnas tras D23).
2. ✅ **Fase A+B+C completa**: se agregan los 168 registros nuevos de Contable Mayo + 2 de RRHH (D20). Sandbox pasará de 171 a ~341.
3. ✅ **Contable Mayo/RRHH siempre predominan sobre la sandbox** ante cualquier conflicto de valor — regla general para todos los campos, no solo advisers (D21). Reemplaza la regla por defecto de "solo llenar vacíos" de D15/[`09`](09-seguridad-y-respaldo.md).
4. ✅ **Sin exclusión** por status/etiqueta: los 168 nuevos entran todos, incluidos los 99 `Done` (D22).

## A2 · Llave de cruce: normalización de `RUT` y nombre 🔒🧮

El cruce fuente↔sandbox se hace **primero por `RUT`** (clave fuerte) y, en su defecto, por **nombre normalizado** (`w`).

### A2.1 · `RUT` como clave canónica (validable con dígito verificador)
El RUT chileno trae un **dígito verificador** calculable por **módulo 11**: permite validar y normalizar de forma determinista (atrapa typos en la fuente).

- [x] Normalizar: quitar puntos y espacios, mayúscula la `K`, separar cuerpo y DV (`12345678-5`).
- [x] Validar DV con módulo 11 (algoritmo A-RUT abajo); marcar `RUT_INVALIDO` los que no cuadren.
- [x] Usar el RUT normalizado (`cuerpo-DV`) como clave de join.

```text
# Algoritmo A-RUT · dígito verificador (módulo 11)
entrada: cuerpo (dígitos del RUT sin DV)
s = 2; suma = 0
para cada dígito d de cuerpo, de derecha a izquierda:
    suma += d * s
    s = 2 si s == 7 sino s + 1          # ciclo 2,3,4,5,6,7,2,3,...
resto = 11 - (suma mod 11)
DV = "0" si resto == 11 ; "K" si resto == 10 ; str(resto) en otro caso
```

> 🐛 **Bug corregido (01-jul-2026):** una versión anterior de este pseudocódigo tenía `s = 3 si s == 7` (typo), rompiendo el ciclo real del módulo 11 (`2,3,4,5,6,7,2,3,...`) y produciendo falsos positivos masivos de "DV inválido" al reimplementarlo. Verificado con casos conocidos (`10207640-0`, `12345678-5`, `16630663-9`) y contra el reconteo real de la sandbox (10 vacíos + 2 DV inválido + 1 duplicado, que sí coincide con lo documentado en §A1b).

### A2.2 · Nombre (`w`) como clave de respaldo
- [x] `norm(s)` = trim · minúsculas · sin tildes · colapsar espacios · quitar sufijos societarios (`SPA`, `SA`, `LTDA`, `EIRL`, `SPA.`).
- [x] Para residuales sin RUT, match por nombre normalizado exacto + cola de revisión humana.
- [ ] Para residuales sin RUT, **fuzzy match** con RapidFuzz si el match exacto no es suficiente (ver A3).

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

- [x] Implementar match determinista por RUT.
- [x] Implementar match por nombre normalizado para el residual (sin ML; con umbral exacto + cola de revisión humana).
- [ ] Implementar fuzzy por nombre (RapidFuzz) si el residual crece o el match exacto no es suficiente.
- [x] Reportar: `MATCH`, `AMBIGUO` (revisión humana), `SIN_FUENTE`.

## A4 · Protocolo de volcado a la sandbox (dry-run → confirmación → escritura) 🔒

> Reafirma [`09`](09-seguridad-y-respaldo.md): nunca al original; backup fechado previo; apuntar por clave estable; log de auditoría.

```text
# Algoritmo A-VOLCADO · idempotente y no destructivo
precondición: backup CSV de hoy guardado de forma segura
para cada (cliente, campo_faltante) detectado por el match:
    valor ← fuente_auxiliar[cliente][campo]
    si sandbox[cliente][campo] ya tiene valor:  SKIP   # no sobreescribir (salvo decisión caso a caso del usuario)
    si match es AMBIGUO:                          SKIP → cola de revisión humana
    registrar en diff: (ID | RUT, campo, "" → valor, fuente, score)
mostrar diff COMPLETO al usuario        # DRY-RUN, no aplica nada
esperar confirmación explícita
aplicar escritura por clave estable (ID de tipo unique_id o RUT; nunca por posición)
escribir log de auditoría: (id, columna, antes → después, timestamp, fuente, score)
```

- [ ] Generar el diff (dry-run) y mostrarlo sin aplicar.
- [ ] Confirmación del usuario por lote/columna.
- [ ] Escritura idempotente por clave estable (`ID` de tipo `unique_id`) + log de auditoría.
- [ ] Re-medir completitud post-volcado (cuántos `CLAVE SII`/`RUT`/`email`/`Previred`/advisers se recuperaron).

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

- [x] Las 3 fuentes auxiliares mapeadas y cruzadas con la sandbox.
- [ ] Data faltante recuperada en la sandbox (`CLAVE SII`, `RUT`, `email`, `Previred`, advisers) y **completitud re-medida**.
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
| **504** | Remanente de crédito fiscal **del mes anterior** (el que **entra**; se lee de la propuesta del F29, puede no estar) | Entrada (P3) — ✅ validado GCP |
| **115** | **Tasa del PPM** del contribuyente (subsección PPM de la propuesta, columna «Tasa») | Entrada (P5) — ✅ validado GCP |
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

> ✅ **Rutas operativas validadas (GCP, jul-2026):** en la interfaz web del RCV, estos campos corresponden a la pestaña **«VENTA»** (columnas «Monto IVA», «Monto Neto», «Monto Exento») y a la pestaña **«COMPRA»** (columna «IVA Recuperable»), con **período = mes anterior al actual**. Ruta completa, propuesta del F29 (casillas 504/115) e informe de boletas: [`17-especificacion-literal-calculo-f29.md`](17-especificacion-literal-calculo-f29.md) §3.

## B4 · Especificación formal de las 6 partes 🧮

Reescribe el algoritmo A1 de [`11`](11-checklist-maestro.md) como contrato implementable (entrada → fórmula → salida → código F29):

- [ ] **P1 Débito** = Σ `MntIVA` de docs emitidos afectos → cód. 538 (total débitos). Para `CLIENTE1`: doc 48 → $462.
- [ ] **P2 Crédito** = Σ `MntIVA` recuperable de docs recibidos → cód. 537 (total créditos). `CLIENTE1`: 11 facturas → $260.143.
- [ ] **P3 Remanente** = casilla **504** de la **propuesta del F29** (remanente del mes anterior, ya reajustado UTM; si no aparece, P3 = 0), arrastrado en negativo. `CLIENTE1`: $158.117. *(La planilla lo rotula `77`; el literal es 504 — ver [`17`](17-especificacion-literal-calculo-f29.md) §3.4.)*
- [ ] **P4 IVA determinado** = P1 + P2 + P3 → si > 0 cód. 89 (IVA a pagar); si < 0 cód. 77 (remanente a favor, se arrastra). `CLIENTE1`: −$417.798.
- [ ] **P5 Otros** = PPM (cód. 62) + ret. honorarios (151) + ret. imp. único (48). PPM = `BI × tasa`, con **BI = Σ(Monto Neto + Monto Exento) de las ventas** (NC restan) y **tasa = casilla 115** de la propuesta (por contribuyente). `CLIENTE1`: BI $2.432 × 0,125% = $3. *(✅ validado GCP; antes se usaba el atajo `débito ÷ 0,19`, que omite el exento.)*
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

- ✅ Esquema real de las 3 fuentes auxiliares (A1) y auditoría de completitud ejecutada (A1b).
- ✅ **Decisión usuario (D19):** mapeo `USUARIO`/`CLAVE` de RRHH → `Previred` de GCD — resuelto y ejecutado en la sandbox.
- ✅ **Decisión usuario (D20):** ejecutar Fase A+B+C completa (incluye agregar 170 registros nuevos).
- ✅ **Decisión usuario (D21):** Contable Mayo/RRHH predominan siempre sobre la sandbox ante conflicto — regla general.
- ⏳ Resolver 1 RUT duplicado en sandbox y 1 en Contable Mayo antes del volcado.
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
