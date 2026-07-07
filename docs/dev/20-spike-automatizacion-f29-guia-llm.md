# 20 · Spike de automatización F29 de punta a punta — guía ejecutable para LLM

> **Misión:** demostrar que el sistema puede, **sin intervención manual**, tomar las credenciales
> de un cliente desde la base central de Notion, entrar al SII, extraer los datos, y calcular el
> Formulario 29 completo — verificando el resultado **al peso** contra el caso real ya validado
> (golden test `CLIENTE1`, período **abril 2026**).
>
> **Naturaleza:** spike/prototipo (adelanta la Etapa B2 "muestras reales" de [`16`](16-frente-b-plan-calculo-f29.md)).
> **No** cierra el gate del Frente A (D18) ni es el motor definitivo.
>
> **Decisiones ya tomadas por el usuario (06-jul-2026) — no re-preguntar:**
> cliente de prueba = **Cliente 1** · credenciales **desde Notion, automático** · navegador
> **visible y supervisado** · alcance **M1+M2+M3 completo**.

---

## §0 · Orden de lectura y economía de tokens

1. [`../../AGENTS.md`](../../AGENTS.md) — reglas de oro del proyecto (obligatorio).
2. **Este documento completo.** Es autosuficiente: contiene las secuencias clic a clic
   (transcritas de [`17`](17-especificacion-literal-calculo-f29.md) §4, la spec validada por GCP).
   Ante cualquier duda de fondo tributario, la autoridad es el doc 17.
3. [`../../spike_f29/README.md`](../../spike_f29/README.md) y el código ya creado (§2).

**Economía de tokens (para ti, LLM):**
- Los volcados del SII/Notion pueden ser enormes: **guárdalos en `spike_f29/data/` y examínalos
  con Grep o lecturas parciales**. Jamás los imprimas completos en la conversación.
- Trabaja por fases (§4–§11) y **verifica el criterio de aceptación de cada una antes de seguir**.
- No re-verifiques lo que §2 ya da por verificado.

---

## §1 · Reglas inquebrantables

| # | Regla | Detalle |
|---|---|---|
| R1 | **Credenciales solo en memoria** | RUT y CLAVE SII jamás se imprimen, loguean, escriben a disco ni aparecen en la conversación. Todo diagnóstico pasa por `descripcion_segura()` de [`notion_lookup.py`](../../spike_f29/notion_lookup.py). El usuario **jamás** debe escribir la clave en el chat; si intenta hacerlo, detenlo. |
| R2 | **Un solo intento de login** | Si el SII rechaza el login, muestra captcha o desafío: **abortar y reportar** (los reintentos bloquean la clave del cliente). No reintentar sin autorización del usuario. |
| R3 | **Prohibido enviar nada** | Solo consultas de lectura. **Lista negra global** (regex sobre el texto de TODO elemento antes de clickearlo): `enviar\|firmar\|pagar\|presentar\|rectificar`. En el flujo de la propuesta (Fase 7) rige además una **lista blanca**: solo los clicks exactos de esa secuencia. Pantalla inesperada ⇒ pausar y preguntar al usuario. |
| R4 | **No-trampa** (compromiso con el usuario) | **Jamás abrir `PRUEBA1.xlsx` ni `PRUEBA1.csv`.** El código de extracción y el motor no contienen ningún valor del golden test. Los valores esperados (§12) se usan **solo al final, para comparar**. |
| R5 | **PII fuera de outputs** | El RCV contiene RUTs de contrapartes: los volcados van a `spike_f29/data/` (gitignored) y no se imprimen. Solo se muestran **agregados** (sumas y conteos). Los pantallazos van a `spike_f29/capturas/` y **nunca** se toma pantallazo de la página de login. |
| R6 | **El usuario supervisa** | Navegador **visible** (`headless=False`, `slow_mo=300`). Avisar al usuario antes de cada fase que toque el SII, y especialmente antes de la Fase 7. |
| R7 | **Identidad de Cliente 1** | Su nombre real NO está en la documentación (anonimizado por diseño). **Pregúntaselo al usuario.** No intentes deducirlo de ningún archivo. |
| R8 | **Si algo no calza, no adivines** | Selector que no existe, pantalla nueva, JSON con otra forma ⇒ volcar evidencia a `data/`/`capturas/`, mostrar al usuario un resumen y decidir juntos. Lección Zsabesky: jamás asociar/asumir por similitud difusa. |

---

## §2 · Estado ya preparado y verificado (06-jul-2026) — NO lo redescubras

### Máquina (Windows 10 Home, PowerShell 5.1)
- **Python 3.14.0** (`python`) ✓ · **Node 22.20.0** ✓ · **uv NO instalado** (usar `venv`+`pip`).
- **`NOTION_TOKEN` definida** en el entorno (50 chars). `opencode.json` solo tiene la referencia
  `{env:NOTION_TOKEN}`; `.mcp.json` usa el conector http OAuth (inútil para scripts).

### Notion (verificado por SQL esta semana)
- Sandbox **`General Customers Data - AuditAI`**: data source `4ff12147-b3ea-82f4-98dd-072067524cdc`,
  **331 clientes**. Propiedad **título = `w`** (nombre del cliente) · credenciales en propiedades
  **`RUT`** y **`CLAVE SII`** (rich_text). Esquema completo: [`08`](08-notion-general-customers-data.md).
- API REST: `POST https://api.notion.com/v1/data_sources/{id}/query` con header
  `Notion-Version: 2025-09-03` **funciona** con este token.
- ⚠️ El workspace se **rate-limita fácil** (429 `collection_router_upstream`; su `retry_after: 30`
  es optimista). Backoff real: **≥60 s**, máximo 3 reintentos, minimizar consultas.

### Código ya creado en [`spike_f29/`](../../spike_f29/)
| Archivo | Estado | Qué hace |
|---|---|---|
| `motor_f29.py` | ✅ completo | `EntradasF29` → `calcular()` → casillas `502/503/538/519/520/537/504/89/77/62/151/48/595/91` + `formatear()`. Todo `Decimal`, redondeo SII (`ROUND_HALF_UP`) una vez por casilla. Convención de signos: P1 ≥ 0, **P2 y P3 entran en negativo**, tasa como fracción (`0,125 % → Decimal("0.00125")`). |
| `notion_lookup.py` | ✅ completo | `credenciales_cliente(nombre)` busca por título exacto (luego `contains`) y devuelve `{nombre, rut, clave}` en memoria. CLI de verificación: imprime solo confirmación enmascarada. |
| `README.md` | ✅ | Uso y reglas del spike. |
| `sii_robot.py` | ❌ por crear | Esqueleto completo en §6 — cópialo y ajústalo en vivo. |
| `main.py` | ❌ por crear | Especificación en §8. |
| `.venv` | ❌ por crear | Fase 1 (§5). |
- `.gitignore` ya protege `spike_f29/data/`, `spike_f29/capturas/`, `.venv/`, `*.env`, `backups/`.

---

## §3 · Convenciones del dominio que el robot debe respetar

- **Período:** siempre formato `AAAA-MM`. El golden test usa **2026-04**. (En producción el período
  es "mes anterior al actual"; aquí es abril porque es el caso validado.)
- **Tipos de documento (DTE) que afectan las sumas** (catálogo completo: [`12`](12-fase1-plan-detallado.md) §B0):
  | TpoDoc | Documento | Efecto |
  |---|---|---|
  | 33 | Factura electrónica | suma |
  | 34 | Factura exenta | suma (solo neto/exento a BI) |
  | 39 | Boleta electrónica | suma |
  | **48** | **Comprobante de pago electrónico** | suma (es el que genera el débito de CLIENTE1) |
  | 56 | Nota de débito | suma |
  | **61** | **Nota de crédito** | **RESTA en todas las sumas (P1, P2 y BI)** |
  | 914 | DIN (importación) | suma al crédito (P2) |
- ⚠️ No confundir los **tres sistemas de códigos**: tipo de documento (48 = comprobante) ≠ casilla
  F29 (48 = ret. impuesto único) ≠ código de impuesto. Ver [`12`](12-fase1-plan-detallado.md) §B0.
- **Regla de dinero:** parsear montos como `Decimal` (los JSON del SII traen enteros CLP; si
  llegara un string con puntos de miles, limpiarlo antes). Nada de `float`.

---

## §4 · Mapa del proceso completo (fases y criterios de aceptación)

| Fase | Qué se hace | Criterio de aceptación (gate para seguir) |
|---|---|---|
| **1** | Preparar entorno (venv + Playwright) | `playwright --version` responde y Chromium instalado |
| **2** | Identidad Cliente 1 + credenciales (M0) | `notion_lookup.py` imprime `OK · … RUT ✔ · Clave SII ✔` |
| **3** | Crear `sii_robot.py` (§6) | El archivo existe y pasa `python -c "import sii_robot"` |
| **4** | Login al SII (M1a) | Sesión iniciada; nombre del contribuyente visible; usuario lo vio |
| **5** | RCV abril: VENTA + COMPRA (M1b) | P1, P2, BI y conteos extraídos de los JSON capturados |
| **6** | Motor + comparación (M2) | Casillas calculadas coinciden **al peso** con §12 |
| **7** | Propuesta F29 en vivo (M3) | 504 y 115 del período actual leídos; cero clicks fuera de lista blanca |
| **8** | (Extensión, si aplica) Boletas + RRHH | 151 y 48 obtenidos según §10 |
| **9** | Informe final + limpieza | Doc `21` creado; `data/` depurado; `git status` limpio de PII |

Si la Fase 5 falla por estructura desconocida del sitio: el primer intento es de **reconocimiento**
(capturar, volcar, ajustar) — es lo esperable en un spike. Itera con el usuario mirando.

---

## §5 · Fase 1 — Preparar el entorno (una sola vez)

```powershell
cd c:\Users\Hp\Documents\AuditAI\spike_f29
python -m venv .venv
.venv\Scripts\python -m pip install --quiet playwright
.venv\Scripts\playwright install chromium    # descarga ~150 MB
.venv\Scripts\playwright --version           # verificación
```

**Contingencias:**
- `pip install playwright` falla compilando `greenlet` (Python 3.14 muy nuevo) ⇒ instalar un
  Python estable en paralelo (`winget install Python.Python.3.12`), recrear el venv con
  `py -3.12 -m venv .venv`. Si tampoco, plan C: robot en Node (`npm i playwright`) manteniendo
  motor y lookup en Python.
- Descarga de Chromium bloqueada por proxy/red ⇒ reintentar; si persiste, preguntar al usuario.
- PowerShell bloquea `Activate.ps1` ⇒ no actives el venv: invoca siempre
  `.venv\Scripts\python …` con ruta completa (como en todos los comandos de esta guía).

---

## §6 · Fase 2 y 3 — Credenciales y construcción del robot

### Fase 2 · M0: identidad y credenciales
1. **Pregunta al usuario, literalmente:** «¿Cómo se llama exactamente Cliente 1 en la base
   central (columna de nombre)? Recuerda: NO me digas la clave — solo el nombre.»
2. Verifica (imprime solo confirmación enmascarada):
   ```powershell
   .venv\Scripts\python notion_lookup.py "<NOMBRE EXACTO>"
   ```
3. Errores posibles: `no encontrado` ⇒ pedir al usuario el nombre exacto como aparece en Notion ·
   `calza con N fichas` ⇒ pedir el nombre completo · `sin CLAVE SII` ⇒ detenerse (ver [`15`](15-barrido-bases-contables-mensuales.md)) ·
   HTTP 429 ⇒ esperar ≥60 s.
4. **Pregunta también, para la Fase 6:** «Del F29 declarado de abril de Cliente 1: ¿cuál fue el
   remanente del mes anterior (casilla 504) y la tasa de PPM (casilla 115)? Son las dos entradas
   que el robot no puede leer de una propuesta que ya no existe.» *(Alternativa automatizada: §9.)*

### Fase 3 · Crear `spike_f29/sii_robot.py`
Esqueleto completo — cópialo tal cual y ajusta **solo** lo marcado `# VERIFICAR EN VIVO`:

```python
"""Robot SII (spike) — SOLO LECTURA. Reglas R1-R3: credenciales en memoria,
un intento de login, lista negra de botones. Navegador visible (R6)."""
from __future__ import annotations
import json, re, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page

DATA = Path(__file__).parent / "data"; DATA.mkdir(exist_ok=True)
CAPT = Path(__file__).parent / "capturas"; CAPT.mkdir(exist_ok=True)
PROHIBIDOS = re.compile(r"enviar|firmar|pagar|presentar|rectificar", re.I)

URL_LOGIN = "https://zeusr.sii.cl/AUT2000/InicioAutenticacion/IngresoRutClave.html"
URL_RCV = "https://www4.sii.cl/consdcvinternetui/#/index"


def click_seguro(page: Page, selector_o_texto: str, descripcion: str) -> None:
    """Único camino permitido para clickear. Aplica la lista negra R3."""
    loc = (page.get_by_text(selector_o_texto, exact=False).first
           if not selector_o_texto.startswith(("#", ".", "//", "css="))
           else page.locator(selector_o_texto).first)
    texto = (loc.inner_text(timeout=5000) or "") + " " + (loc.get_attribute("value") or "")
    if PROHIBIDOS.search(texto):
        raise RuntimeError(f"🛑 R3: click bloqueado sobre '{texto.strip()[:60]}' ({descripcion})")
    loc.click()


def login(page: Page, rut: str, clave: str) -> None:
    """Paso 0 de la spec (doc 17 §4). UN intento (R2). No imprime credenciales (R1)."""
    page.goto(URL_LOGIN, wait_until="domcontentloaded")
    page.fill("#rutcntr", rut)          # VERIFICAR EN VIVO (selector clásico del SII)
    page.fill("#clave", clave)          # VERIFICAR EN VIVO
    page.click("#bt_ingresar")          # VERIFICAR EN VIVO
    page.wait_for_load_state("networkidle")
    cuerpo = page.content().lower()
    for senal in ("clave incorrecta", "bloqueado", "captcha", "no es v", "error de autent"):
        if senal in cuerpo:
            raise RuntimeError(f"🛑 R2: login rechazado (señal: '{senal}'). ABORTAR, no reintentar.")
    # Paso 0.5: si aparece "Escoja cómo desea ingresar", entrar a la información personal
    if "escoja" in cuerpo and "ingresar" in cuerpo:
        click_seguro(page, "Continuar", "paso 0.5 ingreso a información tributaria personal")
    # Paso 0.6: verificación de identidad la hace el USUARIO mirando la esquina superior.
    print("✅ Login OK — usuario: confirma en pantalla que el nombre del contribuyente es el esperado.")


def capturar_rcv(page: Page, periodo: str) -> list[Path]:
    """Pasos 1 y 2 de la spec: RCV, período, pestañas VENTA y COMPRA.
    Estrategia: NO scrapear el DOM — capturar los XHR JSON de la app Angular."""
    capturados: list[Path] = []

    def guardar(resp):
        ct = (resp.headers or {}).get("content-type", "")
        if "consdcvinternetui/services" in resp.url and "json" in ct:
            try:
                destino = DATA / f"rcv_{periodo}_{len(capturados):02d}.json"
                destino.write_text(json.dumps(
                    {"url": resp.url, "body": resp.json()}, ensure_ascii=False, indent=1),
                    encoding="utf-8")
                capturados.append(destino)
            except Exception:
                pass  # respuestas no-JSON o vacías: ignorar

    page.on("response", guardar)
    page.goto(URL_RCV, wait_until="networkidle")
    # 1.3 · Período AAAA-MM. La UI tiene selects de mes y año.  VERIFICAR EN VIVO:
    anio, mes = periodo.split("-")
    try:
        page.select_option("select#periodoAnho, select[name*=anho i]", anio)
        page.select_option("select#periodoMes, select[name*=mes i]", mes)
    except Exception:
        print("⚠ Selectores de período no calzaron. Abriendo inspector: fija el período "
              f"{periodo} a mano y presiona Resume ▶ en la barra de Playwright.")
        page.pause()                      # recon supervisado (R8)
    click_seguro(page, "Consultar", "1.4 consultar RCV")
    page.wait_for_load_state("networkidle"); time.sleep(2)
    click_seguro(page, "VENTA", "1.5 pestaña VENTA (no 'Información Electrónica de Ventas')")
    page.wait_for_load_state("networkidle"); time.sleep(2)
    click_seguro(page, "COMPRA", "2.1 pestaña COMPRA")
    page.wait_for_load_state("networkidle"); time.sleep(2)
    print(f"📥 {len(capturados)} respuestas JSON capturadas en spike_f29/data/")
    return capturados


def resumen_capturas(rutas: list[Path]) -> None:
    """Reconocimiento SIN imprimir PII: para cada JSON, muestra solo la ruta del
    endpoint, las claves de primer nivel y, si hay listas de documentos, sus campos."""
    for ruta in rutas:
        d = json.loads(ruta.read_text(encoding="utf-8"))
        cuerpo = d["body"]
        print(f"· {ruta.name} ← …{d['url'][-70:]}")
        def explorar(nodo, prefijo="  "):
            if isinstance(nodo, dict):
                print(prefijo + "claves: " + ", ".join(list(nodo)[:20]))
                for v in nodo.values():
                    if isinstance(v, list) and v and isinstance(v[0], dict):
                        print(prefijo + f"lista[{len(v)}] campos: " + ", ".join(list(v[0])[:25]))
        explorar(cuerpo)
```

**Notas de diseño (no negociables):**
- Todo click pasa por `click_seguro()` — nunca `loc.click()` directo.
- El listener de XHR hace innecesaria la paginación del DOM (el servicio devuelve el detalle completo).
- `resumen_capturas()` es la única inspección permitida en consola: claves y conteos, jamás filas.

---

## §7 · Fases 4–5 — Ejecución M1, clic a clic

> Secuencia funcional transcrita de la spec validada por GCP ([`17`](17-especificacion-literal-calculo-f29.md) §4).
> El robot la ejecuta; tú (LLM) verificas cada checkpoint con el usuario mirando.

### Fase 4 · Login (paso 0)
| # | Acción | Detalle |
|---|---|---|
| 0.1 | Credenciales desde Notion | `credenciales_cliente(nombre)` — en memoria (R1) |
| 0.2 | Abrir el login | `URL_LOGIN` (si `www4.sii.cl` redirige a otra pantalla de login, seguirla) |
| 0.3 | Llenar campos | RUT en «RUT Usuario» (`#rutcntr`), clave en «Clave» (`#clave`) |
| 0.4 | Click **«Ingresar»** | `#bt_ingresar` |
| 0.5 | Pantalla «Escoja cómo desea ingresar» (solo si el RUT representa a otros) | elegir **«Ingresar a mi información tributaria personal (Continuar)»** |
| 0.6 | Verificar identidad | El **usuario** confirma en pantalla que el nombre de la esquina = Cliente 1. Si no coincide: **abortar** |

### Fase 5 · RCV abril (pasos 1 y 2)
| # | Acción | Detalle |
|---|---|---|
| 1.1 | Menú | Servicios online → **Impuestos mensuales** → **Registro de Compras y Ventas** *(el robot va directo a `URL_RCV`, equivalente)* |
| 1.3 | Período | **2026-04** (formato AAAA-MM) |
| 1.4 | Click **«Consultar»** | dispara los XHR que el listener captura |
| 1.5 | Pestaña **«VENTA»** | ⚠️ la pestaña VENTA, **no** "Información Electrónica de Ventas" |
| 1.6 | Por cada fila (del JSON) | leer `TpoDoc`, `NroDoc`, `FchDoc`, **Monto Neto** (`MntNeto`), **Monto Exento** (`MntExe`), **Monto IVA** (`MntIVA`) |
| 1.7 | Sumar | **P1 = Σ MntIVA** (TpoDoc 61 resta) · **BI = Σ (MntNeto + MntExe)** (61 resta) · contar docs → casilla 503 |
| 2.1 | Pestaña **«COMPRA»** | mismo período ya consultado |
| 2.2 | Por cada fila | leer además `RUTDoc`; usar **«IVA Recuperable»** (`MntIVA` recuperable) |
| 2.3 | Sumar | **P2 = −Σ IVA Recuperable** (61 resta; 914 DIN suma) · **excluir `MntIVANoRec`** · contar docs → 519 |

**Procedimiento con los JSON capturados:**
1. `resumen_capturas()` → identifica cuál archivo trae la lista de documentos de VENTA y cuál la
   de COMPRA (por la ruta del endpoint y los campos de la lista).
2. Con Grep sobre el archivo confirma los **nombres reales** de los campos (probables: `mntIVA`,
   `mntNeto`, `mntExento`/`mntExe`, `mntIVARecuperable`, `tpoDoc`/`dcvTipoDoc`, `rutProveedor`).
3. Escribe entonces (no antes) la función de suma exacta en `sii_robot.py`, respetando la regla
   del TpoDoc 61. Imprime **solo** los agregados: `P1`, `BI`, `P2`, conteos.

**Checkpoint Fase 5:** anota P1/P2/BI extraídos. **Aún no los compares con nada** — eso es Fase 6.

---

## §8 · Fase 6 — `main.py`, motor y comparación (M2)

`spike_f29/main.py` orquesta:

```python
# argumentos: --cliente "NOMBRE" --periodo 2026-04 --remanente N --tasa X [--m3]
# 1) cred = notion_lookup.credenciales_cliente(args.cliente)          (R1)
# 2) print(notion_lookup.descripcion_segura(cred))
# 3) with sync_playwright() as p:
#        browser = p.chromium.launch(headless=False, slow_mo=300)     (R6)
#        page = browser.new_page()
#        sii_robot.login(page, cred["rut"], cred["clave"])
#        rutas = sii_robot.capturar_rcv(page, args.periodo)
#        (si --m3): quinientos4, tasa115 = sii_robot.leer_propuesta(page)   # §9
#        browser.close()
# 4) p1, p2, bi, n_v, n_c = sii_robot.sumar(rutas)                    (§7)
# 5) e = motor_f29.EntradasF29(
#        p1_debito=p1, p2_credito=p2,
#        p3_remanente=-abs(Decimal(args.remanente)),   # entra en NEGATIVO
#        bi_ppm=bi,
#        tasa_ppm=Decimal(args.tasa) / 100,            # "0.125" → 0.00125
#        n_docs_venta=n_v, n_docs_compra=n_c)
# 6) r = motor_f29.calcular(e); print(motor_f29.formatear(r))
```

**Las dos entradas** (`--remanente`, `--tasa`) son las casillas **504 y 115 de abril**: para un
período ya declarado no existe "propuesta", así que las provee el **usuario** leyéndolas del F29
declarado (pedidas en Fase 2, paso 4). **No** las tomes de la documentación (R4): trátalas como
dato del usuario. *(Automatizarlas: §9, opción B.)*

**Comparación final (recién aquí se abre §12):** construir tabla `casilla | calculado | esperado |
✓/✗`. Éxito = todas ✓ al peso. Si algo difiere: identificar en `data/` el documento que explica
la diferencia (por TpoDoc/folio, sin imprimir PII) y reportarlo.

---

## §9 · Fase 7 — Propuesta del F29 en vivo (M3), clic a clic

> ⚠️ La fase delicada: pasa por pantallas del flujo de declaración **sin declarar nada**.
> Ejecutar SOLO con Fases 4–6 verdes, avisando antes al usuario ("mira la pantalla ahora").
> Rige **lista blanca**: los únicos clicks permitidos son los de esta tabla, en este orden.
> Cualquier otra pantalla/botón ⇒ `page.pause()`, pantallazo a `capturas/`, preguntar al usuario.

| # | Click permitido (texto literal) | Qué aparece después |
|---|---|---|
| 3.1a | Servicios online → **«Impuestos mensuales»** | menú de impuestos mensuales |
| 3.1b | **«Declaración mensual (F29)»** | opciones de declaración |
| 3.1c | **«Declarar IVA (F29)»** | selector de período (⚠️ es navegación, no envío — permitido) |
| 3.2 | **«Aceptar»** (dejando el mes predeterminado) | continúa el flujo |
| 3.3 | **«Continuar»** | pantalla de información adicional |
| 3.4 | checkbox **«Confirmar que no hay información adicional a incorporar»** | habilita el paso siguiente |
| 3.5 | **«Confirmar que no debo completar»** | pantalla **«PROPUESTA DE DECLARACIÓN FORMULARIO 29»** (texto tipo: *"Estimado(a) [razón social]… tienes una declaración… correspondiente al periodo [MM-AAAA]. Revisa el detalle de tu propuesta…"*) |
| 3.7 | **«Ingresar aquí»** | se abre el **F29 propuesto** (tabla de casillas) |
| 3.8 | *(sin clicks)* leer casilla **`504`** «Remanente Crédito Fiscal mes anterior» | si no aparece ⇒ no hay remanente (P3 = 0 para ese período) |
| 3.9 | *(sin clicks)* leer casilla **`115`** — subsección **PPM**, columna **«Tasa»** | tasa propia del cliente (% con un decimal) |
| fin | **Cerrar el navegador** | ❌ NUNCA botones de envío/pago (R3) |

Imprimir solo: `504 = $N (o "no aparece")` · `115 = X %` · período de la propuesta. Estos valores
son del **período actual** (no sirven para recalcular abril; son la demostración de M3).

**Opción B (alternativa para las entradas de abril, no validada por GCP):** el F29 **declarado**
de abril puede consultarse en *Impuestos mensuales → Consulta y seguimiento (F29)* y leerse ahí
504/115. Ruta no validada — solo explorarla supervisado y con lista negra activa.

---

## §10 · Fase 8 (extensión) — Boletas de honorarios y RRHH (casillas 151 y 48)

Para **Cliente 1 ambas son $0** (perfil: sin honorarios, sin trabajadores — doc 17 §5 paso 0), así
que **no bloquean el spike**. Ejecutarlas solo si el usuario quiere la demostración completa:

**Casilla 151 — boletas de honorarios (clic a clic, doc 17 §4 P5.b):**
1. Servicios online → **«Boleta de honorarios electrónica»** → **«Emitir boleta»** *(es el acceso a consultas)* →
   **«Consulta sobre la boleta electrónica»** → **«Consultar boletas recibidas»**.
2. Modo de consulta: **«Año»** = año en curso.
3. Se muestra el **«Informe anual de boletas de honorarios electrónicas recibidas»** (una fila por
   mes; columnas: emisiones vigentes/anuladas, honorario bruto, **retención de terceros**, total líquido).
4. Tomar la **fila del mes del período** y leer **«Retención de terceros»** = `ret_honorarios` → 151.
5. Si el cliente no recibe boletas: `ret_honorarios = 0` (no se llena).

**Casilla 48 — impuesto único (Notion, único dato fuera del SII, doc 17 §4 P5.c):**
1. Leer de la base central el rollup **`IMPUESTO ÚNICO`** (y `MONTO IMPOSICIONES|` como referencia)
   — vienen de `RRHH <MES>` vía la relación `RRHH Origen` ([`18`](18-integracion-impuesto-unico-imposiciones.md)).
2. Se **transcribe**, no se calcula. Sin trabajadores ⇒ 0.

---

## §11 · Contingencias (tabla de decisión)

| Situación | Acción |
|---|---|
| Notion 429 | Esperar **≥60 s**, máx. 3 reintentos; si persiste, avisar al usuario y pausar |
| Login falla / captcha / 2FA / clave bloqueada | **Abortar** (R2). Reportar la pantalla vista (sin credenciales) y esperar instrucciones |
| SII en mantención (madrugadas/fines de semana suele haber ventanas) | Reportar y reprogramar con el usuario |
| Pantalla «Escoja cómo desea ingresar» | Paso 0.5: «Ingresar a mi información tributaria personal (Continuar)» |
| Modal/popup inesperado (encuestas, avisos) | Si tiene solo «Cerrar»/«X»: cerrarlo con `click_seguro`. Si ofrece acciones: R8 (pausar y preguntar) |
| Sesión SII expira a mitad de flujo | NO re-loguear automáticamente (R2). Avisar al usuario y decidir juntos |
| Selectores de login/período no existen | `page.pause()` → el usuario hace ese paso a mano una vez → registrar el selector real → actualizar `sii_robot.py` |
| El XHR esperado no aparece / JSON con otra forma | `resumen_capturas()` + Grep sobre `data/`; ajustar el parser. No adivinar (R8) |
| RCV de abril vacío | Verificar período fijado; si realmente está vacío, preguntar al usuario |
| `playwright install` o wheels fallan en Python 3.14 | §5 contingencias (Python 3.12 o robot en Node) |
| El usuario intenta escribir la clave en el chat | Detenerlo de inmediato (R1) y recordarle que el script la lee solo de Notion |

---

## §12 · Verificación final — golden test (ABRIR SOLO EN FASE 6, regla R4)

Valores del caso real `CLIENTE1 · abril 2026`, validados contra la propuesta del SII
(fuentes: [`17`](17-especificacion-literal-calculo-f29.md) §5 · [`01`](01-dominio-F29.md) §4 · [`02`](02-estado-del-proyecto.md)):

| Concepto | Esperado | Casillas |
|---|---|---|
| P1 débito — 3 comprobantes de pago electrónico (TpoDoc 48) | **$462** | 502 = 462 · 503 = 3 · 538 = 462 |
| P2 crédito — 11 facturas | **−$260.143** | 520 = 260.143 · 519 = 11 · 537 = 260.143 + 504 |
| BI del PPM (neto + exento) | **$2.432** | — |
| Remanente anterior (ENTRADA del usuario) | $158.117 | 504 = 158.117 |
| Tasa PPM (ENTRADA del usuario) | 0,125 % | 115 |
| P4 IVA determinado | **−$417.798** | 89 = 0 · 77 = 417.798 |
| PPM | **$3** | 62 = 3 · 595 = 3 |
| **P6 total a pagar** | **$3** | **91 = 3** · 92/93 = 0 |

**Éxito del spike = M1 reproduce P1/P2/BI al peso + M2 reproduce P4/PPM/P6 y todas las casillas al peso.**
*(Nota: `537` = crédito + remanente = 260.143 + 158.117 = 418.260 según el mapeo literal del F29 —
así lo calcula `motor_f29.py`; el doc 17 §5 tabula el crédito puro. Si difiere del F29 declarado
real, reportarlo como hallazgo de mapeo — está en la lista de pendientes del doc 17 §7.)*

---

## §13 · Fase 9 — Informe final y limpieza

1. Crear **`docs/dev/21-resultado-spike-f29.md`** con esta estructura:
   - **Resultado:** ÉXITO / PARCIAL / FALLO + tabla comparativa completa (§12 vs calculado).
   - **Selectores y URLs reales** encontrados (login, período, pestañas) — insumo del motor definitivo.
   - **Estructura JSON real del RCV**: endpoints, nombres de campo, forma de la respuesta (sin datos, solo esquema).
   - **Tiempos y fricciones**: qué requirió `page.pause()`, qué falló, cuántas iteraciones.
   - **Lecciones y riesgos** para las Fases 2–4 del [`ROADMAP`](../ROADMAP.md).
2. Actualizar [`README.md`](README.md) (índice: doc 20 → ✅ o estado real, agregar doc 21) y
   [`11-checklist-maestro.md`](11-checklist-maestro.md) si corresponde.
3. **Limpieza de PII:** borrar de `spike_f29/data/` y `capturas/` todo lo que no se necesite;
   verificar con `git status` que **nada** de `data/`, `capturas/` ni credenciales aparece para commit.
4. Preguntar al usuario si desea commitear el código del spike (solo código, jamás datos).

---

## §14 · Checklist de éxito total (marcar al final)

- [ ] Fase 1: entorno instalado y verificado
- [ ] Fase 2: credenciales confirmadas sin exponerlas (R1) · entradas 504/115 de abril obtenidas del usuario
- [ ] Fase 4: login con un solo intento, identidad confirmada por el usuario (R2/R6)
- [ ] Fase 5: P1/P2/BI extraídos de los XHR, con regla TpoDoc 61/914 aplicada
- [ ] Fase 6: motor reproduce el golden **al peso** (§12)
- [ ] Fase 7: 504/115 del período actual leídos con lista blanca intacta (R3)
- [ ] Cero credenciales/PII impresas en toda la sesión (R1/R5)
- [ ] `PRUEBA1.*` jamás abierto (R4)
- [ ] Fase 9: doc 21 escrito, índice actualizado, `data/` depurado, git limpio

---

**Anterior:** [`19-registro-variables-f29.md`](19-registro-variables-f29.md) · **Volver al** [`README`](README.md)
