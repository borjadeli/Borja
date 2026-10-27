"""Tests del paper nuevo v2 (Fase 4, doc 55 §1.5). Ledger fiel SQLite in-memory, sin API."""
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.agentes.orquestador_decision import ResultadoDecision
from backend.agentes.paper_pm import ejecutar
from backend.ledger import core
from backend.ledger.models import crear_tablas

CAPITAL = 100_000.0
F = date(2026, 10, 27)


@pytest.fixture
def sesion():
    engine = create_engine("sqlite:///:memory:", future=True)
    crear_tablas(engine)
    with Session(engine, future=True) as s:
        core.depositar(s, CAPITAL, date(2026, 1, 1))
        yield s


def _res(pesos_finales, *, no_action=False, demoradas=None):
    return ResultadoDecision(pesos_objetivo=dict(pesos_finales), pesos_finales=dict(pesos_finales),
                             caja_final=round(1 - sum(pesos_finales.values()), 6),
                             clip="none", no_action=no_action, demoradas=demoradas or [])


def test_compra_traduce_peso_a_shares_enteras(sesion):
    r = ejecutar(sesion, _res({"OKLO": 0.1}), precios={"OKLO": 50.0}, fecha_fill=F)
    assert r.fills == [{"ticker": "OKLO", "lado": "buy", "shares": 200, "precio": 50.0}]
    est = core.proyectar(sesion, {"OKLO": 50.0})
    assert est["posiciones"]["OKLO"].shares == 200 and est["caja"] == pytest.approx(90_000)


def test_nombre_que_sale_del_libro_se_vende_entero(sesion):
    core.registrar_fill(sesion, ticker="OKLO", lado="buy", shares=200, precio=50, fecha_fill=F)
    r = ejecutar(sesion, _res({}), precios={"OKLO": 50.0}, fecha_fill=F)   # OKLO ya no está en el objetivo
    assert r.fills == [{"ticker": "OKLO", "lado": "sell", "shares": 200, "precio": 50.0}]
    assert core.proyectar(sesion, {"OKLO": 50.0})["posiciones"] == {}


def test_ventas_antes_de_compras_y_tope_de_caja(sesion):
    core.registrar_fill(sesion, ticker="A", lado="buy", shares=1000, precio=10, fecha_fill=F)
    r = ejecutar(sesion, _res({"B": 0.9}), precios={"A": 10.0, "B": 100.0}, fecha_fill=F)
    assert [f["lado"] for f in r.fills] == ["sell", "buy"]      # venta primero
    assert r.fills[0]["ticker"] == "A" and r.fills[1] == {"ticker": "B", "lado": "buy", "shares": 900, "precio": 100.0}
    est = core.proyectar(sesion, {"B": 100.0})
    assert est["posiciones"]["B"].shares == 900 and "A" not in est["posiciones"]


def test_aumento_demorado_no_se_ejecuta(sesion):
    core.registrar_fill(sesion, ticker="OKLO", lado="buy", shares=100, precio=50, fecha_fill=F)
    r = ejecutar(sesion, _res({"OKLO": 0.2}, demoradas=["OKLO"]), precios={"OKLO": 50.0}, fecha_fill=F)
    assert r.fills == [] and r.demoradas == ["OKLO"]
    assert core.proyectar(sesion, {"OKLO": 50.0})["posiciones"]["OKLO"].shares == 100   # sin cambios


def test_no_action_no_opera(sesion):
    r = ejecutar(sesion, _res({"OKLO": 0.1}, no_action=True), precios={"OKLO": 50.0}, fecha_fill=F)
    assert r.fills == [] and r.nota and "NO_ACTION" in r.nota


def test_nombre_sin_precio_no_se_opera(sesion):
    r = ejecutar(sesion, _res({"XYZ": 0.1}), precios={}, fecha_fill=F)
    assert r.fills == [] and r.sin_precio == ["XYZ"]


def test_equity_cero_sin_deposito():
    engine = create_engine("sqlite:///:memory:", future=True)
    crear_tablas(engine)
    with Session(engine, future=True) as s:
        r = ejecutar(s, _res({"OKLO": 0.1}), precios={"OKLO": 50.0}, fecha_fill=F)
        assert r.fills == [] and r.nota and "equity" in r.nota
