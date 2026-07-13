"""Helper HTTP con reintentos y backoff (Fase 2, doc 27 — prevención, H6).

Un hipo transitorio de red (timeout, error de conexión, HTTP 5xx, o 429 de rate
limit) ya no pierde la operación: se reintenta con backoff exponencial. Los 4xx
"definitivos" (400/401/403/404) NO se reintentan — reintentar no ayuda y solo
demoraría el aviso de error al asesor.

Presupuesto de latencia (webhook síncrono): por defecto 3 intentos con backoff
base 0.5s → esperas de 0.5s + 1s = 1.5s extra en el peor caso *entre* intentos.
Los reintentos por 5xx/429/conexión vuelven rápido; solo un timeout real agota
el `timeout` de cada intento (raro, y si pasa 3 veces seguidas el fallo es
correcto). No loguea headers ni body (llevan token/PII); solo método + un id
corto de la URL (host + último segmento, sin querystring).
"""
from __future__ import annotations
import time
import logging
import requests

log = logging.getLogger("auditai")

# Transitorios que vale la pena reintentar (servidor caído momentáneo / rate limit).
_STATUS_REINTENTABLES = {429, 500, 502, 503, 504}


def _etiqueta_url(metodo: str, url: str) -> str:
    """host + último segmento, SIN querystring (para no loguear tokens en la URL)."""
    try:
        sin_q = url.split("?", 1)[0]
        partes = sin_q.split("/")
        host = partes[2] if len(partes) > 2 else ""
        ultimo = partes[-1][:12] if partes else ""
        return f"{metodo} {host}/…/{ultimo}"
    except Exception:
        return metodo


def _espera_retry_after(r: requests.Response) -> float | None:
    """Retry-After en segundos si viene como número entero (429/503)."""
    ra = r.headers.get("Retry-After", "")
    if ra.strip().isdigit():
        return float(ra.strip())
    return None


def request_con_reintentos(
    metodo: str, url: str, *, intentos: int = 3, backoff_base: float = 0.5, **kwargs
) -> requests.Response:
    """`requests.request` con reintentos ante fallos transitorios.

    Devuelve el `Response` final (el llamador aplica su propia lógica:
    `raise_for_status()`, chequear `status_code`, etc.). Si se agotan los
    intentos por una excepción de red, relanza la última excepción.
    """
    etiqueta = _etiqueta_url(metodo, url)
    r = None
    for i in range(intentos):
        ultimo = i == intentos - 1
        try:
            r = requests.request(metodo, url, **kwargs)
        except (requests.Timeout, requests.ConnectionError) as exc:
            if ultimo:
                log.error("%s: %s tras %d intentos, se rinde", etiqueta, type(exc).__name__, intentos)
                raise
            espera = backoff_base * (2 ** i)
            log.warning("%s: %s, reintento %d/%d en %.1fs",
                        etiqueta, type(exc).__name__, i + 1, intentos - 1, espera)
            time.sleep(espera)
            continue

        if r.status_code in _STATUS_REINTENTABLES and not ultimo:
            espera = _espera_retry_after(r) or backoff_base * (2 ** i)
            log.warning("%s: HTTP %d, reintento %d/%d en %.1fs",
                        etiqueta, r.status_code, i + 1, intentos - 1, espera)
            time.sleep(espera)
            continue

        return r

    return r  # status reintentable pero se acabaron los intentos: devolver el último
