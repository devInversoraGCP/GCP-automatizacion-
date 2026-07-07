"""Robot SII (spike) — SOLO LECTURA. Reglas R1-R3: credenciales en memoria,
un intento de login, lista negra de botones. Navegador visible (R6).

Promesa al usuario (06-jul-2026): ESTRICTAMENTE solo lectura y descarga en el SII.
Cero envíos, cero declaraciones, cero pagos, cero firmas. Lista negra permanente
en TODO click; Fase 7 con lista blanca explícita.

Anti-detección SII (07-jul-2026): el SII detecta navegadores automatizados.
Estrategia: Chrome real del sistema (channel="chrome") + stealth + typing
humanizado (keyboard.type con delays, no page.fill) + movimientos de mouse +
pausas aleatorias. El SII responde a page.fill con error 01.01.132.500.771.52.
"""
from __future__ import annotations
import json, random, re, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, BrowserContext

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

DATA = Path(__file__).parent / "data"; DATA.mkdir(exist_ok=True)
CAPT = Path(__file__).parent / "capturas"; CAPT.mkdir(exist_ok=True)
PROHIBIDOS = re.compile(r"enviar|firmar|pagar|presentar|rectificar|declarar", re.I)

URL_LOGIN = "https://zeusr.sii.cl/AUT2000/InicioAutenticacion/IngresoRutClave.html"
URL_RCV = "https://www4.sii.cl/consdcvinternetui/#/index"

# User-Agent real de Chrome estable en Windows (no el de HeadlessChrome)
UA_REAL = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36")


def lanzar_navegador(p):
    """Lanza Chrome REAL del sistema (no el Chromium headless-shell de Playwright).

    El SII detecta el Chromium empaquetado de Playwright y responde con errores
    genéricos (01.01.132.500.771.52). Usar channel="chrome" lanza el Chrome real
    instalado en el sistema — binario genuino, mucho más difícil de detectar.
    Anti-automation flags: --disable-blink-features=AutomationControlled quita la
    huella más obvia de CDP/automatización.
    """
    return p.chromium.launch(
        headless=False,
        slow_mo=300,
        channel="chrome",
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--no-first-run",
            "--no-default-browser-check",
        ],
    )


def nuevo_contexto_stealth(browser) -> BrowserContext:
    """Crea un contexto de navegador con huellas realistas (anti-detección SII)."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        locale="es-CL",
        timezone_id="America/Santiago",
        user_agent=UA_REAL,
        color_scheme="light",
        is_mobile=False,
        has_touch=False,
        java_script_enabled=True,
    )
    # playwright-stealth: enmascara navigator.webdriver, plugins, languages, WebGL, etc.
    try:
        from playwright_stealth import Stealth
        Stealth().apply_stealth_sync(context)
    except Exception as e:
        print(f"⚠ playwright-stealth no aplicado ({e}); siguiendo con UA real solamente.")
    # Refuerzo extra: parchear webdriver en cada nueva página
    def _parchear(page: Page) -> None:
        page.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
            "Object.defineProperty(navigator,'languages',{get:()=>['es-CL','es','en']});"
            "Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});"
        )
    context.on("page", _parchear)
    return context


def click_seguro(page: Page, selector_o_texto: str, descripcion: str) -> None:
    """Único camino permitido para clickear. Aplica la lista negra R3."""
    loc = (page.get_by_text(selector_o_texto, exact=False).first
           if not selector_o_texto.startswith(("#", ".", "//", "css="))
           else page.locator(selector_o_texto).first)
    texto = (loc.inner_text(timeout=5000) or "") + " " + (loc.get_attribute("value") or "")
    if PROHIBIDOS.search(texto):
        raise RuntimeError(f"🛑 R3: click bloqueado sobre '{texto.strip()[:60]}' ({descripcion})")
    loc.click()


def _espera_humana(min_s: float = 0.8, max_s: float = 2.5) -> None:
    """Pausa aleatoria que imita el tiempo de reacción humano."""
    time.sleep(random.uniform(min_s, max_s))


def _escribir_humano(page: Page, selector: str, texto: str) -> None:
    """Escribe texto tecla por tecla con delays variables (NO page.fill).
    page.fill setea el valor instantáneamente sin eventos keydown/keyup
    individuales — es la huella #1 que detecta el SII."""
    page.click(selector)
    _espera_humana(0.3, 0.8)
    page.evaluate(f"document.querySelector('{selector}').value = ''")  # limpiar
    for ch in texto:
        page.keyboard.type(ch, delay=random.randint(50, 180))
    _espera_humana(0.5, 1.5)


def _click_humano(page: Page, selector: str) -> None:
    """Mueve el mouse al elemento con trayectoria y hace click (no click instantáneo)."""
    loc = page.locator(selector).first
    box = loc.bounding_box()
    if box:
        # Mover el mouse cerca del elemento con leve offset aleatorio
        page.mouse.move(
            box["x"] + box["width"] / 2 + random.uniform(-5, 5),
            box["y"] + box["height"] / 2 + random.uniform(-3, 3),
            steps=random.randint(10, 25),
        )
        _espera_humana(0.2, 0.6)
    loc.click()


def login(page: Page, rut: str, clave: str) -> None:
    """Paso 0 de la spec (doc 17 §4). UN intento (R2). No imprime credenciales (R1).
    Typing humanizado para evadir detección anti-bot del SII."""
    page.goto(URL_LOGIN, wait_until="domcontentloaded")
    _espera_humana(1.5, 3.0)  # tiempo de "lectura" de la página

    try:
        page.wait_for_selector("#rutcntr", timeout=15000)
    except Exception:
        page.screenshot(path=str(CAPT / "login_form_no_encontrado.png"))
        ids = page.eval_on_selector_all("input", "els => els.map(e => ({id:e.id,name:e.name,type:e.type}))")
        print(f"⚠ #rutcntr no encontrado. Inputs en la página: {ids}")
        print("   Captura guardada en capturas/login_form_no_encontrado.png")
        raise RuntimeError("Selector de login no encontrado — inspecciona captura y ajusta")

    # Escribir RUT y clave tecla por tecla (humano)
    _escribir_humano(page, "#rutcntr", rut)
    _espera_humana(0.5, 1.5)
    _escribir_humano(page, "#clave", clave)
    _espera_humana(0.8, 2.0)

    # Click humanizado en "Ingresar"
    _click_humano(page, "#bt_ingresar")
    page.wait_for_load_state("networkidle")
    _espera_humana(1.0, 2.0)

    cuerpo = page.content().lower()

    # Señales de rechazo de credenciales / bloqueo / desafío
    for senal in ("clave incorrecta", "bloqueado", "captcha", "no es v", "error de autent"):
        if senal in cuerpo:
            raise RuntimeError(f"🛑 R2: login rechazado (señal: '{senal}'). ABORTAR, no reintentar.")
    # Error de servicio del SII (clave tributaria / mantención / error transitorio / anti-bot)
    for senal in ("no se puede responder a sus requerimientos",
                  "int\u00e9ntelo m\u00e1s tarde",
                  "c\u00f3digos de mensaje de error",
                  "clave tributaria"):
        if senal in cuerpo:
            page.screenshot(path=str(CAPT / "login_error_sii.png"))
            raise RuntimeError(
                f"\U0001f6d1 SII devolvi\u00f3 un error de servicio (se\u00f1al: '{senal}').\n"
                "   NO es un rechazo de credenciales — el login se acept\u00f3, pero el SII\n"
                "   no puede atender el requerimiento ahora. Captura guardada en capturas/.\n"
                "   Abortar (R2): no reintentar autom\u00e1ticamente."
            )
    # Paso 0.5: si aparece "Escoja cómo desea ingresar", entrar a la información personal
    if "escoja" in cuerpo and "ingresar" in cuerpo:
        click_seguro(page, "Continuar", "paso 0.5 ingreso a información tributaria personal")
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
