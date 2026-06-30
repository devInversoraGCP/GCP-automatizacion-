# Documentación dev · AuditAI

Bienvenido a la documentación para desarrolladores de **AuditAI**. Su objetivo es que cualquier persona —empezando por el propio equipo creador— pueda entender el proyecto de forma **detallada y completa**: el porqué, el dominio tributario, el estado actual y el panorama del mercado.

## Cómo leer esta documentación

Léela en orden, de **00 a 10**. Cada documento enlaza al siguiente.

| # | Documento | Qué encontrarás | Estado |
|---|-----------|-----------------|:------:|
| 00 | [Introducción](00-introduccion.md) | Qué es AuditAI, la visión, el problema, el alcance y los principios de diseño | ✅ |
| 01 | [El dominio: F29 e IVA](01-dominio-F29.md) | **Documento núcleo.** El dominio tributario chileno explicado para devs, con el caso real `CLIENTE1` trabajado de punta a puntada | ✅ |
| 02 | [Estado del proyecto](02-estado-del-proyecto.md) | Inventario de activos, qué está validado, qué falta, fase actual y deuda técnica | ✅ |
| 03 | [Estado del arte](03-estado-del-arte.md) | Cómo se resuelve hoy el F29 (SII, software contable, Excel) y el diferencial de AuditAI | ✅ |
| 04 | [Glosario](04-glosario.md) | Términos tributarios y técnicos para consulta rápida | ✅ |
| 05 | [Decisiones y preguntas abiertas](05-decisiones-y-preguntas.md) | Decisiones de diseño (ADR-lite) confirmadas por el creador y temas por resolver | ✅ |
| 06 | [Stack técnico](06-stack-tecnico.md) | Recomendación de stack 2026 (data-driven, preciso, multiempresa), con comparativas y fuentes | ✅ |
| 07 | [Flujo de datos y centralización](07-flujo-de-datos.md) | 🔁 **Cambio de rumbo:** ingesta automatizada (Notion → SII → XLSX) y centralización en Notion ("General Customers Data") primero, BD especializada después | ✅ |
| 08 | [Notion: "General Customers Data"](08-notion-general-customers-data.md) | Esquema (22 columnas) de la base central del cliente, mapeado en **solo lectura** | ✅ |
| 09 | [Seguridad y respaldo](09-seguridad-y-respaldo.md) | 🛡️ **Protocolo obligatorio** antes de tocar Notion: 3 capas (sandbox + backup externo + recuperación nativa), checklist y log de auditoría | ✅ |
| 10 | [Fuentes auxiliares Notion](10-fuentes-auxiliares-notion.md) | 📥 Las 3 bases (Contable Mayo, RRHH Junio 2026, Tickets - Servicios) de donde recuperar la **data faltante** para llenar la sandbox | ✅ |
| 11 | [Checklist maestro](11-checklist-maestro.md) | ✅ **Índice/todolist de inicio a fin:** todas las fases → tareas → subtareas → algoritmos, con lo hecho marcado. Fuente única del avance | ✅ |
| 12 | [Fase 1 — plan detallado](12-fase1-plan-detallado.md) | 🔬 **Plan profundo de la Fase 1:** centralización (matching, API Notion, volcado) + formalización (catálogo oficial de documentos SII, códigos F29, 6 partes) | ✅ |

## Documentos relacionados (fuera de `dev/`)

Estos ya existen y **no se duplican aquí** — se enlazan como fuente única de verdad:

- [`../ARQUITECTURA.md`](../ARQUITECTURA.md) — sistema objetivo, diagrama de flujo y el "porqué" de cada etapa.
- [`../ROADMAP.md`](../ROADMAP.md) — fases, hitos y criterios de aceptación.
- [`../../CONTEXT.md`](../../CONTEXT.md) — descripción original de la lógica de las 6 partes.

## Archivos de datos y referencia

- [`../../PRUEBA1.xlsx`](../../PRUEBA1.xlsx) — planilla `CLIENTE1`: **fuente de verdad del cálculo** (con fórmulas).
- [`../../PRUEBA1.csv`](../../PRUEBA1.csv) — exportación en CSV (solo valores).
- [`../../F29.pdf`](../../F29.pdf) — Formulario 29 oficial del SII (~140 códigos).
- [`../../presentacion.html`](../../presentacion.html) — presentación para cliente (no técnica), con demo interactiva.

## Documentación futura (pendiente)

Lo que vendrá en próximas iteraciones de la versión dev, a medida que avancen las fases del [roadmap](../ROADMAP.md):

| Documento | Cuándo | Estado |
|-----------|--------|:------:|
| Diccionario completo de los ~140 códigos del F29 | Fase 1 | 📋 |
| Modelo de datos (esquema de libros de compra/venta) | Fase 1–2 | 📋 |
| Guía de setup del entorno de desarrollo | Fase 2 (al haber código) | 📋 |
| Documentación del motor de cálculo | Fase 2 | 📋 |
| Especificación de la conciliación/auditoría | Fase 4 | 📋 |

---

**Leyenda de estado:** ✅ listo · 🚧 en progreso · 📋 pendiente
