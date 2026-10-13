"""Motor de respaldo: búsqueda con retroceso (backtracking) y heurísticas.

Se usa cuando OR-Tools no está disponible (por ejemplo en entornos serverless
con límite de tamaño) o si se pide explícitamente con ``motor="heuristico"``.

1. Cada materia se divide en *bloques* diarios (p. ej. 5 h con máximo 2 h/día
   -> bloques de 2, 2 y 1 h), cada uno en un día distinto.
2. Se elige primero el bloque con menos opciones válidas (MRV, *minimum
   remaining values*), que es donde es más probable fallar.
3. Las opciones (día, hora, salón) se ordenan por costo suave: huecos que
   crea en el grupo/profesor y horas fuera del turno preferido.
4. Si un bloque se queda sin opciones se retrocede. Hay un límite de nodos y
   de tiempo; al agotarse se informa ``sin_solucion``.

Es exhaustivo para la descomposición fija de bloques, pero no prueba
infactibilidad en general ni garantiza el óptimo del objetivo como CP-SAT.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.schemas import Dia
from app.solver.problem import Problema, Solucion, Tarea, en_turno


@dataclass(frozen=True, eq=False)
class Bloque:
    tarea: Tarea
    n: int  # índice del bloque dentro de la tarea
    largo: int


def _bloques(t: Tarea) -> list[Bloque]:
    restantes, out = t.horas, []
    while restantes > 0:
        largo = min(t.max_dia, restantes)
        out.append(Bloque(t, len(out), largo))
        restantes -= largo
    return out


class _Busqueda:
    def __init__(self, p: Problema, max_nodos: int = 200_000) -> None:
        self.p = p
        self.deadline = time.monotonic() + p.config.tiempo_limite_s
        self.max_nodos = max_nodos
        self.nodos = 0
        self.agotado = False
        self.prof: set[tuple[str, Dia, int]] = set()
        self.grupo: set[tuple[str, Dia, int]] = set()
        self.salon: set[tuple[str, Dia, int]] = set()
        self.dias_tarea: dict[int, set[Dia]] = {}
        self.salon_tarea: dict[int, str] = {}
        self.colocados: dict[Bloque, tuple[Dia, int, str]] = {}

    def opciones(self, b: Bloque) -> list[tuple[Dia, int, str]]:
        p, t = self.p, b.tarea
        usados = self.dias_tarea.get(t.idx, set())
        salones = (
            (self.salon_tarea[t.idx],) if p.config.mismo_salon_por_materia and t.idx in self.salon_tarea else t.salones
        )
        out = []
        horas = p.horas
        for d in p.dias:
            if d in usados:
                continue
            for i in range(len(horas) - b.largo + 1):
                rango = horas[i : i + b.largo]
                if any(
                    (t.profesor.id, d, h) in self.prof
                    or (t.grupo.id, d, h) in self.grupo
                    or not p.disponible(t.profesor, d, h)
                    for h in rango
                ):
                    continue
                for r in salones:
                    if all((r, d, h) not in self.salon for h in rango):
                        out.append((d, rango[0], r))
        return out

    def costo(self, b: Bloque, op: tuple[Dia, int, str]) -> int:
        d, ini, _ = op
        t, w = b.tarea, self.p.config.pesos
        fin = ini + b.largo
        c = w.fuera_de_turno * sum(1 for h in range(ini, fin) if not en_turno(t.profesor, h))
        for clave, ocup, peso in (
            (t.grupo.id, self.grupo, w.huecos_grupo),
            (t.profesor.id, self.prof, w.huecos_profesor),
        ):
            horas = [h for h in self.p.horas if (clave, d, h) in ocup]
            if horas:
                # Distancia al bloque existente más cercano = huecos que se crean.
                dist = max(0, ini - max(horas) - 1, min(horas) - fin)
                c += peso * dist
            else:
                c += 1  # leve preferencia por concentrar clases en menos días
        return c

    def aplicar(self, b: Bloque, op: tuple[Dia, int, str], signo: bool) -> None:
        d, ini, r = op
        t = b.tarea
        for h in range(ini, ini + b.largo):
            for conj, k in ((self.prof, t.profesor.id), (self.grupo, t.grupo.id), (self.salon, r)):
                (conj.add if signo else conj.discard)((k, d, h))
        dias = self.dias_tarea.setdefault(t.idx, set())
        if signo:
            dias.add(d)
            self.colocados[b] = op
            self.salon_tarea.setdefault(t.idx, r)
        else:
            dias.discard(d)
            del self.colocados[b]
            if not any(x.tarea.idx == t.idx for x in self.colocados):
                self.salon_tarea.pop(t.idx, None)

    def buscar(self, pendientes: list[Bloque]) -> bool:
        if not pendientes:
            return True
        self.nodos += 1
        if self.nodos > self.max_nodos or (self.nodos % 256 == 0 and time.monotonic() > self.deadline):
            self.agotado = True
            return False
        # MRV: el bloque más restringido primero (desempate: bloques largos).
        mejor, mejor_ops = None, None
        for b in pendientes:
            ops = self.opciones(b)
            if mejor_ops is None or (len(ops), -b.largo) < (len(mejor_ops), -mejor.largo):
                mejor, mejor_ops = b, ops
                if not ops:
                    return False
        resto = [b for b in pendientes if b is not mejor]
        for op in sorted(mejor_ops, key=lambda o: self.costo(mejor, o)):
            self.aplicar(mejor, op, True)
            if self.buscar(resto):
                return True
            self.aplicar(mejor, op, False)
            if self.agotado:
                return False
        return False


def resolver(p: Problema) -> tuple[str, Solucion]:
    bloques = [b for t in p.tareas for b in _bloques(t)]
    s = _Busqueda(p)
    if not s.buscar(bloques):
        # La búsqueda es exhaustiva solo para una descomposición fija en bloques,
        # así que un fallo no prueba infactibilidad: se reporta como sin_solucion.
        return "sin_solucion", {}
    sol: Solucion = {}
    for b, (d, ini, r) in s.colocados.items():
        for h in range(ini, ini + b.largo):
            sol[b.tarea.idx, d, h] = r
    return "factible", sol
