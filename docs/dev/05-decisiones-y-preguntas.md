# 05 · Decisiones de diseño y preguntas abiertas

> Registro de las decisiones que dan forma al proyecto (formato ADR-lite: decisión + motivo) y de las preguntas que aún hay que resolver. Mantener vivo este documento evita rediscutir lo ya decidido y mantiene visible lo pendiente.
>
> **Última actualización:** 30-jun-2026, incorporando la red de seguridad montada y ejecutada (D15), las fuentes auxiliares identificadas (D16), la aclaración sobre datos sensibles (D17, matiz de la regla de oro #2) y la **secuencialidad de la Fase 1 (D18):** Frente A (base de datos) al 100% antes que Frente B (reglas).

## Decisiones de diseño (ADR-lite)

### D1 · Cálculo determinista, separado de la IA — ✅ Confirmada
**Decisión:** el monto del F29 se calcula con funciones matemáticas de programación (100% determinista y data-driven). La IA es una capa aparte que **explica y detecta anomalías**, nunca la que determina el monto.
**Motivo:** en un contexto tributario el número debe ser reproducible, preciso y auditable; un modelo probabilístico no puede ser la fuente del impuesto a pagar.
**Nota del creador:** confirmado — no se deja a un LLM haciendo los cálculos. Son plenamente matemáticos, con funciones de programación, para maximizar precisión y credibilidad: hay que ser 100% data-driven.

### D2 · El SII como contraparte de auditoría, no como verdad absoluta — ✅ Confirmada *(matiz importante)*
**Decisión:** la propuesta del F29 del SII se usa como un **segundo origen** contra el cual conciliar el cálculo propio, **no** como la verdad incuestionable. La fuente primaria es **nuestro** cálculo.
**Motivo:** auditar es comparar dos orígenes independientes; el SII ya provee uno oficial y gratuito (ver [`03-estado-del-arte.md`](03-estado-del-arte.md)).
**Nota del creador:** a veces el SII hace mal los cálculos y no son los correctos; no debemos confiarles la verdad, tenemos que estar seguros por nosotros mismos.

### D3 · Documentación: no duplicar + documentos pequeños y enfocados — ✅ Ampliada
**Decisión:** la versión dev **enlaza** en lugar de copiar; y además se prefiere **crear documentos nuevos y acotados** antes que engordar los archivos existentes.
**Motivo:** fuente única de verdad **y** mantener cada archivo liviano para no saturar la ventana de contexto de los LLMs que lean el repo, conservando la comprensión del proyecto.
**Nota del creador:** mejor crear más documentos aparte para no sobrecargar el contenido ni colapsar la ventana de contexto, y que un LLM siga comprendiendo el proyecto al leer estos archivos; además, mejorar la calidad de la presentación en su versión HTML.
**Acciones derivadas:** ① el detalle del stack se movió a su propio documento → [`06-stack-tecnico.md`](06-stack-tecnico.md). ② La mejora de calidad de `presentacion.html` queda registrada como acción pendiente (ver Preguntas abiertas #4).

### D4 · Separación ingesta → cálculo → salida — ✅ Confirmada
**Decisión:** las tres responsabilidades se mantienen en componentes separados.
**Motivo:** las reglas tributarias cambian con la ley; aislarlas permite actualizarlas sin reescribir ingesta ni salida.
**Nota del creador:** sí.

### D5 · Documentación en español — ✅ Confirmada
**Decisión:** toda la documentación se escribe en español.
**Motivo:** consistencia con el repo y con el dominio (normativa y términos del SII en español).
**Nota del creador:** sí.

## Decisiones derivadas de las preguntas resueltas

### D6 · Multiempresa desde el MVP
**Decisión:** el motor se diseña **multiempresa (multitenant) desde el primer momento**; cada insumo lleva su identificador de empresa y el cálculo se ejecuta por empresa-período.
**Motivo:** evita una reescritura posterior; la planilla `CLIENTE1` ya anticipaba varios clientes. Detalle de cómo se implementa sin infra extra en [`06-stack-tecnico.md`](06-stack-tecnico.md).
**Nota del creador:** "démosle de una como multiempresa".

### D7 · Ingesta inicial: CSV y XLSX exportados del SII
**Decisión:** la entrada prioritaria del sistema son archivos **`.csv` y `.xlsx`** (los que se descargan del SII). Sin integración por API por ahora. **El gatillo (trigger) que descarga ese XLSX es una automatización** descrita en D12 y en [`07-flujo-de-datos.md`](07-flujo-de-datos.md).
**Nota del creador:** son los Excel que se sacan del SII; admitir CSV y XLSX es la prioridad.

### D8 · MVP-first: empezar por lo básico — *ajustada por D11*
**Decisión:** primero un **MVP completo y funcional con lo justo y necesario**; las mejoras (detección avanzada de IA, sugerencias) vienen **después** de que el MVP funcione.
**Motivo:** reducir riesgo y validar la arquitectura cuanto antes con algo que funcione de extremo a extremo.
**Nota del creador:** empezar por lo básico, lo justo y necesario; cuando el MVP esté completo y funcional, recién ahí hacer mejoras. "A la calma, de a poquito."
**⚠️ Ajuste (ver D11):** la **base de datos deja de ser "para después"** y pasa a formar parte del núcleo del MVP. El espíritu incremental se mantiene, pero el alcance del MVP ahora **incluye la centralización de datos** desde el inicio.

### D9 · Remanente: valor del SII como insumo, historial como control
**Decisión:** el remanente de crédito fiscal se **toma del valor que entrega el SII** (que ya viene reajustado por la variación de la **UTM**). En paralelo se mantiene un **historial mensual** que sirve para **validar** ese valor: el histórico reajustado debe ser **razonable y muy similar** al del SII, con un **margen muy pequeño**. Si la diferencia excede ese margen → se marca como **anomalía / fluctuación / dato faltante**.
**Motivo:** combina D2 (no confiar ciegamente en el SII) con un control de consistencia automático. Se implementa con validación de datos (ver [`06-stack-tecnico.md`](06-stack-tecnico.md)).
**Nota del creador:** el SII actualiza el remanente por la variación de la UTM; usamos su valor porque viene actualizado, pero el historial nos sirve para revisar que no haya fluctuaciones, anomalías ni falta de datos — el valor histórico debe variar solo un margen muy pequeño.
**Regla de anomalía (resuelta — antes Pregunta #2):** **no** hay un umbral porcentual fijo. La diferencia entre meses es **normal** porque sigue la variación natural de la UTM; solo se alerta cuando el cambio es **brusco y extraño**, fuera de lo que esa variación explicaría. El historial sirve para establecer ese "comportamiento esperado".

### D10 · Stack: Python + tooling moderno, data-driven y preciso
**Decisión:** Python con prácticas vigentes 2026 (**uv, Ruff, mypy**), DataFrames y validación (**Polars + Pandera/Pydantic**), aritmética monetaria exacta (**`Decimal`**) y **pytest**. Justificación completa, comparativas y fuentes en **[`06-stack-tecnico.md`](06-stack-tecnico.md)**.
**Motivo:** mejores prácticas y precisión exigidas por D1.
**Nota del creador:** sí; deben ser las mejores prácticas posibles y necesarias; investigar el stack más valorado del mercado actual para este tipo de desarrollos. *(Investigación realizada → documento 06.)*

### D11 · 🔁 Centralización de datos en dos etapas (Notion primero)
**Decisión (refinada con el creador):** la centralización se hace en **dos etapas**:
1. **Etapa 1 — Notion como base central (AHORA).** Acumular y centralizar toda la data en **Notion**, concretamente en la página **"General Customers Data"** que el cliente ya usa (o desea usar) como base central. Tarea inmediata: **recuperarla y actualizarla** —hoy está desactualizada, con datos faltantes y "se dejó estar"— y **automatizar la integración** de los datos hacia ella.
2. **Etapa 2 — Base de datos especializada (DESPUÉS).** Una vez que todo esté centralizado en Notion y la integración automatizada, migrar a un almacén más profundo y especializado en datos (**Supabase / PostgreSQL** u otro).
**Motivo:** trabajar donde el cliente **ya guarda, inyecta y extrae** su data (Notion, en distintas hojas) reduce fricción y entrega valor de inmediato; recién con la data centralizada se justifica invertir en una BD especializada. Coherente con D8 (incremental) y con posicionarse como asesoría **data-driven**.
**Notas del creador:**
- *(inicial)* "empecemos altiro con una base de datos… centralizar toda la data posible."
- *(refinamiento)* empezar acumulando la data **solo en Notion**; cuando esté todo centralizado y automatizada la integración en la página **"General Customers Data"**, recién pasar a resguardar los datos en un lugar más profundo y especializado. Es clave **trabajar siempre junto a Notion**, porque ahí el cliente guarda/inyecta/extrae datos en distintas hojas. "General Customers Data" está desactualizada y el cliente pidió **recuperar su importancia** y centralizar todo ahí.
**Recomendaciones del asesor (técnicas):**
- Diseñar el código con una **capa de acceso a datos (abstracción)** para que migrar de Notion → BD especializada en la Etapa 2 **no obligue a reescribir** (coherente con D4).
- Como Notion **no valida esquema**, la capa de **validación (Pandera/Pydantic)** es crítica para atacar justamente el problema de "datos faltantes".
**Conexión con Notion:** ver **D14**. Flujo completo en [`07-flujo-de-datos.md`](07-flujo-de-datos.md).

### D12 · Ingesta automatizada: Notion → SII → descarga del XLSX (el trigger)
**Decisión:** el insumo primario del sistema es el **XLSX del cliente descargado desde el SII** por una **automatización** que: ① lee del **registro de clientes en Notion** la fila del cliente, ② extrae sus credenciales (columnas **RUT** y **contraseña** — Clave Única), ③ inicia sesión en el SII (con o sin Clave Única según sea persona o empresa) y ④ descarga el XLSX. Ese XLSX es el **gatillo** que activa el flujo principal.
**Motivo:** automatizar de punta a punta desde la fuente real de datos del cliente.
**Nota del creador:** describe el algoritmo (Notion → buscar fila del cliente → extraer RUT y contraseña → entrar al SII → descargar XLSX = "el alimento e input", el trigger del flujo).
**Pendiente:** el algoritmo está **incompleto** ("algunos pasos más…"); falta detallar el flujo completo y la estructura exacta de la tabla en Notion (ver Preguntas abiertas #2). **Seguridad:** manejo de credenciales de clientes — ver nota en [`07-flujo-de-datos.md`](07-flujo-de-datos.md).

### D13 · Anomalía del remanente: sin umbral fijo, alerta por cambio brusco
*(Formaliza la regla resuelta en D9.)*
**Decisión:** no se define un porcentaje fijo de tolerancia; el sistema alerta solo cuando la variación del remanente es **brusca y atípica** respecto a lo que la variación natural de la UTM explicaría.
**Nota del creador:** la diferencia normalmente no influye porque depende del cambio natural de la UTM; solo influye cuando es un cambio muy brusco y extraño.

### D14 · Trabajar conectados directamente a Notion
**Decisión:** trabajar **directamente sobre Notion**, por dos vías complementarias:
- **API oficial de Notion** — la que usará el *producto* para leer/escribir programáticamente la base "General Customers Data" (la automatización de integración).
- **Conector / MCP de Notion en claude.ai** — para que el asistente (Claude) tenga **contexto y acceso directo** a la estructura real de Notion mientras construimos.
**Estado:** ✅ **Conectado** (jun-2026). Claude Code vía conector de claude.ai (OAuth); opencode vía servidor local con token (`opencode.json`, `NOTION_TOKEN`). Política de acceso **escalonada**: lectura por defecto, escritura solo con autorización explícita y sobre copia (ver [`../../AGENTS.md`](../../AGENTS.md)). Esquema mapeado en [`08-notion-general-customers-data.md`](08-notion-general-customers-data.md).
**Motivo:** acceder a la estructura real de "General Customers Data" resuelve varias preguntas abiertas (hojas, propiedades, datos faltantes) y permite un trabajo mucho mejor fundado.
**Nota del creador:** es clave tener la API o el MCP de Notion para trabajar directo desde ahí y darle a Claude el mayor contexto, acceso y posibilidades.

### D15 · Protocolo de seguridad y respaldo de datos (red de seguridad, ejecutada 30-jun-2026)
**Decisión:** antes de tocar la base de Notion, **respaldo obligatorio** (export CSV fechado, guardado seguro) y **trabajar siempre sobre una copia sandbox**, nunca sobre la tabla original. Escrituras solo con dry-run + confirmación + log de auditoría. Red de seguridad de **3 capas** (sandbox + backup externo + recuperación nativa). Protocolo completo en [`09-seguridad-y-respaldo.md`](09-seguridad-y-respaldo.md).
**Motivo:** los datos del cliente son sagrados; el historial/papelera de Notion no son backup y no protegen cambios de esquema ni masivos.
**Nota del creador:** "es muy importante generar un backup de seguridad y no trabajar en la tabla original".
**Estado:** ✅ **Ejecutada el 30-jun-2026.** Plan Notion **Business** (historial 90 días, papelera 30 días) · snapshot CSV base en `backups/general-customers-data/2026-06-30_all.csv` (171 registros, vista "All") · sandbox `General Customers Data - AuditAI` (ID `16f12147-b3ea-8354-872b-814f104871b7`, 171 filas, copia fiel — incluye credenciales reales).

### D16 · Completar la data faltante desde fuentes auxiliares de Notion
**Decisión:** para alimentar, completar y agregar la **data faltante** en "General Customers Data" (sandbox), se recurre a **otras páginas/bases del mismo workspace** que **sí se han utilizado últimamente** y donde vive esa información. Las identificadas son tres (todas activas, `last_edited` = 30-jun-2026):
1. **Contable Mayo** (`37212147-...`, data source `fdb12147-...`) — operación contable del período; candidata a aportar `RUT`, `CLAVE SII`, `Adviser Accounting`, fechas, contacto/facturación.
2. **RRHH JUNIO 2026** (`38712147-...`, data source `9c512147-...`) — operación remuneraciones/RR.HH.; candidata a aportar `Adviser RR.HH`, `email`, `Whatsapp`, referencias de personas (RUT RL).
3. **Tickets - Servicios** (`16912147-...`, data source `9d312147-...`) — dashboard transversal de servicios contables; útil para los 20 sin `CLAVE SII` y 10 sin `RUT`.
**Motivo:** la base central "se dejó estar" (20 sin `CLAVE SII`, 10 sin `RUT`, ~100 sin `email`); la operación siguió en otras hojas, ahí está la data. Más eficiente que reconstruirla desde cero.
**Política de volcado:** las 3 fuentes son **solo lectura**; el destino es siempre la **sandbox**, nunca el original. Ningún campo se sobreescribe si ya está poblado (salvo decisión caso a caso del usuario). Dry-run del diff → confirmación del usuario → escritura por clave estable (`userDefined:ID` o `RUT`). Llave de cruce: primero `RUT`, luego nombre (`w`) normalizado.
**Detalle completo:** [`10-fuentes-auxiliares-notion.md`](10-fuentes-auxiliares-notion.md).

### D17 · Datos sensibles: insumo legítimo, no se redactan en la base
*(Aclaración/matiz de la regla de oro #2, formalizada tras discusión con el creador.)*
**Decisión:** las columnas `CLAVE SII` y `Previred` (credenciales) y `RUT`/`RUT RL`/`email`/`Whatsapp` (PII) son **insumo legítimo de la automatización SII** (D12): **no** se redactan, **no** se sustituyen por placeholders y **no** se eliminan de la base. Lo único que se evita es **exponerlas en outputs del agente** (respuestas, logs, ejemplos). Snapshot/sandbox mantienen los valores reales.
**Motivo:** redactar caprichosamente rompería la automatización D12 (login al SII), que es el corazón del flujo. La protección se enfoca en **no imprimir**, no en **no almacenar**.
**Implicación operativa:** cuando el repo tenga `git`, `backups/` (con valores reales) va a `.gitignore`; **nunca** se commitean snapshots con credenciales. Pero working local y Notion sí conservan los valores.

### D18 · Fase 1 secuencial: Frente A (base de datos) al 100% antes que Frente B (reglas) — ✅ Confirmada
**Decisión:** los dos frentes de la Fase 1 **no se trabajan en paralelo**. Primero se dedica el **100% del esfuerzo al Frente A — centralizar y fortalecer la base de datos** ("General Customers Data") hasta que esté **verdaderamente terminada, robusta y verificada**. **Recién entonces** se inicia el **Frente B — formalización de las reglas del F29**.
**Motivo:** la base de datos central es **la prioridad** y el activo que sostiene todo lo demás (asesoría data-driven). Trabajar ambos frentes en paralelo arriesga hacer las cosas a medias y dividir el potencial que debe ir, completo, a la base.
**Nota del creador:** "no quiero hacer las cosas a medias ni dividir el potencial; primero el Frente 1 al 100%, y cuando la base de datos esté final y robusta, recién pasamos al Frente 2."
**Criterio de término del Frente A (gate):** base completa (sin huecos en campos clave), sin duplicados, validada (Pandera/Pydantic) y verificada contra las fuentes; data faltante recuperada y trazable (log de auditoría); completitud re-medida. Detalle: [`12-fase1-plan-detallado.md`](12-fase1-plan-detallado.md).
**Implicación operativa:** el catálogo oficial de documentos del SII (Frente B) capturado durante la investigación queda **archivado como adelanto**, pero el trabajo activo del Frente B **no avanza** hasta cerrar el gate del Frente A.

## Preguntas abiertas (lo que aún falta definir)

1. ~~**Estructura real de "General Customers Data" (D11/D14):** ¿qué hojas/propiedades tiene, qué datos faltan, cómo se relacionan?~~ → **resuelto** vía D14 (esquema de 22 columnas mapeado en [`08`](08-notion-general-customers-data.md)). Pendiente el **solape exacto** de "listos para SII" (RUT + CLAVE SII), que quedó pendiente por rate-limit Notion 429.
2. **Algoritmo completo de la automatización (D12):** faltan los "pasos más" intermedios y la estructura de la tabla de credenciales (columnas, persona vs. empresa para el login).
3. **Manejo seguro de credenciales (D12):** ¿cómo se almacenan/usan los RUT y Clave Única de clientes (cifrado, gestor de secretos, permisos)? Ver [`07-flujo-de-datos.md`](07-flujo-de-datos.md).
4. **Tecnología de la BD especializada — Etapa 2 (D11):** ¿**Supabase**, **PostgreSQL** u otra? Se decide cuando la data ya esté centralizada en Notion.
5. **Esquema del Excel del SII (D7):** columnas/encabezados reales del XLSX, para fijar el parser. Hace falta una **muestra real**.
6. **Esquema de las 3 fuentes auxiliares (D16):** pendiente mapear las propiedades de Contable Mayo, RRHH Junio 2026 y Tickets - Servicios (vía `query-data-source` con `page_size=1` por base).
7. **Solape cliente a cliente** entre cada fuente auxiliar y la sandbox: ¿qué porcentaje de los 171 está presente en cada base auxiliar?

> A medida que estas preguntas se respondan, conviértelas en decisiones (D18, D19, …) en este mismo documento.

---

**Anterior:** [`04-glosario.md`](04-glosario.md) · **Siguiente:** [`06-stack-tecnico.md`](06-stack-tecnico.md) · **Volver al** [`README`](README.md)
