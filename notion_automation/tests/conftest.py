"""Configuración compartida de los tests del backend AuditAI (Fase 3, doc 27).

Setea env vars de PRUEBA antes de que se importe cualquier módulo del backend.
`load_dotenv()` (que corre al importar `app`) usa `override=False`, así que NO
pisa estas variables — quedan deterministas también en local con un `.env` real.
Ningún test toca Notion ni SendGrid de verdad: todo va mockeado.
"""
import os

os.environ["WEBHOOK_SECRET"] = "test-secret"
os.environ["NOTION_TOKEN"] = "test-token"
os.environ.setdefault("EMAIL_FROM", "notificaciones@inversoragcp.com")
# Sin ADMIN_ALERT_EMAIL por defecto: cada test que lo necesite lo setea explícito.
os.environ.pop("ADMIN_ALERT_EMAIL", None)
os.environ.pop("SENDGRID_API_KEY", None)
