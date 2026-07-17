# 27 · Robustez, tolerancia a fallos y observabilidad (plan por fases)

> **Estado (actualizado 17-jul-2026): ✅ Fases 0–3 ejecutadas** (salvo la rotación de App Passwords,
> tarea humana). Este documento fue la hoja de ruta; hoy casi todo está construido y en producción.
> Objetivo del creador (12-jul-2026): *"un sistema tan robusto que la probabilidad de errores o
> caídas sea mínima, y enterarme del detalle de cada error para solucionarlo directamente."*
>
> 🆕 **Extensión (15-17 jul):** sobre este plan se sumaron 5 capas más de robustez/observabilidad
> (validación de Email antes de SendGrid, reintento ante rebote, fallback F29 a la base madre,
> multi-destinatario, y **avisos a 2 audiencias** con query para LLM que cumple de lleno *"enterarme
> del detalle para solucionarlo directamente"*). Consolidadas en
> [`31`](31-mejoras-robustez-correo-jul-2026.md).
>
> Se lee después del [`24`](24-arquitectura-multi-automatizacion.md) (arquitectura del backend).

## 0 · Las dos metas y la filosofía

El pedido tiene **dos caras** que se refuerzan pero no son lo mismo:

| Meta | Qué significa | Cómo se logra |
|------|---------------|---------------|
| **A · Prevención** | Que fallen y se caigan menos cosas | Reintentos, idempotencia, matar el cold-start, validación temprana |
| **B · Observabilidad** | Enterarte del **detalle** de cada error para arreglarlo | Alertas globales, log que **no se borra**, monitor de caídas, matriz de fallos |

Principio rector: **fail-safe y fail-loud a la vez**. El sistema nunca debe dejar al cliente sin
correo *en silencio*: o se recupera solo (prevención), o grita con el detalle exacto
(observabilidad). Hoy falla más bien *en silencio* — ese es el hueco central.

Sub-principios (mejores prácticas que guían todo el plan):
- **MVP-first:** cada fase entrega valor por sí sola; se puede parar entre fases sin dejar el
  sistema a medias.
- **Defensa en profundidad:** varias capas independientes; si una falla, otra atrapa el error
  (mismo patrón que el [`09`](09-seguridad-y-respaldo.md) para los datos).
- **No romper lo que ya anda:** el sistema **funciona hoy** (E2E verificado en F29, RRHH, Tickets).
  Todo cambio debe ser aditivo y reversible.
- **Sin PII en logs/alertas:** se mantiene la regla del [`AGENTS.md`](../../AGENTS.md) #2 — nunca
  loguear email, monto, RUT ni credenciales, ni siquiera en las alertas de error.

---

## 1 · Diagnóstico del estado actual (data-driven)

### 1.1 Lo que YA es robusto (no partimos de cero)

| # | Fortaleza existente | Dónde |
|---|---------------------|-------|
| ✅ | Logging estructurado sin PII, con rotación | [`app.py:26-35`](../../notion_automation/app.py#L26-L35) |
| ✅ | Write-back **tolerante**: si falta una columna, no tumba el resto | [`app.py:137-153`](../../notion_automation/app.py#L137-L153) |
| ✅ | Cascada de fallbacks para identificar la fila (`page_id` → RUT → CLIENTE/Tarea) | [`app.py:249-289`](../../notion_automation/app.py#L249-L289) |
| ✅ | Aviso por correo al asesor cuando falla el F29 (`_alertar_error`) | [`app.py:90-100`](../../notion_automation/app.py#L90-L100) |
| ✅ | `enviar_aviso_error` es best-effort: nunca lanza excepción propia | [`email_sender.py:613-660`](../../notion_automation/email_sender.py#L613-L660) |
| ✅ | Tope de tamaño de adjuntos (evita rebotes por >25 MB) | [`email_sender.py:365-390`](../../notion_automation/email_sender.py#L365-L390) |
| ✅ | Fallback de email en RRHH (lookup en base central) que **nunca** tumba el request | [`rrhh.py:46-68`](../../notion_automation/handlers/rrhh.py#L46-L68) |
| ✅ | Health check para el balanceador | [`app.py:352-354`](../../notion_automation/app.py#L352-L354) |

### 1.2 Los huecos (rankeados por impacto)

| # | Hueco | Severidad | Evidencia | Fase |
|---|-------|:---------:|-----------|:----:|
| **H0** | **App Passwords SMTP commiteadas en el repo** en texto plano (4 asesores). El archivo *dice* estar gitignored pero **no lo está** (`git cat-file -e HEAD:...` → existe) | 🔴🔴 | [`asesores_smtp.json`](../../notion_automation/asesores_smtp.json) + `.gitignore` no lo cubre | **0** |
| ~~**H1**~~ | ~~El aviso de error solo existe en F29~~ → **✅ RESUELTO 12-jul:** RRHH y Tickets ahora avisan al asesor en todo fallo conocido, vía `alertas.avisar_fallo_asesor` | ✅ | [`alertas.py`](../../notion_automation/alertas.py), [`rrhh.py`](../../notion_automation/handlers/rrhh.py), [`tickets.py`](../../notion_automation/handlers/tickets.py) | — |
| **H2** | El log **se borra solo**: `auditai.log` vive en disco efímero de Render (se pierde en cada redeploy/sleep/reinicio) | 🔴 | [`app.py:28`](../../notion_automation/app.py#L28) | **1** |
| **H3** | **Nadie vigila si el backend entero se cae** (deploy roto, token expirado, Render caído). Los avisos solo cubren fallos de un envío individual | 🔴 | no existe monitor externo | **1** |
| ~~**H4**~~ | ~~**Cold start:** el plan free duerme tras 15 min~~ → **✅ RESUELTO:** Render está en plan **Starter ($7/mes, always-on)**, sin sleep ni cold-start | ✅ | [`render.yaml:11`](../../render.yaml#L11) (`plan: starter`) | — |
| **H5** | **Doble-click = doble correo.** No hay guard de idempotencia; el Status se escribe recién al final | 🟠 | [`app.py:110-154`](../../notion_automation/app.py#L110-L154) | **2** |
| **H6** | **Sin reintentos.** Un hipo de red a Notion o SendGrid = fallo definitivo | 🟠 | [`notion_client.py`](../../notion_automation/notion_client.py), [`email_sender.py:604-610`](../../notion_automation/email_sender.py#L604-L610) | **2** |
| ~~**H7**~~ | ~~Excepción no prevista = 500 mudo~~ → **✅ RESUELTO 12-jul:** wrapper try/except en los 3 webhooks; excepciones no previstas avisan al admin (`avisar_excepcion_admin`) en vez de morir en un 500 mudo | ✅ | [`app.py`](../../notion_automation/app.py) (webhooks), [`alertas.py`](../../notion_automation/alertas.py) | — |
| **H8** | **Cero tests.** Cualquier cambio futuro puede romper algo en silencio | 🟡 | no existe `tests/` | **3** |
| ~~**H9**~~ | ~~`WEBHOOK_SECRET` opcional~~ → **✅ RESUELTO 12-jul (Fase 0):** ahora obligatorio, 503 si falta | ✅ | [`app.py`](../../notion_automation/app.py) (`_validar_secreto`) | — |

---

## 2 · El roadmap (fases)

Ordenadas MVP-first: cada fila entrega valor solo y habilita la siguiente.

| Fase | Nombre | Cierra | Esfuerzo | Depende de | Estado |
|:----:|--------|:------:|:--------:|:----------:|:------:|
| **0** | Higiene de seguridad urgente | H0, H9 | ½ día | — | ✅ código listo · falta rotar passwords (humano) |
| **1** | Observabilidad ("enterarme de todo") | H1, H2, H3, H7 | 1–2 días | 0 | ✅ 1.1/1.2/1.5 hechas · 1.3 descartada · 1.4 pospuesta |
| **2** | Prevención ("a prueba de caídas") | H5, H6 | 1–2 días | 1 | ✅ 2.1 reintentos + 2.2 idempotencia hechas |
| **3** | Red de seguridad de cambios | H8 | 1–2 días | — (paralelizable) | ✅ 74 tests + CI |
| **4** | Endurecimiento continuo | resiliencia extra | continuo | 1–3 | 📋 pendiente (opcional) |

> **Recomendación:** hacer **0 → 1 → 2 → 3** en ese orden. La Fase 0 es bloqueante (fuga de
> credenciales activa). La Fase 1 es la que más se parece a *"enterarme del detalle de cada error"*
> y da el mayor retorno. La 3 puede empezar en paralelo cuando quieras.

---

## Fase 0 — Higiene de seguridad urgente (bloqueante) 🔴

Antes de blindar contra caídas, hay que cerrar una **fuga activa**.

### 0.1 · Sacar las App Passwords del repo (H0)
Las contraseñas de aplicación de Sebastián, Constanza y Carlos están en `HEAD` en texto plano.
Quien tenga acceso al repo (incluido el repo espejo de deploy `gcp-dev26/GCP-automatizacion-`) las
tiene. Plan:

1. **Rotar las 3 App Passwords YA** (Cuenta Google → Seguridad → Contraseñas de aplicación →
   revocar la vieja, generar una nueva). Una credencial commiteada se considera **comprometida**;
   cambiar el archivo no basta, hay que invalidar la vieja.
2. **Mover el secreto fuera del repo:** dejar `asesores_smtp.json` **sin** passwords (solo
   `nombre_norm`, `firma_png`, `pendiente`) e inyectar las credenciales por env var
   `ASESORES_SMTP_JSON` en Render — el código **ya soporta** esa vía ([`email_sender.py:86-90`](../../notion_automation/email_sender.py#L86-L90)).
   > Nota: en la nube las passwords SMTP hoy **no se usan** (Render envía por SendGrid API, no SMTP).
   > O sea que el archivo del repo puede quedar **sin passwords** sin romper producción. Solo el
   > fallback SMTP local las necesita, y ese corre en tu PC con el archivo local.
3. **Añadir al `.gitignore`** el patrón correcto y **corregir el comentario mentiroso** `_security`
   del propio JSON.
4. **Purgar del historial** (opcional pero recomendado): `git filter-repo` o BFG para borrar el
   archivo del pasado. Coordinar con Carlos porque reescribe historia en ambos remotos.

- [ ] **Rotadas las 3 App Passwords vivas** ← única tarea humana pendiente (Sebastián, Constanza, Carlos)
- [x] `asesores_smtp.json` versionado queda **sin** `password`/`password_fmt` (12-jul)
- [x] Credenciales locales solo en `asesores_smtp.local.json` (gitignored); `_cargar_asesores()`
      ahora carga env var → `.local.json` → versionado (verificado con test: modo local y modo nube)
- [x] `.gitignore` corregido (`git check-ignore` OK) + comentario `_security` del JSON arreglado
- [ ] (Opcional) historial purgado, coordinado con el repo de Carlos — menos urgente una vez rotadas

### 0.2 · Hacer obligatorio el `WEBHOOK_SECRET` (H9) — ✅ hecho 12-jul
Antes, si la env var no estaba seteada, el endpoint aceptaba **cualquier** POST. Ahora:
helper `_validar_secreto()` compartido por los 4 endpoints — **503** si el server no tiene
secreto (config incompleta, fail-safe), **401** si el header no coincide; log `CRITICAL` al
arrancar si falta; y `/health` expone `webhook_secret_configurado` (booleano, nunca el valor).

- [x] `WEBHOOK_SECRET` seteado en Render — **verificado contra producción 12-jul** (POST sin
      secreto → 401, o sea el secreto está activo; el deploy del 503 no rompe nada)
- [x] Arranque loguea CRITICAL si falta; política: **503** (verificado con test client en los
      3 webhooks + `/health` delatando la config)

---

## Fase 1 — Observabilidad: "enterarme del detalle de cada error" 🔴

El corazón del pedido. Cuatro piezas.

### 1.1 · Red de captura global de errores (H1, H7) — ✅ implementado y verificado 12-jul
Nuevo módulo [`alertas.py`](../../notion_automation/alertas.py) con dos funciones:
`avisar_fallo_asesor(...)` (fallos esperados) y `avisar_excepcion_admin(flujo, page_id, exc)`
(excepciones NO previstas). En [`app.py`](../../notion_automation/app.py), los 3 webhooks
(`/enviar-f29`, `/webhook/rrhh`, `/webhook/tickets/<tipo>`) envuelven identificación + llamada al
handler en un `try/except`: `HTTPException` (los `abort()` intencionales: 400/401/404/503)
**propaga tal cual**; cualquier otra excepción dispara `avisar_excepcion_admin` y devuelve
`{"ok": False, "motivo": "...administrador notificado"}, 500` en vez de un 500 mudo de Flask.
`page_id` empieza vacío y solo se rellena tras confirmarse que es un UUID — así un RUT que llegue
en el payload nunca se filtra al alert si la excepción ocurre antes de resolver la fila.

**RRHH y Tickets ahora avisan al asesor** en *todos* sus caminos de fallo conocido (antes solo
devolvían `{"ok": False}` y morían ahí): fila sin Email/Cliente, asesor pendiente, rechazo de
SendGrid, excepción de envío. En ambos handlers se adelantó el cálculo del nombre del asesor
(`nombre_asesor` en RRHH, `asesor` ya existía en Tickets) para que esté disponible en los
`return` tempranos.

- [x] Wrapper (try/except + `HTTPException` pass-through) en los 3 webhooks — verificado con
      excepciones inyectadas: 500 + admin avisado con `page_id` correcto; `abort()` NO dispara
      el aviso de excepción (es un 400/401/404/503 normal)
- [x] RRHH y Tickets avisan al asesor igual que F29 — verificado: sin Email, fallo de envío
      (`ValueError`/`Exception`) en ambos handlers llaman a `avisar_fallo_asesor` con el
      asesor/cliente/motivo correctos
- [x] La alerta de excepción incluye: flujo, `page_id`, tipo/mensaje/traceback (sin PII —
      `page_id` es un UUID interno, no dato personal)

### 1.2 · Canal de errores del administrador (H1) — ✅ implementado 12-jul, pendiente de activar
`email_sender.enviar_aviso_error` ahora agrega `ADMIN_ALERT_EMAIL` como **cc** (si está seteada y
difiere del destinatario) — como TODOS los flujos pasan por esta función vía `avisar_fallo_asesor`,
el admin queda en copia de cada fallo conocido automáticamente, sin duplicar código por flujo.
Para las excepciones no previstas (1.1), `avisar_excepcion_admin` manda un correo aparte solo al
admin con el detalle técnico completo (traceback), ya que ahí no siempre hay un asesor identificable.

- [x] Env var `ADMIN_ALERT_EMAIL` soportada, **con múltiples destinatarios** (separados por coma,
      `email_sender.admin_emails()`) — decidido 12-jul: `brunel.fr99@gmail.com,carloscereceda@inversoragcp.com`.
      Verificado con test: ambos reciben cc en fallos conocidos y "to" en excepciones no previstas;
      si uno de los admins ES el asesor del correo (ej. Carlos avisándose de sí mismo), no se
      duplica. **Falta setearla en Render** — ver pendientes al final de esta sección
- [x] Todo fallo conocido (los 3 flujos) copia al admin — verificado: cc se agrega correctamente,
      no se duplica si admin==asesor, retrocompatible si la env var no está seteada
- [x] Toda excepción no prevista llega solo al admin con traceback — verificado con excepción real
      (`sys.exc_info()` capturado correctamente desde dentro del `except`)
- [ ] Rate-limit del canal (no inundar si algo falla en loop) — no implementado; **riesgo conocido**
      si un bug entra en loop de reintentos podría mandar muchos correos. Evaluar si hace falta
      cuando exista el volumen real (Fase 4 candidato, no bloqueante para cerrar 1.2)

**✅ Activado en producción 12-jul-2026:**
1. [x] Código desplegado (commits `c03a422` + `fa84467`, push a ambos remotos → Render).
2. [x] `ADMIN_ALERT_EMAIL = brunel.fr99@gmail.com,carloscereceda@inversoragcp.com` seteada en Render.
   **Verificado objetivamente:** `GET /health` responde `admin_alerts_configurados: 2` (los dos
   correos parseados; el campo nuevo de `/health` sirve de check permanente sin exponer los correos).
3. [x] `webhook_secret_configurado: true` en prod → Fase 0.2 desplegada sin romper los botones.

**✅ 1.1/1.2 CERRADAS con confianza total (12-jul):** no hizo falta una prueba de humo artificial —
ocurrió un **fallo de envío REAL en producción** y el creador **recibió el correo de alerta**.
Observabilidad validada end-to-end en vivo.

### 1.3 · Registro que NO se borra (H2) — ❌ DESCARTADO por decisión del creador (12-jul)
**Decisión (12-jul):** no se construye la base de log en Notion. Razón: el creador (que es el propio
asesor de IA que operaría el sistema, sin equipo de devs) revisará los logs **directo en el log
stream de Render** cuando haga falta. La combinación que ya existe alcanza para su operación:
- **Alerta por correo (1.1/1.2):** le avisa al *instante* de cada error → reacciona en el momento.
- **Log stream de Render:** para el detalle técnico; retención ~7 días, suficiente porque reacciona
  al toque al recibir el correo, no días después.

Alineado con la restricción del dueño ("simple, bajo mantenimiento, sin depender de devs"). Si en el
futuro el volumen o la rotación de personas lo pidieran, se puede retomar con **Sentry** (Fase 4).

- [ ] Decisión: destino del log persistente (recomendado A+B)
- [x] ~~base Notion de log~~ **descartada** (12-jul) — se usa el log stream de Render + las alertas por correo

### 1.4 · Aviso si el backend se cae (H3) — ⏸️ pospuesto por el creador (12-jul)
Si el backend **entero** se cae (deploy roto, OOM, crash), nada interno puede avisarte (está
muerto): hace falta un vigía **externo**.

> ⚠️ **Contexto de decisión:** ya se descartó **UptimeRobot** por simplicidad / "sin depender de
> devs" (restricción del dueño). Y el cold-start (H4) **ya no aplica** — Render está en Starter
> always-on. Así que aquí NO se trata de mantener despierto nada, solo de **detectar caídas**.

Camino recomendado, alineado con "simple, sin devs": usar las **notificaciones nativas de Render**
(el panel avisa por correo ante *deploy fallido* y *servicio caído/suspendido*) — cero infra nueva,
cero cuenta de terceros. Si más adelante se quiere algo más fino (chequeo cada X min + canal
Telegram/WhatsApp), se reevalúa un monitor externo liviano; pero como MVP, las alertas de Render
cubren el caso "el backend está caído".

> **Decisión (12-jul):** el creador lo deja "así nomás" por ahora — considera que con los correos
> de alerta de envío ya está cubierto para su operación. ⚠️ **Matiz honesto:** las alertas de la app
> NO cubren la caída del *backend entero* (si el proceso está muerto, no puede mandar correos). El
> hueco H3 queda parcialmente abierto. Es config de 2 minutos en el panel de Render (Settings →
> Notifications → "Only failure notifications") si algún día se quiere cerrar; no cuesta código.

- [ ] Notificaciones de Render activadas (deploy fallido + servicio caído) — **pospuesto por el creador**
- [ ] (Opcional futuro) monitor externo cada X min si se quiere detección más rápida

### 1.5 · Aviso de cuota / cuenta del proveedor de correo (nuevo)
Riesgo real detectado (12-jul): SendGrid **ya no tiene plan gratis permanente** — es una prueba de
**60 días**, luego el envío **se pausa**. Si vence sin aviso, **todos los correos dejan de salir en
silencio** (misma clase que H3). Ver [`PENDIENTES-CORREO-NUBE.md`](../../PENDIENTES-CORREO-NUBE.md).

- [x] Fecha de expiración confirmada: **la prueba de SendGrid vence el 07-sep-2026** ⏰
- [x] **Decisión CERRADA (12-jul-2026): pagar SendGrid Essentials** (~US$19,95/mes, cero migración).
      Brevo descartado: su free sí es permanente (300/día, verificado en help.brevo.com) pero estampa
      "Sent with Brevo" en cada correo; Carlos prefiere pagar antes que marca de agua (Brevo sin logo
      = $18/mes ≈ SendGrid + rehacer DNS/código).
- [x] El rechazo de SendGrid por cuota/auth (403/402/429) ya llega como alerta (al asesor + admin
      en cc) gracias a 1.1/1.2: el mensaje de `ValueError` incluye el HTTP status y el `motivo`
      completo de SendGrid, así que un 403 por cuenta vencida se ve tal cual en el correo de aviso
- [x] ✅ **SendGrid Essentials CONTRATADO/PAGADO (17-jul-2026)** — se cierra el riesgo de pausa
      silenciosa al vencer el trial. Ya no hay acción pendiente con fecha límite.
- [ ] El wrapper de errores (1.1) trata el **403/402/429 de cuota** de SendGrid como alerta crítica al admin

### Criterio de aceptación de la Fase 1
> *"Provoco un fallo a propósito en cada flujo (email vacío, token inválido, SendGrid 403) y en
> los 3 casos recibo una alerta con el detalle, y queda registrado en un lugar que sobrevive a un
> redeploy. Si el backend se cae o un deploy falla, Render me avisa por correo."*

---

## Fase 2 — Prevención: "a prueba de caídas" 🟠

Que muchos fallos **ni siquiera lleguen** a ser un error visible.

### 2.1 · Reintentos con backoff (H6) — ✅ implementado y verificado 13-jul
Nuevo módulo [`http_util.py`](../../notion_automation/http_util.py) con
`request_con_reintentos(metodo, url, ...)`: 3 intentos, backoff exponencial base 0.5s (esperas
0.5s + 1s). Reintenta timeouts, errores de conexión, HTTP 429/5xx; respeta `Retry-After`. NO
reintenta 4xx definitivos (el 403 de SendGrid cae directo al `ValueError`). La etiqueta de log usa
host + último segmento **sin querystring**, para no filtrar tokens.

- [x] Helper de reintentos (3 intentos, backoff 0.5s/1s) — verificado con tests (éxito, 503→ok,
      403 sin reintento, timeout persistente relanza, 429 respeta Retry-After)
- [x] Aplicado a Notion (`get_page`, `update_props`, `query_data_source`, `get_database_title`) y al
      envío SendGrid (`_enviar_via_sendgrid`) — verificado que reintentan en integración
- [x] Respeta `Retry-After` en 429; no reintenta 4xx definitivos
- Nota: los avisos de error (`enviar_aviso_error`, `avisar_excepcion_admin`) quedan **best-effort
  sin reintentos** a propósito, para no demorar la respuesta del webhook.

### 2.2 · Idempotencia anti-doble-correo (H5) — ✅ implementado y verificado 13-jul
Dedupe en memoria por `page_id` ([`app.py`](../../notion_automation/app.py), `_dedupe_reservar` /
`_dedupe_liberar`, ventana `DEDUPE_VENTANA_S = 60`). Lógica: se reserva al entrar; si el envío tuvo
**éxito**, la reserva vive 60s y un segundo click devuelve `{"ok": True, "duplicado": True}` (no
manda segundo correo). Si el envío **falló** (o hubo excepción), se libera vía `finally` → un
reintento legítimo reprocesa (no había correo que duplicar). Cubre los 3 flujos.

- [x] Dedupe por `page_id` con ventana de 60s (memoria del proceso) — verificado en F29 y en el
      webhook genérico (RRHH/Tickets)
- [x] Respuesta clara "duplicado ignorado" con 200 (no cuenta como error)
- [x] Decisión tomada: **no** bloquear por Status. La ventana en memoria mata el doble-click sin
      bloquear un reenvío intencional posterior; más simple y no depende del valor del status.
- Limitación conocida: con gunicorn sync 1 worker (el default de este deploy) el dict basta; con
  varios workers el dedupe no se comparte entre procesos.

### 2.3 · Respuesta rápida al webhook (opcional)
Notion/el navegador esperan la respuesta del botón. Con Starter always-on el cold-start ya no es un
factor, pero un envío con **adjuntos grandes** aún podría tardar. Plan a evaluar solo si se observa
el problema: responder `200 aceptado` rápido y procesar el envío en un hilo/cola. **MVP: no hacer
nada hasta medir** — probablemente los reintentos (2.1) bastan.

- [ ] Medir tiempos reales de request (¿algún caso pasa de ~10s?)
- [ ] Solo si hace falta: procesamiento diferido (hilo/cola) + respuesta inmediata

---

## Fase 3 — Red de seguridad de cambios (tests + CI) 🟡

Lo que te quita el **miedo a tocar el código** sin romper lo que anda.

### 3.1 · Suite de tests (H8) — ✅ implementada y en verde 13-jul
**74 tests** en [`notion_automation/tests/`](../../notion_automation/tests/) con pytest, todos
pasando (0.3s, cero llamadas reales a Notion/SendGrid). Config: [`pytest.ini`](../../pytest.ini)
(pythonpath a `notion_automation`), [`conftest.py`](../../notion_automation/tests/conftest.py)
(env vars de prueba; `load_dotenv` no las pisa por `override=False`).

- [x] `test_puras.py` — funciones puras: `fecha_limite`/`fecha_limite_rrhh` (día hábil, **traslado
      fin de semana**, cruce de año, inválidos), `clp`, `_variantes`, `_combinar_info`, `_norm`,
      `_mes_nombre`, `_es_habil` (sábado/feriado/hábil)
- [x] `test_parsing.py` — identificación de fila: `_es_uuid`, `_buscar_clave` (los 3 formatos),
      `_extraer_plano_notion`, y `_estructura` (que NO filtra PII)
- [x] `test_http_util.py` — reintentos (éxito, 503→ok, 403 sin reintento, timeout, 429 Retry-After,
      etiqueta sin querystring)
- [x] `test_endpoints.py` — guard 401/503, `/health`, captura de excepciones (500 + admin, `abort`
      no dispara aviso, RUT no se filtra), dedupe (doble-click, fallo libera, excepción libera)
- [x] `test_alertas.py` — `admin_emails`, aviso al asesor, aviso al admin con traceback, cc a los
      2 admins sin duplicar
- [x] `test_handlers.py` — RRHH y Tickets avisan al asesor en todo fallo conocido

### 3.2 · CI (GitHub Actions) — ✅ implementado 13-jul
[`.github/workflows/tests.yml`](../../.github/workflows/tests.yml): en cada push a `main` y en cada
PR, instala deps (`requirements.txt` + `requirements-dev.txt`) y corre `pytest` en Python 3.12.
Como el push va a ambos remotos, el CI corre donde GitHub Actions esté habilitado (el repo del
creador y el de Carlos). No necesita secretos (todo mockeado).

- [x] Workflow que instala deps y corre `pytest` en push/PR
- [ ] (Opcional) gate de auto-deploy si fallan — Render no lo soporta nativo desde el blueprint;
      queda como mejora futura (o mover el deploy a que dependa del check verde)

### 3.3 · Smoke test post-deploy — ⏸️ ya cubierto a mano
El chequeo de `/health` tras cada deploy ya se viene haciendo manualmente (polling que confirma
`webhook_secret_configurado`/`admin_alerts_configurados`). Automatizarlo formalmente queda como
opcional; no bloquea.

- [x] Smoke test de `/health` tras deploy — hecho a mano en cada deploy de este plan
- [ ] (Opcional) automatizarlo + fila "cliente de prueba" para E2E

---

## Fase 4 — Endurecimiento continuo (futuro) 🟢

- **Validación de payloads con Pydantic** en el borde (rechazar temprano lo malformado).
- **Health check profundo:** `/health` que además verifica que Notion y SendGrid respondan
  (detecta token/key expirados **antes** de que un cliente lo sufra).
- **Sentry** (opción C de 1.3) si el volumen de errores crece: agrupa, cuenta y alerta.
- **Runbook de incidentes:** un `docs/dev/` con "si pasa X, mirar Y, arreglar Z" (ver anexo).
- **Backup del `asesores_smtp.json` local** cifrado (mismo espíritu que el [`09`](09-seguridad-y-respaldo.md)).

---

## 3 · Anexo — Matriz de modos de fallo (failure mode analysis)

La herramienta central de la meta B: para cada cosa que puede fallar, **cómo se detecta hoy** y
**cómo quedará** tras el plan.

| Modo de fallo | Detección HOY (12-jul, tras 0+1.1+1.2) | Detección tras el plan completo | Fase |
|---------------|----------------------------------------|----------------------------------|:----:|
| Fila sin Email / sin Month | ✅ Aviso al asesor **+ admin (cc)**, los 3 flujos | Igual + registrado en log persistente | — / 1.3 |
| Asesor `pendiente:true` | ✅ `ValueError` → aviso al asesor + admin, los 3 flujos | Igual + registrado en log persistente | — / 1.3 |
| SendGrid 403/402/429 (cuota, remitente no verificado) | ✅ `ValueError` → aviso al asesor + admin (motivo trae el HTTP status) | + no se reintenta (es 4xx definitivo) | — / 2 |
| SendGrid/Notion 5xx o timeout | ⚠️ Fallo definitivo, pero **ahora avisa** (F29 vía try conocido; excepción cruda vía wrapper → admin) | Reintento con backoff antes de rendirse | 2 |
| Notion 429 (rate limit) | ⚠️ Fallo, pero avisa (wrapper de excepción → admin) | Reintento respetando `Retry-After` | 2 |
| Excepción inesperada (bug, dato raro) | ✅ **RESUELTO:** wrapper en los 3 webhooks → alerta al admin con stacktrace, 500 explícito (antes: mudo) | — | — |
| Backend caído (deploy roto, OOM) | ❌ Nadie se entera (el wrapper no ayuda si el proceso está muerto) | Notificaciones nativas de Render → alerta | 1.4 |
| Cold start / timeout del botón | ✅ ya no aplica (Render Starter always-on) | — | — |
| Prueba SendGrid vencida / cuota agotada | ⚠️ Se verá como 403/429 (fila de arriba) pero sin alerta *proactiva* de "se acerca el vencimiento" | Alerta de cuota (1.5) + monitoreo de expiración | 1.5 |
| Token Notion / API key SendGrid expirados | ⚠️ Falla el próximo envío, pero ahora avisa (excepción → admin) | Health profundo lo detecta *antes* de que un cliente lo sufra | 4 |
| Doble-click | ❌ Doble correo al cliente | Dedupe lo ignora | 2 |
| Log perdido en redeploy | ❌ Historial se pierde (aunque las alertas por correo sí quedan, en la bandeja) | Registro persistente (Notion/externo) | 1.3 |
| App Passwords filtradas | ✅ **RESUELTO (Fase 0):** fuera del repo; falta solo rotar las viejas (tarea humana) | — | — |
| `WEBHOOK_SECRET` ausente | ✅ **RESUELTO (Fase 0):** 503 en vez de aceptar abierto | — | — |

---

## 4 · Definición de "robusto" (criterio de cierre global)

El sistema se considera blindado cuando **todas** estas frases son ciertas:

- [x] **Ningún** fallo deja al cliente sin correo *en silencio*: o se recupera (reintentos + reintento
      post-bounce + fallback a la base madre), o me llega **alerta con detalle** (avisos a 2 audiencias, doc 31).
- [ ] Puedo ver el historial de qué se envió y qué falló, **aunque Render se haya reiniciado**
      (log persistente 1.3 descartado por decisión; queda el log stream de Render ~7d + las alertas en la bandeja).
- [ ] Si el backend se cae, me entero por un canal externo en **minutos** (1.4 pospuesto; config de
      2 min en las notificaciones de Render si se quiere cerrar).
- [x] Un doble-click no manda dos correos (dedupe, 2.2).
- [x] Un hipo de red no pierde un envío (reintentos con backoff, 2.1).
- [x] Puedo cambiar el código con la confianza de una suite de tests que corre sola (**175 tests** + CI).
- [x] No hay credenciales en el repo (Fase 0; falta solo **rotar** las viejas del historial — tarea humana).

---

**Anterior:** [`26-automatizacion-tickets-correo.md`](26-automatizacion-tickets-correo.md) · **Volver al** [`README`](README.md)
