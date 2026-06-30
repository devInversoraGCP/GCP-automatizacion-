# AGENTS.md — Instrucciones para agentes de IA (AuditAI)

> Este archivo orienta a cualquier agente de IA (opencode, Claude Code, etc.) que trabaje en este repo. Léelo completo antes de actuar.

## Qué es AuditAI

Asistente que **lee los datos contables de una empresa, calcula el Formulario 29 del SII (Chile) y lo audita contra la propuesta del SII**, marcando y explicando discrepancias. Objetivo: automatizar y profesionalizar una asesoría contable **data-driven**.

## ⚠️ Reglas de oro (NO negociables)

1. **Notion se trata con cuidado (acceso escalonado).** Los datos del cliente son **sagrados**.
   - **Por defecto: solo lectura.** Usar solo herramientas de lectura (`notion-search`, `notion-fetch`, `notion-query-data-sources`). No crear, editar, mover, duplicar ni borrar nada automáticamente.
   - **Con autorización explícita del usuario (caso a caso):** se permiten operaciones de escritura/edición/borrado, de preferencia **sobre una copia**. El agente debe pedir confirmación antes de cada escritura y mostrar exactamente qué cambiará.
   - **Respaldo obligatorio + sandbox:** antes de CUALQUIER escritura hay que tener backup fechado y trabajar sobre una copia, **nunca** sobre la tabla original. Protocolo completo: [`docs/dev/09-seguridad-y-respaldo.md`](docs/dev/09-seguridad-y-respaldo.md).
   - **Cuando el sistema sea robusto y seguro (meta futura):** se abrirá a operaciones automáticas completas (lectura, escritura, edición, borrado). El criterio de "robustez" queda por definir (ver `docs/dev/05-decisiones-y-preguntas.md`).
   - En todas las etapas, las credenciales (`CLAVE SII`, `Previred`) y PII (RUT/email/Whatsapp) **nunca** se imprimen, registran ni salen del entorno.
2. **Credenciales y PII en outputs, no en storage.** Las columnas `CLAVE SII` y `Previred` (y RUT/email/Whatsapp como PII) **nunca** se imprimen, registran ni exponen en las respuestas o outputs del agente. **No** se redactan ni se sustituyen en la base: son insumo legítimo de la automatización SII (ver D12). Lo que se evita es su exposición en logs/respuestas, no su almacenamiento.
3. **El cálculo es determinista, la IA no calcula montos.** Los números del F29 salen de funciones matemáticas verificables (100% data-driven). La IA solo explica y detecta anomalías.
4. **Idioma:** español.
5. **MVP-first:** lo justo y necesario primero; mejoras después. "A la calma, de a poquito."
6. **Docs granulares:** preferir crear documentos nuevos y acotados antes que engordar archivos (no saturar la ventana de contexto).
7. **El usuario valida.** Proponer la solución y esperar su feedback antes de cambios grandes. Respaldar recomendaciones técnicas con fuentes oficiales.
8. **Protocolo de respaldo obligatorio.** Antes de CUALQUIER escritura hay que tener backup fechado y trabajar sobre una copia, **nunca** sobre la tabla original. Protocolo completo: [`docs/dev/09-seguridad-y-respaldo.md`](docs/dev/09-seguridad-y-respaldo.md).

## Por dónde empezar (orden de lectura)

Toda la documentación viva está en [`docs/dev/`](docs/dev/). Léela en orden:

1. [`docs/dev/README.md`](docs/dev/README.md) — índice.
2. `00-introduccion` → `11` (introducción, dominio F29, estado, estado del arte, glosario, **decisiones D1–D17**, stack, flujo de datos, Notion central, **seguridad/respaldo**, **fuentes auxiliares Notion**, **checklist maestro**).
3. Contexto de negocio: [`CONTEXT.md`](CONTEXT.md). Datos de referencia: [`PRUEBA1.xlsx`](PRUEBA1.xlsx) (caso `CLIENTE1`), [`F29.pdf`](F29.pdf).
4. **Checklist maestro** [`docs/dev/11-checklist-maestro.md`](docs/dev/11-checklist-maestro.md) — el índice ejecutable del avance (qué hacer y en qué orden, con lo hecho marcado). Empieza por aquí para orientarte rápido.

## Estado actual (30-jun-2026)

- Fase 0 (cimientos) **completa** → entrando a Fase 1.
- **Cambio de rumbo:** centralizar datos primero en **Notion** (base "General Customers Data"), luego BD especializada (ver [`docs/dev/07-flujo-de-datos.md`](docs/dev/07-flujo-de-datos.md)).
- **Notion conectado en modo lectura por defecto** (escritura/edición/borrado solo con autorización explícita del usuario; automatización completa queda para cuando el sistema sea robusto). Esquema de "General Customers Data" ya mapeado: [`docs/dev/08-notion-general-customers-data.md`](docs/dev/08-notion-general-customers-data.md).
- **Red de seguridad montada (30-jun-2026):** plan Notion **Business** (historial 90 días, papelera 30 días) · **snapshot CSV base** en `backups/general-customers-data/2026-06-30_all.csv` (171 registros, vista "All") · **sandbox** `General Customers Data - AuditAI` (ID `16f12147-b3ea-8354-872b-814f104871b7`, 171 filas, copia fiel del original). Protocolo completo: [`docs/dev/09-seguridad-y-respaldo.md`](docs/dev/09-seguridad-y-respaldo.md).
- **Fuentes auxiliares identificadas** para completar la data faltante: bases **Contable Mayo**, **RRHH JUNIO 2026** y **Tickets - Servicios**. Detalle: [`docs/dev/10-fuentes-auxiliares-notion.md`](docs/dev/10-fuentes-auxiliares-notion.md).
- No hay código aún. Stack propuesto: Python + uv/Ruff/mypy + Polars + Pandera/Pydantic + `Decimal` + pytest (ver [`docs/dev/06-stack-tecnico.md`](docs/dev/06-stack-tecnico.md)).

## Próximo hito

> ⛔ **Fase 1 secuencial (D18):** primero el **Frente A — construir y fortalecer la base de datos** (centralización en Notion) al **100% y verificado**; **recién entonces** el **Frente B — formalizar las reglas del F29**. No en paralelo: la base de datos es la prioridad. Ver [`docs/dev/12-fase1-plan-detallado.md`](docs/dev/12-fase1-plan-detallado.md).

**Frente A (AHORA):** mapear el esquema de las 3 fuentes auxiliares (Contable Mayo, RRHH Junio 2026, Tickets - Servicios), cruzarlas con la sandbox y volcar la **data faltante** hacia `General Customers Data - AuditAI` (dry-run + confirmación por cliente), validar y verificar hasta tener una base **final y robusta**. **Frente B (después):** diseñar el motor de cálculo (MVP) que reproduzca el caso `CLIENTE1` (resultado $3, remanente −$158.117).
