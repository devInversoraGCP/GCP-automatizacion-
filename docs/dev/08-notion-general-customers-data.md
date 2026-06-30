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

La data faltante (20 sin `CLAVE SII`, 10 sin `RUT`, ~100 sin `email`) se recupera desde 3 bases activas del mismo workspace: **Contable Mayo**, **RRHH JUNIO 2026** y **Tickets - Servicios**. Volcado siempre hacia la **sandbox** (D16/D15), con dry-run + confirmación del usuario.

## Esquema: 22 columnas

**🔴 Credenciales / sensibles (nunca exponer su valor):**
| Columna | Tipo |
|---|---|
| `CLAVE SII` | text — clave del SII |
| `Previred` | text — credencial Previred |
| `RUT` | text — PII |
| `RUT RL` | text — RUT representante legal (PII) |
| `email` | email — PII |
| `Whatsapp` | text — PII |

**🏢 Identificación / segmentación:**
| Columna | Tipo |
|---|---|
| `w` | title (nombre del cliente) |
| `userDefined:ID` | auto_increment_id |
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

## Relevancia para el proyecto

- **Automatización SII (D12):** `RUT` + `CLAVE SII` son exactamente las credenciales para iniciar sesión en el SII y descargar el XLSX. `RUT RL` distingue persona/representante.
- **Centralización (D11):** esta base es la "Etapa 1" donde se centraliza todo antes de migrar a una BD especializada.

## Cómo consultarla (solo lectura)

- `notion-fetch` con el ID o la collection URL → esquema (respuesta grande: ~92K chars, conviene parsear localmente).
- `notion-query-data-sources` (SQL) usando `collection://690945e4-220a-48c3-a888-7fe9ae242d55` como tabla. Requiere plan Business + Notion AI. **Excluir siempre** `CLAVE SII`/`Previred` de cualquier SELECT que se vaya a mostrar.

## Completitud (medida en solo lectura · jun-2026)

- **Total de clientes:** **171**
- Sin `RUT`: **10** (~6%)
- Sin `CLAVE SII` 🔑: **20** (~12%) — no automatizables al SII hasta completarlos
- Sin `email`: **100** (~58%)
- **Listos para automatización SII** (tienen `RUT` + `CLAVE SII`): **~141–151** (entre 20 y 30 con credenciales incompletas según solape; el número exacto quedó pendiente por *rate-limit* de Notion 429).

Confirma lo reportado por el cliente: la base está incompleta / "se dejó estar".

## Pendiente

- Mapear el **esquema de las 3 fuentes auxiliares** (Contable Mayo, RRHH Junio 2026, Tickets - Servicios) para saber qué columnas aportan (ver [`10`](10-fuentes-auxiliares-notion.md)).
- Cruzar las fuentes auxiliares con la sandbox y volcar la **data faltante** (dry-run + confirmación) — D16.
- Obtener el número exacto de "listos para SII" (reintentar la consulta de solape tras el rate-limit Notion 429).
- Identificar **qué 20 clientes** no tienen `CLAVE SII` (prioridad para recuperar la base).
- Confirmar significado de columnas ambiguas (`Column`, `Texto`, `Nº`).
- Definir qué subconjunto se centraliza/normaliza primero.

---

**Anterior:** [`07-flujo-de-datos.md`](07-flujo-de-datos.md) · **Volver al** [`README`](README.md)
