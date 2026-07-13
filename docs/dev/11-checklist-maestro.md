# 11 · Checklist maestro del proyecto (de inicio a fin)

> **Fuente única de verdad del avance.** Índice completo de todo lo que el proyecto requiere, de principio a fin, con cada fase descompuesta en **tareas → subtareas → algoritmos**. Lo ya hecho queda marcado `[x]`; lo pendiente, `[ ]`. Mantener este documento vivo: al cerrar una subtarea, márcala aquí.
>
> **Última actualización:** 07-jul-2026 (Frente N — E2E exitoso: botón "Enviar Correo F29" → webhook → backend → correo → write-back Status, sobre Contable Junio con fila de prueba `ZZ_TEST AuditAI`; ver [`23`](23-automatizacion-notion-contable-correo.md) §5.6. Backend en Flask + SMTP Gmail por asesor, identificación de fila por RUT con extractor recursivo).
> Complementa [`../ROADMAP.md`](../ROADMAP.md) (visión de fases) y [`05-decisiones-y-preguntas.md`](05-decisiones-y-preguntas.md) (decisiones D1–D17). No duplica: aquí está el **detalle ejecutable**.

## Cómo usar este documento (si eres un LLM / agente)

Este archivo es un **índice ejecutable**, no la fuente primaria de cada tema. Para trabajar bien:

1. **Lee primero, en este orden:** [`../../AGENTS.md`](../../AGENTS.md) (reglas no negociables) → [`00-introduccion.md`](00-introduccion.md) → [`01-dominio-F29.md`](01-dominio-F29.md) (dominio + caso `CLIENTE1`) → [`05-decisiones-y-preguntas.md`](05-decisiones-y-preguntas.md) (D1–D17). Luego **este `11`** para saber qué hacer y en qué orden.
2. **Jerarquía de fuentes de verdad** (si algo se contradice, manda la fuente de la derecha para su tema):

   | Tema | Fuente de verdad |
   |---|---|
   | Cálculo del F29 (**qué** se calcula) | **`F29.pdf`** — formulario oficial SII, ~140 códigos (fuente de verdad madre, D24) → [`01`](01-dominio-F29.md). `PRUEBA1.xlsx` = **golden test + formato de salida**, no autoridad |
   | Reglas para agentes (seguridad, PII, idioma) | [`../../AGENTS.md`](../../AGENTS.md) |
   | Decisiones de diseño | [`05`](05-decisiones-y-preguntas.md) (D1–D17) |
   | Esquema de Notion / IDs | [`08`](08-notion-general-customers-data.md), [`10`](10-fuentes-auxiliares-notion.md) |
   | Protocolo de respaldo | [`09`](09-seguridad-y-respaldo.md) |
   | Stack técnico | [`06`](06-stack-tecnico.md) |

3. **Mantenimiento:** al cerrar una subtarea, marca `[x]` aquí **y** refleja el cambio en la sección "Checklist" de [`../../presentacion.html`](../../presentacion.html) (clase `ck todo`→`ck done`, contador y ancho de la barra). Ambos deben quedar **sincronizados**.
4. **Sobre el fasaje:** este documento refleja el **reordenamiento posterior al cambio de rumbo del 30-jun-2026** (centralización de data plegada en la Fase 1; BD especializada en la Fase 6). [`../ROADMAP.md`](../ROADMAP.md) conserva la numeración previa; ante diferencia de fasaje, **manda este `11`**.

## Reglas no negociables (resumen operativo)

Resumen de [`../../AGENTS.md`](../../AGENTS.md); el detalle manda allí. **Antes de cualquier acción:**

- 🔒 **Notion = solo lectura por defecto.** Escritura/edición/borrado solo con autorización explícita del usuario, **sobre la sandbox** (nunca el original), con **dry-run + confirmación + log de auditoría** y backup fechado previo (ver [`09`](09-seguridad-y-respaldo.md)).
- 🔒 **Nunca imprimir credenciales ni PII** en respuestas/logs/ejemplos: `CLAVE SII`, `Previred`, `RUT`, `RUT RL`, `email`, `Whatsapp`. Pero **no se redactan ni se borran** de la base: son insumo legítimo del login al SII (D17). Se evita exponerlas, no almacenarlas.
- 🧮 **La IA no calcula montos.** Los números del F29 salen de funciones deterministas y verificables; el LLM solo **explica** y **detecta** anomalías (D1).
- **Idioma:** español · **MVP-first** · **docs granulares** · **el usuario valida** antes de cambios grandes.

## Datos duros / invariantes (para no alucinar)

> Constantes y referencias estables. Verifica contra la fuente citada antes de usarlas en producción.

**Tasas y caso `CLIENTE1` (período ABRIL) — el *golden test*:**

| Magnitud | Valor |
|---|---|
| Tasa IVA | 19% |
| P1 · Débito (ventas) | $462 |
| P2 · Crédito (compras) | −$260.143 |
| P3 · Remanente anterior (casilla 504 de la propuesta) | −$158.117 |
| P4 · IVA determinado | −$417.798 (negativo ⇒ no paga IVA; queda a favor → 77) |
| BI del PPM (Monto Neto + Monto Exento de ventas) | $2.432 |
| Tasa PPM (casilla 115, por contribuyente; caso) | 0,125% |
| P5 · Otros impuestos | PPM $3 · honorarios 14,5% → $0 · imp. único → $0 |
| P6 · Total a pagar | **$3** |

**Códigos F29 usados** (verificar el resto en la tarea 1.4): `62` PPM neto · `48` ret. imp. único · `151` ret. honorarios (Ley 21.133) · `504` remanente que entra · `77` remanente que sale · `115` tasa PPM · `538` total débitos · `537` total créditos.

**Notion — IDs estables:**

| Base | database ID | data source |
|---|---|---|
| General Customers Data (original — **NO tocar**) | `1a23f5e4-0223-46a6-9ad5-16ea823b64ba` | `690945e4-220a-48c3-a888-7fe9ae242d55` |
| General Customers Data - AuditAI (**sandbox**) | `16f12147-b3ea-8354-872b-814f104871b7` | `4ff12147-b3ea-82f4-98dd-072067524cdc` |
| Contable Mayo (aux) | `37212147-b3ea-80fa-ab06-cfd9782372a9` | `fdb12147-b3ea-820b-8595-07535e078336` |
| RRHH JUNIO 2026 (aux) | `38712147-b3ea-80f9-9484-e0ad99c94a26` | `9c512147-b3ea-8256-a570-871254c13b3d` |
| Tickets - Servicios (aux) | `16912147-b3ea-82bc-a491-814729bcca4c` | `9d312147-b3ea-83bf-b111-877c7b24db75` |

Parent de ambas GCP: `dd47681b-89fe-4f49-bea3-f8038d571d44`. Plan workspace: **Business** (historial 90 d, papelera 30 d). Snapshot base: `backups/general-customers-data/2026-06-30_all.csv` (171 filas, vista "All").

**Completitud de la base — evolución:**
- *Baseline (jun-2026, 171 clientes):* 12 RUTs problemáticos · 20 sin `CLAVE SII` · 100 sin `email` · 158 listos para SII.
- **Actual (02-jul-2026, post-barrido Febrero): 331 clientes** — 330 con `RUT` válido (99,7%) · **1 sin RUT** (solo `Steven` ID 48) · 324 con `CLAVE SII` · **324 listos para automatización SII (97,9%)** · email 88 (secundario) · 19 marcados `Email por revisar`. (334 tras Fase C; −3 retirados a "Descartados AuditAI"). Barrido Febrero (02-jul tarde): 1/7 claves rescatada (Escuela de Voces Manuela); 6/7 + RUT de Steven no aparecen en Notion → escalados al usuario (ver [`15`](15-barrido-bases-contables-mensuales.md) §3).

**Esquema:** 22 columnas en el **original** · **28 en la sandbox** (post-D19/D23 + `Email por revisar`, 02-jul-2026) — tipos en [`08`](08-notion-general-customers-data.md) y corregido en [`12`](12-fase1-plan-detallado.md): credenciales/PII (`CLAVE SII`, `Previred` [text en original; **status** en sandbox], `USUARIO-Previred` 🆕 sandbox, `CLAVE-Previred` 🆕 sandbox, `RUT`, `RUT RL`, `email`, `Whatsapp`) · identificación (`w` title, **`ID`** (unique_id), `Nº`, `CRM`, `Rubro`, `Segmentación`, `Ciudad`, `Municipalidad`) · gestión (`Adviser Accounting`, `Adviser RR.HH`, `1ra Factura o Propuesta`, `Respaldo Anual`) · enlaces/otros (`Drive Empresa`, `Propuesta de Servicio`, `Column`, `Texto`) · **trazabilidad** (`Origen` 🆕, `Origen Contable Mayo` 🆕, `RRHH Origen`).

**Stack (D10 / [`06`](06-stack-tecnico.md)):** Python 3.12+ · uv · Ruff · mypy --strict · Polars · Pandera · Pydantic v2 · `decimal.Decimal` (dinero, **nunca `float`**) · pytest.

## Leyenda

- `[x]` completado y verificado · `[ ]` pendiente · 🟡 = parcial (subtareas mixtas).
- **Estado por fase:** ✅ completa · 🟡 en curso · ⬜ no iniciada.
- 🔒 = toca credenciales/PII → aplica [`09-seguridad-y-respaldo.md`](09-seguridad-y-respaldo.md) y regla de oro #2 de [`../../AGENTS.md`](../../AGENTS.md).
- 🧮 = lógica determinista (D1): nunca la calcula un LLM.

## Resumen de avance

| Fase | Nombre | Estado | Progreso |
|---|---|:--:|:--:|
| 0 | Cimientos y red de seguridad | ✅ | completa |
| 1 | Centralizar la data + formalizar reglas | 🟡 | en foco |
| 2 | Motor de cálculo (MVP) | ⬜ | no iniciada |
| 3 | Ingesta real desde el SII | ⬜ | no iniciada |
| 4 | Auditoría / conciliación | ⬜ | no iniciada |
| 5 | Capa de IA | ⬜ | no iniciada |
| 6 | BD especializada y producto multi-cliente | ⬜ | no iniciada |
| **N** | **Automatización Notion + correo F29 / multi-automatización RRHH + Tickets** (foco, [`23`](23-automatizacion-notion-contable-correo.md) / [`24`](24-arquitectura-multi-automatizacion.md)) | 🟡 | **E2E F29 exitoso** · arquitectura multi-handler definida · RRHH en implementación · Tickets planificado |

---

## Fase 0 — Cimientos y red de seguridad ✅

**Objetivo:** tener un caso real de referencia, entender el dominio y montar la red de seguridad antes de tocar datos. **Criterio de aceptación:** cualquier persona nueva entiende el proyecto leyendo `docs/`; los datos del cliente están respaldados.

### 0.1 · Caso de referencia y dominio
- [x] Caso de ejemplo `CLIENTE1`
  - [x] Planilla con fórmulas reales: [`PRUEBA1.xlsx`](../../PRUEBA1.xlsx)
  - [x] Exportación CSV (solo valores): [`PRUEBA1.csv`](../../PRUEBA1.csv)
  - [x] Formulario oficial de referencia (~140 códigos): [`F29.pdf`](../../F29.pdf)
  - [x] *Golden test* fijado: total **$3**, remanente **−$158.117** (P1 $462 · P2 −$260.143 · P3 −$158.117 · P4 −$417.798)
- [x] Descripción original de la lógica de las 6 partes: [`../../CONTEXT.md`](../../CONTEXT.md)

### 0.2 · Documentación
- [x] Arquitectura objetivo + diagrama de flujo: [`../ARQUITECTURA.md`](../ARQUITECTURA.md)
- [x] Hoja de ruta con criterios de aceptación: [`../ROADMAP.md`](../ROADMAP.md)
- [x] Documentación dev `00`–`10` (introducción, dominio, estado, estado del arte, glosario, decisiones, stack, flujo, Notion, seguridad, fuentes auxiliares)
- [x] Onboarding para agentes IA: [`../../AGENTS.md`](../../AGENTS.md)
- [x] Este checklist maestro (`11`)
- [x] Presentación de cliente (no técnica) con demo interactiva: [`../../presentacion.html`](../../presentacion.html)
  - [x] Secciones de seguridad, avance real y estrategia en 2 etapas
  - [x] Pulido técnico: SEO/OpenGraph, accesibilidad (aria), estilos de impresión/PDF
  - [x] Sección visual del checklist maestro (espejo de este documento, en `presentacion.html`)

### 0.3 · Conexión y mapeo de Notion 🔒
- [x] Conectar Notion a Claude Code (MCP, [`../../.mcp.json`](../../.mcp.json)) y a opencode (token local, [`../../opencode.json`](../../opencode.json))
- [x] Política de acceso escalonado definida (lectura por defecto; escritura con autorización + sobre copia) — D14
- [x] Mapear esquema de `General Customers Data` (22 columnas): [`08-notion-general-customers-data.md`](08-notion-general-customers-data.md)
- [x] Medir completitud: 171 clientes · 10 sin `RUT` · 20 sin `CLAVE SII` · ~100 sin `email`
- [ ] Obtener número exacto de "listos para SII" (`RUT` + `CLAVE SII`) — bloqueado por *rate-limit* Notion 429, reintentar

### 0.4 · Red de seguridad (3 capas) 🔒
- [x] Capa 3 — confirmar plan Notion **Business** (historial 90 d, papelera 30 d)
- [x] Capa 2 — snapshot CSV base fechado: `backups/general-customers-data/2026-06-30_all.csv` (171 registros, vista "All")
- [x] Capa 1 — crear sandbox `General Customers Data - AuditAI` (ID `16f12147-…`, 171 filas, copia fiel)
- [x] Documentar protocolo obligatorio (dry-run, confirmación, log de auditoría): [`09-seguridad-y-respaldo.md`](09-seguridad-y-respaldo.md)
- [x] Identificar 3 fuentes auxiliares de data faltante: [`10-fuentes-auxiliares-notion.md`](10-fuentes-auxiliares-notion.md)

### 0.5 · Control de versiones *(cierre de Fase 0)* ✅
- [x] `git init` del repositorio (rama `main`)
- [x] `.gitignore` que excluye `backups/` y cualquier export con credenciales/PII (D17) + `.gitattributes` (LF)
- [x] Primer commit del estado actual (verificado: `backups/` NO incluido)

---

## Fase 1 — Centralizar la data + formalizar las reglas 🟡  *(EN FOCO)*

> **🎯 Objetivo principal reforzado:** no es solo recuperar `RUT`/`CLAVE SII`. Es **completar, corregir y enriquecer toda la base de datos central** `General Customers Data`, usando `Contable Mayo` y `RRHH JUNIO 2026` como fuentes. Esto incluye: recuperar campos faltantes, corregir RUTs inválidos, resolver duplicados, llenar advisers, completar credenciales `Previred`, y agregar registros de clientes que existen en las fuentes pero no en la base central.

**Objetivo:** recuperar/completar la base central en Notion (Etapa 1 de D11) y convertir el conocimiento implícito de las fórmulas en una especificación explícita. **Criterio de aceptación:** la base tiene la data faltante recuperada, está depurada de duplicados, validada y trazable; un desarrollador puede implementar el cálculo sin abrir el Excel.

> 🔬 **Plan detallado de esta fase** (investigación, mapeo de elementos, algoritmos, catálogo oficial de documentos del SII, límites reales de la API de Notion): **[`12-fase1-plan-detallado.md`](12-fase1-plan-detallado.md)**. Las tareas de abajo son el índice; el `12` tiene el *cómo*.

> ⛔ **Secuencial, NO en paralelo (D18):** primero el **Frente A (centralización, §1.1–1.3)** al 100% y verificado — hasta tener la base de datos **final y robusta** —; **recién entonces** el **Frente B (reglas, §1.4–1.6)**. La base de datos es la prioridad: todo el esfuerzo va ahí primero.

#### Frente A · AHORA — construir y fortalecer la base de datos 🗂️

### 1.1 · Mapear las 3 fuentes auxiliares 🔒 ✅
- [x] `Contable Mayo` — esquema obtenido por API (`retrieve-a-data-source` + query paginada)
- [x] `RRHH JUNIO 2026` — esquema obtenido por API
- [x] `Tickets - Servicios` — esquema obtenido por API y **descartada** como fuente de GCD
- [x] Para cada fuente, identificar qué columna aporta a cada campo faltante (`RUT`, `CLAVE SII`, `email`, `Previred`, `Whatsapp`, `Adviser …`)
- [x] Identificar propiedad de agrupación de Contable Mayo (select sin nombre / "Dinámico de grupo")

### 1.2 · Cruzar fuentes auxiliares ↔ sandbox 🔒 ✅
- [x] Determinar el solape cliente-a-cliente (qué % de los 171 aparece en cada fuente)
- [x] **Algoritmo de matching** implementado y ejecutado (llave de cruce):

  ```text
  para cada cliente C en sandbox:
      candidatos ← fuente.where(RUT_normalizado == C.RUT_normalizado)   # 1º por RUT validado (módulo 11)
      si candidatos vacío:
          candidatos ← fuente.where(norm(nombre) == norm(C.w))          # 2º por nombre normalizado
      si candidatos == 1: match
      si candidatos > 1:  marcar AMBIGUO → revisión humana
      si candidatos == 0: marcar SIN_FUENTE
  norm(s) = trim + minúsculas + sin tildes + colapsar espacios + sin sufijos societarios (SPA/LTDA/EIRL/SA)
  ```

- [x] Conteos de solape reales:
  - Sandbox ↔ Contable Mayo: **112** coincidencias por RUT válido
  - Sandbox ↔ RRHH JUNIO 2026: **16** coincidencias por RUT válido
  - Contable Mayo ↔ RRHH JUNIO 2026: **16** coincidencias
- [x] Detectar duplicados: 1 RUT duplicado en sandbox, 1 en Contable Mayo
- [x] Detectar registros nuevos: **168** en Contable Mayo, **2** en RRHH

### 1.3 · Volcar data faltante hacia la sandbox 🔒  *(nunca al original — D15)*
> **Alcance ampliado:** el volcado no es solo `RUT`/`CLAVE SII`/`email`. Incluye también `Previred`, `Adviser Accounting`, `Adviser RR.HH`, corrección de RUTs inválidos y, si el usuario lo aprueba, **agregar registros nuevos** desde las fuentes.

- [x] **Fase A — Limpieza pre-volcado** ✅ (01-jul-2026, detalle en [`12`](12-fase1-plan-detallado.md))
  - [x] Backup fresco de la sandbox (`backups/general-customers-data/2026-07-01_sandbox_pre-fase-A.csv`)
  - [x] RUT duplicado en la sandbox (`SOCIAL UP SPV I/II`): se mantienen como 2 clientes separados, RUT sin tocar hasta consulta al cliente final
  - [x] RUTs problemáticos: **7/12 corregidos** desde Contable Mayo (log en `log-auditoria-volcado.csv`); 5 quedan pendientes de consulta al cliente final
  - [x] RUT duplicado en Contable Mayo (`ADMINISTRADORES CHILE`): no se toca la fuente; se deduplica al importar en Fase C
- [x] **Fase B — Enriquecimiento de registros existentes** ✅ (01-jul-2026: 151 cambios en 103 páginas — `RUT` 166/171, `CLAVE SII` 162/171, `email` 84/171; `Previred` resuelto vía relación+rollup a RRHH sin exponer credenciales; `Adviser Accounting` 90 escrituras, `Adviser RR.HH` 10 escrituras). Log completo en `backups/general-customers-data/log-auditoria-volcado.csv`.

  ```text
  precondición: backup CSV de hoy existe y está a salvo
  para cada (cliente, campo_faltante) detectado:
      valor ← fuente_auxiliar[cliente][campo]
      si sandbox[cliente][campo] ya tiene valor: SKIP (no sobreescribir, salvo decisión caso a caso)
      si match es AMBIGUO: SKIP → cola de revisión humana
      registrar en diff: (ID | RUT, campo, "" → valor, fuente)
  mostrar diff COMPLETO al usuario        # DRY-RUN, sin aplicar
  esperar confirmación explícita
  aplicar escritura por clave estable (ID de tipo unique_id o RUT; nunca por posición)
  escribir log de auditoría: (id, columna, valor_anterior → valor_nuevo, timestamp, fuente)
  ```

  **Campos recuperados en registros existentes — ✅ ejecutado 01-jul-2026 (regla D21: la fuente auxiliar predomina ante conflicto, no solo vacíos):**
  - [x] RUT: **7** recuperados/corregidos (Fase A, Contable Mayo) — 5 quedan pendientes de consulta al cliente final
  - [x] CLAVE SII: **31** escritos (Contable Mayo) — más que la estimación inicial de 7, por la regla D21
  - [x] email: **15** escritos (Contable Mayo) — más que la estimación inicial de 12
  - [x] Previred (`USUARIO`/`CLAVE`): resuelto **sin extracción directa** — relación Notion `RRHH Origen` + columnas rollup `USUARIO-Previred`/`CLAVE-Previred` (16 clientes enlazados); el valor nunca pasa por el agente. `DTGO` sigue sin mapear.
  - [x] Previred (estado): **5** cambios reales aplicados
  - [x] Adviser Accounting: **90** escrituras (9 llenaban vacío + 81 sobrescribieron por D21)
  - [x] Adviser RR.HH: **10** escrituras (3 llenaban vacío + 7 sobrescribieron por D21)
- [x] **Fase C — Agregar registros nuevos** ✅ *(ejecutado 01-jul-2026 · detalle en [`13-fase-c-volcado-nuevos-registros.md`](13-fase-c-volcado-nuevos-registros.md))*
  - [x] Plan de ejecución, algoritmo y validaciones documentados en [`13-fase-c-volcado-nuevos-registros.md`](13-fase-c-volcado-nuevos-registros.md)
  - [x] Backup fresco de la sandbox antes de la escritura → `2026-07-01_sandbox_pre-fase-C.csv`
  - [x] Dry-run generado y revisado → 163 registros nuevos (161 Contable Mayo + 2 RRHH)
  - [x] Agregar registros nuevos a la sandbox → **163/163 creados exitosamente**
  - [x] Corrección relación RRHH para los 2 registros de RRHH
  - [x] Re-medir completitud post-volcado → **334 registros**, 329 RUTs válidos, 322 listos para SII
- [x] Validar con Pandera/Pydantic **post-volcado** → 334 registros validados; Pandera pasa; 19 errores Pydantic (todos emails inválidos)
- [x] Re-medir completitud post-volcado → **334 registros**, 329 RUTs válidos, 322 listos para SII
- [x] Identificar específicamente los **12 clientes sin `CLAVE SII`** post-volcado
- [x] **Trazabilidad de origen (D23)** — crear y poblar `Origen` (select) + `Origen Contable Mayo` (relation) en la sandbox → **334/334 con Origen**, 161/161 con relación a Contable Mayo
- [ ] Resolver casos anómalos identificados (ver [`14-construccion-dataset-y-anomalias.md`](14-construccion-dataset-y-anomalias.md)):
  - [x] **Decisiones de cierre resueltas (02-jul-2026, ver [`14`](14-construccion-dataset-y-anomalias.md) §4):**
    - [x] Clientes sin RUT: XIT recuperado; `Sergio ??`/`Patricia`/`Zsabesky` retirados a "Descartados AuditAI"; **`Steven` queda pendiente** (único sin RUT)
    - [x] Duplicado `SOCIAL UP SPV I/II`: se mantiene (mismo cliente, intencional)
    - [x] 18–19 emails inválidos: etiquetados con checkbox `Email por revisar` (no se limpian por ahora; secundario)
    - [x] Campos sin fuente: quedan opcionales para el MVP
  - [ ] **Único pendiente del gate Frente A:** rescatar el `RUT` de `Steven` (barrido de meses [`15`](15-barrido-bases-contables-mensuales.md) o consulta al adviser)

#### Frente B · EN PAUSA — arranca al cerrar el Frente A (gate D18) 📐
> **Gate:** el Frente A debe estar terminado (fuentes cruzadas · data faltante recuperada · sin duplicados · validación en verde · base verificada y trazable) antes de trabajar §1.4–1.6. Lo marcado `[x]` abajo es **adelanto de investigación**, no trabajo activo del Frente B.

### 1.4 · Diccionario de códigos del F29 🧮
> ⚠️ **No confundir 3 sistemas de códigos** (ver [`12`](12-fase1-plan-detallado.md) §B0): tipo de documento DTE · código de impuesto/recargo (Tabla 7) · casilla del F29. En `CLIENTE1` hay dos "48" distintos: documento tipo 48 (Comprobante de Pago Electrónico) y casilla F29 48 (ret. imp. único).
- [ ] Construir tabla `código → significado → de qué documento se alimenta` (detalle en [`12`](12-fase1-plan-detallado.md) §B2)
  - [x] Confirmados contra SII: **502/503** (facturas emitidas + débito), **519/520** (facturas recibidas + crédito), **538** (total débitos), **537** (total créditos), **89** (IVA determinado), **77** (remanente)
  - [ ] Verificar **62** (PPM), **48** (ret. imp. único), **151** (ret. honorarios) contra normativa
  - [ ] Extender al resto de los ~140 códigos del [`F29.pdf`](../../F29.pdf) (marcar `verificar`)

### 1.5 · Catálogo de tipos de documento 🧮
- [x] Catálogo oficial capturado del SII (Formato IECV §4) → [`12`](12-fase1-plan-detallado.md) §B1
- [ ] Fijar el mapeo cada tipo → parte del F29:
  - [ ] Factura electrónica 33 → P1/P2 (débito/crédito) · Factura de compra 46 → retención
  - [ ] **Comprobante de pago electrónico (doc 48)** → P1 (genera el débito de `CLIENTE1`)
  - [ ] Nota de crédito 61 → rebaja · Nota de débito 56 → aumenta · DIN 914 → P2 (crédito)
  - [ ] Marcar los "solo resumen" (35, 38, 39, 41, 47, 48, …) — entran agregados, no uno a uno

### 1.6 · Especificación de las 6 partes (entrada → fórmula → salida) 🧮
- [ ] Documentar P1–P6 como reglas formales (insumos, fórmula, salida, código F29 asociado)
- [ ] Especificar explícitamente la **regla condicional de P6** (ver Algoritmo A1 abajo)

---

## Fase 2 — Motor de cálculo (MVP) ⬜ 🧮

**Objetivo:** reproducir la planilla en código, determinista y sin intervención manual. **Criterio de aceptación:** el script reproduce el resultado de `CLIENTE1` **exactamente** ($3 / −$158.117).

### 2.1 · Entorno de desarrollo (stack D10 / doc 06)
- [ ] Inicializar proyecto con **uv** + `pyproject.toml` (Python 3.12+)
- [ ] Configurar **Ruff** (lint + formato, incluir reglas `S`/Bandit) y **mypy --strict**
- [ ] Configurar **pytest** (+ pytest-cov)
- [ ] Añadir dependencias: **Polars**, **Pandera**, **Pydantic v2**

### 2.2 · Modelo de datos (multiempresa desde el MVP — D6)
- [ ] Definir modelos Pydantic: `Documento`, `LibroVentas`, `LibroCompras`, `PeriodoEmpresa`
- [ ] Cada insumo lleva `empresa_id` + `periodo` (cálculo por empresa-período)
- [ ] Esquemas Pandera (contrato de datos): columnas obligatorias, tipos, montos ≥ 0, sin nulos

### 2.3 · Aritmética de dinero (precisión — D1)
- [ ] Usar `decimal.Decimal` para toda la aritmética tributaria (**nunca `float`**)
- [ ] Definir regla de redondeo explícita a peso entero (CLP sin centavos)
- [ ] Patrón: DataFrame (Polars) para ingerir/agrupar/contar; `Decimal` para los totales finales

### 2.4 · Núcleo: las 6 partes (ver Algoritmo A1 · rutas SII validadas GCP en doc 17 §3)
- [ ] P1 · Débito fiscal = Σ «Monto IVA» de la pestaña **VENTA** del RCV (NC restan)
- [ ] P2 · Crédito fiscal = −Σ «IVA Recuperable» de la pestaña **COMPRA** del RCV (NC restan)
- [ ] P3 · Remanente = casilla **504** de la **propuesta del F29** (puede no estar ⇒ 0), en negativo
- [ ] P4 · IVA determinado = P1 + P2 + P3 (positivo = paga IVA; negativo = remanente a favor → 77)
- [ ] P5 · Otros impuestos = PPM + ret. honorarios + ret. imp. único
  - [ ] PPM: `BI = Σ(«Monto Neto» + «Monto Exento») de VENTA (NC restan)`; `ppm = BI × tasa`, **tasa = casilla 115** de la propuesta (0,125% en el caso)
  - [ ] ret. honorarios: «Retención de terceros», informe anual de boletas recibidas, fila del mes anterior
  - [ ] ret. imp. único: Notion RRHH `IMPUESTO ÚNICO` (transcripción, no cálculo)
- [ ] P6 · Total = **si P4 > 0:** P4 + P5; **si P4 ≤ 0:** solo P5
- [ ] Mapear el resultado a los códigos F29 (consume el diccionario de 1.4)

### 2.5 · Golden test
- [ ] Test que carga `CLIENTE1` y verifica P1–P6 == ($462, −$260.143, −$158.117, −$417.798, $3, $3)
- [ ] Tests de borde: P4 exactamente 0; remanente 0; sin documentos; débito > crédito (paga IVA)

### 2.6 · CLI (MVP = librería + CLI, sin web/BD — YAGNI)
- [ ] Comando que recibe libros + remanente y emite F29 + informe
- [ ] Capa de acceso a datos abstracta (para migrar Notion → BD sin reescribir — D11)

---

## Fase 3 — Ingesta real desde el SII ⬜

**Objetivo:** dejar de tipear datos a mano. **Criterio de aceptación:** se carga un RCV/XLSX real y el motor calcula sin edición manual.

### 3.1 · Parser del RCV / XLSX del SII (D7)
- [ ] Conseguir una **muestra real** del XLSX del SII (pendiente — Pregunta abierta #5)
- [ ] Parsear CSV (separador `;`) y XLSX (motor `calamine` de Polars u openpyxl)
- [ ] Normalización: UTF-8 (arreglar `mi�rcoles`, `N�`), formatos de monto y fecha chilenos

### 3.2 · Validaciones de ingesta (Pandera)
- [ ] Detectar documentos duplicados, montos negativos inesperados, tipos desconocidos
- [ ] Rechazar/avisar en la ingesta, no en el resultado final

### 3.3 · Automatización SII: el trigger (D12) 🔒  *(algoritmo incompleto — ver A2)*
- [ ] Completar los pasos intermedios del algoritmo (hoy solo inicio y fin definidos)
- [ ] Definir login persona vs. empresa (con/sin Clave Única)
- [ ] **Manejo seguro de credenciales** (Pregunta abierta #3): cifrado en reposo, gestor de secretos, mínimo privilegio, trazabilidad de acceso; no texto plano

---

## Fase 4 — Auditoría / conciliación ⬜ 🧮

**Objetivo:** el núcleo de "Audit". **Criterio de aceptación:** ante una diferencia inyectada a propósito, el sistema la detecta y la localiza.

- [ ] Cargar la propuesta del F29 del SII como **segundo origen** (D2: contraparte, no verdad absoluta)
- [ ] **Algoritmo de conciliación (ver A3):** comparar cálculo propio vs. propuesta, código por código
- [ ] Informe de discrepancias: código, monto esperado, monto SII, diferencia, documento probable causante
- [ ] **Control de anomalía del remanente (D9/D13 — ver A4):** sin umbral fijo; alerta solo ante cambio brusco/atípico respecto a la variación natural de la UTM
- [ ] Trazabilidad: cada cifra de salida rastreable hasta su documento de origen

---

## Fase 5 — Capa de IA ⬜

**Objetivo:** el "AI" de AuditAI (la IA **explica/detecta**, no calcula montos — D1). **Criterio de aceptación:** el sistema explica una discrepancia de forma que un contador la acepte sin rehacer el cálculo.

- [ ] Explicación en lenguaje natural de cada discrepancia ("la diferencia del código 77 viene de un remanente no arrastrado")
- [ ] Detección de anomalías (facturas atípicas, saltos de patrón mes a mes)
- [ ] Sugerencias de corrección
- [ ] Garantía de aislamiento: la IA nunca determina el monto del impuesto

---

## Fase 6 — BD especializada y producto multi-cliente ⬜

**Objetivo:** pasar de prototipo a herramienta usable. **Criterio de aceptación:** un contador gestiona varios clientes y períodos sin tocar planillas.

### 6.1 · Migración a BD especializada (Etapa 2 de D11)
- [ ] Decidir tecnología (Supabase / PostgreSQL u otra — Pregunta abierta #4)
- [ ] Migrar desde Notion reutilizando la capa de acceso a datos (sin reescribir el motor)
- [ ] Stack de servicio cuando aplique: FastAPI + PostgreSQL + SQLAlchemy 2.0

### 6.2 · Producto
- [ ] Soporte multi-empresa completo (ya previsto en el modelo — D6)
- [ ] Historial mensual y arrastre automático del remanente
- [ ] Interfaz (web o escritorio)
- [ ] Eventual integración con API del SII

---

## Algoritmos de referencia

### A1 · Motor de cálculo — las 6 partes 🧮
```text
# 🔄 Actualizado con el feedback de los expertos GCP (P1–P6, jul-2026).
#    Rutas de extracción reales en el SII: doc 17 §3.
entrada: rcv_ventas (pestaña VENTA), rcv_compras (pestaña COMPRA),   # RCV, período = mes anterior
         remanente_anterior (casilla 504 de la propuesta F29; puede no existir),
         tasa_ppm (casilla 115 de la propuesta F29, por contribuyente),
         ret_honorarios («Retención de terceros», informe anual boletas recibidas, fila mes anterior),
         ret_impuesto_unico (Notion RRHH <Mes>: `IMPUESTO ÚNICO`)
# todo en Decimal; redondeo final a peso entero
# notas de crédito: RESTAN en ambos lados (ventas y compras)

P1 = Σ monto_iva(fila) para fila en rcv_ventas          # columna «Monto IVA» (NC restan) — débito (≥ 0)
P2 = -Σ iva_recuperable(fila) para fila en rcv_compras  # columna «IVA Recuperable» (NC restan) — crédito (≤ 0)
P3 = -abs(remanente_anterior) si existe casilla 504, si no 0   # saldo a favor (≤ 0), ya reajustado UTM
P4 = P1 + P2 + P3                                       # > 0: IVA a pagar · ≤ 0: remanente a favor

BI  = Σ (monto_neto(fila) + monto_exento(fila)) para fila en rcv_ventas   # NC restan
PPM = round(BI * tasa_ppm)                              # casilla 62
P5 = PPM + ret_honorarios + ret_impuesto_unico

if P4 > 0:
    P6 = P4 + P5            # paga IVA + otros impuestos
else:
    P6 = P5                # NO paga IVA; remanente -P4 se arrastra (casilla 77); otros impuestos se pagan igual
    remanente_siguiente = abs(P4)

salida: {P1..P6, remanente_siguiente, mapeo_codigos_F29}
```
> ⚠️ La rama `else` (P4 ≤ 0) es el error manual más común y la razón de ser de la auditoría.

### A2 · Trigger de ingesta SII (D12) 🔒  *(incompleto — faltan pasos intermedios)*
```text
1. leer fila del cliente en Notion (registro de clientes)
2. extraer credenciales: RUT + contraseña (Clave Única)        # 🔒 nunca imprimir
3. determinar tipo: persona | empresa  → login con/sin Clave Única
4. iniciar sesión en el SII
5. … (pasos intermedios por definir) …
6. descargar XLSX del cliente   = TRIGGER del flujo principal
7. entregar el archivo a la etapa de normalización/validación
```

### A3 · Conciliación contra la propuesta del SII 🧮
```text
para cada código c en F29:
    propio ← calculo_propio[c]
    sii    ← propuesta_sii[c]
    if propio != sii:
        diff ← propio - sii
        causa ← rastrear_documentos(c)        # qué doc(s) alimentan ese código
        reportar(c, esperado=propio, sii=sii, diferencia=diff, causa)
# D2: el cálculo propio es la fuente primaria; el SII es contraparte, no verdad absoluta
```

### A4 · Control de anomalía del remanente (D9/D13) 🧮
```text
remanente_sii      ← valor del SII (ya reajustado por variación UTM)
remanente_esperado ← remanente_historico_reajustado_por_UTM
usar remanente_sii como insumo del cálculo
if |remanente_sii - remanente_esperado| es "brusco/atípico":   # sin umbral % fijo
    marcar ANOMALÍA (revisión humana)
else:
    variación considerada normal (sigue la UTM)
```

---

## Preguntas abiertas que bloquean tareas

Trasladadas de [`05-decisiones-y-preguntas.md`](05-decisiones-y-preguntas.md); cada una bloquea la tarea indicada:

- [ ] #2 — Algoritmo completo del trigger SII (bloquea 3.3 / A2)
- [ ] #3 — Manejo seguro de credenciales de clientes (bloquea 3.3)
- [ ] #4 — Tecnología de la BD especializada (bloquea 6.1)
- [ ] #5 — Esquema real del XLSX del SII: falta muestra (bloquea 3.1)
- [x] #6 — Esquema de las 3 fuentes auxiliares (resuelto en [`12`](12-fase1-plan-detallado.md) §A1)
- [x] #7 — Solape cliente-a-cliente fuente↔sandbox (resuelto en [`12`](12-fase1-plan-detallado.md) §A1b)
- [x] Número exacto de "listos para SII" (resuelto: **158** actuales / **165** post-volcado)
- [x] **Decisión usuario (D19):** mapeo `USUARIO`/`CLAVE` de RRHH → `USUARIO-Previred`/`CLAVE-Previred` (nuevas) + `RRHH Origen` (relation) + `Previred` → status. **Ejecutado en la sandbox** (esquema 22→27 columnas tras D23). `DTGO` sin mapear.
- [x] **Decisión usuario (D23):** trazabilidad de origen — columnas `Origen` (select) + `Origen Contable Mayo` (relation). **Ejecutado en la sandbox**.
- [x] **Decisión usuario (D20):** Fase A+B+C completa — se agregan los 170 registros nuevos (sandbox pasará a ~341).
- [x] **Decisión usuario (D21):** Contable Mayo/RRHH predominan siempre sobre la sandbox ante conflicto de valor (regla general, no solo advisers) — reemplaza la regla de "solo llenar vacíos".
- [x] **Decisión usuario (D22):** sin exclusión por status/etiqueta al agregar los 168 registros nuevos.

---

## Frente N — Automatización de Notion + multi-automatización 🟡 *(foco, jul-2026)*

> **Cambio de foco:** el SII se **pausa** (login bloqueado por F5 — ver [`21`](21-resultado-spike-f29.md);
> la vía correcta es certificado digital, [`22`](22-via-oficial-certificado-digital-api-sii.md), pendiente
> de gestión de negocio). Mientras, el foco es **automatizar páginas de Notion**: primero
> **Contable** (F29, ya operativa), luego **RRHH JUNIO 2026** (en implementación), y después
> **Tickets - Servicios** (planificado). Todo desde un backend centralizado con handlers
> modulares. Arquitectura multi-automatización en
> [`24-arquitectura-multi-automatizacion.md`](24-arquitectura-multi-automatizacion.md).
>
> 🎉 **Hito (07-jul-2026): E2E del correo F29 exitoso.** Botón en Notion → webhook → backend
> Flask → SMTP Gmail → correo al cliente + write-back Status = "1) Enviado y Pendiente".
> Fila de prueba `ZZ_TEST AuditAI` en Contable Junio. SMTP desde `sebastianrobles@inversoragcp.com`.
>
> 🆕 **Hito (09-jul-2026): arquitectura multi-handler definida.** Se crea el patrón de handlers
> (`handlers/f29.py`, `handlers/rrhh.py`, `handlers/tickets.py`) y el documento
> [`24`](24-arquitectura-multi-automatizacion.md) con el plano de la expansión.

### N.1 · Plantilla del correo F29 ✅
- [x] `notion_automation/email_templates/f29_email.html` (email-safe, tablas + estilos inline, **inline CID** para logo y firma — Gmail bloquea `data:` URIs)
- [x] `notion_automation/email_templates/f29_email.txt` (respaldo en texto plano)
- [x] `notion_automation/email_templates/README.md` (variables, variantes, 4 reglas del usuario)
- [x] `notion_automation/email_templates/preview-correo-f29.html` (vista previa interactiva con
      logo GCP incrustado, 3 toggles para los bloques opcionales y 3 variantes de resultado)
- [x] **4 reglas del usuario (07-jul-2026) aplicadas:**
  - [x] **(1) Asunto fijo** `"Asesoría Honorario"` (sin variables).
  - [x] **(2) Fecha límite sin paréntesis** — solo `lunes 22 de junio de 2026.`, sin texto redundante.
  - [x] **(3) Info adicional flexible** — bloque opcional (si la celda está vacía no aparece) y
        variable (no siempre es el remanente; GCP escribe lo que corresponda).
  - [x] **(4) Honorarios + datos de transferencia** — si el cliente debe honorarios (> 0), el bloque
        incluye los datos bancarios de GCP: **Banco Santander · Cuenta Corriente N° 0-000-8577678-9
        · RUT 76.976.672-3 · Razón Social Inversora GCP Ltda**.
- [x] Lógica de **fecha límite** con feriados chilenos (`FERIADOS_CL`, fuente `date.nager.at`):
      día 20 del mes siguiente, trasladado al siguiente día hábil si es fin de semana o feriado.
- [x] `email_sender.py` carga la plantilla y reemplaza `{{marcadores}}`; funciones
      `_bloque_fecha`/`_bloque_honorarios`/`_bloque_info`. **Envío por SMTP Gmail** (no SendGrid)
      con `MIMEMultipart("related")` + nested `"alternative"` para inline CID.
- [x] **Orden del correo (feedback GCP):** (1) saludo+contexto, (2) monto IVA (card navy),
      (3) fecha límite, (4) info adicional, (5) honorarios + datos transferencia, (6) cierre.
      Sin el texto "Es el pago…" en honorarios. "Datos para la transferencia" destacado.

### N.2 · Backend, columnas y botón — ✅ E2E verificado
- [x] Fase 0: `notion_automation/` con venv, deps (`flask`, `requests`, `python-dotenv`,
      `jinja2`) y `.env` (secretos fuera de git). `.gitignore` excluye `asesores_smtp.json` y `data/`.
- [x] `notion_client.py` (helpers REST + `find_page_by_rut()`), `email_sender.py` (SMTP Gmail +
      inline CID + env var fallback `_cargar_asesores`), `app.py` (Flask `host="0.0.0.0"`,
      `--test` + `--test-rut`, logging a `auditai.log` sin PII) escritos y arrancando.
- [x] **`asesores_smtp.json`** (gitignored): 5 asesores mapeados. **Solo Sebastián Robles** tiene
      App Password + `firma_png: "firmas/firma-sebastian-robles.png"` (los 4 restantes pendientes).
- [x] Backup previo: `backups/contable-junio/2026-07-07_pre-columnas.csv` (288 filas).
- [x] Columnas nuevas en Contable Junio creadas: `Honorarios Pendientes` (number, vía API),
      `Info Adicional` (rich_text, vía API). `Enviar Correo F29` (button) se creó desde la UI
      (la API de Notion **no soporta crear propiedades tipo `button`**).
- [x] Fila de prueba `ZZ_TEST AuditAI` (page_id `39612147-b3ea-810f-b761-d610a3be1ce3`):
      Email=`fbrunel@miuandes.cl`, Impuestos=12345, Honorarios=85000, Info Adicional=remanente,
      Adviser=Sebastián, Month="Junio 2026", Rut=`12345678-9` (ficticio, asignado para el test).
- [x] Botón `Enviar Correo F29` + Send webhook configurado en Contable Junio: header
      `X-AuditAI-Secret` + body con `Rut`+`Email`+`Customers` (propiedades seleccionables —
      Notion no expone `page_id` como variable; ver [`23`](23-automatizacion-notion-contable-correo.md) §5.4).
- [x] **`Month` no lo tipea el asesor (feedback 07-jul):** bulk-set `Month = "Junio 2026"` a las
      289 filas de Contable Junio (`bulk_set_month.py`, backup previo) + fallback C en el backend
      (`derivar_month_desde_base()` deriva del título de la base parent si llega vacío). Ver
      [`23`](23-automatizacion-notion-contable-correo.md) §5.2.d.
- [x] **Prueba E2E exitosa (07-jul-2026):** botón → correo a `fbrunel@miuandes.cl` desde
      `sebastianrobles@inversoragcp.com` con monto correcto → `Status = "1) Enviado y Pendiente"`.
- [x] **Extractor recursivo robusto** (`_buscar_clave` + `_extraer_plano_notion`): tolerante al
      formato real `{"source": {...}, "data": {...}}` de Notion (las props van anidadas en
      `data`, no en la raíz). 5/5 casos de test pasan. El `page_id` viene gratis en
      `source.page_id` (Notion lo incluye automáticamente) — el backend lo usa directo si es
      UUID válido; si no, cae a `find_page_by_rut()`.
- [x] Logging sin PII: dump estructural (solo keys y tipos, nunca valores) + `auditai.log`
      con `RotatingFileHandler`. Verificado en el E2E.
- [x] Cloud-ready: `requirements.txt`, `runtime.txt` (python-3.11), `Procfile`, `README.md`
      (paquete). `host="0.0.0.0"`, rutas `firma_png` relativas, `ASESORES_SMTP_JSON` env var fallback.
- [x] ngrok instalado (`C:\ngrok\ngrok.exe` v3.39.9, authtoken configurado, PATH actualizado).
- [x] Documentos de misión creados: `MISION-ARREGLAR-CORREO-F29.md` (misión Claude Opus 4.8,
      ✅ completada) y `MIGRACION-A-RENDER.md` (manual de migración a la nube, 405 líneas).
- [ ] **App Passwords de 2 asesores restantes** (Andrea, Matilde) — pendiente tras confirmar que Sebastián, Constanza y Carlos funcionan en el botón real. Andrea y Matilde además no tienen contraseña normal de Gmail.
- [ ] Caso borde sin Email (verificado vía `--test`, falta clic real del botón).

### N.3 · Rotación mensual (redirigida a doc 28) — ✅ decidido · robustez aplicada
> **Decisión de Carlos Cereceda (13-jul-2026, doc [`28`](28-cambio-de-mes-y-rotacion-manual.md)):**
> cada mes él mismo **duplica manualmente** la página Contable en Notion. **Se cancela
> `duplicar_mes.py`** (Fase 2 del doc 23 §6): la duplicación nativa de Notion (1 clic) es
> más confiable que recrear la base por API. La robustece el backend con una lista
> `DS_CONTABLES` (más reciente primero) para el fallback por RUT.
- [x] **Decisión formal registrada** en [`28`](28-cambio-de-mes-y-rotacion-manual.md) §1.
- [x] **Backend robustecido para el cambio de mes:** `DS_CONTABLE_JUNIO` (single) →
      lista `DS_CONTABLES` en `notion_client.py`; `find_page_by_rut()` itera la lista;
      alias `DS_CONTABLE_JUNIO` mantiene compatibilidad con imports viejos.
- [x] **Tests del cambio de mes:** `notion_automation/tests/test_cambio_mes.py` (6/6
      pasan, valida iteración en orden, alias legacy y caso de lista vacía).
- [x] **Flujo principal `page_id`-agnóstico:** confirmado — el webhook envía
      `source.page_id` automáticamente (verificado en el E2E del 07-jul, doc 23 §5.4).
      El cambio de mes NO requiere cambios de código en el flujo principal.
- [ ] **Primer cambio de mes real** (cuando Carlos duplique `Contable Julio`):
      anotar el nuevo `data source ID` arriba de `DS_CONTABLES` y correr E2E (pruebas
      §10.2 y §10.3 del doc 28) — **operación de 30 segundos + 1 clic de prueba**.
- [ ] ~~`duplicar_mes.py` con `--dry-run` correcto~~ — ❌ **CANCELADO** por decisión
      de negocio (Carlos duplica a mano). Ver doc 28 §9.

### N.4 · Endurecer y llevar a la nube (Fase 3 del doc 23, pendiente)
- [ ] Backend en la nube con URL estable (Render — manual en `MIGRACION-A-RENDER.md`),
      secretos en gestor, dominio de correo verificado.
- [ ] Idempotencia y observabilidad (logs sin PII — el logging ya está listo).
- [ ] Aplicar a las bases reales con backup + confirmación (R2/R5 — Contable Junio ya operativa).

### N.5 · Handler RRHH JUNIO 2026 🆕 *(en implementación, 09-jul-2026)*
- [ ] `handlers/rrhh.py` — mapeo de columnas, lógica de composición, write-back Status/Fecha
- [ ] `email_templates/rrhh_email.html` y `rrhh_email.txt` — plantilla del correo de imposiciones
  - [ ] Asunto: `Imposiciones {mes} {año}- {CLIENTE}`
  - [ ] Cuerpo: "Por medio de la presente informo el monto a pagar por concepto de imposiciones del mes de {mes} {año}. Plazo hasta {día} {nº} de {mes_siguiente} a las 13.45 horas. Total a pagar $ {monto}.-"
  - [ ] Fecha límite: **13 del mes siguiente** (día hábil) a las 13:45
- [ ] Endpoint `POST /webhook/rrhh` en `app.py`
- [ ] Lookup de email: si `Email Cliente` vacío, buscar en General Customers Data por RUT
- [ ] Columnas nuevas en Notion RRHH: `Email Cliente` (email), `Estado Correo` (status), `Fecha Envío` (date)
- [ ] Botón "Enviar Correo RRHH" en la página RRHH JUNIO 2026 (lo crea el usuario)
- [ ] Prueba E2E con fila real de RRHH

### N.6 · Handler Tickets - Servicios 🆕 *(planificado)*
- [ ] `handlers/tickets.py` — mapeo de columnas y lógica
- [ ] `email_templates/tickets_email.html` y `tickets_email.txt`
- [ ] Endpoint `POST /webhook/tickets` en `app.py`
- [ ] Botón en la página Tickets - Servicios
- [ ] Definir contenido del correo (pendiente con el usuario)

---

**Anterior:** [`10-fuentes-auxiliares-notion.md`](10-fuentes-auxiliares-notion.md) · **Volver al** [`README`](README.md)
