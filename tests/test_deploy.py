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


# --- Fixes de la revisión externa (AI 1 + AI 2) ---

def test_precio_faltante_hace_raise(sesion):
    core.registrar_fill(sesion, ticker="OLD", lado="buy", shares=100, precio=50, fecha_fill=date(2026, 1, 2))
    with pytest.raises(ValueError, match="precios faltantes"):
        desplegar(sesion, mix={}, precios={}, fecha=date(2026, 1, 3))


def test_venta_producido_negativo_es_pendiente(sesion):
    core.registrar_fill(sesion, ticker="ACME", lado="buy", shares=1, precio=0.5, fecha_fill=date(2026, 1, 2))
    r = desplegar(sesion, mix={}, precios={"ACME": 0.5}, fecha=date(2026, 1, 3), comision_min=1.0)
    assert not r["completo"]
    assert r["cash"] >= 0
    assert "ACME" in core.proyectar(sesion, {"ACME": 0.5})["posiciones"]   # no se vendió


def test_venta_truncada_por_adv_bloquea_compras(sesion):
    core.registrar_fill(sesion, ticker="OLD", lado="buy", shares=1000, precio=50, fecha_fill=date(2026, 1, 2))
    r = desplegar(sesion, mix={"NEW": 0.5}, precios={"OLD": 50, "NEW": 20}, fecha=date(2026, 1, 3),
                  adv_usd={"OLD": 10_000, "NEW": 10_000_000},
                  slippage_bps=0.0, comision_por_accion=0.0, comision_min=0.0)
    assert not r["completo"]
    assert not r["compras"]


def test_adv_acumulado_mismo_dia(sesion):
    kw = dict(adv_usd={"ACME": 100_000}, slippage_bps=0.0, comision_por_accion=0.0, comision_min=0.0)
    r1 = desplegar(sesion, mix={"ACME": 0.5}, precios={"ACME": 50}, fecha=date(2026, 1, 2), **kw)
    assert r1["compras"][0]["shares"] == 300           # 15% de $100k / $50
    r2 = desplegar(sesion, mix={"ACME": 0.9}, precios={"ACME": 50}, fecha=date(2026, 1, 2), **kw)
    assert not r2["compras"]                            # presupuesto de ADV ya agotado hoy


def test_floor_no_supera_objetivo():
    engine = create_engine("sqlite:///:memory:", future=True)
    crear_tablas(engine)
    with Session(engine, future=True) as s:
        core.depositar(s, 1000.0, date(2026, 1, 1))
        r = desplegar(s, mix={"ACME": 0.25}, precios={"ACME": 150}, fecha=date(2026, 1, 2),
                      slippage_bps=0.0, comision_por_accion=0.0, comision_min=0.0)
        assert r["compras"][0]["shares"] == 1          # floor(1.667)=1, NO 2 (que sería 30%>25%)


def test_validacion_post_trade_reporta_residual(sesion):
    from backend.seleccion.validador import Candidata
    core.registrar_fill(sesion, ticker="OLD", lado="buy", shares=1000, precio=50, fecha_fill=date(2026, 1, 2))
    cands = [Candidata("NEW", elegible=True, hard_cap=0.5, sector="s")]   # OLD no está
    r = desplegar(sesion, mix={"NEW": 0.4}, precios={"OLD": 50, "NEW": 20}, fecha=date(2026, 1, 3),
                  adv_usd={"OLD": 10_000, "NEW": 10_000_000}, slippage_bps=0.0,
                  comision_por_accion=0.0, comision_min=0.0, candidatas=cands, cash_objetivo=0.6)
    # La venta de OLD queda truncada por ADV → residual OLD que NO está en el mix aprobado.
    assert r["violaciones_post"]
    assert any("OLD" in v for v in r["violaciones_post"])
