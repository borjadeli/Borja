"""Precio Base sin Contratos (v4.2 sec 7.2-7.4) — para empresas con tesis forward-looking.

Fórmula determinista (sin LLM):
    Precio Base = (Revenue recurrente actual × p50 EV/Sales Emerging Peers) − Deuda neta

Usa Fully Diluted Equity Value como divisor.

Output: Current FD EV, Base, Banda p25-p75, % bull case priceado, Confidence
basada en dispersión del peer group.

Limitaciones MVP: Fully Diluted shares se aproxima con shares_outstanding
(no parsea warrants/convertibles aún).
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from backend.services import edgar, market_data
from backend.utils import get_logger

log = get_logger(__name__)


# Umbrales de Confidence basado en coeficiente de variación de EV/Sales peers.
CV_CONFIDENCE_ALTA = 0.40
CV_CONFIDENCE_MEDIA = 0.70


@dataclass
class PeerStats:
    ticker: str
    market_cap: float | None
    ev: float | None
    revenue_ttm: float | None
    ev_sales: float | None


@dataclass
class PrecioBaseResult:
    ticker: str
    current_fd_equity_value_usd: float | None
    base_equity_value_usd: float | None
    base_precio: float | None
    banda_p25_precio: float | None
    banda_p75_precio: float | None
    reference_anchor_precio: float | None
    implied_future_value_usd: float | None
    pct_bull_case_priceado: float | None
    confidence: str  # 'Alta' | 'Media' | 'Baja'
    cv_emerging: float | None
    n_emerging_peers: int
    n_anchor_peers: int
    notas: list[str] = field(default_factory=list)


def _ev_sales_de_ticker(t: str) -> PeerStats:
    """Computa EV/Sales para un ticker (usado para peer y target)."""
    snap = market_data.get_price_snapshot(t)
    fin = edgar.get_financials_quarterly(t, periodos=8)
    precio = snap.precio_actual if snap else None
    shares = fin.shares_outstanding
    cash = fin.cash or 0.0
    debt = fin.total_debt or 0.0
    rev = fin.revenue_ttm

    market_cap = (precio * shares) if precio and shares else None
    ev = (market_cap + debt - cash) if market_cap is not None else None
    ev_sales = (ev / rev) if ev is not None and rev else None

    return PeerStats(
        ticker=t.upper(),
        market_cap=market_cap,
        ev=ev,
        revenue_ttm=rev,
        ev_sales=ev_sales,
    )


def _confidence_from_cv(cv: float | None) -> str:
    if cv is None:
        return "Baja"
    if cv < CV_CONFIDENCE_ALTA:
        return "Alta"
    if cv < CV_CONFIDENCE_MEDIA:
        return "Media"
    return "Baja"


def calculate_precio_base(
    ticker: str,
    revenue_recurrente_target: float | None,
    bull_case_precio: float | None,
    emerging_peers: list[str],
    anchor_peers: list[str] | None = None,
) -> PrecioBaseResult:
    """Computa precio base + banda + confidence para un ticker.

    revenue_recurrente_target: revenue del target a usar en la fórmula. Idealmente
        revenue recurrente, no total. Si None, usa revenue_ttm como aproximación
        y agrega una nota.
    bull_case_precio: precio bull case del Analista para computar % priceado.
    emerging_peers: lista 5-10 tickers de small caps comparables.
    anchor_peers: lista 1-2 tickers de mid caps establecidas (referencia).
    """
    notas: list[str] = []
    anchor_peers = anchor_peers or []

    # Stats del target
    target_stats = _ev_sales_de_ticker(ticker)
    rev_recurrente = revenue_recurrente_target
    if rev_recurrente is None:
        rev_recurrente = target_stats.revenue_ttm
        if rev_recurrente:
            notas.append("revenue_recurrente no provisto, usando revenue_ttm como aproximación")

    # FD shares (MVP: usa shares_outstanding hasta que se sume warrants/convertibles)
    target_fin = edgar.get_financials_quarterly(ticker, periodos=1)
    fd_shares = target_fin.shares_outstanding
    deuda_neta = (target_fin.total_debt or 0.0) - (target_fin.cash or 0.0)

    # Stats de emerging peers
    peer_stats: list[PeerStats] = []
    for p in emerging_peers:
        s = _ev_sales_de_ticker(p)
        if s.ev_sales is not None and s.ev_sales > 0:
            peer_stats.append(s)
    ev_sales_emerging = [p.ev_sales for p in peer_stats]

    # p25/p50/p75 + cv
    if len(ev_sales_emerging) >= 3:
        ev_sales_emerging.sort()
        p25 = statistics.quantiles(ev_sales_emerging, n=4)[0]
        p50 = statistics.median(ev_sales_emerging)
        p75 = statistics.quantiles(ev_sales_emerging, n=4)[2]
        mean = statistics.mean(ev_sales_emerging)
        stdev = statistics.stdev(ev_sales_emerging) if len(ev_sales_emerging) > 1 else 0.0
        cv = stdev / mean if mean else None
    elif len(ev_sales_emerging) == 2:
        p25 = min(ev_sales_emerging)
        p50 = statistics.mean(ev_sales_emerging)
        p75 = max(ev_sales_emerging)
        cv = (statistics.stdev(ev_sales_emerging) / p50) if p50 else None
        notas.append("solo 2 emerging peers — confidence reducida")
    elif len(ev_sales_emerging) == 1:
        p25 = p50 = p75 = ev_sales_emerging[0]
        cv = None
        notas.append("solo 1 emerging peer — métrica orientativa, no decisoria")
    else:
        p25 = p50 = p75 = None
        cv = None
        notas.append("sin emerging peers válidos — peer group inválido")

    confidence = _confidence_from_cv(cv) if cv is not None else "Baja"
    if confidence != "Alta" and len(ev_sales_emerging) >= 2:
        notas.append("Métrica orientativa, no decisoria. Peer group con alta dispersión.")

    # Cálculo de precio base
    base_ev = None
    base_precio = None
    banda_p25_precio = None
    banda_p75_precio = None
    if p50 is not None and rev_recurrente:
        base_ev = (rev_recurrente * p50) - deuda_neta
        if fd_shares:
            base_precio = base_ev / fd_shares
            banda_p25_precio = ((rev_recurrente * p25) - deuda_neta) / fd_shares if p25 else None
            banda_p75_precio = ((rev_recurrente * p75) - deuda_neta) / fd_shares if p75 else None

    # Anchor reference
    reference_anchor_precio = None
    if anchor_peers:
        anchor_stats = [_ev_sales_de_ticker(t) for t in anchor_peers]
        anchor_ev_sales = [a.ev_sales for a in anchor_stats if a.ev_sales]
        if anchor_ev_sales and rev_recurrente and fd_shares:
            anchor_p50 = statistics.median(anchor_ev_sales)
            ref_ev = (rev_recurrente * anchor_p50) - deuda_neta
            reference_anchor_precio = ref_ev / fd_shares

    # % bull case priceado
    pct_priceado = None
    if base_precio is not None and bull_case_precio and target_stats.market_cap and fd_shares:
        precio_actual = target_stats.market_cap / fd_shares
        if bull_case_precio - base_precio > 0:
            pct_priceado = ((precio_actual - base_precio) / (bull_case_precio - base_precio)) * 100.0

    # Implied future value
    implied = None
    if target_stats.market_cap and base_ev is not None:
        implied = target_stats.market_cap - base_ev

    return PrecioBaseResult(
        ticker=ticker.upper(),
        current_fd_equity_value_usd=target_stats.market_cap,
        base_equity_value_usd=base_ev,
        base_precio=round(base_precio, 2) if base_precio else None,
        banda_p25_precio=round(banda_p25_precio, 2) if banda_p25_precio else None,
        banda_p75_precio=round(banda_p75_precio, 2) if banda_p75_precio else None,
        reference_anchor_precio=round(reference_anchor_precio, 2) if reference_anchor_precio else None,
        implied_future_value_usd=implied,
        pct_bull_case_priceado=round(pct_priceado, 1) if pct_priceado is not None else None,
        confidence=confidence,
        cv_emerging=round(cv, 3) if cv is not None else None,
        n_emerging_peers=len(peer_stats),
        n_anchor_peers=len(anchor_peers),
        notas=notas,
    )
