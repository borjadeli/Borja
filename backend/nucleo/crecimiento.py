"""Crecimiento DEMOSTRADO (doc 36 §3/§4) — `g_D` per-share, castigado y fadeado. Input del reverse-DCF.

Falsación, no proyección: `g_D` es lo que la empresa YA hizo (hecho duro XBRL), NO lo que promete. Se computa
como `min(g_revenue, g_gross_profit)` per-share (revenue pass-through con GP estancado NO es growth), se
castiga unidireccionalmente (solo recorta: deceleración, margen comprado, inorgánico, base chica, cap por
arquetipo) y entra al reverse-DCF FADEADO hacia g_∞ (doc 36 §4). Determinista y auditable (traza).
"""
from __future__ import annotations

from backend.nucleo import politica


def _ttm(serie: list, hasta: int) -> float | None:
    """Suma TTM (4 trimestres) que termina en el índice `hasta` (inclusive). None si falta algún trimestre."""
    if hasta < 3 or hasta >= len(serie):
        return None
    win = serie[hasta - 3:hasta + 1]
    if len(win) < 4 or any(x is None for x in win):
        return None
    return sum(win)


def _p25(xs: list[float]) -> float | None:
    """Percentil 25 (interpolación lineal). Piso repetible: evita que 1-2 trimestres excepcionales dominen."""
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    k = 0.25 * (len(xs) - 1)
    lo = int(k)
    if lo + 1 >= len(xs):
        return xs[lo]
    return xs[lo] + (k - lo) * (xs[lo + 1] - xs[lo])


def _ajustar_per_share(vals: list, shares: list) -> tuple[list, bool]:
    """Divide por diluted shares (crecer emitiendo no es crecer). Si las shares faltan en la mayoría de los
    trimestres, cae a agregado (flag es_per_share=False) — honesto, no inventa el denominador."""
    if sum(1 for s in shares if s) >= len(vals) - 1:
        return [v / s if (v is not None and s) else None for v, s in zip(vals, shares)], True
    return list(vals), False


def _cagr_3fy(ps: list) -> float | None:
    """CAGR 3FY: TTM vigente vs TTM de hace 3 años (12 trimestres). Requiere ≥16 trimestres."""
    now, prior = _ttm(ps, len(ps) - 1), _ttm(ps, len(ps) - 13)
    if not now or not prior or prior <= 0:
        return None
    return (now / prior) ** (1 / 3) - 1


def _yoy_ttm(ps: list) -> float | None:
    """YoY del TTM: TTM vigente vs TTM de hace 1 año (4 trimestres). Detecta deceleración actual."""
    now, prior = _ttm(ps, len(ps) - 1), _ttm(ps, len(ps) - 5)
    if not now or not prior or prior <= 0:
        return None
    return now / prior - 1


def _yoy_8q(ps: list) -> list[float]:
    """Los últimos 8 YoY trimestrales (q[i]/q[i-4] − 1)."""
    out = []
    for i in range(max(4, len(ps) - 8), len(ps)):
        a, b = ps[i], ps[i - 4]
        if a is not None and b and b > 0:
            out.append(a / b - 1)
    return out


def _crecimiento_serie(vals: list, shares: list) -> tuple[float | None, list[float], bool]:
    """g de una serie = min(CAGR_3FY, YoY_TTM, P25(8×YoY)) per-share (doc 36 §3). El min hace el growth
    conservador (piso repetible). Devuelve (g, serie_8yoy, es_per_share)."""
    ps, es_ps = _ajustar_per_share(vals, shares)
    s8 = _yoy_8q(ps)
    cands = [x for x in (_cagr_3fy(ps), _yoy_ttm(ps), _p25(s8)) if x is not None]
    return (min(cands) if cands else None), s8, es_ps


def _decel(s8: list[float]) -> float:
    """Deceleración normalizada [0,1] de los 8 YoY: (media 1ª mitad − media 2ª mitad)/media 1ª. 0 si acelera."""
    if len(s8) < 6:
        return 0.0
    h = len(s8) // 2
    m1 = sum(s8[:h]) / h
    m2 = sum(s8[h:]) / (len(s8) - h)
    if m1 <= 0:
        return 0.0
    return max(0.0, min(1.0, (m1 - m2) / m1))


def crecimiento_demostrado(serie, arquetipo: str, *, delta_gm_3y: float | None = None,
                           ma_intensity: float | None = None, concentracion: float | None = None) -> dict:
    """`g_D` DEMOSTRADO castigado (doc 36 §3/§4) desde una `edgar.SerieCrecimiento`. Castigos unidireccionales
    (solo recortan). `delta_gm_3y` (fracción, ej. −0.04), `ma_intensity` (M&A_cash/ΔRevenue) y `concentracion`
    (fracción top-cliente) son opcionales: si None, ese castigo no aplica (conservador ≠ inventar).
    Devuelve {g_D, g_rev, g_gp, es_per_share, traza}."""
    g_rev, s8_rev, es_ps = _crecimiento_serie(serie.revenue, serie.diluted_shares)
    g_gp, _, _ = _crecimiento_serie(serie.gross_profit, serie.diluted_shares)
    base = [g for g in (g_rev, g_gp) if g is not None]
    if not base:
        return {"g_D": None, "g_rev": g_rev, "g_gp": g_gp, "es_per_share": es_ps, "traza": ["serie insuficiente"]}
    g = min(base)                                    # min(rev, GP): pass-through con GP estancado no es growth
    traza = [f"g_rev={g_rev:.1%}" if g_rev is not None else "g_rev=NA",
             f"g_gp={g_gp:.1%}" if g_gp is not None else "g_gp=NA", f"base_min={g:.1%}",
             "per_share" if es_ps else "AGREGADO (sin diluted shares)"]

    decel = _decel(s8_rev)
    if decel > 0:                                    # deceleración de los 8 YoY
        f = 1 - politica.FACTOR_DECEL_MAX * decel
        g *= f
        traza.append(f"decel {decel:.2f} → ×{f:.2f}")
    if delta_gm_3y is not None and delta_gm_3y < politica.UMBRAL_GM_COMPRADO:
        g *= politica.FACTOR_MARGEN_COMPRADO         # crecimiento "comprado" con caída de margen
        traza.append(f"margen_comprado (ΔGM {delta_gm_3y:.1%}) → ×{politica.FACTOR_MARGEN_COMPRADO}")
    if ma_intensity is not None and ma_intensity >= politica.UMBRAL_INORGANICO:
        g *= politica.FACTOR_INORGANICO              # crecimiento inorgánico (M&A)
        traza.append(f"inorgánico (M&A {ma_intensity:.0%}) → ×{politica.FACTOR_INORGANICO}")
    if concentracion is not None and concentracion > politica.UMBRAL_CONCENTRACION_FRAGIL:
        g *= politica.FACTOR_CONCENTRACION           # crecimiento CONCENTRADO = frágil, no durable (validación 2026-08)
        traza.append(f"concentración {concentracion:.0%} > {politica.UMBRAL_CONCENTRACION_FRAGIL:.0%} → frágil ×{politica.FACTOR_CONCENTRACION}")
    rev_ttm = _ttm(serie.revenue, len(serie.revenue) - 1)
    if rev_ttm is not None and rev_ttm < politica.UMBRAL_BASE_CHICA:
        g = min(g, politica.CAP_BASE_CHICA)          # base chica → no sostenible
        traza.append(f"base_chica (rev {rev_ttm/1e6:.0f}M) → cap {politica.CAP_BASE_CHICA:.0%}")
    cap = politica.CAP_CRECIMIENTO_ARQ.get(arquetipo, 0.40)
    g = max(0.0, min(g, cap))                        # cap DURO por arquetipo
    traza.append(f"cap_arq {arquetipo} {cap:.0%}")
    return {"g_D": round(g, 4), "g_rev": g_rev, "g_gp": g_gp, "es_per_share": es_ps, "decel": round(decel, 3),
            "traza": traza}


def fade(g_D: float, t: int, *, estres: bool = False) -> float:
    """Crecimiento demostrado FADEADO al año t hacia g_∞ (doc 36 §4). Base: half-life 3 años. Estrés:
    shock inicial (−max(5pp, 25% del gap)) + half-life 2 años. `t` es 1-indexado (año 1 = primer año)."""
    g_inf = politica.G_TERMINAL
    if estres:
        shock = max(0.05, 0.25 * (g_D - g_inf))
        g0 = g_D - shock
        lam = 2 ** (-1 / 2)
    else:
        g0 = g_D
        lam = 2 ** (-1 / 3)
    return g_inf + (g0 - g_inf) * (lam ** (t - 1))
