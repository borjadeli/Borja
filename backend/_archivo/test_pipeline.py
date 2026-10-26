"""Test de integración end-to-end (Etapas 3→6). Hechos inyectados, sin API/red."""
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend import pipeline
from backend.ingreso.filtro0 import HechosFiltro0
from backend.ingreso.universo import HechosUniverso
from backend.ledger import core
from backend.ledger import entidades as e
from backend.ledger.entidades import Estado
from backend.ledger.models import crear_tablas
from backend.pipeline import Solicitud


def _entrada_madura(ticker):
    from backend.nucleo.arquetipo import HechosArquetipo
    from backend.nucleo.flujo import EntradaEmpresa
    from backend.nucleo.fragility import HechosFragility
    from backend.nucleo.gate import HechosGate, Trigger
    from backend.nucleo.quality import HechosQuality
    return EntradaEmpresa(
        ticker=ticker,
        hechos_arquetipo=HechosArquetipo(revenue_elegible=100e6,
                                         crecimiento_elegible_yoy=0.10, fcf_ttm=5e6),
        hechos_gate=HechosGate(arquetipo="", madura_hecho_vigente=True, triggers=[
            Trigger(hecho="deuda", umbral=">2x", fecha="2026-01-01", fuente="A",
                    es_estructura_capital=True),
            Trigger(hecho="cliente", umbral="<10%", fecha="2026-01-01", fuente="A",
                    atado_a_hecho_de_entrada=True),
        ]),
        hechos_quality=HechosQuality(margen_bruto=0.55, revenue_recurrente=True),
        hechos_fragility=HechosFragility(financiacion_completa_cerrada=True,
                                         redundancia_comercial_real=True),
        precio=50.0, bull=90.0, bear=30.0,   # asimetría = (90-50)/(50-30) = 2.0
    )


def _universo_ok(**kw):
    base = dict(jurisdiccion="US", market_cap=500e6, adv_usd=5e6, tiene_nodo=True)
    base.update(kw)
    return HechosUniverso(**base)


@pytest.fixture
def sesion():
    engine = create_engine("sqlite:///:memory:", future=True)
    crear_tablas(engine)
    with Session(engine, future=True) as s:
        core.depositar(s, 100_000.0, date(2026, 1, 1))
        yield s


def test_pipeline_end_to_end(sesion):
    nodo = e.crear_nodo(sesion, nombre="Ciber", cluster="ciber")
    sol = Solicitud(ticker="ACME", universo=_universo_ok(),
                    filtro0=HechosFiltro0(crecimiento_yoy=0.30, margen_bruto=0.45),
                    nodo_id=nodo.id, entrada_deep=_entrada_madura("ACME"),
                    sector="ciber", factores=["fx"])
    r = pipeline.correr_ciclo(sesion, [sol], precios={"ACME": 50}, cash_objetivo=0.5,
                              fecha=date(2026, 1, 2))
    # Recorrió TODO: Filtro 0 investigar → deep research Elegible → PM incluye → deploy compra.
    assert r["por_ticker"]["ACME"]["filtro0"]["resultado"] == "investigar"
    assert "ACME" in r["elegibles"]
    assert r["pm"]["ok"] and "ACME" in r["pm"]["mix"]
    assert r["deploy"]["compras"]
    assert not r["deploy"]["violaciones_post"]                  # cap duro tras costos
    assert e.estado_desde_log(sesion, "ACME") == Estado.POSICION.value
    assert "ACME" in core.proyectar(sesion, {"ACME": 50})["posiciones"]


def test_pipeline_descartada_no_llega_al_pm(sesion):
    nodo = e.crear_nodo(sesion, nombre="Ciber", cluster="ciber")
    sol = Solicitud(ticker="BAD", universo=_universo_ok(),
                    filtro0=HechosFiltro0(crecimiento_yoy=0.02, margen_bruto=0.05),  # feo/feo
                    nodo_id=nodo.id, sector="ciber")
    r = pipeline.correr_ciclo(sesion, [sol], precios={"BAD": 50}, cash_objetivo=0.5,
                              fecha=date(2026, 1, 2))
    assert r["por_ticker"]["BAD"]["filtro0"]["resultado"] == "descartar"
    assert "BAD" not in r["elegibles"]
    assert e.estado_desde_log(sesion, "BAD") == Estado.DESCARTADA.value


def test_pipeline_elegible_no_elegida_va_a_watchlist(sesion):
    # Dos elegibles del mismo sector+factor; con poco presupuesto entra una, la otra → Watchlist.
    nodo = e.crear_nodo(sesion, nombre="Ciber", cluster="ciber")
    sols = []
    for tk in ("AAA", "BBB"):
        sols.append(Solicitud(ticker=tk, universo=_universo_ok(),
                              filtro0=HechosFiltro0(crecimiento_yoy=0.30, margen_bruto=0.45),
                              nodo_id=nodo.id, entrada_deep=_entrada_madura(tk),
                              sector="ciber", factores=["fx"]))
    # cash_objetivo alto → budget chico (0.10): entra una sola (factor cap + budget).
    r = pipeline.correr_ciclo(sesion, sols, precios={"AAA": 50, "BBB": 50},
                              cash_objetivo=0.90, fecha=date(2026, 1, 2))
    estados = {tk: e.estado_desde_log(sesion, tk) for tk in ("AAA", "BBB")}
    assert Estado.POSICION.value in estados.values()
    assert Estado.WATCHLIST.value in estados.values()
