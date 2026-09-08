"""Equity curve histórica + benchmark SPY.

Backfill de portfolio_snapshots usando precios de cierre históricos (Yahoo) +
los Trades ya registrados (apertura/cierre). Determinista, sin LLM.

Permite generar la curva diaria desde el primer trade hasta hoy y compararla
con SPY normalizado al mismo capital base.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from backend import panic
from backend.database import session_scope
from backend.models import PortfolioSnapshot, Trade
from backend.services.market_data import get_price_history
from backend.utils import get_logger, utcnow

log = get_logger(__name__)


def _historico_diario(ticker: str, period: str = "3mo") -> dict[date, float]:
    """Devuelve {date: close} para un ticker."""
    rows = get_price_history(ticker, period=period)
    return {row["date"].date(): float(row["close"]) for row in rows if row.get("close")}


def _daterange(d_inicio: date, d_fin: date):
    cur = d_inicio
    while cur <= d_fin:
        yield cur
        cur += timedelta(days=1)


def computar_equity_dia(
    fecha: date,
    capital_total: float,
    trades: list,
    precios: dict[str, dict[date, float]],
) -> dict | None:
    """Equity al cierre de `fecha`. None si no hay datos suficientes (fin de semana).

    Para cada Trade:
    - Si fecha_apertura > fecha: trade aún no existía → ignorar.
    - Si trade abierto y fecha_apertura ≤ fecha: P&L abierto al precio de ese día.
    - Si trade cerrado y fecha_cierre ≤ fecha: P&L realizado fijo.
    - Si trade cerrado pero fecha < fecha_cierre: trade aún abierto ese día → P&L abierto.
    """
    if fecha.weekday() >= 5:  # sábado/domingo
        return None

    equity = float(capital_total)
    pnl_realizado = 0.0
    pnl_abierto = 0.0
    n_open = 0
    n_closed = 0
    posiciones_dia: list[dict] = []

    for t in trades:
        if t.fecha_apertura.date() > fecha:
            continue  # trade aún no abierto

        cerrado_a_la_fecha = (
            t.status == "closed"
            and t.fecha_cierre is not None
            and t.fecha_cierre.date() <= fecha
        )

        if cerrado_a_la_fecha:
            pnl_realizado += t.pnl_realizado_usd or 0.0
            n_closed += 1
            continue

        # Trade activo en `fecha`: tomar precio de cierre de ese día (o el más cercano anterior)
        hist = precios.get(t.ticker, {})
        precio_dia = hist.get(fecha)
        if precio_dia is None:
            # Buscar el más cercano hacia atrás (hasta 5 días, por feriados)
            for delta in range(1, 6):
                precio_dia = hist.get(fecha - timedelta(days=delta))
                if precio_dia:
                    break
        if precio_dia is None:
            continue

        valor_dia = t.capital_deployado_usd * (precio_dia / t.precio_entrada)
        pnl_t = valor_dia - t.capital_deployado_usd
        pnl_abierto += pnl_t
        n_open += 1
        posiciones_dia.append({
            "ticker": t.ticker,
            "precio_entrada": t.precio_entrada,
            "precio_dia": precio_dia,
            "pnl_usd": round(pnl_t, 2),
        })

    pnl_total = pnl_realizado + pnl_abierto
    equity += pnl_total

    return {
        "fecha": fecha.strftime("%Y-%m-%d"),
        "equity_total_usd": round(equity, 2),
        "pnl_total_usd": round(pnl_total, 2),
        "pnl_realizado_usd": round(pnl_realizado, 2),
        "pnl_abierto_usd": round(pnl_abierto, 2),
        "n_open": n_open,
        "n_closed": n_closed,
        "posiciones_dia": posiciones_dia,
    }


def backfill_equity_historico(fecha_inicio: date | None = None) -> dict:
    """Recompone portfolio_snapshots día por día desde la primera apertura de trade.

    Idempotente: si ya hay snapshot para una fecha, lo actualiza.
    """
    capital_total = panic.estado().get("capital_total_usd") or 0.0
    if not capital_total:
        return {"error": "capital_total_usd no configurado"}

    with session_scope() as s:
        trades = s.query(Trade).all()
        if not trades:
            return {"error": "no hay trades — nada que backfillear"}
        # Detach: convertir a dataclasses simples para no mantener sesión abierta
        trades_simples = [
            type("T", (), {
                "ticker": t.ticker,
                "status": t.status,
                "fecha_apertura": t.fecha_apertura,
                "precio_entrada": t.precio_entrada,
                "capital_deployado_usd": t.capital_deployado_usd,
                "fecha_cierre": t.fecha_cierre,
                "pnl_realizado_usd": t.pnl_realizado_usd,
            })()
            for t in trades
        ]
        primera_apertura = min(t.fecha_apertura for t in trades_simples).date()

    inicio = fecha_inicio or primera_apertura
    hoy = utcnow().date()

    # Bajar histórico de todos los tickers involucrados
    tickers = sorted({t.ticker for t in trades_simples})
    log.info("backfill_equity — descargando histórico Yahoo: %s", tickers)
    precios: dict[str, dict[date, float]] = {}
    for tk in tickers:
        precios[tk] = _historico_diario(tk, period="3mo")

    # Computar y persistir cada día (laborales)
    creados = 0
    actualizados = 0
    saltados = 0
    detalle: list[dict] = []
    for d in _daterange(inicio, hoy):
        dia = computar_equity_dia(d, capital_total, trades_simples, precios)
        if dia is None:
            saltados += 1
            continue
        with session_scope() as s:
            snap = s.query(PortfolioSnapshot).filter_by(fecha=dia["fecha"]).first()
            if snap:
                snap.equity_total_usd = dia["equity_total_usd"]
                snap.pnl_total_usd = dia["pnl_total_usd"]
                # pnl_total_pct = (pnl / capital) * 100
                snap.pnl_total_pct = round(dia["pnl_total_usd"] / capital_total * 100.0, 4)
                actualizados += 1
            else:
                snap = PortfolioSnapshot(
                    timestamp=datetime.combine(d, datetime.min.time()),
                    fecha=dia["fecha"],
                    capital_total_usd=capital_total,
                    equity_total_usd=dia["equity_total_usd"],
                    cash_usd=capital_total - sum(t.capital_deployado_usd for t in trades_simples if t.status == "open" and t.fecha_apertura.date() <= d),
                    exposicion_pct=0.0,
                    n_posiciones=dia["n_open"],
                    pnl_total_usd=dia["pnl_total_usd"],
                    pnl_total_pct=round(dia["pnl_total_usd"] / capital_total * 100.0, 4),
                    pnl_dia_usd=0.0,  # se recalcula abajo
                    posiciones_json=dia["posiciones_dia"],
                )
                s.add(snap)
                creados += 1
        detalle.append({
            "fecha": dia["fecha"],
            "equity": dia["equity_total_usd"],
            "pnl": dia["pnl_total_usd"],
        })

    # Recalcular pnl_dia_usd (delta vs día anterior)
    with session_scope() as s:
        snaps = s.query(PortfolioSnapshot).order_by(PortfolioSnapshot.fecha.asc()).all()
        prev_eq: float | None = None
        for sn in snaps:
            if prev_eq is not None:
                sn.pnl_dia_usd = round(sn.equity_total_usd - prev_eq, 2)
            else:
                sn.pnl_dia_usd = 0.0
            prev_eq = sn.equity_total_usd

    log.info(
        "backfill_equity — creados=%d actualizados=%d saltados=%d",
        creados, actualizados, saltados,
    )
    return {
        "creados": creados,
        "actualizados": actualizados,
        "saltados_finsem": saltados,
        "detalle": detalle,
    }


def equity_curve_vs_spy(fecha_desde: str | None = None) -> dict:
    """Devuelve la curva BORJA vs SPY normalizada al capital base.

    Output: {
        "fechas": ["2026-04-21", ...],
        "borja_equity": [100000.0, ...],
        "spy_equity": [100000.0, ...],   (normalizado al mismo capital base)
        "borja_pct": [0.0, ...],
        "spy_pct": [0.0, ...],
        "alpha_pct": [0.0, ...],         (borja - spy)
    }
    """
    capital_total = panic.estado().get("capital_total_usd") or 100_000.0

    with session_scope() as s:
        snaps_q = s.query(PortfolioSnapshot).order_by(PortfolioSnapshot.fecha.asc())
        if fecha_desde:
            snaps_q = snaps_q.filter(PortfolioSnapshot.fecha >= fecha_desde)
        snaps = snaps_q.all()
        snap_data = [
            {"fecha": sn.fecha, "equity": sn.equity_total_usd, "pnl_pct": sn.pnl_total_pct}
            for sn in snaps
        ]

    if not snap_data:
        return {"fechas": [], "borja_equity": [], "spy_equity": [], "borja_pct": [], "spy_pct": [], "alpha_pct": []}

    fechas = [d["fecha"] for d in snap_data]

    # SPY histórico
    spy_hist = _historico_diario("SPY", period="3mo")
    fecha_inicio = datetime.strptime(fechas[0], "%Y-%m-%d").date()

    # Precio SPY en fecha_inicio (o el más cercano hacia atrás)
    spy_inicial = None
    for delta in range(0, 8):
        spy_inicial = spy_hist.get(fecha_inicio - timedelta(days=delta))
        if spy_inicial:
            break
    if spy_inicial is None:
        # Sin datos SPY: devolver solo BORJA
        return {
            "fechas": fechas,
            "borja_equity": [d["equity"] for d in snap_data],
            "spy_equity": [],
            "borja_pct": [d["pnl_pct"] for d in snap_data],
            "spy_pct": [],
            "alpha_pct": [],
        }

    borja_equity: list[float] = []
    spy_equity: list[float] = []
    borja_pct: list[float] = []
    spy_pct: list[float] = []
    alpha_pct: list[float] = []
    for d in snap_data:
        f_date = datetime.strptime(d["fecha"], "%Y-%m-%d").date()
        precio_spy = spy_hist.get(f_date)
        if precio_spy is None:
            for delta in range(1, 6):
                precio_spy = spy_hist.get(f_date - timedelta(days=delta))
                if precio_spy:
                    break
        if precio_spy is None:
            continue
        spy_eq = capital_total * (precio_spy / spy_inicial)
        spy_p = (precio_spy / spy_inicial - 1) * 100.0

        borja_equity.append(round(d["equity"], 2))
        spy_equity.append(round(spy_eq, 2))
        borja_pct.append(round(d["pnl_pct"], 3))
        spy_pct.append(round(spy_p, 3))
        alpha_pct.append(round(d["pnl_pct"] - spy_p, 3))

    # Drawdown — caída desde el peak histórico, calculado punto a punto.
    # No requiere supuestos estadísticos: es un hecho duro sobre la peor caída.
    def _drawdown_series(equity: list[float]) -> list[float]:
        out: list[float] = []
        peak = equity[0] if equity else 0.0
        for v in equity:
            if v > peak:
                peak = v
            dd = ((v - peak) / peak * 100.0) if peak else 0.0
            out.append(round(dd, 3))
        return out

    borja_dd = _drawdown_series(borja_equity)
    spy_dd = _drawdown_series(spy_equity)

    return {
        "fechas": fechas[:len(borja_equity)],
        "capital_total_usd": capital_total,
        "borja_equity": borja_equity,
        "spy_equity": spy_equity,
        "borja_pct": borja_pct,
        "spy_pct": spy_pct,
        "alpha_pct": alpha_pct,
        "borja_drawdown_pct": borja_dd,
        "spy_drawdown_pct": spy_dd,
        "borja_max_drawdown_pct": round(min(borja_dd) if borja_dd else 0.0, 3),
        "spy_max_drawdown_pct": round(min(spy_dd) if spy_dd else 0.0, 3),
        "borja_drawdown_actual_pct": borja_dd[-1] if borja_dd else 0.0,
        "spy_drawdown_actual_pct": spy_dd[-1] if spy_dd else 0.0,
    }
