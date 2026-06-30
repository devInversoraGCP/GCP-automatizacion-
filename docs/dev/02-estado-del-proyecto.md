# 02 · Estado del proyecto

> Foto del proyecto al **30 de junio de 2026**. Responde tres preguntas: ¿qué hay?, ¿qué está validado?, ¿qué falta?

## Inventario de activos

Todo lo que existe hoy en el repositorio:

| Archivo | Tipo | Rol |
|---------|------|-----|
| [`PRUEBA1.xlsx`](../../PRUEBA1.xlsx) | Datos (Excel, hoja `CLIENTE1`) | **Fuente de verdad del cálculo.** Contiene las fórmulas reales de las 6 partes |
| [`PRUEBA1.csv`](../../PRUEBA1.csv) | Datos (CSV) | Exportación del Excel (solo valores, sin fórmulas; con problemas de codificación) |
| [`F29.pdf`](../../F29.pdf) | Referencia oficial | Formulario 29 del SII con los ~140 códigos |
| [`CONTEXT.md`](../../CONTEXT.md) | Documentación | Descripción original de la lógica de las 6 partes |
| [`docs/ARQUITECTURA.md`](../ARQUITECTURA.md) | Documentación | Sistema objetivo, diagrama de flujo y el "porqué" de cada etapa |
| [`docs/ROADMAP.md`](../ROADMAP.md) | Documentación | Fases, hitos y criterios de aceptación |
| [`presentacion.html`](../../presentacion.html) | Presentación | Material para cliente (no técnico), con demo interactiva |
| [`docs/dev/`](.) | Documentación | **Esta** documentación para desarrolladores (00–11) |
| [`docs/dev/11-checklist-maestro.md`](11-checklist-maestro.md) | Documentación | **Checklist maestro:** índice ejecutable de todas las fases (tareas → subtareas → algoritmos), con lo hecho marcado |
| [`AGENTS.md`](../../AGENTS.md) | Onboarding IA | Instrucciones y reglas de oro para agentes (opencode lo lee solo) |
| [`.mcp.json`](../../.mcp.json) | Config | Conexión MCP de Notion para Claude Code |
| [`opencode.json`](../../opencode.json) | Config | Conexión MCP de Notion para opencode (token local) |
| `backups/general-customers-data/2026-06-30_all.csv` | Snapshot (CSV) | **Backup base** de Notion (vista "All", 171 registros). Contiene credenciales/PII → no commitear (ver [`09`](09-seguridad-y-respaldo.md)) |

### Activos en Notion (identificados en solo lectura)

| Activo | ID | Rol |
|---|---|---|
| `General Customers Data` *(original)* | `1a23f5e4-0223-46a6-9ad5-16ea823b64ba` / data source `690945e4-220a-48c3-a888-7fe9ae242d55` | Base central del cliente — **no se toca** salvo respaldo + autorización |
| `General Customers Data - AuditAI` *(sandbox)* | `16f12147-b3ea-8354-872b-814f104871b7` / data source `4ff12147-b3ea-82f4-98dd-072067524cdc` | Copia fiel (171 filas) para trabajar sin riesgo |
| `Contable Mayo` | `37212147-b3ea-80fa-ab06-cfd9782372a9` / data source `fdb12147-b3ea-820b-8595-07535e078336` | Fuente auxiliar — ver [`10`](10-fuentes-auxiliares-notion.md) |
| `RRHH JUNIO 2026` | `38712147-b3ea-80f9-9484-e0ad99c94a26` / data source `9c512147-b3ea-8256-a570-871254c13b3d` | Fuente auxiliar — ver [`10`](10-fuentes-auxiliares-notion.md) |
| `Tickets - Servicios` | `16912147-b3ea-82bc-a491-814729bcca4c` / data source `9d312147-b3ea-83bf-b111-877c7b24db75` | Fuente auxiliar — ver [`10`](10-fuentes-auxiliares-notion.md) |

Plan del workspace: **Business** → historial de página **90 días**, papelera **30 días**.

## Qué existe y está validado ✅

- **La lógica de cálculo (las 6 partes)**: definida y, lo más importante, **verificada contra la propuesta del SII** (la nota *"P Verificado con la propuesta del SII"* en la planilla). Es conocimiento de dominio probado en un caso real.
- **El caso de referencia `CLIENTE1`** con resultados conocidos que sirven de *golden test*: total $3, remanente −$158.117.
- **La arquitectura objetivo** y la **hoja de ruta** están documentadas.
- **Material de presentación** para cliente, listo para usar.
- **Documentación dev 00–11** completa (incluye seguridad/respaldo, fuentes auxiliares y **checklist maestro**), con onboarding para agentes ([`AGENTS.md`](../../AGENTS.md)).
- **Notion conectado** (Claude Code + opencode), modo lectura por defecto. **Esquema de "General Customers Data" mapeado** y completitud medida: **171 clientes** (ver [`08-notion-general-customers-data.md`](08-notion-general-customers-data.md)).
- **Red de seguridad montada (30-jun-2026):** plan Business confirmado, snapshot CSV base fechado (`2026-06-30_all.csv`), sandbox `General Customers Data - AuditAI` con 171 filas. Protocolo en [`09-seguridad-y-respaldo.md`](09-seguridad-y-respaldo.md).
- **Fuentes auxiliares identificadas** para recuperar la data faltante (Contable Mayo, RRHH Junio 2026, Tickets - Servicios — ver [`10`](10-fuentes-auxiliares-notion.md)).

## Qué NO existe aún ❌

- **Código ejecutable**: no hay ni una línea de programa. Todo el cálculo vive en fórmulas de Excel.
- **Motor de cálculo**: ninguna implementación que reproduzca las 6 partes fuera del Excel.
- **Parser / ingesta de datos**: nada que lea libros de compra-venta del SII automáticamente.
- **Conciliación automática**: el cuadre contra el SII se hace a mano.
- **Diccionario de códigos F29**: solo están mapeados los códigos del caso actual (62, 48, 151, 77), no los ~140.
- **Esquema de las fuentes auxiliares** mapeado: solo tenemos metadata de las 3 bases (IDs), no sus columnas.
- **Volcado de data faltante** desde las fuentes auxiliares hacia la sandbox: pendiente.
- *(Resuelto)* ~~Control de versiones~~: ✅ repositorio git inicializado (cierre de Fase 0).

## Fase actual

Según [`../ROADMAP.md`](../ROADMAP.md):

```
Fase 0  Cimientos              ██████████  completa
Fase 1  Centralizar + reglas   █░░░░░░░░░  en foco (Frente A primero)
Fase 2  Motor de cálculo       ░░░░░░░░░░
...
```

**Fase 0 completa**: caso real, lógica documentada, formulario de referencia, arquitectura, roadmap, docs dev 00–11, Notion conectado, red de seguridad (snapshot + sandbox), fuentes auxiliares identificadas y **repositorio git inicializado** (`.gitignore` excluye `backups/`).

> 🔁 **Cambio de rumbo (ver D11–D16 y [`07-flujo-de-datos.md`](07-flujo-de-datos.md)):** la prioridad pasó a **centralizar la data primero en Notion** ("General Customers Data") y luego migrar a una BD especializada. La fase actual gira en torno a **recuperar/completar esa base**, alimentándola desde las fuentes auxiliares.

**Próximo hito inmediato:** mapear el esquema de las 3 fuentes auxiliares (Contable Mayo, RRHH Junio 2026, Tickets - Servicios) y cruzarlas con la sandbox para volcar la **data faltante** (20 sin `CLAVE SII`, 10 sin `RUT`, ~100 sin `email`). Dry-run + confirmación del usuario antes de cualquier escritura (ver [`09`](09-seguridad-y-respaldo.md)).

**Hito de valor siguiente:** el **motor de cálculo (MVP)** — un programa que reproduzca exactamente el resultado de `CLIENTE1`. Es la prueba de que toda la arquitectura es viable.

> 🗂️ El desglose ejecutable de todas las fases (tareas → subtareas → algoritmos, con lo hecho marcado) está en [`11-checklist-maestro.md`](11-checklist-maestro.md).

## Riesgos y deuda técnica conocidos

| Riesgo | Detalle | Mitigación prevista |
|--------|---------|---------------------|
| **Codificación de datos** | `PRUEBA1.csv` tiene caracteres rotos (`mi�rcoles`, `N�`) por charset latino y separador `;` | Normalización a UTF-8 en la etapa de ingesta (Fase 3) |
| **Lógica frágil** | El cálculo solo existe en fórmulas de Excel; un cambio accidental lo rompe sin aviso | Trasladar a código con *golden tests* (Fase 2) |
| ~~Sin control de versiones~~ ✅ | Resuelto: repositorio git inicializado | `git init` + `.gitignore` (excluye `backups/`) hecho |
| **Códigos sin verificar** | El mapeo de códigos F29 está incompleto y sin contraste normativo | Diccionario verificado en Fase 1 |
| **Base de clientes incompleta** | "General Customers Data" tiene datos faltantes (20 sin `CLAVE SII`, 10 sin `RUT`, 100 sin `email`) | Recuperar/completar la base (prioridad actual) |

---

**Anterior:** [`01-dominio-F29.md`](01-dominio-F29.md) · **Siguiente:** [`03-estado-del-arte.md`](03-estado-del-arte.md)
