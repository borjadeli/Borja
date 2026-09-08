"""Backtest POINT-IN-TIME de la valuación (doc 40 Bloque 0.2) — el meta-gate empírico.

Responde la pregunta que las dos IAs pusieron ANTES de cerrar cualquier número (doc 39 §6): **¿el frame de
valuación SEPARA retornos forward?** ¿los COVERED/STRETCH superan a los OPTION_PRICED/NON_UNDERWRITABLE a N años?
Si no separan, el frame no tiene poder predictivo y todo lo demás es teología. Si separan, esto CALIBRA en vez
de argumentar.

Point-in-time SIN look-ahead: reconstruye el estado como se conocía en `as_of` (XBRL `filed ≤ as_of`) y mide el
retorno con precios reales de ahí en adelante. Se limita a la VALUACIÓN (computable desde XBRL solo) — que es
DONDE vivieron los dos bugs (g=0, r=15%). Usa `r_mkt` (la lente de LECTURA de doc 37, ~10%), no el hurdle.

CAVEATS (honestos): (1) survivorship — el universo son nombres que HOY existen; (2) el estado no incluye los
gates de evidencia/pilares (que necesitan fact-store as-of, intratable) — es un backtest del EJE VALUACIÓN, no
del sistema entero; (3) muestra chica → señal ruidosa hasta escalar con bulk XBRL (P1).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.services import edgar, market_data
from backend.nucleo import crecimiento as C, politica, valuacion_reverse as VR

R_MKT_DEFAULT = 0.10          # lente de LECTURA (doc 37): Rf + β_sectorial × ERP ≈ 10% software líquido
_ORDEN = {"COVERED": 0, "STRETCH": 1, "OPTION_PRICED": 2, "NON_UNDERWRITABLE": 3}


def _ttm_asof(facts: dict, tags: list[str], as_of: str) -> float | None:
    """TTM (4 trimestres de-acumulados) de un concepto de FLUJO, conocido en `as_of` (filed ≤ as_of)."""
    entries = []
    for t in tags:
        e = edgar._extract_concept(facts, t)
        if e:
            entries = e
            break
    q = edgar._sorted_flow_quarters(edgar._filed_hasta(entries, as_of), n=8)
    vals = [x["val"] for x in q][-4:]
    return sum(vals) if len(vals) >= 4 else None


def _instant_asof(facts: dict, tags: list[str], as_of: str) -> float | None:
    """Último valor INSTANTÁNEO (balance) conocido en `as_of` (filed ≤ as_of, end más reciente)."""
    for t in tags:
        e = edgar._filed_hasta(edgar._extract_concept(facts, t), as_of)
        if e:
            return sorted(e, key=lambda x: x["end"])[-1]["val"]
    return None


@dataclass
class FundamentalsAsOf:
    ticker: str
    as_of: str
    revenue_ttm: float | None = None
    owner_fcf_ttm: float | None = None
    m0: float | None = None
    diluted_shares: float | None = None
    cash: float | None = None
    g_D: float | None = None
    sbc_ttm: float | None = None
    gp_qtrs: list = field(default_factory=list)      # serie point-in-time p/ ruteo (doc 42)
    opex_qtrs: list = field(default_factory=list)


def fundamentals_asof(ticker: str, as_of: str, arquetipo: str = "Growth") -> FundamentalsAsOf:
    """Reconstruye los inputs de valuación como se conocían en `as_of`. owner-FCF = CFO − capex − SBC (TTM)."""
    out = FundamentalsAsOf(ticker=ticker.upper(), as_of=as_of)
    cik = edgar.get_cik(ticker)
    if not cik:
        return out
    facts = edgar._get_companyfacts(cik)
    if not facts:
        return out
    serie = edgar.serie_crecimiento(ticker, n_q=16, as_of=as_of)
    rev = [x for x in serie.revenue if x]
    out.revenue_ttm = sum(rev[-4:]) if len(rev) >= 4 else None
    out.g_D = C.crecimiento_demostrado(serie, arquetipo).get("g_D")
    ocf = _ttm_asof(facts, ["NetCashProvidedByUsedInOperatingActivities"], as_of)
    capex = _ttm_asof(facts, ["PaymentsToAcquirePropertyPlantAndEquipment",
                              "PaymentsForCapitalImprovements"], as_of)
    sbc = _ttm_asof(facts, ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"], as_of)
    if ocf is not None:
        out.owner_fcf_ttm = ocf - (capex or 0.0) - (sbc or 0.0)
        if out.revenue_ttm:
            out.m0 = out.owner_fcf_ttm / out.revenue_ttm
    out.sbc_ttm = sbc
    out.gp_qtrs = list(serie.gross_profit)
    out.opex_qtrs = [(gp - oi) if (gp is not None and oi is not None) else None
                     for gp, oi in zip(serie.gross_profit, serie.operating_income)]
    out.diluted_shares = next((s for s in reversed(serie.diluted_shares) if s), None)
    out.cash = _instant_asof(facts, ["CashAndCashEquivalentsAtCarryingValue",
                                     "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"], as_of)
    return out


def _precio_asof(rows: list[dict], fecha: str) -> float | None:
    """Close más reciente en o antes de `fecha` (ISO). None si no hay precio previo."""
    prev = [r for r in rows if r["date"].date().isoformat() <= fecha[:10]]
    return prev[-1]["close"] if prev else None


@dataclass
class CasoBacktest:
    ticker: str
    as_of: str
    estado: str | None = None
    ruteo: str | None = None
    g_D: float | None = None
    precio_0: float | None = None
    precio_fwd: float | None = None
    retorno_fwd: float | None = None
    motivo: str = ""


def evaluar_caso(ticker: str, as_of: str, *, horizonte_dias: int = 365 * 3, r_mkt: float = R_MKT_DEFAULT,
                 modelo: str = "software", arquetipo: str = "Growth") -> CasoBacktest:
    """Un caso: reconstruye el estado de valuación en `as_of` y mide el retorno a `as_of + horizonte`."""
    caso = CasoBacktest(ticker=ticker.upper(), as_of=as_of)
    f = fundamentals_asof(ticker, as_of, arquetipo)
    if not (f.revenue_ttm and f.m0 is not None and f.diluted_shares):
        caso.motivo = "fundamentals as-of insuficientes"
        return caso
    caso.g_D = f.g_D
    rows = market_data.get_price_history(ticker, period="max") or []
    p0 = _precio_asof(rows, as_of)
    if not p0:
        caso.motivo = "sin precio en as_of"
        return caso
    from datetime import date, timedelta
    fwd = (date.fromisoformat(as_of[:10]) + timedelta(days=horizonte_dias)).isoformat()
    pf = _precio_asof(rows, fwd)
    caso.precio_0, caso.precio_fwd = p0, pf
    if pf:
        caso.retorno_fwd = pf / p0 - 1.0
    # Ruteo de 2 ejes as-of (doc 42 §2) → gramática. Mide el frame REBALANCEADO (no el estado directo viejo).
    from backend.nucleo import ruteo as RT
    rt = RT.rutear(ticker, revenue_ttm=f.revenue_ttm, gp_qtrs=f.gp_qtrs, opex_qtrs=f.opex_qtrs,
                   owner_fcf=f.owner_fcf_ttm, sbc_ttm=f.sbc_ttm, cfo_ttm=None, capex_ttm=None)
    caso.ruteo = rt.estado
    res = VR.estado_por_ruteo(ticker, rt.estado, revenue_ttm=f.revenue_ttm, owner_fcf=f.owner_fcf_ttm,
                              shares=f.diluted_shares, precio=p0, cash=f.cash, g_D=f.g_D, modelo=modelo)
    caso.estado = res.estado if res is not None else rt.estado   # BURDEN/PRE_REV → el estado de ruteo
    return caso


def _resumen(rets: list[float]) -> dict:
    if not rets:
        return {"n": 0, "media": None, "mediana": None}
    xs = sorted(rets)
    n = len(xs)
    med = xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2
    return {"n": n, "media": round(sum(xs) / n, 4), "mediana": round(med, 4),
            "min": round(xs[0], 4), "max": round(xs[-1], 4)}


def correr(pares: list[tuple[str, str]], *, horizonte_dias: int = 365 * 3, r_mkt: float = R_MKT_DEFAULT,
           modelo_por_ticker: dict[str, str] | None = None) -> dict:
    """Corre el backtest sobre pares (ticker, as_of). Agrega retorno forward POR ESTADO y computa la
    SEPARACIÓN (compra COVERED+STRETCH vs rechazo OPTION+NON). Devuelve {casos, por_estado, separacion}."""
    modelo_por_ticker = modelo_por_ticker or {}
    casos = [evaluar_caso(t, d, horizonte_dias=horizonte_dias, r_mkt=r_mkt,
                          modelo=modelo_por_ticker.get(t.upper(), "software")) for t, d in pares]
    con_ret = [c for c in casos if c.estado and c.retorno_fwd is not None]
    por_estado: dict[str, list[float]] = {}
    for c in con_ret:
        por_estado.setdefault(c.estado, []).append(c.retorno_fwd)
    compra = [c.retorno_fwd for c in con_ret if _ORDEN.get(c.estado, 9) <= 1]
    rechazo = [c.retorno_fwd for c in con_ret if _ORDEN.get(c.estado, 9) >= 2]
    rc, rr = _resumen(compra), _resumen(rechazo)
    sep = (rc["media"] - rr["media"]) if (rc["media"] is not None and rr["media"] is not None) else None
    return {"casos": casos, "n_evaluables": len(con_ret),
            "por_estado": {k: _resumen(v) for k, v in por_estado.items()},
            "compra": rc, "rechazo": rr, "separacion": round(sep, 4) if sep is not None else None,
            "politica": politica.sello()}
