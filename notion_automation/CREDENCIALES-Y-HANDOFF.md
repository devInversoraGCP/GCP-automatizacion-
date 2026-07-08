# Credenciales y traspaso (handoff) — Backend del correo F29

> **Para:** la persona que quede a cargo del backend de correos F29 de GCP.
> **Regla de oro:** este documento **NO contiene ningún valor de credencial** — solo dice
> **qué existe, dónde vive y cómo se regenera**. El `NOTION_TOKEN` y el `WEBHOOK_SECRET` viven en
> `.env` (gitignored, fuera del repo) y en las env vars de Render.
>
> ⚠️ **Excepción decidida por el dueño (08-jul-2026):** `asesores_smtp.json` (las App Passwords de
> los asesores) **SÍ está versionado en el repo**, que es **privado**. Esto se apartó de la regla 1/2
> de [`../AGENTS.md`](../AGENTS.md) de forma consciente, para simplificar el traspaso. **Riesgo
> asumido:** si el repo alguna vez se vuelve público, se filtra por un colaborador, o GitHub sufre un
> incidente, esas contraseñas de envío quedan expuestas. Mitigación mínima: mantener el repo privado,
> con acceso restringido, y rotar cualquier App Password si se sospecha exposición.

Última actualización: **08-jul-2026** (scrub de fugas en docs + rotación del `WEBHOOK_SECRET`;
decisión de versionar `asesores_smtp.json` en repo privado).

---

## 1. Qué credenciales usa el sistema

| Credencial | Qué protege / para qué sirve | Dónde vive (local) | Dónde vive (producción) |
|---|---|---|---|
| **`NOTION_TOKEN`** | Leer/escribir las filas de Contable en Notion vía API | `notion_automation/.env` | Env var en Render |
| **`WEBHOOK_SECRET`** | Autentica el webhook del botón (header `X-AuditAI-Secret`). Sin él, cualquiera podría disparar correos | `notion_automation/.env` | Env var en Render **+** header del botón en Notion (deben coincidir) |
| **App Passwords de Gmail (por asesor)** | Enviar el correo desde la cuenta Gmail de cada asesor vía SMTP | `notion_automation/asesores_smtp.json` | Env var `ASESORES_SMTP_JSON` en Render (el JSON completo en una línea) |

> Estado 08-jul: `.env` está **gitignored** (fuera del repo). `asesores_smtp.json` **está versionado
> en el repo privado** (decisión del dueño — ver la nota ⚠️ arriba). Los docs quedaron sin secretos
> en texto tras el scrub del 08-jul.

---

## 2. Estado de los remitentes (asesores Gmail)

Cada cliente tiene un **`Adviser Accounting`** en Notion; el correo sale desde el Gmail de ese asesor.
El mapeo nombre→credencial está en `asesores_smtp.json` (campo `nombre_norm`).

| Asesor | Estado del envío | Nota |
|---|---|---|
| **Sebastián Robles** | ✅ **Verificado** (E2E 07-jul) | Único con App Password confirmada funcionando. Tiene firma PNG (`firmas/firma-sebastian-robles.png`). |
| Constanza Gaggero | ⚠️ Por verificar | Tiene credencial cargada pero no probada en el botón real. |
| Carlos Cereceda | ⚠️ Por verificar | Ídem. |
| Andrea González | ⛔ Pendiente | Marcada `pendiente: true` — sin App Password. |
| Matilde Mateluna | ⛔ Pendiente | Marcada `pendiente: true` — sin App Password. |

> Si un cliente tiene asignado un asesor `pendiente`, el backend responde con error claro y **no**
> envía (no rompe). Fallback: si no hay asesor, usa `EMAIL_FROM`.

### Cómo generar/renovar una App Password de Gmail

1. La cuenta del asesor debe tener **verificación en 2 pasos (2FA)** activada.
2. Ir a https://myaccount.google.com/apppasswords (con esa cuenta) → crear una nueva → nombre "AuditAI".
3. Google entrega **16 caracteres**. Guardarlos en `asesores_smtp.json` (campo `password`), poner
   `pendiente: false`.
4. **Producción:** regenerar el `ASESORES_SMTP_JSON` compacto y actualizarlo en Render (ver §4).
5. Las contraseñas normales de Gmail **no funcionan** por SMTP desde 2022 — tiene que ser App Password.

---

## 3. Dónde está todo (mapa del despliegue)

```
Botón "Enviar Correo F29" (Notion, base Contable Junio)
  │  header X-AuditAI-Secret = WEBHOOK_SECRET   ← debe coincidir con Render
  ▼
https://<servicio>.onrender.com/enviar-f29   (Render, backend Flask + gunicorn, 24/7)
  │  env vars: NOTION_TOKEN, WEBHOOK_SECRET, EMAIL_FROM, EMAIL_CONTACTO, ASESORES_SMTP_JSON
  │
  ├─ lee la fila por API (NOTION_TOKEN)
  ├─ envía el correo por SMTP Gmail (App Password del asesor)
  └─ write-back Status = "1) Enviado y Pendiente"
```

| Recurso | Dónde |
|---|---|
| Código | GitHub `francoSW99/AuditAI---GCP`, carpeta `notion_automation/` (rama `main`) |
| Guía de deploy paso a paso | [`../MIGRACION-A-RENDER.md`](../MIGRACION-A-RENDER.md) |
| Diseño completo de la automatización | [`../docs/dev/23-automatizacion-notion-contable-correo.md`](../docs/dev/23-automatizacion-notion-contable-correo.md) |
| Base operativa en Notion | Contable Junio (data source `09b12147-b3ea-8337-a218-87538eab23fc`) |
| Backend en producción | Render (URL definida al crear el servicio) |

---

## 4. Runbook — tareas de mantenimiento comunes

**Rotar el `WEBHOOK_SECRET`:**
1. `python -c "import secrets; print(secrets.token_hex(32))"`.
2. Poner el nuevo valor en `notion_automation/.env` (local), en la env var de Render, y en el
   header `X-AuditAI-Secret` del botón en Notion. **Los tres deben coincidir.**

**Rotar el `NOTION_TOKEN`:**
1. https://www.notion.so/profile/integrations → la integración → **Regenerate token**.
2. Actualizar `.env` local + env var de Render.

**Agregar/renovar un asesor:** ver §2 (App Password) + regenerar `ASESORES_SMTP_JSON` en Render.

**Regenerar `ASESORES_SMTP_JSON` (una sola línea) para Render:**
```powershell
python -c "import json; print(json.dumps(json.load(open('notion_automation/asesores_smtp.json', encoding='utf-8')), ensure_ascii=False))"
```

**Verificar que no se filtró ningún secreto al repo** (correr antes de cada push importante):
```powershell
git ls-files | Select-String "asesores_smtp|\.env$"   # no debe imprimir nada
```

---

## 5. Si TÚ recibes el proyecto (checklist de traspaso)

- [ ] Te dan acceso al repo de GitHub `francoSW99/AuditAI---GCP` (o se transfiere la propiedad).
- [ ] Te dan acceso al **dashboard de Render** (donde viven las env vars = los secretos de producción).
- [ ] Te comparten el valor de `.env` (NOTION_TOKEN + WEBHOOK_SECRET) por un **canal seguro**
      (gestor de contraseñas, no por chat/mail). El `asesores_smtp.json` ya viene en el repo
      (decisión 08-jul), así que lo obtienes al clonar. Con ambos puedes correr el backend local.
- [ ] Acceso a la **integración de Notion** (para poder regenerar el `NOTION_TOKEN` si hace falta).
- [ ] Acceso de edición al **botón `Enviar Correo F29`** en Contable Junio (para la URL/header).
- [ ] Idealmente, acceso a las cuentas Gmail de los asesores (o que ellos generen sus App Passwords).
- [ ] Lee [`../MIGRACION-A-RENDER.md`](../MIGRACION-A-RENDER.md) y [`../docs/dev/23-...md`](../docs/dev/23-automatizacion-notion-contable-correo.md).

> **Recomendación fuerte:** guardar los valores reales (`NOTION_TOKEN`, `WEBHOOK_SECRET`, App
> Passwords) en un **gestor de contraseñas compartido** del equipo (1Password, Bitwarden, etc.),
> no en archivos sueltos. Así el traspaso no depende de la PC de nadie.
