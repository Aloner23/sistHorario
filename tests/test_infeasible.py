"""Detección y explicación de entradas infactibles."""

from __future__ import annotations

import pytest

from app.schemas import Estado
from app.solver import resolver
from tests.conftest import MOTORES, mini, solicitud


def _codigos(r) -> set[str]:
    return {d.codigo for d in r.diagnosticos}


def test_sin_laboratorio():
    data = mini(salones=[{"id": "A1", "tipo": "aula"}])
    r = resolver(solicitud(data))
    assert r.estado == Estado.infactible
    assert "sin_salon_compatible" in _codigos(r)
    assert "M2" in r.diagnosticos[0].entidades
    assert r.horario == []


def test_capacidad_de_salon():
    data = mini(
        grupos=[{"id": "G1", "carrera": "C", "semestre": 1, "alumnos": 50}],
        salones=[{"id": "A1", "tipo": "aula", "capacidad": 30}, {"id": "L1", "tipo": "laboratorio"}],
    )
    r = resolver(solicitud(data))
    assert "sin_salon_compatible" in _codigos(r)


def test_profesor_sobrecargado():
    data = mini()
    data["profesores"][0]["no_disponible"] = [
        {"dia": d, "inicio": 7, "fin": 12} for d in ["lun", "mar", "mie", "jue", "vie"]
    ]
    # Solo queda 12-13 cada día = 5 h, pero P1 necesita 4 -> factible; subimos a 6.
    data["materias"][0]["horas_semanales"] = 6
    data["materias"][0]["max_horas_dia"] = 2
    r = resolver(solicitud(data))
    assert r.estado == Estado.infactible
    assert "profesor_sobrecargado" in _codigos(r)


def test_materia_no_cabe_en_la_semana():
    data = mini()
    data["materias"][0].update(horas_semanales=12, max_horas_dia=2)
    r = resolver(solicitud(data))
    assert "materia_no_cabe" in _codigos(r)


def test_grupo_sobrecargado():
    data = mini(configuracion={"hora_inicio": 7, "hora_fin": 8, "dias": ["lun", "mar"]})
    r = resolver(solicitud(data))
    assert r.estado == Estado.infactible
    assert "grupo_sobrecargado" in _codigos(r)


def _conflicto() -> dict:
    # Tres grupos con una sola aula y profesores disponibles solo lun y mar
    # (7-9 h). Cada recurso por separado alcanza, pero los tres juntos
    # necesitan 6 h de aula en una ventana que solo tiene 4.
    solo_lun_mar = [{"dia": d, "inicio": 7, "fin": 9} for d in ["mie", "jue", "vie"]]
    return mini(
        profesores=[{"id": f"P{i}", "nombre": f"P{i}", "no_disponible": solo_lun_mar} for i in range(3)],
        grupos=[{"id": f"G{i}", "carrera": "C", "semestre": i + 1} for i in range(3)],
        materias=[{"clave": "M1", "nombre": "Mate", "horas_semanales": 2, "tipo": "aula", "max_horas_dia": 1}],
        salones=[{"id": "A1", "tipo": "aula"}],
        asignaciones=[{"grupo": f"G{i}", "materia": "M1", "profesor": f"P{i}"} for i in range(3)],
        configuracion={"hora_inicio": 7, "hora_fin": 9, "tiempo_limite_s": 2},
    )


@pytest.mark.skipif("cpsat" not in MOTORES, reason="ortools no instalado")
def test_conflicto_combinado_detectado_por_cpsat():
    r = resolver(solicitud(_conflicto(), "cpsat"))
    assert r.estado == Estado.infactible
    assert _codigos(r) == {"conflicto_combinado"}


def test_heuristico_no_afirma_infactibilidad_sin_prueba():
    r = resolver(solicitud(_conflicto(), "heuristico"))
    assert r.estado == Estado.sin_solucion
    assert r.diagnosticos
