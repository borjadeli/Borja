"""Dilución forward = burn_yield + runway (doc 31 §5, v2). mcap del feed."""
from types import SimpleNamespace
from backend.nucleo.dilucion import dilucion_forward


def _fin(fcf_ttm=None, cash=None):
    return SimpleNamespace(fcf_ttm=fcf_ttm, cash=cash)


def test_burn_yield_quema():
    d = dilucion_forward(_fin(fcf_ttm=-100e6), mcap=1000e6)   # 10%/año → material
    assert abs(d.burn_yield - 0.10) < 1e-9 and d.banda == "material"


def test_burn_yield_severo():
    assert dilucion_forward(_fin(fcf_ttm=-400e6), mcap=1000e6).banda == "severo"  # 40%


def test_fcf_positivo_sin_burn():
    d = dilucion_forward(_fin(fcf_ttm=50e6), mcap=1000e6)
    assert d.burn_yield == 0.0 and d.banda == "bajo"


def test_runway_critico():
    d = dilucion_forward(_fin(fcf_ttm=-100e6, cash=50e6), mcap=1000e6)  # 50/100 = 0.5a < 1
    assert d.runway_anos == 0.5 and d.runway_critico is True


def test_runway_holgado():
    d = dilucion_forward(_fin(fcf_ttm=-100e6, cash=300e6), mcap=1000e6)  # 3a
    assert d.runway_anos == 3.0 and d.runway_critico is False


def test_datos_insuficientes():
    assert dilucion_forward(_fin(fcf_ttm=None), mcap=1000e6).burn_yield is None
    assert dilucion_forward(_fin(fcf_ttm=-100e6), mcap=None).burn_yield is None
