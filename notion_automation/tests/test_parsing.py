"""Tests de la identificación de la fila desde el payload del webhook.
_es_uuid, _buscar_clave y _extraer_plano_notion son el punto donde un cambio de
formato del payload de Notion podría dejar de encontrar la fila."""
import app


class TestEsUuid:
    def test_uuid_valido(self):
        assert app._es_uuid("12345678-1234-1234-1234-123456789012") is True

    def test_no_uuid_por_largo(self):
        assert app._es_uuid("1234") is False

    def test_no_uuid_por_caracter(self):
        assert app._es_uuid("zzzzzzzz-1234-1234-1234-123456789012") is False


class TestBuscarClave:
    def test_string_plano(self):
        val, ruta = app._buscar_clave({"page_id": "abc"}, ["page_id"])
        assert val == "abc" and ruta == "page_id"

    def test_case_insensitive(self):
        val, _ = app._buscar_clave({"RUT": "11.111.111-1"}, ["rut"])
        assert val == "11.111.111-1"

    def test_anidado(self):
        data = {"data": {"properties": {"Rut": "22"}}}
        val, ruta = app._buscar_clave(data, ["Rut"])
        assert val == "22" and "Rut" in ruta

    def test_no_encontrado(self):
        val, ruta = app._buscar_clave({"otra": "x"}, ["page_id"])
        assert val is None and ruta == ""

    def test_objeto_propiedad_notion_rich_text(self):
        # formato objeto-propiedad de Notion (con plain_text)
        data = {"Rut": {"type": "rich_text", "rich_text": [{"plain_text": "33"}]}}
        val, _ = app._buscar_clave(data, ["Rut"])
        assert val == "33"


class TestExtraerPlanoNotion:
    def test_rich_text_sin_type(self):
        v = {"rich_text": [{"plain_text": "hola"}]}
        assert app._extraer_plano_notion(v) == "hola"

    def test_email(self):
        assert app._extraer_plano_notion({"email": "a@b.com"}) == "a@b.com"

    def test_select(self):
        assert app._extraer_plano_notion({"select": {"name": "Remanente"}}) == "Remanente"

    def test_vacio(self):
        assert app._extraer_plano_notion({}) == ""


class TestEstructuraSinPII:
    def test_solo_keys_y_tipos(self):
        # _estructura no debe devolver valores (solo nombres de tipo) -> sin PII
        data = {"Email": "secreto@cliente.com", "monto": 123456}
        estr = app._estructura(data)
        assert estr == {"Email": "str", "monto": "int"}
        assert "secreto@cliente.com" not in str(estr)
