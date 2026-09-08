"""Validador determinista del PM (Etapa 6, Art. 4.4).

Rechaza-e-informa: NO modifica la propuesta del PM. Si viola un límite duro,
devuelve los errores concretos y el PM re-propone (bucle acotado aguas arriba).

Límites (Art. 4.1/4.3): solo elegibles (nada inventado); peso ∈ [piso, hard cap];
máx posiciones por sector; cap por factor macro (conteo completo en
multi-pertenencia); invertido ≤ (1 − cash objetivo del operador).

Ajustes tras revisión externa (AI 1): rechaza NaN/no-finitos (peso, config, caps);
valida rangos de config; normaliza sector/factor (strip+casefold) y deduplica
factores; detecta candidatas duplicadas en el universo.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from backend.nucleo.constantes import MAX_POR_SUBSECTOR, PISO_POSICION

# Máx % de cartera expuesto a un mismo factor macro (calibrable — registro 14).
FACTOR_CAP = 0.40


@dataclass
class Candidata:
    ticker: str
    elegible: bool
    hard_cap: float
    sector: str | None = None
    factores: list[str] = field(default_factory=list)   # factores macro (conteo completo)


@dataclass
class LineaPropuesta:
    ticker: str
    peso: float


def _finito(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _norm(s):
    return s.strip().casefold() if isinstance(s, str) and s.strip() else None


def validar_propuesta(lineas: list[LineaPropuesta], candidatas: list[Candidata], *,
                      cash_objetivo: float, piso: float = PISO_POSICION,
                      max_por_sector: int = MAX_POR_SUBSECTOR,
                      factor_cap: float = FACTOR_CAP, max_posiciones: int = 10,
                      tol: float = 1e-9) -> dict:
    """Valida la propuesta contra los límites duros. {ok, errores, invertido, cash}."""
    errores: list[str] = []

    # --- Config finita y en rango (si falla, no se puede computar seguro) ---
    for nombre, v in (("cash_objetivo", cash_objetivo), ("piso", piso),
                      ("factor_cap", factor_cap), ("tol", tol)):
        if not _finito(v) or not (0.0 <= v <= 1.0):
            errores.append(f"config inválida: {nombre}={v}")
    if not (isinstance(max_por_sector, int) and max_por_sector >= 0):
        errores.append(f"config inválida: max_por_sector={max_por_sector}")
    if not (isinstance(max_posiciones, int) and max_posiciones >= 1):
        errores.append(f"config inválida: max_posiciones={max_posiciones}")

    # --- Universo elegible: sin duplicados, hard_cap finito ---
    por_ticker: dict[str, Candidata] = {}
    for c in candidatas:
        t = c.ticker.upper()
        if t in por_ticker:
            errores.append(f"{t}: candidata duplicada en el universo elegible")
        por_ticker[t] = c
        if not _finito(c.hard_cap) or not (0.0 <= c.hard_cap <= 1.0):
            errores.append(f"{t}: hard_cap inválido ({c.hard_cap})")

    if errores:
        return {"ok": False, "errores": errores, "invertido": None, "cash": None}

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
        if not _finito(l.peso):
            errores.append(f"{t}: peso no finito ({l.peso})")
            continue
        if l.peso <= 0:
            errores.append(f"{t}: peso {l.peso} ≤ 0 (independiente del piso)")
            continue

        if not c.elegible:
            errores.append(f"{t}: no elegible")
        if l.peso < piso - tol:
            errores.append(f"{t}: peso {l.peso:.1%} < piso {piso:.0%}")
        if l.peso > c.hard_cap + tol:
            errores.append(f"{t}: peso {l.peso:.1%} > hard cap {c.hard_cap:.0%}")

        invertido += l.peso
        sec = _norm(c.sector) or "SIN_SECTOR"   # sin sector NO exime del cap (fail-closed)
        por_sector[sec] = por_sector.get(sec, 0) + 1
        for f in {_norm(x) for x in c.factores if _norm(x)}:   # normaliza + deduplica
            por_factor[f] = por_factor.get(f, 0.0) + l.peso

    for s, n in por_sector.items():
        if n > max_por_sector:
            errores.append(f"sector {s}: {n} posiciones > máx {max_por_sector}")
    for f, w in por_factor.items():
        if w > factor_cap + tol:
            errores.append(f"factor {f}: {w:.1%} > cap {factor_cap:.0%}")

    if len(vistos) > max_posiciones:
        errores.append(f"{len(vistos)} posiciones > máx {max_posiciones}")

    maximo_invertible = 1.0 - cash_objetivo
    if invertido > maximo_invertible + tol:
        errores.append(f"invertido {invertido:.1%} > máximo {maximo_invertible:.0%} "
                       f"(cash objetivo {cash_objetivo:.0%})")

    return {"ok": not errores, "errores": errores,
            "invertido": invertido, "cash": 1.0 - invertido}
