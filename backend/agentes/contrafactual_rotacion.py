"""P2.1 (doc 91) — Contrafactual de ROTACIÓN: ¿cada rotación MEJORA vs mantener?

Cada vez que BORJA vende A y compra B, seguimos AMBAS virtualmente a 30/90/180/365 días. Descubre si BORJA es
bueno ENCONTRANDO pero malo VENDIENDO (vende ganadores temprano), o si evita pérdidas permanentes. Es —según
IA2— la mejor forma de validar el edge: "mucho más informativo que saber que el Auditor aprobó el 95%".

Barato ($0, sin LLM): lee el ledger de decisiones (ya tiene ticker/accion/precio/ciclo) + precios históricos. NO
toca el path de decisión. Las decisiones recientes quedan PENDIENTES hasta que venza cada horizonte (como los
falsadores): el instrumento se puebla con el tiempo.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

HORIZONTES = (30, 90, 180, 365)       # días
_VENTAS = ("vender", "caja")
_COMPRAS = ("comprar", "aumentar")


def _close_en_o_despues(hist: dict, objetivo: date) -> float | None:
    """El close en o después de `objetivo` (el primero disponible). None si la historia no llega hasta ahí."""
    if not hist:
        return None
    obj = objetivo.isoformat()
    futuras = sorted(d for d in hist if d >= obj)
    return hist[futuras[0]] if futuras else None


@dataclass
class ResultadoHorizonte:
    dias: int
    n_ventas: int = 0
    n_compras: int = 0
    ret_ventas: float | None = None    # retorno medio de lo VENDIDO (si se hubiera MANTENIDO)
    ret_compras: float | None = None   # retorno medio de lo COMPRADO
    edge: float | None = None          # compras − ventas (POSITIVO = la rotación agregó; NEGATIVO = vendió mejor de lo que compró)


def contrafactual(decisiones, *, hist_fn, hoy: date | None = None) -> list[ResultadoHorizonte]:
    """`decisiones` = registros del ledger (con .accion/.precio/.ciclo/.ejecutada). `hist_fn(ticker) -> {date_iso:
    close}`. Devuelve un ResultadoHorizonte por cada horizonte (solo cuenta decisiones cuyo horizonte YA venció)."""
    hoy = hoy or date.today()
    items: list[tuple[str, str, date, float]] = []     # (lado, ticker, fecha_decisión, precio)
    for d in decisiones:
        if not getattr(d, "ejecutada", True):          # solo rotaciones que MOVIERON el libro
            continue
        acc = (getattr(d, "accion", "") or "").lower()
        p0 = getattr(d, "precio", None)
        if not p0:
            continue
        try:
            fdec = date.fromisoformat((getattr(d, "ciclo", "") or "")[:10])
        except ValueError:
            continue
        if acc in _VENTAS:
            items.append(("venta", d.ticker.upper(), fdec, p0))
        elif acc in _COMPRAS:
            items.append(("compra", d.ticker.upper(), fdec, p0))

    hist_cache: dict[str, dict] = {}
    out: list[ResultadoHorizonte] = []
    for h in HORIZONTES:
        rv: list[float] = []
        rc: list[float] = []
        for lado, tk, fdec, p0 in items:
            fh = fdec + timedelta(days=h)
            if fh > hoy:                               # horizonte aún no vencido → pendiente
                continue
            hist = hist_cache.setdefault(tk, hist_fn(tk) or {})
            c = _close_en_o_despues(hist, fh)
            if not c:
                continue
            (rv if lado == "venta" else rc).append(c / p0 - 1.0)
        res = ResultadoHorizonte(dias=h, n_ventas=len(rv), n_compras=len(rc),
                                 ret_ventas=(sum(rv) / len(rv) if rv else None),
                                 ret_compras=(sum(rc) / len(rc) if rc else None))
        if res.ret_ventas is not None and res.ret_compras is not None:
            res.edge = res.ret_compras - res.ret_ventas
        out.append(res)
    return out
