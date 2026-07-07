# Manual: migración del backend AuditAI de local → Render (producción)

> **Para:** cualquier dev/asesor de GCP que vaya a poner en producción el backend del correo F29.
> **Prerrequisito:** el backend ya funciona local con ngrok (prueba end-to-end exitosa).
> **Tiempo estimado:** 30–45 minutos.
> **Costo:** gratis (Render free tier — suficiente para el volumen de GCP).
> **Resultado:** backend corriendo 24/7 en `https://auditai-backend.onrender.com/enviar-f29`, sin depender de tu PC.

---

## ¿Por qué migrar a Render?

| | Local + ngrok (desarrollo) | Render (producción) |
|---|---|---|
| Backend corre en | Tu PC | Servidor cloud |
| URL pública | Temporal, cambia cada reinicio | Permanente (`onrender.com`) |
| Disponibilidad | Solo cuando tu PC está encendido | 24/7 |
| Si apagas tu PC | Todo se cae | Siguen funcionando los correos |
| App Passwords | `asesores_smtp.json` local | Env var `ASESORES_SMTP_JSON` en Render |
| Botón de Notion | Hay que actualizar la URL cada vez | Se configura 1 vez y no se toca más |

**Limitación del free tier:** el servicio "duerme" tras 15 min sin tráfico. El primer request tarda ~30s en despertarlo. Para producción 24/7 sin latencia, plan pago ($7/mes) — pero para el volumen de GCP (unos 300 correos/mes) el free tier basta.

---

## Checklist de prerrequisitos (antes de empezar)

- [ ] El backend funciona local (`python app.py --test <page_id>` envía el correo OK).
- [ ] Tienes cuenta en **GitHub** y el repo `AuditAI` subido ahí (o lo subes en el paso 1).
- [ ] Tienes acceso a la **integración de Notion** (`NOTION_TOKEN`).
- [ ] Tienes el `WEBHOOK_SECRET` (está en `notion_automation/.env`).
- [ ] Tienes el contenido de `asesores_smtp.json` (las App Passwords de los asesores).
- [ ] Tienes acceso al botón `Enviar Correo F29` en Contable Junio (Notion) para editar la URL.

> ⚠️ **No hace falta instalar nada en tu PC para migrar.** Render descarga el repo y lo corre en su propio servidor. Todo se hace desde el navegador.

---

## Paso 1 — Subir el repo a GitHub

Render despliega desde GitHub. Si el repo ya está en GitHub, saltar al paso 2.

### 1.1. Crear el repo en GitHub (si no existe)

1. Ir a https://github.com/new
2. **Repository name:** `AuditAI`
3. **Private** (recomendado — tiene datos de negocio en la docs).
4. **No** inicializar con README/license/gitignore (ya los tienes).
5. **Create repository**.

### 1.2. Subir el código desde tu PC

```powershell
cd C:\Users\Hp\Documents\AuditAI
git remote add origin https://github.com/TU_USUARIO/AuditAI.git
git branch -M main
git push -u origin main
```

### 1.3. Verificar que los secretos NO se subieron

```powershell
git log --all --diff-filter=A --name-only --pretty=format: | Sort-Object -Unique | Select-String "asesores_smtp|\.env$"
```

**No debe imprimir nada.** Si imprime un archivo, significa que un secreto se commiteó — ver "Recuperación" al final.

Confirmar que los archivos gitignored no están en GitHub:
- `notion_automation/asesores_smtp.json` → **NO** debe aparecer en GitHub.
- `notion_automation/.env` → **NO** debe aparecer.
- `notion_automation/firmas/*.png` → **SÍ** debe aparecer (no son secretos).
- `notion_automation/email_templates/*` → **SÍ** debe aparecer.

---

## Paso 2 — Crear el Web Service en Render

### 2.1. Registrarse en Render

1. Ir a https://render.com/ → **Sign up** (con GitHub es lo más fácil).
2. Autorizar a Render a acceder a tu GitHub.

### 2.2. Crear el servicio

1. Dashboard → **New +** → **Web Service**.
2. **Build and deploy from a Git repository** → Next.
3. Buscar y seleccionar el repo `AuditAI`.
4. Configurar:

| Campo | Valor |
|---|---|
| **Name** | `auditai-backend` (o el que prefieras — define la URL) |
| **Region** | `Oregon (US West)` o `Frankfurt (EU Central)` — elegir el más cercano a Chile (Frankfurt suele dar mejor latencia desde LATAM, pero la diferencia es marginal). |
| **Branch** | `main` |
| **Root Directory** | `notion_automation` ⚠️ **importante**: el código está en esta subcarpeta, no en la raíz del repo. |
| **Runtime** | `Python 3` (Render lee `runtime.txt` automáticamente) |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python app.py` |
| **Instance Type** | `Free` (suficiente para empezar) |

5. **No** hacer deploy todavía — primero configurar las env vars (paso 3).
6. Hacer clic en **Advanced** (opcional) y revisar. No hace falta tocar nada.

> 💡 Si dejas vacío **Root Directory**, Render buscará `requirements.txt` en la raíz del repo y fallará. Por eso es crítico poner `notion_automation`.

### 2.3. Guardar (sin deploy aún)

Hacer clic en **Save** (o **Create Web Service** si no aparece Save). Render puede intentar un deploy inicial — va a fallar porque faltan las env vars. Eso es normal, lo arreglamos en el paso 3.

---

## Paso 3 — Configurar las variables de entorno (los secretos)

Render no tiene acceso a tu `.env` local (está gitignored, bien). Hay que meter los secretos a mano en el panel de Render.

### 3.1. Ir a las env vars del servicio

1. En Render: dashboard → `auditai-backend` → **Environment** (barra lateral izquierda).
2. Hacer clic en **Add Environment Variable**.

### 3.2. Agregar estas variables (una por una)

| Key | Value | De dónde sacarlo |
|---|---|---|
| `NOTION_TOKEN` | `<tu token>` | `notion_automation/.env` local (línea `NOTION_TOKEN=...`) — **NO commitear** |
| `WEBHOOK_SECRET` | `29ba2103b03fd589f219d1ba1b1ef3147ff91cc27534ac6d64c1fa7bf988a9a5` | El mismo que está en el botón de Notion (deben coincidir) |
| `EMAIL_FROM` | `notificaciones@inversoragcp.com` | Remitente fallback (cuando el cliente no tiene asesor asignado) |
| `EMAIL_CONTACTO` | `contacto@gcp.cl` | Correo que va en el pie del correo |
| `ASESORES_SMTP_JSON` | *(ver 3.3 abajo)* | El contenido completo de `asesores_smtp.json` como string |

### 3.3. El valor de `ASESORES_SMTP_JSON`

Es el contenido **completo** del archivo `notion_automation/asesores_smtp.json`, pero en **una sola línea** (sin saltos de línea). Para obtenerlo:

```powershell
# En tu PC, leer el JSON y compactarlo a una línea:
python -c "import json; print(json.dumps(json.load(open('C:/Users/Hp/Documents/AuditAI/notion_automation/asesores_smtp.json', encoding='utf-8')), ensure_ascii=False))"
```

Copia el output (un string JSON de una línea) y pégalo como valor de `ASESORES_SMTP_JSON` en Render.

> ⚠️ **No borres** `asesores_smtp.json` de tu PC — sigue siendo útil para desarrollo local. En Render, el backend lee de la env var; en local, lee del archivo. El código maneja ambos casos (`_cargar_asesores()` en `email_sender.py`).

### 3.4. Guardar y hacer deploy

1. Hacer clic en **Save Changes**.
2. Render te lleva a la pestaña **Manual Deploy** → **Deploy latest commit**.
3. Esperar a que termine el build (2-5 min la primera vez). Verás logs en tiempo real.

### 3.5. Verificar que arrancó

En los logs de Render, buscar:
```
arrancando backend en 0.0.0.0:<PUERTO>
```

Si aparece, el backend está corriendo. Render te da una URL pública:
```
https://auditai-backend.onrender.com
```

Probar el endpoint de health (en el navegador o con curl):
```
https://auditai-backend.onrender.com/health
```

Debe responder:
```json
{"ok": true, "service": "auditai-f29"}
```

Si responde eso, **el backend está en producción**. 🎉

---

## Paso 4 — Actualizar el botón de Notion con la URL de Render

Ahora que tienes URL estable, reemplaza la de ngrok en el botón de Notion.

### 4.1. Editar el botón

1. Abrir **Contable Junio** en Notion.
2. Click en el encabezado de la columna **`Enviar Correo F29`** → **Edit property**.
3. En el step **Send webhook**:

| Campo | Valor anterior (ngrok) | Valor nuevo (Render) |
|---|---|---|
| **URL** | `https://xxxx.ngrok-free.app/enviar-f29` | `https://auditai-backend.onrender.com/enviar-f29` |
| **Method** | POST | POST (sin cambio) |
| **Header `X-AuditAI-Secret`** | `29ba2103...` | `29ba2103...` (sin cambio — debe coincidir con la env var de Render) |
| **Body** | `{ "page_id": "<ID>" }` | `{ "page_id": "<ID>" }` (sin cambio) |

4. **Guardar**.

### 4.2. Probar el botón end-to-end

1. Ir a la fila de prueba `ZZ_TEST AuditAI` (o cualquier fila real con email + Impuestos + Adviser).
2. Apretar el botón **Enviar F29**.
3. Verificar:
   - El correo llega a la bandeja del cliente (revisa spam la primera vez).
   - El `Status` de la fila cambia a `1) Enviado y Pendiente`.
   - En Render → **Logs**, aparece:
     ```
     correo enviado OK · page_id=... remitente=sebastianrobles@inversoragcp.com
     status actualizado · page_id=... → 1) Enviado y Pendiente
     ```

Si todo eso pasa, **la migración está completa**. El backend ya no depende de tu PC.

---

## Paso 5 — Limpieza post-migración

### 5.1. Cerrar ngrok (ya no lo necesitas para producción)

En tu PC:
- Cerrar la terminal de ngrok (Ctrl+C).
- Opcional: dejar ngrok instalado para futuras pruebas locales (no molesta).

### 5.2. Marcar la URL de Render como definitiva

Anotar la URL en un lugar seguro (docs del proyecto, Notion interna de GCP):
```
URL producción backend: https://auditai-backend.onrender.com/enviar-f29
```

### 5.3. (Opcional) Plan pago cuando el volumen lo justifique

Si el free tier se queda corto (el servicio duerme y los correos se retrasan), subir a **Starter** ($7/mes):
- Render → dashboard → `auditai-backend` → **Settings** → **Instance Type** → `Starter`.
- Sin downtime, Render migra solo.

---

## Mantenimiento posterior

### Cuando agregues un asesor nuevo (con App Password)

1. Generar su App Password (guía en `notion_automation/README.md`).
2. **Local:** actualizar `notion_automation/asesores_smtp.json` + poner su `firma_png` en `firmas/`.
3. **Render:** actualizar el valor de la env var `ASESORES_SMTP_JSON` con el JSON completo nuevo (Environment → editar → Save → Deploy).
4. Si agregaste una firma PNG nueva, hacer `git push` para que Render la descargue.

### Cuando cambies algo del código

1. Editar local, probar con `python app.py --test <page_id>`.
2. `git commit` + `git push`.
3. Render detecta el push y **hace deploy automático** (si tienes auto-deploy activado, que viene activado por defecto).
4. Si prefieres deploy manual: Render → **Manual Deploy** → **Deploy latest commit**.

### Cuando el servicio no responda

1. Render → dashboard → `auditai-backend` → **Logs** (ver qué pasa).
2. Si está dormido (free tier): hacer un request a `/health` para despertarlo, o subir a plan pago.
3. Si las env vars están mal: **Environment** → revisar valores.
4. Si Notion no manda el webhook: revisar que la URL del botón coincida con la de Render y que el `X-AuditAI-Secret` coincida con `WEBHOOK_SECRET`.

---

## Recuperación: si un secreto se commiteó por error

Si por algún motivo `asesores_smtp.json` o `.env` se subieron a GitHub:

### 1. Rotar los secretos comprometidos (lo más importante)

- **App Passwords:** cada asesor whose password was exposed debe generar una nueva App Password en https://myaccount.google.com/apppasswords (las antiguas quedan revocadas automáticamente al crear una nueva, o las revocas manualmente en la misma página).
- **NOTION_TOKEN:** en https://www.notion.so/profile/integrations → tu integración → **Regenerate token**. Actualizar la env var de Render y el `.env` local.
- **WEBHOOK_SECRET:** generar uno nuevo (`python -c "import secrets; print(secrets.token_hex(32))"`), actualizar Render + el botón de Notion.

### 2. Sacar el archivo del historial de git

```powershell
# Instalar git-filter-repo (1 vez):
pip install git-filter-repo

# Borrar el archivo del historial (todas las ramas y commits):
cd C:\Users\Hp\Documents\AuditAI
git filter-repo --invert-paths --path notion_automation/asesores_smtp.json
git filter-repo --invert-paths --path notion_automation/.env

# Force push (cuidado: reescribe el historial):
git push origin --force --all
git push origin --force --tags
```

### 3. Verificar

- En GitHub: el archivo ya no debe aparecer en ningún commit pasado.
- Pedir a los colaboradores que vuelvan a clonar el repo (`git clone` de nuevo).

> 💡 **Prevención:** el `.gitignore` ya excluye `*.env` y `asesores_smtp.json`. Siempre que no edites el `.gitignore`, esto no debería pasar.

---

## Resumen visual del flujo en producción

```
[Asesor de GCP en Notion]
   │
   │ apreta botón "Enviar F29" en una fila de Contable Junio
   ▼
[Notion]  ── POST https://auditai-backend.onrender.com/enviar-f29
              Header: X-AuditAI-Secret: <WEBHOOK_SECRET>
              Body: { "page_id": "<id>" }
           │
           ▼
[Render] auditai-backend (Flask, 24/7)
   │  app.py valida el secreto
   │  notion_client.py lee la fila por API (NOTION_TOKEN)
   │  email_sender.py compone el correo (plantilla + logo + firma inline)
   │  SMTP Gmail con App Password del asesor (ASESORES_SMTP_JSON)
   │  write-back: Status → "1) Enviado y Pendiente"
   ▼
[Cliente de GCP]  ←  correo en su bandeja
   De: "Sebastián Robles · GCP" <sebastianrobles@inversoragcp.com>
   Asunto: Asesoria Honorario
```

**Tu PC no participa en absoluto.** Puedes apagarlo, irte de vacaciones, y los correos siguen saliendo.

---

## Apéndice: URLs y IDs importantes

| Recurso | URL / ID |
|---|---|
| Backend producción (Render) | `https://auditai-backend.onrender.com` *(definida tras el paso 2)* |
| Endpoint del webhook | `https://auditai-backend.onrender.com/enviar-f29` |
| Health check | `https://auditai-backend.onrender.com/health` |
| Contable Junio (Notion) | `https://app.notion.com/p/39612147b3ea80e798e6dbe3de45b76e` |
| Fila de prueba ZZ_TEST | page_id `39612147-b3ea-810f-b761-d610a3be1ce3` |
| Panel de Render | `https://dashboard.render.com` |
| Logs de Render | `https://dashboard.render.com/web/srv-XXXX/logs` *(XXXX = ID del servicio)* |

---

## Apéndice: troubleshooting

### El deploy de Render falla en el build

**Síntoma:** logs dicen `pip install: command not found` o `requirements.txt not found`.

**Causa:** Render no encuentra `requirements.txt` porque no configuraste **Root Directory**.

**Fix:** Render → dashboard → `auditai-backend` → **Settings** → **Root Directory** = `notion_automation` → Save → Manual Deploy.

### El deploy arranca pero el health check devuelve 502/503

**Síntoma:** `https://auditai-backend.onrender.com/health` da 502 Bad Gateway.

**Causa probable:** el backend no está escuchando en `0.0.0.0` (solo en localhost).

**Fix:** verificar que `app.py` tiene `app.run(host="0.0.0.0", port=port)`. Si no, corregir + push + redeploy. (Ya está arreglado en el código actual.)

### El botón de Notion no dispara el webhook

**Síntoma:** apretas el botón y no pasa nada (Status no cambia, no llega correo).

**Debug:**
1. Render → **Logs** → mirar si llega el request. Si no llega, el problema es de Notion.
2. En Notion: abrir la automatización/historial del botón → ver si muestra error.
3. Verificar que la URL del botón es exactamente `https://auditai-backend.onrender.com/enviar-f29` (sin barra al final, sin espacios).
4. Verificar que el header `X-AuditAI-Secret` coincide con `WEBHOOK_SECRET` de Render.

### El correo llega a spam

**Síntoma:** el correo se envía pero está en spam del cliente.

**Causa:** primera vez que la cuenta del asesor envía por SMTP, Gmail puede marcarlo. Mejora con el tiempo. Para acelerar:
- El cliente marca "no spam" la primera vez.
- Si persiste, configurar SPF/DKIM en el dominio `inversoragcp.com` (lo hace el admin del Workspace de Google, no nosotros).

### `ASESORES_SMTP_JSON` no se parsea

**Síntoma:** logs de Render dicen `json.decoder.JSONDecodeError`.

**Causa:** el JSON se pegó con saltos de línea o se cortó.

**Fix:** regenerar el JSON compacto:
```powershell
python -c "import json; print(json.dumps(json.load(open('notion_automation/asesores_smtp.json', encoding='utf-8')), ensure_ascii=False))"
```
Pegar el output completo (una sola línea) en el valor de la env var → Save → Deploy.

---

## Checklist final de migración

- [ ] Paso 1: repo en GitHub, secretos NO commiteados.
- [ ] Paso 2.2: Web Service creado en Render con Root Directory = `notion_automation`.
- [ ] Paso 3.2: env vars configuradas (`NOTION_TOKEN`, `WEBHOOK_SECRET`, `EMAIL_FROM`, `EMAIL_CONTACTO`, `ASESORES_SMTP_JSON`).
- [ ] Paso 3.5: `/health` responde `{"ok": true}` en la URL de Render.
- [ ] Paso 4.1: botón de Notion actualizado con URL de Render.
- [ ] Paso 4.2: prueba end-to-end OK (botón → correo → Status cambia).
- [ ] Paso 5.1: ngrok cerrado.
- [ ] Paso 5.2: URL de Render anotada en docs internas.

**Tiempo total:** ~30-45 min si todo va bien. ~1h si hay que debuggear algo.

---

**Documentación relacionada:**
- [`notion_automation/README.md`](notion_automation/README.md) — setup local + estructura del paquete.
- [`docs/dev/23-automatizacion-notion-contable-correo.md`](docs/dev/23-automatizacion-notion-contable-correo.md) — guía ejecutable completa de la automatización.
- [`AGENTS.md`](AGENTS.md) — reglas de oro (PII, credenciales, etc.).
