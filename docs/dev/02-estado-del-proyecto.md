# 02 · Estado del proyecto

> Foto del proyecto al **07 de julio de 2026**. Responde tres preguntas: ¿qué hay?, ¿qué está validado?, ¿qué falta?

## Inventario de activos

Todo lo que existe hoy en el repositorio:

| Archivo | Tipo | Rol |
|---------|------|-----|
| [`PRUEBA1.xlsx`](../../PRUEBA1.xlsx) | Datos (Excel, hoja `CLIENTE1`) | **Golden test + entregable simplificado** al cliente (resumen por correo). Contiene las fórmulas de las 6 partes, pero **NO es la autoridad del cálculo** (esa es `F29.pdf`, ver D24) |
| [`PRUEBA1.csv`](../../PRUEBA1.csv) | Datos (CSV) | Exportación del Excel (solo valores, sin fórmulas; con problemas de codificación) |
| [`F29.pdf`](../../F29.pdf) | **Fuente de verdad madre del cálculo** | Formulario 29 oficial del SII (~140 códigos): define **qué** se calcula por cada caso de cliente (D24) |
| [`CONTEXT.md`](../../CONTEXT.md) | Documentación | Descripción original de la lógica de las 6 partes |
| [`docs/ARQUITECTURA.md`](../ARQUITECTURA.md) | Documentación | Sistema objetivo, diagrama de flujo y el "porqué" de cada etapa |
| [`docs/ROADMAP.md`](../ROADMAP.md) | Documentación | Fases, hitos y criterios de aceptación |
| [`presentacion.html`](../../presentacion.html) | Presentación | Material para cliente (no técnico), con demo interactiva |
| [`docs/dev/`](.) | Documentación | **Esta** documentación para desarrolladores (00–24) |
| [`docs/dev/11-checklist-maestro.md`](11-checklist-maestro.md) | Documentación | **Checklist maestro:** índice ejecutable de todas las fases (tareas → subtareas → algoritmos), con lo hecho marcado |
| [`docs/dev/12-fase1-plan-detallado.md`](12-fase1-plan-detallado.md) | Documentación | Plan detallado de la Fase 1: centralización + formalización de reglas |
| [`docs/dev/13-fase-c-volcado-nuevos-registros.md`](13-fase-c-volcado-nuevos-registros.md) | Documentación | Ejecución de la Fase C: 163 registros nuevos en la sandbox |
| [`docs/dev/14-construccion-dataset-y-anomalias.md`](14-construccion-dataset-y-anomalias.md) | Documentación | Cierre del Frente A: validación y decisiones (resueltas 02-jul) |
| [`docs/dev/15-barrido-bases-contables-mensuales.md`](15-barrido-bases-contables-mensuales.md) | Documentación | Plan/guía ejecutable para rescatar RUTs faltantes desde las bases contables **mensuales** (Febrero, etc.) |
| [`docs/dev/23-automatizacion-notion-contable-correo.md`](23-automatizacion-notion-contable-correo.md) | Documentación | 🆕 **Foco (07-jul):** automatización de Notion — botón "Enviar Correo F29" por fila → correo al cliente + duplicación mensual. Guía ejecutable con código del backend, plantilla del correo y **el payload real del webhook de Notion** (`{"source": {...}, "data": {...}}` — props anidadas en `data`) |
| [`notion_automation/`](../../notion_automation/) | **Código (backend)** | 🆕 **E2E verificado (07-jul):** `app.py` (Flask `host="0.0.0.0"`, `--test`/`--test-rut`, logging sin PII), `email_sender.py` (SMTP Gmail por asesor + inline CID logo/firma), `notion_client.py` (helpers REST + `find_page_by_rut()`), `asesores_smtp.json` (gitignored, Sebastián con App Password). Cloud-ready: `requirements.txt`, `runtime.txt`, `Procfile` |
| [`notion_automation/email_templates/`](../../notion_automation/email_templates/) | Código (plantillas) | Plantilla del correo F29: `f29_email.html` (email-safe, inline CID), `f29_email.txt`, `README.md` y `preview-correo-f29.html`. Aplican los 4 feedbacks del usuario: asunto fijo `"Asesoría Honorario"`, fecha sin paréntesis, info adicional flexible, honorarios + datos de transferencia de GCP |
| [`MISION-ARREGLAR-CORREO-F29.md`](../../MISION-ARREGLAR-CORREO-F29.md) | Documentación | Misión Claude Opus 4.8 (4 objetivos: backend, plantilla, GCP feedback, cloud-ready) — ✅ completada |
| [`MIGRACION-A-RENDER.md`](../../MIGRACION-A-RENDER.md) | Documentación | Manual de migración del backend local (ngrok) a Render (URL estable, 24/7) — 405 líneas |
| [`AGENTS.md`](../../AGENTS.md) | Onboarding IA | Instrucciones y reglas de oro para agentes (opencode lo lee solo) |
| [`.mcp.json`](../../.mcp.json) | Config | Conexión MCP de Notion para Claude Code |
| [`opencode.json`](../../opencode.json) | Config | Conexión MCP de Notion para opencode (token local) |
| `backups/general-customers-data/2026-06-30_all.csv` | Snapshot (CSV) | **Backup base** de Notion (vista "All", 171 registros). Contiene credenciales/PII → no commitear (ver [`09`](09-seguridad-y-respaldo.md)) |

### Activos en Notion (identificados en solo lectura)

| Activo | ID | Rol |
|---|---|---|
| `General Customers Data` *(original)* | `1a23f5e4-0223-46a6-9ad5-16ea823b64ba` / data source `690945e4-220a-48c3-a888-7fe9ae242d55` | Base central del cliente — **no se toca** salvo respaldo + autorización |
| `General Customers Data - AuditAI` *(sandbox)* | `16f12147-b3ea-8354-872b-814f104871b7` / data source `4ff12147-b3ea-82f4-98dd-072067524cdc` | Copia de trabajo — **331 filas** (334 tras Fase C; −3 retirados a "Descartados AuditAI" el 02-jul) |
| `🗑️ Descartados AuditAI` | `39112147-b3ea-812e-822b-ff1afac2c9eb` | Página donde se movieron 3 clientes descartados por el cliente (recuperables) |
| `Contable Mayo` | `37212147-b3ea-80fa-ab06-cfd9782372a9` / data source `fdb12147-b3ea-820b-8595-07535e078336` | Fuente auxiliar — ver [`10`](10-fuentes-auxiliares-notion.md) |
| `RRHH JUNIO 2026` | `38712147-b3ea-80f9-9484-e0ad99c94a26` / data source `9c512147-b3ea-8256-a570-871254c13b3d` | Fuente auxiliar — ver [`10`](10-fuentes-auxiliares-notion.md) |
| `Tickets - Servicios` | `16912147-b3ea-82bc-a491-814729bcca4c` / data source `9d312147-b3ea-83bf-b111-877c7b24db75` | Fuente auxiliar — ver [`10`](10-fuentes-auxiliares-notion.md) |

Plan del workspace: **Business** → historial de página **90 días**, papelera **30 días**.

## Qué existe y está validado ✅

- **La lógica de cálculo (las 6 partes)**: definida y, lo más importante, **verificada contra la propuesta del SII** (la nota *"P Verificado con la propuesta del SII"* en la planilla). Es conocimiento de dominio probado en un caso real.
- **El caso de referencia `CLIENTE1`** con resultados conocidos que sirven de *golden test*: total $3, remanente −$158.117.
- **La arquitectura objetivo** y la **hoja de ruta** están documentadas.
- **Material de presentación** para cliente, listo para usar.
- **Documentación dev 00–24** completa (incluye seguridad/respaldo, fuentes auxiliares, **checklist maestro**, plan Fase 1, ejecución Fase C, cierre del Frente A, plan de barrido de bases mensuales, especificación literal del cálculo validada por GCP, integración impuesto único, registro de variables F29, spike F29, vía del certificado digital, **automatización de Notion + correo F29** y **arquitectura multi-automatización** para RRHH y Tickets), con onboarding para agentes ([`AGENTS.md`](../../AGENTS.md)).
- **Notion conectado** (Claude Code + opencode), modo lectura por defecto salvo la sandbox (escritura autorizada). **Esquema mapeado** y completitud medida: **331 clientes** en la sandbox (ver [`08-notion-general-customers-data.md`](08-notion-general-customers-data.md)).
- **Red de seguridad montada (30-jun-2026):** plan Business confirmado, snapshot CSV base fechado (`2026-06-30_all.csv`), sandbox `General Customers Data - AuditAI`. Protocolo en [`09-seguridad-y-respaldo.md`](09-seguridad-y-respaldo.md)).
- **Fuentes auxiliares identificadas** (Contable Mayo, RRHH Junio 2026, Tickets - Servicios — ver [`10`](10-fuentes-auxiliares-notion.md)). **Nuevo (02-jul):** se descubrieron bases contables **mensuales** adicionales (Febrero, etc.) como fuentes extra — ver [`15`](15-barrido-bases-contables-mensuales.md).
- **Fase A+B+C de centralización ejecutada (01-jul-2026):** 151 datos recuperados/corregidos + 163 registros nuevos; base de 171 → 334. Logs en `backups/general-customers-data/`.
- **Decisiones de cierre del Frente A resueltas (02-jul-2026):** 3 clientes descartados retirados, duplicado SOCIAL UP mantenido, 19 emails inválidos etiquetados (`Email por revisar`), campos sin fuente dejados opcionales, y XIT recuperado (RUT desde Contable Febrero). Base: **331 filas**. Ver [`14`](14-construccion-dataset-y-anomalias.md) §4.
- **Validación con Pandera/Pydantic** ejecutada: Pandera pasa; los errores Pydantic eran emails inválidos (ya etiquetados). Detalle en [`14`](14-construccion-dataset-y-anomalias.md).
- **Trazabilidad de origen (D23):** columna `Origen` y relación `Origen Contable Mayo` pobladas al 100%.
- 🆕 **E2E del correo F29 exitoso (07-jul-2026, Frente N):** el flujo completo **botón "Enviar Correo F29" en Notion → webhook → backend Flask → SMTP Gmail → correo al cliente + write-back Status = "1) Enviado y Pendiente"** funciona de punta a punta. Probado sobre la fila `ZZ_TEST AuditAI` en Contable Junio (base operativa), correo enviado desde `sebastianrobles@inversoragcp.com` a `fbrunel@miuandes.cl`. **Descubrimiento clave:** Notion envía el webhook como `{"source": {...}, "data": {...}}` (props anidadas en `data`, no en la raíz) y la UI del botón **no expone `page_id`** como variable seleccionable — solo deja elegir propiedades existentes (Rut, Email, Customers). Solución: **identificación de fila por RUT** + extractor recursivo robusto (`_buscar_clave`) que encuentra `page_id` (en `source`, gratis) o `Rut` en cualquier nivel. 5/5 casos de test pasan. Ver [`23`](23-automatizacion-notion-contable-correo.md) §5.3/§5.4/§5.6.

## Qué NO existe aún ❌

- **Código ejecutable del cálculo F29**: no hay ni una línea del motor de cálculo. Todo el cálculo vive en fórmulas de Excel. *(El backend del correo F29 sí existe y está verificado — eso es otra cosa, ver Frente N.)*
- **Motor de cálculo**: ninguna implementación que reproduzca las 6 partes fuera del Excel.
- **Parser / ingesta de datos**: nada que lea libros de compra-venta del SII automáticamente.
- **Conciliación automática**: el cuadre contra el SII se hace a mano.
- **Diccionario de códigos F29**: solo están mapeados los códigos del caso actual (62, 48, 151, 77), no los ~140.
- *(Resuelto)* ~~Esquema de las fuentes auxiliares~~: ✅ mapeado en [`10`](10-fuentes-auxiliares-notion.md) y [`12`](12-fase1-plan-detallado.md).
- *(Resuelto)* ~~Volcado de data faltante~~: ✅ Fase A+B+C ejecutada el 01-jul-2026 (ver [`13`](13-fase-c-volcado-nuevos-registros.md)).
- *(Resuelto)* ~~Control de versiones~~: ✅ repositorio git inicializado (cierre de Fase 0).
- *(Resuelto)* ~~Backend del correo F29~~: ✅ **E2E verificado 07-jul-2026** — `app.py`/`email_sender.py`/`notion_client.py` + columnas en Contable Junio + botón configurado. Ver [`23`](23-automatizacion-notion-contable-correo.md) §5.6.
- **Duplicación mensual de Contable** (`duplicar_mes.py`): pendiente (Fase 2 del doc 23).
- **Migración a la nube (Render)**: pendiente — manual listo en [`MIGRACION-A-RENDER.md`](../../MIGRACION-A-RENDER.md).
- **App Passwords de 4 asesores**: solo Sebastián Robles tiene la suya (verificada en el E2E). Constanza, Carlos, Andrea, Matilde pendientes (Andrea y Matilde además sin contraseña normal).

## Fase actual

Según [`../ROADMAP.md`](../ROADMAP.md):

```
Fase 0  Cimientos              ██████████  completa
Fase 1  Centralizar + reglas   ████████░░  en foco (Frente A casi cerrado)
Fase 2  Motor de cálculo       ░░░░░░░░░░
...
```

**Fase 0 completa**: caso real, lógica documentada, formulario de referencia, arquitectura, roadmap, docs dev 00–11, Notion conectado, red de seguridad (snapshot + sandbox), fuentes auxiliares identificadas y **repositorio git inicializado** (`.gitignore` excluye `backups/`).

> 🔁 **Cambio de rumbo (ver D11–D16 y [`07-flujo-de-datos.md`](07-flujo-de-datos.md)):** la prioridad pasó a **centralizar la data primero en Notion** ("General Customers Data") y luego migrar a una BD especializada. La fase actual gira en torno a **recuperar/completar esa base**, alimentándola desde las fuentes auxiliares.

**Próximo hito inmediato:** las 4 decisiones de cierre del Frente A **ya se resolvieron** (02-jul, ver [`14`](14-construccion-dataset-y-anomalias.md) §4). Queda **un solo** pendiente para cerrar el gate: rescatar el `RUT` de **Steven** (ID 48) — vía barrido de bases mensuales ([`15`](15-barrido-bases-contables-mensuales.md)) o consulta al adviser. Con eso, el Frente A queda cerrado.

**Hito de valor siguiente:** el **motor de cálculo (MVP)** — un programa que reproduzca exactamente el resultado de `CLIENTE1`. Es la prueba de que toda la arquitectura es viable. El Frente B (formalización de reglas del F29) arranca solo tras cerrar el gate del Frente A (D18). 🆕 **Avance clave (04/05-jul-2026):** los **expertos de GCP validaron el cálculo P1–P6** y entregaron las **rutas reales de extracción en el SII** (RCV pestañas «VENTA»/«COMPRA», propuesta del F29 → casillas 504/115, informe anual de boletas). La especificación operativa quedó en [`17`](17-especificacion-literal-calculo-f29.md); las columnas de RRHH para la casilla 48 ya están integradas a la base central ([`18`](18-integracion-impuesto-unico-imposiciones.md)).

> 🗂️ El desglose ejecutable de todas las fases (tareas → subtareas → algoritmos, con lo hecho marcado) está en [`11-checklist-maestro.md`](11-checklist-maestro.md).

> 🆕 **Foco (07-jul-2026) — automatización de Notion + correo F29:** la automatización del SII
> se **pausa** (login bloqueado por anti-bot F5 — ver [`21`](21-resultado-spike-f29.md); la vía
> correcta es **certificado digital** + API SII, [`22`](22-via-oficial-certificado-digital-api-sii.md),
> pendiente de gestión de negocio). Mientras, el foco es **automatizar las páginas Contable de
> Notion**: **(B)** un botón "Enviar Correo F29" por fila → webhook → backend → correo al cliente con su
> monto; **(A)** la duplicación mensual de la página Contable + alta de clientes nuevos.
>
> 🎉 **Hito (07-jul-2026): E2E del correo F29 verificado.** Botón → webhook → backend Flask →
> SMTP Gmail → correo + write-back Status. Fila `ZZ_TEST AuditAI` en Contable Junio. Falta:
> (1) **4 App Passwords** de asesores restantes, (2) **`duplicar_mes.py`** (Fase 2), (3) **migración
> a Render** (Fase 3, manual en [`MIGRACION-A-RENDER.md`](../../MIGRACION-A-RENDER.md)). Guía
> ejecutable completa en [`23`](23-automatizacion-notion-contable-correo.md).
>
> 🆕 **Expansión multi-automatización (09-jul-2026):** la arquitectura del backend se extiende
> para soportar **múltiples páginas de Notion** desde un solo sistema, con handlers modulares
> (`handlers/f29.py`, `handlers/rrhh.py`, `handlers/tickets.py`). **RRHH JUNIO 2026** es la
> siguiente en implementarse, seguida de **Tickets - Servicios**. Patrón y detalle en
> [`24-arquitectura-multi-automatizacion.md`](24-arquitectura-multi-automatizacion.md).

## Riesgos y deuda técnica conocidos

| Riesgo | Detalle | Mitigación prevista |
|--------|---------|---------------------|
| **Codificación de datos** | `PRUEBA1.csv` tiene caracteres rotos (`mi�rcoles`, `N�`) por charset latino y separador `;` | Normalización a UTF-8 en la etapa de ingesta (Fase 3) |
| **Lógica frágil** | El cálculo solo existe en fórmulas de Excel; un cambio accidental lo rompe sin aviso | Trasladar a código con *golden tests* (Fase 2) |
| ~~Sin control de versiones~~ ✅ | Resuelto: repositorio git inicializado | `git init` + `.gitignore` (excluye `backups/`) hecho |
| **Códigos sin verificar** | El mapeo de códigos F29 está incompleto y sin contraste normativo | Diccionario verificado en Fase 1 |
| ~~Casos residuales por decidir~~ ✅ | Resuelto 02-jul: 3 descartados retirados · duplicado SOCIAL UP mantenido · 19 emails etiquetados · campos sin fuente opcionales | Decisiones aplicadas con backup + log ([`14`](14-construccion-dataset-y-anomalias.md) §4) |
| **1 RUT pendiente** | Solo `Steven` (ID 48) sin RUT | Barrido de bases mensuales ([`15`](15-barrido-bases-contables-mensuales.md)) o consulta al adviser |
| **Base de clientes casi completa** | 331 clientes · 330 con `RUT` válido · 323 con `CLAVE SII` · email sigue bajo (secundario) | RUT + Clave SII casi al 100%; el resto es metadata secundaria |

---

**Anterior:** [`01-dominio-F29.md`](01-dominio-F29.md) · **Siguiente:** [`03-estado-del-arte.md`](03-estado-del-arte.md)
