"""Templates de valuación operable por arquetipo (doc 28 §2/§3) — cohort-free.

Reemplaza la perpetuidad cruda sobre el margen ACTUAL (que explotaba con margen bajo) por un
bridge honesto sobre el **margen FCF TTM** (normalizado a 4 trimestres) + un **gate de generación
de caja** (FCF TTM > 0). Un nombre que no genera caja **no recibe terminal** → su valor operable cae
al **piso de balance** (caja neta), y el precio de mercado queda explicado por opcionalidad (carril
especulativo, doc 29), no por el número duro.

Por qué FCF TTM y no per-quarter ni EBIT:
  - EBIT (operating income GAAP) castiga al software: SBC + amortización hacen el EBIT negativo aunque
    el FCF sea fuerte (caso TENB: FCF TTM $254M, EBIT negativo).
  - El FCF POR TRIMESTRE es poco confiable en XBRL: el OCF en los 10-Q suele venir YTD (acumulado), y
    el filtro de ~90 días deja pocos trimestres limpios. El FCF TTM (OCF−CapEx sumado 4Q) sí es sólido.
  - Doc 28 §3 pide "≥4Q de FCF+"; con el dato disponible, FCF TTM > 0 es el proxy reliable.

Cohort-free (terminal = FCF/r, g=0). La diferencia entre arquetipos es la tasa r (política).
El spread bear/bull operable proviene del revenue CONTRATADO (doc 28); sin contratado extraído,
bear≈base≈bull (honesto: sin backlog, no hay upside operable más allá del run-rate).

TODO (diferido, honesto): I2 "bear despojado" de no-recurrentes; margen bear/bull por distribución
(requiere de-acumular el OCF YTD por trimestre). Nota: FCF es levered; para baja deuda, EV=FCF/r +
caja neta es aproximación razonable.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.nucleo import politica


@dataclass
class EscenarioValuacion:
    arquetipo: str
    genera_caja: bool
    con_terminal: bool
    bear_price: float | None
    base_price: float | None
    bull_price: float | None
    margen_fcf: float | None = None
    multiplo_sobre_operable: float | None = None   # precio / base (cuántas× lo operable paga el mercado)
    nota: str = ""
    traza: list[str] = field(default_factory=list)


def escenario_operable(revenue_ttm: float | None, fcf_ttm: float | None, arquetipo: str,
                       shares: float | None, caja: float | None, deuda: float | None, *,
                       precio: float | None = None, revenue_contratado: float = 0.0,
                       sbc_ttm: float | None = None) -> EscenarioValuacion:
    """Bear/base/bull operable como PRECIOS. Cohort-free, margen OWNER-FCF TTM, gate de caja del accionista."""
    r = politica.r_efectiva(arquetipo)
    caja_neta = (caja or 0.0) - (deuda or 0.0)
    piso = (caja_neta / shares) if (shares and shares > 0) else None
    # owner_fcf = FCF − SBC (review build 2026-08): el SBC infla el FCF crudo; con share count actual
    # hay que restarlo. Si SBC desconocida se usa FCF con flag (no-software suele tener SBC ~0).
    sbc_desconocida = sbc_ttm is None
    owner_fcf = (fcf_ttm - (sbc_ttm or 0.0)) if fcf_ttm is not None else None
    extra = ["sbc_desconocida→operable_puede_sobrestimar"] if (sbc_desconocida and fcf_ttm and fcf_ttm > 0) else []

    # Gate: OWNER-FCF positivo (genera caja tras pagar SBC). Si no → piso de balance.
    if not owner_fcf or owner_fcf <= 0 or not revenue_ttm or revenue_ttm <= 0 or not shares or shares <= 0:
        nota = ("no genera caja del accionista (owner-FCF ≤ 0): operable = piso de balance; el resto es "
                "opcionalidad" + (" [FCF+ solo por add-back de SBC]" if (fcf_ttm and fcf_ttm > 0) else ""))
        return EscenarioValuacion(
            arquetipo=arquetipo, genera_caja=bool(owner_fcf and owner_fcf > 0), con_terminal=False,
            bear_price=piso, base_price=piso, bull_price=piso,
            multiplo_sobre_operable=(precio / piso if (precio and piso and piso > 0) else None),
            nota=nota, traza=[f"fcf_ttm={fcf_ttm}", f"sbc_ttm={sbc_ttm}", f"owner_fcf={owner_fcf}"] + extra)

    m = owner_fcf / revenue_ttm             # margen OWNER-FCF TTM (FCF − SBC)
    rev_bull = revenue_ttm + (revenue_contratado or 0.0)

    def _price(rev: float) -> float:
        # Convención FCFE (auditoría 2026-08): el FCF es LEVERED (OCF−CapEx, post-intereses) → su
        # perpetuidad ya es valor de EQUITY. Se suma la caja como activo pero NO se resta la deuda
        # (ya está en el FCF vía intereses) — si no, se contaría la deuda dos veces.
        equity_ops = (rev * m) / r          # perpetuidad g=0 (cohort-free)
        return (equity_ops + caja) / shares

    bear = base = _price(revenue_ttm)       # run-rate (sin contratado)
    bull = _price(rev_bull)                 # + revenue contratado (spread operable)
    return EscenarioValuacion(
        arquetipo=arquetipo, genera_caja=True, con_terminal=True,
        bear_price=bear, base_price=base, bull_price=bull, margen_fcf=m,
        multiplo_sobre_operable=(precio / base if (precio and base and base > 0) else None),
        nota="terminal owner-FCF/r (g=0) sobre margen (FCF−SBC) TTM",
        traza=[f"margen_owner_fcf_ttm={m:.1%}", f"r={r:.0%}", f"rev_bull={rev_bull:.0f}",
               f"caja_neta={caja_neta:.0f}", f"sbc_ttm={sbc_ttm}"] + extra)


def asimetria_operable(bull: float | None, precio: float | None,
                       bear: float | None) -> float | None:
    """(bull − precio) / (precio − bear). None si el denominador ≤ 0 (precio ≤ bear)."""
    if bull is None or precio is None or bear is None:
        return None
    denom = precio - bear
    if denom <= 0:
        return None
    return (bull - precio) / denom
