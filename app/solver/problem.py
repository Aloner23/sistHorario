"""Representación interna del problema, compartida por todos los motores."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas import (
    TURNOS,
    Dia,
    Grupo,
    Materia,
    Profesor,
    Salon,
    Sesion,
    SolicitudHorario,
)

# Solución cruda: (índice de tarea, día, hora) -> id de salón
Solucion = dict[tuple[int, Dia, int], str]


@dataclass(frozen=True, eq=False)
class Tarea:
    """Una asignación (grupo, materia, profesor) lista para programarse."""

    idx: int
    grupo: Grupo
    materia: Materia
    profesor: Profesor
    salones: tuple[str, ...]

    @property
    def horas(self) -> int:
        return self.materia.horas_semanales

    @property
    def max_dia(self) -> int:
        return self.materia.max_horas_dia

    @property
    def etiqueta(self) -> str:
        return f"{self.materia.clave}@{self.grupo.id}"


def salon_compatible(salon: Salon, materia: Materia, grupo: Grupo) -> bool:
    if salon.tipo != materia.tipo:
        return False
    if salon.capacidad is not None and grupo.alumnos is not None:
        return salon.capacidad >= grupo.alumnos
    return True


def en_turno(profesor: Profesor, hora: int) -> bool:
    if profesor.turno_preferido is None:
        return True
    ini, fin = TURNOS[profesor.turno_preferido]
    return ini <= hora < fin


@dataclass
class Problema:
    solicitud: SolicitudHorario
    dias: list[Dia] = field(init=False)
    horas: list[int] = field(init=False)
    tareas: list[Tarea] = field(init=False)
    salones: dict[str, Salon] = field(init=False)

    def __post_init__(self) -> None:
        s = self.solicitud
        cfg = s.configuracion
        self.dias = list(cfg.dias)
        self.horas = cfg.horas
        self.salones = {x.id: x for x in s.salones}
        profes = {p.id: p for p in s.profesores}
        materias = {m.clave: m for m in s.materias}
        grupos = {g.id: g for g in s.grupos}
        self.tareas = []
        for i, a in enumerate(s.asignaciones):
            m, g = materias[a.materia], grupos[a.grupo]
            compatibles = tuple(x.id for x in s.salones if salon_compatible(x, m, g))
            self.tareas.append(Tarea(i, g, m, profes[a.profesor], compatibles))

    @property
    def config(self):
        return self.solicitud.configuracion

    def disponible(self, profesor: Profesor, dia: Dia, hora: int) -> bool:
        return not any(f.contiene(dia, hora) for f in profesor.no_disponible)

    def por_profesor(self) -> dict[str, list[Tarea]]:
        out: dict[str, list[Tarea]] = {}
        for t in self.tareas:
            out.setdefault(t.profesor.id, []).append(t)
        return out

    def por_grupo(self) -> dict[str, list[Tarea]]:
        out: dict[str, list[Tarea]] = {}
        for t in self.tareas:
            out.setdefault(t.grupo.id, []).append(t)
        return out

    def a_sesiones(self, sol: Solucion) -> list[Sesion]:
        """Convierte la solución hora-por-hora en bloques continuos."""
        sesiones: list[Sesion] = []
        orden_dia = {d: i for i, d in enumerate(self.dias)}
        for t in self.tareas:
            for d in self.dias:
                actual: Sesion | None = None
                for h in self.horas:
                    salon = sol.get((t.idx, d, h))
                    if salon is not None and actual and actual.fin == h and actual.salon == salon:
                        actual.fin = h + 1
                        continue
                    if actual:
                        sesiones.append(actual)
                        actual = None
                    if salon is not None:
                        actual = Sesion(
                            grupo=t.grupo.id,
                            materia=t.materia.clave,
                            profesor=t.profesor.id,
                            salon=salon,
                            dia=d,
                            inicio=h,
                            fin=h + 1,
                        )
                if actual:
                    sesiones.append(actual)
        sesiones.sort(key=lambda x: (x.grupo, orden_dia[x.dia], x.inicio))
        return sesiones
