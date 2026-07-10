# 26 · Automatización Tickets - Servicios — correo al cliente (guía ejecutable para LLM)

> **Misión:** implementar la automatización de correos de la página **Tickets - Servicios** en Notion.
> Cada fila es un **trámite de un cliente** (constitución de empresa, recupero de IVA, patente, etc.).
> El asesor aprieta un botón y se le envía al cliente un correo sobre su trámite. Hay **3 tipos**
> (3 plantillas), y **el cuerpo del correo lo redacta el asesor por ticket** en una columna de Notion:
> **Avance** (reporte de estado), **Completado**, **Cobranza**.
>
> **Origen de los requisitos:** audio de Carlos (jefe de GCP), transcrito en
> [`../audio-carlos.txt`](../audio-carlos.txt). Carlos pidió explícitamente poder **personalizar el
> mensaje escribiéndolo "en otra casilla del mismo Notion"**, para ir **reportando** al cliente
> ("está listo esto, esto no, falta esto de tu parte"), y que el flujo termine en **cobranza**
> ("le salimos a cobrar el trabajo"). El §0.1 mapea cada frase suya a cómo se cumple.
>
> **Arquitectura:** se inserta en el sistema multi-handler del [`doc 24`](24-arquitectura-multi-automatizacion.md)
> siguiendo el patrón ya probado de RRHH ([`doc 25`](25-automatizacion-rrhh-correo.md)): un handler
> `handlers/tickets.py` + 3 plantillas `tickets_*.html/.txt` + endpoints `POST /webhook/tickets/<tipo>`.
> Se reutiliza toda la infraestructura (API Notion, SendGrid, asesores, BCC a Carlos).
>
> **Verificado contra la base real por API (09-jul-2026).** Trae el código completo del handler, las 3
> plantillas y la config. Si algo difiere al implementar, mandan `app.py`, `handlers/` y `email_sender.py`.

---

## §0 · Decisiones tomadas (usuario + Carlos, 09-jul-2026) — NO re-preguntar

- **Destinatario:** el **cliente** del ticket (su nombre está en `Tarea`).
- **Fuente del email:** una **nueva columna `Email`** en Tickets, que el asesor llena por fila (la base
  no tiene RUT para cruzar con la central; por eso email directo, como RRHH).
- **Cuerpo del correo:** lo escribe el asesor por ticket en una **nueva columna `Mensaje Correo`**
  (texto libre). Ahí redacta el reporte ("está listo el borrador, nos falta tu cédula", etc.).
  - **Si `Mensaje Correo` está vacío** → sale un **texto estándar por tipo** (fallback). Así se cubren
    las dos opciones que planteó Carlos: personalizable **y** "muy estándar".
  - El texto libre **respeta saltos de línea**, así el asesor puede hacer una lista tipo:
    `✓ Escritura lista` / `✗ Falta tu cédula`.
- **3 tipos = 3 plantillas = 3 botones:** Avance, Completado, Cobranza. Cada uno con su marco visual;
  el cuerpo sale de `Mensaje Correo` (o su estándar).
- **Cobranza** agrega automáticamente los **datos de transferencia GCP** (constante `BANCO_GCP_HTML`).
- **Disparador:** botón manual por fila (mismo patrón F29/RRHH). **Re-enviable** (los tickets duran de
  1 a 4 meses; el asesor puede mandar varios avances a lo largo del trámite).
- **Remitente/firma:** la persona en `Asignado` (mapea directo a `asesores_smtp.json`).
- **`Descripción`** (columna interna existente) **NO** se envía al cliente (puede tener notas internas);
  el correo usa solo `Mensaje Correo`.

### §0.1 · Cómo este diseño cumple lo que pidió Carlos (audio)

| Frase de Carlos | Cómo se cumple |
|-----------------|----------------|
| "le tratamos de cobrar, le salimos a cobrar el trabajo al cliente" | Correo **Cobranza** (`/webhook/tickets/cobranza`) con los datos de transferencia GCP. |
| "un correo tipo… reportando: está listo esto, esto no, falta esto de tu parte" | Correo **Avance**; el reporte lo escribe el asesor en `Mensaje Correo` (con saltos de línea para listar). |
| "ese correo tipo se puede ir personalizando… anotando en otra casilla del mismo Notion" | Columna **`Mensaje Correo`** (rich_text) editable por fila = cuerpo del correo. |
| "o tú lo tenés que parametrizar, todo muy estándar" | Fallback: `Mensaje Correo` vacío → texto **estándar por tipo**. |
| "está listo esto" | Correo **Completado**. |
| "estos son un poco distintos a los de los impuestos" | Sin monto, sin fecha límite: contenido libre + 3 tipos propios de trámite. |
| "ese ticket dura un mes, esas otras duran cuatro" | Botón re-enviable; el sistema no asume ningún período. |

---

## §1 · Reglas inquebrantables

| # | Regla | Detalle |
|---|-------|---------|
| R1 | **La base original es sagrada** | Tickets - Servicios es real (79 trámites). Solo se **agregan** columnas (aditivo, reversible), y **las crea el usuario** en la UI, con backup CSV previo. El backend nunca modifica el esquema. |
| R2 | **Identificación por `Tarea`** | El payload del botón no trae page_id utilizable (lección F29/RRHH). Se identifica por **`Tarea`** (title = nombre del cliente). Hoy las 79 son únicas (verificado). Cascada: page_id → `data.id`/`entity.id` → `Tarea`. |
| R3 | **PII nunca en outputs** | Nombre, email y mensaje no se imprimen ni loguean (solo presencia booleana). Se lee la fila por API en memoria. |
| R4 | **El webhook se autentica** | Header `X-AuditAI-Secret` = `WEBHOOK_SECRET` (el mismo de F29/RRHH). Sin secreto válido → 401. |
| R5 | **Verificar nombre EXACTO de columna vía API antes de codear** | Notion es case/acento-sensitive (`Fecha Envío` ≠ `Fecha envío`). Este bug ya pegó 3 veces. Confirmar cada columna nueva contra el esquema en vivo antes de fijar la constante. |
| R6 | **Write-back tolerante** | El PATCH se arma **solo con las columnas presentes** en la fila. Un correo enviado nunca queda sin registrar por una columna mal nombrada o ausente. |
| R7 | **BCC automático a Carlos** | Constante `BCC_EXTRA` en `email_sender.py`. Ya aplica a todos los envíos. Sin cambios. |

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
| `Tipo` | **multi_select** | Servicio(s): Constitución, Cuenta Corriente, Patente Comercial, Asesoría Tributaria, Declaración de Renta, Oficina Virtual, Fiscalización SII, F29, Declaración de Renta (F22), Termino de Giro, Reorganización Empresarial, Recupero de IVA → asunto y cuerpo |
| `Estado` | **status** | Avance interno → se muestra como línea "Estado actual" en el correo de **Avance** |
| `Asignado` | **person** | Miembro de GCP a cargo → **remitente/firma** (mapea a `asesores_smtp.json`) |
| `Descripción` | text | Notas internas — **NO** se envían al cliente |
| `Fecha prometida` | date | Compromiso opcional → línea en el correo de **Avance** |
| `Compromiso` | formula (read-only) | Marca atrasados. No se escribe |
| `Número` | number | Casi vacío (2/79). **No** usar como identificador |
| `Actualizado` | last_edited_time (read-only) | No se usa |

> **`Asignado` son los 4 asesores** (Constanza Gaggero, Matilde Mateluna, Carlos Cereceda, Sebastián
> Robles), todos en `asesores_smtp.json` **con nombre completo**. A diferencia de RRHH, `nc.people_names()`
> devuelve el nombre completo y matchea directo — **no hace falta mapa de alias**. Filas con `Asignado`
> vacío → remitente genérico `EMAIL_FROM` con firma "Equipo GCP".

### 2.3 · Columnas a CREAR en Tickets (las crea el usuario en la UI)

| Columna nueva | Tipo | Nombre EXACTO | Para qué |
|---------------|------|---------------|----------|
| **`Email`** | email (o text) | `Email` | Correo del cliente destinatario. **Requerido** para enviar. |
| **`Mensaje Correo`** | text | `Mensaje Correo` | **Cuerpo del correo**, redactado por el asesor por ticket. Si está vacío → texto estándar. |
| **`Estado Correo`** | status | `Estado Correo` | Write-back tras el envío. Crear la opción exacta **`Enviado`**. |
| **`Fecha Envío`** | date | `Fecha Envío` | Write-back con la fecha/hora del envío. |
| **`Enviar Avance`** | button | — | Dispara el correo de avance (§6). |
| **`Enviar Completado`** | button | — | Dispara el correo de completado (§6). |
| **`Enviar Cobranza`** | button | — | Dispara el correo de cobranza (§6). |

> ⚠️ Respetar los nombres EXACTOS (R5). Si `Estado Correo` no tiene la opción `Enviado`, o `Fecha
> Envío`/`Mensaje Correo` se llaman distinto, el write-back tolerante **omite esa columna** (deja un
> `warning`) y el correo igual se envía. Verificar por API tras crearlas.

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
  ├─ 2. extrae Tarea(cliente), Email, Mensaje Correo, Tipo, Estado, Fecha prometida, Asignado
  ├─ 3. valida Email y cliente (si faltan → error controlado, sin crash)
  ├─ 4. cuerpo = Mensaje Correo (si hay) o texto estándar del tipo
  ├─ 5. Asignado (person) → nombre → asesor de asesores_smtp.json (firma/remitente)
  ├─ 6. es.enviar(template="tickets_<tipo>", asunto=..., extra_vars=...)
  │     ├─ SendGrid (SENDGRID_API_KEY en Render; SMTP solo fallback local)
  │     └─ BCC automático a Carlos (BCC_EXTRA)
  └─ 7. write-back TOLERANTE: Estado Correo="Enviado" + Fecha Envío=now (si existen)
```

Un solo handler y un endpoint parametrizado por `<tipo>`; los 3 botones solo difieren en la URL.
Errores controlados (sin Email, asesor `pendiente`, fallo SendGrid) devuelven
`{"ok": false, "motivo": ...}` y quedan en el log de Render **sin PII**.

---

## §4 · Los 3 correos: contenido

Los tres comparten el layout visual de F29/RRHH (tabla 600px, logo GCP inline por CID, navy `#0B1F3A`,
firma del asesor, pie de confidencialidad). **El cuerpo central es el `Mensaje Correo` del asesor**
(o el estándar del tipo si está vacío). Cambian el asunto y el marco.

### 4.1 · Avance (`tickets_avance`)
- **Asunto:** `Avance de su trámite de {Tipo} — GCP`
- **Cuerpo:** saludo + **mensaje del asesor** (o estándar: "Le escribimos para informarle sobre el
  avance de su trámite de {Tipo}.") + línea **Estado actual: {Estado}** + **Fecha comprometida** si hay.
- Ejemplo de `Mensaje Correo` que escribiría el asesor:
  > Su constitución avanza bien. Ya está lista la escritura y el RUT.
  > Nos falta de su parte: cédula escaneada por ambos lados.

### 4.2 · Completado (`tickets_completado`)
- **Asunto:** `Su trámite de {Tipo} está listo — GCP`
- **Cuerpo:** saludo + insignia "✓ Trámite completado" + **mensaje del asesor** (o estándar: "Nos
  complace informarle que su trámite de {Tipo} ha sido completado exitosamente.").

### 4.3 · Cobranza (`tickets_cobranza`)
- **Asunto:** `Pago pendiente — trámite de {Tipo} — GCP`
- **Cuerpo:** saludo + **mensaje del asesor** (o estándar: "Su trámite de {Tipo} se encuentra
  finalizado y registra un pago pendiente.") + "Puede regularizarlo mediante transferencia a:" +
  **datos bancarios GCP** (`BANCO_GCP_HTML`).

**Variables que inyecta el handler** (vía `extra_vars`, §5.2): `{{tipo}}`, `{{bloque_mensaje}}`
(cuerpo, HTML), `{{linea_mensaje}}` (cuerpo, texto), `{{bloque_detalle}}` (Estado+fecha en avance /
datos bancarios en cobranza), `{{linea_detalle}}`. Las estándar (`{{nombre_cliente}}`,
`{{bloque_firma}}`, `{{contacto_email}}`) las provee `render()`.

---

## §5 · Código a implementar

### 5.1 · `handlers/tickets.py` — handler completo

Crear `notion_automation/handlers/tickets.py`:

```python
"""Handler de los botones Enviar Avance / Completado / Cobranza de Tickets - Servicios.
Destinatario = CLIENTE (Tarea = nombre, Email = correo). Remitente = Asignado.
El CUERPO lo escribe el asesor en la columna 'Mensaje Correo' (personalizable por ticket:
'esta listo X, nos falta Y de tu parte'); si esta vacia, se usa un texto estandar por tipo.
Un mismo handler sirve las 3 plantillas segun tipo_correo (audio de Carlos, doc 26 §0.1)."""
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
ASIGNADO = "Asignado"           # person -> remitente/firma
EMAIL_CLIENTE = "Email"         # columna nueva
MENSAJE = "Mensaje Correo"      # columna nueva: cuerpo personalizable (rich_text)
FECHA_PROM = "Fecha prometida"  # date

# Write-back (columnas nuevas)
STATUS_COL = "Estado Correo"
STATUS_ENVIADO = "Enviado"
FECHA_COL = "Fecha Envío"

# tipo_correo -> (plantilla, plantilla de asunto, texto estandar si Mensaje Correo esta vacio)
CORREOS = {
    "avance": (
        "tickets_avance",
        "Avance de su trámite de {tipo} — GCP",
        "Le escribimos para informarle sobre el avance de su trámite de {tipo}.",
    ),
    "completado": (
        "tickets_completado",
        "Su trámite de {tipo} está listo — GCP",
        "Nos complace informarle que su trámite de {tipo} ha sido completado exitosamente.",
    ),
    "cobranza": (
        "tickets_cobranza",
        "Pago pendiente — trámite de {tipo} — GCP",
        "Su trámite de {tipo} se encuentra finalizado y registra un pago pendiente.",
    ),
}


def _fmt_fecha(iso: str) -> str:
    """ISO -> 'dd/mm/aaaa'. '' si no hay o no parsea."""
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except ValueError:
        return iso[:10]


def _bloque_mensaje(mensaje: str, estandar: str) -> tuple[str, str]:
    """Cuerpo principal: el texto del asesor (personalizado) o el estandar del tipo.
    Respeta saltos de linea para que el asesor pueda listar (checklist)."""
    txt = (mensaje or "").strip() or estandar
    html_txt = es._escape(txt).replace("\n", "<br>")
    html = (
        f'<p style="margin:0 0 18px 0;font-size:15px;line-height:1.6;color:#3a4658;">{html_txt}</p>'
    )
    return html, txt


def _bloque_detalle(tipo_correo: str, estado: str, fecha_prom: str) -> tuple[str, str]:
    """Extra especifico del tipo. avance: Estado + Fecha; cobranza: datos bancarios GCP."""
    ph, pt = [], []
    if tipo_correo == "avance":
        if estado:
            ph.append(
                f'<p style="margin:0 0 8px 0;font-size:14px;color:#3a4658;line-height:1.6;">'
                f'<b>Estado actual:</b> {es._escape(estado)}.</p>'
            )
            pt.append(f"Estado actual: {estado}.")
        f = _fmt_fecha(fecha_prom)
        if f:
            ph.append(
                f'<p style="margin:0 0 14px 0;font-size:14px;color:#3a4658;line-height:1.6;">'
                f'<b>Fecha comprometida:</b> {f}.</p>'
            )
            pt.append(f"Fecha comprometida: {f}.")
    elif tipo_correo == "cobranza":
        ph.append(
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            'style="margin:0 0 18px 0;"><tr><td style="background:#eef4ff;border:1px solid #d3e0f5;'
            'border-left:4px solid #0B1F3A;border-radius:10px;padding:14px 18px;font-size:14px;'
            f'color:#3a4658;line-height:1.6;">{es.BANCO_GCP_HTML}</td></tr></table>'
        )
        pt.append(es.BANCO_GCP_TXT)
    return "".join(ph), "\n".join(pt)


def procesar(page_id: str, tipo_correo: str) -> dict:
    """Lee la fila, envia el correo del tipo pedido y escribe el write-back.
    Devuelve {'ok': bool, 'remitente': str, 'motivo': str (si falla)}."""
    cfg = CORREOS.get(tipo_correo)
    if not cfg:
        return {"ok": False, "motivo": f"tipo de correo desconocido: {tipo_correo!r}"}
    plantilla, asunto_tpl, estandar_tpl = cfg

    props = nc.get_page(page_id)["properties"]
    cliente = nc.plain(props.get(TAREA, {}))
    email = nc.plain(props.get(EMAIL_CLIENTE, {}))
    mensaje = nc.plain(props.get(MENSAJE, {}))
    estado = (props.get(ESTADO, {}).get("status") or {}).get("name", "")
    fecha_prom = (props.get(FECHA_PROM, {}).get("date") or {}).get("start", "") or ""
    tipos = [o.get("name", "") for o in (props.get(TIPO, {}).get("multi_select") or [])]
    tipo = ", ".join(t for t in tipos if t) or "trámite"
    asignados = nc.people_names(props.get(ASIGNADO, {}))
    asesor = asignados[0] if asignados else ""

    log.info("tickets tipo=%s page_id=%s cliente_present=%s email_present=%s mensaje_present=%s asesor=%r",
             tipo_correo, page_id, bool(cliente), bool(email), bool(mensaje), asesor)

    if not email:
        return {"ok": False, "motivo": "fila sin Email (columna Email vacía)"}
    if not cliente:
        return {"ok": False, "motivo": "fila sin Tarea (nombre de cliente, necesario)"}

    estandar = estandar_tpl.format(tipo=tipo)
    b_msg = _bloque_mensaje(mensaje, estandar)
    b_det = _bloque_detalle(tipo_correo, estado, fecha_prom)
    extra_vars = {
        "tipo": tipo,
        "bloque_mensaje": b_msg[0], "linea_mensaje": b_msg[1],
        "bloque_detalle": b_det[0], "linea_detalle": b_det[1],
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

Las plantillas de Tickets usan marcadores propios (`{{tipo}}`, `{{bloque_mensaje}}`,
`{{linea_mensaje}}`, `{{bloque_detalle}}`, `{{linea_detalle}}`) que `render()` hoy no conoce. Se agrega
un parámetro genérico `extra_vars` que se **fusiona** en el dict de variables (gana sobre las estándar).
Cambio pequeño y retro-compatible (no afecta F29 ni RRHH).

**a) En `render()`** — agregar el parámetro y fusionarlo antes del bucle de reemplazo:

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
    # (justo antes de:  for k, v in vars_.items():)
    if extra_vars:
        vars_.update({k: (v if isinstance(v, str) else str(v)) for k, v in extra_vars.items()})
    for k, v in vars_.items():
        html = html.replace("{{" + k + "}}", v)
        txt = txt.replace("{{" + k + "}}", v)
    return html, txt
```

**b) En `enviar()`** — aceptar `extra_vars` y pasarlo a `render()` en la rama genérica (`else`):

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

> No se toca la rama `if template == "rrhh_email"` ni la lógica de F29. `BANCO_GCP_HTML`,
> `BANCO_GCP_TXT` y `_escape` (`from html import escape as _escape`) ya existen en `email_sender.py`.

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

En `_procesar_webhook_generico()` (en `app.py`), agregar la rama de TICKETS junto a la de RRHH. Dos puntos:

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
> columna **title** `Tarea` — verificado que Notion acepta `rich_text` sobre `title` (igual que RRHH
> con `RUT`). **Mejora futura opcional** (doc 24 §6): reemplazar estas ramas por un registro
> `{nombre: (ds_id, prop)}`. No es necesario para el MVP.

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

        <p style="margin:0 0 16px 0;font-size:13px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#3a5a8c;">Avance · {{tipo}}</p>

        {{bloque_mensaje}}
        {{bloque_detalle}}

        <p style="margin:18px 0 8px 0;font-size:14px;line-height:1.6;color:#3a4658;">Saludos cordiales,</p>
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

Igual estructura que §5.5 (mismo encabezado y pie). El bloque del cuerpo:

```html
      <tr><td style="padding:30px 28px 8px 28px;">
        <p style="margin:0 0 16px 0;font-size:15px;line-height:1.6;">Estimado/a <b>{{nombre_cliente}}</b>:</p>

        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 18px 0;">
          <tr><td style="background:#e8f5ee;border-left:4px solid #1c7c4a;border-radius:10px;padding:12px 16px;font-size:14px;font-weight:700;color:#1c7c4a;">
            ✓ Trámite de {{tipo}} completado
          </td></tr>
        </table>

        {{bloque_mensaje}}
        {{bloque_detalle}}

        <p style="margin:18px 0 8px 0;font-size:14px;line-height:1.6;color:#3a4658;">Saludos cordiales,</p>
        {{bloque_firma}}
      </td></tr>
```

### 5.7 · `email_templates/tickets_cobranza.html`

Igual estructura; el bloque del cuerpo:

```html
      <tr><td style="padding:30px 28px 8px 28px;">
        <p style="margin:0 0 16px 0;font-size:15px;line-height:1.6;">Estimado/a <b>{{nombre_cliente}}</b>:</p>

        {{bloque_mensaje}}

        <p style="margin:0 0 12px 0;font-size:14px;line-height:1.6;color:#3a4658;">
          Puede regularizar el pago mediante transferencia a la siguiente cuenta:
        </p>
        {{bloque_detalle}}

        <p style="margin:18px 0 8px 0;font-size:14px;line-height:1.6;color:#3a4658;">Saludos cordiales,</p>
        {{bloque_firma}}
      </td></tr>
```

(El `{{bloque_detalle}}` de cobranza trae los datos bancarios GCP; lo arma el handler, §5.1.)

### 5.8 · Plantillas de texto plano

Crear las 3 `.txt`. Ejemplo `tickets_avance.txt`:

```
Asunto: Avance de su trámite de {{tipo}} — GCP

Estimado/a {{nombre_cliente}}:

{{linea_mensaje}}
{{linea_detalle}}

Saludos cordiales,
GCP · Asesoría Contable
```

`tickets_completado.txt` y `tickets_cobranza.txt` son análogas (cambia el asunto y alguna frase; las
tres incluyen `{{linea_mensaje}}` y `{{linea_detalle}}`; cobranza usa `{{linea_detalle}}` para los
datos bancarios).

---

## §6 · Configuración en Notion (lo hace el usuario)

1. **Backup** de Tickets - Servicios (export CSV antes de tocar — R1).
2. **Crear las columnas** de §2.3 con los nombres EXACTOS: `Email` (email), `Mensaje Correo` (text),
   `Estado Correo` (status, con opción `Enviado`), `Fecha Envío` (date).
3. **Crear los 3 botones** (tipo Button → *Add step* → *Send webhook*), todos con:
   - **Method:** POST
   - **Header:** `X-AuditAI-Secret` = el `WEBHOOK_SECRET` (el mismo de F29/RRHH)
   - **Contenido (body):** agregar las propiedades **`Tarea`** y **`Email`** (⚠️ sin `Tarea` el backend
     no puede identificar la fila → 400 "No se puede ejecutar el botón").
   - **URL** (única diferencia entre los 3):

   | Botón | URL |
   |-------|-----|
   | `Enviar Avance` | `https://auditai-backend-gubv.onrender.com/webhook/tickets/avance` |
   | `Enviar Completado` | `https://auditai-backend-gubv.onrender.com/webhook/tickets/completado` |
   | `Enviar Cobranza` | `https://auditai-backend-gubv.onrender.com/webhook/tickets/cobranza` |

4. **Uso diario:** el asesor escribe el reporte en `Mensaje Correo` (o lo deja vacío para el estándar)
   y aprieta el botón que corresponda. Puede reenviar avances las veces que necesite durante el trámite.

---

## §7 · Prueba end-to-end (criterio de aceptación)

### 7.1 · Preparación
1. Crear/elegir una fila de prueba: `Tarea` = `ZZ_TEST Tickets`, `Email` = un correo propio,
   `Tipo` = Constitución, `Estado` = En progreso, `Asignado` = un asesor activo, `Mensaje Correo` =
   un texto de prueba con 2 líneas, opcional `Fecha prometida`.
2. Producción es Render (always-on); no hace falta backend local ni ngrok.

### 7.2 · Ejecución y criterios
1. Apretar **cada** botón (Avance, Completado, Cobranza) en la fila de prueba.
2. Logs de Render: `request recibida · path=/webhook/tickets/<tipo> · tiene_secreto=True` →
   `correo tickets/<tipo> enviado OK · remitente=...`.
3. Correos recibidos:
   - **Avance:** asunto `Avance de su trámite de Constitución — GCP`; el cuerpo muestra el
     `Mensaje Correo` (respetando los saltos de línea) + "Estado actual: En progreso" + fecha si hay.
   - **Completado:** insignia "✓ Trámite de Constitución completado" + el mensaje.
   - **Cobranza:** el mensaje + "transferencia a:" + datos bancarios GCP.
   - Los 3: logo, firma del asesor asignado, BCC a Carlos.
4. **Fallback:** vaciar `Mensaje Correo` y reenviar → debe salir el **texto estándar** del tipo.
5. En Notion: `Estado Correo` = `Enviado` y `Fecha Envío` poblada tras cada envío.
6. Casos borde: fila **sin `Email`** → `{"ok": false, "motivo": "fila sin Email..."}` sin crash;
   `Asignado` vacío → sale desde `EMAIL_FROM` con firma "Equipo GCP".

### 7.3 · Depuración

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| "No se puede ejecutar el botón" (404) | URL mal, o deploy no aplicado | `POST` sin secreto a la URL debe dar **401**, no 404. Push → Render redespliega (~2-3 min). |
| 400 "No se puede ejecutar" | Falta `Tarea` en el Contenido del botón | Agregar `Tarea` y `Email` al Contenido (§6). |
| 404 "no se encontro fila con ese Tarea" | El nombre no matchea exacto (espacios/tildes) | Corregir el valor de `Tarea`. |
| Botón "exitoso" pero no llega correo | Fila sin `Email` → `{"ok": false, ...}` (solo en logs) | Poblar `Email`. |
| Sale texto estándar cuando esperaba el personalizado | `Mensaje Correo` vacío o mal nombrado | Verificar la columna (nombre exacto) y que tenga texto. |
| Llega con plantilla equivocada (parece F29) | Falta el archivo `tickets_<tipo>.html/.txt` → `render()` cae a `f29_email` | Crear los 6 archivos (§5.5–5.8). |
| `Asesor '...' marcado como pendiente` | El `Asignado` está `pendiente:true` en `asesores_smtp.json` | Activarlo o reasignar la fila. |
| Envía pero `Estado Correo`/`Fecha Envío` no cambian | Columna ausente o nombre/opción no calza | Ver §2.3 y R5; el log dice qué columna se omitió. |

---

## §8 · Checklist de implementación

### Fase 0 — Código
- [ ] `handlers/tickets.py` (§5.1) — `procesar(page_id, tipo_correo)`, cuerpo desde `Mensaje Correo` con fallback estándar, write-back tolerante
- [ ] Extender `render()` y `enviar()` en `email_sender.py` con `extra_vars` (§5.2)
- [ ] Endpoint `POST /webhook/tickets/<tipo>` en `app.py` (§5.3)
- [ ] Ramas de identificación por `Tarea` en `_procesar_webhook_generico` (§5.4)
- [ ] 3 plantillas HTML: `tickets_avance/completado/cobranza.html` (§5.5–5.7)
- [ ] 3 plantillas TXT: `tickets_avance/completado/cobranza.txt` (§5.8)
- [ ] `python -m py_compile` de los archivos tocados + smoke test de render (sin enviar)

### Fase 1 — Notion (lo hace el usuario)
- [ ] Backup CSV de Tickets - Servicios
- [ ] Columna `Email` (email)
- [ ] Columna `Mensaje Correo` (text)
- [ ] Columna `Estado Correo` (status, con opción `Enviado`)
- [ ] Columna `Fecha Envío` (date)
- [ ] 3 botones con sus URLs, header y `Tarea`+`Email` en el Contenido (§6)

### Fase 2 — Prueba E2E
- [ ] Fila de prueba `ZZ_TEST Tickets` con Email propio y `Mensaje Correo`
- [ ] Apretar los 3 botones → verificar los 3 correos + write-back (§7)
- [ ] Verificar el fallback estándar (Mensaje Correo vacío)
- [ ] Caso borde: fila sin `Email` → error controlado
- [ ] Verificar que F29 y RRHH siguen funcionando (no se rompió `enviar()`/router)

### Fase 3 — Integración
- [ ] Verificar BCC a Carlos en los 3 correos
- [ ] Actualizar [`24-arquitectura-multi-automatizacion.md`](24-arquitectura-multi-automatizacion.md) (Tickets pasa a ✅) y el [`README`](README.md)

---

## §9 · Contingencias

| Situación | Acción |
|-----------|--------|
| Dos filas con el mismo `Tarea` (mismo cliente, 2 trámites) | Hoy no pasa (79 únicas), pero el filtro devuelve la primera. Mitigar: diferenciar el `Tarea` (ej. "Cliente — Servicio") o agregar un identificador único al Contenido del botón. |
| `Asignado` vacío o no está en `asesores_smtp.json` | Fallback a `EMAIL_FROM` con firma "Equipo GCP" (ya implementado). |
| `Tipo` con varios servicios (multi_select) | El handler los une con ", " (ej. "Constitución, Recupero de IVA"). |
| El cliente no tiene email conocido | Poblar `Email` a mano. No hay lookup por RUT (la base no tiene RUT). |
| El asesor quiere un cuerpo distinto por envío | Editar `Mensaje Correo` antes de cada clic (se reenvía con el texto nuevo). |
| Falta un archivo de plantilla | `render()` cae a `f29_email` (no rompe, pero manda el correo equivocado). Crear los 6 archivos. |
| Se quiere un 4º tipo de correo | Agregar la entrada a `CORREOS` en `handlers/tickets.py`, el `<tipo>` a `_TICKETS_TIPOS` en `app.py`, y las 2 plantillas. |

---

**Anterior:** [`25-automatizacion-rrhh-correo.md`](25-automatizacion-rrhh-correo.md) · **Volver al** [`README`](README.md)
