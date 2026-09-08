"""P&L / mark-to-market / equity del libro paper del núcleo nuevo.

Modelo simple y honesto: capital simulado fijo ($100K). El sizing de cada posición
es su % del capital inicial; las shares se derivan del precio de entrada. El equity
se marca a mercado con el precio actual. La curva se arma con snapshots diarios
(arranca hoy; se llena con el tiempo — no se backfillea porque el libro nació hoy).
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.utils import get_logger

log = get_logger(__name__)

CAPITAL_INICIAL = 100_000.0


def marcar(libro, precios: dict[str, float]) -> dict:
    """Mark-to-market del libro dado un dict {ticker: precio_actual}.

    Devuelve equity, cash, P&L total y P&L por posición. Puro (no toca red).
    """
    invertido_frac = sum(p.get("sizing") or 0 for p in libro.posiciones.values())
    cash = CAPITAL_INICIAL * (1 - invertido_frac)

    posiciones = []
    valor_mkt_total = 0.0
    costo_total = 0.0
    for ticker, p in libro.posiciones.items():
        sizing = p.get("sizing") or 0
        costo = sizing * CAPITAL_INICIAL
        pe = p.get("precio_entrada")
        precio = precios.get(ticker)
        if pe and precio:
            shares = costo / pe
            valor = shares * precio
            pnl = valor - costo
            pnl_pct = precio / pe - 1
        else:
            valor, pnl, pnl_pct = costo, 0.0, 0.0   # sin precio → asumir flat.
        valor_mkt_total += valor
        costo_total += costo
        posiciones.append({
            "ticker": ticker, "sizing": sizing, "arquetipo": p.get("arquetipo"),
            "merito": p.get("merito"), "precio_entrada": pe, "precio_actual": precio,
            "costo": costo, "valor": valor, "pnl": pnl, "pnl_pct": pnl_pct,
        })

    equity = cash + valor_mkt_total
    pnl_total = equity - CAPITAL_INICIAL
    posiciones.sort(key=lambda x: -(x["valor"]))
    return {
        "equity": equity,
        "cash": cash,
        "invertido_mkt": valor_mkt_total,
        "invertido_pct": invertido_frac,
        "pnl_total": pnl_total,
        "pnl_total_pct": pnl_total / CAPITAL_INICIAL,
        "pnl_abierto": valor_mkt_total - costo_total,
        "n_posiciones": len(posiciones),
        "posiciones": posiciones,
        "capital_inicial": CAPITAL_INICIAL,
    }


def registrar_snapshot(libro, mtm: dict, fecha: str, spy: float | None = None) -> None:
    """Agrega un punto a la curva de equity del libro (idempotente por fecha).
    `spy` = precio de SPY ese día, para el benchmark (se guarda crudo; se normaliza
    al graficar)."""
    snaps = getattr(libro, "snapshots", None)
    if snaps is None:
        libro.snapshots = []
        snaps = libro.snapshots
    # Reemplaza el del mismo día si ya existe (un punto por día).
    snaps[:] = [s for s in snaps if s.get("fecha", "")[:10] != fecha[:10]]
    snaps.append({"fecha": fecha, "equity": round(mtm["equity"], 2),
                  "pnl_pct": round(mtm["pnl_total_pct"], 6), "spy": spy})
    snaps.sort(key=lambda s: s["fecha"])


def _backfill_spy(snapshots: list) -> None:
    """Rellena el precio de SPY en snapshots que no lo tengan (vía histórico)."""
    from datetime import date, timedelta
    from backend.agents.equity_curve import _historico_diario
    faltan = [s for s in snapshots if s.get("spy") is None]
    if not faltan:
        return
    spy_hist = _historico_diario("SPY", period="6mo")
    for s in faltan:
        try:
            d = date.fromisoformat(s["fecha"][:10])
        except ValueError:
            continue
        for delta in range(0, 12):
            px = spy_hist.get(d - timedelta(days=delta))
            if px:
                s["spy"] = px
                break


def curva_vs_spy(snapshots: list) -> dict:
    """Normaliza la curva de equity y SPY al mismo capital base (§benchmark).
    Puro: usa el SPY ya guardado en cada snapshot. Devuelve series alineadas."""
    if not snapshots:
        return {"fechas": [], "equity": [], "spy_equity": [], "alpha_pct": []}
    fechas = [s["fecha"][:10] for s in snapshots]
    equity = [s["equity"] for s in snapshots]
    spy_px = [s.get("spy") for s in snapshots]
    spy0 = next((p for p in spy_px if p), None)
    spy_equity, alpha = [], []
    for i, px in enumerate(spy_px):
        if px and spy0:
            se = round(CAPITAL_INICIAL * px / spy0, 2)
            spy_equity.append(se)
            alpha.append(round((equity[i] - se) / CAPITAL_INICIAL * 100, 2))
        else:
            spy_equity.append(None)
            alpha.append(None)
    return {"fechas": fechas, "equity": equity, "spy_equity": spy_equity, "alpha_pct": alpha}


def _precio_actual(ticker: str) -> float | None:
    from backend.agents.equity_curve import _historico_diario
    from backend.services import market_data
    snap = market_data.get_price_snapshot(ticker)
    if snap and snap.precio_actual:
        return snap.precio_actual
    hist = _historico_diario(ticker, period="5d")
    return max(hist.items())[1] if hist else None


def correr_snapshot() -> dict | None:
    """Trae precios, marca a mercado el libro paper, registra snapshot + last_mtm y
    persiste. Reusado por el CLI y por el job diario. Devuelve el MtM (o None)."""
    from datetime import datetime
    from backend.seleccion import paper_trader as pt
    libro = pt.cargar_libro()
    if not libro.posiciones:
        return None
    precios = {t: p for t in libro.posiciones if (p := _precio_actual(t))}
    # Guarda anti-blip: si el fetch de precios falló para la mayoría de las posiciones,
    # NO marcar — un last_mtm bueno NO debe ser pisado por un P&L 0 espurio por una
    # falla de red transitoria (incidente 2026-06-30).
    if len(precios) < max(1, len(libro.posiciones) // 2):
        log.warning("paper_pnl — precios %d/%d; se omite el snapshot para no pisar el P&L con un marcado flat",
                    len(precios), len(libro.posiciones))
        return None
    mtm = marcar(libro, precios)
    fecha = datetime.utcnow().isoformat(timespec="seconds")
    spy = _precio_actual("SPY")                      # benchmark del día.
    registrar_snapshot(libro, mtm, fecha, spy=spy)
    _backfill_spy(libro.snapshots)                   # rellena SPY de puntos viejos.
    libro.last_mtm = {**mtm, "fecha": fecha, "precios": precios}
    pt.guardar_libro(libro)
    return mtm
