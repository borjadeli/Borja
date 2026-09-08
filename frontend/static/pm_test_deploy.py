"""Tests del deploy al ledger (Etapa 6). SQLite in-memory."""
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.ledger import core
from backend.ledger.models import crear_tablas
from backend.seleccion.deploy import desplegar

CAPITAL = 100_000.0


@pytest.fixture
def sesion():
    engine = create_engine("sqlite:///:memory:", future=True)
    crear_tablas(engine)
    with Session(engine, future=True) as s:
        core.depositar(s, CAPITAL, date(2026, 1, 1))
        yield s


def test_deploy_desde_cash_compra(sesion):
    r = desplegar(sesion, mix={"ACME": 0.5}, precios={"ACME": 50}, fecha=date(2026, 1, 2),
                  slippage_bps=0.0, comision_por_accion=0.0, comision_min=0.0)
    assert len(r["compras"]) == 1 and r["compras"][0]["shares"] == 1000
    assert r["invertido"] == pytest.approx(50_000)
    assert r["cash"] == pytest.approx(50_000)


def test_reconciliacion_tras_deploy(sesion):
    desplegar(sesion, mix={"ACME": 0.4, "BETA": 0.3}, precios={"ACME": 50, "BETA": 20},
              fecha=date(2026, 1, 2))
    rec = core.reconciliar(sesion, {"ACME": 50, "BETA": 20})
    assert rec["ok"], rec["violaciones"]


def test_deploy_vende_lo_que_sale_del_mix(sesion):
    desplegar(sesion, mix={"ACME": 0.5}, precios={"ACME": 50}, fecha=date(2026, 1, 2),
              slippage_bps=0.0, comision_por_accion=0.0, comision_min=0.0)
    # Nuevo mix sin ACME → se vende a cero.
    r = desplegar(sesion, mix={"BETA": 0.3}, precios={"ACME": 50, "BETA": 20},
                  fecha=date(2026, 1, 3), slippage_bps=0.0, comision_por_accion=0.0, comision_min=0.0)
    est = core.proyectar(sesion, {"ACME": 50, "BETA": 20})
    assert "ACME" not in est["posiciones"]
    assert "BETA" in est["posiciones"]
    assert any(v["ticker"] == "ACME" for v in r["ventas"])


def test_cap_adv_limita_la_orden(sesion):
    # ADV $100k, participación 15% → máx $15k/día = 300 acciones @50 (vs 1000 objetivo).
    r = desplegar(sesion, mix={"ACME": 0.5}, precios={"ACME": 50}, fecha=date(2026, 1, 2),
                  adv_usd={"ACME": 100_000}, slippage_bps=0.0, comision_por_accion=0.0, comision_min=0.0)
    assert r["compras"][0]["shares"] == 300


def test_no_deja_caja_negativa(sesion):
    # Pide 100% en ACME con costos → el guard evita caja negativa.
    r = desplegar(sesion, mix={"ACME": 1.0}, precios={"ACME": 50}, fecha=date(2026, 1, 2),
                  slippage_bps=50.0, comision_por_accion=0.01, comision_min=1.0)
    assert r["cash"] >= 0


def test_ventas_antes_que_compras(sesion):
    # Cartera con ACME; nuevo mix cambia a BETA → debe vender ACME (libera cash) y comprar BETA.
    desplegar(sesion, mix={"ACME": 0.9}, precios={"ACME": 50}, fecha=date(2026, 1, 2),
              slippage_bps=0.0, comision_por_accion=0.0, comision_min=0.0)
    r = desplegar(sesion, mix={"BETA": 0.9}, precios={"ACME": 50, "BETA": 20},
                  fecha=date(2026, 1, 3), slippage_bps=0.0, comision_por_accion=0.0, comision_min=0.0)
    assert r["ventas"] and r["compras"]
    assert r["cash"] >= 0
