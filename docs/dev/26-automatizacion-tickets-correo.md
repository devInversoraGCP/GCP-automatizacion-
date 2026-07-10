# 26 · Automatización Tickets - Servicios — correo al cliente (guía ejecutable para LLM)

> **Misión:** implementar la automatización de la página **Tickets - Servicios** en Notion.
> Cada fila es un **trámite de un cliente** (constitución, recupero de IVA, patente, etc.). El asesor
> aprieta un botón y se le envía al cliente un correo sobre su trámite. Hay **3 tipos de correo**
> (3 plantillas), y el asesor elige cuál mandar según el caso: **Avance**, **Completado**, **Cobranza**.
>
> **Arquitectura:** se inserta en el sistema multi-handler del [`doc 24`](24-arquitectura-multi-automatizacion.md)
> siguiendo el patrón ya probado de RRHH ([`doc 25`](25-automatizacion-rrhh-correo.md)): un handler
> `handlers/tickets.py` + 3 plantillas `tickets_*.html/.txt` + endpoints `POST /webhook/tickets/<tipo>`.
> Se reutiliza sin cambios toda la infraestructura: API de Notion, envío por SendGrid, credenciales
> de asesores, BCC a Carlos.
>
> **Este documento es autosuficiente y verificado.** El esquema de la base y los IDs se confirmaron
> por API en vivo (09-jul-2026). Trae el código completo del handler, las 3 plantillas y la config.
> Si algo difiere al implementar, mandan `app.py`, `handlers/` y `email_sender.py`.

---

## §0 · Decisiones ya tomadas por el usuario (09-jul-2026) — NO re-preguntar

Definidas explícitamente antes de escribir este doc:

- **Destinatario:** el **cliente** del ticket (su nombre está en la columna `Tarea`).
- **Fuente del email:** una **nueva columna `Email`** en la base Tickets, que el asesor llena por fila
  (mismo enfoque que RRHH — es lo más confiable; la base **no tiene RUT** para cruzar con la central).
- **3 correos = 3 plantillas**, el asesor elige cuál según el caso:
  1. **Avance** — informa en qué estado va el trámite.
  2. **Completado** — avisa que el trámite quedó listo.
  3. **Cobranza** — avisa que hay un pago pendiente (con datos de transferencia GCP).
- **Disparador:** **botón manual por fila** (mismo patrón de F29/RRHH). Se implementa como **3 botones**
  (uno por tipo de correo), cada uno apuntando a su endpoint.
- **Remitente/firma:** la persona en la columna `Asignado` (mapea directo a `asesores_smtp.json`).

---

## §1 · Reglas inquebrantables

| # | Regla | Detalle |
|---|-------|---------|
| R1 | **La base original es sagrada** | Tickets - Servicios es una base real con 79 trámites. Solo se **agregan** columnas (aditivo, reversible), y **las crea el usuario** en la UI, con backup CSV previo. El backend nunca modifica el esquema. |
| R2 | **Identificación por `Tarea`** | El payload del botón no trae page_id utilizable (lección F29/RRHH). Se identifica la fila por **`Tarea`** (columna title = nombre del cliente). Hoy las 79 son únicas (verificado). Cascada: page_id → `data.id`/`entity.id` → `Tarea`. |
| R3 | **PII nunca en outputs** | Nombre de cliente, email y descripción no se imprimen ni loguean (solo presencia booleana). El backend lee la fila por API en memoria. |
| R4 | **El webhook se autentica** | Header `X-AuditAI-Secret` = `WEBHOOK_SECRET` (el mismo de F29/RRHH). Sin secreto válido → 401. |
| R5 | **Verificar nombre EXACTO de columna vía API antes de codear** | Notion es case/acento-sensitive: `Fecha Envío` ≠ `Fecha envío`. Este bug ya pegó 3 veces. Antes de fijar una constante de columna, confirmarla contra el esquema en vivo. |
| R6 | **Write-back tolerante** | El PATCH de write-back se arma **solo con las columnas presentes** en la fila. Un correo enviado nunca debe quedar sin registrar por una columna mal nombrada o inexistente. |
| R7 | **BCC automático a Carlos** | Constante `BCC_EXTRA` en `email_sender.py`. Ya aplica a todos los envíos, Tickets incluido. Sin cambios. |

---

## §2 · La base Tickets - Servicios — esquema REAL (verificado por API, 09-jul-2026)

### 2.1 · IDs confirmados

| Recurso | ID |
|---------|----|
| Tickets - Servicios (data source) | `9d312147-b3ea-83bf-b111-877c7b24db75` |
| Tickets - Servicios (database) | `16912147-b3ea-82bc-a491-814729bcca4c` |
| Backend (Render) | `https://auditai-backend-gubv.onrender.com` |

### 2.2 · Columnas existentes (verificadas)

| Columna | Tipo real | Uso en la automatización |
|---------|-----------|--------------------------|
| `Tarea` | **title** | **Nombre del cliente** → saludo, asunto e **identificador de la fila** (R2) |
| `Tipo` | **multi_select** | Servicio(s): Constitución, Cuenta Corriente, Patente Comercial, Asesoría Tributaria, Declaración de Renta, Oficina Virtual, Fiscalización SII, F29, Declaración de Renta (F22), Termino de Giro, Reorganización Empresarial, Recupero de IVA → cuerpo y asunto |
| `Estado` | **status** | Avance: No empezado, Prioridad, Conservador, Amoblado, por notificar, En progreso, Notificación, Presentado, Rechazado, Cobranza, Listo → usado en la plantilla **Avance** |
| `Asignado` | **person** | Miembro de GCP a cargo → **remitente/firma** (mapea a `asesores_smtp.json`) |
| `Descripción` | text | Detalle opcional del trámite → bloque en el cuerpo |
| `Fecha prometida` | date | Compromiso opcional → bloque en la plantilla **Avance** |
| `Compromiso` | formula (read-only) | Marca atrasados. No se escribe; opcionalmente informativo |
| `Número` | number | Casi vacío (2/79). **No** usar como identificador |
| `Actualizado` | last_edited_time (read-only) | No se usa |

> **`Asignado` son exactamente los 4 asesores** (Constanza Gaggero, Matilde Mateluna, Carlos Cereceda,
> Sebastián Robles), todos ya en `asesores_smtp.json` **con nombre completo**. A diferencia de RRHH
> (que usa nombres cortos como "Seba"), aquí `nc.people_names()` devuelve el nombre completo y matchea
> directo — **no hace falta mapa de alias**. 2 filas tienen `Asignado` vacío → caen al remitente
> genérico `EMAIL_FROM` con firma "Equipo GCP".

### 2.3 · Columnas a CREAR en Tickets (las crea el usuario en la UI)

| Columna nueva | Tipo | Nombre EXACTO | Para qué |
|---------------|------|---------------|----------|
| **`Email`** | email (o text) | `Email` | Correo del cliente destinatario. **Requerido** para enviar. |
| **`Estado Correo`** | status | `Estado Correo` | Write-back tras el envío. Crear la opción exacta **`Enviado`**. |
| **`Fecha Envío`** | date | `Fecha Envío` | Write-back con la fecha/hora del envío. |
| **`Enviar Avance`** | button | — | Dispara el correo de avance (§6). |
| **`Enviar Completado`** | button | — | Dispara el correo de completado (§6). |
| **`Enviar Cobranza`** | button | — | Dispara el correo de cobranza (§6). |

> ⚠️ **Respetar los nombres EXACTOS** (R5). Si `Estado Correo` no tiene la opción `Enviado`, o
> `Fecha Envío` se llama distinto, el write-back tolerante simplemente **omite esa columna** (deja
> un `warning` en el log) — el correo igual se envía. Verificar por API tras crearlas.

---

## §3 · Arquitectura: cómo se conecta

```
Notion (Tickets - Servicios)
  │  [3 botones: Enviar Avance / Enviar Completado / Enviar Cobranza]
  │  POST https://auditai-backend-gubv.onrender.com/webhook/tickets/<tipo>
  │        <tipo> ∈ { avance, completado, cobranza }
  │  header: X-AuditAI-Secret = <WEBHOOK_SECRET>
  │  body: propiedades del "Contenido" del botón (Tarea, Email)
  ▼
app.py · @app.post("/webhook/tickets/<tipo>")
  │  valida <tipo> → _procesar_webhook_generico(lambda pid: tickets.procesar(pid, tipo), "TICKETS")
  │  valida secreto → identifica la fila: page_id → data.id/entity.id → Tarea
  ▼
handlers/tickets.py · procesar(page_id, tipo_correo)
  ├─ 1. nc.get_page(page_id)                 # lee la fila en memoria
  ├─ 2. extrae Tarea(cliente), Email, Tipo, Estado, Descripción, Fecha prometida, Asignado
  ├─ 3. valida Email y cliente (si faltan → error controlado, sin crash)
  ├─ 4. Asignado (person) → nombre → asesor de asesores_smtp.json (firma/remitente)
  ├─ 5. arma extra_vars + asunto según tipo_correo (avance/completado/cobranza)
  ├─ 6. es.enviar(template="tickets_<tipo>", asunto=..., extra_vars=...)
  │     ├─ SendGrid (SENDGRID_API_KEY en Render; SMTP solo fallback local)
  │     └─ BCC automático a Carlos (BCC_EXTRA)
  └─ 7. write-back TOLERANTE: Estado Correo="Enviado" + Fecha Envío=now (si existen)
```

Un solo handler y un solo endpoint parametrizado por `<tipo>`; los 3 botones solo difieren en la URL.
Errores controlados (sin Email, asesor `pendiente`, fallo SendGrid) devuelven
`{"ok": false, "motivo": ...}` y quedan en el log de Render **sin PII**.

---

## §4 · Los 3 correos: contenido exacto

Los tres comparten el layout visual de F29/RRHH (tabla 600px, logo GCP inline por CID, navy `#0B1F3A`,
firma del asesor, pie de confidencialidad). Cambian el asunto y el cuerpo.

### 4.1 · Avance (`tickets_avance`)

- **Asunto:** `Estado de su trámite de {Tipo} — GCP`
- **Cuerpo:**
  > Estimado/a **{cliente}**:
  > Le informamos el estado de su trámite de **{Tipo}**.
  > Estado actual: **{Estado}**.
  > _{Descripción, si hay}_
  > _Fecha comprometida: {Fecha prometida}, si hay_

### 4.2 · Completado (`tickets_completado`)

- **Asunto:** `Su trámite de {Tipo} está listo — GCP`
- **Cuerpo:**
  > Estimado/a **{cliente}**:
  > Nos complace informarle que su trámite de **{Tipo}** ha sido **completado** exitosamente.
  > _{Descripción / próximos pasos, si hay}_

### 4.3 · Cobranza (`tickets_cobranza`)

- **Asunto:** `Pago pendiente — trámite de {Tipo} — GCP`
- **Cuerpo:**
  > Estimado/a **{cliente}**:
  > Su trámite de **{Tipo}** se encuentra finalizado y registra un **pago pendiente**.
  > Puede regularizarlo mediante transferencia a:
  > **{datos bancarios GCP}** (constante `BANCO_GCP_HTML` de `email_sender.py`)
  > _{Descripción, si hay}_

**Variables que inyecta el handler** (vía `extra_vars`, ver §5.2): `{{tipo}}`, `{{estado}}`,
`{{bloque_detalle}}` (HTML: descripción + fecha prometida o datos de pago, según el tipo),
`{{linea_detalle}}` (equivalente en texto plano). Las estándar (`{{nombre_cliente}}`, `{{bloque_firma}}`,
`{{contacto_email}}`) las provee `render()` como en F29/RRHH.

---

## §5 · Código a implementar

### 5.1 · `handlers/tickets.py` — handler completo

Crear `notion_automation/handlers/tickets.py`:

```python
"""Handler de los botones "Enviar Avance / Completado / Cobranza" de Tickets - Servicios.
El destinatario es el CLIENTE (columna Tarea = nombre; Email = correo). El remitente es el
asesor de la columna Asignado. Un mismo handler sirve las 3 plantillas segun tipo_correo."""
from __future__ import annotations
import logging
from datetime import datetime, timezone
import notion_client as nc
import email_sender as es

log = logging.getLogger("auditai")

# Data source de Tickets - Servicios
DS_ID = "9d312147-b3ea-83bf-b111-877c7b24db75"

# Columnas (nombres EXACTOS verificados por API)
TAREA = "Tarea"                 # title = nombre del cliente
TIPO = "Tipo"                   # multi_select
ESTADO = "Estado"               # status
DESCRIPCION = "Descripción"     # rich_text
ASIGNADO = "Asignado"           # person -> remitente/firma
EMAIL_CLIENTE = "Email"         # columna nueva (creada por el usuario)
FECHA_PROM = "Fecha prometida"  # date

# Write-back (columnas nuevas)
STATUS_COL = "Estado Correo"
STATUS_ENVIADO = "Enviado"
FECHA_COL = "Fecha Envío"

# tipo_correo -> (plantilla, plantilla de asunto)
CORREOS = {
    "avance":     ("tickets_avance",     "Estado de su trámite de {tipo} — GCP"),
    "completado": ("tickets_completado", "Su trámite de {tipo} está listo — GCP"),
    "cobranza":   ("tickets_cobranza",   "Pago pendiente — trámite de {tipo} — GCP"),
}


def _fmt_fecha(iso: str) -> str:
    """'2026-07-15' o ISO datetime -> '15/07/2026'. '' si no hay o no parsea."""
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except ValueError:
        return iso[:10]


def _bloque_detalle(tipo_correo: str, descripcion: str, fecha_prom: str) -> tuple[str, str]:
    """Compone el bloque variable del cuerpo segun el tipo de correo.
    Devuelve (html, txt). Cada pieza es opcional."""
    piezas_html, piezas_txt = [], []

    if tipo_correo == "cobranza":
        # Datos de transferencia GCP (constantes ya existentes en email_sender)
        piezas_html.append(
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            'style="margin:0 0 18px 0;"><tr><td style="background:#eef4ff;border:1px solid #d3e0f5;'
            'border-left:4px solid #0B1F3A;border-radius:10px;padding:14px 18px;font-size:14px;'
            f'color:#3a4658;line-height:1.6;">{es.BANCO_GCP_HTML}</td></tr></table>'
        )
        piezas_txt.append(es.BANCO_GCP_TXT)

    if tipo_correo == "avance":
        f = _fmt_fecha(fecha_prom)
        if f:
            piezas_html.append(
                f'<p style="margin:0 0 14px 0;font-size:14px;line-height:1.6;color:#3a4658;">'
                f'<b>Fecha comprometida:</b> {f}.</p>'
            )
            piezas_txt.append(f"Fecha comprometida: {f}.")

    if descripcion.strip():
        d = es._escape(descripcion).replace("\n", "<br>")
        piezas_html.append(
            f'<p style="margin:0 0 14px 0;font-size:14px;line-height:1.6;color:#3a4658;">{d}</p>'
        )
        piezas_txt.append(descripcion.strip())

    return "".join(piezas_html), "\n".join(piezas_txt)


def procesar(page_id: str, tipo_correo: str) -> dict:
    """Lee la fila, envia el correo del tipo pedido y escribe el write-back.
    Devuelve {'ok': bool, 'remitente': str, 'motivo': str (si falla)}."""
    cfg = CORREOS.get(tipo_correo)
    if not cfg:
        return {"ok": False, "motivo": f"tipo de correo desconocido: {tipo_correo!r}"}
    plantilla, asunto_tpl = cfg

    page = nc.get_page(page_id)
    props = page["properties"]

    cliente = nc.plain(props.get(TAREA, {}))
    email = nc.plain(props.get(EMAIL_CLIENTE, {}))
    estado = (props.get(ESTADO, {}).get("status") or {}).get("name", "")
    descripcion = nc.plain(props.get(DESCRIPCION, {}))
    fecha_prom = (props.get(FECHA_PROM, {}).get("date") or {}).get("start", "") or ""
    tipos = [o.get("name", "") for o in (props.get(TIPO, {}).get("multi_select") or [])]
    tipo = ", ".join(t for t in tipos if t) or "trámite"
    asignados = nc.people_names(props.get(ASIGNADO, {}))
    asesor = asignados[0] if asignados else ""

    log.info("tickets tipo=%s page_id=%s cliente_present=%s email_present=%s asesor=%r estado=%r",
             tipo_correo, page_id, bool(cliente), bool(email), asesor, estado)

    if not email:
        return {"ok": False, "motivo": "fila sin Email (columna Email vacía)"}
    if not cliente:
        return {"ok": False, "motivo": "fila sin Tarea (nombre de cliente, necesario)"}

    b_html, b_txt = _bloque_detalle(tipo_correo, descripcion, fecha_prom)
    extra_vars = {
        "tipo": tipo,
        "estado": estado or "—",
        "bloque_detalle": b_html,
        "linea_detalle": b_txt,
    }
    asunto = asunto_tpl.format(tipo=tipo)

    try:
        remitente = es.enviar(
            destinatario=email,
            nombre=cliente,
            mes="",            # Tickets no usa periodo/fecha límite
            monto="0",         # ni monto
            nombre_asesor=asesor,
            template=plantilla,
            asunto=asunto,
            extra_vars=extra_vars,
        )
        log.info("correo tickets/%s enviado OK · page_id=%s remitente=%s", tipo_correo, page_id, remitente)
    except ValueError as exc:
        log.error("error envio tickets · page_id=%s · %s", page_id, exc)
        return {"ok": False, "motivo": str(exc)}
    except Exception as exc:
        log.error("error SMTP tickets · page_id=%s · %s", page_id, exc)
        return {"ok": False, "motivo": f"error SMTP: {exc}"}

    # Write-back tolerante: solo columnas presentes en la fila (R6)
    now_iso = datetime.now(timezone.utc).isoformat()
    updates = {}
    if STATUS_COL in props:
        updates[STATUS_COL] = {"status": {"name": STATUS_ENVIADO}}
    else:
        log.warning("columna %r no existe en Tickets; no se escribe status", STATUS_COL)
    if FECHA_COL in props:
        updates[FECHA_COL] = {"date": {"start": now_iso}}
    else:
        log.warning("columna %r no existe en Tickets; no se escribe fecha", FECHA_COL)
    if updates:
        try:
            nc.update_props(page_id, updates)
            log.info("write-back OK (%s) · page_id=%s", ", ".join(updates), page_id)
        except Exception as exc:
            log.warning("no se pudo actualizar status/fecha · page_id=%s · %s", page_id, exc)

    return {"ok": True, "remitente": remitente}
```

### 5.2 · Extensión mínima de `email_sender.py`

Las plantillas de Tickets usan marcadores propios (`{{tipo}}`, `{{estado}}`, `{{bloque_detalle}}`,
`{{linea_detalle}}`) que `render()` hoy no conoce. Se agrega un parámetro genérico `extra_vars` que
se **fusiona** en el dict de variables (gana sobre las estándar). Es un cambio pequeño y retro-compatible.

**a) En `render()`** — agregar el parámetro y fusionarlo antes del reemplazo:

```python
def render(
    nombre: str, periodo: str, monto: str, asesor: str, contacto: str,
    logo_url: str, honorarios: str = "", info_valor: str = "", info_motivo: str = "",
    msg_adjuntos: str = "", firma_html: str = "",
    template: str = "f29_email",
    titulo_override: str = "", mensaje_override: str = "",
    bloque_fecha_override: str = "", linea_fecha_override: str = "",
    extra_vars: dict | None = None,          # 🆕
) -> tuple[str, str]:
    ...
    # (justo antes del bucle `for k, v in vars_.items()`)
    if extra_vars:
        vars_.update({k: (v if isinstance(v, str) else str(v)) for k, v in extra_vars.items()})
    ...
```

**b) En `enviar()`** — aceptar `extra_vars` y pasarlo a `render()` en la rama genérica:

```python
def enviar(
    ...,
    template: str = "f29_email",
    asunto: str | None = None,
    extra_vars: dict | None = None,          # 🆕
) -> str:
    ...
    else:
        html, txt = render(
            nombre, mes, monto, asesor_firma, contacto, logo_url,
            honorarios, info_valor, info_motivo, msg_adjuntos, firma_html,
            template=template,
            extra_vars=extra_vars,           # 🆕
        )
```

> No se toca la rama `if template == "rrhh_email"` ni la lógica de F29: `extra_vars` es opcional y por
> defecto `None`. `BANCO_GCP_HTML`, `BANCO_GCP_TXT` y `_escape` ya existen en `email_sender.py`.

### 5.3 · Endpoints en `app.py`

Agregar (junto al de RRHH):

```python
import handlers.tickets as tickets_handler

_TICKETS_TIPOS = {"avance", "completado", "cobranza"}

@app.post("/webhook/tickets/<tipo>")
def webhook_tickets(tipo):
    """Webhook de los botones de Tickets - Servicios. <tipo> elige la plantilla."""
    if tipo not in _TICKETS_TIPOS:
        abort(404, f"tipo de correo tickets desconocido: {tipo}")
    return _procesar_webhook_generico(
        lambda page_id: tickets_handler.procesar(page_id, tipo), "TICKETS"
    )
```

### 5.4 · Identificación por `Tarea` en el router

En `_procesar_webhook_generico()` (en `app.py`), agregar la rama de TICKETS junto a la de RRHH. Dos
puntos a tocar:

**a)** Tras el fallback de RRHH por CLIENTE, agregar el de TICKETS por `Tarea`:

```python
    prop_busqueda = "RUT"
    if not ident and nombre_handler == "RRHH":
        ident, ruta = _buscar_clave(data, ["CLIENTE", "Cliente", "cliente"])
        prop_busqueda = "CLIENTE"
    if not ident and nombre_handler == "TICKETS":          # 🆕
        ident, ruta = _buscar_clave(data, ["Tarea", "tarea", "Nombre"])
        prop_busqueda = "Tarea"
```

**b)** En la resolución del `page_id`, agregar la rama de TICKETS:

```python
    else:
        if nombre_handler == "RRHH":
            from handlers.rrhh import DS_ID as DS
            page_id = nc.find_page_by_rut_generico(ident, DS, prop_busqueda)
        elif nombre_handler == "TICKETS":                  # 🆕
            from handlers.tickets import DS_ID as DS
            page_id = nc.find_page_by_rut_generico(ident, DS, prop_busqueda)
        else:
            page_id = nc.find_page_by_rut(ident)
```

> `find_page_by_rut_generico(ident, DS, "Tarea")` filtra con `rich_text: {equals: ident}` sobre la
> columna **title** `Tarea` — verificado que Notion acepta el filtro `rich_text` sobre `title`
> (mismo caso que RRHH con `RUT`). **Mejora futura opcional** (doc 24 §6): reemplazar estas ramas
> `if nombre_handler == ...` por un registro `{nombre: (ds_id, prop)}`. No es necesario para el MVP.

### 5.5 · `email_templates/tickets_avance.html`

Crear `notion_automation/email_templates/tickets_avance.html`:

```html
<!-- Correo Tickets · Avance de trámite · AuditAI / GCP -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0;padding:0;background:#f2f4f8;">
  <tr><td align="center" style="padding:24px 12px;">
    <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:600px;max-width:100%;background:#ffffff;border-radius:14px;overflow:hidden;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#16202e;box-shadow:0 6px 18px rgba(11,31,58,.08);">

      <tr><td style="background:#ffffff;padding:18px 28px;border-bottom:3px solid #0B1F3A;">
        <img src="cid:logo-gcp" alt="GCP · Audit Tax and Consulting" height="46" border="0" style="height:46px;width:auto;display:block;border:none;outline:none;">
      </td></tr>

      <tr><td style="padding:30px 28px 8px 28px;">
        <p style="margin:0 0 16px 0;font-size:15px;line-height:1.6;">Estimado/a <b>{{nombre_cliente}}</b>:</p>
        <p style="margin:0 0 18px 0;font-size:15px;line-height:1.6;color:#3a4658;">
          Le informamos el estado de su trámite de <b>{{tipo}}</b>.
        </p>

        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 18px 0;">
          <tr><td style="background:#0B1F3A;border-radius:14px;padding:24px 30px;">
            <div style="font-size:13px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#8fb4ee;margin-bottom:10px;">Estado actual</div>
            <div style="font-size:30px;font-weight:800;color:#ffffff;line-height:1.1;">{{estado}}</div>
          </td></tr>
        </table>

        {{bloque_detalle}}

        <p style="margin:0 0 8px 0;font-size:14px;line-height:1.6;color:#3a4658;">Saludos cordiales,</p>
        {{bloque_firma}}
      </td></tr>

      <tr><td style="padding:18px 28px 26px 28px;border-top:1px solid #e5eaf2;">
        <p style="margin:0;font-size:12px;line-height:1.6;color:#8593a8;">
          Este correo y su contenido son confidenciales y están dirigidos exclusivamente a <b>{{nombre_cliente}}</b>.
        </p>
      </td></tr>

    </table>
  </td></tr>
</table>
```

### 5.6 · `email_templates/tickets_completado.html`

Crear `notion_automation/email_templates/tickets_completado.html` (igual estructura; cambia el bloque
central y el mensaje). Reemplazar el bloque del cuerpo por:

```html
      <tr><td style="padding:30px 28px 8px 28px;">
        <p style="margin:0 0 16px 0;font-size:15px;line-height:1.6;">Estimado/a <b>{{nombre_cliente}}</b>:</p>
        <p style="margin:0 0 18px 0;font-size:15px;line-height:1.6;color:#3a4658;">
          Nos complace informarle que su trámite de <b>{{tipo}}</b> ha sido
          <b style="color:#1c7c4a;">completado</b> exitosamente.
        </p>

        {{bloque_detalle}}

        <p style="margin:0 0 8px 0;font-size:14px;line-height:1.6;color:#3a4658;">Saludos cordiales,</p>
        {{bloque_firma}}
      </td></tr>
```

(El encabezado con logo y el pie de confidencialidad son idénticos a §5.5.)

### 5.7 · `email_templates/tickets_cobranza.html`

Crear `notion_automation/email_templates/tickets_cobranza.html`. Bloque del cuerpo:

```html
      <tr><td style="padding:30px 28px 8px 28px;">
        <p style="margin:0 0 16px 0;font-size:15px;line-height:1.6;">Estimado/a <b>{{nombre_cliente}}</b>:</p>
        <p style="margin:0 0 18px 0;font-size:15px;line-height:1.6;color:#3a4658;">
          Su trámite de <b>{{tipo}}</b> se encuentra finalizado y registra un
          <b>pago pendiente</b>. Puede regularizarlo mediante transferencia a la siguiente cuenta:
        </p>

        {{bloque_detalle}}

        <p style="margin:0 0 8px 0;font-size:14px;line-height:1.6;color:#3a4658;">Saludos cordiales,</p>
        {{bloque_firma}}
      </td></tr>
```

(El `{{bloque_detalle}}` de cobranza trae los datos bancarios GCP; lo arma el handler, §5.1.)

### 5.8 · Plantillas de texto plano

Crear las 3 versiones `.txt` (fallback para clientes sin HTML). Ejemplo `tickets_avance.txt`:

```
Asunto: Estado de su trámite de {{tipo}} — GCP

Estimado/a {{nombre_cliente}}:

Le informamos el estado de su trámite de {{tipo}}.
Estado actual: {{estado}}.
{{linea_detalle}}

Saludos cordiales,
GCP · Asesoría Contable
```

`tickets_completado.txt` y `tickets_cobranza.txt` son análogas (cambian las frases; ambas incluyen
`{{linea_detalle}}`; cobranza lo usa para los datos bancarios).

---

## §6 · Configuración en Notion (lo hace el usuario)

1. **Backup** de Tickets - Servicios (export CSV antes de tocar — R1).
2. **Crear las columnas** de §2.3 con los nombres EXACTOS: `Email` (email), `Estado Correo` (status,
   con opción `Enviado`), `Fecha Envío` (date).
3. **Crear los 3 botones** (tipo Button → *Add step* → *Send webhook*), todos con:
   - **Method:** POST
   - **Header:** `X-AuditAI-Secret` = el `WEBHOOK_SECRET` (el mismo de F29/RRHH)
   - **Contenido (body):** agregar las propiedades **`Tarea`** y **`Email`** (⚠️ crítico: sin
     `Tarea` el backend no puede identificar la fila → 400 "No se puede ejecutar el botón").
   - **URL** (única diferencia entre los 3 botones):

   | Botón | URL |
   |-------|-----|
   | `Enviar Avance` | `https://auditai-backend-gubv.onrender.com/webhook/tickets/avance` |
   | `Enviar Completado` | `https://auditai-backend-gubv.onrender.com/webhook/tickets/completado` |
   | `Enviar Cobranza` | `https://auditai-backend-gubv.onrender.com/webhook/tickets/cobranza` |

---

## §7 · Prueba end-to-end (criterio de aceptación)

### 7.1 · Preparación
1. Elegir/crear una fila de prueba con `Tarea` = un nombre de prueba (ej. `ZZ_TEST Tickets`),
   `Email` = un correo propio verificable, `Tipo` = un servicio (ej. Constitución), `Estado` = un
   estado (ej. En progreso), `Asignado` = un asesor activo (Seba/Carlos/Constanza/Matilde),
   opcional `Descripción` y `Fecha prometida`.
2. No hace falta backend local ni ngrok: producción es Render (always-on).

### 7.2 · Ejecución y criterios
1. Apretar **cada** botón (Avance, Completado, Cobranza) en la fila de prueba.
2. Logs de Render: `request recibida · path=/webhook/tickets/<tipo> · tiene_secreto=True` →
   `correo tickets/<tipo> enviado OK · remitente=...`.
3. Correos recibidos (los 3):
   - **Avance:** asunto `Estado de su trámite de Constitución — GCP`, muestra el `Estado`, la
     descripción y la fecha comprometida si las hay.
   - **Completado:** asunto `Su trámite de Constitución está listo — GCP`.
   - **Cobranza:** asunto `Pago pendiente — trámite de Constitución — GCP`, con datos bancarios GCP.
   - Los 3: logo, firma del asesor asignado, BCC a Carlos.
4. En Notion: `Estado Correo` = `Enviado` y `Fecha Envío` poblada tras cada envío.
5. Casos borde: fila **sin `Email`** → `{"ok": false, "motivo": "fila sin Email..."}` sin crash;
   `Asignado` vacío → sale desde `EMAIL_FROM` con firma "Equipo GCP".

### 7.3 · Depuración

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| "No se puede ejecutar el botón" (404) | La URL no coincide (`/webhook/tickets/<tipo>` con tipo válido) o el deploy no está | `POST` sin secreto a la URL debe dar **401**, no 404. Push → Render redespliega (~2-3 min). |
| 400 "No se puede ejecutar" | Falta `Tarea` en el Contenido del botón, o payload sin identificador | Agregar `Tarea` y `Email` al Contenido (§6). Ver `estructura payload` en el log. |
| 404 "no se encontro fila con ese Tarea" | El nombre no matchea exacto (espacios, tildes) | Corregir el valor de `Tarea` en la fila. |
| Botón "exitoso" pero no llega correo | Fila sin `Email` → `{"ok": false, ...}` (solo en logs de Render) | Poblar `Email`. |
| Llega con plantilla equivocada (parece F29) | Falta el archivo `tickets_<tipo>.html/.txt` → `render()` cae a `f29_email` | Crear los 6 archivos de plantilla (§5.5–5.8). |
| `Asesor '...' marcado como pendiente` | El `Asignado` está `pendiente:true` en `asesores_smtp.json` | Activarlo o reasignar la fila. |
| Envía pero `Estado Correo`/`Fecha Envío` no cambian | Columna ausente o nombre/opción no calza exacto | Ver §2.3 y R5; el log dice qué columna se omitió. |

---

## §8 · Checklist de implementación

### Fase 0 — Código
- [ ] `handlers/tickets.py` (§5.1) — `procesar(page_id, tipo_correo)` con las 3 variantes y write-back tolerante
- [ ] Extender `render()` y `enviar()` en `email_sender.py` con `extra_vars` (§5.2)
- [ ] Endpoint `POST /webhook/tickets/<tipo>` en `app.py` (§5.3)
- [ ] Ramas de identificación por `Tarea` en `_procesar_webhook_generico` (§5.4)
- [ ] 3 plantillas HTML: `tickets_avance/completado/cobranza.html` (§5.5–5.7)
- [ ] 3 plantillas TXT: `tickets_avance/completado/cobranza.txt` (§5.8)
- [ ] `python -m py_compile` de los archivos tocados + smoke test de render (sin enviar)

### Fase 1 — Notion (lo hace el usuario)
- [ ] Backup CSV de Tickets - Servicios
- [ ] Columna `Email` (email)
- [ ] Columna `Estado Correo` (status, con opción `Enviado`)
- [ ] Columna `Fecha Envío` (date)
- [ ] 3 botones con sus URLs, header y `Tarea`+`Email` en el Contenido (§6)

### Fase 2 — Prueba E2E
- [ ] Fila de prueba `ZZ_TEST Tickets` con Email propio
- [ ] Apretar los 3 botones → verificar los 3 correos + write-back (§7)
- [ ] Caso borde: fila sin `Email` → error controlado
- [ ] Verificar que F29 y RRHH siguen funcionando (no se rompió `enviar()`/router)

### Fase 3 — Integración
- [ ] Verificar BCC a Carlos en los 3 correos
- [ ] Actualizar [`24-arquitectura-multi-automatizacion.md`](24-arquitectura-multi-automatizacion.md) (Tickets pasa de 📋 a ✅) y el [`README`](README.md)

---

## §9 · Contingencias

| Situación | Acción |
|-----------|--------|
| Dos filas con el mismo `Tarea` (mismo cliente, 2 trámites) | Hoy no pasa (79 únicas), pero el filtro devuelve la primera. Mitigar: diferenciar el `Tarea` (ej. "Cliente — Servicio") o agregar un identificador único al Contenido del botón. |
| `Asignado` vacío o no está en `asesores_smtp.json` | Fallback a `EMAIL_FROM` con firma "Equipo GCP" (ya implementado en `email_sender.py`). |
| `Tipo` con varios servicios (multi_select) | El handler los une con ", " (ej. "Constitución, Recupero de IVA"). |
| El cliente no tiene email conocido | Poblar `Email` a mano en la fila. No hay lookup por RUT (la base no tiene RUT). |
| Falta un archivo de plantilla | `render()` cae a `f29_email` (no rompe, pero manda el correo equivocado). Crear los 6 archivos. |
| Se quiere un 4º tipo de correo | Agregar la entrada a `CORREOS` en `handlers/tickets.py`, el `<tipo>` a `_TICKETS_TIPOS` en `app.py`, y las 2 plantillas. |

---

**Anterior:** [`25-automatizacion-rrhh-correo.md`](25-automatizacion-rrhh-correo.md) · **Volver al** [`README`](README.md)
