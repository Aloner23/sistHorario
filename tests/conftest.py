from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

from app.demo import DEMO
from app.main import app
from app.schemas import SolicitudHorario
from app.solver import cpsat_disponible

MOTORES = ["cpsat", "heuristico"] if cpsat_disponible() else ["heuristico"]


@pytest.fixture
def demo_dict() -> dict:
    return copy.deepcopy(DEMO)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def solicitud(data: dict, motor: str = "auto", **cfg) -> SolicitudHorario:
    data = copy.deepcopy(data)
    data.setdefault("configuracion", {})
    data["configuracion"].update({"motor": motor, **cfg})
    return SolicitudHorario.model_validate(data)


def mini(**over) -> dict:
    """Instancia pequeña: 1 grupo, 2 materias, 2 profesores."""
    base = {
        "profesores": [{"id": "P1", "nombre": "Uno"}, {"id": "P2", "nombre": "Dos"}],
        "materias": [
            {"clave": "M1", "nombre": "Mate", "horas_semanales": 4, "tipo": "aula"},
            {"clave": "M2", "nombre": "Prog", "horas_semanales": 4, "tipo": "laboratorio"},
        ],
        "salones": [{"id": "A1", "tipo": "aula"}, {"id": "L1", "tipo": "laboratorio"}],
        "grupos": [{"id": "G1", "carrera": "Comp", "semestre": 1}],
        "asignaciones": [
            {"grupo": "G1", "materia": "M1", "profesor": "P1"},
            {"grupo": "G1", "materia": "M2", "profesor": "P2"},
        ],
        "configuracion": {"hora_inicio": 7, "hora_fin": 13, "tiempo_limite_s": 5},
    }
    base.update(over)
    return base
