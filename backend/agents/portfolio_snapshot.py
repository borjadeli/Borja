"""Snapshot diario equity — habilita equity curve histórica.

Computa **P&L abierto** (posiciones vivas) + **P&L realizado** (trades cerrados).
El P&L total = realizado + abierto.

Modelo de capital (modo paper):
- Cada posición viva tiene `sizing_actual` (% del capital) y `precio_entrada`.
- Capital deployado por posición = sizing% × capital_total.
- Valor actual de la posición = capital deployado × (precio_actual / precio_entrada).
- P&L abierto por posición = valor actual − capital deployado.

Cuando una posición se cierra (rotar/salir), su P&L queda en `Trade.pnl_realizado_usd`.
Sumamos todos los P&L realizados para que el total no desaparezca cuando una posición sale.

Equity total = capital_inicial + pnl_realizado_acumulado + pnl_abierto_actual.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func

from backend import panic
from backend.database import session_scope
from backend.models import EstadoFicha, Ficha, PortfolioSnapshot, Trade
from backend.utils import get_logger, utcnow

log = get_logger(__name__)


def _precio_actual(f: Ficha) -> float | None:
    return f.precio_mtm or f.precio_ultima_actualizacion_ficha or f.precio_entrada


def calcular_estado_portfolio(capital_total: float | None = None) -> dict:
    """Computa estado vivo del portfolio (no persiste). Reusable por dashboard.

    Devuelve dict con equity, cash, exposición, P&L total y posiciones detalladas.
    Si capital_total es None, lo lee de panic.estado().
    """
    if capital_total is None:
        capital_total = panic.estado().get("capital_total_usd") or 0.0

    posiciones: list[dict] = []
    capital_deployado = 0.0
    valor_actual_total = 0.0
    pnl_abierto_usd = 0.0
    now = utcnow()

    with session_scope() as s:
        # P&L realizado acumulado de trades cerrados
        pnl_realizado_total = (
            s.query(func.coalesce(func.sum(Trade.pnl_realizado_usd), 0.0))
            .filter_by(status="closed").scalar() or 0.0
        )
        n_trades_cerrados = s.query(Trade).filter_by(status="closed").count()

        # Trades abiertos (informativo)
        n_trades_abiertos = s.query(Trade).filter_by(status="open").count()

        # Posiciones vivas (P&L abierto)
        rows = (
            s.query(Ficha)
            .filter(Ficha.estado.in_([
                EstadoFicha.PORTFOLIO_ACTIVO.value,
                EstadoFicha.BUCKET_EXPLORATORIO.value,
            ]))
            .all()
        )
        for f in rows:
            sizing_pct = f.sizing_actual or 0.0
            precio_act = _precio_actual(f)
            precio_in = f.precio_entrada
            cap_deployado = (sizing_pct / 100.0) * (capital_total or 0.0)
            if precio_in and precio_act:
                valor_act = cap_deployado * (precio_act / precio_in)
                pnl_pct = (precio_act - precio_in) / precio_in * 100.0
            else:
                valor_act = cap_deployado
                pnl_pct = 0.0
            pnl_usd = valor_act - cap_deployado

            dias = None
            if f.fecha_entrada_portfolio:
                dias = (now - f.fecha_entrada_portfolio).days

            posiciones.append({
                "ticker": f.ticker,
                "nombre": f.nombre,
                "sector": f.sector,
                "estado": f.estado,
                "sizing_pct": sizing_pct,
                "precio_entrada": precio_in,
                "precio_actual": precio_act,
                "precio_mtm_at": f.precio_mtm_at.isoformat() if f.precio_mtm_at else None,
                "capital_deployado_usd": round(cap_deployado, 2),
                "valor_actual_usd": round(valor_act, 2),
                "pnl_pct": round(pnl_pct, 2),
                "pnl_usd": round(pnl_usd, 2),
                "dias_en_cartera": dias,
            })
            capital_deployado += cap_deployado
            valor_actual_total += valor_act
            pnl_abierto_usd += pnl_usd

    # Equity total v4.2: capital + realizado acumulado + abierto vigente.
    # El cash refleja la imagen actual (capital - capital deployado en posiciones vivas).
    pnl_total_usd = pnl_realizado_total + pnl_abierto_usd
    cash = (capital_total or 0.0) - capital_deployado + pnl_realizado_total
    equity_total = cash + valor_actual_total
    pnl_total_pct = (pnl_total_usd / capital_total * 100.0) if capital_total else 0.0
    exposicion_pct = (capital_deployado / capital_total * 100.0) if capital_total else 0.0

    return {
        "capital_total_usd": round(capital_total or 0.0, 2),
        "capital_deployado_usd": round(capital_deployado, 2),
        "valor_actual_usd": round(valor_actual_total, 2),
        "cash_usd": round(cash, 2),
        "equity_total_usd": round(equity_total, 2),
        "exposicion_pct": round(exposicion_pct, 2),
        "pnl_total_usd": round(pnl_total_usd, 2),
        "pnl_total_pct": round(pnl_total_pct, 2),
        "pnl_realizado_usd": round(pnl_realizado_total, 2),
        "pnl_abierto_usd": round(pnl_abierto_usd, 2),
        "n_posiciones": len(posiciones),
        "n_trades_cerrados": n_trades_cerrados,
        "n_trades_abiertos": n_trades_abiertos,
        "posiciones": posiciones,
    }


def generar_snapshot_diario() -> dict:
    """Persiste snapshot del día en portfolio_snapshots. Idempotente por fecha (ET-naive)."""
    estado = calcular_estado_portfolio()
    fecha = utcnow().strftime("%Y-%m-%d")

    with session_scope() as s:
        existente = s.query(PortfolioSnapshot).filter_by(fecha=fecha).first()
        # P&L del día = equity hoy − equity de ayer (si hay snapshot previo)
        ayer = (
            s.query(PortfolioSnapshot)
            .filter(PortfolioSnapshot.fecha < fecha)
            .order_by(PortfolioSnapshot.fecha.desc())
            .first()
        )
        pnl_dia = (
            estado["equity_total_usd"] - ayer.equity_total_usd
            if ayer else 0.0
        )

        if existente:
            existente.timestamp = utcnow()
            existente.capital_total_usd = estado["capital_total_usd"]
            existente.equity_total_usd = estado["equity_total_usd"]
            existente.cash_usd = estado["cash_usd"]
            existente.exposicion_pct = estado["exposicion_pct"]
            existente.n_posiciones = estado["n_posiciones"]
            existente.pnl_total_usd = estado["pnl_total_usd"]
            existente.pnl_total_pct = estado["pnl_total_pct"]
            existente.pnl_dia_usd = round(pnl_dia, 2)
            existente.posiciones_json = estado["posiciones"]
            snapshot_id = existente.id
        else:
            snap = PortfolioSnapshot(
                timestamp=utcnow(),
                fecha=fecha,
                capital_total_usd=estado["capital_total_usd"],
                equity_total_usd=estado["equity_total_usd"],
                cash_usd=estado["cash_usd"],
                exposicion_pct=estado["exposicion_pct"],
                n_posiciones=estado["n_posiciones"],
                pnl_total_usd=estado["pnl_total_usd"],
                pnl_total_pct=estado["pnl_total_pct"],
                pnl_dia_usd=round(pnl_dia, 2),
                posiciones_json=estado["posiciones"],
            )
            s.add(snap)
            s.flush()
            snapshot_id = snap.id

    log.info(
        "portfolio_snapshot — fecha=%s equity=%.2f pnl_total=%.2f pnl_dia=%.2f n=%d",
        fecha, estado["equity_total_usd"], estado["pnl_total_usd"], pnl_dia, estado["n_posiciones"],
    )
    return {
        "snapshot_id": snapshot_id,
        "fecha": fecha,
        "equity_total_usd": estado["equity_total_usd"],
        "pnl_total_usd": estado["pnl_total_usd"],
        "pnl_dia_usd": round(pnl_dia, 2),
        "n_posiciones": estado["n_posiciones"],
    }
