"""Corrección del solucionador: toda salida debe pasar un verificador independiente."""

from __future__ import annotations

import random
from collections import defaultdict

import pytest

from app.schemas import Estado
from app.solver import resolver
from app.solver.problem import Problema
from app.solver.validate import verificar
from tests.conftest import MOTORES, mini, solicitud


def _revisar_restricciones(data: dict, r) -> None:
    """Revisión explícita de cada restricción dura, independiente de validate.py."""
    profes = {p["id"]: p for p in data["profesores"]}
    materias = {m["clave"]: m for m in data["materias"]}
    salones = {s["id"]: s for s in data["salones"]}
    asign = {(a["grupo"], a["materia"]): a["profesor"] for a in data["asignaciones"]}

    prof_h, salon_h, grupo_h = set(), set(), set()
    horas = defaultdict(int)
    for s in r.horario:
        assert asign[(s.grupo, s.materia)] == s.profesor
        assert salones[s.salon]["tipo"] == materias[s.materia].get("tipo", "aula"), "tipo de salón"
        for h in range(s.inicio, s.fin):
            for conj, k in ((prof_h, s.profesor), (salon_h, s.salon), (grupo_h, s.grupo)):
                assert (k, s.dia, h) not in conj, f"doble asignación de {k} {s.dia} {h}"
                conj.add((k, s.dia, h))
            for f in profes[s.profesor].get("no_disponible", []):
                assert not (f["dia"] == s.dia and f["inicio"] <= h < f["fin"]), "disponibilidad"
            horas[(s.grupo, s.materia)] += 1
    for (g, m), _ in asign.items():
        assert horas[(g, m)] == materias[m]["horas_semanales"], f"horas de {m}@{g}"


@pytest.mark.parametrize("motor", MOTORES)
def test_demo_cumple_todas_las_restricciones(demo_dict, motor):
    r = resolver(solicitud(demo_dict, motor))
    assert r.estado in (Estado.optimo, Estado.factible)
    assert r.verificacion.valido, r.verificacion.violaciones
    _revisar_restricciones(demo_dict, r)
    assert r.metricas.horas_asignadas == sum(
        m["horas_semanales"]
        for m in demo_dict["materias"]
        if any(a["materia"] == m["clave"] for a in demo_dict["asignaciones"])
    )


@pytest.mark.skipif("cpsat" not in MOTORES, reason="ortools no instalado")
def test_cpsat_minimiza_huecos_y_respeta_turnos(demo_dict):
    r = resolver(solicitud(demo_dict, "cpsat"))
    assert r.estado == Estado.optimo
    assert r.metricas.huecos_grupos == 0
    assert r.metricas.horas_fuera_de_turno == 0


@pytest.mark.skipif("cpsat" not in MOTORES, reason="ortools no instalado")
def test_cpsat_no_es_peor_que_heuristico(demo_dict):
    a = resolver(solicitud(demo_dict, "cpsat"))
    b = resolver(solicitud(demo_dict, "heuristico"))
    assert a.metricas.objetivo <= b.metricas.objetivo


@pytest.mark.parametrize("motor", MOTORES)
def test_bloques_continuos_y_max_horas_dia(demo_dict, motor):
    r = resolver(solicitud(demo_dict, motor))
    max_dia = {m["clave"]: m.get("max_horas_dia", 2) for m in demo_dict["materias"]}
    por_dia = defaultdict(list)
    for s in r.horario:
        por_dia[(s.grupo, s.materia, s.dia)].append(s)
    for (_, m, _), ses in por_dia.items():
        assert len(ses) == 1, "una materia debe ser un único bloque por día"
        assert ses[0].fin - ses[0].inicio <= max_dia[m]


@pytest.mark.parametrize("motor", MOTORES)
def test_mismo_salon_por_materia(demo_dict, motor):
    r = resolver(solicitud(demo_dict, motor))
    salones = defaultdict(set)
    for s in r.horario:
        salones[(s.grupo, s.materia)].add(s.salon)
    assert all(len(v) == 1 for v in salones.values())


@pytest.mark.parametrize("motor", MOTORES)
def test_profesor_compartido_entre_grupos(motor):
    # P1 imparte la misma materia a dos grupos con un solo salón: nunca a la vez.
    data = mini(
        grupos=[{"id": "G1", "carrera": "C", "semestre": 1}, {"id": "G2", "carrera": "C", "semestre": 3}],
        asignaciones=[
            {"grupo": "G1", "materia": "M1", "profesor": "P1"},
            {"grupo": "G2", "materia": "M1", "profesor": "P1"},
        ],
    )
    r = resolver(solicitud(data, motor))
    assert r.verificacion.valido
    _revisar_restricciones(data, r)


@pytest.mark.parametrize("motor", MOTORES)
@pytest.mark.parametrize("seed", range(6))
def test_instancias_aleatorias(motor, seed):
    rnd = random.Random(seed)
    n_prof, n_grupos = rnd.randint(3, 6), rnd.randint(2, 4)
    profes = [
        {
            "id": f"P{i}",
            "nombre": f"Prof {i}",
            "turno_preferido": rnd.choice([None, "matutino", "vespertino"]),
            "no_disponible": [{"dia": rnd.choice(["lun", "mar", "mie", "jue", "vie"]), "inicio": 7, "fin": 10}],
        }
        for i in range(n_prof)
    ]
    materias, asign = [], []
    for g in range(n_grupos):
        for k in range(rnd.randint(2, 4)):
            clave = f"M{g}{k}"
            materias.append(
                {
                    "clave": clave,
                    "nombre": clave,
                    "horas_semanales": rnd.randint(2, 5),
                    "tipo": rnd.choice(["aula", "aula", "laboratorio"]),
                }
            )
            asign.append({"grupo": f"G{g}", "materia": clave, "profesor": f"P{rnd.randrange(n_prof)}"})
    data = {
        "profesores": profes,
        "materias": materias,
        "salones": [{"id": "A1", "tipo": "aula"}, {"id": "A2", "tipo": "aula"}, {"id": "L1", "tipo": "laboratorio"}],
        "grupos": [{"id": f"G{g}", "carrera": "C", "semestre": g + 1} for g in range(n_grupos)],
        "asignaciones": asign,
        "configuracion": {"tiempo_limite_s": 5},
    }
    r = resolver(solicitud(data, motor))
    assert r.estado in (Estado.optimo, Estado.factible), r.diagnosticos
    assert r.verificacion.valido, r.verificacion.violaciones
    _revisar_restricciones(data, r)


def test_verificador_detecta_violaciones(demo_dict):
    """El verificador no es complaciente: una solución alterada debe fallar."""
    s = solicitud(demo_dict)
    r = resolver(s)
    p = Problema(s)
    malas = [x.model_copy() for x in r.horario]
    malas[1] = malas[1].model_copy(update={"dia": malas[0].dia, "inicio": malas[0].inicio, "fin": malas[0].fin})
    v = verificar(p, malas)
    assert not v.valido
    assert any("doble asignación" in x or "h programadas" in x for x in v.violaciones)

    lab = next(x for x in r.horario if x.salon.startswith("LI"))
    otra = [x if x is not lab else lab.model_copy(update={"salon": "A-101"}) for x in r.horario]
    assert any("asignada a A-101" in x for x in verificar(p, otra).violaciones)
