"""P2.1 (doc 91) — contrafactual de rotación: ¿vender A para comprar B mejoró o empeoró?"""
from datetime import date
from types import SimpleNamespace

from backend.agentes.contrafactual_rotacion import contrafactual


def _dec(ticker, accion, precio, ciclo, ejecutada=True):
    return SimpleNamespace(ticker=ticker, accion=accion, precio=precio, ciclo=ciclo, ejecutada=ejecutada)


def test_rotacion_mala_vendio_ganador():
    # Vendió A (que luego subió +50%) para comprar B (que subió solo +10%) → edge NEGATIVO a 30d (vendió temprano).
    decisiones = [_dec("A", "vender", 100.0, "2026-01-01"),
                  _dec("B", "comprar", 100.0, "2026-01-01")]
    hist = {"A": {"2026-01-31": 150.0}, "B": {"2026-01-31": 110.0}}
    res = contrafactual(decisiones, hist_fn=lambda t: hist[t], hoy=date(2026, 6, 1))
    h30 = next(r for r in res if r.dias == 30)
    assert abs(h30.ret_ventas - 0.50) < 1e-9 and abs(h30.ret_compras - 0.10) < 1e-9
    assert h30.edge < 0 and abs(h30.edge + 0.40) < 1e-9        # la rotación RESTÓ valor


def test_rotacion_buena_vendio_perdedor():
    # Vendió A (que cayó -30%) para comprar B (que subió +20%) → edge POSITIVO (evitó pérdida + capturó upside).
    decisiones = [_dec("A", "vender", 100.0, "2026-01-01"),
                  _dec("B", "comprar", 100.0, "2026-01-01")]
    hist = {"A": {"2026-01-31": 70.0}, "B": {"2026-01-31": 120.0}}
    res = contrafactual(decisiones, hist_fn=lambda t: hist[t], hoy=date(2026, 6, 1))
    h30 = next(r for r in res if r.dias == 30)
    assert h30.edge > 0 and abs(h30.edge - 0.50) < 1e-9


def test_horizonte_no_vencido_queda_pendiente():
    # Decisión de ayer → ningún horizonte (≥30d) venció todavía → n=0, sin edge (se poblará con el tiempo).
    decisiones = [_dec("A", "vender", 100.0, "2026-11-24"), _dec("B", "comprar", 100.0, "2026-11-24")]
    res = contrafactual(decisiones, hist_fn=lambda t: {}, hoy=date(2026, 11, 25))
    assert all(r.n_ventas == 0 and r.n_compras == 0 and r.edge is None for r in res)


def test_no_ejecutada_no_cuenta():
    # un aumento BLOQUEADO (ejecutada=False) no es una rotación real → no entra.
    decisiones = [_dec("B", "comprar", 100.0, "2026-01-01", ejecutada=False)]
    res = contrafactual(decisiones, hist_fn=lambda t: {"2026-01-31": 200.0}, hoy=date(2026, 6, 1))
    assert all(r.n_compras == 0 for r in res)
