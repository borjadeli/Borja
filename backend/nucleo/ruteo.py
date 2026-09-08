"""Ruteo de dos ejes (doc 42 §2, Bloque 2 Decisión 2) — qué GRAMÁTICA de valuación usar por empresa.

Arregla el "good loser": el signo de owner-FCF mide intensidad de inversión, NO la clase de empresa. El defecto
del switch viejo era que el SaaS-que-escala y el negocio-que-muere caían al MISMO bucket. Fix (triangulado):
**test de DERIVADA, no de nivel** — `Δ8Q(GrossProfit)/Δ8Q(OpEx) > 1.0` = apalancamiento operativo DEMOSTRADO.
4 estados deterministas, todo XBRL. **Muro SBC:** `fcf_pre_sbc` (=CFO−capex) SOLO rutea; `owner_FCF` (=CFO−capex
−SBC) SOLO valúa (doc 42 §2). El ruteo es PRE-SBC; la valuación POST-SBC.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.nucleo import politica

# Estados de ruteo (doc 42 §2). Cada uno manda a una gramática de valuación distinta.
COMERCIAL_MADURO = "COMERCIAL_MADURO"          # → reverse-DCF as-is (margen demostrado)
COMERCIAL_ESCALANDO = "COMERCIAL_ESCALANDO"    # → reverse-DCF margen normalizado (el "good loser")
PRE_REVENUE_BINARIO = "PRE_REVENUE_BINARIO"    # → gramática binaria (doc 42 §1)
BURDEN = "BURDEN"                              # → excluido / sin posición


def _delta_8q(serie: list) -> float | None:
    """Δ sobre ~8 trimestres: (suma últimos 4) − (suma 4 anteriores). Mide la variación TTM-sobre-TTM anterior,
    robusto a estacionalidad. None si falta historia."""
    xs = [x for x in serie if x is not None]
    if len(xs) < 8:
        return None
    return sum(xs[-4:]) - sum(xs[-8:-4])


def apalancamiento_operativo(gp_qtrs: list, opex_qtrs: list, *, lag_q: int = 0) -> float | None:
    """`Δ8Q(GrossProfit_lag) / Δ8Q(OpEx)` (doc 42 §2 + doc 47) — el test de DERIVADA. > 1.0 = cada dólar extra de
    opex trae MÁS de un dólar de gross profit = apalancamiento operativo demostrado = 'pierde plata ESCALANDO'
    (no muriendo).

    `lag_q` (doc 47, triangulación IA#3): el S&M de HOY produce gross profit `lag_q` trimestres DESPUÉS. Medir GP y
    OpEx contemporáneos sesga el apal ABAJO en quien acelera inversión → se adelanta el GP `lag_q` trimestres.
    **Guarda anti-artefacto de recorte de costos:** exige AMBOS deltas > 0 (si ΔOpEx<0 y ΔGP<0 el ratio sale
    positivo por la razón equivocada — 'no escala, recorta'). None si falta historia, el opex no creció, o algún
    delta no es positivo."""
    gp, opex = list(gp_qtrs), list(opex_qtrs)
    if lag_q:
        if len(gp) <= lag_q:
            return None
        gp = gp[lag_q:]                       # GP adelantado lag_q trimestres
        opex = opex[:len(opex) - lag_q]       # OpEx atrasado, alineado
    d_gp, d_opex = _delta_8q(gp), _delta_8q(opex)
    if d_gp is None or d_opex is None or abs(d_opex) < 1e-9:
        return None
    if d_gp <= 0 or d_opex <= 0:              # artefacto de recorte (ambos negativos → ratio+ espurio) → no medible
        return None
    return d_gp / d_opex


@dataclass
class Ruteo:
    ticker: str
    estado: str
    apalancamiento: float | None = None
    gross_margin: float | None = None
    sbc_over_rev: float | None = None
    owner_fcf: float | None = None
    motivo: str = ""


def _gross_margin(rev_ttm: float | None, gp_ttm: float | None) -> float | None:
    return (gp_ttm / rev_ttm) if (rev_ttm and gp_ttm is not None) else None


def rutear(ticker: str, *, revenue_ttm: float | None, gp_qtrs: list, opex_qtrs: list,
           owner_fcf: float | None, sbc_ttm: float | None, cfo_ttm: float | None, capex_ttm: float | None,
           runway_meses: float | None = None, hito_binario: bool = False,
           base_rate_n: int = 0) -> Ruteo:
    """Rutea a uno de los 4 estados (doc 42 §2). owner_fcf = CFO−capex−SBC (POST-SBC, para el gate MADURO).
    fcf_pre_sbc = CFO−capex (PRE-SBC, no se usa acá salvo diagnóstico — el ruteo NO depende del signo de FCF).
    `hito_binario`/`base_rate_n` los pasa el llamador (hecho citado + tabla) para la vía binaria."""
    gp_ttm = sum([x for x in gp_qtrs if x is not None][-4:]) if gp_qtrs else None
    gm = _gross_margin(revenue_ttm, gp_ttm)
    # apal con lag (doc 47): el GP de hoy responde al OpEx de hace ~3Q. Corrige el sesgo-abajo del acelerador.
    apal = apalancamiento_operativo(gp_qtrs, opex_qtrs, lag_q=politica.APAL_LAG_Q)
    sbc_over_rev = (sbc_ttm / revenue_ttm) if (sbc_ttm and revenue_ttm) else None
    r = Ruteo(ticker=ticker, estado=BURDEN, apalancamiento=apal, gross_margin=gm,
              sbc_over_rev=sbc_over_rev, owner_fcf=owner_fcf)

    # SBC > 25% del revenue sostenido → motor comercial ficticio → BURDEN (doc 42 §2, 2ª guarda).
    if sbc_over_rev is not None and sbc_over_rev > politica.SBC_REV_MAX_COMERCIAL:
        r.motivo = f"SBC/rev {sbc_over_rev:.0%} > {politica.SBC_REV_MAX_COMERCIAL:.0%} → motor comercial ficticio"
        return r

    tiene_rev = bool(revenue_ttm and revenue_ttm > 0)
    gp_pos = gp_ttm is not None and gp_ttm > 0

    # PRE_REVENUE_BINARIO: sin revenue recurrente + hito nombrado + base rate con denominador (n≥20).
    if not tiene_rev:
        if hito_binario and base_rate_n >= politica.BASE_RATE_N_MIN:
            r.estado, r.motivo = PRE_REVENUE_BINARIO, f"pre-revenue + hito + base_rate n={base_rate_n}"
        else:
            r.estado, r.motivo = BURDEN, "pre-revenue sin hito/base-rate auditable (quinto estado: floor-only)"
        return r

    # COMERCIAL_MADURO: genera caja owner-FCF+ → reverse-DCF con margen demostrado.
    if gp_pos and owner_fcf is not None and owner_fcf > 0:
        r.estado, r.motivo = COMERCIAL_MADURO, "owner-FCF+ → reverse-DCF margen demostrado"
        return r

    # COMERCIAL_ESCALANDO (el "good loser"): comercial pero owner-FCF<0, con apalancamiento operativo DEMOSTRADO.
    escala = (gp_pos and gm is not None and gm >= politica.GM_MIN_ESCALANDO
              and apal is not None and apal > 1.0
              and (runway_meses is None or runway_meses >= politica.RUNWAY_MIN_ESCALANDO_M))
    if escala:
        r.estado, r.motivo = (COMERCIAL_ESCALANDO,
                              f"good-loser: GM {gm:.0%}, apalancamiento Δ8Q(GP)/Δ8Q(OpEx)={apal:.2f}>1 (escala, no muere)")
        return r

    # No calificó → BURDEN (pierde plata SIN apalancamiento demostrado = 'muere', no 'escala').
    detalle = f"apalancamiento={apal:.2f}" if apal is not None else "sin historia de apalancamiento"
    r.motivo = f"comercial pero owner-FCF<0 y sin escala demostrada ({detalle}) → BURDEN"
    return r
