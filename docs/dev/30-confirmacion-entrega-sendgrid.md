# 30 · Confirmación de entrega real (SendGrid Event Webhook)

> **Estado (14-jul-2026):** ✅ Código implementado y testeado (118/118). Pendiente:
> configuración en SendGrid + columna en Notion + env var en Render (ver §4).
>
> **Origen:** incidente del 13-jul-2026 (caso "Asiri Boutique Spa"): SendGrid agotó
> el crédito del trial (`HTTP 401 Maximum credits exceeded`), el correo no salió,
> el aviso de error tampoco (viaja por el mismo SendGrid) y el botón de Notion
> mostró "éxito" igual (el backend responde 200 aunque `ok=false`). Idea del
> usuario: que SendGrid "avise de vuelta" cuando el correo realmente se entregó.

---

## §1 · El problema

El `202` de la API de SendGrid significa **"aceptado para envío"**, NO "entregado".
Si el correo rebota después (dirección mala, casilla llena, spam), el Status en
Notion queda "1) Enviado y Pendiente" y nadie se entera.

## §2 · El diseño (dos capas)

```
Capa 1 (existente): 202 de SendGrid → write-back optimista de Status/Fecha Envío
Capa 2 (nueva):     SendGrid Event Webhook → POST /webhook/sendgrid → corrige/enriquece
```

1. Cada correo sale con `custom_args = {page_id, flujo}` — SendGrid los devuelve
   tal cual en cada evento, así el evento vuelve "etiquetado" con la fila exacta.
2. SendGrid postea los eventos reales al backend:
   - `delivered` → columna **`Entrega Correo`** = `✅ Entregado · <fecha> UTC`
   - `bounce` / `dropped` → `❌ No entregado (<tipo>) · <fecha> · <razón>` + **aviso
     por correo al asesor** (vía `alertas.avisar_fallo_asesor`)
3. El Status NO espera al `delivered` (la entrega puede tardar y un webhook
   perdido dejaría la fila "sin enviar" para siempre): el webhook solo agrega
   información, nunca bloquea el flujo.

**Detalles finos implementados:**
- **Filtro anti-BCC:** cada envío lleva copias BCC (asesor + Carlos) que generan
  sus PROPIOS eventos con el mismo `page_id`. Solo el evento cuyo `email` coincide
  con la columna `Email` de la fila actualiza Notion (un `delivered` de la copia
  del asesor no debe pisar un `bounce` del cliente).
- **Batch tolerante:** SendGrid manda los eventos en lotes; un evento corrupto o
  un hipo de Notion no tumba el lote (se procesa el resto y se responde 200 —
  responder ≠200 haría que SendGrid reintente el lote ENTERO y duplique).
- **Columna tolerante:** si `Entrega Correo` no existe en la base, queda solo el
  log (mismo patrón del doc 24 §5.1). Matching de nombre con `_clave_prop()`
  (ignora mayúsculas/espacios al borde, doc 29).
- **Auth:** token compartido en la query (`?token=...`, env `SENDGRID_WEBHOOK_TOKEN`)
  porque el Event Webhook de SendGrid no permite headers custom. 503 si el server
  no lo tiene (fail-safe, mismo patrón que `WEBHOOK_SECRET`); 401 si no coincide.

## §3 · Archivos tocados

| Archivo | Cambio |
|---|---|
| `email_sender.py` | `enviar(..., custom_args=)` → `payload["custom_args"]` (solo vía SendGrid; el fallback SMTP local lo ignora) |
| `app.py` | Endpoint `POST /webhook/sendgrid` + `_procesar_evento_sendgrid()` + flag en `/health` |
| `handlers/rrhh.py`, `handlers/tickets.py` | Pasan `custom_args={page_id, flujo}` |
| `tests/test_sendgrid_webhook.py` | 14 tests (guards, delivered, bounce, anti-BCC, batch, custom_args) |

## §4 · Configuración pendiente (manual)

1. **Notion:** crear columna **`Entrega Correo`** (tipo *Text/rich_text*) en
   Contable Junio (y después en RRHH/Tickets si se quiere ahí también).
2. **Render** → Environment: agregar **`SENDGRID_WEBHOOK_TOKEN`** = string aleatorio
   largo (ej. generar con `python -c "import secrets; print(secrets.token_urlsafe(32))"`).
3. **SendGrid** → Settings → Mail Settings → **Event Webhook**:
   - HTTP POST URL: `https://auditai-backend-gubv.onrender.com/webhook/sendgrid?token=<EL_MISMO_TOKEN>`
   - Events: marcar SOLO **Delivered**, **Bounced**, **Dropped**
   - Enabled: ON → Save
4. Verificar: `/health` debe mostrar `sendgrid_webhook_token_configurado: true`,
   y tras un envío de prueba (fila ZZ_TEST) la columna `Entrega Correo` debe
   quedar `✅ Entregado · <fecha>`.

## §5 · Limitaciones conocidas

- El aviso de bounce busca el asesor en `Adviser Accounting` (esquema Contable);
  en RRHH/Tickets esa columna no existe → el aviso sale igual pero al remitente
  por defecto (`EMAIL_FROM`) con copia a los admins.
- La firma criptográfica del Event Webhook (ECDSA, "Signed Event Webhook") no se
  implementó en el MVP; la auth es por token secreto en la URL. Si se quiere
  endurecer, SendGrid lo soporta (requiere la lib `cryptography`).
- Pendiente relacionado (decisión aparte): que los fallos de envío devuelvan
  HTTP ≠200 al botón de Notion para que el asesor vea el error al instante
  (hoy el botón muestra "éxito" aunque `ok=false`).

---

**Anterior:** [`29-reset-mes-automatizado.md`](29-reset-mes-automatizado.md) ·
**Volver al** [`README`](README.md)
