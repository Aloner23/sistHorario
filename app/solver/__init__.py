"""Punto de entrada del solucionador: prechequeo -> motor -> verificación."""

from __future__ import annotations

import time

from app.schemas import Estado, Motor, RespuestaHorario, SolicitudHorario
from app.solver import heuristic
from app.solver.diagnostics import diagnostico_generico, precheck
from app.solver.problem import Problema
from app.solver.validate import metricas, verificar

try:  # OR-Tools es opcional: si no está instalado se usa el motor heurístico.
    from app.solver import cpsat
except ImportError:  # pragma: no cover - depende del entorno
    cpsat = None  # type: ignore[assignment]

__all__ = ["cpsat_disponible", "resolver"]


def cpsat_disponible() -> bool:
    return cpsat is not None


def _elegir(motor: Motor):
    if motor == Motor.heuristico or (motor == Motor.auto and cpsat is None):
        return "heuristico", heuristic.resolver
    if cpsat is None:
        raise RuntimeError("El motor cpsat no está disponible: instala ortools")
    return "cpsat", cpsat.resolver


def resolver(solicitud: SolicitudHorario) -> RespuestaHorario:
    t0 = time.perf_counter()
    p = Problema(solicitud)
    nombre, motor = _elegir(solicitud.configuracion.motor)

    def ms() -> int:
        return round((time.perf_counter() - t0) * 1000)

    if diags := precheck(p):
        return RespuestaHorario(estado=Estado.infactible, motor=nombre, tiempo_ms=ms(), diagnosticos=diags)

    estado, sol = motor(p)
    if not sol and p.tareas:
        diag = diagnostico_generico()
        if estado == Estado.sin_solucion:
            diag.codigo = "sin_solucion_en_tiempo"
            diag.mensaje = (
                "No se encontró un horario dentro del límite de tiempo. Puede que no exista o que "
                "se necesite más tiempo (configuracion.tiempo_limite_s)."
            )
        return RespuestaHorario(estado=Estado(estado), motor=nombre, tiempo_ms=ms(), diagnosticos=[diag])

    sesiones = p.a_sesiones(sol)
    return RespuestaHorario(
        estado=Estado.optimo if not p.tareas else Estado(estado),
        motor=nombre,
        tiempo_ms=ms(),
        horario=sesiones,
        metricas=metricas(p, sesiones),
        verificacion=verificar(p, sesiones),
    )
