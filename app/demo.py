"""Datos de ejemplo inspirados en el dominio de sistHorarios (carrera de Computación)."""

from __future__ import annotations

from app.schemas import SolicitudHorario

DEMO: dict = {
    "profesores": [
        {"id": "P01", "nombre": "Mtra. Laura Méndez", "turno_preferido": "matutino"},
        {
            "id": "P02",
            "nombre": "Dr. Ricardo Salas",
            "turno_preferido": "matutino",
            "no_disponible": [{"dia": "vie", "inicio": 7, "fin": 21}],
        },
        {"id": "P03", "nombre": "Ing. Sofía Ramírez", "turno_preferido": "vespertino"},
        {
            "id": "P04",
            "nombre": "Mtro. Bernardo Ortiz",
            "turno_preferido": "vespertino",
            "no_disponible": [{"dia": "lun", "inicio": 7, "fin": 12}],
        },
        {"id": "P05", "nombre": "Dra. Elena Cruz", "turno_preferido": "matutino"},
        {"id": "P06", "nombre": "Ing. Tomás Aguilar"},
    ],
    "materias": [
        {
            "clave": "COM11101",
            "nombre": "Fundamentos de Programación",
            "horas_semanales": 6,
            "tipo": "laboratorio",
            "max_horas_dia": 2,
        },
        {"clave": "COM11102", "nombre": "Cálculo Diferencial", "horas_semanales": 5, "tipo": "aula"},
        {"clave": "COM11103", "nombre": "Matemáticas Discretas", "horas_semanales": 4, "tipo": "aula"},
        {"clave": "COM11107", "nombre": "Comunicación Oral y Escrita", "horas_semanales": 3, "tipo": "aula"},
        {"clave": "COM12101", "nombre": "Estructuras de Datos", "horas_semanales": 6, "tipo": "laboratorio"},
        {"clave": "COM12102", "nombre": "Álgebra Lineal", "horas_semanales": 4, "tipo": "aula"},
        {"clave": "COM12103", "nombre": "Bases de Datos", "horas_semanales": 5, "tipo": "laboratorio"},
        {"clave": "COM16303", "nombre": "Ingeniería de Software", "horas_semanales": 4, "tipo": "aula"},
        {"clave": "COM23101", "nombre": "Inteligencia de Negocios", "horas_semanales": 4, "tipo": "laboratorio"},
        {"clave": "COM23102", "nombre": "Sistemas Operativos", "horas_semanales": 4, "tipo": "aula"},
    ],
    "salones": [
        {"id": "A-101", "tipo": "aula", "capacidad": 40},
        {"id": "A-102", "tipo": "aula", "capacidad": 35},
        {"id": "LI-Pace", "tipo": "laboratorio", "capacidad": 30},
        {"id": "LI-Turing", "tipo": "laboratorio", "capacidad": 30},
    ],
    "grupos": [
        {"id": "COMP-1", "carrera": "Computación", "semestre": 1, "alumnos": 30},
        {"id": "COMP-3", "carrera": "Computación", "semestre": 3, "alumnos": 28},
        {"id": "COMP-5", "carrera": "Computación", "semestre": 5, "alumnos": 25},
    ],
    "asignaciones": [
        {"grupo": "COMP-1", "materia": "COM11101", "profesor": "P01"},
        {"grupo": "COMP-1", "materia": "COM11102", "profesor": "P02"},
        {"grupo": "COMP-1", "materia": "COM11103", "profesor": "P05"},
        {"grupo": "COMP-1", "materia": "COM11107", "profesor": "P06"},
        {"grupo": "COMP-3", "materia": "COM12101", "profesor": "P01"},
        {"grupo": "COMP-3", "materia": "COM12102", "profesor": "P02"},
        {"grupo": "COMP-3", "materia": "COM12103", "profesor": "P03"},
        {"grupo": "COMP-5", "materia": "COM16303", "profesor": "P04"},
        {"grupo": "COMP-5", "materia": "COM23101", "profesor": "P03"},
        {"grupo": "COMP-5", "materia": "COM23102", "profesor": "P06"},
    ],
    "configuracion": {"hora_inicio": 7, "hora_fin": 21, "tiempo_limite_s": 10},
}


def demo() -> SolicitudHorario:
    return SolicitudHorario.model_validate(DEMO)
