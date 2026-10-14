"""Motor principal: modelo de programación con restricciones (OR-Tools CP-SAT).

Variables
---------
x[t, d, h]     1 si la tarea t (grupo+materia+profesor) tiene clase el día d a la hora h.
z[t, r, d, h]  1 si esa hora se imparte en el salón r.
y[t, r]        1 si el salón r es "el" salón de la tarea (cuando mismo_salon_por_materia).

Restricciones duras
-------------------
* Σ_dh x[t,d,h] = horas_semanales(t)
* Σ_t∈grupo x ≤ 1, Σ_t∈profesor x ≤ 1, Σ_t z[t,r,d,h] ≤ 1   (sin traslapes)
* Σ_r z[t,r,d,h] = x[t,d,h]  y z solo existe para salones del tipo correcto
* x = 0 en franjas no disponibles del profesor
* Por día: a lo más max_horas_dia horas y un único bloque continuo.

Objetivo (suave)
----------------
min  w_g·huecos_grupo + w_p·huecos_profesor + w_t·horas_fuera_de_turno
"""

from __future__ import annotations

from ortools.sat.python import cp_model

from app.schemas import Dia
from app.solver.problem import Problema, Solucion, en_turno


def _huecos(model: cp_model.CpModel, ocup: list, nombre: str) -> list:
    """Devuelve variables de hueco para una secuencia de ocupación 0/1 de un día.

    Hay hueco en h si no hay clase en h pero sí antes y después.
    """
    n = len(ocup)
    if n < 3:
        return []
    antes = [model.new_bool_var(f"{nombre}_a{i}") for i in range(n)]
    despues = [model.new_bool_var(f"{nombre}_d{i}") for i in range(n)]
    model.add(antes[0] == 0)
    model.add(despues[n - 1] == 0)
    for i in range(1, n):
        model.add(antes[i] >= antes[i - 1])
        model.add(antes[i] >= ocup[i - 1])
    for i in range(n - 2, -1, -1):
        model.add(despues[i] >= despues[i + 1])
        model.add(despues[i] >= ocup[i + 1])
    huecos = []
    for i in range(1, n - 1):
        g = model.new_bool_var(f"{nombre}_g{i}")
        model.add(g >= antes[i] + despues[i] - ocup[i] - 1)
        huecos.append(g)
    return huecos


def resolver(p: Problema) -> tuple[str, Solucion]:
    cfg = p.config
    m = cp_model.CpModel()
    dias: list[Dia] = p.dias
    horas = p.horas

    x: dict[tuple[int, Dia, int], cp_model.IntVar] = {}
    z: dict[tuple[int, str, Dia, int], cp_model.IntVar] = {}

    for t in p.tareas:
        ys = {}
        if cfg.mismo_salon_por_materia:
            ys = {r: m.new_bool_var(f"y_{t.idx}_{r}") for r in t.salones}
            m.add_exactly_one(ys.values())
        for d in dias:
            fila = []
            for h in horas:
                v = m.new_bool_var(f"x_{t.idx}_{d}_{h}")
                x[t.idx, d, h] = v
                fila.append(v)
                if not p.disponible(t.profesor, d, h):
                    m.add(v == 0)
                zs = []
                for r in t.salones:
                    zr = m.new_bool_var(f"z_{t.idx}_{r}_{d}_{h}")
                    z[t.idx, r, d, h] = zr
                    zs.append(zr)
                    if ys:
                        m.add_implication(zr, ys[r])
                m.add(sum(zs) == v)
            # Máximo de horas por día y un solo bloque continuo.
            m.add(sum(fila) <= t.max_dia)
            inicios = [fila[0]]
            for i in range(1, len(fila)):
                s = m.new_bool_var(f"s_{t.idx}_{d}_{i}")
                m.add(s >= fila[i] - fila[i - 1])
                inicios.append(s)
            m.add(sum(inicios) <= 1)
        m.add(sum(x[t.idx, d, h] for d in dias for h in horas) == t.horas)

    # Sin traslapes: grupo, profesor y salón.
    obj = []
    pesos = cfg.pesos
    for nombre, grupos in (("g", p.por_grupo()), ("p", p.por_profesor())):
        for clave, tareas in grupos.items():
            for d in dias:
                ocup = []
                for h in horas:
                    expr = sum(x[t.idx, d, h] for t in tareas)
                    m.add(expr <= 1)
                    if len(tareas) == 1:
                        ocup.append(x[tareas[0].idx, d, h])
                    else:
                        o = m.new_bool_var(f"o{nombre}_{clave}_{d}_{h}")
                        m.add(o == expr)
                        ocup.append(o)
                peso = pesos.huecos_grupo if nombre == "g" else pesos.huecos_profesor
                if peso:
                    obj += [peso * g for g in _huecos(m, ocup, f"h{nombre}_{clave}_{d}")]

    for r in p.salones:
        for d in dias:
            for h in horas:
                vs = [z[t.idx, r, d, h] for t in p.tareas if (t.idx, r, d, h) in z]
                if len(vs) > 1:
                    m.add_at_most_one(vs)

    if pesos.fuera_de_turno:
        for t in p.tareas:
            for d in dias:
                for h in horas:
                    if not en_turno(t.profesor, h):
                        obj.append(pesos.fuera_de_turno * x[t.idx, d, h])

    if obj:
        m.minimize(sum(obj))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = cfg.tiempo_limite_s
    solver.parameters.num_workers = 8
    solver.parameters.random_seed = 7
    status = solver.solve(m)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return ("infactible" if status == cp_model.INFEASIBLE else "sin_solucion"), {}

    sol: Solucion = {}
    for (ti, r, d, h), zr in z.items():
        if solver.value(zr):
            sol[ti, d, h] = r
    return ("optimo" if status == cp_model.OPTIMAL else "factible"), sol
