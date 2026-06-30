# 11 · Checklist maestro del proyecto (de inicio a fin)

> **Fuente única de verdad del avance.** Índice completo de todo lo que el proyecto requiere, de principio a fin, con cada fase descompuesta en **tareas → subtareas → algoritmos**. Lo ya hecho queda marcado `[x]`; lo pendiente, `[ ]`. Mantener este documento vivo: al cerrar una subtarea, márcala aquí.
>
> **Última actualización:** 30-jun-2026.
> Complementa [`../ROADMAP.md`](../ROADMAP.md) (visión de fases) y [`05-decisiones-y-preguntas.md`](05-decisiones-y-preguntas.md) (decisiones D1–D17). No duplica: aquí está el **detalle ejecutable**.

## Cómo usar este documento (si eres un LLM / agente)

Este archivo es un **índice ejecutable**, no la fuente primaria de cada tema. Para trabajar bien:

1. **Lee primero, en este orden:** [`../../AGENTS.md`](../../AGENTS.md) (reglas no negociables) → [`00-introduccion.md`](00-introduccion.md) → [`01-dominio-F29.md`](01-dominio-F29.md) (dominio + caso `CLIENTE1`) → [`05-decisiones-y-preguntas.md`](05-decisiones-y-preguntas.md) (D1–D17). Luego **este `11`** para saber qué hacer y en qué orden.
2. **Jerarquía de fuentes de verdad** (si algo se contradice, manda la fuente de la derecha para su tema):

   | Tema | Fuente de verdad |
   |---|---|
   | Cálculo del F29 | `PRUEBA1.xlsx` (hoja `CLIENTE1`, con fórmulas) → [`01`](01-dominio-F29.md) / [`../../CONTEXT.md`](../../CONTEXT.md) |
   | Reglas para agentes (seguridad, PII, idioma) | [`../../AGENTS.md`](../../AGENTS.md) |
   | Decisiones de diseño | [`05`](05-decisiones-y-preguntas.md) (D1–D17) |
   | Esquema de Notion / IDs | [`08`](08-notion-general-customers-data.md), [`10`](10-fuentes-auxiliares-notion.md) |
   | Protocolo de respaldo | [`09`](09-seguridad-y-respaldo.md) |
   | Stack técnico | [`06`](06-stack-tecnico.md) |

3. **Mantenimiento:** al cerrar una subtarea, marca `[x]` aquí **y** refleja el cambio en la sección "Checklist" de [`../../presentacion.html`](../../presentacion.html) (clase `ck todo`→`ck done`, contador y ancho de la barra). Ambos deben quedar **sincronizados**.
4. **Sobre el fasaje:** este documento refleja el **reordenamiento posterior al cambio de rumbo del 30-jun-2026** (centralización de data plegada en la Fase 1; BD especializada en la Fase 6). [`../ROADMAP.md`](../ROADMAP.md) conserva la numeración previa; ante diferencia de fasaje, **manda este `11`**.

## Reglas no negociables (resumen operativo)

Resumen de [`../../AGENTS.md`](../../AGENTS.md); el detalle manda allí. **Antes de cualquier acción:**

- 🔒 **Notion = solo lectura por defecto.** Escritura/edición/borrado solo con autorización explícita del usuario, **sobre la sandbox** (nunca el original), con **dry-run + confirmación + log de auditoría** y backup fechado previo (ver [`09`](09-seguridad-y-respaldo.md)).
- 🔒 **Nunca imprimir credenciales ni PII** en respuestas/logs/ejemplos: `CLAVE SII`, `Previred`, `RUT`, `RUT RL`, `email`, `Whatsapp`. Pero **no se redactan ni se borran** de la base: son insumo legítimo del login al SII (D17). Se evita exponerlas, no almacenarlas.
- 🧮 **La IA no calcula montos.** Los números del F29 salen de funciones deterministas y verificables; el LLM solo **explica** y **detecta** anomalías (D1).
- **Idioma:** español · **MVP-first** · **docs granulares** · **el usuario valida** antes de cambios grandes.

## Datos duros / invariantes (para no alucinar)

> Constantes y referencias estables. Verifica contra la fuente citada antes de usarlas en producción.

**Tasas y caso `CLIENTE1` (período ABRIL) — el *golden test*:**

| Magnitud | Valor |
|---|---|
| Tasa IVA | 19% |
| P1 · Débito (ventas) | $462 |
| P2 · Crédito (compras) | −$260.143 |
| P3 · Remanente anterior | −$158.117 |
| P4 · IVA determinado | −$417.798 (negativo ⇒ no paga IVA) |
| Ventas netas (= P1 / 0,19) | $2.432 |
| Tasa PPM (caso) | 0,125% |
| P5 · Otros impuestos | PPM $3 · honorarios 14,5% → $0 · imp. único → $0 |
| P6 · Total a pagar | **$3** |

**Códigos F29 usados** (verificar el resto en la tarea 1.4): `62` PPM neto · `48` ret. imp. único · `151` ret. honorarios (Ley 21.133) · `77` remanente · `538` total débitos · `537` total créditos.

**Notion — IDs estables:**

| Base | database ID | data source |
|---|---|---|
| General Customers Data (original — **NO tocar**) | `1a23f5e4-0223-46a6-9ad5-16ea823b64ba` | `690945e4-220a-48c3-a888-7fe9ae242d55` |
| General Customers Data - AuditAI (**sandbox**) | `16f12147-b3ea-8354-872b-814f104871b7` | `4ff12147-b3ea-82f4-98dd-072067524cdc` |
| Contable Mayo (aux) | `37212147-b3ea-80fa-ab06-cfd9782372a9` | `fdb12147-b3ea-820b-8595-07535e078336` |
| RRHH JUNIO 2026 (aux) | `38712147-b3ea-80f9-9484-e0ad99c94a26` | `9c512147-b3ea-8256-a570-871254c13b3d` |
| Tickets - Servicios (aux) | `16912147-b3ea-82bc-a491-814729bcca4c` | `9d312147-b3ea-83bf-b111-877c7b24db75` |

Parent de ambas GCP: `dd47681b-89fe-4f49-bea3-f8038d571d44`. Plan workspace: **Business** (historial 90 d, papelera 30 d). Snapshot base: `backups/general-customers-data/2026-06-30_all.csv` (171 filas, vista "All").

**Completitud de la base (jun-2026):** 171 clientes · 10 sin `RUT` (~6%) · 20 sin `CLAVE SII` (~12%) · ~100 sin `email` (~58%).

**Esquema (22 columnas)** — tipos en [`08`](08-notion-general-customers-data.md): credenciales/PII (`CLAVE SII`, `Previred`, `RUT`, `RUT RL`, `email`, `Whatsapp`) · identificación (`w` title, `userDefined:ID`, `Nº`, `CRM`, `Rubro`, `Segmentación`, `Ciudad`, `Municipalidad`) · gestión (`Adviser Accounting`, `Adviser RR.HH`, `1ra Factura o Propuesta`, `Respaldo Anual`) · enlaces/otros (`Drive Empresa`, `Propuesta de Servicio`, `Column`, `Texto`).

**Stack (D10 / [`06`](06-stack-tecnico.md)):** Python 3.12+ · uv · Ruff · mypy --strict · Polars · Pandera · Pydantic v2 · `decimal.Decimal` (dinero, **nunca `float`**) · pytest.

## Leyenda

- `[x]` completado y verificado · `[ ]` pendiente · 🟡 = parcial (subtareas mixtas).
- **Estado por fase:** ✅ completa · 🟡 en curso · ⬜ no iniciada.
- 🔒 = toca credenciales/PII → aplica [`09-seguridad-y-respaldo.md`](09-seguridad-y-respaldo.md) y regla de oro #2 de [`../../AGENTS.md`](../../AGENTS.md).
- 🧮 = lógica determinista (D1): nunca la calcula un LLM.

## Resumen de avance

| Fase | Nombre | Estado | Progreso |
|---|---|:--:|:--:|
| 0 | Cimientos y red de seguridad | ✅ | completa |
| 1 | Centralizar la data + formalizar reglas | 🟡 | en foco |
| 2 | Motor de cálculo (MVP) | ⬜ | no iniciada |
| 3 | Ingesta real desde el SII | ⬜ | no iniciada |
| 4 | Auditoría / conciliación | ⬜ | no iniciada |
| 5 | Capa de IA | ⬜ | no iniciada |
| 6 | BD especializada y producto multi-cliente | ⬜ | no iniciada |

---

## Fase 0 — Cimientos y red de seguridad ✅

**Objetivo:** tener un caso real de referencia, entender el dominio y montar la red de seguridad antes de tocar datos. **Criterio de aceptación:** cualquier persona nueva entiende el proyecto leyendo `docs/`; los datos del cliente están respaldados.

### 0.1 · Caso de referencia y dominio
- [x] Caso de ejemplo `CLIENTE1`
  - [x] Planilla con fórmulas reales: [`PRUEBA1.xlsx`](../../PRUEBA1.xlsx)
  - [x] Exportación CSV (solo valores): [`PRUEBA1.csv`](../../PRUEBA1.csv)
  - [x] Formulario oficial de referencia (~140 códigos): [`F29.pdf`](../../F29.pdf)
  - [x] *Golden test* fijado: total **$3**, remanente **−$158.117** (P1 $462 · P2 −$260.143 · P3 −$158.117 · P4 −$417.798)
- [x] Descripción original de la lógica de las 6 partes: [`../../CONTEXT.md`](../../CONTEXT.md)

### 0.2 · Documentación
- [x] Arquitectura objetivo + diagrama de flujo: [`../ARQUITECTURA.md`](../ARQUITECTURA.md)
- [x] Hoja de ruta con criterios de aceptación: [`../ROADMAP.md`](../ROADMAP.md)
- [x] Documentación dev `00`–`10` (introducción, dominio, estado, estado del arte, glosario, decisiones, stack, flujo, Notion, seguridad, fuentes auxiliares)
- [x] Onboarding para agentes IA: [`../../AGENTS.md`](../../AGENTS.md)
- [x] Este checklist maestro (`11`)
- [x] Presentación de cliente (no técnica) con demo interactiva: [`../../presentacion.html`](../../presentacion.html)
  - [x] Secciones de seguridad, avance real y estrategia en 2 etapas
  - [x] Pulido técnico: SEO/OpenGraph, accesibilidad (aria), estilos de impresión/PDF
  - [x] Sección visual del checklist maestro (espejo de este documento, en `presentacion.html`)

### 0.3 · Conexión y mapeo de Notion 🔒
- [x] Conectar Notion a Claude Code (MCP, [`../../.mcp.json`](../../.mcp.json)) y a opencode (token local, [`../../opencode.json`](../../opencode.json))
- [x] Política de acceso escalonado definida (lectura por defecto; escritura con autorización + sobre copia) — D14
- [x] Mapear esquema de `General Customers Data` (22 columnas): [`08-notion-general-customers-data.md`](08-notion-general-customers-data.md)
- [x] Medir completitud: 171 clientes · 10 sin `RUT` · 20 sin `CLAVE SII` · ~100 sin `email`
- [ ] Obtener número exacto de "listos para SII" (`RUT` + `CLAVE SII`) — bloqueado por *rate-limit* Notion 429, reintentar

### 0.4 · Red de seguridad (3 capas) 🔒
- [x] Capa 3 — confirmar plan Notion **Business** (historial 90 d, papelera 30 d)
- [x] Capa 2 — snapshot CSV base fechado: `backups/general-customers-data/2026-06-30_all.csv` (171 registros, vista "All")
- [x] Capa 1 — crear sandbox `General Customers Data - AuditAI` (ID `16f12147-…`, 171 filas, copia fiel)
- [x] Documentar protocolo obligatorio (dry-run, confirmación, log de auditoría): [`09-seguridad-y-respaldo.md`](09-seguridad-y-respaldo.md)
- [x] Identificar 3 fuentes auxiliares de data faltante: [`10-fuentes-auxiliares-notion.md`](10-fuentes-auxiliares-notion.md)

### 0.5 · Control de versiones *(cierre de Fase 0)* ✅
- [x] `git init` del repositorio (rama `main`)
- [x] `.gitignore` que excluye `backups/` y cualquier export con credenciales/PII (D17) + `.gitattributes` (LF)
- [x] Primer commit del estado actual (verificado: `backups/` NO incluido)

---

## Fase 1 — Centralizar la data + formalizar las reglas 🟡  *(EN FOCO)*

**Objetivo:** recuperar/completar la base central en Notion (Etapa 1 de D11) y convertir el conocimiento implícito de las fórmulas en una especificación explícita. **Criterio de aceptación:** la base tiene la data faltante recuperada y un desarrollador puede implementar el cálculo sin abrir el Excel.

> 🔬 **Plan detallado de esta fase** (investigación, mapeo de elementos, algoritmos, catálogo oficial de documentos del SII, límites reales de la API de Notion): **[`12-fase1-plan-detallado.md`](12-fase1-plan-detallado.md)**. Las tareas de abajo son el índice; el `12` tiene el *cómo*.

> ⛔ **Secuencial, NO en paralelo (D18):** primero el **Frente A (centralización, §1.1–1.3)** al 100% y verificado — hasta tener la base de datos **final y robusta** —; **recién entonces** el **Frente B (reglas, §1.4–1.6)**. La base de datos es la prioridad: todo el esfuerzo va ahí primero.

#### Frente A · AHORA — construir y fortalecer la base de datos 🗂️

### 1.1 · Mapear las 3 fuentes auxiliares 🔒
- [ ] `Contable Mayo` — `query-data-source` (`page_size=1`) → listar columnas y tipos
- [ ] `RRHH JUNIO 2026` — idem
- [ ] `Tickets - Servicios` — idem
- [ ] Para cada fuente, identificar qué columna aporta a cada campo faltante (`RUT`, `CLAVE SII`, `email`, `Whatsapp`, `Adviser …`)

### 1.2 · Cruzar fuentes auxiliares ↔ sandbox 🔒
- [ ] Determinar el solape cliente-a-cliente (qué % de los 171 aparece en cada fuente)
- [ ] **Algoritmo de matching** (llave de cruce):

  ```text
  para cada cliente C en sandbox:
      candidatos ← fuente.where(RUT == C.RUT)            # 1º por RUT (exacto)
      si candidatos vacío:
          candidatos ← fuente.where(norm(nombre) == norm(C.w))   # 2º por nombre normalizado
      si candidatos == 1: match
      si candidatos > 1:  marcar AMBIGUO → revisión humana
      si candidatos == 0: marcar SIN_FUENTE
  norm(s) = trim + minúsculas + sin tildes + colapsar espacios + sin sufijos societarios (SPA/LTDA/EIRL)
  ```

### 1.3 · Volcar data faltante hacia la sandbox 🔒  *(nunca al original — D15)*
- [ ] **Algoritmo de volcado (dry-run → confirmación → escritura):**

  ```text
  precondición: backup CSV de hoy existe y está a salvo
  para cada (cliente, campo_faltante) detectado:
      valor ← fuente_auxiliar[cliente][campo]
      si sandbox[cliente][campo] ya tiene valor: SKIP (no sobreescribir, salvo decisión caso a caso)
      registrar en diff: (userDefined:ID|RUT, campo, "" → valor, fuente)
  mostrar diff completo al usuario        # DRY-RUN, sin aplicar
  esperar confirmación explícita
  aplicar escritura apuntando por clave estable (userDefined:ID o RUT, nunca por posición)
  escribir log de auditoría: (id, columna, valor_anterior → valor_nuevo, timestamp, fuente)
  ```
- [ ] Validar con Pandera/Pydantic **antes** de escribir
- [ ] Identificar específicamente los **20 clientes sin `CLAVE SII`** (prioridad para automatización SII)

#### Frente B · EN PAUSA — arranca al cerrar el Frente A (gate D18) 📐
> **Gate:** el Frente A debe estar terminado (fuentes cruzadas · data faltante recuperada · sin duplicados · validación en verde · base verificada y trazable) antes de trabajar §1.4–1.6. Lo marcado `[x]` abajo es **adelanto de investigación**, no trabajo activo del Frente B.

### 1.4 · Diccionario de códigos del F29 🧮
> ⚠️ **No confundir 3 sistemas de códigos** (ver [`12`](12-fase1-plan-detallado.md) §B0): tipo de documento DTE · código de impuesto/recargo (Tabla 7) · casilla del F29. En `CLIENTE1` hay dos "48" distintos: documento tipo 48 (Comprobante de Pago Electrónico) y casilla F29 48 (ret. imp. único).
- [ ] Construir tabla `código → significado → de qué documento se alimenta` (detalle en [`12`](12-fase1-plan-detallado.md) §B2)
  - [x] Confirmados contra SII: **502/503** (facturas emitidas + débito), **519/520** (facturas recibidas + crédito), **538** (total débitos), **537** (total créditos), **89** (IVA determinado), **77** (remanente)
  - [ ] Verificar **62** (PPM), **48** (ret. imp. único), **151** (ret. honorarios) contra normativa
  - [ ] Extender al resto de los ~140 códigos del [`F29.pdf`](../../F29.pdf) (marcar `verificar`)

### 1.5 · Catálogo de tipos de documento 🧮
- [x] Catálogo oficial capturado del SII (Formato IECV §4) → [`12`](12-fase1-plan-detallado.md) §B1
- [ ] Fijar el mapeo cada tipo → parte del F29:
  - [ ] Factura electrónica 33 → P1/P2 (débito/crédito) · Factura de compra 46 → retención
  - [ ] **Comprobante de pago electrónico (doc 48)** → P1 (genera el débito de `CLIENTE1`)
  - [ ] Nota de crédito 61 → rebaja · Nota de débito 56 → aumenta · DIN 914 → P2 (crédito)
  - [ ] Marcar los "solo resumen" (35, 38, 39, 41, 47, 48, …) — entran agregados, no uno a uno

### 1.6 · Especificación de las 6 partes (entrada → fórmula → salida) 🧮
- [ ] Documentar P1–P6 como reglas formales (insumos, fórmula, salida, código F29 asociado)
- [ ] Especificar explícitamente la **regla condicional de P6** (ver Algoritmo A1 abajo)

---

## Fase 2 — Motor de cálculo (MVP) ⬜ 🧮

**Objetivo:** reproducir la planilla en código, determinista y sin intervención manual. **Criterio de aceptación:** el script reproduce el resultado de `CLIENTE1` **exactamente** ($3 / −$158.117).

### 2.1 · Entorno de desarrollo (stack D10 / doc 06)
- [ ] Inicializar proyecto con **uv** + `pyproject.toml` (Python 3.12+)
- [ ] Configurar **Ruff** (lint + formato, incluir reglas `S`/Bandit) y **mypy --strict**
- [ ] Configurar **pytest** (+ pytest-cov)
- [ ] Añadir dependencias: **Polars**, **Pandera**, **Pydantic v2**

### 2.2 · Modelo de datos (multiempresa desde el MVP — D6)
- [ ] Definir modelos Pydantic: `Documento`, `LibroVentas`, `LibroCompras`, `PeriodoEmpresa`
- [ ] Cada insumo lleva `empresa_id` + `periodo` (cálculo por empresa-período)
- [ ] Esquemas Pandera (contrato de datos): columnas obligatorias, tipos, montos ≥ 0, sin nulos

### 2.3 · Aritmética de dinero (precisión — D1)
- [ ] Usar `decimal.Decimal` para toda la aritmética tributaria (**nunca `float`**)
- [ ] Definir regla de redondeo explícita a peso entero (CLP sin centavos)
- [ ] Patrón: DataFrame (Polars) para ingerir/agrupar/contar; `Decimal` para los totales finales

### 2.4 · Núcleo: las 6 partes (ver Algoritmo A1)
- [ ] P1 · Débito fiscal = Σ IVA de documentos emitidos
- [ ] P2 · Crédito fiscal = −Σ IVA de documentos recibidos
- [ ] P3 · Remanente = saldo a favor del período anterior (negativo)
- [ ] P4 · IVA determinado = P1 + P2 + P3
- [ ] P5 · Otros impuestos = PPM + ret. honorarios + ret. imp. único
  - [ ] PPM: `base = ventas_netas = débito / 0,19`; `ppm = base × tasa` (0,125% en el caso)
- [ ] P6 · Total = **si P4 > 0:** P4 + P5; **si P4 ≤ 0:** solo P5
- [ ] Mapear el resultado a los códigos F29 (consume el diccionario de 1.4)

### 2.5 · Golden test
- [ ] Test que carga `CLIENTE1` y verifica P1–P6 == ($462, −$260.143, −$158.117, −$417.798, $3, $3)
- [ ] Tests de borde: P4 exactamente 0; remanente 0; sin documentos; débito > crédito (paga IVA)

### 2.6 · CLI (MVP = librería + CLI, sin web/BD — YAGNI)
- [ ] Comando que recibe libros + remanente y emite F29 + informe
- [ ] Capa de acceso a datos abstracta (para migrar Notion → BD sin reescribir — D11)

---

## Fase 3 — Ingesta real desde el SII ⬜

**Objetivo:** dejar de tipear datos a mano. **Criterio de aceptación:** se carga un RCV/XLSX real y el motor calcula sin edición manual.

### 3.1 · Parser del RCV / XLSX del SII (D7)
- [ ] Conseguir una **muestra real** del XLSX del SII (pendiente — Pregunta abierta #5)
- [ ] Parsear CSV (separador `;`) y XLSX (motor `calamine` de Polars u openpyxl)
- [ ] Normalización: UTF-8 (arreglar `mi�rcoles`, `N�`), formatos de monto y fecha chilenos

### 3.2 · Validaciones de ingesta (Pandera)
- [ ] Detectar documentos duplicados, montos negativos inesperados, tipos desconocidos
- [ ] Rechazar/avisar en la ingesta, no en el resultado final

### 3.3 · Automatización SII: el trigger (D12) 🔒  *(algoritmo incompleto — ver A2)*
- [ ] Completar los pasos intermedios del algoritmo (hoy solo inicio y fin definidos)
- [ ] Definir login persona vs. empresa (con/sin Clave Única)
- [ ] **Manejo seguro de credenciales** (Pregunta abierta #3): cifrado en reposo, gestor de secretos, mínimo privilegio, trazabilidad de acceso; no texto plano

---

## Fase 4 — Auditoría / conciliación ⬜ 🧮

**Objetivo:** el núcleo de "Audit". **Criterio de aceptación:** ante una diferencia inyectada a propósito, el sistema la detecta y la localiza.

- [ ] Cargar la propuesta del F29 del SII como **segundo origen** (D2: contraparte, no verdad absoluta)
- [ ] **Algoritmo de conciliación (ver A3):** comparar cálculo propio vs. propuesta, código por código
- [ ] Informe de discrepancias: código, monto esperado, monto SII, diferencia, documento probable causante
- [ ] **Control de anomalía del remanente (D9/D13 — ver A4):** sin umbral fijo; alerta solo ante cambio brusco/atípico respecto a la variación natural de la UTM
- [ ] Trazabilidad: cada cifra de salida rastreable hasta su documento de origen

---

## Fase 5 — Capa de IA ⬜

**Objetivo:** el "AI" de AuditAI (la IA **explica/detecta**, no calcula montos — D1). **Criterio de aceptación:** el sistema explica una discrepancia de forma que un contador la acepte sin rehacer el cálculo.

- [ ] Explicación en lenguaje natural de cada discrepancia ("la diferencia del código 77 viene de un remanente no arrastrado")
- [ ] Detección de anomalías (facturas atípicas, saltos de patrón mes a mes)
- [ ] Sugerencias de corrección
- [ ] Garantía de aislamiento: la IA nunca determina el monto del impuesto

---

## Fase 6 — BD especializada y producto multi-cliente ⬜

**Objetivo:** pasar de prototipo a herramienta usable. **Criterio de aceptación:** un contador gestiona varios clientes y períodos sin tocar planillas.

### 6.1 · Migración a BD especializada (Etapa 2 de D11)
- [ ] Decidir tecnología (Supabase / PostgreSQL u otra — Pregunta abierta #4)
- [ ] Migrar desde Notion reutilizando la capa de acceso a datos (sin reescribir el motor)
- [ ] Stack de servicio cuando aplique: FastAPI + PostgreSQL + SQLAlchemy 2.0

### 6.2 · Producto
- [ ] Soporte multi-empresa completo (ya previsto en el modelo — D6)
- [ ] Historial mensual y arrastre automático del remanente
- [ ] Interfaz (web o escritorio)
- [ ] Eventual integración con API del SII

---

## Algoritmos de referencia

### A1 · Motor de cálculo — las 6 partes 🧮
```text
entrada: libro_ventas, libro_compras, remanente_anterior, tasa_ppm, tasa_honorarios
# todo en Decimal; redondeo final a peso entero

P1 = Σ iva(doc) para doc en documentos_emitidos        # débito (≥ 0)
P2 = -Σ iva(doc) para doc en documentos_recibidos      # crédito (≤ 0)
P3 = -abs(remanente_anterior)                          # saldo a favor (≤ 0)
P4 = P1 + P2 + P3                                       # IVA determinado

ventas_netas = P1 / 0.19
PPM          = round(ventas_netas * tasa_ppm)
P5 = PPM + ret_honorarios + ret_impuesto_unico

if P4 > 0:
    P6 = P4 + P5            # paga IVA + otros impuestos
else:
    P6 = P5                # NO paga IVA; remanente -P4 se arrastra; otros impuestos se pagan igual
    remanente_siguiente = abs(P4)

salida: {P1..P6, remanente_siguiente, mapeo_codigos_F29}
```
> ⚠️ La rama `else` (P4 ≤ 0) es el error manual más común y la razón de ser de la auditoría.

### A2 · Trigger de ingesta SII (D12) 🔒  *(incompleto — faltan pasos intermedios)*
```text
1. leer fila del cliente en Notion (registro de clientes)
2. extraer credenciales: RUT + contraseña (Clave Única)        # 🔒 nunca imprimir
3. determinar tipo: persona | empresa  → login con/sin Clave Única
4. iniciar sesión en el SII
5. … (pasos intermedios por definir) …
6. descargar XLSX del cliente   = TRIGGER del flujo principal
7. entregar el archivo a la etapa de normalización/validación
```

### A3 · Conciliación contra la propuesta del SII 🧮
```text
para cada código c en F29:
    propio ← calculo_propio[c]
    sii    ← propuesta_sii[c]
    if propio != sii:
        diff ← propio - sii
        causa ← rastrear_documentos(c)        # qué doc(s) alimentan ese código
        reportar(c, esperado=propio, sii=sii, diferencia=diff, causa)
# D2: el cálculo propio es la fuente primaria; el SII es contraparte, no verdad absoluta
```

### A4 · Control de anomalía del remanente (D9/D13) 🧮
```text
remanente_sii      ← valor del SII (ya reajustado por variación UTM)
remanente_esperado ← remanente_historico_reajustado_por_UTM
usar remanente_sii como insumo del cálculo
if |remanente_sii - remanente_esperado| es "brusco/atípico":   # sin umbral % fijo
    marcar ANOMALÍA (revisión humana)
else:
    variación considerada normal (sigue la UTM)
```

---

## Preguntas abiertas que bloquean tareas

Trasladadas de [`05-decisiones-y-preguntas.md`](05-decisiones-y-preguntas.md); cada una bloquea la tarea indicada:

- [ ] #2 — Algoritmo completo del trigger SII (bloquea 3.3 / A2)
- [ ] #3 — Manejo seguro de credenciales de clientes (bloquea 3.3)
- [ ] #4 — Tecnología de la BD especializada (bloquea 6.1)
- [ ] #5 — Esquema real del XLSX del SII: falta muestra (bloquea 3.1)
- [ ] #6 — Esquema de las 3 fuentes auxiliares (bloquea 1.1)
- [ ] #7 — Solape cliente-a-cliente fuente↔sandbox (bloquea 1.2)
- [ ] Número exacto de "listos para SII" (rate-limit Notion 429) (bloquea 0.3)

---

**Anterior:** [`10-fuentes-auxiliares-notion.md`](10-fuentes-auxiliares-notion.md) · **Volver al** [`README`](README.md)
