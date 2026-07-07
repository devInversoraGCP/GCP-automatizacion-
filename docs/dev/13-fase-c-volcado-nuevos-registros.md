# 13 · Fase C — Volcado de registros nuevos a la sandbox

> Documento de trabajo dedicado a la **Fase C del Frente A**: agregar a la sandbox `General Customers Data - AuditAI` los ~170 registros nuevos que existen en las fuentes auxiliares (`Contable Mayo` y `RRHH JUNIO 2026`) pero que no están en la base central.
>
> ⚠️ **Estado:** en preparación · esperando luz verde del usuario para ejecutar escrituras.
>
> 🔒 = toca credenciales/PII · 🧮 = lógica determinista.

---

## 1 · Contexto y objetivo

Tras completar la **Fase A** (limpieza) y la **Fase B** (enriquecimiento de los 171 registros existentes) el 01-jul-2026, el siguiente paso del **Frente A** es la **Fase C**: agregar los registros nuevos detectados en las fuentes auxiliares.

**Objetivo:** que `General Customers Data` pase de ser una base parcial y desactualizada a ser el **registro maestro completo** de clientes activos de la asesoría.

**Meta numérica:** llevar la sandbox de **171** registros actuales a **~341** registros (168 de `Contable Mayo` + 2 de `RRHH JUNIO 2026` + 171 actuales; el total final puede variar ligeramente por deduplicaciones).

**Fuente única de verdad de este documento:** [`11-checklist-maestro.md`](11-checklist-maestro.md) (tarea 1.3 · Fase C) y [`12-fase1-plan-detallado.md`](12-fase1-plan-detallado.md) (§A1b y decisiones D19–D22).

---

## 2 · Alcance

### Sí se hace

- Agregar a la sandbox los registros de `Contable Mayo` con **RUT válido** que **no existan ya** en la sandbox: **168 registros**.
- Agregar a la sandbox los registros de `RRHH JUNIO 2026` con **RUT válido** que **no existan ya** en la sandbox: **2 registros**.
- Poblar en cada nuevo registro todos los campos mapeables desde la fuente (`RUT`, `CLAVE SII`, `email`, `Adviser Accounting`, `CRM`, `Previred`/`USUARIO-Previred`/`CLAVE-Previred`, `Adviser RR.HH`).
- Deduplicar dentro de cada fuente antes de escribir (ej. `ADMINISTRADORES CHILE SPA`/`SpA` en Contable Mayo).
- Validar cada fila contra el contrato de datos antes de escribir.
- Generar **backup fresco** y **log de auditoría** completo.

### No se hace

- **No se toca la base original** `General Customers Data` (ID `1a23f5e4-…`).
- **No se escriben credenciales ni PII en outputs** del agente; los valores reales viajan solo por la API de Notion.
- **No se fusionan** los dos registros `SOCIAL UP SPV I SPA` / `SPV II SPA` de la sandbox (quedan pendientes de consulta al cliente).
- **No se agregan** registros sin RUT válido (no cruzables de forma confiable).
- **No se ejecuta la escritura** sin mostrar antes el diff completo al usuario y recibir confirmación explícita.

---

## 3 · Precondiciones (checklist previo a la escritura)

- [x] Decisiones D19–D22 confirmadas.
- [x] Esquemas de las 3 fuentes auxiliares mapeados ([`10-fuentes-auxiliares-notion.md`](10-fuentes-auxiliares-notion.md), [`12-fase1-plan-detallado.md`](12-fase1-plan-detallado.md) §A1).
- [x] Cruce fuente↔sandbox ejecutado ([`12-fase1-plan-detallado.md`](12-fase1-plan-detallado.md) §A1b).
- [x] **Backup fresco de la sandbox** guardado en `backups/general-customers-data/2026-07-01_sandbox_pre-fase-C.csv` (171 registros).
- [x] Modelo Pydantic/Pandera `ClienteNuevo` listo y probado (validación de RUT + DV implementada).
- [x] Dry-run generado y revisado por el usuario (ver §10).
- [ ] Confirmación explícita del usuario (luz verde).

---

## 4 · Fuentes de datos

| Fuente | Filas con RUT válido | Nuevos vs sandbox | Campos aportados |
|--------|----------------------|-------------------|------------------|
| `Contable Mayo` | 281 | **168** | `Customers`→`w`, `Rut`→`RUT`, `Clave SII`→`CLAVE SII`, `Email`→`email`, `Adviser Accounting`→`Adviser Accounting`, `CRM`→`CRM` |
| `RRHH JUNIO 2026` | 18 | **2** | `CLIENTE`→`w`, `RUT`→`RUT`, `USUARIO`/`CLAVE`→`USUARIO-Previred`/`CLAVE-Previred`, `ASISTENTE`→`Adviser RR.HH` |

> Nota: `RRHH JUNIO 2026` aporta 16 RUTs que ya cruzan con la sandbox; solo 2 son netamente nuevos.

---

## 5 · Mapeo de campos (fuente → sandbox)

### Desde `Contable Mayo`

| Campo fuente | Campo sandbox | Tipo sandbox | Notas |
|--------------|---------------|--------------|-------|
| `Customers` (title) | `w` (title) | title | Nombre del cliente. Normalizar: trim + title case consistente con el resto de la base. |
| `Rut` | `RUT` | text | Normalizar: quitar puntos/espacios, mayúscula la `K`, formato `12345678-5`. Validar DV con módulo 11. |
| `Clave SII` | `CLAVE SII` | text | 🔒 Credencial. Copiar tal cual si está presente. |
| `Email` | `email` | email | Validar formato básico. |
| `Adviser Accounting` | `Adviser Accounting` | person | Mapear directamente si la API lo permite; si no, dejar vacío y anotar en log. |
| `CRM` | `CRM` | multi_select | Copiar opciones existentes. |

### Desde `RRHH JUNIO 2026`

| Campo fuente | Campo sandbox | Tipo sandbox | Notas |
|--------------|---------------|--------------|-------|
| `CLIENTE` | `w` (title) | title | Nombre del cliente. |
| `RUT` (title) | `RUT` | text | Normalizar y validar DV. |
| `USUARIO`/`CLAVE` | `RRHH Origen` → `USUARIO-Previred` / `CLAVE-Previred` | relation → rollup | 🔒 Login/clave Previred. En la sandbox `USUARIO-Previred` y `CLAVE-Previred` son **rollups** de la relación `RRHH Origen`. Por tanto, para que se poblen se debe crear la **relación** apuntando a la página de origen en `RRHH JUNIO 2026`. |
| `ASISTENTE` | `Adviser RR.HH` | person | Asistente de RRHH. |

### ⚠️ Nota sobre tipos de columna en la sandbox

Durante la Fase B se transformó el esquema de la sandbox (D19): `USUARIO-Previred` y `CLAVE-Previred` son **rollups**, no text; y `Previred` es **status** (con valor por defecto `Not started`). Esto afecta cómo se cuentan los campos "poblados" en la verificación post-volcado: un rollup vacío o un status en `Not started` **no aporta información real** y debe contarse como vacío.

### Campos que quedarán vacíos (sin fuente identificada)

- `RUT RL`
- `Whatsapp`
- `Rubro`, `Segmentación`, `Ciudad`, `Municipalidad`
- `Nº`, `Column`, `Texto`
- `1ra Factura o Propuesta`
- `Drive Empresa`
- `Propuesta de Servicio`
- `Respaldo Anual` (puede dejarse con un valor por defecto si aplica)

---

## 6 · Algoritmo de volcado Fase C

```text
# A-FASE-C · Volcado de registros nuevos a la sandbox

ENTRADAS:
  sandbox  ← query completa de General Customers Data - AuditAI (171 filas)
  contable ← query completa de Contable Mayo (283 filas)
  rrhh     ← query completa de RRHH JUNIO 2026 (51 filas)

SALIDAS:
  nuevos_creados  ← lista de IDs de páginas creadas en Notion
  diff            ← reporte CSV de qué se va a crear/creó
  log_auditoria   ← archivo con timestamp, fuente, campos y valores

PRECONDICIÓN:
  backup_fresco_sandbox_guardado() == True

# ─────────────────────────────────────────────────────────────
# PASO 1 · Normalizar y validar RUTs de todas las fuentes
# ─────────────────────────────────────────────────────────────
para cada fila en sandbox:
    sandbox_ruts_normalizados ← normalizar_rut(fila.RUT) si es válido

para cada fila en contable:
    fila.rut_norm ← normalizar_rut(fila.Rut)
    fila.rut_valido ← validar_dv_modulo_11(fila.rut_norm)

para cada fila en rrhh:
    fila.rut_norm ← normalizar_rut(fila.RUT)
    fila.rut_valido ← validar_dv_modulo_11(fila.rut_norm)

# ─────────────────────────────────────────────────────────────
# PASO 2 · Deduplicar fuentes internamente
# ─────────────────────────────────────────────────────────────
# Contable Mayo: hay 1 RUT duplicado (ADMINISTRADORES CHILE SPA/SpA).
# Criterio: quedarse con la fila con más campos poblados;
# si empatan, con la de last_edited más reciente;
# si persisten diferencias, marcar para revisión humana.
contable_dedup ← deduplicar_por_rut(contable)

# RRHH: sin duplicados detectados; verificar de todas formas.
rrhh_dedup ← deduplicar_por_rut(rrhh)

# ─────────────────────────────────────────────────────────────
# PASO 3 · Identificar registros nuevos
# ─────────────────────────────────────────────────────────────
nuevos_contable ← []
para cada fila en contable_dedup:
    si fila.rut_valido y fila.rut_norm ∉ sandbox_ruts_normalizados:
        nuevos_contable.append(fila)

nuevos_rrhh ← []
para cada fila en rrhh_dedup:
    si fila.rut_valido y fila.rut_norm ∉ sandbox_ruts_normalizados
       y fila.rut_norm ∉ ruts_de_nuevos_contable:    # evitar doble creación
        nuevos_rrhh.append(fila)

# ─────────────────────────────────────────────────────────────
# PASO 4 · Mapear a modelo ClienteNuevo y validar
# ─────────────────────────────────────────────────────────────
registros_a_crear ← []
para cada fila en nuevos_contable + nuevos_rrhh:
    cliente ← mapear_a_modelo(fila, fuente)
    resultado ← validar(ClienteNuevo, cliente)
    si resultado OK:
        registros_a_crear.append(cliente)
    sino:
        cola_errores.append((fila, resultado.errores))

# ─────────────────────────────────────────────────────────────
# PASO 5 · Generar diff (dry-run)
# ─────────────────────────────────────────────────────────────
para cada cliente en registros_a_crear:
    diff.append({
        fuente: cliente.fuente,
        nombre: cliente.w,
        rut: cliente.RUT,
        campos_a_poblar: lista_no_vacios(cliente),
        advertencias: campos_sin_fuente(cliente)
    })

mostrar(diff)               # sin aplicar nada
mostrar(cola_errores)       # registros que no pasaron validación

# ─────────────────────────────────────────────────────────────
# PASO 6 · Confirmación del usuario
# ─────────────────────────────────────────────────────────────
esperar confirmación explícita del usuario   # luz verde

# ─────────────────────────────────────────────────────────────
# PASO 7 · Crear páginas en la sandbox
# ─────────────────────────────────────────────────────────────
para cada cliente en registros_a_crear (en lotes, con throttling ≤ 3 req/s):
    pagina ← notion.pages.create(
        parent = { database_id: SANDBOX_ID },
        properties = cliente.a_notion_properties()
    )
    log_auditoria.append({
        timestamp: ahora(),
        acción: "CREAR",
        id_nuevo: pagina.id,
        fuente: cliente.fuente,
        rut: cliente.RUT,
        nombre: cliente.w,
        campos_poblados: lista_no_vacios(cliente)
    })

# ─────────────────────────────────────────────────────────────
# PASO 8 · Verificación post-volcado
# ─────────────────────────────────────────────────────────────
sandbox_post ← query completa de la sandbox
contar_filas(sandbox_post)                         # esperado ~341
contar_ruts_validos(sandbox_post)
contar_claves_sii(sandbox_post)
contar_emails(sandbox_post)
comparar_con_diff(log_auditoria, sandbox_post)
```

---

## 7 · Validaciones (Pandera/Pydantic)

Modelo `ClienteNuevo` mínimo:

| Campo | Tipo | Validación |
|-------|------|------------|
| `w` | str | obligatorio, longitud > 0 |
| `RUT` | str | formato `12345678-5`, DV válido módulo 11 |
| `CLAVE SII` | str \| None | opcional, no exponer en logs |
| `email` | str \| None | opcional, formato email si presente |
| `USUARIO-Previred` | str \| None | opcional, no exponer en logs |
| `CLAVE-Previred` | str \| None | opcional, no exponer en logs |
| `Adviser Accounting` | person \| None | opcional |
| `Adviser RR.HH` | person \| None | opcional |
| `CRM` | list[str] \| None | opcional, valores dentro del catálogo existente |
| `fuente` | str | obligatorio: `Contable Mayo` o `RRHH JUNIO 2026` |

Reglas adicionales:
- Si `RUT` está duplicado respecto a la sandbox → **no crear** (ya existe; pasar a revisión manual si hay conflicto de nombre).
- Si `w` está vacío o es un placeholder genérico → marcar advertencia.
- Si no hay ni `CLAVE SII` ni `email` ni credenciales Previred → aceptable, pero marcar como "cliente nuevo con datos mínimos".

---

## 8 · Manejo de duplicados y casos especiales

### `ADMINISTRADORES CHILE SPA` / `ADMINISTRADORES CHILE SpA` (Contable Mayo)

- **Situación:** mismo RUT, dos filas en Contable Mayo.
- **Acción:** deduplicar antes de crear en la sandbox.
- **Criterio de deduplicación:**
  1. Quedarse con la fila que tenga más campos poblados.
  2. Si empatan, quedarse con la de `last_edited_time` más reciente.
  3. Si persisten diferencias en campos clave (`CLAVE SII`, `email`), anotar en log y consultar al usuario.

### `SOCIAL UP SPV I SPA` / `SPV II SPA` (sandbox)

- **Situación:** dos clientes distintos en la sandbox comparten el mismo RUT.
- **Acción:** no se resuelve en Fase C. Se mantiene el estado actual y se deja anotado en [`12-fase1-plan-detallado.md`](12-fase1-plan-detallado.md) para consulta al cliente.

### Posible solape nombre vs RUT

- El cruce para detectar "nuevo" se hace **solo por RUT válido**.
- Si un cliente de Contable Mayo tiene RUT vacío/inválido → **no se agrega** en esta fase.
- Si un cliente de RRHH tiene RUT que ya existe en Contable Mayo (dentro de los 168 nuevos) → **no se crea dos veces**; priorizar Contable Mayo para `w`, `RUT`, `CLAVE SII`, `email`; y complementar con RRHH para `USUARIO-Previred`/`CLAVE-Previred` si es posible.

---

## 9 · Log de auditoría

Cada creación genera una línea en `backups/general-customers-data/log-fase-c-YYYY-MM-DD.csv`:

| Campo | Descripción |
|-------|-------------|
| `timestamp` | Fecha/hora UTC de la creación |
| `accion` | `CREAR` |
| `id_nuevo` | ID de página Notion generada |
| `fuente` | `Contable Mayo` o `RRHH JUNIO 2026` |
| `rut` | RUT normalizado (sin DV en log, o RUT enmascarado) |
| `nombre` | Nombre del cliente (`w`) |
| `campos_poblados` | Lista de campos que se poblaron |
| `campos_vacios` | Lista de campos que quedaron vacíos |
| `advertencias` | Errores de validación o casos especiales |

> 🔒 **PII/Credenciales:** el log no incluye valores de `CLAVE SII`, `USUARIO-Previred`, `CLAVE-Previred` ni emails completos.

---

## 10 · Dry-run y confirmación

Antes de tocar Notion se generará un diff que incluya:

1. **Resumen ejecutivo:** cuántos registros se crearán, de qué fuente, cuántos campos se poblarán.
2. **Lista detallada:** nombre, RUT, fuente y campos a poblar por cada nuevo registro.
3. **Cola de errores:** registros que no pasaron validación y por qué.
4. **Casos especiales:** deduplicaciones aplicadas, registros descartados.
5. **Estimación de completitud post-volcado:** cuántos `RUT`, `CLAVE SII`, `email`, `Previred` quedarán.

### Resultado del dry-run (01-jul-2026)

> Archivos generados:
> - Público (sin PII): `backups/general-customers-data/2026-07-01_dry-run-fase-C-publico.csv`
> - Privado (con datos para escritura): `backups/general-customers-data/2026-07-01_dry-run-fase-C-privado.json`

| Métrica | Valor |
|---------|-------|
| Registros actuales en sandbox | **171** |
| RUTs válidos en sandbox | **165** |
| Filas Contable Mayo (crudo) | **283** |
| Filas Contable Mayo deduplicadas | **282** |
| Nuevos de Contable Mayo | **161** |
| Nuevos de RRHH JUNIO 2026 | **2** |
| **Total registros a crear** | **163** |
| Sandbox post-volcado (estimado) | **~334** |

**Campos a poblar en los 163 nuevos:**

| Campo | Registros con dato |
|-------|-------------------:|
| `CLAVE SII` | 160 |
| `email` | 4 |
| `USUARIO-Previred` | 2 |
| `CLAVE-Previred` | 2 |
| `Adviser Accounting` | 161 |
| `Adviser RR.HH` | 2 |
| `CRM` | 1 |

**Casos especiales detectados:**
- `ADMINISTRADORES CHILE SPA`/`SpA`: RUT duplicado en Contable Mayo (2 filas). Se eligió la de mayor score.
- `RENOFAT SPA`: doble asignación en `Adviser Accounting`.

El usuario debe responder con **confirmación explícita** (luz verde) para proceder a la escritura.

---

## 11 · Post-condiciones y verificación ✅

Tras la escritura se verificó:

- [x] La sandbox tiene **334 registros** (171 + 163 nuevos; la diferencia con la estimación inicial de ~341 se debe a que solo 161 de Contable Mayo eran netamente nuevos por RUT, no 168).
- [x] No hay RUTs duplicados nuevos; el único duplicado seguimiento es el preexistente `SOCIAL UP SPV I SPA` / `SPV II SPA`.
- [x] Re-medición de completitud realizada (ver §14).
- [x] Validar esquema con Pandera/Pydantic sobre el 100% de la sandbox → Pandera pasa; 19 errores Pydantic (18 emails inválidos + 1 sin @). Detalle en [`14-construccion-dataset-y-anomalias.md`](14-construccion-dataset-y-anomalias.md).
- [x] [`11-checklist-maestro.md`](11-checklist-maestro.md) actualizado marcando Fase C como completada.
- [x] [`02-estado-del-proyecto.md`](02-estado-del-proyecto.md) actualizado con nuevos conteos.
- [x] [`14-construccion-dataset-y-anomalias.md`](14-construccion-dataset-y-anomalias.md) creado con anomalías y decisiones pendientes.

---

## 14 · Resultados de la ejecución (01-jul-2026)

### Escritura en la sandbox

- **Registros creados:** 163/163 exitosos, 0 fallidos.
- **Log de auditoría:** `backups/general-customers-data/log-fase-c-2026-07-01.csv`
- **Resumen:** `backups/general-customers-data/resumen-fase-c-2026-07-01.json`

### Corrección post-escritura: relación RRHH

Se detectó que `USUARIO-Previred` y `CLAVE-Previred` son **rollups** de la relación `RRHH Origen`. Por tanto, los valores directos de `USUARIO`/`CLAVE` no se pueden escribir directamente; hay que establecer la relación.

- Se actualizaron los 2 registros de RRHH (`INVERSORA GCP`, `JAVIERA COMPAN`) para que apunten a sus páginas de origen en `RRHH JUNIO 2026`.
- **Log de corrección:** `backups/general-customers-data/log-fase-c-correccion-rrhh-2026-07-01.csv`
- Tras la corrección, los rollups se poblaron automáticamente.

### Completitud final de la sandbox

| Métrica | Valor |
|---------|-------:|
| Total registros | **334** |
| RUTs válidos | **329** (98,5%) |
| Sin RUT | **5** |
| RUTs inválidos | **0** |
| Listos para automatización SII (RUT válido + CLAVE SII) | **322** |
| RUTs duplicados | **1** (preexistente) |

**Población por columna (relevantes):**

| Columna | Poblados | % |
|---------|---------:|--:|
| `w` | 334 | 100% |
| `RUT` | 329 | 98,5% |
| `CLAVE SII` | 322 | 96,4% |
| `email` | 88 | 26,3% |
| `Adviser Accounting` | 329 | 98,5% |
| `Adviser RR.HH` | 33 | 9,9% |
| `USUARIO-Previred` / `CLAVE-Previred` | 17 | 5,1% |
| `Previred` (status real ≠ Not started) | 5 | 1,5% |
| `CRM` | 125 | 37,4% |

> Nota: `Previred`, `Respaldo Anual` y los rollups vacíos no se cuentan como poblados en esta medición, ya que su valor por defecto no aporta información.

---

## 12 · Rollback

Si algo sale mal:

1. **Restaurar desde backup CSV** (`backups/general-customers-data/YYYY-MM-DD_sandbox_pre-fase-C.csv`).
2. Si el daño es parcial, usar los IDs del log de auditoría para borrar/selectivamente las páginas creadas.
3. Como último recurso, volver a duplicar la base original a partir de su último backup o de la sandbox anterior.

---

## 13 · Dependencias y estado

- Depende de que la sandbox tenga el esquema de 27 columnas post-D19/D23.
- Depende de tener acceso de escritura a la sandbox `General Customers Data - AuditAI` (autorizado por el usuario desde 01-jul-2026, según [`AGENTS.md`](../../AGENTS.md)).
- ✅ Ejecutado el 01-jul-2026 tras luz verde del usuario.

---

**Anterior:** [`12-fase1-plan-detallado.md`](12-fase1-plan-detallado.md) · **Volver al** [`README`](README.md)
