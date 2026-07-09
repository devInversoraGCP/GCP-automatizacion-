# Pendientes — Sistema de correo F29 en la nube

> **Creado:** noche del 08-jul-2026. **Para retomar:** mañana (09-jul-2026).
> Recordatorio de lo que quedó pendiente tras dejar el sistema **funcionando en la nube**.

## ✅ Estado actual (FUNCIONA)

- **Backend en Render 24/7:** `https://auditai-backend-gubv.onrender.com` (deploy desde el repo de Carlos `gcp-dev26/GCP-automatizacion-`).
- **Envío por SendGrid** (API HTTPS) — porque **Render BLOQUEA el SMTP de Gmail**. Esto es el **Plan B** (Single Sender). El plan definitivo es la **Tarea 2**.
- **Probado E2E (08-jul):** botón en Notion → Render → SendGrid → correo enviado desde `sebastianrobles@inversoragcp.com`, **con el PC apagado**. ✅ Correo recibido OK.
- **Asesores ACTIVOS** (verificados en SendGrid + `pendiente:false`): **Sebastián Robles**, **Carlos Cereceda**.
- **Asesores PENDIENTES** (`pendiente:true`, NO envían aún): **Constanza Gaggero**, **Matilde Mateluna**, **Andrea González**.

> ⚠️ **Push pendiente:** el 08-jul se marcó `constanzagaggero` como `pendiente:true` en
> `asesores_smtp.json` (estaba en `false` sin estar verificada → daría error 403). **Falta
> `git add/commit/push`** de ese archivo para que Render lo tome (se puede subir junto con las
> activaciones de mañana).

---

## 📌 TAREA 1 (mañana) — Activar Constanza y Matilde en SendGrid

> **Andrea González NO se activa por ahora** (decisión: hasta nuevo aviso no enviará correos).

**Mañana:** avisar a **Constanza** y **Matilde** que revisen su correo `@inversoragcp.com` y hagan
clic en el link de verificación que les llega de SendGrid.

**Receta para activar cada asesor:**
1. **En SendGrid** (cuenta ya creada): Settings → **Sender Authentication** → **Single Sender
   Verification** → **Create New Sender**. From Email = el `@inversoragcp.com` **exacto** del asesor.
2. **El asesor** abre su correo y hace clic en **"Verify Single Sender"**.
3. **Poner `"pendiente": false`** para ese asesor en `notion_automation/asesores_smtp.json`.
   Comando rápido (activa ambas de una):
   ```powershell
   python -c "import json,pathlib; p=pathlib.Path('notion_automation/asesores_smtp.json'); d=json.load(open(p,encoding='utf-8')); d['constanzagaggero@inversoragcp.com']['pendiente']=False; d['matildemateluna@inversoragcp.com']['pendiente']=False; json.dump(d,open(p,'w',encoding='utf-8'),ensure_ascii=False,indent=2); print('OK')"
   ```
   (Hazlo solo para quien YA verificó en SendGrid; si no, da 403.)
4. **Subir:** `git add notion_automation/asesores_smtp.json` → `git commit -m "activar asesores en SendGrid"` → `git push` → Render redespliega solo (~2-3 min).
5. Probar con una fila de ese asesor.

**Direcciones a verificar:** `constanzagaggero@inversoragcp.com` · `matildemateluna@inversoragcp.com`

---

## 📌 TAREA 2 (plan definitivo) — Verificación de DOMINIO (cuando haya acceso a Vercel)

> **Aclaración clave:** esto **NO reemplaza SendGrid**. Es **autenticar el dominio
> `inversoragcp.com` DENTRO de SendGrid**, agregando unos registros DNS **en Vercel** (ahí vive el
> DNS: `ns1/ns2.vercel-dns.com`). Sigue siendo **SendGrid** el que envía, pero con dominio verificado.

**Por qué (es el upgrade del Plan B):**
- **TODOS** los `@inversoragcp.com` pueden enviar de una (sin verificar uno por uno).
- Se quita el **"via sendgrid.net"** que ven los clientes.
- **Mucha mejor entregabilidad** (SPF/DKIM) → deja de caer en spam/promociones.

**Pasos (cuando se tenga el acceso a Vercel):**
1. Conseguir acceso al **panel de Vercel** de `inversoragcp.com` (lo maneja quien montó la web de GCP).
2. SendGrid: Settings → Sender Authentication → **Domain Authentication** → **Authenticate Your
   Domain** → SendGrid da unos registros **CNAME**.
3. Agregar esos CNAME en **Vercel** (dominio `inversoragcp.com` → DNS Records).
4. En SendGrid dar **Verify**. Listo. (No rompe el correo de Google Workspace.)

---

## 📌 TAREA 3 (opcional) — Keep-alive para el "sleep" de Render

**Problema:** el plan **Free de Render duerme tras 15 min sin tráfico**. El primer clic del botón
tras inactividad tarda ~30-50s y **Notion puede mostrar "no se pudo ejecutar el botón"** (aunque el
backend despierte y procese).

**Soluciones:**
- **Gratis:** un monitor tipo **UptimeRobot** que haga `GET .../health` cada 5-10 min → nunca duerme.
- **$7/mes:** Render **Starter** → siempre despierto, cero latencia.

---

## Datos clave (para retomar rápido)

| Cosa | Valor |
|---|---|
| Backend (Render) | `https://auditai-backend-gubv.onrender.com` |
| Health | `.../health` → `{"ok":true,...}` |
| Repo del que deploya Render | `gcp-dev26/GCP-automatizacion-` |
| Env var clave en Render | `SENDGRID_API_KEY` (+ `NOTION_TOKEN`, `WEBHOOK_SECRET`, `EMAIL_FROM`, `EMAIL_CONTACTO`) |
| Config asesores | `notion_automation/asesores_smtp.json` (campo `pendiente`) |
| Código de envío | `notion_automation/email_sender.py` → `_enviar_via_sendgrid()` |

**Docs relacionadas:** [`MIGRACION-A-RENDER.md`](MIGRACION-A-RENDER.md) · [`notion_automation/CREDENCIALES-Y-HANDOFF.md`](notion_automation/CREDENCIALES-Y-HANDOFF.md) · [`docs/dev/23-automatizacion-notion-contable-correo.md`](docs/dev/23-automatizacion-notion-contable-correo.md)
