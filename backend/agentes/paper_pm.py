"""Paper nuevo v2 (Fase 4, doc 55 §1.5) — ejecuta una decisión del PM contra el ledger fiel.

Opera desde `ResultadoDecision` (del orquestador de decisión): traduce `pesos_finales` (fracciones objetivo
de cartera, ya pasadas por el gate del IPS) a **acciones enteras** y emite fills al ledger fiel
(`backend.ledger.core`, append-only, con proyección + P&L + reconciliación). Reemplaza al `paper_trader` v3
(mérito/sizing_final/selector/challenger), que queda congelado hasta su archivado físico.

Reglas:
- `equity` y las posiciones actuales salen del propio ledger (proyección point-in-time con `precios`).
- objetivo por nombre = `peso_final × equity` → `shares = floor(valor / precio)` (acciones enteras).
- un nombre en cartera que NO está en `pesos_finales` → se vende entero (el PM lo sacó).
- **ventas primero** (liberan caja), después compras acotadas por la caja disponible (no sobre-gira).
- **demoradas**: un aumento demorado 1 ciclo por el auditor NO se ejecuta (se mantiene el nombre como está).
- `no_action` (violación agregada) → no se ejecuta nada.

Puro sobre una `Session` inyectada (SQLite in-memory en tests), igual que `ledger.core`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from backend.agentes.orquestador_decision import ResultadoDecision
from backend.ledger import core


@dataclass
class _Orden:
    ticker: str
    lado: str          # buy | sell
    shares: int
    precio: float


@dataclass
class ResultadoPaper:
    fills: list[dict] = field(default_factory=list)       # {ticker, lado, shares, precio}
    demoradas: list[str] = field(default_factory=list)    # aumentos no ejecutados (demora 1 ciclo)
    sin_precio: list[str] = field(default_factory=list)   # nombres objetivo sin precio → no operados
    nota: str | None = None


def ejecutar(session: Session, resultado: ResultadoDecision, *, precios: dict[str, float],
             fecha_fill: date | None = None, comision: float = 0.0,
             input_hash: str | None = None) -> ResultadoPaper:
    fecha_fill = fecha_fill or date.today()
    precios = {t.upper(): float(p) for t, p in precios.items() if p and math.isfinite(p) and p > 0}
    demoradas = {t.upper() for t in resultado.demoradas}

    if resultado.no_action:
        return ResultadoPaper(nota="NO_ACTION (violación agregada del IPS) — no se opera")

    est = core.proyectar(session, precios)
    equity = est["equity"]
    if equity <= 0:
        return ResultadoPaper(nota="equity <= 0 (falta depósito inicial) — no se opera")
    shares_actuales = {t: int(round(p.shares)) for t, p in est["posiciones"].items()}

    objetivo = {t.upper(): w for t, w in resultado.pesos_finales.items()}
    nombres = set(objetivo) | set(shares_actuales)

    res = ResultadoPaper()
    ordenes: list[_Orden] = []
    for tk in sorted(nombres):
        peso = objetivo.get(tk, 0.0)                      # no mencionado → objetivo 0 (venta)
        actual = shares_actuales.get(tk, 0)
        if peso > 0 and tk not in precios:
            res.sin_precio.append(tk)
            continue                                       # sin precio no se puede dimensionar → no se toca
        precio = precios.get(tk, 0.0)
        objetivo_shares = int(math.floor(peso * equity / precio)) if peso > 0 and precio > 0 else 0

        # demora: no ejecutar un AUMENTO demorado (se mantiene como está).
        if tk in demoradas and objetivo_shares > actual:
            res.demoradas.append(tk)
            continue

        delta = objetivo_shares - actual
        if delta > 0:
            ordenes.append(_Orden(tk, "buy", delta, precio))
        elif delta < 0:
            ordenes.append(_Orden(tk, "sell", -delta, precio))

    # Ventas primero (liberan caja), después compras acotadas por la caja disponible.
    ordenes.sort(key=lambda o: 0 if o.lado == "sell" else 1)
    caja = est["caja"]
    for o in ordenes:
        if o.lado == "sell":
            caja += o.shares * o.precio - comision
        else:
            costo = o.shares * o.precio + comision
            if costo > caja + 1e-9:                        # recorta la compra a lo que alcanza la caja
                asequibles = int(math.floor((caja - comision) / o.precio)) if o.precio > 0 else 0
                if asequibles <= 0:
                    continue
                o.shares = asequibles
                costo = o.shares * o.precio + comision
            caja -= costo
        core.registrar_fill(session, ticker=o.ticker, lado=o.lado, shares=o.shares, precio=o.precio,
                             comision=comision, fecha_fill=fecha_fill, input_hash=input_hash,
                             nota="paper_pm")
        res.fills.append({"ticker": o.ticker, "lado": o.lado, "shares": o.shares, "precio": o.precio})
    return res
