# 24 · Arquitectura multi-automatización (F29 + RRHH + Tickets + …)

> **Propósito:** definir una arquitectura **centralizada** que permita automatizar múltiples
> páginas de Notion (cada una con su propio botón, columnas, plantilla de correo y lógica)
> desde **un solo backend**, reutilizando el máximo de componentes comunes.
>
> Aprobado por el usuario el 09-jul-2026 para las 3 páginas:
> - ✅ **Contable** (F29) — ya operativa
> - **RRHH JUNIO 2026** — en implementación
> - **Tickets - Servicios** — planificada (próximo hito)

---

## §0 · Principios

| # | Principio | Detalle |
|---|-----------|---------|
| P1 | **Un backend, N handlers** | `app.py` rutea cada webhook al handler correspondiente. No hay microservicios ni repos separados. |
| P2 | **Cada página = un handler** | `handlers/f29.py`, `handlers/rrhh.py`, `handlers/tickets.py`. Cada uno define qué columnas leer, qué plantilla usar, y qué hacer con los datos. |
| P3 | **Todo lo común se comparte** | `notion_client.py` (API Notion), `email_sender.py` (envío SMTP/SendGrid), `asesores_smtp.json` (credenciales de asesores), `BCC_EXTRA` (copias a Carlos/Andrea). Sin duplicación. |
| P4 | **Cada handler es autocontenido** | Dentro de `handlers/<pagina>.py` vive todo: el mapping de propiedades, el data source ID, la lógica de composición del correo, y el write-back. |
| P5 | **Cada página tiene su plantilla** | `email_templates/f29_email.html`, `rrhh_email.html`, `tickets_email.html`. Misma estructura visual (logo GCP, firma del asesor, colores), pero contenido específico. |

---

## §1 · Estructura del repositorio

```
notion_automation/
├── app.py                        # Router central: POST /webhook/<tipo>
├── notion_client.py              # Helpers API Notion (sin cambios)
├── email_sender.py               # Envío SMTP/SendGrid + BCC_EXTRA (sin cambios)
├── asesores_smtp.json            # Credenciales de asesores (sin cambios)
├── handlers/
│   ├── __init__.py               # (vacio o re-export)
│   ├── base.py                   # 🆕 Clase/métodos comunes a handlers (opcional)
│   ├── f29.py                    # 🔁 Extraído de app.py actual
│   ├── rrhh.py                   # 🆕 Handler para RRHH JUNIO 2026
│   └── tickets.py                # 🆕 Handler para Tickets - Servicios
├── email_templates/
│   ├── f29_email.html / .txt     # (existente)
│   ├── rrhh_email.html / .txt    # 🆕
│   └── tickets_email.html / .txt # 🆕 (para después)
├── firmas/                       # (existente) PNG de firmas de asesores
└── data/                         # volcados (gitignored)
```

### App router (`app.py`)

Cada botón de Notion apunta a un endpoint distinto. El router selecciona el handler según el path:

| Botón en Notion | Endpoint | Handler | Data source Notion |
|---|---|---|---|
| "Enviar Correo F29" | `POST /webhook/f29` | `handlers/f29.procesar()` | Contable Junio (`09b12147-…`) |
| "Enviar Correo RRHH" | `POST /webhook/rrhh` | `handlers/rrhh.procesar()` | RRHH JUNIO 2026 (`9c512147-…`) |
| "Enviar Correo Ticket" | `POST /webhook/tickets` | `handlers/tickets.procesar()` | Tickets - Servicios (`9d312147-…`) |

```python
# app.py (esquema del router)
@app.post("/webhook/f29")
def webhook_f29():
    return _ruteador("f29")

@app.post("/webhook/rrhh")
def webhook_rrhh():
    return _ruteador("rrhh")
```

Cada handler recibe un `page_id` (identificado desde el webhook igual que el F29: por RUT o UUID), lee la fila de su data source, compone su correo con su plantilla, envía y escribe el status de vuelta.

---

## §2 · Patrón de cada handler

```python
# handlers/rrhh.py (estructura canónica)
from __future__ import annotations
import logging
import notion_client as nc
import email_sender as es

log = logging.getLogger("auditai")

# Data source de la página en Notion
DS_ID = "9c512147-b3ea-8256-a570-871254c13b3d"

# Columnas de la página (nombre exacto en Notion → clave interna)
PROPS = {
    "CLIENTE": "CLIENTE",
    "ASISTENTE": "ASISTENTE",
    "MONTO": "MONTO IMPOSICIONES|",
    "RUT": "RUT",
    "EMAIL": "Email Cliente",
}

# Nombre de la columna de status para write-back
STATUS_COL = "Estado Correo"
STATUS_ENVIADO = "Enviado"
TEMPLATE = "rrhh_email"  # -> email_templates/rrhh_email.html / .txt


def procesar(page_id: str) -> dict:
    """Lee la fila, envía el correo, actualiza Status.
    Sigue exactamente el mismo patrón que handlers/f29.py."""
    page = nc.get_page(page_id)
    props = page["properties"]

    # Extraer valores
    nombre = nc.plain(props.get(PROPS["CLIENTE"], {}))
    email = nc.plain(props.get(PROPS["EMAIL"], {}))
    monto = nc.plain(props.get(PROPS["MONTO"], {}))
    rut = nc.plain(props.get(PROPS["RUT"], {}))
    asistente = nc.plain_select(props.get(PROPS["ASISTENTE"], {}))

    # Si no hay Email propio, buscar en base central por RUT
    if not email and rut:
        email = _buscar_email_en_central(rut)

    if not email:
        return {"ok": False, "motivo": "fila sin Email"}

    # Componer y enviar correo (cada handler define su lógica)
    mes = "Junio 2026"  # vendrá de la página o se deriva
    try:
        remitente = es.enviar(
            destinatario=email,
            nombre=nombre,
            mes=mes,
            monto=monto or "0",
            nombre_asesor=asistente,
        )
    except Exception as exc:
        return {"ok": False, "motivo": str(exc)}

    # Write-back del status
    nc.update_props(page_id, {STATUS_COL: {"status": {"name": STATUS_ENVIADO}}})

    return {"ok": True, "remitente": remitente}
```

---

## §3 · Las 3 automatizaciones

### 3.1 · F29 / Contable (✅ operativa)

Base: `Contable Junio` / `Contable <Mes>`
Botón: `Enviar Correo F29`
Handler: `handlers/f29.py`
Template: `f29_email.html` / `f29_email.txt`
Columnas clave: `Customers`, `Email`, `Month`, `Impuestos`, `Honorarios Pendientes`, `Valor-Info adicional`, `Motivo-Info adicional`, `Adviser Accounting`, `Rut`, `Status`
Asunto: `Resumen impuestos {mes}`
Particularidad: fecha límite día 20 del mes siguiente · honorarios con datos de transferencia GCP

### 3.2 · RRHH JUNIO 2026 (🚧 en implementación)

Base: `RRHH JUNIO 2026` (data source `9c512147-…`)
Botón: `Enviar Correo RRHH`
Handler: `handlers/rrhh.py`
Template: `rrhh_email.html` / `rrhh_email.txt`
Columnas clave: `CLIENTE`, `ASISTENTE` (select), `MONTO IMPOSICIONES|`, `IMPUESTO ÚNICO`, `Nº. Trab.`, `RUT`, `Email Cliente` (🆕), `Previred`, `Liquidaciones`, `Estado Correo` (🆕), `Fecha Envío` (🆕)
Asunto: `Imposiciones {mes} {año} - {CLIENTE}`
Cuerpo:
> Por medio de la presente informo el monto a pagar por concepto de imposiciones del mes de {mes} {año}.
> Plazo hasta {día_semana} {día_nº} de {mes_siguiente} a las 13.45 horas.
> Total a pagar $ {monto}.-
Fecha límite: **13 del mes siguiente** (día hábil) a las 13:45, con la misma lógica de feriados chilenos de `email_sender.py`.
Particularidad: si la fila no tiene `Email Cliente`, se busca el email desde la base central `General Customers Data - AuditAI` cruzando por `RUT`.

### 3.3 · Tickets - Servicios (📋 planificado)

Base: `Tickets - Servicios` (data source `9d312147-…`)
Botón: `Enviar Correo Ticket`
Handler: `handlers/tickets.py`
Template: `tickets_email.html` / `tickets_email.txt`
Columnas clave: `Tarea` (title), `Descripción`, `Tipo`, `Asignado`, `Estado`, `Compromiso`, `Fecha prometida`
Estado: pendiente de definición del contenido del correo.

---

## §4 · Cómo agregar una automatización nueva

1. **Crear `handlers/<pagina>.py`** siguiendo el patrón de §2
2. **Crear `email_templates/<pagina>_email.html`** y **`.txt`** con la plantilla del correo
3. **Agregar endpoint en `app.py`**: `POST /webhook/<pagina>` → llama al handler
4. **En Notion:** crear columna tipo Button que apunte a `POST /webhook/<pagina>` con header `X-AuditAI-Secret`
5. **Si hay lookup de email:** la función `_buscar_email_en_central()` en `notion_client.py` cruza RUT contra `General Customers Data - AuditAI`

---

## §5 · ID de data sources (referencia)

| Página | database ID | data source ID |
|--------|-------------|----------------|
| General Customers Data (original — NO tocar) | `1a23f5e4-0223-46a6-9ad5-16ea823b64ba` | `690945e4-220a-48c3-a888-7fe9ae242d55` |
| General Customers Data - AuditAI (sandbox) | `16f12147-b3ea-8354-872b-814f104871b7` | `4ff12147-b3ea-82f4-98dd-072067524cdc` |
| Contable Junio (operativa) | `09b12147-b3ea-8337-a218-87538eab23fc` | `09b12147-b3ea-8337-a218-87538eab23fc` |
| RRHH JUNIO 2026 | `38712147-b3ea-80f9-9484-e0ad99c94a26` | `9c512147-b3ea-8256-a570-871254c13b3d` |
| Tickets - Servicios | `16912147-b3ea-82bc-a491-814729bcca4c` | `9d312147-b3ea-83bf-b111-877c7b24db75` |

---

## §6 · Seguridad (mismas reglas que F29)

- **Webhook autenticado:** mismo `X-AuditAI-Secret` en todos los endpoints
- **Identificación por RUT:** el botón de Notion envía las columnas seleccionables (RUT, Email, nombre); el backend busca el `page_id` por RUT o lo extrae de `source.page_id`
- **Log sin PII:** no se registran emails, montos ni RUT en los logs
- **BCC automático:** Carlos + Andrea reciben copia de todos los correos enviados (definido en `BCC_EXTRA` en `email_sender.py`)

---

**Anterior:** [`23-automatizacion-notion-contable-correo.md`](23-automatizacion-notion-contable-correo.md) · **Volver al** [`README`](README.md)
