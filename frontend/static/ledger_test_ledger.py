"""Tests de invariantes del ledger (Etapa 2, init_docs/16 §E).

Los 7 invariantes de reconciliación son la red de seguridad del ledger. Corren
sobre SQLite in-memory — no tocan data/borja.db.
"""
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.ledger import core
from backend.ledger.models import crear_tablas

CAPITAL = 100_000.0


@pytest.fixture
def sesion():
    engine = create_engine("sqlite:///:memory:", future=True)
    crear_tablas(engine)
    with Session(engine, future=True) as s:
        core.depositar(s, CAPITAL, date(2026, 1, 1))
        yield s


def test_deposito_inicial(sesion):
    est = core.proyectar(sesion, {})
    assert est["caja"] == pytest.approx(CAPITAL)
    assert est["equity"] == pytest.approx(CAPITAL)
    assert est["posiciones"] == {}


def test_compra_descuenta_caja_y_crea_posicion(sesion):
    core.registrar_fill(sesion, ticker="ACME", lado="buy", shares=100, precio=50,
                        comision=1, fecha_fill=date(2026, 1, 2))
    est = core.proyectar(sesion, {"ACME": 50})
    assert est["caja"] == pytest.approx(CAPITAL - 5001)
    p = est["posiciones"]["ACME"]
    assert p.shares == pytest.approx(100)
    assert p.costo_total == pytest.approx(5001)
    assert est["equity"] == pytest.approx(CAPITAL - 1)  # perdió la comisión


def test_venta_realiza_pnl(sesion):
    core.registrar_fill(sesion, ticker="ACME", lado="buy", shares=100, precio=50,
                        comision=1, fecha_fill=date(2026, 1, 2))
    core.registrar_fill(sesion, ticker="ACME", lado="sell", shares=100, precio=60,
                        comision=1, fecha_fill=date(2026, 1, 3))
    est = core.proyectar(sesion, {"ACME": 60})
    # pnl = 100*60 - 1 - 100*50.01 = 998
    assert est["realized_pnl"] == pytest.approx(998)
    assert "ACME" not in est["posiciones"]
    assert est["caja"] == pytest.approx(CAPITAL + 998)
    assert est["equity"] == pytest.approx(CAPITAL + 998)


def test_split_no_cambia_equity(sesion):
    core.registrar_fill(sesion, ticker="ACME", lado="buy", shares=100, precio=50,
                        fecha_fill=date(2026, 1, 2))
    core.aplicar_corporate_action(sesion, ticker="ACME", tipo="split",
                                  fecha=date(2026, 1, 5), ratio=2.0)
    est = core.proyectar(sesion, {"ACME": 25})  # precio a la mitad tras el split
    p = est["posiciones"]["ACME"]
    assert p.shares == pytest.approx(200)
    assert p.costo_promedio == pytest.approx(25.0)
    assert est["equity"] == pytest.approx(CAPITAL)


def test_dividendo_acredita_caja(sesion):
    core.registrar_fill(sesion, ticker="ACME", lado="buy", shares=100, precio=50,
                        fecha_fill=date(2026, 1, 2))
    core.aplicar_corporate_action(sesion, ticker="ACME", tipo="dividendo",
                                  fecha=date(2026, 1, 6), monto_por_accion=0.5)
    est = core.proyectar(sesion, {"ACME": 50})
    assert est["caja"] == pytest.approx(CAPITAL - 5000 + 50)


def test_cierre_fuerza_salida(sesion):
    core.registrar_fill(sesion, ticker="ACME", lado="buy", shares=100, precio=50,
                        fecha_fill=date(2026, 1, 2))
    core.aplicar_corporate_action(sesion, ticker="ACME", tipo="cierre",
                                  fecha=date(2026, 1, 9), valor_recupero=10)
    est = core.proyectar(sesion, {"ACME": 0})
    assert "ACME" not in est["posiciones"]
    assert est["caja"] == pytest.approx(CAPITAL - 5000 + 1000)
    assert est["realized_pnl"] == pytest.approx(1000 - 5000)


def test_reconciliacion_multi_nombre(sesion):
    core.registrar_fill(sesion, ticker="ACME", lado="buy", shares=100, precio=50,
                        comision=1, fecha_fill=date(2026, 1, 2))
    core.registrar_fill(sesion, ticker="BETA", lado="buy", shares=10, precio=200,
                        comision=1, fecha_fill=date(2026, 1, 3))
    r = core.reconciliar(sesion, {"ACME": 55, "BETA": 190})
    assert r["ok"], r["violaciones"]


def test_pesos_mas_cash_suman_100(sesion):
    core.registrar_fill(sesion, ticker="ACME", lado="buy", shares=100, precio=50,
                        fecha_fill=date(2026, 1, 2))
    est = core.proyectar(sesion, {"ACME": 55})
    peso = est["posiciones"]["ACME"].shares * 55 / est["equity"]
    cash_pct = est["caja"] / est["equity"]
    assert peso + cash_pct == pytest.approx(1.0)


def test_determinismo(sesion):
    core.registrar_fill(sesion, ticker="ACME", lado="buy", shares=100, precio=50,
                        fecha_fill=date(2026, 1, 2))
    a = core.proyectar(sesion, {"ACME": 55})
    b = core.proyectar(sesion, {"ACME": 55})
    assert a["equity"] == b["equity"]
    assert a["caja"] == b["caja"]


def test_no_posicion_sin_fill(sesion):
    est = core.proyectar(sesion, {"XYZ": 10})
    assert "XYZ" not in est["posiciones"]


def test_snapshot_registra_equity(sesion):
    core.registrar_fill(sesion, ticker="ACME", lado="buy", shares=100, precio=50,
                        fecha_fill=date(2026, 1, 2))
    snap = core.snapshot(sesion, fecha=date(2026, 1, 2), precios={"ACME": 55},
                         benchmark=600.0, capital_inicial=CAPITAL)
    assert snap.equity == pytest.approx(CAPITAL + 500)   # +$5 x 100 sh
    assert snap.pnl_modelado == pytest.approx(500)
    assert snap.n_posiciones == 1


def test_fill_invalido_rechaza(sesion):
    with pytest.raises(ValueError):
        core.registrar_fill(sesion, ticker="ACME", lado="hold", shares=1, precio=1,
                            fecha_fill=date(2026, 1, 2))
    with pytest.raises(ValueError):
        core.registrar_fill(sesion, ticker="ACME", lado="buy", shares=-1, precio=1,
                            fecha_fill=date(2026, 1, 2))
