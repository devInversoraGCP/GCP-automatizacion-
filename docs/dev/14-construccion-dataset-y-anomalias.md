# 14 · Construcción del dataset y anomalías por decidir

> Documento de cierre del **Frente A** de la Fase 1. Resume cómo se construyó el dataset central en Notion, los resultados de la validación con Pandera/Pydantic, y las **decisiones de cierre** (ya **resueltas** el 02-jul-2026, ver §4). Tras las decisiones, la base quedó en **331 clientes** (las métricas de §2 reflejan el estado post-Fase C con 334; §4 detalla los ajustes del 02-jul).
>
> 🔒 = toca credenciales/PII · 🧮 = lógica determinista.

---

## 1 · Contexto

El objetivo del Frente A era transformar `General Customers Data` de una base parcial y desactualizada (171 registros, muchos campos vacíos) en el **registro maestro completo** de clientes de la asesoría.

El trabajo se ejecutó en tres sub-fases:

| Fase | Qué se hizo | Resultado |
|------|-------------|-----------|
| **A** | Limpieza pre-volcado | 7 RUTs corregidos, duplicados identificados, backup previo |
| **B** | Enriquecimiento de registros existentes | 151 cambios en 103 páginas (RUT, CLAVE SII, email, advisers, Previred) |
| **C** | Agregar registros nuevos | **163 registros nuevos** creados en la sandbox (161 Contable Mayo + 2 RRHH) |

Detalle de la Fase C: [`13-fase-c-volcado-nuevos-registros.md`](13-fase-c-volcado-nuevos-registros.md).

---

## 2 · Dataset resultante

### Métricas generales (post-Fase C, 01-jul-2026)

| Métrica | Valor |
|---------|-------:|
| Total de clientes en sandbox | **334** |
| RUTs válidos | **329** (98,5%) |
| RUTs inválidos | **0** |
| Sin RUT | **5** |
| Listos para automatización SII (RUT + CLAVE SII) | **322** (96,4%) |
| RUTs duplicados | **1** par (preexistente) |

### Completitud por columna relevante

| Columna | Poblados | % |
|---------|---------:|--:|
| `w` (nombre) | 334 | 100% |
| `RUT` | 329 | 98,5% |
| `CLAVE SII` | 322 | 96,4% |
| `email` | 88 | 26,3% |
| `Adviser Accounting` | 329 | 98,5% |
| `Adviser RR.HH` | 33 | 9,9% |
| `CRM` | 125 | 37,4% |
| `USUARIO-Previred` / `CLAVE-Previred` | 17 | 5,1% |
| `Previred` (status real ≠ Not started) | 5 | 1,5% |
| `Origen` | 334 | 100% |
| `Origen Contable Mayo` (donde aplica) | 161/161 | 100% |

> Nota: `USUARIO-Previred` y `CLAVE-Previred` son **rollups** de la relación `RRHH Origen`; solo se cuentan como poblados cuando el rollup tiene valor. `Previred` y `Respaldo Anual` son status con valor por defecto `Not started`, que no se considera información real.

### Trazabilidad de origen (D23)

Para que cada fila sea auditable, se agregaron dos columnas en la sandbox:

| Columna | Tipo | Poblado |
|---|---|---|
| `Origen` | select (`Original` · `Contable Mayo` · `RRHH JUNIO 2026`) | 334/334 (100%) |
| `Origen Contable Mayo` | relation → `Contable Mayo` | 161/161 (100% de los que aplican) |
| `RRHH Origen` | relation → `RRHH JUNIO 2026` | 16/16 clientes con origen RRHH (2 nuevos + 14 existentes) |

Distribución final:
- **Original:** 171 registros (los de la base inicial).
- **Contable Mayo:** 161 registros (nuevos agregados en Fase C).
- **RRHH JUNIO 2026:** 2 registros (nuevos agregados en Fase C).

Esto permite saber, para cada cliente, de qué fuente proviene y navegar directamente a la página fuente en Notion.

---

## 3 · Validación con Pandera/Pydantic

### Metodología

Se descargaron los 334 registros de la sandbox vía API de Notion y se validaron con:

- **Pydantic:** modelo `Cliente` con validación de RUT (módulo 11), email, y campos obligatorios.
- **Pandera:** `DataFrameSchema` con tipos y nulabilidad esperada.

Script: `validar_esquema_fase_c.py` (ejecutado el 01-jul-2026).

### Resultados

| Validador | Resultado |
|-----------|-----------|
| **Pandera** | ✅ **Pasa** — el DataFrame cumple el esquema de tipos y nulabilidad. |
| **Pydantic** | ⚠️ **19 errores** — todos asociados a campos `email` con formato inválido. |

### Tipos de anomalías detectadas

| Tipo | Cantidad | Descripción |
|------|---------:|-------------|
| Sin `RUT` | 5 | Clientes con nombre placeholder o genérico, sin RUT en ninguna fuente. |
| `RUT` duplicado | 1 par | `SOCIAL UP SPV I SPA` y `SPV II SPA` comparten el mismo RUT. |
| `email` inválido | 18 | Múltiples emails en un campo, notas entre paréntesis, "SOLO WHATSAPP", etc. |

**Archivos generados:**
- `backups/general-customers-data/2026-07-01_validacion-esquema-fase-C.json`
- `backups/general-customers-data/2026-07-01_validacion-esquema-fase-C-anomalias.csv`

---

## 4 · Decisiones — ✅ resueltas por el usuario (02-jul-2026)

> **Resolución del cliente/usuario:**
> 1. **5 sin RUT →** XIT **resuelto** (RUT rescatado de Contable Febrero). `Sergio ??`, `Patricia` y `Zsabesky Servicios` → **eliminar** (el cliente final confirmó que ya no importan). `Steven` (ID 48) **no fue mencionado** en la orden de borrado → queda **pendiente de confirmación** (¿eliminar también o mantener?). ⚠️ La API de Notion no envía filas a papelera; el "borrado" se hace **moviéndolas fuera de la base** (recuperable) o el usuario las borra en la UI.
> 2. **Duplicado `SOCIAL UP SPV I/II` →** **se dejan tal cual.** Es un mismo cliente con las mismas empresas; el RUT compartido es intencional, no un error. Sin acción.
> 3. **18 emails inválidos →** **se dejan tal cual** (metadata secundaria). Se agrega una **etiqueta/marcador en Notion** para poder **filtrarlos** y completarlos más adelante. La prioridad real es `RUT` + `CLAVE SII` de todos los registros; el resto es secundario.
> 4. **Campos sin fuente →** **ignorar por ahora** (metadata secundaria, no crítica para el MVP). Sin acción.

### Ejecución (02-jul-2026)

- **D1 ✅ ejecutada:** `Sergio ??` (78), `Patricia` (50) y `Zsabesky Servicios` (113) **movidos fuera de la base** a la página **🗑️ Descartados AuditAI** (`39112147-b3ea-812e-822b-ff1afac2c9eb`) — recuperables. La base pasa de **334 → 331**. `Steven` (48) **se mantiene** (RUT pendiente de rescatar). XIT ya estaba resuelto. Log en `log-auditoria-volcado.csv`.
- **D2 ✅:** sin acción (duplicado SOCIAL UP intencional).
- **D3 ✅ ejecutada:** nueva columna checkbox **`Email por revisar`** en la sandbox; **19 registros** con email inválido (validación Pydantic) marcados `true` para poder filtrarlos y completarlos después. Log registrado.
- **D4 ✅:** sin acción (campos sin fuente, opcionales para el MVP).

> **Gate del Frente A:** queda pendiente solo **Steven (RUT)** — vía barrido de meses ([`15`](15-barrido-bases-contables-mensuales.md)) o consulta a Carlos Cereceda. Con eso resuelto, el Frente A se puede declarar cerrado y pasar al Frente B.

Detalle original de cada caso (para contexto):

### 4.1 · Los 5 clientes sin RUT

**Lista:**

| Nombre | page_id | Situación |
|--------|---------|-----------|
| Sergio ?? | `78e12147-…` | Nombre placeholder, sin candidato en fuentes auxiliares. |
| Patricia | `c7512147-…` | Nombre genérico, sin candidato confiable. |
| Zsabesky Servicios | `82b12147-…` | Nombre ambiguo, sin RUT en fuentes. |
| Steven | `e2412147-…` | Nombre genérico, sin candidato confiable. |
| XIT | `91512147-…` | Nombre de marca/proyecto, sin RUT claro. |

**Opciones a decidir:**

1. **Eliminar** los 5 registros de la sandbox (no son clientes operativos identificables).
2. **Mantenerlos** como clientes en estado "pendiente de RUT" y marcarlos con un status/etiqueta.
3. **Consultar al cliente final** de la asesoría para identificar quiénes son y recuperar sus RUTs.

**Recomendación técnica:** la opción 3 es la más segura; mientras tanto, marcarlos con una etiqueta de revisión. La opción 1 solo si se confirma que son residuos/duplicados no recuperables.

---

### 4.2 · Duplicado `SOCIAL UP SPV I SPA` / `SPV II SPA`

**Situación:** dos clientes distintos en la sandbox comparten el mismo RUT `77798724-0`.

**Opciones a decidir:**

1. **Mantener ambos** si realmente son dos entidades distintas (ej. SPV I y SPV II) y uno de los RUTs está mal cargado. Corregir el RUT incorrecto cuando se identifique.
2. **Fusionar** en un solo registro si es el mismo cliente duplicado.
3. **Eliminar uno** si se confirma que es un duplicado puro.

**Recomendación técnica:** no fusionar ni eliminar automáticamente. Consultar al cliente final para determinar cuál RUT es el correcto de cada SPV.

---

### 4.3 · Emails inválidos (18 registros)

**Situación:** el campo `email` contiene valores que no son una única dirección válida, como:
- Múltiples emails separados por espacios, comas o punto y coma.
- Notas adicionales: `"carol@wegroup.cl german@wegroup.cl"`, `"SOLO WHATSAPP"`, `"... (clave Fabian2025)"`.
- Rut u otros datos en el campo email.

**Opciones a decidir:**

1. **Limpiar automáticamente** extrayendo la primera dirección válida y descartando el resto.
2. **Mover la información extra** a una columna de notas o `Texto`.
3. **Marcar para revisión manual** y no tocar el campo hasta que un humano lo valide.
4. **Crear una columna adicional** `email_secundario` si se quiere conservar múltiples emails.

**Recomendación técnica:** la opción 1 es razonable para el email principal, pero con **dry-run previo** mostrando antes→después. Los casos más complejos (múltiples emails activos) deberían pasar a revisión manual.

---

### 4.4 · Campos sin fuente identificada

Algunas columnas de `General Customers Data` no tienen fuente auxiliar que los alimente:

- `Whatsapp`
- `Rubro`, `Segmentación`, `Ciudad`, `Municipalidad`
- `Nº`, `Column`, `Texto`
- `1ra Factura o Propuesta`
- `Drive Empresa`
- `Propuesta de Servicio`
- `RUT RL`

**Opciones a decidir:**

1. **Buscar otras fuentes** en el workspace de Notion que puedan completarlos.
2. **Dejarlos vacíos** si no son críticos para la automatización SII.
3. **Definir cuáles son obligatorios** y cuáles opcionales para el MVP.

**Recomendación técnica:** para el MVP del F29 solo son estrictamente necesarios `RUT` + `CLAVE SII`. Los demás campos pueden quedar como metadata opcional. Se recomienda definir el contrato final en el modelo Pydantic (`Cliente`) marcando obligatorios vs. opcionales.

---

## 5 · Recomendación para cerrar el gate del Frente A

Para declarar la base "final y robusta" y pasar al Frente B (formalización de reglas del F29), se propone:

| Paso | Acción | Responsable |
|------|--------|-------------|
| 1 | Decidir el destino de los **5 sin RUT** y el **duplicado SPV**. | Usuario (asesoría) |
| 2 | Aplicar la decisión en la sandbox con backup + dry-run + log. | Agente |
| 3 | Limpiar emails inválidos (primera dirección válida; casos complejos a revisión). | Agente + validación usuario |
| 4 | Ejecutar validación Pandera/Pydantic nuevamente y confirmar **0 errores de esquema**. | Agente |
| 5 | Documentar contrato final de datos (`Cliente` Pydantic) y columnas obligatorias/opcionales. | Agente |
| 6 | **Declarar Frente A cerrado** y comenzar Frente B. | Usuario |

---

## 6 · Relación con el resto de la documentación

- Fase C (ejecución): [`13-fase-c-volcado-nuevos-registros.md`](13-fase-c-volcado-nuevos-registros.md)
- Plan detallado Fase 1: [`12-fase1-plan-detallado.md`](12-fase1-plan-detallado.md)
- Checklist maestro: [`11-checklist-maestro.md`](11-checklist-maestro.md)
- Esquema Notion: [`08-notion-general-customers-data.md`](08-notion-general-customers-data.md)
- Decisiones de diseño: [`05-decisiones-y-preguntas.md`](05-decisiones-y-preguntas.md)

---

**Anterior:** [`13-fase-c-volcado-nuevos-registros.md`](13-fase-c-volcado-nuevos-registros.md) · **Volver al** [`README`](README.md)
