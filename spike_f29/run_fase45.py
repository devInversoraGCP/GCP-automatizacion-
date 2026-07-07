"""Fase 4 + 5 del spike: login SII (1 intento) + captura RCV mayo 2026.

SOLO LECTURA en el SII (promesa al usuario 06-jul-2026 + R3).
Credenciales en memoria (R1), navegador visible (R6), pausa para confirmar identidad.
"""
from __future__ import annotations
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright
import notion_lookup
import sii_robot

CLIENTE = "BAQUI SPA - FRANCISCO"   # nombre exacto en Notion (verificado Fase 2)
PERIODO = "2026-05"                  # mayo 2026


def main() -> None:
    # R1: credenciales SOLO en memoria, nunca se imprimen
    cred = notion_lookup.credenciales_cliente(CLIENTE)
    print("✅ Credenciales cargadas en memoria:", notion_lookup.descripcion_segura(cred))

    with sync_playwright() as p:
        browser = sii_robot.lanzar_navegador(p)                 # Chrome real del sistema
        context = sii_robot.nuevo_contexto_stealth(browser)        # anti-detección SII
        page = context.new_page()

        # ── Fase 4: login (1 intento, R2) ──────────────────────────────
        print("\n🌐 Abriendo navegador y haciendo login en el SII (1 intento)...")
        sii_robot.login(page, cred["rut"], cred["clave"])

        # Pausa R6/paso 0.6: el usuario confirma identidad mirando la pantalla
        print("\n" + "=" * 64)
        print("⏸  PAUSA — GATE DE IDENTIDAD (R6, paso 0.6 de la spec)")
        print(f"   Mira el navegador: en la esquina superior debe decir")
        print(f"   el nombre del contribuyente = '{cred['nombre']}'.")
        print("   · Si SÍ coincide  → presiona Resume ▶ en la barra verde")
        print("     del Playwright Inspector para continuar a la Fase 5.")
        print("   · Si NO coincide → cierra el navegador y avísame; ABORTAR.")
        print("=" * 64 + "\n")
        page.pause()

        # ── Fase 5: capturar RCV período 2026-05 ────────────────────────
        print(f"📥 Fase 5: capturando RCV período {PERIODO} (pestañas VENTA + COMPRA)...")
        rutas = sii_robot.capturar_rcv(page, PERIODO)

        print(f"\n📋 Resumen de los {len(rutas)} JSON capturados (solo esquema, sin PII):")
        sii_robot.resumen_capturas(rutas)

        print(f"\n✅ Fases 4+5 completas. {len(rutas)} JSON guardados en spike_f29/data/")
        print("   (cierra el navegador si no se cerró solo).")
        context.close()
        browser.close()


if __name__ == "__main__":
    main()
