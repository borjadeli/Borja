"""Motor de valuación disciplinado — bull/base/bear (Etapa 4b.1, Art. 12.1).

El LLM trae fundamento citado + pares + horizonte; ESTE motor determinista computa
los precios. El LLM NO pone el número.

Principios (triangulados, versión simple):
  - La discreción vive en el FUNDAMENTO, no en el múltiplo.
  - Múltiplo del peer set: bear=P25, base=P50. El BULL usa el múltiplo BASE (P50),
    no lo expande → su upside viene solo del fundamento documentado (anti doble-conteo).
  - Puente: EV = fund × múltiplo → equity = EV − deuda neta → precio = equity /
    (acciones diluidas × (1 + CAGR_dilución × horizonte)).
  - Descuento a hoy por tasa fija del arquetipo (castiga las historias lejanas).
  - Guardas baratas: match de convención, techo P90 propio, flags de baja confianza,
    dispersión e implausibilidad (EV bull > TAM).

Diferido (NO v1): treasury-stock iterado, puente completo (leases/preferidas/…),
modelar cada convertible/warrant/ATM, proyectar deuda neta a la fecha del fundamento,
"ganar el percentil" por ranking de drivers. Ver init_docs/17 + registro 14.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

# Tasa de descuento anual por arquetipo (decisión del operador; calibrable — registro 14).
TASA_DESCUENTO = {
    "Madura": 0.10, "Growth": 0.14, "Tracción": 0.16,
    "Pre-revenue": 0.22, "Binary": 0.22,
}
TASA_DEFAULT = 0.15
MIN_PARES = 3
DISPERSION_MAX = 3.0   # P75/P25 por encima → baja confianza


@dataclass
class HechosValuacion:
    arquetipo: str
    metrica: str                       # "EV/EBITDA" | "EV/Sales" | "EV/GP" | "EV/EBIT"
    pares_multiplos: list[float]       # múltiplos de comparables (LLM trae los pares; los datos, los múltiplos)
    fund_bear: float
    fund_base: float
    fund_bull: float                   # fundamento del bull: documentado (contratado+financiado+fechado)
    deuda_neta: float                  # deuda − caja (a hoy)
    acciones_diluidas: float
    dilucion_cagr: float               # CAGR 3a del share count diluido (anual)
    horizon_years: float
    convencion_fundamento: str = ""    # ej. "NTM|SBC-out"
    convencion_multiplo: str = ""      # debe matchear convencion_fundamento
    techo_multiplo_propio: float | None = None   # P90 del múltiplo propio trailing (guard)
    tam: float | None = None           # para el flag de implausibilidad


@dataclass
class ResultadoValuacion:
    bull: float | None
    base: float | None
    bear: float | None
    multiplo_bear: float
    multiplo_base: float
    flags: list[str] = field(default_factory=list)
    detalle: dict = field(default_factory=dict)


def _percentil(valores: list[float], p: float) -> float:
    xs = sorted(valores)
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def _precio_desde_ev(ev: float, h: HechosValuacion) -> float | None:
    equity = ev - h.deuda_neta
    diluidas = h.acciones_diluidas * (1.0 + h.dilucion_cagr * h.horizon_years)
    if diluidas <= 0:
        return None
    return equity / diluidas


def _descontar(precio: float | None, tasa: float, años: float) -> float | None:
    if precio is None:
        return None
    return precio / ((1.0 + tasa) ** años)


def valuar(h: HechosValuacion) -> ResultadoValuacion:
    """Computa bull/base/bear descontados. Determinista. Levanta ValueError si la
    convención no matchea (fundamento y múltiplo deben medirse igual)."""
    if h.convencion_fundamento != h.convencion_multiplo:
        raise ValueError(
            f"convención no matchea: fund={h.convencion_fundamento!r} múltiplo={h.convencion_multiplo!r}")

    flags: list[str] = []
    pares = [m for m in h.pares_multiplos if m is not None and m > 0]
    if len(pares) < MIN_PARES:
        flags.append(f"baja confianza: {len(pares)} pares (<{MIN_PARES})")
    if not pares:
        return ResultadoValuacion(None, None, None, 0.0, 0.0, flags, {"error": "sin pares"})

    p25, p50, p75 = _percentil(pares, 0.25), _percentil(pares, 0.50), _percentil(pares, 0.75)
    if p25 > 0 and p75 / p25 > DISPERSION_MAX:
        flags.append(f"dispersión alta (P75/P25={p75 / p25:.1f})")

    mult_base = p50
    if h.techo_multiplo_propio is not None:
        mult_base = min(mult_base, h.techo_multiplo_propio)   # no re-ratear a un múltiplo nunca tenido
    mult_bear = min(p25, mult_base)

    tasa = TASA_DESCUENTO.get(h.arquetipo, TASA_DEFAULT)
    ev_bear = h.fund_bear * mult_bear
    ev_base = h.fund_base * mult_base
    ev_bull = h.fund_bull * mult_base           # BULL NO expande el múltiplo → upside = fundamento

    if h.tam is not None and ev_bull > h.tam:
        flags.append(f"implausible: EV bull ({ev_bull:.0f}) > TAM ({h.tam:.0f})")

    bear = _descontar(_precio_desde_ev(ev_bear, h), tasa, h.horizon_years)
    base = _descontar(_precio_desde_ev(ev_base, h), tasa, h.horizon_years)
    bull = _descontar(_precio_desde_ev(ev_bull, h), tasa, h.horizon_years)

    return ResultadoValuacion(
        bull=bull, base=base, bear=bear, multiplo_bear=mult_bear, multiplo_base=mult_base,
        flags=flags,
        detalle={"ev_bear": ev_bear, "ev_base": ev_base, "ev_bull": ev_bull,
                 "p25": p25, "p50": p50, "p75": p75, "tasa": tasa},
    )


def merito_ranking(quality_tier: int, asimetria: float | None) -> float | None:
    """Mérito para ranking: CÓNCAVO en asimetría (raíz), en vez de winsorizar a 5:1.
    Un 20:1 pesa más que un 5:1 (√20 vs √5) pero no 4× → preserva la cola sin
    premiar la asimetría inflada linealmente. None si no calculable o ≤0."""
    if asimetria is None or asimetria <= 0:
        return None
    return quality_tier * math.sqrt(asimetria)
