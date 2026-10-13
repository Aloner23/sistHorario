"""Horarios API v2 — FastAPI."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.demo import demo
from app.schemas import RespuestaHorario, SolicitudHorario
from app.solver import cpsat_disponible, resolver

STATIC = Path(__file__).parent / "static"

app = FastAPI(
    title="Horarios API",
    version=__version__,
    summary="Generador de horarios escolares con programación por restricciones (CP-SAT).",
    description=(
        "API REST que recibe profesores, materias, salones, grupos y asignaciones, y devuelve "
        "un horario semanal que respeta todas las restricciones duras, optimizando huecos y "
        "turnos preferidos. Segunda versión de "
        "[sistHorarios](https://github.com/Aloner23/sistHorarios)."
    ),
    license_info={"name": "MIT"},
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])


@app.get("/health", tags=["sistema"])
def health() -> dict:
    return {"status": "ok", "version": __version__, "cpsat": cpsat_disponible()}


@app.get("/v1/examples/demo", response_model=SolicitudHorario, tags=["ejemplos"])
def ejemplo_demo() -> SolicitudHorario:
    """Entrada de ejemplo lista para enviarse a `/v1/schedules/solve`."""
    return demo()


@app.post("/v1/schedules/solve", response_model=RespuestaHorario, tags=["horarios"])
async def resolver_horario(solicitud: SolicitudHorario) -> RespuestaHorario:
    """Genera un horario.

    * `estado = optimo | factible`: `horario` contiene las sesiones y `metricas` el costo.
    * `estado = infactible`: `diagnosticos` explica qué restricción lo impide.
    * `estado = sin_solucion`: se agotó el tiempo sin encontrar horario.
    """
    try:
        # CP-SAT es CPU-bound: se ejecuta fuera del event loop.
        return await run_in_threadpool(resolver, solicitud)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
