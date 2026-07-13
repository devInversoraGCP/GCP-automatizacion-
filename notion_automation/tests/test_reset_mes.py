"""Tests del endpoint /reset-mes (doc 29 — reset de mes automatizado).

Cubre: guards del payload, safety switch (checkbox 'Confirmar Reset' en la
fila RESET_MES), preservación de campos estáticos, limpieza de campos dinámicos,
tolerancia a fallos por fila y guard de concurrencia. Todo mockeado: ningún
test toca la API real de Notion.
"""
from unittest.mock import patch
import pytest
import app as A
import notion_client as nc

H = {"X-AuditAI-Secret": "test-secret"}
DB_ID = "39612147-b3ea-80e7-98e6-dbe3de45b76e"
DS_ID = "09b12147-b3ea-8337-a218-87538eab23fc"
BODY = {"tipo": "contable", "database_id": DB_ID}


def _fila(page_id: str, titulo: str, confirmar: bool = False) -> dict:
    """Fila Contable de mentira con campos estáticos y dinámicos."""
    return {
        "id": page_id,
        "properties": {
            # estáticos (NUNCA deben resetearse)
            "Customers": {"type": "title", "title": [{"plain_text": titulo}]},
            "Rut": {"type": "rich_text", "rich_text": [{"plain_text": "11.111.111-1"}]},
            "Clave SII": {"type": "rich_text", "rich_text": [{"plain_text": "secreta"}]},
            "Email": {"type": "email", "email": "test@test.com"},
            # dinámicos (SÍ deben resetearse)
            "Month": {"type": "rich_text", "rich_text": [{"plain_text": "Junio 2026"}]},
            "Impuestos": {"type": "number", "number": 1000},
            "Status": {"type": "status", "status": {"name": "1) Enviado y Pendiente"}},
            "Ventas": {"type": "checkbox", "checkbox": True},
            "Fecha Envío": {"type": "date", "date": {"start": "2026-06-15"}},
            "Confirmar Reset": {"type": "checkbox", "checkbox": confirmar},
        },
    }


PID_1 = "11111111-1111-1111-1111-111111111111"
PID_2 = "22222222-2222-2222-2222-222222222222"
PID_ZZ = "99999999-9999-9999-9999-999999999999"


@pytest.fixture()
def client():
    A._dedupe.clear()
    A._resets_activos.clear()
    return A.app.test_client()


class TestGuardsPayload:
    def test_sin_secreto_da_401(self, client):
        r = client.post("/reset-mes", json=BODY, headers={"X-AuditAI-Secret": "MALO"})
        assert r.status_code == 401

    def test_tipo_desconocido_da_400(self, client):
        r = client.post("/reset-mes", json={"tipo": "banana", "database_id": DB_ID}, headers=H)
        assert r.status_code == 400

    def test_sin_database_id_da_400(self, client):
        r = client.post("/reset-mes", json={"tipo": "contable"}, headers=H)
        assert r.status_code == 400

    def test_tipo_rrhh_aun_no_implementado_da_400(self, client):
        r = client.post("/reset-mes", json={"tipo": "rrhh", "database_id": DB_ID}, headers=H)
        assert r.status_code == 400

    def test_tipo_tickets_aun_no_implementado_da_400(self, client):
        r = client.post("/reset-mes", json={"tipo": "tickets", "database_id": DB_ID}, headers=H)
        assert r.status_code == 400


class TestSafetySwitch:
    def test_reset_sin_checkbox_rechaza(self, client):
        filas = [_fila(PID_1, "Cliente Uno"), _fila(PID_ZZ, "RESET_MES", confirmar=False)]
        with patch.object(nc, "get_data_source_id", return_value=DS_ID), \
             patch.object(nc, "query_data_source", return_value=filas), \
             patch.object(A, "_lanzar_reset") as m:
            r = client.post("/reset-mes", json=BODY, headers=H)
        assert r.status_code == 400
        assert "Confirmar Reset" in r.get_data(as_text=True)
        assert not m.called

    def test_reset_sin_fila_control_rechaza(self, client):
        filas = [_fila(PID_1, "Cliente Uno", confirmar=True)]  # sin RESET_MES
        with patch.object(nc, "get_data_source_id", return_value=DS_ID), \
             patch.object(nc, "query_data_source", return_value=filas), \
             patch.object(A, "_lanzar_reset") as m:
            r = client.post("/reset-mes", json=BODY, headers=H)
        assert r.status_code == 400
        assert not m.called

    def test_tipo_y_db_por_headers_como_boton_notion(self, client):
        # el botón de Notion no permite body custom: tipo y db van en headers
        # y el body es el payload de la fila que manda Notion (se ignora)
        filas = [_fila(PID_ZZ, "RESET_MES", confirmar=True)]
        headers = {**H, "X-Reset-Tipo": "contable", "X-Reset-DB": DB_ID}
        with patch.object(nc, "get_data_source_id", return_value=DS_ID), \
             patch.object(nc, "query_data_source", return_value=filas), \
             patch.object(A, "_lanzar_reset") as m:
            r = client.post("/reset-mes", json={"source": {"page_id": PID_ZZ}}, headers=headers)
        assert r.status_code == 202
        assert m.call_args[0][0] == "contable" and m.call_args[0][1] == DS_ID

    def test_reset_con_checkbox_lanza_el_reset(self, client):
        filas = [_fila(PID_1, "Cliente Uno"), _fila(PID_ZZ, "RESET_MES", confirmar=True)]
        with patch.object(nc, "get_data_source_id", return_value=DS_ID), \
             patch.object(nc, "query_data_source", return_value=filas), \
             patch.object(A, "_lanzar_reset") as m:
            r = client.post("/reset-mes", json=BODY, headers=H)
        assert r.status_code == 202
        body = r.get_json()
        assert body["ok"] is True and body["en_proceso"] is True
        assert body["tipo"] == "contable" and body["filas_totales"] == 2
        tipo, ds_id, campos, filas_arg = m.call_args[0]
        assert tipo == "contable" and ds_id == DS_ID
        assert campos is A.RESET_CONTABLE and len(filas_arg) == 2


class TestResetAplicar:
    def test_reset_limpia_campos_dinamicos(self):
        filas = [_fila(PID_1, "Cliente Uno", confirmar=True)]
        with patch.object(nc, "update_props") as m:
            res = A._reset_aplicar("contable", DS_ID, A.RESET_CONTABLE, filas)
        assert res["filas_reseteadas"] == 1 and res["filas_fallidas"] == 0
        updates = m.call_args[0][1]
        assert updates["Month"] == {"rich_text": []}
        assert updates["Impuestos"] == {"number": None}
        assert updates["Status"] == {"status": {"name": "sin empezar"}}
        assert updates["Ventas"] == {"checkbox": False}
        assert updates["Fecha Envío"] == {"date": None}

    def test_reset_preserva_campos_estaticos(self):
        filas = [_fila(PID_1, "Cliente Uno")]
        with patch.object(nc, "update_props") as m:
            A._reset_aplicar("contable", DS_ID, A.RESET_CONTABLE, filas)
        updates = m.call_args[0][1]
        for estatico in ("Customers", "Rut", "Clave SII", "Email"):
            assert estatico not in updates

    def test_reset_desmarca_confirmar_reset(self):
        filas = [_fila(PID_ZZ, "RESET_MES", confirmar=True)]
        with patch.object(nc, "update_props") as m:
            A._reset_aplicar("contable", DS_ID, A.RESET_CONTABLE, filas)
        assert m.call_args[0][1]["Confirmar Reset"] == {"checkbox": False}

    def test_reset_solo_escribe_columnas_existentes(self):
        # una fila sin varias columnas dinámicas -> el PATCH no debe incluirlas
        fila = {
            "id": PID_1,
            "properties": {
                "Customers": {"type": "title", "title": [{"plain_text": "X"}]},
                "Impuestos": {"type": "number", "number": 5},
            },
        }
        with patch.object(nc, "update_props") as m:
            A._reset_aplicar("contable", DS_ID, A.RESET_CONTABLE, [fila])
        assert set(m.call_args[0][1]) == {"Impuestos"}

    def test_fallo_en_una_fila_no_aborta_el_resto_y_avisa_admin(self):
        filas = [_fila(PID_1, "Uno"), _fila(PID_2, "Dos")]
        with patch.object(nc, "update_props", side_effect=[RuntimeError("boom"), None]), \
             patch.object(A.alertas, "avisar_excepcion_admin") as alerta:
            res = A._reset_aplicar("contable", DS_ID, A.RESET_CONTABLE, filas)
        assert res["filas_reseteadas"] == 1 and res["filas_fallidas"] == 1
        assert alerta.called

    def test_libera_el_guard_de_concurrencia_al_terminar(self):
        A._resets_activos.add(DS_ID)
        with patch.object(nc, "update_props"):
            A._reset_aplicar("contable", DS_ID, A.RESET_CONTABLE, [_fila(PID_1, "Uno")])
        assert DS_ID not in A._resets_activos


class TestConcurrencia:
    def test_reset_ya_en_curso_se_ignora(self, client):
        filas = [_fila(PID_ZZ, "RESET_MES", confirmar=True)]
        A._resets_activos.add(DS_ID)
        with patch.object(nc, "get_data_source_id", return_value=DS_ID), \
             patch.object(nc, "query_data_source", return_value=filas), \
             patch.object(A, "_lanzar_reset") as m:
            r = client.post("/reset-mes", json=BODY, headers=H)
        assert r.status_code == 200
        assert r.get_json().get("duplicado") is True
        assert not m.called
