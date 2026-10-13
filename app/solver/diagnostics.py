"""Chequeos rápidos de infactibilidad antes de invocar al motor.

Cada chequeo es una condición *necesaria*: si falla, no existe horario
válido, y el mensaje explica exactamente por qué. Si todos pasan el problema
aún puede ser infactible por una combinación de restricciones; en ese caso el
motor lo detecta y se devuelve un diagnóstico general.
"""

from __future__ import annotations

from collections import defaultdict

from app.schemas import Diagnostico
from app.solver.problem import Problema


def precheck(p: Problema) -> list[Diagnostico]:
    diags: list[Diagnostico] = []
    n_franjas = len(p.dias) * len(p.horas)

    # 1. Cada asignación necesita al menos un salón compatible.
    for t in p.tareas:
        if not t.salones:
            cap = f" con capacidad para {t.grupo.alumnos} alumnos" if t.grupo.alumnos else ""
            diags.append(
                Diagnostico(
                    codigo="sin_salon_compatible",
                    mensaje=(
                        f"La materia {t.materia.clave} ({t.materia.tipo.value}) del grupo "
                        f"{t.grupo.id} no tiene ningún salón de tipo {t.materia.tipo.value}{cap}."
                    ),
                    entidades=[t.materia.clave, t.grupo.id],
                )
            )

    # 2. Las horas de una materia deben caber en los días disponibles.
    for t in p.tareas:
        dias_utiles = sum(1 for d in p.dias if any(p.disponible(t.profesor, d, h) for h in p.horas))
        tope = dias_utiles * min(t.max_dia, len(p.horas))
        if t.horas > tope:
            diags.append(
                Diagnostico(
                    codigo="materia_no_cabe",
                    mensaje=(
                        f"{t.materia.clave} requiere {t.horas} h/semana pero con máximo "
                        f"{t.max_dia} h/día y {dias_utiles} días útiles solo caben {tope} h."
                    ),
                    entidades=[t.materia.clave, t.grupo.id, t.profesor.id],
                )
            )

    # 3. Ningún profesor puede tener más horas que franjas disponibles.
    for prof_id, tareas in p.por_profesor().items():
        prof = tareas[0].profesor
        libres = sum(1 for d in p.dias for h in p.horas if p.disponible(prof, d, h))
        carga = sum(t.horas for t in tareas)
        if carga > libres:
            diags.append(
                Diagnostico(
                    codigo="profesor_sobrecargado",
                    mensaje=(
                        f"El profesor {prof.nombre} ({prof_id}) tiene {carga} h asignadas pero "
                        f"solo {libres} h disponibles en la semana."
                    ),
                    entidades=[prof_id],
                )
            )

    # 4. Ningún grupo puede tener más horas que franjas en la semana.
    for grupo_id, tareas in p.por_grupo().items():
        carga = sum(t.horas for t in tareas)
        if carga > n_franjas:
            diags.append(
                Diagnostico(
                    codigo="grupo_sobrecargado",
                    mensaje=f"El grupo {grupo_id} necesita {carga} h pero la semana tiene {n_franjas} franjas.",
                    entidades=[grupo_id],
                )
            )

    # 5. Capacidad total por tipo de salón.
    demanda: dict[str, int] = defaultdict(int)
    for t in p.tareas:
        demanda[t.materia.tipo.value] += t.horas
    for tipo, horas in demanda.items():
        n_salones = sum(1 for s in p.salones.values() if s.tipo.value == tipo)
        oferta = n_salones * n_franjas
        if n_salones and horas > oferta:
            diags.append(
                Diagnostico(
                    codigo="capacidad_salones_insuficiente",
                    mensaje=(
                        f"Se requieren {horas} h en salones tipo {tipo} pero solo hay "
                        f"{n_salones} salón(es) = {oferta} h disponibles."
                    ),
                    entidades=[tipo],
                )
            )

    return diags


def diagnostico_generico() -> Diagnostico:
    return Diagnostico(
        codigo="conflicto_combinado",
        mensaje=(
            "Cada recurso tiene capacidad suficiente por separado, pero la combinación de "
            "restricciones (disponibilidad de profesores, salones compartidos y traslapes de "
            "grupo) no admite solución. Prueba ampliando el rango de horas, agregando salones "
            "o relajando la disponibilidad de los profesores con más carga."
        ),
    )
