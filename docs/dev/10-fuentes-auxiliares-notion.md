# 10 · Fuentes auxiliares en Notion (para completar General Customers Data)

> Documento dedicado (principio de granularidad **D3**). Desarrolla el **cambio de rumbo** acordado con el cliente: recuperar y completar la base central ["General Customers Data"](`08-notion-general-customers-data.md`) tomándola como contenedor, y alimentar los **datos faltantes** desde otras páginas/bases que **sí se han usado últimamente** y donde vive esa información. Opera siempre sobre la **sandbox** [`General Customers Data - AuditAI`](08-notion-general-customers-data.md) (ver [`09-seguridad-y-respaldo.md`](09-seguridad-y-respaldo.md)).
>
> ⚠️ **Acceso escalonado a Notion:** lectura por defecto; cualquier volcado/copia de datos faltantes hacia la sandbox se hace con **dry-run + confirmación del usuario** (ver [`../../AGENTS.md`](../../AGENTS.md) y [`09`](09-seguridad-y-respaldo.md)).

## Motivo

La base central "se dejó estar" (ver [`02`](02-estado-del-proyecto.md) y [`08`](08-notion-general-customers-data.md)): 20 clientes sin `CLAVE SII`, 10 sin `RUT`, ~100 sin `email`. La operación, sin embargo, siguió en **otras hojas/bases** del mismo workspace; ahí debe estar la data faltante que buscamos. Este documento inventaría esas fuentes auxiliares.

## Las 3 bases fuente identificadas (30-jun-2026)

Todas **activas** (`last_edited` = 30-jun-2026) y bajo el mismo workspace de `Inversora GCP SpA` → `CONTABILIDAD - SII - TESORERÍA`.

| # | Nombre | ID database | ID data source | Creada | Editada |
|---|---|---|---|---|---|
| 1 | **Contable Mayo** | `37212147-b3ea-80fa-ab06-cfd9782372a9` | `fdb12147-b3ea-820b-8595-07535e078336` | 01-jun-2026 | 30-jun-2026 |
| 2 | **RRHH JUNIO 2026** | `38712147-b3ea-80f9-9484-e0ad99c94a26` | `9c512147-b3ea-8256-a570-871254c13b3d` | 22-jun-2026 | 30-jun-2026 |
| 3 | **Tickets - Servicios** | `16912147-b3ea-82bc-a491-814729bcca4c` | `9d312147-b3ea-83bf-b111-877c7b24db75` | 02-jun-2026 | 30-jun-2026 |

### 1 · Contable Mayo
Base de operación **contable** del período mayo. Fuente candidata para completar: `RUT`, `CLAVE SII`, `Adviser Accounting`, fechas, contacto y datos de facturación presentes en su operación mensual.

### 2 · RRHH JUNIO 2026
Base de operación **remuneraciones / RR.HH.** del período junio. Fuente candidata para completar: `Adviser RR.HH`, `email`, `Whatsapp` y referencias de personas (RUT RL).

### 3 · Tickets - Servicios
Dashboard transversal de **gestión de servicios contables**. Fuente candidata para recuperar el vínculo cliente → responsable, estado del servicio y referencias cruzadas (utiles para los 20 sin `CLAVE SII` y los 10 sin `RUT`).

## Cómo se relacionan con General Customers Data

- **Llave de cruce esperada:** `RUT` (cuando existe) y, en su defecto, el nombre del cliente (`w` — title). El match se hace primero por `RUT` y luego por nombre normalizado.
- **Dirección del flujo:** las 3 bases son **fuentes de datos** (solo lectura); el destino de la data faltante es la **sandbox** `General Customers Data - AuditAI`, nunca el original (ver [`09`](09-seguridad-y-respaldo.md)).
- **Política:** ningún campo se sobreescribe si ya está poblado, a menos que el usuario decida actualizar un valor obsoleto caso a caso.

## Qué falta por hacer sobre estas fuentes

1. **Mapear el esquema de cada una** (propiedades/columnas): pendiente de `query-data-source` con `page_size=1` por base (ver Preguntas abiertas en [`05`](05-decisiones-y-preguntas.md)).
2. **Determinar el solape cliente a cliente** entre cada fuente auxiliar y la sandbox (qué porcentaje de los 171 aparece en cada una).
3. **Campo a campo:** para cada dato faltante en la sandbox, identificar de qué columna de qué fuente auxiliar proviene.
4. **Definir el protocolo de volcado**: dry-run del diff → confirmación del usuario → escritura en la sandbox por clave estable (`userDefined:ID` o `RUT`).

## Seguridad

- Estas bases también pueden contener **PII / credenciales** (`RUT`, `email`, `Whatsapp`, etc.). Aplican las mismas reglas que al original:
  - **No imprimir** valores sensibles en los outputs del agente (ver [`../../AGENTS.md`](../../AGENTS.md)).
  - Los datos sensibles **no se redactan** ni se sustituyen de la base — son insumo legítimo de la automatización SII (ver D12). Lo que se evita es su exposición en logs/respuestas, no su almacenamiento.
- Antes de cualquier volcado hacia la sandbox: backup fresco y dry-run (ver [`09`](09-seguridad-y-respaldo.md)).

---

**Anterior:** [`09-seguridad-y-respaldo.md`](09-seguridad-y-respaldo.md) · **Volver al** [`README`](README.md)