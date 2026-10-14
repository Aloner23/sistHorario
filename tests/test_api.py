"""Pruebas de la API con TestClient."""

from __future__ import annotations

import pytest

from tests.conftest import MOTORES, mini


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert isinstance(body["cpsat"], bool)


def test_demo_es_entrada_valida(client):
    demo = client.get("/v1/examples/demo").json()
    assert {"profesores", "materias", "salones", "grupos", "asignaciones"} <= demo.keys()
    r = client.post("/v1/schedules/solve", json=demo)
    assert r.status_code == 200
    body = r.json()
    assert body["estado"] in ("optimo", "factible")
    assert body["verificacion"]["valido"] is True
    assert body["horario"]
    assert {"grupo", "materia", "profesor", "salon", "dia", "inicio", "fin"} <= body["horario"][0].keys()


@pytest.mark.parametrize("motor", MOTORES)
def test_elegir_motor(client, motor):
    data = mini()
    data["configuracion"]["motor"] = motor
    body = client.post("/v1/schedules/solve", json=data).json()
    assert body["motor"] == motor
    assert body["verificacion"]["valido"]


def test_infactible_devuelve_200_con_diagnostico(client):
    body = client.post("/v1/schedules/solve", json=mini(salones=[{"id": "A1", "tipo": "aula"}])).json()
    assert body["estado"] == "infactible"
    assert body["diagnosticos"][0]["codigo"] == "sin_salon_compatible"
    assert body["metricas"] is None


@pytest.mark.parametrize(
    ("cambio", "fragmento"),
    [
        ({"asignaciones": [{"grupo": "G1", "materia": "NOPE", "profesor": "P1"}]}, "materia 'NOPE' no existe"),
        ({"profesores": [{"id": "P1", "nombre": "a"}, {"id": "P1", "nombre": "b"}]}, "id repetido"),
        ({"configuracion": {"hora_inicio": 10, "hora_fin": 9}}, "hora_fin"),
        ({"materias": [{"clave": "M1", "nombre": "x", "horas_semanales": 0}]}, "greater than or equal"),
    ],
)
def test_validacion_422(client, cambio, fragmento):
    r = client.post("/v1/schedules/solve", json=mini(**cambio))
    assert r.status_code == 422
    assert fragmento in r.text


def test_campos_desconocidos_rechazados(client):
    data = mini()
    data["profesores"][0]["edad"] = 40
    assert client.post("/v1/schedules/solve", json=data).status_code == 422


def test_frontend_y_openapi(client):
    assert "Horarios API" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200
    spec = client.get("/openapi.json").json()
    assert "/v1/schedules/solve" in spec["paths"]
