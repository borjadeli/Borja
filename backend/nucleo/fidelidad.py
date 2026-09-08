"""Fidelidad de datos — unidad canónica + guard de plausibilidad en CADA boundary de datos.

Principio del operador: un dato mal NO debe pasar bajo ningún concepto. Todo número que cruza
del mundo externo (EDGAR, mercado, LLM) a una decisión pasa por `canon()`: se convierte a la
unidad canónica (fracción para %, USD para montos) y se valida contra un rango plausible. Fuera
de rango o no numérico → None (UNKNOWN) + log. Es la barrera contra el villano recurrente
%/fracción y contra valores absurdos de la fuente.
"""
from __future__ import annotations

from backend.utils import get_logger

log = get_logger(__name__)

# Rangos plausibles en unidad CANÓNICA (fracción para tasas, USD para montos).
RANGOS: dict[str, tuple[float | None, float | None]] = {
    "margen": (-1.0, 1.0),          # gross margin: -100% a 100%
    "crecimiento": (-1.0, 20.0),    # YoY: -100% a +2000% (permite hipercrecimiento real)
    "dilucion": (-0.5, 3.0),        # 3y: -50% (recompras) a +300%
    "fraccion": (-1.0, 20.0),       # tasa genérica
    "positivo": (0.0, None),        # revenue, EV, shares, precio
    "monto": (None, None),          # USD cualquier signo (FCF, deuda neta)
}


def canon(valor, *, tipo: str, es_pct: bool = False, campo: str = "") -> float | None:
    """Convierte a unidad canónica + valida plausibilidad. Fuera de rango/unidad → None (+log)."""
    if valor is None:
        return None
    try:
        v = float(valor)
    except (TypeError, ValueError):
        log.warning("fidelidad: %s no numérico (%r) → descartado", campo or tipo, valor)
        return None
    if es_pct:
        v = v / 100.0                # % → fracción (unidad canónica)
    lo, hi = RANGOS.get(tipo, (None, None))
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        log.warning("fidelidad: %s=%s fuera de rango %s → descartado (UNKNOWN)",
                    campo or tipo, v, (lo, hi))
        return None
    return v
