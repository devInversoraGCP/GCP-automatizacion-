# 28 · Cambio de mes y rotación manual de las páginas Contable

> **Decisión formal de Carlos Cereceda (dueño de GCP, 13-jul-2026):** cada mes, **el mismo
> duplica manualmente** la página Contable en Notion (menú `•••` → Duplicar) para abrir el
> nuevo mes. **Con esa página duplicada, todo el sistema (botón "Enviar Correo F29", backend,
> correos, write-back del Status) sigue funcionando sin que el equipo AuditAI toque código.**
>
> Este documento registra la decisión, define el **checklist mensual** que ejecuta Carlos al
> duplicar, detalla **qué hace el sistema solo vs. qué requiere Carlos** y deja la
> **matriz de robustez** que explica por qué el cambio de mes es seguro sin re-arquitectura.

---

## §0 · Orden de lectura

1. [`../../AGENTS.md`](../../AGENTS.md) — reglas de oro (obligatorio).
2. [`23-automatizacion-notion-contable-correo.md`](23-automatizacion-notion-contable-correo.md) —
   guía operativa del handler F29 (botón → webhook → correo → write-back).
3. [`24-arquitectura-multi-automatizacion.md`](24-arquitectura-multi-automatizacion.md) —
   arquitectura centralizada de un solo backend con handlers modulares.
4. [`27-robustez-observabilidad-plan.md`](27-robustez-observabilidad-plan.md) — robustez
   general del backend (este doc complementa con el caso concreto de **rotación de mes**).
5. Este documento.

---

## §1 · Decisión formal (D-new · 13-jul-2026)

| Campo | Valor |
|---|---|
| **Quién decide** | Carlos Cereceda (dueño de GCP) |
| **Decisión** | Cada mes, Carlos **duplica manualmente** la página Contable del mes anterior desde la UI de Notion (menú `•••` → Duplicar). **No** se automatiza la duplicación. |
| **Alcance** | Páginas **Contable** (motor del correo F29). Las páginas **RRHH** y **Tickets** siguen el mismo patrón cuando roten (ver §8). |
| **Justificación** | La duplicación nativa de Notion (1 clic) copia esquema + filas + opciones de select/status en un solo paso — más confiable que recrear la base propiedad por propiedad vía API. Carlos ya la hace como hábito contable mensual. |
| **Implicación** | El backend **no construye `duplicar_mes.py`** (lo que era la **Fase 2 / §6 del doc 23**). Esa tarea se **cancela** (ver §9). El backend sí queda **robustecido para reconocer el mes nuevo** automáticamente. |

> 📝 **Esto sustituye la "Fase 2 — Duplicación mensual" del doc 23 §6.** La automatización A
> (duplicar) queda cancelada por decisión de negocio; la automatización B (correo) sigue siendo
> el foco. El plan "Opción A + fallback C" del doc 23 §5.2.d para la columna `Month` **se mantiene**.

---

## §2 · Qué cambia y qué NO cambia al rotar el mes

El sistema está diseñado para que el cambio de mes sea **"transparente para el backend"**.
La clave: el webhook del botón envía el **`page_id` de la fila** automáticamente (Notion lo
incluye dentro de `source.page_id` — confirmado en el E2E del 07-jul-2026, ver doc 23 §5.4). El
backend lee la fila **por ID**, no por nombre de base, así que **funciona sobre cualquier
Contable <Mes>** sin configuración.

### ✅ Cosas que NO cambian (agnósticas al mes)

| Componente | Por qué es agnóstico | Dónde |
|---|---|---|
| Endpoint `/enviar-f29` | Recibe `page_id` desde `source.page_id` (Notion lo envía solo); lee la fila por ID, sin importar a qué Contable <Mes> pertenece. | `notion_automation/app.py` |
| `nc.derivar_month_desde_base()` | Lee el título de la base parent ("Contable Julio" → "Julio 2026"); así calcula la fecha límite del F29 aunque `Month` esté vacío. | `notion_automation/notion_client.py` |
| Plantilla del correo | Las variables `{{periodo}}`, `{{monto}}`, etc. se reemplazan con los datos de la fila. | `notion_automation/email_templates/f29_email.html` |
| Write-back del Status | PATCH por `page_id` sobre la misma fila. | `notion_automation/app.py` |
| `EMAIL_FROM`, App Passwords, `WEBHOOK_SECRET`, `asesores_smtp.json` | Config del backend, no toca Notion. | `notion_automation/.env`, `asesores_smtp.json` |
| Fila de prueba `ZZ_TEST AuditAI` | Se copia con el duplicado; el botón sigue funcionando ahí también. | Contable <Mes> |

### ⚠️ Cosas que SÍ cambian / requieren acción por mes

| Componente | Acción | Responsable | Muralla de protección |
|---|---|---|---|
| Data source ID del Contable nuevo | **Anotarlo y agregarlo arriba de `DS_CONTABLES`** en `notion_client.py` (1 línea) — solo si el fallback por RUT se usa (ver §4.b). | Equipo AuditAI | `notion_client.py` + este doc |
| ~~Bulk-set `Month` en la nueva página~~ | **Ya no necesario.** El backend prioriza el título de la base parent (ver §4.a). `bulk_set_month.py` queda obsoleto. | ~~Equipo AuditAI~~ | — |
| Columna `Enviar Correo F29` (button) | **Se duplica con la página** (Notion copia las columnas tipo button). **No hay que recrearla** salvo que el duplicado no la traiga — ver §7 contingencia. | Notion (automático) | doc 23 §5.4 |
| URL del webhook en el botón duplicado | **Se copia con la página** (Notion replica la config del botón). En producción (URL estable en Render), no cambia. Solo cambiaría si el backend mudó de URL entre meses. | Notion (automático) | doc 23 §5.4 |
| `Customers`, `Rut`, `Clave SII`, `Email`, advisers (campos estáticos) | Se copian con la página. **No tocar.** | Notion (automático) | doc 23 §6.1 paso 4 |
| `Status`, `Impuestos`, `Ventas`/`Compras`/`Pre-Imptos`/`PreImp`, status de proceso | **Se copian con los valores del mes anterior** — Notion no los resetea. ⚠️ **Esto es lo único que Carlos/Eskalon AuditAI debe revisar** (ver §3 paso 4) | Equipo AuditAI | §3 paso 4 de este doc |

---

## §3 · Checklist mensual de Carlos (al duplicar la página)

> **Cuándo:** el día que se abre el nuevo mes (típicamente los primeros días del mes siguiente,
> cuando GCP empieza a trabajar el F29 del mes que cierra).
>
> **Quién:** Carlos (o quien él designe en GCP). No requiere al equipo AuditAI salvo en los pasos
> marcados **⚙** (operación del backend).
>
> **Duración estimada:** 5 minutos en Notion + 1 paso opcional de backend.

1. **Duplicar la página en Notion.**
   - Abrir la página Contable del mes anterior (hoy: `Contable Junio`).
   - Menú `•••` (arriba derecha) → **Duplicar**.
   - Renombrar la copia a **`Contable <Mes>`** (ej.: `Contable Julio`). El nombre **debe seguir
     el patrón `Contable <NombreMes>`** (capitalizado en español, sin año) — el backend
     `derivar_month_desde_base()` lo parsea así.
2. **Verificar que copió el esquema completo.**
   - Comprobar que están todas las columnas: `Customers`, `Rut`, `Email`, `Month`,
     `Impuestos`, `Honorarios Pendientes`, `Valor-Info adicional`, `Motivo-Info adicional`,
     `Status`, `Adviser Accounting`, `Enviar Correo F29` (botón), `Adjuntos`, `Mensaje Adjuntos`,
     `Fecha Envío`, etc.
   - Si falta alguna, ver §7 contingencia.
3. **Verificar que el botón "Enviar Correo F29" quedó funcional.**
   - Hacer clic en el botón de la fila `ZZ_TEST AuditAI` (la prueba). Tiene que llegar el correo
     a la casilla de prueba.
4. **Resetear campos del mes (operación contable, no del backend).**
   - Limpiar/reseteear lo que GCP suele resetear: `Status`, `Impuestos`, flags
     `Ventas`/`Compras`/`Pre-Imptos`/`PreImp`, y los status de proceso (`ARec`,
     `Control Solicitudes`, `emision de boletas`, `solicitud/informe /boletas`).
   - Notion NO resetea estos campos al duplicar — GCP lo hace a mano o vía bulk (ver §6 si se
     quiere automatizar).
5. **⚙ (no necesario) Bulk-set `Month` en la nueva página.**
   - ~~Equipo AuditAI corre `bulk_set_month.py` con el `MONTH_OBJETIVO` y `DS` del mes nuevo.~~
   - **Ya no es necesario** desde que el backend prioriza el título de la base parent (ver §4).
   - Solo serviría como **override por fila** si el asesor quiere手动mente forzar un mes distinto
     al del título (caso muy borde). Por defecto, **no correrlo**.
6. **⚙ (solo si el fallback por RUT se usa) Registrar el data source ID nuevo.**
   - Equipo AuditAI anota el data source ID del Contable nuevo y lo agrega arriba de la lista
     `DS_CONTABLES` en `notion_automation/notion_client.py` (1 línea) — ver §4.
   - Solo es **estrictamente necesario** si se quita Contable Junio de la vista. Como la lista
     es "más seguro arriba", el backend busca en Julio primero, después en Junio (si Julio no
     se ha creado, cae a Junio y sigue funcionando).
   - **NOTA:** el `data_source_id` solo se usa en el **fallback por RUT** (edge case donde el
     webhook llega sin `page_id`). El flujo principal no lo necesita.
7. **Prueba E2E (recomendada la primera vez del mes nuevo).**
   - Clic real en el botón de una fila de prueba (o de `ZZ_TEST AuditAI`) → verificar correo
     recibido con el **mes del título de la base** ("Julio 2026") y `Status = "1) Enviado y Pendiente"`.

---

## §4 · Robustez del backend para el cambio de mes

> **Estado antes de este doc (13-jul-2026):**
> - `notion_client.py` tenía **una sola constante `DS_CONTABLE_JUNIO`** y `find_page_by_rut()` buscaba solo en Junio. → **corregido** (lista `DS_CONTABLES`).
> - `app.py:_procesar_page` leía **primero** `Month` de la fila y solo caía al título de la base parent si `Month` estaba vacío. Yield que **al duplicar la página Contable, las filas conservan `Month` del mes anterior** ("Junio 2026") porque Notion no resetea la propiedad al duplicar. Resultado: el correo salía con "Junio" aunque la base se llamara "Contable Julio". → **corregido** (el título pasó a ser fuente principal).

### §4.a · Título de la base parent como FUENTE PRINCIPAL del mes

**Cambio:** el mes del correo se determina **primero** leyendo el título de la base parent de la
fila (`"Contable Julio"` → `"Julio 2026"`). El `Month` de la fila queda solo como fallback si el
título no se puede parsear (base sin el patrón `"Contable <Mes>"`).

```python
# notion_automation/app.py · _procesar_page
# El título de la base parent es la fuente principal del mes.
mes_fila = mes                                        # leído de la propiedad Month
mes = nc.derivar_month_desde_base(page)               # prioridad: título de la base parent
mes_derivado = bool(mes)
if not mes:
    mes = mes_fila                                    # fallback: Month de la fila
if mes_derivado and mes_fila and mes_fila != mes:
    log.info("discrepancia mes (prevalece el titulo de la base) · page_id=%s", page_id)
```

**Por qué priorizar el título sobre `Month` de la fila (y no solo como fallback):**

1. **Caso real de cambio de mes:** Carlos duplica `Contable Junio` → renombra a
   `Contable Julio`. Las filas conservan `Month = "Junio 2026"` (Notion no las resetea).
   Antes, el correo salía con "Junio". Ahora sale con **"Julio 2026"** correctamente.
2. **Agnóstico a cualquier mes:** funciona para agosto, septiembre, enero (con la corrección
   diciembre/enero ya en `derivar_month_desde_base`).
3. **Sin scripts manuales:** Carlos no necesita correr `bulk_set_month.py` por fila ni por
   página. Solo duplica + renombra.
4. **El asesor no pierde override:** si el asesor quiere que una fila específica diga un mes
   distinto, basta con que la base se llame "Contable <otro>" — o, si quiere override por fila,
   necesita otra columna (no implementada; **YAGNI** hoy).

> **`bulk_set_month.py` queda obsoleto.** Se conserva en el repo por si GCP lo quiere usar como
> override manual en algún caso borde; **no se corre por defecto**.

### §4.b · Fallback por RUT (lista `DS_CONTABLES`)

Se reemplaza la constante única `DS_CONTABLE_JUNIO` por una **lista ordenada**
`DS_CONTABLES` (más reciente primero). El fallback por RUT itera la lista en orden y devuelve
el primer match. **No es re-arquitectura: 1 constante → lista; 1 query → bucle.**

```python
# notion_automation/notion_client.py
# Contables conocidos, MAS RECIENTE PRIMERO. Si se agrega un mes nuevo, ponerlo arriba.
DS_CONTABLES: list[tuple[str, str]] = [
    # ("Contable Julio",  "<nuevo_data_source_id>"),   # descomentar cuando exista
    ("Contable Junio", "09b12147-b3ea-8337-a218-87538eab23fc"),
]
# Alias legacy: DS_CONTABLE_JUNIO = DS_CONTABLES[0][1]  (para no romper imports viejos)
```

```python
def find_page_by_rut(rut: str) -> str | None:
    """Busca el page_id por RUT en los Contables conocidos (orden: mas reciente
    primero). Devuelve None si no hay match en ninguno. No loguea el RUT (PII).
    Asume RUT unico por cliente (un cliente NO aparece en dos Contables a la vez)."""
    for _nombre, ds_id in DS_CONTABLES:
        body = {"filter": {"property": "Rut",
                           "rich_text": {"equals": rut}},
                "page_size": 5}
        results = query_data_source(ds_id, body)
        if results:
            return results[0]["id"]
    return None
```

**Por qué esto es suficiente y robusto:**

- El flujo **principal** (caso normal) usa `source.page_id` que Notion envía automáticamente; el
  fallback por RUT solo se activa en edge cases (Notion cambia el formato del payload, o el
  botón se configura distinto). Incluso si el fallback nunca se activara, el sistema funcionaría.
- Si Carlos duplica Julio y agrega Julio arriba de la lista → el fallback busca en Julio
  primero, después en Junio → ambos meses funcionan. **No hay que borrar Junio**.
- Si el equipo AuditAI se olvida de agregar Julio a la lista → el flujo principal sigue
  funcionando (usa `page_id`); solo el edge case del fallback por RUT devolvería 404.
- **Idempotencia y observabilidad ya están** (doc 27): doble-clic ignorado por `_dedupe`, logs
  sin PII, alertas globales en caso de excepción.

### §4.c · Matriz actualizada

| Cambio | Dónde | Efecto |
|---|---|---|
| **Título base parent = fuente principal del mes** | `app.py:_procesar_page` | La duplicación + rename de Carlos es **suficiente**; sin scripts manuales |
| `DS_CONTABLE_JUNIO` → `DS_CONTABLES` (lista) | `notion_client.py` | Fallback por RUT reconoce múltiples meses |
| `bulk_set_month.py` queda obsoleto | (conservado en repo) | Ya no se corre por defecto |
| Alias `DS_CONTABLE_JUNIO` | `notion_client.py` | Mantiene compatibilidad con imports viejos |

**Alternativa descartada (auto-detección dinámica):** buscar Contables via `notion-search`
post-filter por `"Contable "`. No se implementa porque: (a) búsqueda full-text es lenta vs. una
lista de 1-12 IDs; (b) puede traer basura (`Contable Febrero (1)` que son duplicados junk);
(c) MVP-first — la lista es simple, mantenible y explícita. La auto-detección es **YAGNI** hoy.

**Esquema del cambio de mes (cómo fluyen los datos):**

```text
Mes N (Contable Junio)               Mes N+1 (Contable Julio)
┌──────────────────────────┐        ┌──────────────────────────┐
│ Fila del cliente X       │        │ Fila del cliente X       │
│ page_id = A              │        │ page_id = B (nuevo)      │
│ Rut = 12.345.678-9       │──┐     │ Rut = 12.345.678-9       │
│ Month = "Junio 2026"     │  │duplicar│ Month = "Julio 2026"│
│ Impuestos = 12345        │  └─→  │ Impuestos = vacío (reset)│
│ [Botón "Enviar Correo"]  │        │ [Botón "Enviar Correo"]  │
└──────────────────────────┘        └──────────────────────────┘
            │                                   │ click
            │ (ya terminado)                    ▼
            │                       webhook {source.page_id=B}
            │                                   │
            │                                   ▼
            │                       app.py: leer fila por B
            │                                   │ _procesar_page(B)
            │                                   ▼
            │                       correo al cliente (Mes=Julio 2026)
            │                                   │
            │                                   ▼
            │                       Status = "1) Enviado y Pendiente"
            ▼
            │ (la página vieja NO se borra — queda historica)
```

El webhook siempre lleva el `page_id` **de la fila donde se apretó el botón**, así que el
backend ni siquiera necesita saber "qué mes" es hasta leer la fila en memoria.

---

## §5 · Cómo agregar un nuevo mes al backend (1 línea, 30 segundos)

Cuando Carlos cree `Contable Julio` (por ejemplo), el equipo AuditAI debe hacer **esto solo
la primera vez**:

1. **Anotar el data source ID** de `Contable Julio`. Se obtiene con la herramienta MCP `fetch`
   sobre el database_id de la nueva página, **o** abriendo la base en Notion y mirando la URL
   (`notion.so/<workspace>/<database_id>?v=...` — el ID es el primer UUID largo de la URL).
   También se ve con un one-liner:
   ```bash
   .venv/Scripts/python -c "import notion_client as nc, os; from dotenv import load_dotenv; load_dotenv(); print(nc.get_database_title('<database_id_de_la_nueva_base>'))"
   ```
   Recomendado: dejarlo guardado junto con el data source ID en `backups/contables/registry.csv`
   (ver §6).
2. **Editar `notion_automation/notion_client.py`** y **agregar la entrada arriba** de
   `DS_CONTABLES`:
   ```python
   DS_CONTABLES = [
       ("Contable Julio",  "<nuevo_data_source_id>"),    # ← nuevo
       ("Contable Junio",  "09b12147-b3ea-8337-a218-87538eab23fc"),
   ]
   ```
3. **Commit + (si está en la nube) redeploy.** Listo. El fallback ya reconoce Julio.

> ⚠️ **No borrar meses anteriores de la lista.** Mantenerlos como histórico. Si un cliente
> aprieta el botón en una fila de un mes viejo (recorre histórico), el fallback lo encuentra.
> Solo si algún Contable se elimina definitivamente de Notion, se puede quitar de la lista.

---

## §6 · Registro externo de Contables (recomendado)

Para no depender solo del código fuente, mantener un CSV externo (no se commitea o se commitea
**sin PII**) que liste los Contables y sus IDs:

```text
backups/contables/registry.csv
mes,data_source_id,database_id,creado_por,fecha_creacion,notas
Contable Mayo,fdb12147-...,37212147-...,Carlos,2026-05-01,retirada (verificar)
Contable Junio,09b12147-...,39612147-...,Carlos,2026-06-01,base operativa
Contable Julio,<nuevo>,<db>,Carlos,2026-07-13,nuevo
```

Reglas:

- **Sin PII.** No lleva RUT/email (`mes` y `data_source_id` no son PII — son IDs públicos de Notion).
- **Es un respaldo del repo** (la fuente de verdad sigue siendo `DS_CONTABLES` en `notion_client.py`).
- Si se commitea, no pasa nada (no es PII); si preferís no commitear, agregar
  `backups/contables/registry.csv` a `.gitignore`.

---

## §7 · Contingencias

| Situación | Acción |
|---|---|
| El duplicado no trajo el botón `Enviar Correo F29` | Recrearlo a mano con la config del doc 23 §5.4 (URL del webhook, header `X-AuditAI-Secret`, body con `Rut`+`Email`+`Customers`). Le va a tomar 2 minutos. La columna tipo button **no se puede crear por API**, solo por UI. |
| El duplicado no trajo una columna (_algún tipo de propiedad no se copia nativamente_) | Agregarla a mano en la UI. La API puede crear `number`, `rich_text`, `status`, `date`, `people`, `email`, `select`. **No** puede crear `button` (ver doc 23 §5.2.c). |
| El botón duplicado apunta a una URL del webhook vieja | Si el backend cambió de URL (ej. ngrok reiniciado, o migró de dominio), editar la acción "Send webhook" del botón en la UI de Notion. recordatorio: el backend de producción (Render) debería tener **URL estable**. |
| Llega un webhook de Contable Julio pero el equipo AuditAI olvidó agregarlo a `DS_CONTABLES` | **No rompe el flujo principal**: el backend recibe `source.page_id` y lee la fila por ID. Solo rompería si, además, el `page_id` no viniera y el fallback tuviera que buscar por RUT (edge case). En ese caso, agregar Julio a la lista. |
| Carlos duplica la página pero deja el mismo `Month` ("Junio 2026") en filas de Julio | `bulk_set_month.py` con el `MONTH_OBJETIVO` y `DS` nuevos lo corrige en 1 corrida. Si no se corre, `derivar_month_desde_base()` resuelve el mes desde el título de la base parent ("Contable Julio" → "Julio 2026"). |
| GCP quiere resetear `Status`/`Impuestos`/flags masivamente al duplicar | Es la **única automatización pendiente** — si Mercado lo pide, se construye un script `reset_mes.py` (1 script nuevo, no toca el backend). Hoy se hace a mano (§3 paso 4). Ver §6 below. |
| Una fila de Contable Julio se borra sin querer | Notion Business permite restaurar hasta 30 días (papelera). Listar la papelera del workspace y restaurar. |
| Página contable ROJA (no coincide el count con el mes anterior) | Reportar al equipo, no enviar masivamente. Ver protocolo de respaldo doc 09. |

---

## §8 · Extensión a RRHH y Tickets

Las páginas **RRHH** y **Tickets - Servicios** seguirán el **mismo patrón** cuando roten:

- **RRHH**: cada handler define su `DS_ID` en `handlers/rrhh.py`. Cuando existan múltiples
  páginas `RRHH <Mes>`, aplicar el mismo refactor: reemplazar `DS_ID` único por
  `DS_RRHH_HISTORICO = [...]` y `find_page_by_rut_generico` iterar. Mismo MVP-first.
- **Tickets**: igual, pero Tickets es probablemente **permanente** (no rota por mes — es un
  backlog de servicios). Si GCP decide archivarlo por mes, aplicar el mismo patrón.
- **F29**: este doc 28 ya lo deja listo.

> Por ahora (13-jul-2026) solo Contable rota mensualmente; RRHH tiene una sola página activa y
> Tickets es backlog. Aplicar el refactor del §4 a esas páginas **cuando GCP abra un segundo
  mes** de cada una.

---

## §9 · Tareas canceladas / actualizadas por esta decisión

| Tarea | Estado anterior | Estado tras este doc | Motivo |
|---|---|---|---|
| `duplicar_mes.py` (Fase 2 del doc 23) | pendiente | **❌ CANCELADA** | Carlos duplica manualmente. MVP-first: no se construye el script. |
| Línea N.3 del checklist maestro `11` | pendiente | **Actualizada:** se referencia este doc 28. |
| "Disparo de la Fase A — botón generador del mes nuevo o job agendado" (doc 23 §6.2) | pendiente | **❌ CANCELADA** | Ya no hay script que disparar. |
| Detección de clientes nuevos (paso 5 del doc 23 §6.1) | pendiente | **Pendiente** como operación contable de GCP, **no del backend**. Si GCP la pide automatizada, construir un script ad-hoc (no toca `app.py`). |
| Bulk-set Month por página nueva | pendiente | **Operación opcional del backend** (§3 paso 5), no crítica. |

---

## §10 · Pruebas

### 10.1 · Prueba unitaria: `find_page_by_rut` itera la lista

[`tests/test_cambio_mes.py`](../../notion_automation/tests/test_cambio_mes.py) (6 tests) valida:

- El fallback por RUT busca en `DS_CONTABLES` en orden (más reciente primero).
- Encuentra la fila aunque esté en un Contable más antiguo de la lista.
- Devuelve `None` si no está en ningún Contable.
- Caso borde: lista vacía, alias `DS_CONTABLE_JUNIO` legacy.

### 10.2 · Prueba unitaria: prioridad del título de la base parent

[`tests/test_mes_titulo_prioridad.py`](../../notion_automation/tests/test_mes_titulo_prioridad.py)
(5 tests) valida:

- **Caso de cambio de mes:** `Month` fila = "Junio 2026" pero el título de la base parent dice
  "Julio 2026" → el correo sale con **"Julio 2026"** (lo del título, no el de la fila).
- El `Month` de la fila se usa solo si el título no se puede parsear.
- Sin ningún mes disponible → se rechaza con `ok: false` y el asesor recibe alerta.
- Funciona para cualquier mes ("Agosto 2026", "Septiembre 2026", "Enero 2027") — caso
  específico pedido por el usuario.

### 10.3 · Prueba E2E del cambio de mes (manual)

Cuando Carlos cree el primer Contable nuevo (ej. Julio):

1. **Asegurar `ZZ_TEST AuditAI`** en la página nueva (si se copió con el duplicado, ya está).
2. Completar la fila de prueba: `Email`, `Impuestos`, `Rut = 12345678-9`,
   `Honorarios Pendientes`. **NO hace falta tocar `Month`** — el backend lo deriva del título
   de la base ("Contable Julio" → "Julio 2026").
3. **Apretar el botón** `Enviar Correo F29` de esa fila.
4. Verificar:
   - (a) el backend recibe el POST (log: `page_id=...`),
   - (b) el correo llega con `periodo = "Julio 2026"` y la fecha límite calculada (día 20 del
     mes siguiente → trasladado al día hábil),
   - (c) la fila queda con `Status = "1) Enviado y Pendiente"`.
5. ❌ **Punto de control:** si el correo sigue saliendo con "Junio 2026" (el del `Month` viejo),
   el backend está usando el `Month` de la fila en vez del título. **Eso fue el bug detectado en
   la simulación del 13-jul-2026** — corregido en el mismo día (ver §4.a). Si reaparece,
   revisar `app.py:_procesar_page` — el `derivar_month_desde_base` debe ir primero.
6. Caso borde: si por algún edge case el botón llega sin `page_id`, el fallback por RUT
   buscará en `DS_CONTABLES`. Si Julio aún no está en la lista → 404. Solución: agregar Julio
   a la lista (1 línea, §5).

### 10.4 · Prueba de regresión del mes anterior

Después de agregar Julio a `DS_CONTABLES`, verificar que **Junio sigue funcionando**:

- Tomar la fila `ZZ_TEST AuditAI` de `Contable Junio`.
- Apretar el botón.
- Tiene que llegar el correo con `periodo = "Junio 2026"` (porque el título de la base parent es
  "Contable Junio", que el backend parsea a "Junio 2026").
- La fila de Junio queda `Status = "1) Enviado y Pendiente"`.

Esto confirma que **ambos meses coexisten** sin romperse (gracias a la identificación por
`page_id` y a que el título de cada base define su propio mes).

---

## §11 · Preguntas que se cierran / abren

### Cierran

- ❓ "¿Cómo rota el sistema al mes siguiente?" → **R:** Carlos duplica + renombra la base en
  Notion. El backend lee el título de la base parent y lo usa como mes (ver §4.a). El flujo
  principal usa `page_id` automáticamente. Solo el fallback por RUT puede requerir el ID del mes
  nuevo agregado a `DS_CONTABLES` (1 línea, §5).
- ❓ "¿Conviene construir `duplicar_mes.py`?" → **R:** no. La duplicación nativa de Notion es
  más confiable que recrear la base por API. Cancelado.
- ❓ "¿Qué pasa con la columna `Month`?" → **R:** el título de la base parent es la fuente
  principal del mes. `Month` de la fila queda como fallback si el título no se puede parsear.
  El `bulk_set_month.py` queda obsoleto (no se corre por defecto).
- ❓ "¿Q pasa si Carlos duplica la página y las filas conservan `Month` del mes viejo?" →
  **R:** ese fue el bug detectado en la simulación del 13-jul-2026, ya corregido en §4.a con el
  título de la base como fuente principal del mes.

### Abren

- 🔜 "¿Conviene un `reset_mes.py` para resetear `Status`/`Impuestos`/flags masivamente al
  duplicar?" → **decisión pendiente de GCP.** Es 1 script nuevo, no toca el backend. Si GCP lo
  pide, se construye; si no, queda como operación manual.
- 🔜 "¿Commutamos el历史上的 Contable Mayo/Junio a solo-lectura para evitar emails accidentales
  en meses viejos?" → decisión de GCP (no urgente; los write-back no son destructivos).
- 🔜 "¿Llevamos un `registry.csv` de Contables?" → §6, opcional.

---

## §12 · Referencias

- [`../../AGENTS.md`](../../AGENTS.md) — reglas no negociables (Notion en lectura por defecto,
  PII, etc.).
- [`23-automatizacion-notion-contable-correo.md`](23-automatizacion-notion-contable-correo.md) —
  guía operativa del F29. §5.2.d (Month), §5.4 (botón + payload con `source.page_id`), §6
  (Fase 2 — cancelada por este doc).
- [`24-arquitectura-multi-automatizacion.md`](24-arquitectura-multi-automatizacion.md) —
  arquitectura multi-handler. RRHH y Tickets cuando roten seguirán el patrón de §4 aquí.
- [`27-robustez-observabilidad-plan.md`](27-robustez-observabilidad-plan.md) — observabilidad
  general del backend; este doc complementa con robustez específica para rotación de mes.
- [`11-checklist-maestro.md`](11-checklist-maestro.md) §N.3 — actualizado para referencia este
  doc.

---

**Anterior:** [`27-robustez-observabilidad-plan.md`](27-robustez-observabilidad-plan.md) ·
**Volver al** [`README`](README.md)