from unittest.mock import MagicMock, patch

import pytest
import requests

import app as portal


@pytest.fixture
def client():
    portal.app.config["TESTING"] = True
    return portal.app.test_client()


def respuesta(status=200, body=None, json_error=False):
    r = MagicMock()
    r.status_code = status
    if json_error:
        r.json.side_effect = ValueError("no es JSON")
    else:
        r.json.return_value = body or {}
    if status >= 400:
        r.raise_for_status.side_effect = requests.exceptions.HTTPError(f"{status}")
    return r


EVENTOS = {"events": [{"id": 1, "name": "Concierto Rock", "venue": "Estadio", "date": "2025-12-15", "available_seats": 3}]}


class TestIndex:
    def test_lista_eventos_de_app1(self, client):
        with patch.object(portal.requests, "get", return_value=respuesta(body=EVENTOS)) as get:
            r = client.get("/")
        assert r.status_code == 200
        assert "Concierto Rock" in r.get_data(as_text=True)
        assert get.call_args.args[0] == portal.APP1_API_URL

    def test_app1_caida_muestra_mensaje(self, client):
        with patch.object(portal.requests, "get", side_effect=requests.exceptions.ConnectionError()):
            r = client.get("/")
        assert r.status_code == 200
        assert "No se pudo cargar la lista de eventos" in r.get_data(as_text=True)


class TestAsientos:
    def test_muestra_asientos_del_evento(self, client):
        asientos = {"seats": [{"id": 10, "seat_number": "A-1", "status": "available"}]}
        with patch.object(portal.requests, "get", side_effect=[respuesta(body=EVENTOS), respuesta(body=asientos)]) as get:
            r = client.get("/evento/1/asientos")
        assert r.status_code == 200
        assert "A-1" in r.get_data(as_text=True)
        assert get.call_args_list[1].args[0].endswith("/api/events/1/seats")

    def test_evento_inexistente_no_consulta_asientos(self, client):
        with patch.object(portal.requests, "get", return_value=respuesta(body=EVENTOS)) as get:
            r = client.get("/evento/99/asientos")
        assert "El evento especificado no fue encontrado." in r.get_data(as_text=True)
        assert get.call_count == 1

    def test_error_al_consultar_asientos(self, client):
        with patch.object(portal.requests, "get", side_effect=[respuesta(body=EVENTOS), respuesta(status=502)]):
            r = client.get("/evento/1/asientos")
        assert "No se pudo cargar la información de los asientos." in r.get_data(as_text=True)


class TestReserva:
    payload = {"seat_id": 10, "user_id": 12345678, "event_id": 1}

    def test_reserva_y_encola_facturacion(self, client):
        with patch.object(portal.requests, "post", side_effect=[respuesta(200, {}), respuesta(200, {})]) as post:
            r = client.post("/reservar_asiento", json=self.payload)

        assert r.status_code == 200
        assert "exitosamente" in r.get_json()["message"]
        (url1,), kw1 = post.call_args_list[0]
        (url2,), kw2 = post.call_args_list[1]
        assert url1 == portal.APP1_RESERVE_URL and kw1["json"] == {"seat_id": 10, "user_id": 12345678}
        assert url2 == portal.MIDDLEWARE_URL
        assert kw2["json"] == {"event_id": "1", "user_id": "12345678", "quantity": 1}

    def test_asiento_ocupado_propaga_409_y_no_factura(self, client):
        with patch.object(portal.requests, "post", return_value=respuesta(409, {"error": "Asiento no disponible"})) as post:
            r = client.post("/reservar_asiento", json=self.payload)
        assert r.status_code == 409
        assert "Asiento no disponible" in r.get_json()["error"]
        assert post.call_count == 1

    def test_error_de_app1_sin_json_no_rompe(self, client):
        # p. ej. un 502 HTML de nginx cuando ninguna réplica responde
        with patch.object(portal.requests, "post", return_value=respuesta(502, json_error=True)):
            r = client.post("/reservar_asiento", json=self.payload)
        assert r.status_code == 502
        assert "Error desconocido en App1" in r.get_json()["error"]

    def test_app1_inalcanzable_devuelve_503(self, client):
        with patch.object(portal.requests, "post", side_effect=requests.exceptions.Timeout()):
            r = client.post("/reservar_asiento", json=self.payload)
        assert r.status_code == 503

    def test_middleware_caido_mantiene_la_reserva(self, client):
        with patch.object(portal.requests, "post", side_effect=[respuesta(200, {}), requests.exceptions.ConnectionError()]):
            r = client.post("/reservar_asiento", json=self.payload)
        assert r.status_code == 200
        assert "problema al generar tu factura" in r.get_json()["message"]
