"""Tests del adapter de datos (ticker real → hechos). Mockea los servicios: NO hace
llamadas de red. Verifica el mapeo de campos y la conversión de unidades.
"""
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.ingreso import adapter
from backend.ingreso.filtro0 import HechosFiltro0  # noqa: F401 (doc)
from backend.ledger import entidades as e
from backend.ledger.entidades import Estado
from backend.ledger.models import crear_tablas
from backend.services.edgar import FinancialsQuarterly
from backend.services.market_data import PriceSnapshot


def _snap(precio=50.0, adv=5e6):
    return PriceSnapshot(ticker="ACME", precio_actual=precio,
                         volumen_diario_promedio_30d=adv, market_cap=None)


def _fin(**kw):
    base = dict(ticker="ACME", cik="0000123", revenue_ttm=500e6, organic_growth_yoy=25.0,
                margen_bruto_ultimo=45.0, total_debt=100e6, shares_outstanding=20e6,
                cash=None, burn_rate_monthly=None)
    base.update(kw)
    return FinancialsQuarterly(**base)


@pytest.fixture
def mock_datos(monkeypatch):
    def _set(snap, fin):
        monkeypatch.setattr(adapter.market_data, "get_price_snapshot", lambda t: snap)
        monkeypatch.setattr(adapter.edgar, "get_financials_quarterly", lambda t, periodos=8: fin)
    return _set


def test_convierte_porcentaje_a_fraccion(mock_datos):
    mock_datos(_snap(), _fin(organic_growth_yoy=25.0, margen_bruto_ultimo=45.0))
    h = adapter.construir_hechos("ACME", tiene_nodo=True)
    assert h.filtro0.crecimiento_yoy == pytest.approx(0.25)
    assert h.filtro0.margen_bruto == pytest.approx(0.45)


def test_market_cap_y_jurisdiccion(mock_datos):
    mock_datos(_snap(precio=50.0), _fin(shares_outstanding=20e6))
    h = adapter.construir_hechos("ACME", tiene_nodo=True)
    assert h.universo.market_cap == pytest.approx(50.0 * 20e6)  # $1B
    assert h.universo.jurisdiccion == "US"
    assert h.universo.adv_usd == pytest.approx(5e6)


def test_sin_cik_jurisdiccion_none(mock_datos):
    mock_datos(_snap(), _fin(cik=None))
    h = adapter.construir_hechos("ACME", tiene_nodo=True)
    assert h.universo.jurisdiccion is None


def test_prerevenue_por_umbral(mock_datos):
    mock_datos(_snap(), _fin(revenue_ttm=5e6))     # < $10M
    assert adapter.construir_hechos("ACME", tiene_nodo=True).filtro0.es_prerevenue is True
    mock_datos(_snap(), _fin(revenue_ttm=50e6))    # >= $10M
    assert adapter.construir_hechos("ACME", tiene_nodo=True).filtro0.es_prerevenue is False


def test_campos_cualitativos_los_pasa_el_caller(mock_datos):
    mock_datos(_snap(), _fin())
    h = adapter.construir_hechos("ACME", tiene_nodo=True,
                                 tiene_contrato_vinculante_material=True, es_adr=True)
    assert h.filtro0.tiene_contrato_vinculante_material is True
    assert h.universo.es_adr is True


def test_sin_precio_devuelve_none(mock_datos):
    mock_datos(None, _fin())
    assert adapter.construir_hechos("ACME", tiene_nodo=True) is None


def test_ingresar_ticker_end_to_end(mock_datos):
    # ACME: US, $1B cap, ADV $5M, crecimiento 25%, margen 45% → investigar → En-deep-research
    mock_datos(_snap(), _fin())
    engine = create_engine("sqlite:///:memory:", future=True)
    crear_tablas(engine)
    with Session(engine, future=True) as s:
        nodo = e.crear_nodo(s, nombre="HBM", cluster="datacenter")
        r = adapter.ingresar_ticker(s, ticker="ACME", nodo_id=nodo.id, fecha=date(2026, 1, 1))
        assert r["resultado"] == "investigar"
        assert e.estado_desde_log(s, "ACME") == Estado.EN_DEEP_RESEARCH.value


def test_ingresar_ticker_sin_datos(mock_datos):
    mock_datos(None, _fin())
    engine = create_engine("sqlite:///:memory:", future=True)
    crear_tablas(engine)
    with Session(engine, future=True) as s:
        r = adapter.ingresar_ticker(s, ticker="ZZZZ", nodo_id=1, fecha=date(2026, 1, 1))
        assert r["resultado"] == "sin_datos"
