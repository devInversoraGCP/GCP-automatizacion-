# Misión: arreglar el correo F29 de AuditAI (4 objetivos) — ✅ COMPLETADA

> **Para:** Claude Opus 4.8 (multimodal)
> **Proyecto:** AuditAI — automatización del correo del Formulario 29 (Chile)
> **Fecha:** 07-jul-2026
> **Estado:** ✅ **Completada (07-jul-2026).** Los 4 objetivos (A logo, B honorarios+info, C firma hardcodeada, D firma del asesor) están resueltos y verificados. Adicionalmente se resolvió el **bug del webhook de Notion** (payload anidado en `data`, no en la raíz) con un extractor recursivo, logrando **E2E exitoso**: botón → webhook → backend → SMTP Gmail → correo + write-back Status. Ver [`docs/dev/23-automatizacion-notion-contable-correo.md`](docs/dev/23-automatizacion-notion-contable-correo.md) §5.3/§5.4/§5.6.
>
> **Contexto:** El backend ya envía correos por SMTP desde la cuenta del asesor. La prueba end-to-end llegó a la bandeja de entrada, pero tenía 4 problemas que había que arreglar. Este documento es **autosuficiente**: contiene el contexto, los 4 objetivos, el código actual y las rutas a las imágenes que tienes que **ver** (eres multimodal).

---

## Contexto del proyecto

AuditAI automatiza el envío del correo del F29 a clientes de la asesoría contable GCP. El flujo:

```
Notion (fila Contable Junio, botón "Enviar F29")
  → HTTP POST (webhook) con {page_id}
  → backend Flask (app.py)
    → lee la fila por API de Notion (notion_client.py)
    → compone el correo con la plantilla (email_sender.py)
    → envía por SMTP de Gmail con la App Password del asesor
    → write-back: Status = "1) Enviado y Pendiente"
  → correo llega al cliente
```

Cada cliente tiene un **asesor asignado** (columna `Adviser Accounting` en Notion). El correo se envía **desde la cuenta Gmail del asesor**, no desde una cuenta genérica. Cada asesor tiene su propia **firma de Gmail** (configurada nativamente en la web de Gmail).

**Reglas de oro (no negociables):**
- 🔒 **Nunca imprimir/loguear/exponer credenciales ni PII** (email, RUT, claves) en outputs, logs o respuestas. Es regla #2 de `AGENTS.md`.
- 📁 **Las credenciales SMTP** viven en `notion_automation/asesores_smtp.json` (gitignored). **No se commitean ni se imprimen.**
- 🇨🇱 **Idioma:** español.
- 🧮 **La IA no calcula montos.** Los montos salen de la columna `Impuestos` de Notion; la IA solo arma el correo.

---

## Los 4 objetivos

### Objetivo A — El logo de GCP se ve mal

**Síntoma:** En el correo de prueba, el logo no se visualiza — se ve código/placeholder roto en lugar de la imagen.

**Causa raíz:** La plantilla `f29_email.html` línea 17 usa `{{logo_url}}` que se reemplaza por `https://gcp.cl/logo.png` (del `.env`), pero **esa URL no existe**. Los clientes de correo (Gmail, Outlook) **bloquean `data:` URIs** por seguridad, así que embeber como base64 tampoco funciona.

**Solución:** Embeber el logo como **inline CID** (Content-ID) en el correo. Es el patrón estándar para imágenes en emails: se adjunta al correo y se referencia por `cid:logo-gcp` en el `<img src=...>`. Gmail lo muestra correctamente.

**Imagen del logo:** `C:\Users\Hp\Documents\AuditAI\LOGO-GCP.png` (42 KB)

### Objetivo B — Faltan los bloques de honorarios e info adicional

**Síntoma:** El correo de prueba no muestra los bloques de:
- **Honorarios de asesoría pendientes** (con monto + datos de transferencia bancaria de GCP)
- **Información adicional** (texto libre, p. ej. remanente)

**Causa raíz:** La fila de prueba `ZZ_TEST AuditAI` en Notion tenía esos campos vacíos. La lógica en `email_sender.py` solo inyecta los bloques si hay datos (correcto), pero **para la prueba hay que llenarlos**.

**Solución (2 partes):**
1. **Llenar los campos** en la fila `ZZ_TEST AuditAI` (page_id `39612147-b3ea-810f-b761-d610a3be1ce3`) en Contable Junio:
   - `Honorarios Pendientes` (number) = `85000`
   - `Info Adicional` (rich_text) = `A su favor queda un remanente de $417.798 que se arrastra al próximo período.`
2. **Reenviar** el correo de prueba y verificar que los bloques aparecen.

**HTML esperado del bloque honorarios** (ya está en `email_sender.py` `_bloque_honorarios()`):
```html
<div style="margin:0 0 18px 0;background:#fff8ec;border:1px solid #f2e2bf;border-left:4px solid #E7A100;border-radius:10px;padding:14px 18px;">
  <div style="font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#9a7400;margin-bottom:3px;">Honorarios de asesoría · pendientes</div>
  <div style="font-size:14px;color:#3a4658;line-height:1.55;">Además, registra <b>honorarios de asesoría pendientes por $85.000</b> por nuestros servicios del mes. Este monto es independiente del impuesto del F29 y se cancela directamente a GCP.</div>
  <div style="margin-top:10px;padding-top:10px;border-top:1px solid #f2e2bf;font-size:13px;color:#3a4658;line-height:1.7;">
    <b>Datos para la transferencia:</b><br>Banco Santander · Cuenta Corriente<br>N° 0-000-8577678-9<br>RUT: 76.976.672-3<br>Razón Social: Inversora GCP Ltda
  </div>
</div>
```

### Objetivo C — Eliminar la firma hardcodeada "Carlos Vergara / contacto@gcp.cl"

**Síntoma:** El correo de prueba muestra al final:
```
Carlos Vergara
Asesoría Contable · GCP
contacto@gcp.cl
```

**Eso es incorrecto.** "Carlos Vergara" es un placeholder que se coló en la vista previa interactiva y **no debería estar hardcodeado**. El asesor real sale de la columna `Adviser Accounting` de Notion (en la prueba era Sebastián Robles).

**Causa raíz:** 
- La plantilla `f29_email.html` (líneas 51-56) tiene un bloque de firma fija con `{{asesor}}` / `GCP · Asesoría Contable` / `{{contacto_email}}`. Eso hay que **eliminarlo** porque la firma va como imagen (Objetivo D).
- La vista previa `preview-correo-f29.html` tiene "Carlos Vergara" hardcodeado en el HTML — es solo metadata de demo, no afecta al correo real, pero conviene arreglarlo.

**Solución:** Eliminar el bloque de firma en texto de la plantilla y reemplazarlo por la **imagen de la firma del asesor** (Objetivo D). Si el asesor no tiene firma PNG configurada, fallback a un texto simple con su nombre (sin "Carlos Vergara" inventado).

### Objetivo D — Integrar la firma real del asesor (pie de página de Gmail)

**Síntoma:** Sebastián Robles tiene una firma nativa en Gmail (con logo, datos de contacto, branding GCP) que aparece automáticamente cuando él envía un correo desde la web/app de Gmail. Pero por SMTP esa firma **no se adjunta** — SMTP envía exactamente el cuerpo que le damos.

**Causa raíz:** La firma nativa de Gmail vive en la configuración web de la cuenta (`Settings → Signature`). SMTP no tiene acceso a esa configuración; es una limitación del protocolo, no algo que se arregle con una tool o action.

**Solución:** Embeber la firma como **imagen inline CID**, igual que el logo. Cada asesor tiene su propio PNG de firma, mapeado en `asesores_smtp.json`.

**Imagen de la firma de Sebastián:** `C:\Users\Hp\Documents\AuditAI\pie de pagina-Robles.png` (100 KB)

**Estructura del mapeo en `asesores_smtp.json`** (agregar campo `firma_png` por asesor):
```json
"sebastianrobles@inversoragcp.com": {
  "password": "<App Password>",
  "nombre": "Sebastián Robles",
  "firma_png": "C:\\Users\\Hp\\Documents\\AuditAI\\pie de pagina-Robles.png",
  ...
}
```

**Si un asesor no tiene `firma_png`**, fallback a texto simple con su nombre (sin inventar "Carlos Vergara").

---

## Archivos relevantes (rutas absolutas)

| Archivo | Rol | Qué hacer |
|---|---|---|
| `C:\Users\Hp\Documents\AuditAI\LOGO-GCP.png` | Logo GCP (42 KB) | **Ver esta imagen** — es el logo que debe ir en el encabezado |
| `C:\Users\Hp\Documents\AuditAI\pie de pagina-Robles.png` | Firma de Sebastián (100 KB) | **Ver esta imagen** — es la firma que debe ir al pie, reemplazando el texto "Carlos Vergara" |
| `C:\Users\Hp\Documents\AuditAI\notion_automation\email_templates\f29_email.html` | Plantilla HTML del correo | **Modificar** — eliminar la firma en texto (líneas 51-56), dejar el `<img src="{{logo_cid}}">` y agregar `<img src="{{firma_cid}}">` |
| `C:\Users\Hp\Documents\AuditAI\notion_automation\email_templates\f29_email.txt` | Plantilla texto plano (respaldo) | **Modificar** — eliminar la firma en texto, dejar solo el nombre del asesor |
| `C:\Users\Hp\Documents\AuditAI\notion_automation\email_sender.py` | Lógica de envío SMTP | **Modificar** — embeber logo + firma como inline CID con `email.mime.image.MIMEImage` |
| `C:\Users\Hp\Documents\AuditAI\notion_automation\asesores_smtp.json` | Credenciales + config por asesor | **Modificar** — agregar campo `firma_png` por asesor |
| `C:\Users\Hp\Documents\AuditAI\notion_automation\app.py` | Backend Flask (endpoint /enviar-f29) | No tocar (ya funciona) |
| `C:\Users\Hp\Documents\AuditAI\notion_automation\notion_client.py` | Helpers REST de Notion | No tocar (ya funciona) |
| `C:\Users\Hp\Documents\AuditAI\notion_automation\email_templates\preview-correo-f29.html` | Vista previa interactiva | **Modificar** — quitar "Carlos Vergara" hardcodeado, poner imagen de firma |
| `C:\Users\Hp\Documents\AuditAI\notion_automation\.env` | Secretos (gitignored) | No commitear — tiene `NOTION_TOKEN` y `WEBHOOK_SECRET` |

**IDs de Notion necesarios:**
- Contable Junio (base): `39612147-b3ea-80e7-98e6-dbe3de45b76e`
- Contable Junio (data source): `09b12147-b3ea-8337-a218-87538eab23fc`
- Fila de prueba `ZZ_TEST AuditAI` (page_id): `39612147-b3ea-810f-b761-d610a3be1ce3`
- User ID de Sebastián Robles en Notion: `91e6795d-f1aa-40b0-a748-4c3b88fb3f82`

---

## Código actual (para contexto)

### `email_sender.py` (lógica de envío SMTP)

```python
"""Compone y envía el correo del F29 via SMTP de Gmail.
El remitente es el asesor asignado al cliente, no una cuenta genérica.
Cada asesor envía desde su propio Gmail con su App Password (ver asesores_smtp.json)."""
from __future__ import annotations
import os, smtplib, ssl, datetime, json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

TEMPLATES = Path(__file__).parent / "email_templates"
ASESORES_JSON = Path(__file__).parent / "asesores_smtp.json"
ASUNTO = "Asesoria Honorario"

# ... (FERIADOS_CL, BANCO_GCP_HTML, BANCO_GCP_TXT, _MESES, etc.) ...

def _norm(s: str) -> str:
    import unicodedata
    s = (s or "").lower().strip()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return " ".join(s.split())

def _buscar_asesor_por_nombre(nombre_asesor: str) -> dict | None:
    data = _cargar_asesores()
    norm = _norm(nombre_asesor)
    for email, info in data.items():
        if email.startswith("_"):
            continue
        if info.get("nombre_norm") == norm:
            return {"email": email, **info}
    return None

# ... (clp, fecha_limite, _variantes, _bloque_fecha, _bloque_honorarios, _bloque_info, render) ...

def enviar(destinatario, nombre, mes, monto, nombre_asesor="", honorarios="", info_adicional="", contacto=None, logo_url=None):
    contacto = contacto or os.environ.get("EMAIL_CONTACTO", "contacto@gcp.cl")
    logo_url = logo_url or os.environ.get("LOGO_URL", "https://gcp.cl/logo.png")

    # Determinar remitente: el asesor del cliente, o fallback a EMAIL_FROM
    remitente_email = os.environ.get("EMAIL_FROM", "notificaciones@inversoragcp.com")
    remitente_pass = None
    asesor_firma = nombre_asesor or "Equipo GCP"

    if nombre_asesor:
        asesor_info = _buscar_asesor_por_nombre(nombre_asesor)
        if asesor_info and asesor_info.get("password") and not asesor_info.get("pendiente"):
            remitente_email = asesor_info["email"]
            remitente_pass = asesor_info["password"]
            asesor_firma = asesor_info.get("nombre", nombre_asesor)
        elif asesor_info and asesor_info.get("pendiente"):
            raise ValueError(f"Asesor '{nombre_asesor}' no tiene App Password aún.")

    if not remitente_pass:
        raise ValueError(f"No se encontró contraseña SMTP para {remitente_email}.")

    html, txt = render(nombre, mes, monto, asesor_firma, contacto, logo_url, honorarios, info_adicional)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = ASUNTO
    msg["From"] = f"{asesor_firma} · GCP <{remitente_email}>"
    msg["To"] = destinatario
    msg.attach(MIMEText(txt, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    pass_clean = remitente_pass.replace(" ", "")
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=30) as server:
        server.login(remitente_email, pass_clean)
        server.sendmail(remitente_email, [destinatario], msg.as_string())

    return remitente_email
```

### `f29_email.html` (plantilla — la parte del final que hay que cambiar)

```html
            <!-- Líneas 51-56 — ELIMINAR este bloque (Objetivo C) -->
            <p style="margin:0 0 4px 0;font-size:14px;line-height:1.6;color:#3a4658;">Saludos cordiales,</p>
            <p style="margin:0 0 24px 0;font-size:14px;line-height:1.5;">
              <b>{{asesor}}</b><br/>
              <span style="color:#5a6b82;">GCP · Asesoría Contable</span><br/>
              <a href="mailto:{{contacto_email}}" style="color:#2f5bbf;text-decoration:none;">{{contacto_email}}</a>
            </p>
```

**Reemplazar por** (Objetivo D — imagen de la firma del asesor):
```html
            <p style="margin:0 0 4px 0;font-size:14px;line-height:1.6;color:#3a4658;">Saludos cordiales,</p>
            <!-- Firma del asesor (imagen inline CID). Si no hay firma_png, fallback a texto. -->
            {{bloque_firma}}
```

### `asesores_smtp.json` (estructura — agregar `firma_png`)

```json
{
  "sebastianrobles@inversoragcp.com": {
    "password": "<App Password>",
    "nombre": "Sebastián Robles",
    "nombre_norm": "sebastian robles",
    "tipo": "workspace",
    "pendiente": false,
    "app_password": true,
    "firma_png": "C:\\Users\\Hp\\Documents\\AuditAI\\pie de pagina-Robles.png",
    "generada": "2026-07-07"
  }
}
```

---

## Cómo embeber imágenes inline CID (patrón estándar)

El patrón para que Gmail muestre imágenes correctamente (sin bloquearlas) es **inline CID**:

```python
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart

# 1. Crear el mensaje como "related" (no "alternative") para poder anexar imágenes
msg = MIMEMultipart("related")
msg["Subject"] = "Asesoria Honorario"
msg["From"] = "Sebastián Robles · GCP <sebastianrobles@inversoragcp.com>"
msg["To"] = destinatario

# 2. El cuerpo HTML va dentro de un "alternative" que cuelga del "related"
alt = MIMEMultipart("alternative")
alt.attach(MIMEText(txt, "plain", "utf-8"))
alt.attach(MIMEText(html, "html", "utf-8"))
msg.attach(alt)

# 3. Adjuntar el logo con Content-ID "logo-gcp"
with open("LOGO-GCP.png", "rb") as f:
    img = MIMEImage(f.read())
img.add_header("Content-ID", "<logo-gcp>")
img.add_header("Content-Disposition", "inline", filename="logo-gcp.png")
msg.attach(img)

# 4. Adjuntar la firma con Content-ID "firma-asesor"
with open("pie de pagina-Robles.png", "rb") as f:
    firma = MIMEImage(f.read())
firma.add_header("Content-ID", "<firma-asesor>")
firma.add_header("Content-Disposition", "inline", filename="firma-asesor.png")
msg.attach(firma)

# 5. En el HTML, referenciar por cid:
# <img src="cid:logo-gcp" ...>
# <img src="cid:firma-asesor" ...>
```

⚠️ **Importante:** El `MIMEMultipart` raíz debe ser `"related"` (no `"alternative"`) para que las imágenes inline se asocien al cuerpo. Si se queda como `"alternative"`, Gmail puede mostrar las imágenes como adjuntos sueltos en vez de inline.

---

## Pasos sugeridos (orden recomendado)

1. **Ver las 2 imágenes** (`LOGO-GCP.png` y `pie de pagina-Robles.png`) para entender qué representan y qué dimensiones tienen.
2. **Modificar `asesores_smtp.json`** — agregar campo `firma_png` a Sebastián con la ruta absoluta. No tocar las contraseñas.
3. **Modificar `email_sender.py`** — 
   - Cambiar `MIMEMultipart("alternative")` → `MIMEMultipart("related")` con un `alternative` anidado.
   - Cargar y adjuntar el logo con `Content-ID: <logo-gcp>`.
   - Cargar y adjuntar la firma del asesor (si tiene `firma_png`) con `Content-ID: <firma-asesor>`.
   - Reemplazar `{{logo_url}}` por `cid:logo-gcp` en el HTML final.
   - Construir `{{bloque_firma}}`: si el asesor tiene firma PNG → `<img src="cid:firma-asesor" ...>`, si no → `<p><b>{nombre_asesor}</b><br>GCP · Asesoría Contable</p>`.
4. **Modificar `f29_email.html`** — 
   - Línea 17: cambiar `src="{{logo_url}}"` por `src="cid:logo-gcp"`.
   - Líneas 51-56: eliminar el bloque de firma en texto, reemplazar por `{{bloque_firma}}`.
5. **Modificar `f29_email.txt`** — eliminar las líneas de "Carlos Vergara" / "contacto@gcp.cl", dejar solo `Saludos cordiales,\n{{asesor}}\nGCP · Asesoría Contable`.
6. **Modificar `preview-correo-f29.html`** — quitar "Carlos Vergara" hardcodeado, poner la imagen de la firma (puede ser `file://` path o base64 para la vista previa, que no pasa por SMTP).
7. **Llenar los campos en Notion** (vía API) de la fila `ZZ_TEST AuditAI`:
   - `Honorarios Pendientes` = 85000
   - `Info Adicional` = "A su favor queda un remanente de $417.798 que se arrastra al próximo período."
8. **Reenviar la prueba** con `python app.py --test 39612147-b3ea-810f-b761-d610a3be1ce3`.
9. **Verificar** que el correo llega con:
   - Logo GCP visible en el encabezado (no roto).
   - Bloque de honorarios + datos de transferencia visible.
   - Bloque de info adicional visible (remanente).
   - Firma de Sebastián (imagen) al pie, **sin** "Carlos Vergara" ni "contacto@gcp.cl".
10. **Reportar** qué se cambió y confirmar que los 4 objetivos están resueltos.

---

## Seguridad — lo que NO se debe hacer

- 🔒 **No imprimir** las contraseñas de `asesores_smtp.json` en logs, outputs, ni respuestas.
- 🔒 **No commitear** `asesores_smtp.json` ni `.env` (están en `.gitignore`).
- 🔒 **No loguear** el email del destinatario ni el monto en el backend (el `app.py` ya cumple esto — no romperlo).
- 🔒 Al llenar campos en Notion vía API, **no exponer** `Clave SII` ni `Rut` en outputs.

---

## Cómo verificar el trabajo

Después de hacer los cambios, correr:

```powershell
cd C:\Users\Hp\Documents\AuditAI\notion_automation
python app.py --test 39612147-b3ea-810f-b761-d610a3be1ce3
```

Debe imprimir (sin PII):
```
correo enviado OK · page_id=39612147-... remitente=sebastianrobles@inversoragcp.com
status actualizado → 1) Enviado y Pendiente
```

Y el correo debe llegar a `fbrunel@miuandes.cl` con los 4 objetivos resueltos. Verificar visualmente:
1. Logo GCP se ve bien (no roto).
2. Bloque honorarios + datos transferencia visible.
3. Bloque info adicional (remanente) visible.
4. Firma de Sebastián al pie, sin "Carlos Vergara".

---

## Notas finales

- El backend **ya funciona** (envía correos por SMTP desde la cuenta del asesor). Solo hay que arreglar el contenido del correo (plantilla + imágenes inline).
- El campo `Adviser Accounting` en Notion devuelve el nombre del asesor (ej. "Sebastián Robles "). El matching con `asesores_smtp.json` se hace por `nombre_norm` (minúsculas, sin tildes, sin espacios extra).
- Si hay dudas sobre cómo Gmail maneja imágenes inline, la doc oficial de Google es: https://developers.google.com/gmail/api/guides/sending#attaching_resources — pero el patrón CID de arriba es estándar y funciona.
- **No usar SendGrid ni otros proveedores**: el usuario confirmó que cada asesor envía desde su Gmail con App Password. SMTP directo.
- **No cambiar el asunto** `"Asesoria Honorario"` (es fijo, por decisión del usuario).
- **No agregar paréntesis aclaratorios** en el cuerpo del correo (regla del usuario: nada de "(Texto libre y opcional: ...)" o "(Independiente del impuesto del F29.)" — eso era metadata de demo que se colaba al cliente).

---

## Imágenes a ver (eres multimodal)

**Logo GCP** (va en el encabezado del correo, 42 KB):
`C:\Users\Hp\Documents\AuditAI\LOGO-GCP.png`

**Firma de Sebastián Robles** (va al pie del correo, reemplazando el texto, 100 KB):
`C:\Users\Hp\Documents\AuditAI\pie de pagina-Robles.png`

Lee ambas imágenes para entender su contenido, dimensiones y proporciones antes de integrarlas en el correo.
