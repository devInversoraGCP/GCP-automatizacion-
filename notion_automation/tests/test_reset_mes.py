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
            "Adjuntos": {"type": "files", "files": [{"name": "F29 junio.pdf", "type": "file"}]},
            "Mensaje Adjuntos": {"type": "rich_text", "rich_text": [{"plain_text": "adjunto el F29"}]},
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


@pytest.fixture(autouse=True)
def _sin_api_real(monkeypatch):
    """Ningún test de este módulo puede salir a la API de Notion.

    Por defecto: el título de la base no se puede leer ('') — así el tipo cae al
    header, que es como llegan los tests de payload — y la planilla vigente de
    cada flujo es la operativa. Los tests que prueban la resolución por la fila
    del clic sobrescriben `get_page` / `get_database_title` con lo suyo."""
    def _sin_fila(*a, **k):
        raise RuntimeError("un test leyó una fila real; parchea nc.get_page")

    monkeypatch.setattr(nc, "get_page", _sin_fila)
    monkeypatch.setattr(nc, "get_database_title", lambda db_id: "")
    monkeypatch.setattr(A, "_ds_contable_vigente", lambda: DS_ID)
    monkeypatch.setattr(A, "_ds_rrhh_vigente", lambda: RRHH_DS)


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

    def test_tipo_tickets_aun_no_implementado_da_400(self, client):
        # Tickets sigue pendiente (RESET_TICKETS vacío) -> 400
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
        assert updates["Status"] == {"status": {"name": "Not started"}}
        assert updates["Ventas"] == {"checkbox": False}
        assert updates["Fecha Envío"] == {"date": None}

    def test_reset_limpia_los_adjuntos_del_mes(self):
        """Los adjuntos son los PDFs de ESE mes, no documentos permanentes del
        cliente. Contable no los limpiaba (doc 29 los listaba como estáticos):
        en la planilla operativa había archivos de junio conviviendo con los de
        julio, o sea clientes recibiendo el PDF de otro mes. El respaldo '(1)'
        los conserva."""
        filas = [_fila(PID_1, "Cliente Uno")]
        with patch.object(nc, "update_props") as m:
            A._reset_aplicar("contable", DS_ID, A.RESET_CONTABLE, filas)
        updates = m.call_args[0][1]
        assert updates["Adjuntos"] == {"files": []}
        assert updates["Mensaje Adjuntos"] == {"rich_text": []}

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

    def test_matching_tolerante_a_mayusculas_y_espacios(self):
        # esquema REAL de Contable Junio (13-jul-2026): 'Confirmar reset' con r
        # minúscula y 'emision de boletas ' con espacio final. El reset debe
        # encontrarlas igual y escribir con el nombre REAL de la columna.
        fila = {
            "id": PID_1,
            "properties": {
                "Confirmar reset": {"type": "checkbox", "checkbox": True},
                "emision de boletas ": {"type": "status", "status": {"name": "Listo"}},
            },
        }
        with patch.object(nc, "update_props") as m:
            A._reset_aplicar("contable", DS_ID, A.RESET_CONTABLE, [fila])
        updates = m.call_args[0][1]
        assert updates["Confirmar reset"] == {"checkbox": False}
        assert updates["emision de boletas "] == {"status": {"name": "Sin empezar"}}

    def test_checkbox_confirmar_reset_con_minuscula_tambien_vale(self, client):
        # la columna real se llama 'Confirmar reset' (r minúscula)
        fila_control = _fila(PID_ZZ, "RESET_MES")
        fila_control["properties"].pop("Confirmar Reset")
        fila_control["properties"]["Confirmar reset"] = {"type": "checkbox", "checkbox": True}
        with patch.object(nc, "get_data_source_id", return_value=DS_ID), \
             patch.object(nc, "query_data_source", return_value=[fila_control]), \
             patch.object(A, "_lanzar_reset") as m:
            r = client.post("/reset-mes", json=BODY, headers=H)
        assert r.status_code == 202 and m.called

    def test_base_sin_columna_confirmar_reset_da_400(self, client):
        fila_control = _fila(PID_ZZ, "RESET_MES")
        fila_control["properties"].pop("Confirmar Reset")
        with patch.object(nc, "get_data_source_id", return_value=DS_ID), \
             patch.object(nc, "query_data_source", return_value=[fila_control]), \
             patch.object(A, "_lanzar_reset") as m:
            r = client.post("/reset-mes", json=BODY, headers=H)
        assert r.status_code == 400 and not m.called

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


# --- Fase 3: RRHH (doc 29) --------------------------------------------------
RRHH_DB = "39e12147-b3ea-807d-b238-fbac8bd2e4c6"    # 'RRHH AGOSTO 2026' (operativa)
RRHH_DS = "89a12147-b3ea-830e-adee-07cbca823fb6"
# La base de junio, de la que se duplicó la de julio: es el id que quedó pegado
# en el header del botón y que el 18-ago-2026 ya estaba en la papelera (§19).
RRHH_DB_PAPELERA = "38712147-b3ea-80f9-9484-e0ad99c94a26"
RRHH_DS_RESPALDO = "d0d12147-b3ea-820b-bae1-07e0b679699a"   # 'RRHH JULIO 2026 (1)'


def _fila_rrhh(page_id: str, rut_titulo: str, confirmar: bool = False) -> dict:
    """Fila RRHH: el title es 'RUT' (no 'Customers'). Estáticos + dinámicos."""
    return {
        "id": page_id,
        "properties": {
            # estáticos — jamás se resetean
            "RUT": {"type": "title", "title": [{"plain_text": rut_titulo}]},
            "CLIENTE": {"type": "rich_text", "rich_text": [{"plain_text": "Empresa X"}]},
            "USUARIO": {"type": "rich_text", "rich_text": [{"plain_text": "user-previred"}]},
            "CLAVE": {"type": "rich_text", "rich_text": [{"plain_text": "secreta"}]},
            "Nº. Trab.": {"type": "number", "number": 5},
            # dinámicos — se resetean
            "MONTO IMPOSICIONES|": {"type": "number", "number": 500000},
            "IMPUESTO ÚNICO": {"type": "number", "number": 12000},
            "Estado Correo": {"type": "status", "status": {"name": "Listo"}},
            "Fecha envío": {"type": "date", "date": {"start": "2026-06-13"}},
            "Previred": {"type": "status", "status": {"name": "Pagadas"}},
            "Liquidaciones": {"type": "status", "status": {"name": "Done"}},
            "Adjuntos": {"type": "files", "files": [{"name": "liq.pdf", "type": "file"}]},
            "Comentario-Adjuntos": {"type": "rich_text", "rich_text": [{"plain_text": "nota"}]},
            "Confirmar reset": {"type": "checkbox", "checkbox": confirmar},
        },
    }


class TestResetRRHH:
    def test_tipo_rrhh_lanza_el_reset(self, client):
        filas = [_fila_rrhh(PID_ZZ, "RESET_MES", confirmar=True)]
        with patch.object(nc, "get_data_source_id", return_value=RRHH_DS), \
             patch.object(nc, "query_data_source", return_value=filas), \
             patch.object(A, "_lanzar_reset") as m:
            r = client.post("/reset-mes", json={"tipo": "rrhh", "database_id": RRHH_DB}, headers=H)
        assert r.status_code == 202
        tipo, ds_id, campos, _ = m.call_args[0]
        assert tipo == "rrhh" and campos is A.RESET_RRHH

    def test_rrhh_resetea_dinamicos_y_preserva_estaticos(self):
        with patch.object(nc, "update_props") as m:
            A._reset_aplicar("rrhh", RRHH_DS, A.RESET_RRHH, [_fila_rrhh(PID_1, "12.345.678-9")])
        updates = m.call_args[0][1]
        # dinámicos reseteados
        assert updates["MONTO IMPOSICIONES|"] == {"number": None}
        assert updates["IMPUESTO ÚNICO"] == {"number": None}
        assert updates["Estado Correo"] == {"status": {"name": "Sin empezar"}}
        assert updates["Previred"] == {"status": {"name": "Not started"}}
        assert updates["Liquidaciones"] == {"status": {"name": "Not started"}}
        assert updates["Adjuntos"] == {"files": []}
        assert updates["Comentario-Adjuntos"] == {"rich_text": []}
        assert updates["Fecha envío"] == {"date": None}
        # estáticos intactos
        for estatico in ("RUT", "CLIENTE", "USUARIO", "CLAVE", "Nº. Trab."):
            assert estatico not in updates

    def test_rrhh_fila_control_por_rut_title(self, client):
        # la fila de control se detecta por el title (RUT), no por 'Customers'
        filas = [_fila_rrhh(PID_ZZ, "RESET_MES", confirmar=False)]
        with patch.object(nc, "get_data_source_id", return_value=RRHH_DS), \
             patch.object(nc, "query_data_source", return_value=filas), \
             patch.object(A, "_lanzar_reset") as m:
            r = client.post("/reset-mes", json={"tipo": "rrhh", "database_id": RRHH_DB}, headers=H)
        assert r.status_code == 400  # checkbox sin marcar
        assert not m.called


# --- La planilla sale del clic, no de la configuración del botón (§19) ------
def _page_del_clic(ds: str, db: str = "db-cualquiera") -> dict:
    """Page object como lo devuelve Notion para la fila donde se apretó el botón."""
    return {"id": PID_ZZ,
            "parent": {"type": "data_source_id", "data_source_id": ds, "database_id": db}}


class TestPlanillaDelClic:
    """Incidente 18-ago-2026 (doc 28 §19). El botón mandaba la base a resetear en
    un header; al duplicar la planilla, el header se copió con ella y quedó
    apuntando a la base del mes viejo, que después se fue a la papelera. Desde
    ahora la planilla y el tipo salen de la FILA donde se apretó el botón: no hay
    configuración manual que pueda quedar vieja."""

    def test_la_planilla_sale_de_la_fila_sin_ningun_header(self, client):
        filas = [_fila_rrhh(PID_ZZ, "RESET_MES", confirmar=True)]
        with patch.object(nc, "get_page", return_value=_page_del_clic(RRHH_DS)), \
             patch.object(nc, "get_database_title", return_value="RRHH AGOSTO 2026"), \
             patch.object(nc, "query_data_source", return_value=filas), \
             patch.object(A, "_lanzar_reset") as m:
            r = client.post("/reset-mes", json={"source": {"page_id": PID_ZZ}}, headers=H)
        assert r.status_code == 202
        tipo, ds_id, campos, _ = m.call_args[0]
        # el tipo salió del título de la base, no de X-Reset-Tipo
        assert tipo == "rrhh" and ds_id == RRHH_DS and campos is A.RESET_RRHH

    def test_la_fila_del_clic_manda_sobre_un_header_viejo(self, client):
        """El caso exacto del incidente: el header apunta a la base de junio (hoy
        en la papelera) y el clic ocurrió en la planilla de agosto."""
        filas = [_fila_rrhh(PID_ZZ, "RESET_MES", confirmar=True)]
        headers = {**H, "X-Reset-Tipo": "rrhh", "X-Reset-DB": RRHH_DB_PAPELERA}
        with patch.object(nc, "get_page", return_value=_page_del_clic(RRHH_DS)), \
             patch.object(nc, "get_database_title", return_value="RRHH AGOSTO 2026"), \
             patch.object(nc, "query_data_source", return_value=filas), \
             patch.object(nc, "get_data_source_id") as m_ds, \
             patch.object(A, "_lanzar_reset") as m:
            r = client.post("/reset-mes", json={"source": {"page_id": PID_ZZ}}, headers=headers)
        assert r.status_code == 202
        assert m.call_args[0][1] == RRHH_DS
        assert not m_ds.called   # ni se miró el id del header

    def test_si_la_fila_no_se_puede_leer_el_header_sigue_sirviendo(self, client):
        """Fallback: curl, tests, o un botón que no mande los datos de la fila."""
        filas = [_fila_rrhh(PID_ZZ, "RESET_MES", confirmar=True)]
        with patch.object(nc, "get_data_source_id", return_value=RRHH_DS), \
             patch.object(nc, "query_data_source", return_value=filas), \
             patch.object(A, "_lanzar_reset") as m:
            r = client.post("/reset-mes", json={"tipo": "rrhh", "database_id": RRHH_DB}, headers=H)
        assert r.status_code == 202 and m.call_args[0][1] == RRHH_DS

    def test_sin_fila_y_sin_header_da_400_que_se_entiende(self, client):
        with patch.object(A, "_lanzar_reset") as m:
            r = client.post("/reset-mes", json={}, headers=H)
        assert r.status_code == 400 and not m.called
        assert "page_id" in r.get_data(as_text=True)

    def test_el_respaldo_no_se_resetea(self, client):
        """El respaldo es la ÚNICA copia del mes cerrado: resetearlo es
        irreversible. El botón viaja en la copia y sigue clicable."""
        with patch.object(nc, "get_page", return_value=_page_del_clic(RRHH_DS_RESPALDO)), \
             patch.object(nc, "get_database_title", return_value="RRHH JULIO 2026 (1)"), \
             patch.object(nc, "query_data_source") as m_query, \
             patch.object(A, "_lanzar_reset") as m:
            r = client.post("/reset-mes", json={"source": {"page_id": PID_ZZ}}, headers=H)
        assert r.status_code == 403 and not m.called
        assert not m_query.called          # ni se leyó la base
        assert "respaldo" in r.get_data(as_text=True)

    def test_una_planilla_de_un_mes_cerrado_no_se_resetea(self, client):
        """Un respaldo renombrado a mano ya no tiene el sufijo '(1)', así que el
        segundo cinturón es el período: solo se resetea la planilla vigente."""
        with patch.object(nc, "get_page", return_value=_page_del_clic("ds-de-un-mes-viejo")), \
             patch.object(nc, "get_database_title", return_value="RRHH JUNIO 2026"), \
             patch.object(A, "_lanzar_reset") as m:
            r = client.post("/reset-mes", json={"source": {"page_id": PID_ZZ}}, headers=H)
        assert r.status_code == 403 and not m.called

    def test_un_reset_rechazado_avisa_al_admin(self, client):
        """El 18-ago el reset falló y se descubrió al día siguiente: el rechazo
        era invisible salvo en los logs de Render."""
        with patch.object(nc, "get_page", return_value=_page_del_clic(RRHH_DS_RESPALDO)), \
             patch.object(nc, "get_database_title", return_value="RRHH JULIO 2026 (1)"), \
             patch.object(A.alertas, "avisar_boton_rechazado") as m_aviso:
            client.post("/reset-mes", json={"source": {"page_id": PID_ZZ}}, headers=H)
        assert m_aviso.call_args[0][0] == "RESET" and m_aviso.call_args[0][1] == 403
