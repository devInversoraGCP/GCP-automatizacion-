# 00 · Introducción

> Punto de partida de la documentación dev. Si llegas nuevo al proyecto, empieza aquí y sigue el orden 00 → 05 (ver [README](README.md)).

## Qué es AuditAI

AuditAI es un asistente que **lee los documentos contables de una empresa, calcula su declaración mensual de impuestos (Formulario 29 del SII de Chile) y la audita contra la propuesta oficial del SII**, marcando automáticamente cualquier discrepancia y explicándola.

En una frase: *convierte el armado manual del F29 —hoy hecho en planillas Excel— en un proceso automático, verificable y auditable.*

## El problema (y por qué es automatizable)

Cada mes, un contador o asesor debe declarar el F29 de cada empresa que administra. Hoy ese trabajo consiste en:

1. Reunir los documentos de ventas y compras del período.
2. Sumar el IVA de cada grupo, restar, arrastrar el remanente del mes anterior.
3. Trasladar esos totales a los códigos correctos del Formulario 29.
4. Cuadrar el resultado contra la propuesta que el SII genera automáticamente.

Es un proceso **repetitivo, basado en reglas fijas y con datos estructurados** — exactamente el perfil de tarea que se puede automatizar. El riesgo de hacerlo a mano es doble: tiempo perdido y errores que cuestan dinero (pagar de más) o multas (declarar mal).

El conocimiento del cálculo ya existe y está validado: vive en las fórmulas de la planilla [`PRUEBA1.xlsx`](../../PRUEBA1.xlsx) (hoja `CLIENTE1`) y está descrito en [`CONTEXT.md`](../../CONTEXT.md). AuditAI lo formaliza en código y le suma la capa de auditoría.

## Alcance

**Qué SÍ resuelve AuditAI:**
- Cálculo automático del IVA mensual y los otros impuestos del F29 (PPM, retenciones).
- Mapeo de los resultados a los códigos oficiales del Formulario 29.
- Conciliación (auditoría) del cálculo propio contra la propuesta del SII.
- Explicación en lenguaje natural de las diferencias detectadas (capa de IA, fase posterior).

**Qué NO es AuditAI (fuera de alcance):**
- No es un software contable completo (no lleva la contabilidad general, no emite documentos tributarios, no maneja remuneraciones ni inventario).
- No reemplaza el criterio del profesional: **propone y verifica; el contador decide y declara**.
- La IA **no determina montos**: los números salen de reglas deterministas y verificables. La IA solo explica y detecta anomalías.

## Principios de diseño

Estos principios guían todas las decisiones técnicas (detalle en [`../ARQUITECTURA.md`](../ARQUITECTURA.md)):

1. **Cálculo determinista; IA opcional.** El monto del F29 debe poder reproducirse y verificarse con reglas. La IA es una capa que explica y detecta, nunca la que calcula el impuesto.
2. **Auditable por diseño.** Cada cifra de salida debe poder rastrearse hasta los documentos de origen que la produjeron.
3. **Separación ingesta → cálculo → salida.** Las reglas tributarias cambian con la ley; aislarlas evita reescribir todo el sistema ante cada cambio.

## Hacia dónde va

El estado actual y los próximos pasos están en [`02-estado-del-proyecto.md`](02-estado-del-proyecto.md) y en la hoja de ruta [`../ROADMAP.md`](../ROADMAP.md). El siguiente hito técnico es el **motor de cálculo (MVP)**: un programa que reproduzca la planilla y dé exactamente el resultado del caso real `CLIENTE1`.

---

**Siguiente:** [`01-dominio-F29.md`](01-dominio-F29.md) — el dominio tributario explicado para desarrolladores.
