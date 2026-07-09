# 25 · Automatización RRHH JUNIO 2026 — correo de imposiciones

> **Estado: ✅ IMPLEMENTADO Y DESPLEGADO** (09-jul-2026, commit base `3aeb05d`, iterado con
> feedback del usuario hasta `HEAD`). Endpoint `POST /webhook/rrhh` vivo en Render.
> **Pendiente:** prueba E2E real apretando el botón en la fila `RODOTECH` (§7).
>
> **Qué hace:** el botón **"Enviar Correo"** de cada fila de **RRHH JUNIO 2026** envía al cliente
> un correo con el monto de sus imposiciones del mes y el plazo de pago (13 del mes siguiente,
> día hábil, 13:45). Sigue el patrón del F29 (doc [`23`](23-automatizacion-notion-contable-correo.md))
> sobre la arquitectura multi-handler (doc [`24`](24-arquitectura-multi-automatizacion.md)).
>
> **Fuente de verdad: el código.** Este doc describe el sistema y su operación; si algo difiere,
> manda lo que dicen `notion_automation/handlers/rrhh.py`, `app.py`, `email_sender.py` y
> `notion_client.py`. El plan original de este doc se corrigió el 09-jul tras contrastarlo con el
> esquema real de la base (ver §5.2 "Desviaciones del plan original").

---

## §0 · Contexto y decisiones vigentes

**Leer antes de operar:** [`../../AGENTS.md`](../../AGENTS.md) · [`09-seguridad-y-respaldo.md`](09-seguridad-y-respaldo.md) · [`24-arquitectura-multi-automatizacion.md`](24-arquitectura-multi-automatizacion.md).

**Decisiones del usuario (09-jul-2026) — NO re-preguntar:**
- **Destinatario:** el correo va **al cliente** (no al asistente).
- **Asunto:** `Imposiciones {mes} {año}- {CLIENTE}` (ej: `Imposiciones Junio 2026- FUNDACION`).
- **Cuerpo literal** (solo cambian las variables):
  > Por medio de la presente informo el monto a pagar por concepto de imposiciones del mes de {mes} {año}.
  > Plazo hasta {día_semana} {día_nº} de {mes_siguiente} a las 13.45 horas.
  > Total a pagar $ {monto_formateado}.-
- **Fecha límite:** **13 del mes siguiente** al período; si no es hábil (finde/feriado CL), el
  siguiente día hábil. Siempre 13:45.
- **Monto:** columna `MONTO IMPOSICIONES|`. **Cliente:** columna `CLIENTE`.
- **Remitente:** columna `ASISTENTE` (select con nombres cortos) → asesor de `asesores_smtp.json`
  vía el mapa `ALIAS_ASESOR` del handler (§5.1).
- **Andrea González: ACTIVA desde el 09-jul** (decisión del usuario; revierte el "no activar" del
  08-jul). No tiene imagen de firma → el correo sale con la firma de texto de respaldo hasta que
  se agregue su PNG en `firmas/` + `asesores_smtp.json`.
- **Yasna y Samuel ya NO trabajan en GCP.** Siguen como opciones del select `ASISTENTE`, pero no
  tienen credenciales ni alias: una fila asignada a ellos saldría desde el remitente genérico
  `EMAIL_FROM` con firma "Equipo GCP". **Reasignar sus filas a un asesor activo.**

---

## §1 · Reglas inquebrantables

| # | Regla | Detalle |
|---|---|---|
| R1 | **La base original es sagrada** | RRHH JUNIO 2026 es una base real del cliente. Solo se le **agregan** columnas (operación aditiva y reversible), y las crea **el usuario** en la UI de Notion, con backup CSV previo. El backend jamás modifica el esquema. |
| R2 | **Identificación en cascada** | Orden: `page_id` en el payload (si Notion lo manda) → `data.id`/`entity.id` (payload tipo page-object) → **`RUT`** → **`CLIENTE`** (fallback RRHH: 33 de 53 filas tienen el RUT vacío, verificado 09-jul). Todo con `find_page_by_rut_generico()`. |
| R3 | **Credenciales y PII nunca en outputs** | RUT, email y montos no se imprimen ni loguean. El backend lee la fila por API en memoria. |
| R4 | **El webhook se autentica** | Header `X-AuditAI-Secret` = `WEBHOOK_SECRET` (el mismo del F29). Sin secreto válido → 401. |
| R5 | **Si algo no calza, no adivinar** | Propiedad inexistente, payload con otra forma ⇒ volcar evidencia (`_estructura()` en el log) y decidir con el usuario. |
| R6 | **BCC automático a Carlos** | Constante `BCC_EXTRA` en `email_sender.py` (solo Carlos desde el 09-jul — Andrea se sacó del BCC). Aplica a todos los envíos, RRHH incluido. |

---

## §2 · La base RRHH JUNIO 2026 — esquema REAL (verificado por API el 09-jul-2026)

### 2.1 · IDs confirmados

| Recurso | ID |
|---------|----|
| RRHH JUNIO 2026 (data source) | `9c512147-b3ea-8256-a570-871254c13b3d` |
| RRHH JUNIO 2026 (database) | `38712147-b3ea-80f9-9484-e0ad99c94a26` |
| General Customers Data - AuditAI (sandbox, para lookup de email por RUT) | `4ff12147-b3ea-82f4-98dd-072067524cdc` |
| Backend (Render) | `https://auditai-backend-gubv.onrender.com` |

### 2.2 · Columnas (las 18 que existen hoy)

| Columna | Tipo real | Uso en la automatización |
|---------|-----------|--------------------------|
| `RUT` | **title** | Identificador de fila (fallback si no llega page_id) y cruce con base central |
| `CLIENTE` | rich_text | Nombre del cliente → asunto y cuerpo |
| `ASISTENTE` | select: `Andrea`, `Yasna`, `Carlos`, `Seba`, `Matilde`, `Samuel` | Remitente, vía `ALIAS_ASESOR` (§5.1). Yasna/Samuel ya no están en GCP |
| `MONTO IMPOSICIONES\|` | number | Monto a pagar → tarjeta del correo (el `\|` final es parte del nombre) |
| `Email` | **rich_text** (⚠️ NO tipo email, y NO se llama "Email Cliente") | Correo del destinatario; si está vacío se busca en la base central por RUT |
| `Adjuntos` | files & media | PDFs/archivos que se adjuntan al correo (igual que F29) |
| `Comentario-Adjuntos` | rich_text | Nota del asesor sobre los adjuntos → bloque "Archivos adjuntos" en el correo |
| `Estado Correo` | status: `Sin empezar` / `En curso` / **`Listo`** | Write-back tras envío exitoso → **"Listo"** (ver §5.2, no existe opción "Enviado") |
| `Fecha envío` | date (⚠️ **`envío` en minúscula** — "Fecha Envío" con mayúscula NO existe) | Write-back con la fecha/hora del envío |
| `Enviar Correo` | **button** | Dispara el webhook (§6). Nota: se llama así, no "Enviar Correo RRHH" |
| `IMPUESTO ÚNICO` | number | No se usa en este correo |
| `Nº. Trab.` | number | No se usa |
| `CLAVE`, `USUARIO` | rich_text | Credenciales del cliente — no se usan, no exponer |
| `Previred`, `Liquidaciones` | status | Operación interna — no se usan |
| `DTGO` | rich_text | No se usa |
| `Date` | date | Preexistente del cliente — **no confundir con `Fecha envío`**, no se toca |

### 2.3 · Columna `Fecha envío` — creada

Ojo con el nombre exacto: es **`Fecha envío`** (e minúscula en "envío"), no "Fecha Envío" como
decía la primera versión de este doc. Ese desajuste habría repetido el mismo bug silencioso que
tuvo `Estado Correo` al principio (§5.2): el handler no revienta si la columna no calza — solo dejaba
de escribirla, con un `warning` en el log. **Ya corregido en `handlers/rrhh.py` (`FECHA_COL`).**
Write-back tolerante: si en el futuro cambia el nombre de nuevo, la fecha deja de escribirse pero
el correo se sigue enviando igual.

### 2.4 · ⚠️ Higiene de datos (medida por API el 09-jul)

De **53 filas**: **33 sin RUT** (title vacío) y **52 sin `Email`**. Consecuencias:
- Sin RUT ni CLIENTE la fila no se puede identificar → el botón falla (400).
- Sin `Email` (y sin RUT que cruce con la base central) **no hay destinatario**: el backend
  responde `{"ok": false, "motivo": "fila sin Email..."}` — el botón se ve "exitoso" pero no
  envía nada (el motivo queda en los logs de Render).
- **Antes del uso masivo: poblar `Email` (y ojalá RUT) en las filas reales.**

---

## §3 · Arquitectura: cómo se conecta

```
Notion (RRHH JUNIO 2026)
  │  [Botón "Enviar Correo"]
  │  POST https://auditai-backend-gubv.onrender.com/webhook/rrhh
  │  header: X-AuditAI-Secret = <WEBHOOK_SECRET>
  │  body: propiedades del "Contenido" del botón (RUT, CLIENTE, Email)
  ▼
app.py · _procesar_webhook_generico()
  │  valida secreto → identifica la fila en cascada:
  │  page_id → data.id/entity.id → RUT → CLIENTE (fallback RRHH)
  ▼
handlers/rrhh.py · procesar(page_id)
  ├─ 1. nc.get_page(page_id)                 # lee la fila en memoria
  ├─ 2. extrae CLIENTE, MONTO IMPOSICIONES|, ASISTENTE, Email, RUT
  ├─ 3. sin Email → nc.query a base central por RUT (columnas email/Email/e-mail)
  ├─ 4. mes = derivar_month_desde_base(page) # "RRHH JUNIO 2026" → "Junio 2026"
  ├─ 5. ASISTENTE corto → ALIAS_ASESOR → asesor de asesores_smtp.json
  ├─ 6. es.enviar(template="rrhh_email", asunto="Imposiciones {mes}- {CLIENTE}")
  │     ├─ SendGrid API (SENDGRID_API_KEY presente en Render; SMTP solo fallback local)
  │     └─ BCC automático (BCC_EXTRA)
  └─ 7. write-back: Estado Correo="Listo" (+ Fecha Envío si la columna existe)
```

Errores controlados (fila sin Email, asesor `pendiente`, fallo SendGrid) devuelven
`{"ok": false, "motivo": ...}` y quedan en el log de Render **sin PII**.

---

## §4 · El correo

- **Asunto:** `Imposiciones Junio 2026- {CLIENTE}` (dinámico por mes derivado del título de la base).
- **HTML** (`email_templates/rrhh_email.html`): mismo layout visual del F29 — tabla 600px, fondo
  `#f2f4f8`, logo GCP inline (CID), navy `#0B1F3A`. Tarjeta con título **"Imposiciones a pagar"**
  (feedback del usuario tras el primer correo de prueba) y el monto en CLP (`$15.474.109`), bloque
  "**Plazo hasta** lunes 13 de julio de 2026 a las 13.45 horas." seguido de un aviso para pagar en
  **Previred** (con link), bloque opcional "Archivos adjuntos" si `Comentario-Adjuntos` tiene texto,
  firma del asesor (imagen si tiene `firma_png`; si no, texto), pie de confidencialidad.
- **Texto plano** (`email_templates/rrhh_email.txt`): mismo contenido sin HTML.
- **Fecha límite:** `fecha_limite_rrhh()` en `email_sender.py` — día **13 del mes siguiente** al
  período, corrido al siguiente día hábil si cae en finde/feriado (`FERIADOS_CL`), siempre 13:45.
  Junio 2026 → **lunes 13 de julio de 2026** (verificado en smoke test).
- **Adjuntos:** columna `Adjuntos` (files & media) → se descargan y adjuntan al correo igual que
  en F29 (`_descargar_adjuntos()`, genérico, mismo tope de tamaño `MAX_ADJUNTOS_MB`). Columna
  `Comentario-Adjuntos` (rich_text) → nota del asesor, se muestra en el bloque "Archivos adjuntos"
  (mismo componente visual que F29, `_bloque_adjuntos()`). Ambas opcionales: fila sin adjuntos ni
  comentario no muestra el bloque.
- **Previred:** constante `PREVIRED_URL` en `email_sender.py`
  (`https://www.previred.com/wPortal/login/login.jsp`), agregada en `_bloque_fecha_rrhh()`.

---

## §5 · Código implementado (commit `3aeb05d`)

### 5.1 · Mapa de archivos

| Archivo | Qué contiene |
|---------|--------------|
| `notion_automation/handlers/rrhh.py` | `procesar(page_id)`: leer fila (incl. `Adjuntos`/`Comentario-Adjuntos`) → validar → lookup email por RUT en central → enviar → write-back (`Estado Correo` + `Fecha envío`). Constantes de columnas, `ALIAS_ASESOR`, `STATUS_ENVIADO="Listo"` |
| `notion_automation/handlers/__init__.py` | vacío (hace paquete a `handlers/`) |
| `notion_automation/app.py` | `_procesar_webhook_generico()` (secreto → page_id/RUT → handler) + endpoint `POST /webhook/rrhh`. `/enviar-f29` intacto |
| `notion_automation/email_sender.py` | `fecha_limite_rrhh()`, `_bloque_fecha_rrhh()`; `enviar()` y `render()` aceptan `template=` y `asunto=` (default sigue siendo F29) |
| `notion_automation/notion_client.py` | `find_page_by_rut_generico(rut, ds_id, prop_rut)`; `derivar_month_desde_base()` acepta títulos `Contable <Mes>` **y** `RRHH <MES> <AÑO>` |
| `notion_automation/email_templates/rrhh_email.html` / `.txt` | Plantillas del correo de imposiciones |

**`ALIAS_ASESOR`** (el select `ASISTENTE` usa nombres cortos; `asesores_smtp.json` matchea por
nombre completo normalizado):

| ASISTENTE (select) | Asesor | ¿Envía hoy? |
|---|---|---|
| `Seba` | Sebastián Robles | ✅ |
| `Carlos` | Carlos Cereceda | ✅ |
| `Matilde` | Matilde Mateluna | ✅ |
| `Constanza` (si se agrega al select) | Constanza Gaggero | ✅ |
| `Andrea` | Andrea González | ✅ desde 09-jul (firma de texto, sin PNG aún) |
| `Yasna`, `Samuel` | — ya no trabajan en GCP | ⚠️ caería a `EMAIL_FROM` genérico → reasignar la fila |

### 5.2 · Desviaciones del plan original (por qué este doc se corrigió)

El plan inicial de este doc se escribió antes de ver el esquema real y tenía 4 supuestos falsos.
Quedaron así:

1. **Columna de email:** el plan decía `Email Cliente` (tipo email). La real es **`Email`**
   (tipo rich_text). El handler usa `EMAIL_CLIENTE = "Email"`.
2. **Status de write-back:** el plan escribía `"Enviado"`, pero el status `Estado Correo` solo
   tiene `Sin empezar/En curso/Listo` y **la API de Notion no puede crear opciones de status**
   ⇒ se escribe **`"Listo"`**. Si el usuario agrega la opción "Enviado" en la UI, cambiar
   `STATUS_ENVIADO` en `handlers/rrhh.py`.
3. **Write-back tolerante:** el plan mandaba Estado + Fecha en un solo PATCH; con una propiedad
   inexistente **el PATCH entero falla**. Ahora se escriben solo las columnas que existen en la
   fila (así una columna con el nombre desalineado no bloquea el envío del correo, solo omite
   ese campo — como pasó con el punto 5).
4. **Matching de asesor:** el plan pasaba el valor del select directo, pero
   `_buscar_asesor_por_nombre()` compara por **igualdad exacta** de `nombre_norm`
   ("seba" ≠ "sebastian robles") ⇒ ningún asesor matcheaba y todo salía del remitente genérico.
   Se agregó `ALIAS_ASESOR` (§5.1).
5. **Nombre de columna con mayúscula distinta:** el código esperaba `"Fecha Envío"` (E mayúscula)
   pero la columna que se creó en Notion se llama `"Fecha envío"` (e minúscula). Notion es
   case-sensitive en nombres de propiedad, así que no calzaban y la fecha nunca se escribía (sin
   error visible, por el punto 3). Corregido comparando contra el esquema real vía API antes de
   asumir el nombre.

### 5.3 · Verificación hecha (09-jul)

- Smoke test local (sin envíos): plantilla renderiza sin marcadores `{{...}}` sueltos, monto CLP
  OK, `fecha_limite_rrhh("Junio 2026")` → lunes 13-jul-2026, alias "Seba" matchea a Sebastián
  Robles activo.
- Deploy: push → Render redesplegó → `POST /webhook/rrhh` **sin** secreto responde **401**
  (antes del deploy respondía 404). `GET /health` OK.
- Sin PII en logs nuevos (mismas convenciones del F29).

---

## §6 · Botón en Notion (ya configurado por el usuario)

Columna **`Enviar Correo`** (tipo button) en RRHH JUNIO 2026, con paso **Send webhook**:

- **URL:** `https://auditai-backend-gubv.onrender.com/webhook/rrhh`
- **Method:** POST
- **Header:** `X-AuditAI-Secret` = el `WEBHOOK_SECRET` (mismo del F29, está en `.env` local y en Render)
- **Contenido (body): ⚠️ CRÍTICO — agregar las propiedades `RUT`, `CLIENTE` y `Email`.**
  El payload del botón NO trae un `page_id` utilizable (lección F29, doc 23 §5.4), así que el
  backend identifica la fila con lo que venga en el Contenido: RUT y, si está vacío, CLIENTE.
  Un botón sin propiedades en Contenido ⇒ `400` ⇒ "No se puede ejecutar el botón".

Si el botón "no hace nada", revisar esta config **antes** que el backend (URL exacta con
`/webhook/rrhh`, header bien escrito, secreto vigente, Contenido con las 3 propiedades).

---

## §7 · Prueba E2E — ⏳ PENDIENTE de ejecutar

### 7.1 · Preparación

**Decisión del usuario (09-jul): la prueba se hace sobre una fila real, no una `ZZ_TEST`.**
Fila elegida: **`RODOTECH`** (`page_id` `39512147-b3ea-805a-a350-e06b9314261b`), a la que el
usuario le puso su propio correo en `Email` para recibir el envío de prueba. Verificado por API:
`CLIENTE`="RODOTECH", `RUT` vacío (ejercita el fallback por CLIENTE de R2), `Email` presente,
`ASISTENTE`="Seba" (activo), `MONTO IMPOSICIONES|` presente, `Estado Correo`="Sin empezar".
No hace falta backend local ni ngrok: producción es Render (always-on, plan Starter).

### 7.2 · Ejecución y criterios
1. Apretar **Enviar Correo** en la fila `RODOTECH`.
2. Logs de Render (Dashboard → servicio → Logs):
   `request recibida · path=/webhook/rrhh · tiene_secreto=True` →
   `identificador en ruta=...` → `correo RRHH enviado OK · page_id=... remitente=...`.
3. Correo recibido (al correo que el usuario puso en `Email` de esa fila): asunto
   `Imposiciones Junio 2026- RODOTECH`, monto según `MONTO IMPOSICIONES|` de la fila,
   plazo `lunes 13 de julio de 2026 a las 13.45 horas`, logo, firma de Sebastián, BCC a Carlos.
4. En Notion: `Estado Correo` = **"Listo"** (y `Fecha Envío` poblada cuando la columna exista).
5. Casos borde (usar otra fila, no RODOTECH): sin `Email` pero con RUT en la central → envía
   igual (lookup); sin RUT ni Email pero con CLIENTE → `{"ok": false, "motivo": "fila sin Email..."}`
   sin crash; sin RUT, sin CLIENTE ni Email → `400` (no identificable).

### 7.3 · Depuración

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| Logs de Render **ni se mueven** | El endpoint no existe en lo desplegado (404; gunicorn no loguea rutas no matcheadas). Pasó el 09-jul: el código estaba solo en local | `git add/commit/push` → Render redespliega (~2-3 min). Confirmar: `POST /webhook/rrhh` sin secreto debe dar **401**, no 404 |
| `401` con el botón | Header `X-AuditAI-Secret` ausente/typo o secreto distinto al de Render | Revisar config del botón y env var en Render |
| "No se puede ejecutar el botón" en fila **sin RUT y sin CLIENTE** | Nada con qué identificar la fila (400) | Poblar CLIENTE (mínimo) o RUT. Pasó el 09-jul: 33/53 filas sin RUT → se agregó el fallback por CLIENTE |
| `400 no se encontro page_id, Rut ni CLIENTE` | Contenido del botón sin propiedades, o payload cambió de forma | Agregar RUT/CLIENTE/Email al Contenido (§6); ver `estructura payload` en el log |
| `404 no se encontro fila con ese RUT/CLIENTE` | El valor no matchea exacto (espacios, guión) | Corregir el valor en la fila |
| El botón dice éxito pero no llega correo | La fila no tiene `Email` y el RUT no está en la central → el backend responde 200 con `{"ok": false, "motivo": ...}` (solo visible en logs de Render) | Poblar `Email` en la fila. (Mejora futura: aviso al asesor como en F29) |
| `fila sin Email` | Sin `Email` en la fila y RUT no está en la base central | Poblar `Email` a mano |
| `Asesor '...' marcado como pendiente` | `pendiente:true` en `asesores_smtp.json` **o** env var `ASESORES_SMTP_JSON` vieja en Render (tiene prioridad sobre el archivo) | Poner `pendiente:false` + push; si persiste, revisar/borrar la env var en el panel de Render |
| SendGrid 403 | Remitente no autorizado | No debería pasar: Domain Authentication de `inversoragcp.com` está verificado (09-jul). Revisar SendGrid → Sender Authentication |
| Envía pero `Estado Correo`/`Fecha envío` no cambia | Falta la columna, la opción del status, o el nombre no calza exacto (mayúscula/acento) | Ver §2.3 y §5.2 punto 5; el log dice qué columna saltó |

---

## §8 · Checklist de estado

### Fase 0 — Código ✅ (commit base `3aeb05d`, iterado hasta `HEAD`, 09-jul-2026)
- [x] `handlers/__init__.py` + `handlers/rrhh.py`
- [x] `fecha_limite_rrhh()` + params `template`/`asunto` en `email_sender.py`
- [x] Plantillas `rrhh_email.html` / `.txt`
- [x] `_procesar_webhook_generico()` + `POST /webhook/rrhh` en `app.py`
- [x] `find_page_by_rut_generico()` en `notion_client.py`
- [x] `ALIAS_ASESOR` + write-back tolerante (ajustes al esquema real)
- [x] Fallback de identificación por `CLIENTE` cuando falta `RUT`
- [x] Título "Imposiciones a pagar" + aviso de pago en Previred
- [x] BCC reducido a solo Carlos (`BCC_EXTRA`)
- [x] Soporte de `Adjuntos` + `Comentario-Adjuntos` (igual que F29)
- [x] `FECHA_COL` corregido a `"Fecha envío"` (nombre real de la columna)

### Fase 1 — Notion
- [x] Columna `Email` (rich_text) — creada por el usuario
- [x] Columna `Estado Correo` (status) — creada por el usuario
- [x] Columna `Fecha envío` (date) — creada por el usuario (nombre real con e minúscula, §2.3)
- [x] Columna `Adjuntos` (files & media) — creada por el usuario
- [x] Columna `Comentario-Adjuntos` (rich_text) — creada por el usuario
- [x] Botón `Enviar Correo` configurado (URL + header + body)

### Fase 2 — Prueba E2E ⏳
- [ ] Fila `RODOTECH` (Email = correo del usuario) + apretar botón + verificar correo y write-back (§7)
- [ ] Caso borde: sin `Email` con RUT en central
- [ ] Caso borde: sin RUT ni Email → error controlado

### Fase 3 — Integración
- [x] `/enviar-f29` intacto (no se tocó su lógica; mismo deploy sano: `/health` OK)
- [x] Andrea activada (`pendiente:false`, 09-jul) — pendiente su firma PNG
- [x] BCC reducido a solo Carlos (09-jul, se sacó a Andrea de `BCC_EXTRA`)
- [ ] Verificar BCC a Carlos en el E2E
- [ ] Reasignar filas de Yasna/Samuel a asesores activos (ya no trabajan en GCP)
- [ ] Actualizar [`11-checklist-maestro.md`](11-checklist-maestro.md) (N.5) y [`02-estado-del-proyecto.md`](02-estado-del-proyecto.md) al cerrar el E2E

---

## §9 · Contingencias

| Situación | Acción |
|-----------|--------|
| Fila con `ASISTENTE` = Yasna/Samuel (ya no están en GCP) | Reasignar a un asesor activo. Si se envía igual, sale desde `EMAIL_FROM` con firma "Equipo GCP" (Domain Auth lo permite, pero no es lo deseado) |
| `ASISTENTE` vacío | Fallback a `EMAIL_FROM` (ya implementado en `email_sender.py`) |
| Lookup en central no encuentra el email | Error claro `fila sin Email...` → poblar `Email` a mano en la fila |
| Falta plantilla `rrhh_email.*` | `render()` cae a `f29_email.*` (no rompe, pero el contenido sería el del F29 — no debería pasar: están versionadas) |
| Payload del botón cambia de forma | `_estructura()` en el log muestra keys/tipos sin PII → ajustar `_buscar_clave` |
| Nuevo asesor o cambio de nombre en el select | Agregar la entrada a `asesores_smtp.json` **y** el alias a `ALIAS_ASESOR` en `handlers/rrhh.py` + push |

---

**Anterior:** [`24-arquitectura-multi-automatizacion.md`](24-arquitectura-multi-automatizacion.md) · **Volver al** [`README`](README.md)
