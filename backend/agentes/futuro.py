"""Calculadoras de futuro DETERMINISTAS (v2 doc 70 D4) — el "qué exige el precio" y "¿llega al hito?" que
hoy el LLM improvisa.

Principio (doc 70 D4, ambas IAs): una fórmula determinista alimentada con un supuesto optimista NO convierte
el supuesto en hecho. Por eso acá: (a) solo se computa con insumos REALES del pack; si falta algo →
**UNKNOWN**, no se fabrica; (b) escenarios base + estrés; (c) por ACCIÓN con dilución; (d) **base rates** —
la pieza anti-especulación: contrastar el crecimiento que el precio exige contra la clase de referencia.
Son funciones PURAS y testeables; `fuente_futuro` las enchufa al data pack como DataPoints DERIVED.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Resultado:
    valor: float | None          # None = UNKNOWN (faltan insumos)
    estado: str                  # COMPUTED | UNKNOWN
    detalle: str


def _unknown(motivo: str) -> Resultado:
    return Resultado(None, "UNKNOWN", motivo)


# --------------------------------------------------------------------------- funded critical path

def meses_runway(cash: float | None, burn_anual: float | None, *, estres: float = 1.0) -> Resultado:
    """Meses de pista = caja / (quema mensual × estrés). `burn_anual` NEGATIVO = quema (flujo op. del pack).
    `estres`>1 sube la quema (p.ej. 1.3 = 30% peor). UNKNOWN si falta un insumo o no quema."""
    if cash is None or burn_anual is None:
        return _unknown(f"falta insumo: {'cash' if cash is None else 'burn'}")
    if burn_anual >= 0:
        return Resultado(None, "UNKNOWN", "flujo operativo no-negativo: no quema caja")
    mensual = abs(burn_anual) / 12.0 * estres
    return Resultado(round(cash / mensual, 1), "COMPUTED", f"caja {cash:.0f} / quema {mensual:.0f}/mes (estrés {estres:g})")


def funded_hasta_hito(cash: float | None, burn_anual: float | None, meses_al_hito: int | None, *,
                      estres: float = 1.3, colchon_meses: int = 6) -> Resultado:
    """¿La caja alcanza hasta el próximo hito + colchón, bajo estrés? (doc 70 D2 test 2). valor = holgura en
    meses (positivo = cubre; negativo = gap). UNKNOWN si falta un insumo."""
    if meses_al_hito is None:
        return _unknown("falta meses_al_hito")
    rw = meses_runway(cash, burn_anual, estres=estres)
    if rw.valor is None:
        return rw
    holgura = round(rw.valor - (meses_al_hito + colchon_meses), 1)
    cubre = holgura >= 0
    return Resultado(holgura, "COMPUTED",
                     f"runway {rw.valor:.0f}m {'≥' if cubre else '<'} hito {meses_al_hito}m + colchón "
                     f"{colchon_meses}m (estrés {estres:g}) → {'cubre' if cubre else 'GAP'}")


# --------------------------------------------------------------------------- dilución para financiar el gap

def dilucion_por_gap(gap_usd: float | None, precio: float | None, shares: float | None, *,
                     descuento: float = 0.0) -> Resultado:
    """% de dilución de financiar un gap de capital emitiendo al precio actual (con `descuento` opcional).
    valor = dilución en %. doc 70 D4: el burden/valor se evalúa POR ACCIÓN, no solo por EV."""
    if gap_usd is None or precio is None or shares is None:
        return _unknown("faltan insumos (gap/precio/shares)")
    if gap_usd <= 0:
        return Resultado(0.0, "COMPUTED", "sin gap: no requiere emitir")
    precio_emision = precio * (1 - descuento)
    if precio_emision <= 0 or shares <= 0:
        return _unknown("precio o shares no válidos")
    nuevas = gap_usd / precio_emision
    return Resultado(round(nuevas / shares * 100, 1), "COMPUTED",
                     f"emitir {nuevas:.0f} acc @ {precio_emision:.2f} s/ {shares:.0f} = dilución")


# --------------------------------------------------------------------------- base rates (anti-especulación)

# Fracción APROXIMADA de empresas que SOSTIENEN un CAGR de revenue durante N años (patrón tipo Mauboussin:
# la persistencia de alto crecimiento decae fuerte). Es orientativa (calibrar con datos reales), pero el
# ORDEN DE MAGNITUD es el punto: "60% CAGR por 7 años" es rarísimo. Interpola lineal entre breakpoints.
_BASE_RATE = {   # (cagr_umbral, años) -> fracción histórica
    (0.20, 3): 0.30, (0.20, 5): 0.18, (0.20, 7): 0.10,
    (0.30, 3): 0.17, (0.30, 5): 0.08, (0.30, 7): 0.04,
    (0.40, 3): 0.09, (0.40, 5): 0.035, (0.40, 7): 0.015,
    (0.60, 3): 0.03, (0.60, 5): 0.01, (0.60, 7): 0.004,
}


def base_rate_cagr(cagr: float | None, anios: int | None) -> Resultado:
    """Fracción histórica (orientativa) de empresas que SOSTUVIERON ese CAGR de revenue por N años. La pieza
    anti-especulación: 'el precio exige 60% CAGR/7a' → '<0.5% lo logró'. UNKNOWN si falta insumo."""
    if cagr is None or anios is None:
        return _unknown("falta cagr o años")
    umbrales = sorted({u for u, _ in _BASE_RATE})
    anios_bp = sorted({a for _, a in _BASE_RATE})
    u = min(umbrales, key=lambda x: abs(x - cagr)) if cagr <= max(umbrales) else max(umbrales)
    a = min(anios_bp, key=lambda x: abs(x - anios))
    frac = _BASE_RATE[(u, a)]
    nota = "extrapolado (CAGR > tabla)" if cagr > max(umbrales) else "aprox."
    return Resultado(round(frac * 100, 2), "COMPUTED",
                     f"~{frac*100:.1f}% sostuvo ≥{u:.0%} CAGR por {a}a ({nota}); exigido {cagr:.0%}/{anios}a")
