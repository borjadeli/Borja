"""Lógica del ledger: append al log + proyección determinista a posición/caja.

Funciones puras sobre una Session inyectada (testeable con SQLite in-memory). El
estado actual (posiciones, caja, equity) es SIEMPRE una proyección del log
inmutable — nunca se guarda mutado. Ver init_docs/16_ledger_etapa2.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.ledger.models import (
    NxCashMovimiento,
    NxCorporateAction,
    NxFill,
    NxSnapshot,
)


@dataclass
class Posicion:
    ticker: str
    shares: float = 0.0
    costo_total: float = 0.0      # base total (incluye comisiones de compra)
    realized_pnl: float = 0.0

    @property
    def costo_promedio(self) -> float:
        return self.costo_total / self.shares if self.shares else 0.0


# ---------------------------- Escritura (append-only) ----------------------------

def depositar(session: Session, monto: float, fecha: date,
              tipo: str = "deposito_inicial", nota: str | None = None) -> NxCashMovimiento:
    mov = NxCashMovimiento(fecha=fecha, tipo=tipo, monto=monto, nota=nota)
    session.add(mov)
    session.flush()
    return mov


def registrar_fill(session: Session, *, ticker: str, lado: str, shares: float,
                   precio: float, comision: float = 0.0, slippage_bps: float = 0.0,
                   fecha_fill: date, fecha_decision: datetime | None = None,
                   fecha_dato: datetime | None = None, input_hash: str | None = None,
                   nota: str | None = None) -> NxFill:
    ticker = ticker.upper()
    if lado not in ("buy", "sell"):
        raise ValueError(f"lado inválido: {lado!r}")
    if shares <= 0 or precio <= 0:
        raise ValueError("shares y precio deben ser > 0")
    bruto = shares * precio
    cash_delta = -(bruto + comision) if lado == "buy" else (bruto - comision)
    fill = NxFill(ticker=ticker, lado=lado, shares=shares, precio=precio,
                  comision=comision, slippage_bps=slippage_bps, cash_delta=cash_delta,
                  fecha_fill=fecha_fill, fecha_decision=fecha_decision,
                  fecha_dato=fecha_dato, input_hash=input_hash, nota=nota)
    session.add(fill)
    session.flush()
    return fill


def aplicar_corporate_action(session: Session, *, ticker: str, tipo: str, fecha: date,
                             ratio: float | None = None, monto_por_accion: float | None = None,
                             valor_recupero: float | None = None,
                             nota: str | None = None) -> NxCorporateAction:
    ticker = ticker.upper()
    if tipo not in ("split", "dividendo", "cierre"):
        raise ValueError(f"corporate action inválida: {tipo!r}")
    ca = NxCorporateAction(ticker=ticker, tipo=tipo, fecha=fecha, ratio=ratio,
                           monto_por_accion=monto_por_accion,
                           valor_recupero=valor_recupero, nota=nota)
    session.add(ca)
    session.flush()
    return ca


# ---------------------------- Proyección (log → estado) ----------------------------

def _eventos_ordenados(session: Session) -> list[tuple]:
    """Log completo en orden cronológico determinista. Misma fecha: primero
    movimientos de caja, luego corporate actions, luego fills."""
    eventos: list[tuple] = []
    for m in session.execute(select(NxCashMovimiento)).scalars():
        eventos.append((m.fecha, 0, m.id, "cash", m))
    for c in session.execute(select(NxCorporateAction)).scalars():
        eventos.append((c.fecha, 1, c.id, "ca", c))
    for f in session.execute(select(NxFill)).scalars():
        eventos.append((f.fecha_fill, 2, f.id, "fill", f))
    eventos.sort(key=lambda e: (e[0], e[1], e[2]))
    return eventos


def proyectar(session: Session, precios: dict | None = None) -> dict:
    """Reconstruye caja + posiciones desde el log. Determinista y puro.

    precios: dict ticker->precio para valuar (sin precio de un ticker → valor 0).
    Devuelve {caja, posiciones, valor_posiciones, equity, realized_pnl}.
    """
    precios = {k.upper(): v for k, v in (precios or {}).items()}
    caja = 0.0
    pos: dict[str, Posicion] = {}

    for _fecha, _rank, _id, kind, ev in _eventos_ordenados(session):
        if kind == "cash":
            caja += ev.monto
        elif kind == "fill":
            p = pos.setdefault(ev.ticker, Posicion(ev.ticker))
            caja += ev.cash_delta
            if ev.lado == "buy":
                p.shares += ev.shares
                p.costo_total += ev.shares * ev.precio + ev.comision
            else:  # sell
                avg = p.costo_promedio
                p.realized_pnl += ev.shares * ev.precio - ev.comision - ev.shares * avg
                p.shares -= ev.shares
                p.costo_total -= ev.shares * avg
                if p.shares <= 1e-9:
                    p.shares = 0.0
                    p.costo_total = 0.0
        elif kind == "ca":
            p = pos.get(ev.ticker)
            if not p or p.shares <= 0:
                continue
            if ev.tipo == "split" and ev.ratio:
                p.shares *= ev.ratio          # costo_total intacto → avg /= ratio
            elif ev.tipo == "dividendo" and ev.monto_por_accion:
                caja += p.shares * ev.monto_por_accion
            elif ev.tipo == "cierre":
                recupero = ev.valor_recupero or 0.0
                avg = p.costo_promedio
                p.realized_pnl += p.shares * recupero - p.shares * avg
                caja += p.shares * recupero
                p.shares = 0.0
                p.costo_total = 0.0

    posiciones = {t: pp for t, pp in pos.items() if pp.shares > 0}
    valor_posiciones = sum(pp.shares * precios.get(t, 0.0) for t, pp in posiciones.items())
    equity = caja + valor_posiciones
    return {
        "caja": caja,
        "posiciones": posiciones,
        "valor_posiciones": valor_posiciones,
        "equity": equity,
        "realized_pnl": sum(pp.realized_pnl for pp in pos.values()),
    }


def snapshot(session: Session, *, fecha: date, precios: dict,
             benchmark: float | None = None, capital_inicial: float | None = None,
             pnl_ideal: float | None = None) -> NxSnapshot:
    est = proyectar(session, precios)
    pnl_modelado = (est["equity"] - capital_inicial) if capital_inicial is not None else None
    snap = NxSnapshot(fecha=fecha, equity=est["equity"], caja=est["caja"],
                      valor_posiciones=est["valor_posiciones"], pnl_ideal=pnl_ideal,
                      pnl_modelado=pnl_modelado, benchmark=benchmark,
                      n_posiciones=len(est["posiciones"]))
    session.add(snap)
    session.flush()
    return snap


def reconciliar(session: Session, precios: dict, *, tol: float = 1e-6) -> dict:
    """Chequea los invariantes de reconciliación (init_docs/16 §E). Devuelve
    {ok, violaciones, estado}."""
    est = proyectar(session, precios)
    precios = {k.upper(): v for k, v in precios.items()}
    violaciones: list[str] = []

    # Inv 1 — caja + Σ(shares×precio) == equity.
    recomputo = est["caja"] + sum(p.shares * precios.get(t, 0.0)
                                  for t, p in est["posiciones"].items())
    if abs(recomputo - est["equity"]) > tol:
        violaciones.append(f"caja+posiciones ({recomputo:.6f}) != equity ({est['equity']:.6f})")

    # Inv 7 — pesos + cash% == 100%.
    if est["equity"] > 0:
        suma = est["caja"] / est["equity"] + sum(
            p.shares * precios.get(t, 0.0) for t, p in est["posiciones"].items()) / est["equity"]
        if abs(suma - 1.0) > tol:
            violaciones.append(f"pesos+cash ({suma:.6f}) != 1.0")

    # Inv 3 — ninguna posición sin fill que la respalde.
    tickers_con_fill = {f.ticker for f in session.execute(select(NxFill)).scalars()}
    for t in est["posiciones"]:
        if t not in tickers_con_fill:
            violaciones.append(f"posición {t} sin fill que la respalde")

    return {"ok": not violaciones, "violaciones": violaciones, "estado": est}
