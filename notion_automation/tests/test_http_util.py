"""Tests del helper de reintentos (Fase 2.1). Se mockea requests.request y
time.sleep para no esperar ni tocar la red."""
from unittest.mock import patch, MagicMock
import requests
import http_util


def _resp(status, headers=None):
    m = MagicMock()
    m.status_code = status
    m.headers = headers or {}
    return m


def test_exito_inmediato_no_reintenta():
    with patch("http_util.requests.request", return_value=_resp(202)) as m, \
         patch("http_util.time.sleep") as sl:
        r = http_util.request_con_reintentos("POST", "https://x/y")
    assert r.status_code == 202 and m.call_count == 1 and sl.call_count == 0


def test_503_reintenta_y_tiene_exito():
    with patch("http_util.requests.request", side_effect=[_resp(503), _resp(202)]) as m, \
         patch("http_util.time.sleep") as sl:
        r = http_util.request_con_reintentos("POST", "https://x/y", intentos=3)
    assert r.status_code == 202 and m.call_count == 2 and sl.call_count == 1


def test_403_definitivo_no_reintenta():
    with patch("http_util.requests.request", return_value=_resp(403)) as m, \
         patch("http_util.time.sleep") as sl:
        r = http_util.request_con_reintentos("POST", "https://x/y", intentos=3)
    assert r.status_code == 403 and m.call_count == 1 and sl.call_count == 0


def test_timeout_persistente_relanza():
    with patch("http_util.requests.request", side_effect=requests.Timeout("t")) as m, \
         patch("http_util.time.sleep"):
        try:
            http_util.request_con_reintentos("GET", "https://x/y", intentos=3)
            assert False, "debió relanzar Timeout"
        except requests.Timeout:
            pass
    assert m.call_count == 3


def test_429_respeta_retry_after():
    esperas = []
    seq = [_resp(429, {"Retry-After": "2"}), _resp(200)]
    with patch("http_util.requests.request", side_effect=seq), \
         patch("http_util.time.sleep", side_effect=lambda s: esperas.append(s)):
        r = http_util.request_con_reintentos("GET", "https://x/y", intentos=3)
    assert r.status_code == 200 and esperas == [2.0]


def test_etiqueta_url_sin_querystring():
    # la etiqueta de log no debe incluir el querystring (donde podría ir un token)
    et = http_util._etiqueta_url("GET", "https://api.notion.com/v1/pages/abc?secret=TOKEN")
    assert "TOKEN" not in et and "secret" not in et
