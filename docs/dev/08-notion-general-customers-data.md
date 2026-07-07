# 08 · Notion: base "General Customers Data" (esquema, solo lectura)

> Mapeo de la base de datos central del cliente en Notion, obtenido en **solo lectura**. Desarrolla D11/D12/D14 de [`05-decisiones-y-preguntas.md`](05-decisiones-y-preguntas.md).
>
> ⚠️ **Acceso escalonado a Notion:** lectura por defecto; escritura/edición/borrado solo con autorización explícita del usuario y sobre copia (ver política completa en [`../../AGENTS.md`](../../AGENTS.md)). Las columnas `CLAVE SII` y `Previred` son **credenciales** y nunca se exponen.

## Identificación

- **Nombre:** 🔓 General Customers Data — tipo **database**.
- **ID:** `1a23f5e4-0223-46a6-9ad5-16ea823b64ba`
- **Data source:** `collection://690945e4-220a-48c3-a888-7fe9ae242d55`
- **Ubicación:** `Inversora GCP SpA` → `CONTABILIDAD - SII - TESORERÍA`.
- Es una base tipo **CRM / maestro de clientes**. Cada cliente además tiene su propia página (ej. NIKILETTERS SPA, CRISTIAN FARIAS, MANUEL TORRES, Refraline…).

## Red de seguridad (montada 30-jun-2026, ver [`09`](09-seguridad-y-respaldo.md))

- **Plan Notion:** Business → historial de página **90 días**, papelera **30 días** (Capa 3 — recuperación nativa).
- **Snapshot CSV base:** `backups/general-customers-data/2026-06-30_all.csv` (vista "All", 171 registros). ⚠️ Contiene credenciales/PII → no commitear (ver D17 y [`../../AGENTS.md`](../../AGENTS.md)).
- **Sandbox:** `General Customers Data - AuditAI`
  - **ID database:** `16f12147-b3ea-8354-872b-814f104871b7`
  - **Data source:** `4ff12147-b3ea-82f4-98dd-072067524cdc`
  - **Parent:** mismo que el original (`dd47681b-89fe-4f49-bea3-f8038d571d44`)
  - **Copia fiel** con las 171 filas, esquema idéntico (incluye credenciales reales — precaución).
  - Toda experimentación y volcado de data faltante se hace aquí, **nunca sobre el original**.

## Fuentes auxiliares para completar data faltante (ver [`10`](10-fuentes-auxiliares-notion.md))

La data faltante se recupera desde las fuentes auxiliares hacia la **sandbox** (D16/D15), con dry-run + confirmación del usuario. Según auditoría de completitud (30-jun-2026): 20 sin `CLAVE SII`, 12 con `RUT` vacío/inválido, 100 sin `email`, 140 sin `Previred`, 12 sin `Adviser Accounting`, 141 sin `Adviser RR.HH`. **Tickets - Servicios queda descartada** como fuente de GCD.

## Esquema: 22 columnas (original) · 30 en la sandbox (post-D19/D23 + `Email por revisar` + rollups RRHH)

> 🆕 **02-jul-2026:** se agregaron 2 rollups sobre la relación `RRHH Origen` → `RRHH JUNIO 2026`: **`IMPUESTO ÚNICO`** y **`MONTO IMPOSICIONES|`** (insumo de la casilla 48 del F29). Relación poblada en **36 filas** (18 pre-existentes + 18 matches seguros). Detalle y pendientes: [`18-integracion-impuesto-unico-imposiciones.md`](18-integracion-impuesto-unico-imposiciones.md).

> ⚠️ **Diverge desde D19/D23 (01-jul-2026):** el esquema de abajo es el del **original** (22 columnas, intocado). La **sandbox** tiene 5 columnas adicionales:
> - `USUARIO-Previred` 🆕 + `CLAVE-Previred` 🆕 + `RRHH Origen` 🆕 (D19)
> - `Origen` 🆕 + `Origen Contable Mayo` 🆕 (D23)
> - `Previred` cambió de *text* a *status* (D19)
>
> Ver detalle en D19/D23 de [`05-decisiones-y-preguntas.md`](05-decisiones-y-preguntas.md). Autorización de escritura plena sobre la sandbox: ver [`AGENTS.md`](../../AGENTS.md).

**🔴 Credenciales / sensibles (nunca exponer su valor):**
| Columna | Tipo (original) | Tipo (sandbox) |
|---|---|---|
| `CLAVE SII` | text — clave del SII | igual |
| `Previred` | text — credencial Previred (cajón de sastre sin estructura) | **status** (D19) — mismas opciones que RRHH: `Not started` / `no aplica` / `transf. a GCP` / `Subidas` / `DNP` / `Pagadas` |
| `USUARIO-Previred` | — (no existe) | **🆕 text** (D19) — login Previred, recuperado de RRHH (`USUARIO`) |
| `CLAVE-Previred` | — (no existe) | **🆕 text** (D19) — clave Previred, recuperada de RRHH (`CLAVE`) |
| `RUT` | text — PII | igual |
| `RUT RL` | text — RUT representante legal (PII) | igual |
| `email` | email — PII | igual |
| `Whatsapp` | text — PII | igual |

**🏢 Identificación / segmentación:**
| Columna | Tipo |
|---|---|
| `w` | title (nombre del cliente) |
| `ID` | unique_id (clave estable para escrituras) |
| `Nº` | select (165 opciones) |
| `CRM` | multi_select (157 opciones) |
| `Rubro` | multi_select (36) |
| `Segmentación` | select (4) |
| `Ciudad` | select (15) |
| `Municipalidad` | select (19) |

**👤 Gestión / contacto / fechas:**
| Columna | Tipo |
|---|---|
| `Adviser Accounting` | person |
| `Adviser RR.HH` | person |
| `1ra Factura o Propuesta` | date |
| `Respaldo Anual` | status |

**🔗 Enlaces / otros:**
| Columna | Tipo |
|---|---|
| `Drive Empresa` | url |
| `Propuesta de Servicio` | url |
| `Column` | select (2) |
| `Texto` | text |

**🔍 Trazabilidad / origen (D23):**
| Columna | Tipo | Descripción |
|---|---|---|
| `Origen` | select (`Original` · `Contable Mayo` · `RRHH JUNIO 2026`) | Indica de qué fuente proviene cada fila. |
| `Origen Contable Mayo` | relation → `Contable Mayo` | Enlace a la página fuente para los registros agregados desde Contable Mayo. |
| `RRHH Origen` | relation → `RRHH JUNIO 2026` | Enlace a la página fuente para registros con origen RRHH. |

## Relevancia para el proyecto

- **Automatización SII (D12):** `RUT` + `CLAVE SII` son exactamente las credenciales para iniciar sesión en el SII y descargar el XLSX. `RUT RL` distingue persona/representante.
- **Centralización (D11):** esta base es la "Etapa 1" donde se centraliza todo antes de migrar a una BD especializada.

## Cómo consultarla (solo lectura)

- `notion-fetch` con el ID o la collection URL → esquema (respuesta grande: ~92K chars, conviene parsear localmente).
- `notion-query-data-sources` (SQL) usando `collection://690945e4-220a-48c3-a888-7fe9ae242d55` como tabla. Requiere plan Business + Notion AI. **Excluir siempre** `CLAVE SII`/`Previred` de cualquier SELECT que se vaya a mostrar.

## Completitud (medida en solo lectura · post-decisiones Frente A, 02-jul-2026)

Base actualizada tras el volcado de la Fase C ([`13`](13-fase-c-volcado-nuevos-registros.md)) y las decisiones de cierre del Frente A ([`14`](14-construccion-dataset-y-anomalias.md) §4). Cambios del 02-jul: XIT recibió RUT+Clave (de Contable Febrero); 3 clientes sin datos (`Sergio ??`, `Patricia`, `Zsabesky Servicios`) fueron **movidos** a la página `🗑️ Descartados AuditAI`; se agregó la columna checkbox **`Email por revisar`** (28 columnas en la sandbox) con 19 registros marcados.

- **Total de clientes:** **331** (antes 334; −3 movidos a Descartados)
- Sin `RUT` (vacío): **1** (solo `Steven` ID 48, RUT pendiente) — antes 5 (XIT resuelto + 3 movidos)
- `RUT` con DV inválido: **0**
- Sin `CLAVE SII` 🔑: **7** (~2,1%) — *(antes 8; −1: Escuela de Voces Manuela rescatada de Contable Febrero, 02-jul tarde, ver [`15`](15-barrido-bases-contables-mensuales.md))*
- Sin `email`: **246** (~73,7%)
- Sin `Previred` (status real ≠ Not started): **329** (~98,5%)
- Sin `Adviser Accounting`: **5** (~1,5%)
- Sin `Adviser RR.HH`: **301** (~90,1%)
- Con `Origen` poblado: **331** (100%)
- Con checkbox `Email por revisar` marcado (email inválido a completar después): **19**
- Con `Origen Contable Mayo` poblado (donde aplica): **161/161** (100%)
- **Listos para automatización SII** (tienen `RUT` válido + `CLAVE SII`): **324** (~97,9%) — *(+1 tras barrido Febrero: Escuela de Voces Manuela, 02-jul tarde; ver [`15`](15-barrido-bases-contables-mensuales.md)). Quedan 6 sin clave no recuperables de Notion → escalamiento al usuario.*

> ⚠️ `USUARIO-Previred` y `CLAVE-Previred` son **rollups** de la relación `RRHH Origen`; solo se consideran poblados cuando el rollup tiene valor. Post-Fase C hay **17** registros con estos datos.

## Pendiente

- ✅ Mapear el **esquema de las 3 fuentes auxiliares** — resuelto en [`12`](12-fase1-plan-detallado.md) §A1.
- ✅ Cruzar las fuentes auxiliares con la sandbox — resuelto en [`12`](12-fase1-plan-detallado.md) §A1b.
- ✅ **Volcar la data faltante** hacia la sandbox — ejecutado el 01-jul-2026 (Fase A+B+C). Ver [`13`](13-fase-c-volcado-nuevos-registros.md).
- ✅ Número exacto de "listos para SII": **322** post-Fase C.
- ✅ Agregar **trazabilidad de origen** (`Origen` select + `Origen Contable Mayo` relation) — ejecutado el 01-jul-2026; ver [`13`](13-fase-c-volcado-nuevos-registros.md) y [`14`](14-construccion-dataset-y-anomalias.md).
- ⏳ Resolver 5 clientes sin `RUT` y el duplicado `SOCIAL UP SPV I/II` (consulta al cliente).
- ✅ Validar esquema completo con Pandera/Pydantic (gate de cierre Frente A) → ejecutado; ver [`14`](14-construccion-dataset-y-anomalias.md).
- ✅ 18–19 emails inválidos → **etiquetados** con checkbox `Email por revisar` (02-jul); se completarán después (secundario).
- Confirmar significado de columnas ambiguas (`Column`, `Texto`, `Nº`).

---

**Anterior:** [`07-flujo-de-datos.md`](07-flujo-de-datos.md) · **Volver al** [`README`](README.md)
