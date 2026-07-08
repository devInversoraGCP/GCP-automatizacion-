# notion_automation — Backend del correo F29

Backend Flask que recibe el webhook del botón **"Enviar F29"** de Notion (página Contable Junio), lee la fila del cliente, compone el correo y lo envía por SMTP desde la cuenta Gmail del asesor asignado.

## Arquitectura

```
Notion (botón "Enviar F29" en fila de Contable Junio)
  → POST /enviar-f29  {page_id}
  → app.py valida secreto (X-AuditAI-Secret)
  → notion_client.py lee la fila por API
  → email_sender.py compone el correo (plantilla + bloques) y envía por SMTP
  → write-back: Status = "1) Enviado y Pendiente"
```

## Estructura

```
notion_automation/
  app.py              # backend Flask (endpoint /enviar-f29 + /health)
  email_sender.py     # plantilla + SMTP Gmail (inline CID logo + firma)
  notion_client.py    # helpers REST de Notion
  asesores_smtp.json  # credenciales SMTP por asesor (GITIGNORED)
  .env                # secretos del entorno (GITIGNORED)
  .env.example        # plantilla del .env (commiteable)
  requirements.txt    # dependencias Python
  runtime.txt         # versión de Python (Render)
  Procfile            # cómo arrancar (Render)
  email_templates/    # plantillas HTML/TXT del correo + vista previa
  firmas/             # PNG de firmas de los asesores (1 archivo por asesor)
  data/               # volcados (gitignored)
```

## Setup local

```powershell
cd notion_automation
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Crear .env (ver .env.example) con:
#   NOTION_TOKEN=<token de la integración>
#   WEBHOOK_SECRET=<generar con: python -c "import secrets; print(secrets.token_hex(32))">
#   EMAIL_FROM=notificaciones@inversoragcp.com
#   EMAIL_CONTACTO=contacto@gcp.cl

# Llenar asesores_smtp.json con las App Passwords de cada asesor (ver abajo)

# Probar sin Notion (inyecta un page_id):
python app.py --test <page_id>

# Arrancar backend:
python app.py   # escucha en 0.0.0.0:8000

# Exponer a internet (para que Notion mande el webhook):
ngrok http 8000
# → copiar URL https://xxxx.ngrok-free.app/enviar-f29 en el botón de Notion
```

## App Passwords de Gmail

Gmail no acepta la contraseña normal para SMTP (desde 2022). Cada asesor debe:

1. Habilitar **2FA** en su cuenta Google.
2. Generar una **App Password** en https://myaccount.google.com/apppasswords (nombre: "AuditAI F29").
3. Pasarle la App Password (16 chars) al admin del sistema, que la guarda en `asesores_smtp.json`.

Estructura de `asesores_smtp.json` (gitignored):
```json
{
  "sebastianrobles@inversoragcp.com": {
    "password": "<APP_PASSWORD_GMAIL>",
    "nombre": "Sebastián Robles",
    "nombre_norm": "sebastian robles",
    "tipo": "workspace",
    "pendiente": false,
    "app_password": true,
    "firma_png": "firmas/firma-sebastian-robles.png"
  }
}
```

**`firma_png`** puede ser ruta absoluta o relativa al paquete `notion_automation/`. En producción (Render) **debe ser relativa** para que el archivo se encuentre dentro del repo clonado.

## Configurar el botón en Notion

1. Abrir Contable Junio → columna `Enviar Correo F29` → edit property.
2. Add step → **Send webhook**.
3. URL: `https://<URL-PÚBLICA>/enviar-f29`
4. Method: POST
5. Headers: `X-AuditAI-Secret` = `<WEBHOOK_SECRET del .env>`
6. Body: `{ "page_id": "<ID de esta página>" }` (variable "Page ID" de Notion)
7. Guardar.

## Prueba end-to-end

1. Fila de prueba `ZZ_TEST AuditAI` en Contable Junio (page_id `39612147-b3ea-810f-b761-d610a3be1ce3`):
   - Email: tu correo personal
   - Impuestos: 12345
   - Honorarios Pendientes: 85000
   - Info Adicional: "A su favor queda un remanente..."
   - Adviser Accounting: Sebastián Robles
   - Month: "Junio 2026"
2. Arrancar backend + ngrok.
3. Apretar botón "Enviar F29" de la fila.
4. Verificar: correo llega, Status → "1) Enviado y Pendiente".

## Despliegue en Render (producción)

1. Push del repo a GitHub (asegurar que `.gitignore` excluye `asesores_smtp.json` y `.env`).
2. En Render: **New → Web Service** → conectar repo.
3. Config:
   - **Build Command:** `pip install -r notion_automation/requirements.txt`
   - **Start Command:** `cd notion_automation && python app.py`
   - **Environment:** Python 3 (Render lee `runtime.txt`).
4. **Environment Variables** (secrets — NO commitear):
   - `NOTION_TOKEN` = token de la integración
   - `WEBHOOK_SECRET` = el mismo que está en el botón de Notion
   - `EMAIL_FROM` = notificaciones@inversoragcp.com
   - `EMAIL_CONTACTO` = contacto@gcp.cl
   - `ASESORES_SMTP_JSON` = **contenido completo** del `asesores_smtp.json` (ver `email_sender.py` — lee de esta env var si existe, fallback al archivo local).
5. Deploy. URL estable: `https://auditai-backend.onrender.com/enviar-f29`.
6. Actualizar el botón de Notion con la URL de Render (reemplazar la de ngrok).

**Notas:**
- Render free tier: el servicio "duerme" tras 15 min sin tráfico. El primer request tarda ~30s en despertarlo. Para producción 24/7 real, plan pago ($7/mes).
- Las App Passwords van en la env var `ASESORES_SMTP_JSON` (Render), no en un archivo. Esto evita tener credenciales en el repo.
- Las firmas PNG (`firmas/`) **sí** se commitean (no son secretos).
