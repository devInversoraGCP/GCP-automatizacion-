# 24 · Arquitectura multi-automatización (F29 + RRHH + Tickets)

> **Propósito:** un **solo backend** en Render automatiza varias páginas de Notion. Cada página
> tiene su botón, sus columnas, su plantilla y su lógica, pero comparte la infraestructura común
> (API de Notion, envío por SendGrid, credenciales de asesores, BCC).
>
> **Fuente de verdad: el código.** Este doc fue escrito como *plan* el 09-jul-2026 y contenía
> varios supuestos que no calzaron con la implementación real (ver §9). Esta versión describe **lo
> que existe hoy**, verificado contra el código y contra el esquema en vivo de Notion (API,
> 09-jul-2026). Si algo difiere, mandan `app.py`, `handlers/`, `email_sender.py` y `notion_client.py`.

---

## §0 · Estado real hoy (no lo redescubras)

| Automatización | Estado | Endpoint | Dónde vive la lógica |
|---|---|---|---|
| **F29 / Contable** | ✅ operativa | `POST /enviar-f29` | **inline en `app.py`** (`_procesar_page()`), NO en un handler |
| **RRHH JUNIO 2026** | ✅ desplegada | `POST /webhook/rrhh` | `handlers/rrhh.py` (`procesar()`) |
| **Tickets - Servicios** | 📋 no empezada | — | no existe handler ni plantilla |
| (salud) | ✅ | `GET /health` | `app.py` |

**Lo importante de entender:** la arquitectura es **mixta, no uniforme**. El F29 se construyó
primero y quedó embebido en `app.py`. Cuando llegó RRHH se extrajo un **router genérico**
(`_procesar_webhook_generico()`) y el patrón "un handler por página" en `handlers/`, pero **el F29
nunca se migró** a ese patrón (funciona, no se tocó). Así que hoy conviven dos estilos:

- **F29:** endpoint propio `/enviar-f29` con toda su lógica adentro.
- **RRHH (y futuras):** endpoint `/webhook/<pagina>` → router genérico → `handlers/<pagina>.procesar()`.

Cualquier doc o LLM que asuma que existe `handlers/f29.py` está equivocado: **no existe**.

---

## §1 · Principios

| # | Principio | Cómo se cumple hoy |
|---|-----------|--------------------|
| P1 | **Un backend, N automatizaciones** | Un solo servicio Flask en Render rutea por path. Sin microservicios ni repos separados. |
| P2 | **Página nueva = handler nuevo** | Las automatizaciones nuevas van en `handlers/<pagina>.py`. (El F29 es la excepción histórica: inline en `app.py`.) |
| P3 | **Lo común se comparte, sin duplicar** | `notion_client.py` (API Notion), `email_sender.py` (envío + plantillas + BCC), `asesores_smtp.json` (credenciales asesores). |
| P4 | **El handler es autocontenido** | Dentro de `handlers/<pagina>.py` viven: el `DS_ID`, el mapping de columnas, la composición del correo y el write-back. |
| P5 | **Cada página tiene su plantilla** | `email_templates/<pagina>_email.html` + `.txt`. Misma estructura visual (logo GCP, firma, colores), contenido distinto. |

---

## §2 · Estructura del repositorio (real)

```
notion_automation/
├── app.py                    # Router: /enviar-f29 (inline), /webhook/rrhh, /health
├── notion_client.py          # Helpers API Notion (get_page, plain, files, update_props, query…)
├── email_sender.py           # Envío SendGrid/SMTP + render de plantillas + BCC_EXTRA + fechas límite
├── asesores_smtp.json        # Credenciales/estado de asesores (versionado; ver correo-nube)
├── handlers/
│   ├── __init__.py           # vacío (hace de paquete)
│   └── rrhh.py               # Handler de RRHH JUNIO 2026
├── email_templates/
│   ├── f29_email.html / .txt
│   ├── rrhh_email.html / .txt
│   └── README.md, preview-correo-f29.html
├── firmas/                   # PNG de firmas de asesores (inline por CID)
└── (data/ gitignored)
```

> **Aún NO existen** (se crearían al construir Tickets): `handlers/tickets.py`,
> `email_templates/tickets_email.*`. Tampoco existe `handlers/base.py` (el plan lo mencionaba como
> opcional; no se hizo — no hace falta con solo un handler real).

---

## §3 · El router (`app.py`)

Dos caminos, por razones históricas:

### 3.1 · F29 — endpoint propio (inline)

`POST /enviar-f29` → valida `X-AuditAI-Secret` → identifica la fila (page_id de `source`, o `Rut` →
`nc.find_page_by_rut()` sobre Contable Junio) → `_procesar_page(page_id)` hace todo (leer, enviar,
write-back). No pasa por el router genérico.

### 3.2 · RRHH (y futuras) — router genérico

```python
@app.post("/webhook/rrhh")
def webhook_rrhh():
    return _procesar_webhook_generico(rrhh_handler.procesar, "RRHH")
```

`_procesar_webhook_generico(handler, nombre_handler)` centraliza: validación del secreto,
identificación de la fila **en cascada**, y la llamada al handler con el `page_id`.

**Identificación de la fila (cascada real):**
1. `page_id` en el payload (si Notion lo manda).
2. `data.id` / `entity.id` (payloads tipo page-object de automations nuevas).
3. `RUT`.
4. `CLIENTE` — **solo para RRHH** (33/53 filas de RRHH tienen el RUT vacío).

> ⚠️ **El router NO es tan genérico como parece.** Tiene ramas cableadas por `nombre_handler`:
> la búsqueda por RUT/CLIENTE y el `DS_ID` están dentro de un `if nombre_handler == "RRHH"`. El
> `else` cae a `nc.find_page_by_rut()`, que apunta a **Contable Junio**. Por eso agregar una 3ª
> automatización **no es solo "registrar un handler"**: hay que tocar esas ramas (o refactorizarlas
> a un registro por handler). Ver §6.

---

## §4 · Anatomía de un handler (el real: `handlers/rrhh.py`)

No hay un `PROPS = {...}` genérico; cada handler declara sus columnas como constantes y arma su
propio correo. Estructura efectiva:

```python
import notion_client as nc
import email_sender as es

DS_ID = "9c512147-b3ea-8256-a570-871254c13b3d"        # data source de la página
DS_CENTRAL = "4ff12147-b3ea-82f4-98dd-072067524cdc"   # sandbox central (lookup de email por RUT)

# Nombres EXACTOS de columnas en Notion (case-sensitive, con acentos)
CLIENTE, ASISTENTE, MONTO = "CLIENTE", "ASISTENTE", "MONTO IMPOSICIONES|"
EMAIL_CLIENTE, ADJUNTOS, MSG_ADJUNTOS = "Email", "Adjuntos", "Comentario-Adjuntos"
STATUS_COL, STATUS_ENVIADO, FECHA_COL = "Estado Correo", "Listo", "Fecha envío"
ALIAS_ASESOR = {"seba": "Sebastián Robles", "carlos": "Carlos Cereceda", ...}  # select corto → nombre completo

def procesar(page_id: str) -> dict:
    props = nc.get_page(page_id)["properties"]
    # 1. leer columnas (incl. Adjuntos y Comentario-Adjuntos)
    # 2. si no hay Email y hay RUT → lookup en DS_CENTRAL
    # 3. mes = nc.derivar_month_desde_base(page)  ("RRHH JUNIO 2026" → "Junio 2026")
    # 4. ASISTENTE (corto) → ALIAS_ASESOR → asesor de asesores_smtp.json
    # 5. es.enviar(template="rrhh_email", asunto=..., adjuntos=..., msg_adjuntos=...)
    # 6. write-back TOLERANTE: escribe solo las columnas que existen en la fila
    return {"ok": True, "remitente": ...}
```

**Dos patrones que un handler nuevo debe copiar** (nacieron de bugs reales, ver doc 25 §5.2):

- **Verificar el nombre EXACTO de cada columna vía API antes de codearlo.** Notion distingue
  mayúsculas y acentos: `Fecha envío` ≠ `Fecha Envío`, y una columna mal nombrada falla en silencio.
- **Write-back tolerante:** un `PATCH` con una propiedad inexistente **falla completo** (se pierde
  también el `Status`). Por eso el handler arma el `updates` solo con las columnas presentes en la
  fila. Un correo enviado nunca debe quedar sin registrar por culpa de una columna renombrada.

---

## §5 · Las tres automatizaciones (columnas reales verificadas)

### 5.1 · F29 / Contable — ✅ operativa

- **Base:** `Contable Junio` (título `Contable <Mes>`). **Handler:** inline en `app.py`.
- **Plantilla:** `f29_email.html` / `.txt`. **Asunto:** dinámico por mes (`Resumen impuestos <Mes>`).
- **Columnas (nombres reales):** `Customers` (title), `Email` (tipo **email**), `Month` (text),
  `Impuestos` (number), `Honorarios Pendientes` (number), `Valor-Info adicional` (number),
  `Motivo-Info adicional` (text), `Adviser Accounting` (**person**), `Adjuntos` (files),
  `Mensaje Adjuntos` (text), `Rut` (text), `Status` (status → `1) Enviado y Pendiente`).
- **Particularidades:** fecha límite día **20** del mes siguiente; bloque de honorarios con datos de
  transferencia GCP; el asesor sale de `Adviser Accounting` (people).
- **⚠️ Bug latente (detectado 09-jul, ver §9):** el write-back escribe `Status` + `Fecha Envío`,
  pero en Contable Junio la columna date se llama **`Fecha`**, no `Fecha Envío`. El `PATCH` completo
  falla → probablemente el `Status` tampoco se está actualizando tras enviar. **Verificar y decidir**
  (renombrar la columna a `Fecha Envío`, o corregir `P_FECHA_ENVIO` en `app.py`).

### 5.2 · RRHH JUNIO 2026 — ✅ desplegada

- **Base:** `RRHH JUNIO 2026` (data source `9c512147-…`). **Handler:** `handlers/rrhh.py`.
- **Plantilla:** `rrhh_email.html` / `.txt`. **Asunto:** `Imposiciones <Mes Año>- <CLIENTE>`.
- **Columnas (reales):** `RUT` (title), `CLIENTE` (text), `ASISTENTE` (select nombres cortos),
  `MONTO IMPOSICIONES|` (number), `Email` (**text**, no tipo email), `Adjuntos` (files),
  `Comentario-Adjuntos` (text), `Estado Correo` (status → **`Listo`**), `Fecha envío`
  (date, **e minúscula**), `Enviar Correo` (button).
- **Particularidades:** fecha límite día **13** del mes siguiente (hábil, 13:45); aviso de pago con
  link a **Previred**; título de la tarjeta "Imposiciones a pagar"; si falta `Email`, lookup por RUT
  en la base central sandbox; `ALIAS_ASESOR` mapea el select corto al asesor. Detalle completo en el
  [`doc 25`](25-automatizacion-rrhh-correo.md).

### 5.3 · Tickets - Servicios — 📋 planificada (esquema real, diseño por definir)

- **Base:** `Tickets - Servicios` (data source `9d312147-…`). **Handler/plantilla:** aún no existen.
- **Columnas reales (verificadas por API):** `Tarea` (title), `Descripción` (text),
  `Tipo` (multi_select: Constitución, Cuenta Corriente, Patente Comercial, Asesoría Tributaria,
  Declaración de Renta, Oficina Virtual, Fiscalización SII, F29, Declaración de Renta (F22),
  Termino de Giro, Reorganización Empresarial, Recupero de IVA), `Asignado` (**person**),
  `Estado` (status: No empezado, Prioridad, Conservador, Amoblado, por notificar, En progreso,
  Notificación, Presentado, Rechazado, Cobranza, Listo), `Compromiso` (formula — marca atrasados),
  `Fecha prometida` (date), `Número` (number), `Actualizado` (last_edited_time).

> **🚨 Decisión pendiente antes de construir Tickets — no está resuelta en el código ni en Notion:**
> esta base **no tiene columna de email de cliente, ni RUT, ni CLIENTE**. `Asignado` es una **persona
> interna de GCP**, no un cliente. Es decir, el patrón "enviar correo al cliente" **no se traslada
> directamente**. Hay que definir primero:
> 1. **¿A quién y para qué?** ¿Es un correo/notificación al cliente (¿de dónde sale su email?), un
>    aviso interno al `Asignado`, o un recordatorio de tareas vencidas (`Compromiso`)?
> 2. **¿Cómo se identifica la fila?** No hay RUT: sería por `page_id` o por `Tarea` (title).
> 3. **¿Qué dispara el correo?** ¿Botón manual como F29/RRHH, o automático por `Estado`/`Compromiso`?
>
> Hasta responder esto, cualquier detalle de columnas/plantilla para Tickets es especulación. La
> versión anterior de este doc inventó columnas (`Compromiso`, `Fecha prometida`) que sí existen,
> pero también asumió un flujo de correo a cliente que la base **no soporta**.

---

## §6 · Cómo agregar una automatización nueva (pasos reales)

1. **Verificar el esquema real** de la base en Notion (API o MCP): nombres EXACTOS de columnas
   (mayúsculas/acentos), tipos, y opciones de los `status`/`select`. No asumir del diseño.
2. **Crear `handlers/<pagina>.py`** con: `DS_ID`, constantes de columnas, `procesar(page_id)` con
   write-back **tolerante** (copiar el patrón de `handlers/rrhh.py`).
3. **Crear `email_templates/<pagina>_email.html` y `.txt`** con los `{{marcadores}}` que produce
   `email_sender.render()`.
4. **Registrar el endpoint en `app.py`:** `@app.post("/webhook/<pagina>")` →
   `_procesar_webhook_generico(<pagina>_handler.procesar, "<NOMBRE>")`.
5. **Tocar las ramas del router (§3.2):** hoy `_procesar_webhook_generico` decide el `DS_ID` y la
   estrategia de búsqueda con `if nombre_handler == "RRHH"`. Para un handler nuevo hay que **agregar
   su rama** (o —mejor— refactorizar a un registro `{nombre: (ds_id, prop_busqueda)}`). Si se olvida,
   la búsqueda por identificador cae al `else` (Contable Junio) y no encuentra la fila.
6. **En Notion:** columna tipo **Button** → *Send webhook* → URL `.../webhook/<pagina>`, header
   `X-AuditAI-Secret`, y en **Contenido** las propiedades para identificar la fila (page_id no viene
   utilizable; incluir el identificador que use el handler).
7. **Si hay lookup de email por RUT:** replicar `_buscar_email_en_central()` (vive en
   `handlers/rrhh.py`, **no** en `notion_client.py`) apuntando al data source central sandbox.

---

## §7 · IDs de data sources (verificados por API, 09-jul-2026)

| Página | database ID | data source ID |
|--------|-------------|----------------|
| General Customers Data — **ORIGINAL (jamás tocar)** | `1a23f5e4-0223-46a6-9ad5-16ea823b64ba` | `690945e4-220a-48c3-a888-7fe9ae242d55` |
| General Customers Data - AuditAI — **sandbox** (lookup email) | `16f12147-b3ea-8354-872b-814f104871b7` | `4ff12147-b3ea-82f4-98dd-072067524cdc` |
| Contable Junio (F29, operativa) | `39612147-b3ea-80e7-98e6-dbe3de45b76e` | `09b12147-b3ea-8337-a218-87538eab23fc` |
| RRHH JUNIO 2026 | `38712147-b3ea-80f9-9484-e0ad99c94a26` | `9c512147-b3ea-8256-a570-871254c13b3d` |
| Tickets - Servicios | `16912147-b3ea-82bc-a491-814729bcca4c` | `9d312147-b3ea-83bf-b111-877c7b24db75` |

> El código usa el **data source ID** para consultar/filtrar (API `2025-09-03`). Corrección vs. la
> versión anterior: Contable Junio tenía el mismo ID en ambas columnas (era el data source repetido);
> su **database ID real** es `39612147-…`. Los IDs de original y sandbox vienen del doc previo (no
> re-verificados esta sesión); los otros tres se confirmaron en vivo.

---

## §8 · Seguridad (compartida por todos los endpoints)

- **Webhook autenticado:** mismo `X-AuditAI-Secret` (env var `WEBHOOK_SECRET` en Render) en todos.
  Sin secreto válido → `401`.
- **Identificación sin exponer PII:** el backend busca el `page_id` por RUT/CLIENTE o lo toma del
  payload; los valores no se loguean.
- **Log sin PII:** no se registran emails, montos ni RUT (solo presencia booleana y rutas).
- **BCC automático = solo Carlos** (`carloscereceda@inversoragcp.com`, constante `BCC_EXTRA` en
  `email_sender.py`). Aplica a F29 y RRHH. Andrea **se sacó** del BCC el 09-jul (sigue activa como
  remitente, pero ya no recibe copia oculta de los correos de otros asesores).
- **Envío por SendGrid** (API HTTPS) porque Render bloquea el SMTP saliente; SMTP de Gmail quedó como
  fallback local. Domain Authentication de `inversoragcp.com` verificado → todos los `@inversoragcp.com`
  pueden remitir. Ver la nota de memoria del correo en la nube.

---

## §9 · Desviaciones del plan original (por qué este doc no era confiable)

La primera versión (commit `8c9e643`) era un **plan pre-implementación**. Al construir RRHH y
verificar contra la realidad, estos supuestos resultaron falsos:

1. **`handlers/f29.py` / `base.py` / `tickets.py`:** no existen. El F29 quedó inline en `app.py`;
   `base.py` no se hizo.
2. **Endpoint del F29:** es `/enviar-f29`, no `/webhook/f29`. El router `_ruteador("f29")` del plan
   no existe; el real es `_procesar_webhook_generico(handler, nombre)`.
3. **`_buscar_email_en_central()`:** vive en `handlers/rrhh.py`, no en `notion_client.py`.
4. **`nc.plain_select()`:** no existe; se usa `nc.plain()` (maneja select/status/etc.).
5. **Columnas de RRHH:** el plan decía `Email Cliente`, `Estado Correo="Enviado"`, `Fecha Envío`.
   Lo real: `Email`, `Estado Correo="Listo"`, `Fecha envío` (minúscula). Ver doc 25 §5.2.
6. **BCC:** el plan decía "Carlos + Andrea"; hoy es **solo Carlos**.
7. **IDs:** el database ID de Contable Junio estaba mal (repetía el data source).
8. **Tickets:** el plan asumió un flujo de correo a cliente que la base **no soporta** (§5.3).

---

**Anterior:** [`23-automatizacion-notion-contable-correo.md`](23-automatizacion-notion-contable-correo.md) · **Siguiente:** [`25-automatizacion-rrhh-correo.md`](25-automatizacion-rrhh-correo.md) · **Volver al** [`README`](README.md)
