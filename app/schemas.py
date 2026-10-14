"""Modelos de entrada y salida de la API (Pydantic v2).

El vocabulario conserva el dominio de sistHorarios (profesores, materias,
salones) y agrega el concepto explícito de *grupo* (carrera + semestre) y de
*asignación* (qué profesor imparte qué materia a qué grupo).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Dia(StrEnum):
    lun = "lun"
    mar = "mar"
    mie = "mie"
    jue = "jue"
    vie = "vie"
    sab = "sab"


class TipoSalon(StrEnum):
    aula = "aula"
    laboratorio = "laboratorio"


class Turno(StrEnum):
    matutino = "matutino"
    vespertino = "vespertino"
    nocturno = "nocturno"


# Rango de horas [inicio, fin) que define cada turno.
TURNOS: dict[Turno, tuple[int, int]] = {
    Turno.matutino: (7, 13),
    Turno.vespertino: (13, 18),
    Turno.nocturno: (18, 22),
}

Hora = Annotated[int, Field(ge=0, le=24)]
Id = Annotated[str, Field(min_length=1, max_length=64)]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Franja(_Base):
    """Bloque de tiempo [inicio, fin) en un día."""

    dia: Dia
    inicio: Hora
    fin: Hora

    @model_validator(mode="after")
    def _orden(self) -> Franja:
        if self.fin <= self.inicio:
            raise ValueError("fin debe ser mayor que inicio")
        return self

    def contiene(self, dia: Dia, hora: int) -> bool:
        return self.dia == dia and self.inicio <= hora < self.fin


class Profesor(_Base):
    id: Id
    nombre: str
    turno_preferido: Turno | None = None
    no_disponible: list[Franja] = Field(
        default_factory=list, description="Franjas en las que el profesor no puede dar clase."
    )


class Materia(_Base):
    clave: Id
    nombre: str
    horas_semanales: int = Field(ge=1, le=20)
    tipo: TipoSalon = TipoSalon.aula
    max_horas_dia: int = Field(default=2, ge=1, le=6, description="Máximo de horas consecutivas por día.")


class Salon(_Base):
    id: Id
    tipo: TipoSalon = TipoSalon.aula
    capacidad: int | None = Field(default=None, ge=1)


class Grupo(_Base):
    id: Id
    carrera: str
    semestre: int = Field(ge=1, le=20)
    alumnos: int | None = Field(default=None, ge=1)


class Asignacion(_Base):
    grupo: Id
    materia: Id
    profesor: Id


class Pesos(_Base):
    """Pesos de la función objetivo (restricciones suaves)."""

    huecos_grupo: int = Field(default=10, ge=0, le=1000)
    huecos_profesor: int = Field(default=3, ge=0, le=1000)
    fuera_de_turno: int = Field(default=5, ge=0, le=1000)


class Motor(StrEnum):
    auto = "auto"
    cpsat = "cpsat"
    heuristico = "heuristico"


class Configuracion(_Base):
    dias: list[Dia] = Field(default_factory=lambda: [Dia.lun, Dia.mar, Dia.mie, Dia.jue, Dia.vie])
    hora_inicio: int = Field(default=7, ge=0, le=23)
    hora_fin: int = Field(default=21, ge=1, le=24, description="Hora en que termina la última clase.")
    mismo_salon_por_materia: bool = Field(
        default=True, description="Si es verdadero, cada asignación usa un único salón toda la semana."
    )
    tiempo_limite_s: float = Field(default=10.0, gt=0, le=60)
    motor: Motor = Motor.auto
    pesos: Pesos = Field(default_factory=Pesos)

    @model_validator(mode="after")
    def _rango(self) -> Configuracion:
        if self.hora_fin <= self.hora_inicio:
            raise ValueError("hora_fin debe ser mayor que hora_inicio")
        if len(set(self.dias)) != len(self.dias) or not self.dias:
            raise ValueError("dias debe contener al menos un día y sin repetir")
        return self

    @property
    def horas(self) -> list[int]:
        return list(range(self.hora_inicio, self.hora_fin))


def _duplicados(valores: list[str]) -> list[str]:
    vistos: set[str] = set()
    repetidos: list[str] = []
    for v in valores:
        if v in vistos and v not in repetidos:
            repetidos.append(v)
        vistos.add(v)
    return repetidos


class SolicitudHorario(_Base):
    profesores: list[Profesor]
    materias: list[Materia]
    salones: list[Salon]
    grupos: list[Grupo]
    asignaciones: list[Asignacion]
    configuracion: Configuracion = Field(default_factory=Configuracion)

    @model_validator(mode="after")
    def _integridad(self) -> SolicitudHorario:
        errores: list[str] = []
        for nombre, ids in (
            ("profesores", [p.id for p in self.profesores]),
            ("materias", [m.clave for m in self.materias]),
            ("salones", [s.id for s in self.salones]),
            ("grupos", [g.id for g in self.grupos]),
        ):
            if rep := _duplicados(ids):
                errores.append(f"{nombre} con id repetido: {', '.join(rep)}")

        profes = {p.id for p in self.profesores}
        materias = {m.clave for m in self.materias}
        grupos = {g.id for g in self.grupos}
        pares: set[tuple[str, str]] = set()
        for i, a in enumerate(self.asignaciones):
            if a.profesor not in profes:
                errores.append(f"asignaciones[{i}]: profesor '{a.profesor}' no existe")
            if a.materia not in materias:
                errores.append(f"asignaciones[{i}]: materia '{a.materia}' no existe")
            if a.grupo not in grupos:
                errores.append(f"asignaciones[{i}]: grupo '{a.grupo}' no existe")
            if (a.grupo, a.materia) in pares:
                errores.append(f"asignaciones[{i}]: la materia '{a.materia}' ya está asignada al grupo '{a.grupo}'")
            pares.add((a.grupo, a.materia))
        if errores:
            raise ValueError("; ".join(errores))
        return self


# ---------------------------------------------------------------- salida


class Sesion(BaseModel):
    """Bloque continuo de clase dentro del horario resultante."""

    grupo: str
    materia: str
    profesor: str
    salon: str
    dia: Dia
    inicio: int
    fin: int


class Diagnostico(BaseModel):
    codigo: str
    mensaje: str
    entidades: list[str] = Field(default_factory=list)


class Metricas(BaseModel):
    horas_asignadas: int
    huecos_grupos: int
    huecos_profesores: int
    horas_fuera_de_turno: int
    ocupacion_salones: float = Field(description="Porcentaje de franjas-salón ocupadas.")
    objetivo: int


class Verificacion(BaseModel):
    valido: bool
    violaciones: list[str] = Field(default_factory=list)


class Estado(StrEnum):
    optimo = "optimo"
    factible = "factible"
    infactible = "infactible"
    sin_solucion = "sin_solucion"


class RespuestaHorario(BaseModel):
    estado: Estado
    motor: str
    tiempo_ms: int
    horario: list[Sesion] = Field(default_factory=list)
    metricas: Metricas | None = None
    diagnosticos: list[Diagnostico] = Field(default_factory=list)
    verificacion: Verificacion | None = None
