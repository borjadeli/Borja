"""Validador determinista del PM (Etapa 6, Art. 4.4).

Rechaza-e-informa: NO modifica la propuesta del PM. Si viola un límite duro,
devuelve los errores concretos y el PM re-propone (bucle acotado aguas arriba).
La frontera queda *enforced*, no confiada a la buena conducta del LLM.

Límites que enforcea (Art. 4.1/4.3):
  - solo empresas ELEGIBLES (nada inventado fuera del conjunto);
  - peso de cada posición en [piso, hard cap];
  - máx posiciones por sector;
  - cap por factor macro (conteo completo en multi-pertenencia, Art. 4.5);
  - el invertido no supera el máximo que deja el cash objetivo del operador (Art. 4.7).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.nucleo.constantes import MAX_POR_SUBSECTOR, PISO_POSICION

# Máx % de cartera expuesto a un mismo factor macro (calibrable — registro 14).
FACTOR_CAP = 0.40


@dataclass
class Candidata:
    """Lo que el validador sabe (determinista) de cada nombre elegible."""
    ticker: str
    elegible: bool
    hard_cap: float
    sector: str | None = None
    factores: list[str] = field(default_factory=list)   # factores macro (conteo completo)


@dataclass
class LineaPropuesta:
    """Una línea de la propuesta del PM."""
    ticker: str
    peso: float


def validar_propuesta(lineas: list[LineaPropuesta], candidatas: list[Candidata], *,
                      cash_objetivo: float, piso: float = PISO_POSICION,
                      max_por_sector: int = MAX_POR_SUBSECTOR,
                      factor_cap: float = FACTOR_CAP, tol: float = 1e-9) -> dict:
    """Valida la propuesta del PM contra los límites duros. Devuelve
    {ok, errores, invertido, cash}. No modifica nada."""
    por_ticker = {c.ticker.upper(): c for c in candidatas}
    errores: list[str] = []
    por_sector: dict[str, int] = {}
    por_factor: dict[str, float] = {}
    invertido = 0.0
    vistos: set[str] = set()

    for l in lineas:
        t = l.ticker.upper()
        c = por_ticker.get(t)
        if c is None:
            errores.append(f"{t}: fuera del conjunto elegible (ticker inventado)")
            continue
        if t in vistos:
            errores.append(f"{t}: duplicado en la propuesta")
            continue
        vistos.add(t)

        if not c.elegible:
            errores.append(f"{t}: no elegible")
        if l.peso < piso - tol:
            errores.append(f"{t}: peso {l.peso:.1%} < piso {piso:.0%}")
        if l.peso > c.hard_cap + tol:
            errores.append(f"{t}: peso {l.peso:.1%} > hard cap {c.hard_cap:.0%}")

        invertido += l.peso
        if c.sector:
            por_sector[c.sector] = por_sector.get(c.sector, 0) + 1
        for f in c.factores:
            por_factor[f] = por_factor.get(f, 0.0) + l.peso

    for s, n in por_sector.items():
        if n > max_por_sector:
            errores.append(f"sector {s}: {n} posiciones > máx {max_por_sector}")
    for f, w in por_factor.items():
        if w > factor_cap + tol:
            errores.append(f"factor {f}: {w:.1%} > cap {factor_cap:.0%}")

    maximo_invertible = 1.0 - cash_objetivo
    if invertido > maximo_invertible + tol:
        errores.append(
            f"invertido {invertido:.1%} > máximo {maximo_invertible:.0%} "
            f"(cash objetivo {cash_objetivo:.0%})")

    return {"ok": not errores, "errores": errores,
            "invertido": invertido, "cash": 1.0 - invertido}
