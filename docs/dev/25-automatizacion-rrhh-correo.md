# 25 · Automatización RRHH JUNIO 2026 — correo de imposiciones (guía ejecutable para LLM)

> **Misión:** implementar la automatización de la página **RRHH JUNIO 2026** en Notion:
> un botón "Enviar Correo RRHH" por fila que, al apretarse, **envía al cliente un correo
> con el detalle de sus imposiciones del mes** (monto, plazo, etc.). Sigue el mismo patrón
> del F29 (doc [`23`](23-automatizacion-notion-contable-correo.md)) pero con su propio
> handler, su plantilla y su lógica de fecha límite (13 del mes siguiente, no 20).
>
> **Arquitectura:** se inserta en el sistema multi-handler definido en
> [`24-arquitectura-multi-automatizacion.md`](24-arquitectura-multi-automatizacion.md):
> un nuevo handler `handlers/rrhh.py` + plantilla `rrhh_email.html`/`.txt` + endpoint
> `POST /webhook/rrhh`. Todo lo demás (API Notion, envío SMTP/SendGrid, credenciales de
> asesores, BCC a Carlos/Andrea) se reutiliza sin cambios.
>
> **Este documento es autosuficiente.** Un LLM debe poder ejecutarlo sin volver a investigar
> otros docs (aunque enlaza a ellos para contexto). Está escrito paso a paso, con el código
> completo del handler, la plantilla y la configuración.

---

## §0 · Orden de lectura y decisiones ya tomadas

**Leer antes de actuar (en este orden):**
1. [`../../AGENTS.md`](../../AGENTS.md) — reglas de oro (obligatorio).
2. [`09-seguridad-y-respaldo.md`](09-seguridad-y-respaldo.md) — protocolo de respaldo antes de escribir en Notion.
3. [`24-arquitectura-multi-automatizacion.md`](24-arquitectura-multi-automatizacion.md) — arquitectura multi-handler donde se inserta este desarrollo.
4. [`23-automatizacion-notion-contable-correo.md`](23-automatizacion-notion-contable-correo.md) — el patrón F29 ya verificado (E2E exitoso). Este doc sigue el mismo approach.
5. Este documento completo.

**Decisiones del usuario (09-jul-2026) — NO re-preguntar:**
- **Destinatario:** el correo se envía **al cliente** (no al asistente).
- **Asunto dinámico:** `"Imposiciones {mes} {año}- {CLIENTE}"` (ej: "Imposiciones Junio 2026- SERV. PROFESIONALES ESTETICA").
- **Cuerpo literal** (solo cambian las variables):
  > Por medio de la presente informo el monto a pagar por concepto de imposiciones del mes de {mes} {año}.
  > Plazo hasta {día_semana} {día_nº} de {mes_siguiente} a las 13.45 horas.
  > Total a pagar $ {monto_formateado}.-
- **Fecha límite:** **13 del mes siguiente** (día hábil) a las 13:45, con la misma lógica de feriados chilenos del F29.
- **Monto:** columna `MONTO IMPOSICIONES|` de la fila RRHH.
- **Cliente:** columna `CLIENTE` (rich_text).
- **Asistente (remitente):** columna `ASISTENTE` (select) — mapea a los asesores de `asesores_smtp.json`.
- **Columnas nuevas en RRHH:** `Email Cliente` (email), `Estado Correo` (status), `Fecha Envío` (date) — las crea el usuario en Notion.
- **Lookup de email:** si `Email Cliente` está vacío, se busca el email desde la base central `General Customers Data - AuditAI` cruzando por RUT.
- **Andrea** no tiene App Password pero con SendGrid en Render no hace falta.

---

## §1 · Reglas inquebrantables

| # | Regla | Detalle |
|---|---|---|
| R1 | **La base original es sagrada** | RRHH JUNIO 2026 es una base real del cliente. Se le **agregan columnas** (Email Cliente, Estado Correo, Fecha Envío), que es operación aditiva y reversible, pero igual se hace con **backup fechado previo** (export CSV de la base antes de tocar). |
| R2 | **Identificación por RUT** | El botón de Notion NO expone `page_id` como variable seleccionable (lección del F29, ver doc 23 §5.4). Se identifica la fila por **`RUT`** (columna title de RRHH). El mismo extractor recursivo `_buscar_clave` de `app.py` encuentra el RUT en el payload anidado. |
| R3 | **Credenciales y PII nunca en outputs** | `RUT`, email, montos no se imprimen, loguean ni salen en la conversación. El backend lee la fila por API **en memoria**. |
| R4 | **El webhook se autentica** | Mismo `X-AuditAI-Secret` compartido que el F29. El endpoint valida el header antes de procesar. |
| R5 | **Si algo no calza, no adivinar** | Propiedad inexistente, payload con otra forma, template que no carga ⇒ volcar evidencia, mostrar resumen al usuario y decidir juntos. |
| R6 | **BCC automático a Carlos + Andrea** | Ya está implementado en `email_sender.py` (constante `BCC_EXTRA`). No hay que hacer nada extra. |

---

## §2 · Estado actual (09-jul-2026) — no lo redescubras

### Entorno
- **Python 3.14.0**, **Flask**, **requests**, **python-dotenv** instalados en `notion_automation/.venv`.
- **NOTION_TOKEN**, **WEBHOOK_SECRET** definidos en `notion_automation/.env`.
- **SendGrid** configurable vía `SENDGRID_API_KEY` (si no, fallback a SMTP Gmail con App Passwords).
- Backend actual corre en `app.py` con un solo endpoint `/enviar-f29`. Se modificará para soportar múltiples endpoints.

### IDs confirmados

| Recurso | ID |
|---------|----|
| RRHH JUNIO 2026 (data source) | `9c512147-b3ea-8256-a570-871254c13b3d` |
| RRHH JUNIO 2026 (database) | `38712147-b3ea-80f9-9484-e0ad99c94a26` |
| General Customers Data - AuditAI (sandbox) | `4ff12147-b3ea-82f4-98dd-072067524cdc` |
| Contable Junio (F29) | `09b12147-b3ea-8337-a218-87538eab23fc` |

### Estructura de RRHH JUNIO 2026 (columnas existentes)

| Columna | Tipo | Ejemplo | Uso en el correo |
|---------|------|---------|------------------|
| `RUT` | title | `3b3` | Identificador de la fila (para lookup por RUT y cruce con base central) |
| `CLIENTE` | rich_text | `FUNDACION`, `RODOTECH` | Nombre del cliente → asunto y cuerpo |
| `ASISTENTE` | select | `Andrea`, `Seba` | Asignado → remitente del correo (busca en `asesores_smtp.json`) |
| `MONTO IMPOSICIONES\|` | number | `259418` | **Monto a pagar** → cuerpo del correo |
| `IMPUESTO ÚNICO` | number | (null en muestra) | No se usa en este correo (es para cálculo F29, doc 17) |
| `Nº. Trab.` | number | `1` | No se usa en el correo actual |
| `CLAVE` | rich_text | `Cies2026#` | Credencial (no se usa aquí, no exponer) |
| `USUARIO` | rich_text | `10793188-0` | Credencial (no se usa aquí, no exponer) |
| `Previred` | status | `DNP` | Estado (no se usa en el correo) |
| `Liquidaciones` | status | `Done`, `In progress` | Estado (no se usa en el correo) |
| `DTGO` | rich_text | (vacío) | Sin mapear |
| `Date` | date | (null) | No se usa |

### Columnas a crear en RRHH (las crea el usuario en la UI de Notion)

| Columna nueva | Tipo | Para qué |
|---------------|------|----------|
| **`Email Cliente`** | email | Correo del cliente destinatario. Si está vacío, el backend busca en la base central por RUT. |
| **`Estado Correo`** | status | Write-back tras el envío → se escribe "Enviado". El usuario puede monitorear qué filas se han enviado. |
| **`Fecha Envío`** | date | Write-back con la fecha/hora del envío. |

### Datos del golden test (para la prueba E2E)

De la fila de prueba (a crear una igual que `ZZ_TEST AuditAI` en F29):

| Campo | Valor de prueba |
|-------|----------------|
| RUT | `12345678-9` |
| CLIENTE | `ZZ_TEST AuditAI RRHH` |
| MONTO IMPOSICIONES| `15474109` |
| ASISTENTE | `Seba` (o el que tenga App Password) |
| Email Cliente | una dirección real verificable |

---

## §3 · Arquitectura: cómo se conecta

```
Notion (RRHH JUNIO 2026)
  │  [Botón "Enviar Correo RRHH"]
  │  POST /webhook/rrhh
  │  header: X-AuditAI-Secret = <WEBHOOK_SECRET>
  │  body: { "Rut": "...", "CLIENTE": "...", "Email Cliente": "..." }
  ▼
app.py → rutea a handlers/rrhh.procesar(page_id)
  │
  ├─ 1. nc.get_page(page_id)           # lee la fila de RRHH
  ├─ 2. extrae: CLIENTE, MONTO IMPOSICIONES|, ASISTENTE, Email Cliente, RUT
  ├─ 3. si falta Email Cliente → nc.find_email_by_rut(rut, DS_CENTRAL)
  ├─ 4. busca asesor en asesores_smtp.json (por nombre normalizado)
  ├─ 5. es.enviar(destinatario=email, ...)   # envía con SMTP o SendGrid
  │     └── BCC automático: Carlos + Andrea (BCC_EXTRA)
  ├─ 6. nc.update_props(page_id, Estado Correo="Enviado")
  └─ 7. nc.update_props(page_id, Fecha Envío=datetime.now())
```

### Flujo detallado

1. El usuario apreta el botón "Enviar Correo RRHH" en una fila de RRHH JUNIO 2026.
2. Notion envía un POST a `https://<backend>/webhook/rrhh` con:
   ```json
   {
     "source": { "type": "button", "page_id": "39512147-..." },
     "data": {
       "Rut": "...",
       "CLIENTE": "...",
       "Email Cliente": "..."
     }
   }
   ```
3. `app.py` recibe el webhook, valida el secreto (R4), extrae el `page_id` (de `source.page_id`) o el RUT.
4. Si viene UUID válido → lo usa directo; si no → busca la fila por RUT en RRHH JUNIO 2026.
5. `handlers/rrhh.py` lee la fila completa por API (`nc.get_page`), extrae las propiedades.
6. Si `Email Cliente` está vacío y hay `RUT` → busca el email en la base central (sandbox `General Customers Data - AuditAI`) filtrando por RUT.
7. Determina el **ASISTENTE** (select) → lo normaliza → busca en `asesores_smtp.json` por `nombre_norm`.
   - Si el asistente no está en el JSON, usa `EMAIL_FROM` como fallback.
8. Compone el correo con la plantilla `rrhh_email.html`/`.txt`.
9. Envía por SendGrid (si hay `SENDGRID_API_KEY`) o SMTP Gmail (App Password del asesor).
10. Escribe `Estado Correo = "Enviado"` y `Fecha Envío = now()`.
11. Responde `{"ok": true, "remitente": "..."}`.

---

## §4 · El correo: contenido exacto

### Asunto

```
Imposiciones {mes} {año}- {CLIENTE}
```

Ejemplos:
- `Imposiciones Junio 2026- SERV. PROFESIONALES ESTETICA`
- `Imposiciones Junio 2026- FUNDACION`

### Cuerpo HTML (misma estructura visual que F29)

Mismo layout: tabla de 600px, fondo `#f2f4f8`, encabezado con logo GCP inline (CID), colores navy `#0B1F3A`.

```
┌──────────────────────────────────┐
│  [LOGO GCP]                      │
├──────────────────────────────────┤
│                                  │
│  Estimado/a {CLIENTE}:           │
│                                  │
│  Por medio de la presente        │
│  informo el monto a pagar por    │
│  concepto de imposiciones del    │
│  mes de {mes} {año}.             │
│                                  │
│  ┌──────────────────────────┐    │
│  │  IMPOSICIONES             │    │
│  │  ${monto_formateado}.-    │    │
│  └──────────────────────────┘    │
│                                  │
│  Plazo hasta {día_semana}        │
│  {día_nº} de {mes_siguiente}     │
│  a las 13.45 horas.              │
│                                  │
│  Saludos cordiales,              │
│  [Firma del asesor]              │
│                                  │
├──────────────────────────────────┤
│  Pie de confidencialidad         │
└──────────────────────────────────┘
```

### Cuerpo texto plano

```
Por medio de la presente informo el monto a pagar por concepto de
imposiciones del mes de {mes} {año}.

Plazo hasta {día_semana} {día_nº} de {mes_siguiente} a las 13.45 horas.
Total a pagar $ {monto_formateado}.-

Saludos cordiales,
{asesor}
GCP · Asesoría Contable
```

### Fecha límite: cálculo

**Regla:** día **13 del mes SIGUIENTE** al período. Si ese día no es hábil (fin de semana o feriado chileno), se traslada al **siguiente día hábil**. Siempre a las **13:45 horas**.

Ejemplo:
- Junio 2026 → mes siguiente = Julio → 13-jul-2026 → lunes (hábil) → **lunes 13 de julio a las 13.45 horas**.
- Si 13 cae sábado → se pasa a lunes 15.

**Implementación:** se crea una función `fecha_limite_rrhh(periodo)` en `email_sender.py` que replica `fecha_limite()` pero con día 13 en vez de 20. Reutiliza `_es_habil()` y `FERIADOS_CL`.

```python
def fecha_limite_rrhh(periodo: str) -> datetime.date | None:
    """'Junio 2026' → día 13 del mes SIGUIENTE; si no es hábil,
    se traslada al siguiente día hábil. Siempre a las 13:45."""
    p = periodo.strip().lower().split()
    mes = next((_MESES[x] for x in p if x in _MESES), None)
    anio = next((int(x) for x in p if x.isdigit() and len(x) == 4), None)
    if not mes or not anio:
        return None
    m2, a2 = (mes + 1, anio) if mes < 12 else (1, anio + 1)
    d = datetime.date(a2, m2, 13)
    while not _es_habil(d):
        d += datetime.timedelta(days=1)
    return d
```

### Variables de la plantilla

| Marcador | De dónde sale | Ejemplo |
|----------|---------------|---------|
| `{{nombre_cliente}}` | columna `CLIENTE` | `SERV. PROFESIONALES ESTETICA` |
| `{{periodo}}` | derivado del mes de la página (ej. "Junio 2026") | `Junio 2026` |
| `{{monto}}` | columna `MONTO IMPOSICIONES\|` → CLP | `$15.474.109` |
| `{{monto_sin_formato}}` | valor numérico plano (para el texto) | `15474109` |
| `{{titulo_resultado}}` | fijo: `"Imposiciones"` | `Imposiciones` |
| `{{bloque_fecha_limite}}` | calculado con `fecha_limite_rrhh()` | HTML |
| `{{linea_fecha_limite}}` | idem en texto plano | `Plazo hasta lunes 13 de julio a las 13.45 horas.` |
| `{{fecha_limite_larga}}` | fecha formateada | `lunes 13 de julio` |
| `{{asesor}}` | columna `ASISTENTE` → nombre en `asesores_smtp.json` | `Seba` |
| `{{contacto_email}}` | config del backend | `contacto@gcp.cl` |

---

## §5 · Código a implementar

### 5.1 · `handlers/rrhh.py` — handler completo

Crear el archivo `notion_automation/handlers/rrhh.py`:

```python
"""Handler del botón "Enviar Correo RRHH" para la página RRHH JUNIO 2026.
Sigue el patrón de handlers/f29.py pero con su propia lógica de composición
y fecha límite (13 del mes siguiente, no 20)."""
from __future__ import annotations
import os
import sys
import logging
from datetime import datetime
import notion_client as nc
import email_sender as es

log = logging.getLogger("auditai")

# Data source de RRHH JUNIO 2026
DS_ID = "9c512147-b3ea-8256-a570-871254c13b3d"

# Data source de la base central (sandbox) para lookup de email
DS_CENTRAL = "4ff12147-b3ea-82f4-98dd-072067524cdc"

# Mapeo de columnas de RRHH → claves internas
CLIENTE = "CLIENTE"
ASISTENTE = "ASISTENTE"
MONTO = "MONTO IMPOSICIONES|"
RUT = "RUT"
EMAIL_CLIENTE = "Email Cliente"

# Columnas de write-back
STATUS_COL = "Estado Correo"
STATUS_ENVIADO = "Enviado"
FECHA_COL = "Fecha Envío"

# Nombre de la plantilla (sin extensión)
TEMPLATE = "rrhh_email"


def _buscar_email_en_central(rut: str) -> str | None:
    """Busca el email de un cliente en la base central por RUT.
    Útil cuando la fila de RRHH no tiene Email Cliente poblado."""
    body = {
        "filter": {
            "property": "RUT",
            "rich_text": {"equals": rut},
        },
        "page_size": 3,
    }
    results = nc.query_data_source(DS_CENTRAL, body)
    if not results:
        return None
    props = results[0].get("properties", {})
    # Intentar varias columnas donde puede estar el email
    for col in ("email", "Email", "e-mail"):
        prop = props.get(col, {})
        val = nc.plain(prop)
        if val:
            return val
    return None


def procesar(page_id: str) -> dict:
    """Lee la fila de RRHH, envía el correo y escribe el status.
    Devuelve {'ok': bool, 'remitente': str, 'motivo': str (si falla)}."""
    page = nc.get_page(page_id)
    props = page["properties"]

    nombre = nc.plain(props.get(CLIENTE, {}))
    monto_str = nc.plain(props.get(MONTO, {}))
    rut = nc.plain(props.get(RUT, {}))
    email = nc.plain(props.get(EMAIL_CLIENTE, {}))
    asistente_raw = nc.plain_select(props.get(ASISTENTE, {}))

    log.info("page_id=%s cliente=%r asistente=%r monto_present=%s email_propio=%s rut_present=%s",
             page_id, nombre, asistente_raw, bool(monto_str), bool(email), bool(rut))

    # Si no hay email propio, buscar en base central por RUT
    if not email and rut:
        encontrado = _buscar_email_en_central(rut)
        if encontrado:
            email = encontrado
            log.info("email recuperado desde base central · page_id=%s", page_id)

    if not email:
        return {"ok": False, "motivo": "fila sin Email (ni columna Email Cliente ni lookup por RUT)"}

    if not nombre:
        return {"ok": False, "motivo": "fila sin CLIENTE (necesario para el asunto y cuerpo)"}

    # Determinar el mes del período (hardcoded o desde la página)
    # Opción A: extraer del título de la base parent (ej. "RRHH JUNIO 2026" → "Junio 2026")
    mes = nc.derivar_month_desde_base(page)
    if not mes:
        # Fallback: mes hardcodeado (para prototipo, luego se automatiza como en F29)
        mes = "Junio 2026"  # TODO: reemplazar con bulk-set o derivación automática

    # Asunto dinámico
    asunto = f"Imposiciones {mes}- {nombre}"

    try:
        remitente = es.enviar(
            destinatario=email,
            nombre=nombre,
            mes=mes,
            monto=monto_str or "0",
            nombre_asesor=asistente_raw,
            # RRHH no usa honorarios, info adicional ni adjuntos
            honorarios="",
            info_valor="",
            info_motivo="",
            msg_adjuntos="",
            adjuntos=None,
            template=TEMPLATE,  # parámetro nuevo para elegir plantilla
            asunto=asunto,      # parámetro nuevo para asunto dinámico
        )
        log.info("correo RRHH enviado OK · page_id=%s remitente=%s", page_id, remitente)
    except ValueError as exc:
        log.error("error envio RRHH · page_id=%s · %s", page_id, exc)
        return {"ok": False, "motivo": str(exc)}
    except Exception as exc:
        log.error("error SMTP RRHH · page_id=%s · %s", page_id, exc)
        return {"ok": False, "motivo": f"error SMTP: {exc}"}

    # Write-back: Estado Correo + Fecha Envío
    now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
    updates = {
        STATUS_COL: {"status": {"name": STATUS_ENVIADO}},
        FECHA_COL: {"date": {"start": now_iso}},
    }
    try:
        nc.update_props(page_id, updates)
        log.info("status+ fecha actualizados · page_id=%s", page_id)
    except Exception as exc:
        log.warning("no se pudo actualizar status/fecha · page_id=%s · %s", page_id, exc)

    return {"ok": True, "remitente": remitente}
```

### 5.2 · Modificaciones a `email_sender.py`

Agregar al archivo existente:

1. **Función `fecha_limite_rrhh()`** (junto a la `fecha_limite()` existente):

```python
def fecha_limite_rrhh(periodo: str) -> datetime.date | None:
    """'Junio 2026' → día 13 del mes SIGUIENTE; si no es hábil,
    se traslada al siguiente día hábil."""
    p = periodo.strip().lower().split()
    mes = next((_MESES[x] for x in p if x in _MESES), None)
    anio = next((int(x) for x in p if x.isdigit() and len(x) == 4), None)
    if not mes or not anio:
        return None
    m2, a2 = (mes + 1, anio) if mes < 12 else (1, anio + 1)
    d = datetime.date(a2, m2, 13)
    while not _es_habil(d):
        d += datetime.timedelta(days=1)
    return d
```

2. Modificar la función `enviar()` para aceptar `template` y `asunto` como parámetros opcionales:

```python
def enviar(
    destinatario: str,
    nombre: str,
    mes: str,
    monto: str,
    nombre_asesor: str = "",
    honorarios: str = "",
    info_valor: str = "",
    info_motivo: str = "",
    msg_adjuntos: str = "",
    adjuntos: list | None = None,
    contacto: str | None = None,
    logo_url: str | None = None,
    template: str = "f29_email",    # 🆕 nombre de la plantilla
    asunto: str | None = None,       # 🆕 asunto dinámico (None = usar ASUNTO_BASE)
) -> str:
```

Y en la sección de renderizado, cargar la plantilla según `template`:

```python
    # 🆕 Cargar plantilla según el parámetro template
    html_path = TEMPLATES / f"{template}.html"
    txt_path = TEMPLATES / f"{template}.txt"
    # Fallback a f29_email si la plantilla no existe
    if not html_path.is_file():
        html_path = TEMPLATES / "f29_email.html"
    if not txt_path.is_file():
        txt_path = TEMPLATES / "f29_email.txt"
    html_src = html_path.read_text(encoding="utf-8")
    txt_src = txt_path.read_text(encoding="utf-8")
```

Y en la sección del asunto, usar el parámetro si se proporciona:

```python
    # 🆕 Asunto: si se pasa asunto explícito, usarlo; si no, el dinámico por mes
    if asunto:
        asunto_final = asunto
    else:
        mes_nombre = _mes_nombre(mes)
        asunto_final = f"{ASUNTO_BASE} {mes_nombre}" if mes_nombre else ASUNTO_BASE
```

### 5.3 · `email_templates/rrhh_email.html` — plantilla HTML

Crear `notion_automation/email_templates/rrhh_email.html`:

```html
<!--
  Plantilla del correo RRHH · Imposiciones · AuditAI / GCP
  Se personaliza por cliente y período reemplazando {{...}}.
  Misma estructura visual que f29_email.html pero con contenido específico de imposiciones.
-->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0;padding:0;background:#f2f4f8;">
  <tr>
    <td align="center" style="padding:24px 12px;">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:600px;max-width:100%;background:#ffffff;border-radius:14px;overflow:hidden;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#16202e;box-shadow:0 6px 18px rgba(11,31,58,.08);">

        <!-- Encabezado con logo GCP -->
        <tr>
          <td style="background:#ffffff;padding:18px 28px;border-bottom:3px solid #0B1F3A;">
            <img src="cid:logo-gcp" alt="GCP · Audit Tax and Consulting" height="46" border="0" style="height:46px;width:auto;display:block;border:none;outline:none;">
          </td>
        </tr>

        <!-- Cuerpo -->
        <tr>
          <td style="padding:30px 28px 8px 28px;">
            <p style="margin:0 0 16px 0;font-size:15px;line-height:1.6;">Estimado/a <b>{{nombre_cliente}}</b>:</p>

            <p style="margin:0 0 18px 0;font-size:15px;line-height:1.6;color:#3a4658;">
              Por medio de la presente informo el monto a pagar por concepto de
              <b>imposiciones</b> del mes de <b>{{periodo}}</b>.
            </p>

            <!-- Tarjeta del monto -->
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 18px 0;">
              <tr>
                <td style="background:#0B1F3A;border-radius:14px;padding:28px 30px;">
                  <div style="font-size:13px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#8fb4ee;margin-bottom:10px;">{{titulo_resultado}}</div>
                  <div style="font-size:52px;font-weight:800;color:#ffffff;font-variant-numeric:tabular-nums;line-height:1;">{{monto}}</div>
                </td>
              </tr>
            </table>

            <!-- Fecha límite -->
            {{bloque_fecha_limite}}

            <!-- Cierre -->
            <p style="margin:0 0 8px 0;font-size:14px;line-height:1.6;color:#3a4658;">Saludos cordiales,</p>
            {{bloque_firma}}
          </td>
        </tr>

        <!-- Pie -->
        <tr>
          <td style="padding:18px 28px 26px 28px;border-top:1px solid #e5eaf2;">
            <p style="margin:0;font-size:12px;line-height:1.6;color:#8593a8;">
              Este correo y su contenido son confidenciales y están dirigidos exclusivamente a
              <b>{{nombre_cliente}}</b>. El monto informado corresponde al período <b>{{periodo}}</b>.
            </p>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>
```

### 5.4 · `email_templates/rrhh_email.txt` — plantilla texto plano

Crear `notion_automation/email_templates/rrhh_email.txt`:

```
Asunto: Imposiciones {{periodo}}- {{nombre_cliente}}

Estimado/a {{nombre_cliente}}:

Por medio de la presente informo el monto a pagar por concepto de
imposiciones del mes de {{periodo}}.

Total a pagar {{monto}}.-
{{linea_fecha_limite}}

Saludos cordiales,
{{asesor}}
GCP · Asesoría Contable
```

### 5.5 · Endpoint en `app.py`

Agregar al archivo `notion_automation/app.py`:

```python
import handlers.rrhh as rrhh_handler

@app.post("/webhook/rrhh")
def webhook_rrhh():
    """Webhook del botón 'Enviar Correo RRHH' en RRHH JUNIO 2026."""
    return _procesar_webhook_generico(rrhh_handler.procesar, "RRHH")
```

Donde `_procesar_webhook_generico` es una función extraída del `enviar_f29()` actual que centraliza la lógica común (validación de secreto, extracción de page_id/RUT, búsqueda por RUT):

```python
def _procesar_webhook_generico(handler, nombre_handler: str):
    """Lógica común para todos los webhooks de botones Notion.
    - Valida X-AuditAI-Secret
    - Extrae page_id o RUT del payload
    - Llama al handler específico con el page_id
    handler: función que recibe (page_id) -> dict
    """
    tiene_secreto = bool(request.headers.get("X-AuditAI-Secret"))
    log.info("request recibida · path=%s · tiene_secreto=%s", request.path, tiene_secreto)

    secreto_esperado = os.environ.get("WEBHOOK_SECRET", "")
    if secreto_esperado:
        if request.headers.get("X-AuditAI-Secret") != secreto_esperado:
            log.warning("secreto invalido · path=%s · 401", request.path)
            abort(401)

    data = request.get_json(force=True, silent=True) or {}
    log.info("estructura payload %s: %s", nombre_handler, _estructura(data))

    ident, ruta = _buscar_clave(data, ["page_id"])
    if not ident:
        ident, ruta = _buscar_clave(data, ["Rut", "rut", "RUT"])
    log.info("identificador en ruta=%r (valor no se loguea)", ruta)

    if not ident:
        abort(400, f"no se encontro page_id ni Rut en el payload ({nombre_handler})")

    if _es_uuid(ident):
        page_id = ident
        log.info("usando page_id directo · %s", nombre_handler)
    else:
        # Buscar en el data source correspondiente
        if nombre_handler == "RRHH":
            from handlers.rrhh import DS_ID as DS
            page_id = nc.find_page_by_rut_generico(ident, DS, "RUT")
        else:
            page_id = nc.find_page_by_rut(ident)
        if not page_id:
            log.warning("RUT no encontrado · %s", nombre_handler)
            abort(404, f"no se encontro fila con ese Rut en {nombre_handler}")

    resultado = handler(page_id)
    return resultado, 200
```

Y agregar a `notion_client.py` una función genérica de búsqueda:

```python
def find_page_by_rut_generico(rut: str, ds_id: str, prop_rut: str = "Rut") -> str | None:
    """Busca el page_id por RUT en un data source genérico.
    ds_id: data source ID de la base.
    prop_rut: nombre de la propiedad que contiene el RUT (title o rich_text)."""
    body = {
        "filter": {
            "property": prop_rut,
            "rich_text": {"equals": rut},
        },
        "page_size": 5,
    }
    results = query_data_source(ds_id, body)
    if not results:
        return None
    return results[0]["id"]
```

El endpoint existente `/enviar-f29` se mantiene sin cambios (o se migra a la nueva función genérica como refactor opcional).

---

## §6 · Configuración del botón en Notion (lo hace el usuario)

1. Abrir la base **RRHH JUNIO 2026** como tabla.
2. Click en **`+`** al final de las columnas → **New property** → tipo **Button** → nombrarla **`Enviar Correo RRHH`**.
3. En la config del botón → **Add step** → elegir **Send webhook**.
4. **URL:** `https://<url-del-backend>/webhook/rrhh`
   - Prototipo local: `https://xxxx.ngrok-free.app/webhook/rrhh`
   - Producción: URL estable de Render
5. **Method:** POST (único soportado).
6. **Encabezado personalizado:**
   - **Key:** `X-AuditAI-Secret`
   - **Value:** el mismo `WEBHOOK_SECRET` del F29
7. **Contenido (body):** agregar propiedades seleccionables:
   - **`RUT`** — identificación de la fila
   - **`CLIENTE`** — validación extra
   - **`Email Cliente`** — validación extra
8. Guardar.

---

## §7 · Prueba end-to-end (criterio de aceptación)

### 7.1 · Preparación

1. Crear una fila de prueba en RRHH JUNIO 2026: `ZZ_TEST AuditAI RRHH`.
2. Poblar: `RUT` = un RUT ficticio (ej. `12345678-9`), `CLIENTE` = `ZZ_TEST AuditAI RRHH`, `MONTO IMPOSICIONES|` = `15474109`, `ASISTENTE` = un asesor con App Password (Sebastián, Constanza o Carlos), `Email Cliente` = una dirección real verificable.
3. Tener el backend corriendo (`python app.py`) y expuesto vía ngrok.

### 7.2 · Ejecución

1. Apretar el botón `Enviar Correo RRHH` en la fila de prueba.
2. Verificar en el log del backend:
   - `request recibida · path=/webhook/rrhh · tiene_secreto=True`
   - `identificador en ruta=...`
   - `correo RRHH enviado OK · page_id=... remitente=...`
3. Verificar que llegó el correo con:
   - Asunto: `Imposiciones Junio 2026- ZZ_TEST AuditAI RRHH`
   - Cuerpo: "Por medio de la presente informo el monto a pagar por concepto de imposiciones del mes de Junio 2026."
   - Total: `$15.474.109.-`
   - Fecha límite correcta
   - Logo GCP visible
   - Firma del asesor visible
4. Verificar en Notion que `Estado Correo` = "Enviado" y `Fecha Envío` tiene fecha.
5. Probar caso borde: fila **sin `Email Cliente`** pero con RUT → debe buscar en base central y enviar igual.

### 7.3 · Depuración

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| `400 no se encontro page_id ni Rut` | Payload de Notion cambió de formato | Verificar estructura con `_estructura()` en el log |
| `404 no se encontro fila con ese Rut` | RUT no matchea exactamente en RRHH | Verificar espacios, guión, mayúsculas |
| `fila sin Email` | No hay Email Cliente ni lookup por RUT | Poblar Email Cliente o verificar RUT en base central |
| error SMTP: asesor pendiente | El asistente está marcado `pendiente: true` | Cambiar a otro asesor o pedir App Password |
| error SMTP: Authentication failed | App Password incorrecta | Regenerar en Gmail y actualizar `asesores_smtp.json` |

---

## §8 · Checklist de implementación

### Fase 0 — Código base (handler + template)

- [ ] Crear `notion_automation/handlers/__init__.py` (vacio)
- [ ] Crear `notion_automation/handlers/rrhh.py` con:
  - [ ] Constantes: `DS_ID`, `DS_CENTRAL`, mapeo de columnas, `STATUS_COL`, `TEMPLATE`
  - [ ] Función `_buscar_email_en_central(rut)`
  - [ ] Función `procesar(page_id)` con ciclo completo (leer → validar → enviar → write-back)
- [ ] Agregar `fecha_limite_rrhh()` a `email_sender.py`
- [ ] Modificar `enviar()` en `email_sender.py` para aceptar `template` y `asunto` como parámetros
- [ ] Crear `email_templates/rrhh_email.html` (plantilla HTML)
- [ ] Crear `email_templates/rrhh_email.txt` (plantilla texto plano)
- [ ] Agregar `_procesar_webhook_generico()` a `app.py`
- [ ] Agregar endpoint `POST /webhook/rrhh` en `app.py`
- [ ] Agregar `find_page_by_rut_generico()` a `notion_client.py`

### Fase 1 — Notion (columnas + botón)

- [ ] Backup de RRHH JUNIO 2026 (export CSV antes de tocar — R1)
- [ ] Usuario crea columna `Email Cliente` (email) en RRHH JUNIO 2026
- [ ] Usuario crea columna `Estado Correo` (status) en RRHH JUNIO 2026
- [ ] Usuario crea columna `Fecha Envío` (date) en RRHH JUNIO 2026
- [ ] Usuario crea columna botón `Enviar Correo RRHH` (button) en RRHH JUNIO 2026
- [ ] Usuario configura el webhook del botón (URL + header + body)

### Fase 2 — Prueba E2E

- [ ] Crear fila de prueba `ZZ_TEST AuditAI RRHH` con datos poblados
- [ ] Backend corriendo (`python app.py`)
- [ ] Túnel ngrok activo
- [ ] Apretar botón → verificar log del backend
- [ ] Verificar correo recibido (asunto, cuerpo, monto, fecha, logo, firma)
- [ ] Verificar write-back en Notion (Estado Correo = "Enviado", Fecha Envío poblada)
- [ ] Probar caso borde: fila sin `Email Cliente` con RUT → verificar lookup
- [ ] Probar caso borde: fila sin RUT ni Email → verificar error controlado

### Fase 3 — Integración y limpieza

- [ ] Verificar que el endpoint `/enviar-f29` (F29) sigue funcionando (no se rompió)
- [ ] Verificar que los BCC a Carlos + Andrea se envían correctamente
- [ ] Documentar cualquier ajuste encontrado durante la implementación
- [ ] Actualizar [`11-checklist-maestro.md`](11-checklist-maestro.md) marcando N.5 como completado
- [ ] Actualizar [`02-estado-del-proyecto.md`](02-estado-del-proyecto.md) si corresponde

---

## §9 · Contingencias

| Situación | Acción |
|-----------|--------|
| **La columna `RUT` de RRHH no tiene el RUT esperado** (varias filas vienen con título vacío) | Usar `CLIENTE` como identificador secundario (extractor ya busca `Rut`/`rut`/`RUT`, si no aparece, ampliar a `CLIENTE`) |
| **No hay `ASISTENTE` en la fila** (select vacío) | El backend debe caer a `EMAIL_FROM` como remitente fallback (ya implementado en `email_sender.py`) |
| **El lookup en base central no encuentra el email** (RUT no existe en sandbox) | El error debe ser claro: "fila sin Email (ni columna Email Cliente ni lookup por RUT)". El usuario debe poblar `Email Cliente` a mano. |
| **SendGrid rechaza el remitente** (el ASISTENTE no está verificado en SendGrid) | Si el ASISTENTE no está verificado como Single Sender, SendGrid responde 403. Solución: agregar el email a SendGrid o usar SMTP Gmail (App Password). |
| **La plantilla `rrhh_email.html` no se encuentra** | El fallback debe cargar `f29_email.html` (con los marcadores correctos). No debe romper. |
| **El extractor recursivo no encuentra el RUT** en el payload | Usar `_estructura()` en el log para diagnosticar la forma exacta del payload y ajustar `_buscar_clave`. |

---

**Anterior:** [`24-arquitectura-multi-automatizacion.md`](24-arquitectura-multi-automatizacion.md) · **Volver al** [`README`](README.md)
