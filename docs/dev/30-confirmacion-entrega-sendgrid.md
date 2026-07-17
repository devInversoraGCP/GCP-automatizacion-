# 30 · Confirmación de entrega real (SendGrid Event Webhook)

> **Estado (17-jul-2026):** ✅ Implementado, configurado y **LIVE**. La config de §4 quedó hecha
> (`/health` → `sendgrid_webhook_token_configurado: true`; columna `Entrega Correo` poblándose en
> producción). 🆕 **Extendido (15-jul):** ante el **primer rebote** ya no se alarma de inmediato —
> se agenda **un reintento automático** a los 10 min (muchos rebotes son un hipo DNS transitorio);
> solo si el reintento también rebota se avisa al asesor. Detalle en §6 y en
> [`31`](31-mejoras-robustez-correo-jul-2026.md) §1.2.
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

## §4 · Configuración (✅ hecha, 14-17 jul)

1. [x] **Notion:** columna **`Entrega Correo`** (rich_text) creada en Contable Junio.
2. [x] **Render** → Environment: **`SENDGRID_WEBHOOK_TOKEN`** seteada.
3. [x] **SendGrid** → Event Webhook: URL `.../webhook/sendgrid?token=<TOKEN>`, eventos
   **Delivered/Bounced/Dropped**, Enabled ON.
4. [x] Verificado: `/health` muestra `sendgrid_webhook_token_configurado: true` y la columna
   `Entrega Correo` se puebla en producción (ej. Mockenau 15-jul: `✅ Entregado · 18:50 UTC`).

## §6 · Reintento automático ante rebote (15-jul-2026)

Ante el **primer** evento `bounce` de una fila, `app._agendar_reintento(page_id, flujo)` programa
**un** reintento del envío a los **10 min** (`REINTENTO_BOUNCE_S`, `threading.Timer`) usando el
handler del `flujo` (`f29`/`rrhh`/`tickets-<tipo>`), **sin alarmar al asesor todavía**. Razón: muchos
rebotes son un hipo transitorio del DNS/MX del receptor (caso real Mockenau: rebotó por
`unable to get mx info`, el reenvío entregó OK). La columna `Entrega Correo` muestra mientras tanto
`❌ No entregado (bounce) · reintento automático en 10 min`. Si el reintento **también** rebota, el
segundo evento sí dispara el aviso (ahora vía los avisos a 2 audiencias, doc 31 §1.5, indicando que
ya se reintentó). `dropped` **no** se reintenta (SendGrid ya lo suprimió). Estado en memoria del
proceso (`_reintentos_hechos`); si Render reinicia dentro de la ventana, el reintento se pierde pero
queda visible en la columna. El **filtro anti-BCC** se actualizó para reconocer **cualquiera** de las
direcciones de una celda multi-destinatario (doc 31 §1.4).

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
