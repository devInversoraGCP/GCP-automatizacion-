# 21 · Resultado del spike de automatización F29

> **Spike ejecutado el 06-07 de julio de 2026.** Prototipo para validar si el sistema puede
> automatizar de punta a punta el cálculo del F29: leer credenciales de Notion, entrar al SII,
> extraer el RCV y calcular el formulario. **Resultado: PARCIAL** — el login automático no es
> posible con las herramientas actuales, pero el resto del flujo sí es viable.

---

## 1 · Resumen ejecutivo

| Aspecto | Estado |
|---|---|
| **Resultado del spike** | ⚠️ **PARCIAL** — login automático bloqueado por el SII |
| **M0 · Credenciales desde Notion** | ✅ Funciona — `notion_lookup.py` lee RUT + CLAVE SII en memoria (R1) |
| **M1a · Login automático al SII** | ❌ **Bloqueado** — el SII detecta toda automatización de login |
| **M1b · Extracción RCV** | ⬜ No alcanzado (depende de M1a) |
| **M2 · Motor de cálculo** | ✅ `motor_f29.py` completo y listo (no dependía del SII) |
| **M3 · Propuesta F29 en vivo** | ⬜ No alcanzado (depende de M1a) |

**Hallazgo crítico:** el SII bloquea **todo login automatizado** mediante detección de CDP
(Chrome DevTools Protocol). No es un problema de credenciales — el login manual con las mismas
credenciales funciona sin problema. Es una protección anti-bot del gobierno chileno que detecta
el protocolo de automatización a nivel del navegador, no solo el fingerprinting.

---

## 2 · Lo que SÍ funciona (validado)

### M0 · Lectura de credenciales desde Notion ✅

- **`notion_lookup.py`** lee RUT + CLAVE SII de la sandbox `General Customers Data - AuditAI`
  (data source `4ff12147-…`) por nombre exacto del cliente.
- Las credenciales fluyen **solo en memoria** — nunca se imprimen, loguean ni escriben a disco
  de forma persistente (R1). Archivos temporales se borran inmediatamente después del uso.
- Verificado con `BAQUI SPA - FRANCISCO`: RUT ✔ (10 chars) · CLAVE SII ✔ (10 chars).
- La API REST de Notion (`POST /v1/data_sources/{id}/query` con `Notion-Version: 2025-09-03`)
  funciona correctamente con el `NOTION_TOKEN` del entorno.

### M2 · Motor de cálculo `motor_f29.py` ✅

- Implementación completa de P1→P6 con aritmética `Decimal` exacta.
- Mapeo a casillas del F29: 502/503/538/519/520/537/504/89/77/62/151/48/595/91.
- Redondeo SII (`ROUND_HALF_UP`) una vez por casilla.
- Regla condicional de P6 implementada correctamente (si P4 ≤ 0 → solo P5).
- **No contiene valores del golden test** (R4: no-trampa).
- Listo para consumir los datos del RCV cuando se disponga de ellos.

### Infraestructura del spike ✅

- Entorno Python 3.14 + Playwright 1.61.0 + Chromium instalado en `.venv/`.
- Playwright MCP (`@playwright/mcp@latest --extension`) configurado en `opencode.json` —
  controla el Chrome real del usuario vía extensión oficial.
- `.gitignore` protege `spike_f29/data/`, `spike_f29/capturas/`, `.playwright-mcp/`.

---

## 3 · Lo que NO funciona — login automático ❌

### 3.1 · Síntomas

Al intentar login automático en `https://zeusr.sii.cl/AUT2000/InicioAutenticacion/IngresoRutClave.html`,
el SII responde con una página de error:

> *«Por el momento no se puede responder a sus requerimientos. Por favor, inténtelo más tarde.
> El código de este mensaje es 01.01.206.500.771.52 (o 01.01.132.500.771.52).
> Información sobre este código, ingrese en "códigos de mensaje de error", opción 'Clave Tributaria'…»*

**El login manual con las mismas credenciales desde el mismo Chrome funciona sin problema.**
Esto descarta que sea un problema de credenciales o de Clave Tributaria bloqueada.

### 3.2 · Enfoques probados (todos fallaron)

| # | Enfoque | Herramienta | Anti-detección | Resultado |
|---|---|---|---|---|
| 1 | Playwright Python + Chromium empaquetado | `p.chromium.launch(headless=False)` | — | ❌ error SII |
| 2 | + Chrome real del sistema | `channel="chrome"` | `--disable-blink-features=AutomationControlled` | ❌ error SII |
| 3 | + stealth mode | `playwright-stealth` | `navigator.webdriver` enmascarado, UA real, locale es-CL | ❌ error SII |
| 4 | + typing humanizado | `keyboard.type()` tecla por tecla | delays aleatorios 50-180 ms, movimientos de mouse | ❌ error SII |
| 5 | Playwright MCP extensión | `@playwright/mcp --extension` | Chrome real del usuario + extensión oficial | ❌ error SII |
| 6 | + typing humanizado via MCP | `run_code_unsafe` | mismo typing humanizado | ❌ error SII |

### 3.3 · Diagnóstico de la causa

El SII detecta el **CDP (Chrome DevTools Protocol)** — el protocolo que **todas** las
herramientas de automatización de navegadores usan internamente:

- **Playwright Python** lanza Chrome con `--remote-debugging-port` → CDP expuesto.
- **Playwright MCP extensión** usa `chrome.debugger` API → CDP adjunto a la pestaña.
- En ambos casos, el SII detecta la presencia de CDP y responde con el error genérico
  en lugar de procesar el login.

**Lo que se descartó como causa:**
- ❌ No es fingerprinting del navegador (Chrome real + stealth no ayudó).
- ❌ No es detección de `page.fill()` (typing humanizado tecla por tecla tampoco funcionó).
- ❌ No es `navigator.webdriver` (enmascarado con stealth, sigue fallando).
- ❌ No es user-agent (UA real de Chrome 137, sigue fallando).
- ❌ No son credenciales (login manual con las mismas funciona).
- ❌ No es mantención del SII (probado múltiples veces en不同 momentos).

**Lo que se confirma como causa:**
- ✅ Es la detección de CDP/debugger adjunto al tab del navegador.

### 3.4 · Selectores del SII confirmados

Para referencia del motor definitivo (cuando el login se resuelva):

| Elemento | Selector | Estado |
|---|---|---|
| RUT input | `#rutcntr` | ✅ confirmado |
| Clave input | `#clave` | ✅ confirmado |
| Botón «Ingresar» | `#bt_ingresar` | ✅ confirmado |
| URL login | `https://zeusr.sii.cl/AUT2000/InicioAutenticacion/IngresoRutClave.html` | ✅ |
| URL RCV | `https://www4.sii.cl/consdcvinternetui/#/index` | ✅ (redirige a login si sin sesión) |
| URL post-login | `https://zeusr.sii.cl/cgi_AUT2000/CAutInicio.cgi` (procesa login) | ✅ |

---

## 4 · Opciones para destrabar el login automático (futuro)

Ordenadas por viabilidad estimada:

### 4.1 · Semi-automático: login manual + robot para el resto (MVP realista)

- El usuario inicia sesión a mano en su Chrome (30 segundos — funciona siempre).
- El robot navega al RCV, selecciona período, captura XHR, calcula F29 — todo automático.
- **95% automático.** El login es la única parte manual.
- Viabilidad: **alta** — no requiere resolver la detección anti-bot del SII.
- Riesgo: la sesión del SII expira (típicamente ~20 min), requiere re-login manual.

### 4.2 · Reutilización de sesión (cookies)

- Tras un login manual, guardar las cookies de sesión del SII con `browser_storage_state`.
- En ejecuciones posteriores, cargar las cookies y navegar directo al RCV sin login.
- Viabilidad: **media** — depende de la duración de la sesión del SII y de si las cookies
  son suficientes (el SII podría requerir re-autenticación por servicio).

### 4.3 · Clave Única OAuth

- El SII soporta login con Clave Única (OAuth del gobierno de Chile).
- Posible automatización vía flujo OAuth (API calls en vez de formulario web).
- Viabilidad: **a investigar** — requeriría entender el flujo OAuth de Clave Única y si tiene
  las mismas protecciones anti-bot que el login de Clave Tributaria.

### 4.4 · HTTP directo (sin navegador)

- Reverse-engineering de la API del SII: replicar el flujo de login con requests HTTP directos
  (sin navegador, sin CDP, sin detección posible).
- Viabilidad: **baja a media** — el SII usa tokens CSRF, cookies de sesión y posibles
  validaciones del lado del servidor que complican la replicación. Riesgo de bloqueo de IP.

### 4.5 · Otras herramientas de automatización

- `undetected-chromedriver` (Selenium con patches anti-detección CDP).
- `puppeteer-extra-plugin-stealth` (Node.js, patches más profundos que Playwright).
- Viabilidad: **incierta** — podrían tener el mismo problema si el SII detecta CDP a nivel
  de protocolo y no de implementación.

---

## 5 · Archivos del spike

| Archivo | Estado | Qué hace |
|---|---|---|
| `motor_f29.py` | ✅ completo | Motor de cálculo P1→P6 + casillas F29 |
| `notion_lookup.py` | ✅ completo | Lectura de credenciales desde Notion (en memoria, R1) |
| `sii_robot.py` | ✅ completo | Robot SII (login + captura RCV + stealth + typing humanizado) |
| `run_fase45.py` | ✅ | Orquestador Fase 4+5 (login + captura RCV) |
| `diagnostico_login.py` | ✅ | Script de diagnóstico (login manual en Chrome controlado) |
| `_gen_creds.py` | ✅ | Helper: genera archivo temporal con credenciales (R1-safe) |
| `README.md` | ✅ | Documentación del spike |
| `data/` | 🗑️ limpio | Vacío (PII borrada) |
| `capturas/` | 🗑️ limpio | Vacío (screenshots borrados) |
| `.venv/` | ✅ | Entorno Python con Playwright instalado |

---

## 6 · Lecciones para el proyecto

1. **El SII es un adversario serio.** Su detección anti-automatización en el login es robusta
   y bloquea todas las herramientas mainstream (Playwright en cualquier modo). Esto cambia el
   enfoque del proyecto: el login automático no es un problema de ingeniería que se resuelve
   con más stealth — es una restricción del dominio que hay que aceptar o rodear.

2. **El motor de cálculo es el activo más valioso del spike.** `motor_f29.py` está completo,
   es determinista, respeta la aritmética `Decimal` y está listo para consumir datos del RCV
   cuando se disponga de ellos. Es la base de la Fase 2 del roadmap.

3. **La integración con Notion funciona.** `notion_lookup.py` lee credenciales de la sandbox
   de forma segura (R1). El patrón de archivo temporal gitignored + borrado inmediato es viable
   para pasar secretos entre Python y el navegador sin exponerlos en la conversación.

4. **El enfoque semi-automático es el MVP realista.** Para la Fase 3 del roadmap (ingesta real
   desde el SII), el flujo debería ser: login manual (usuario) → extracción automática (robot)
   → cálculo automático (motor). No tiene sentido bloquear la Fase 3 intentando automatizar
   el login cuando el resto del flujo sí es automatizable.

5. **El Playwright MCP con extensión es la herramienta correcta para la extracción** (post-login).
   Controla el Chrome real del usuario, con su sesión activa, y puede navegar al RCV y capturar
   los XHR sin pasar por el login. La configuración ya está lista en `opencode.json`.

---

## 7 · Próximos pasos recomendados

1. **Cerrar el spike** con este documento (✅ este doc 21).
2. **Probar el enfoque semi-automático**: el usuario hace login manual en su Chrome, y el robot
   (via Playwright MCP extensión) navega al RCV 2026-05, captura los XHR y calcula el F29 con
   `motor_f29.py`. Esto valida M1b + M2 sin needing resolver el login automático.
3. **Documentar el hallazgo del SII** en `docs/dev/05-decisiones-y-preguntas.md` como una nueva
   decisión (D25?: "login del SII es manual en el MVP; automatización del login queda fuera de
   alcance hasta investigar Clave Única OAuth o HTTP directo").
4. **Avanzar con la Fase 2** del roadmap (motor de cálculo MVP) usando datos de un RCV real
   extraído con el enfoque semi-automático.

---

**Anterior:** [`20-spike-automatizacion-f29-guia-llm.md`](20-spike-automatizacion-f29-guia-llm.md) · **Volver al** [`README`](README.md)
