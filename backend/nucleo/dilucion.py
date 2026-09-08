"""Pilar de dilución (doc 31 §5) — reescrito tras el review del build (2 IAs convergieron, 2026-08-05).

Cambio central: la señal PRIMARIA es la dilución FORWARD esperada, no la histórica.
  burn_yield = −FCF_TTM / market_cap   (cuando FCF < 0)
Es cuánto tendría que diluir por año para financiar la quema — 100% XBRL + precio, y NO la contamina
la mecánica de clases de acciones. Las dos IAs coinciden en que es el proxy honesto de dilución
prospectiva sin parsear notas.

Por qué NO uso la trayectoria de acciones diluidas (lo que tenía): (a) weighted-avg suaviza una
emisión reciente; (b) en empresas con pérdida "diluido"=básico (antidilución GAAP) → no ve warrants/
convertibles justo en los pre-revenue; (c) **en estructuras Up-C (SMR, ASTS) el conteo de Class A
crece por exchanges B→A sin dilución económica** → el "236%/año" de SMR era un artefacto. Medir la
dilución REALIZADA bien exige sumar clases (hechos DIMENSIONALES) que companyfacts no entrega →
diferido a la Fase 2 (parsing filing-céntrico, ver [[extraccion-xbrl-triangulada]]).

La dilución NO entra al ranking como un ρ separado (doble conteo con el SBC ya restado en owner-FCF):
es un pilar/flag propio. La versión limpia (v2) trabaja per-share sobre owner-FCF.
"""
from __future__ import annotations

from dataclasses import dataclass

# Bandas de burn yield (dilución forward anual esperada) — doc 31 §5 / review.
_BANDAS = ((0.05, "bajo"), (0.15, "material"), (0.25, "alto"), (0.50, "severo"))


RUNWAY_CRITICO_ANOS = 1.0             # < 1 año de pista sin financiación comprometida → crítico (doc 31 §4)


@dataclass
class Dilucion:
    burn_yield: float | None          # −FCF/mcap (dilución forward esperada por año); None si no aplica
    banda: str                        # bajo | material | alto | severo | extraordinario | n/a
    runway_anos: float | None         # caja / quema anual (años de pista); None si no quema
    runway_critico: bool              # runway < 1 año (dependencia dura del mercado de capitales)
    forward_dilution_unknown: bool    # True mientras falten notas (overhang ATM/convertibles/warrants)
    nota: str = ""
    # --- Eje §5 construible HOY: dilución REALIZADA + carga SBC (doc 31 §5, triangulación 2026-08) ---
    # Complementan (no reemplazan) la señal primaria burn_yield forward. ATM overhang / warrants /
    # convertibles-peor-caso quedan DIFERIDOS a Fase 2-notas (sin tag XBRL) → siguen bajo
    # forward_dilution_unknown, no se aproximan.
    shares_growth_12m: float | None = None   # Δ fracción de acciones vs ~-365d (total de clases sumadas)
    shares_growth_24m: float | None = None   # Δ fracción vs ~-730d
    shares_serie_fuente: str | None = None   # tag XBRL usado (auditoría)
    up_c_suspect: bool = False               # ≥2 clases → crecimiento puede ser B→A (NO dilución económica)
    sbc_over_revenue: float | None = None    # SBC_TTM / revenue_TTM; None si revenue ~0 (pre-revenue)


def _banda(x: float | None) -> str:
    if x is None or x <= 0:
        return "n/a"
    for umbral, nombre in _BANDAS:
        if x < umbral:
            return nombre
    return "extraordinario"


def _sbc_over_revenue(fin) -> float | None:
    """SBC_TTM / revenue_TTM. None si revenue ~0 (pre-revenue): el ratio no es material — unknown ≠ zero
    (doc 31 §5/§8). No se fuerza a 0 ni ∞; en ese caso el SBC absoluto/mcap queda como lectura forward."""
    sbc = getattr(fin, "sbc_ttm", None)
    rev = getattr(fin, "revenue_ttm", None)
    if sbc is None or not rev or rev <= 0:
        return None
    return round(sbc / rev, 4)


def dilucion_forward(fin, mcap: float | None, shares_growth: dict | None = None) -> Dilucion:
    """Foto de financiación: burn_yield = −FCF/mcap (dilución forward) + runway = caja/quema (años).
    Juntos distinguen un pre-revenue cash-rich de baja presión de uno a meses del capital raise.
    `mcap` viene del feed de mercado (no de XBRL). `shares_growth` = dict de edgar.get_shares_growth
    (dilución REALIZADA + up_c flag); opcional para retrocompat."""
    sg = shares_growth or {}
    ext = {
        "shares_growth_12m": sg.get("g_12m"),
        "shares_growth_24m": sg.get("g_24m"),
        "shares_serie_fuente": sg.get("fuente"),
        "up_c_suspect": bool(sg.get("up_c_suspect")),
        "sbc_over_revenue": _sbc_over_revenue(fin),
    }
    fcf = getattr(fin, "fcf_ttm", None)
    caja = getattr(fin, "cash", None)
    if fcf is None or not mcap or mcap <= 0:
        return Dilucion(None, "n/a", None, False, True, "datos insuficientes para burn_yield", **ext)
    if fcf >= 0:
        return Dilucion(0.0, "bajo", None, False, True,
                        "FCF ≥ 0: sin quema → sin dilución forward por burn", **ext)
    quema = -fcf
    by = quema / mcap
    runway = (caja / quema) if (caja and caja > 0) else 0.0
    critico = runway < RUNWAY_CRITICO_ANOS
    return Dilucion(by, _banda(by), round(runway, 1), critico, True,
                    f"burn_yield={by:.0%}/año · runway={runway:.1f}a (caja {(caja or 0)/1e6:.0f}M / "
                    f"quema {quema/1e6:.0f}M); overhang ATM/convertibles PENDIENTE (notas)", **ext)
