"""P1 (doc 91 §8, review-2 IA1) — validación numérica COMPARTIDA por dominio. Un input material que no respeta su
dominio económico (NaN/inf/bool/negativo/fuera de [0,1]) NUNCA debe convertir una decisión bloqueada en ejecutable.
Devuelven None (en vez del valor) cuando el input no es válido para ese dominio. Determinista, $0.
"""
from __future__ import annotations

import math


def finito(x) -> float | None:
    """Número finito (rechaza None, NaN, ±inf, bool, no-números)."""
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def positivo(x) -> float | None:
    """Finito y estrictamente > 0 (ej. precio)."""
    v = finito(x)
    return v if (v is not None and v > 0) else None


def no_negativo(x) -> float | None:
    """Finito y ≥ 0 (ej. valor por acción, cobertura contractual)."""
    v = finito(x)
    return v if (v is not None and v >= 0) else None


def probabilidad(x) -> float | None:
    """Finito y en [0, 1]."""
    v = finito(x)
    return v if (v is not None and 0.0 <= v <= 1.0) else None


def fraccion(x) -> float | None:
    """Finito y |x| ≤ 1 (crecimiento/márgenes expresados como FRACCIÓN, no %)."""
    v = finito(x)
    return v if (v is not None and -1.0 <= v <= 1.0) else None


def en_rango(x, lo: float, hi: float) -> float | None:
    """Finito y en [lo, hi]."""
    v = finito(x)
    return v if (v is not None and lo <= v <= hi) else None
