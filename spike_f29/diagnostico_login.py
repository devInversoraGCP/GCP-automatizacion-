"""Diagnóstico: ¿es el navegador o la automatización?

Abre Chrome real controlado por Playwright, va al login del SII, y PAUSA.
El usuario hace login A MANO en ese navegador (RUT + clave + click Ingresar).
- Si el error aparece → el SII detecta el NAVEGADOR (fingerprinting profundo).
- Si el login funciona → el SII detecta la AUTOMATIZACIÓN (fill/click de Playwright).

SOLO LECTURA. Cero automatización de clicks. El usuario controla todo.
"""
from __future__ import annotations
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright
import sii_robot

URL_LOGIN = "https://zeusr.sii.cl/AUT2000/InicioAutenticacion/IngresoRutClave.html"


def main() -> None:
    print("🔍 DIAGNÓSTICO: ¿navegador o automatización?")
    print()
    with sync_playwright() as p:
        browser = sii_robot.lanzar_navegador(p)
        context = sii_robot.nuevo_contexto_stealth(browser)
        page = context.new_page()

        print(f"1. Navegando a {URL_LOGIN} ...")
        page.goto(URL_LOGIN, wait_until="domcontentloaded")
        print("   Página de login cargada.")

        print()
        print("=" * 64)
        print("⏸  PAUSA DE DIAGNÓSTICO")
        print("   Ahora TÚ haces el login a mano en el navegador que se abrió:")
        print("   1. Escribe el RUT en 'RUT Usuario'")
        print("   2. Escribe la clave en 'Clave'")
        print("   3. Click 'Ingresar'")
        print()
        print("   Observa qué pasa:")
        print("   · Si aparece el error 01.01.132.500.771.52 → el SII detecta")
        print("     el NAVEGADOR (fingerprinting). Tendremos que ir por modo CDP.")
        print("   · Si el login funciona → el SII detecta la AUTOMATIZACIÓN.")
        print("     Abriremos el inspector (F12) para ver qué huellas quedan.")
        print()
        print("   Cuando termines de observar, presiona Resume ▶ en la barra")
        print("   verde del Playwright Inspector para cerrar.")
        print("=" * 64)
        print()
        page.pause()

        # Después de resume: capturar estado para análisis
        url_actual = page.url
        titulo = page.title()
        print(f"📍 URL final: {url_actual}")
        print(f"📍 Título: {titulo}")
        page.screenshot(path=str(sii_robot.CAPT / "diagnostico_despues_login.png"))
        print("📸 Captura guardada en capturas/diagnostico_despues_login.png")
        # Guardar HTML para análisis offline (sin PII en consola)
        html = page.content()
        (sii_robot.CAPT / "diagnostico_pagina.html").write_text(html, encoding="utf-8")
        print("📄 HTML guardado en capturas/diagnostico_pagina.html")
        # Buscar señales en el HTML
        cuerpo = html.lower()
        if "no se puede responder" in cuerpo:
            print("🔴 Resultado: el SII detectó el NAVEGADOR (mismo error con login manual).")
            print("   → Próximo paso: modo CDP (usuario abre su propio Chrome, robot se conecta).")
        elif "cerrar sesi" in cuerpo or "mi sii" in cuerpo or "contribuyente" in cuerpo:
            print("🟢 Resultado: login manual funcionó → el SII detecta la AUTOMATIZACIÓN.")
            print("   → Próximo paso: refinar anti-detección del fill/click o usar CDP.")

        context.close()
        browser.close()


if __name__ == "__main__":
    main()
