"""Verificador independiente de restricciones duras y cálculo de métricas.

No comparte lógica con los motores: recibe la lista de sesiones final y la
revisa desde cero. Se usa en la respuesta de la API y en las pruebas.
"""

from __future__ import annotations

from collections import defaultdict

from app.schemas import Metricas, Sesion, Verificacion
from app.solver.problem import Problema, en_turno


def _huecos(ocupadas: set[int]) -> int:
    if not ocupadas:
        return 0
    return (max(ocupadas) - min(ocupadas) + 1) - len(ocupadas)


def verificar(p: Problema, sesiones: list[Sesion]) -> Verificacion:
    v: list[str] = []
    profes = {t.profesor.id: t.profesor for t in p.tareas}
    tareas = {(t.grupo.id, t.materia.clave): t for t in p.tareas}
    uso_prof: dict[tuple, str] = {}
    uso_salon: dict[tuple, str] = {}
    uso_grupo: dict[tuple, str] = {}
    horas_tarea: dict[tuple[str, str], int] = defaultdict(int)
    salones_tarea: dict[tuple[str, str], set[str]] = defaultdict(set)

    for s in sesiones:
        clave = (s.grupo, s.materia)
        t = tareas.get(clave)
        if t is None:
            v.append(f"Sesión de {s.materia} para {s.grupo} no corresponde a ninguna asignación")
            continue
        if s.profesor != t.profesor.id:
            v.append(f"{s.materia}@{s.grupo} impartida por {s.profesor}, se esperaba {t.profesor.id}")
        if s.dia not in p.dias or s.inicio < p.horas[0] or s.fin > p.horas[-1] + 1:
            v.append(f"{s.materia}@{s.grupo} fuera de la ventana de horario ({s.dia} {s.inicio}-{s.fin})")
        salon = p.salones.get(s.salon)
        if salon is None:
            v.append(f"Salón inexistente {s.salon}")
        elif salon.tipo != t.materia.tipo:
            v.append(f"{s.materia} ({t.materia.tipo.value}) asignada a {s.salon} ({salon.tipo.value})")
        elif s.salon not in t.salones:
            v.append(f"{s.salon} no es compatible con {s.materia}@{s.grupo} (capacidad)")
        salones_tarea[clave].add(s.salon)
        prof = profes[t.profesor.id]
        for h in range(s.inicio, s.fin):
            horas_tarea[clave] += 1
            etiqueta = f"{s.materia}@{s.grupo}"
            if not p.disponible(prof, s.dia, h):
                v.append(f"{prof.id} no está disponible {s.dia} {h}:00 ({etiqueta})")
            for uso, k, nombre in (
                (uso_prof, (s.profesor, s.dia, h), f"Profesor {s.profesor}"),
                (uso_salon, (s.salon, s.dia, h), f"Salón {s.salon}"),
                (uso_grupo, (s.grupo, s.dia, h), f"Grupo {s.grupo}"),
            ):
                if k in uso:
                    v.append(f"{nombre} con doble asignación {s.dia} {h}:00 ({uso[k]} y {etiqueta})")
                else:
                    uso[k] = etiqueta

    for clave, t in tareas.items():
        if horas_tarea[clave] != t.horas:
            v.append(f"{t.etiqueta}: {horas_tarea[clave]} h programadas, se requieren {t.horas}")
        if p.config.mismo_salon_por_materia and len(salones_tarea[clave]) > 1:
            v.append(f"{t.etiqueta} usa varios salones: {sorted(salones_tarea[clave])}")

    horas_por_dia: dict[tuple[str, str, str], set[int]] = defaultdict(set)
    for s in sesiones:
        horas_por_dia[(s.grupo, s.materia, s.dia)].update(range(s.inicio, s.fin))
    for (g, m, d), hs in horas_por_dia.items():
        t = tareas.get((g, m))
        if t is None:
            continue
        if len(hs) > t.max_dia:
            v.append(f"{m}@{g} tiene {len(hs)} h el {d}, máximo {t.max_dia}")
        if _huecos(hs):
            v.append(f"{m}@{g} está partida en varios bloques el {d}")

    return Verificacion(valido=not v, violaciones=v)


def metricas(p: Problema, sesiones: list[Sesion]) -> Metricas:
    pesos = p.config.pesos
    ocup_g: dict[tuple[str, str], set[int]] = defaultdict(set)
    ocup_p: dict[tuple[str, str], set[int]] = defaultdict(set)
    profes = {t.profesor.id: t.profesor for t in p.tareas}
    fuera = 0
    total = 0
    for s in sesiones:
        for h in range(s.inicio, s.fin):
            total += 1
            ocup_g[(s.grupo, s.dia)].add(h)
            ocup_p[(s.profesor, s.dia)].add(h)
            if not en_turno(profes[s.profesor], h):
                fuera += 1
    hg = sum(_huecos(x) for x in ocup_g.values())
    hp = sum(_huecos(x) for x in ocup_p.values())
    franjas_salon = len(p.salones) * len(p.dias) * len(p.horas)
    return Metricas(
        horas_asignadas=total,
        huecos_grupos=hg,
        huecos_profesores=hp,
        horas_fuera_de_turno=fuera,
        ocupacion_salones=round(100 * total / franjas_salon, 1) if franjas_salon else 0.0,
        objetivo=pesos.huecos_grupo * hg + pesos.huecos_profesor * hp + pesos.fuera_de_turno * fuera,
    )
