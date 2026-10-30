"""Tests de las calculadoras de futuro deterministas (v2 doc 70 D4). Puras, sin red."""
from backend.agentes.futuro import (
    base_rate_cagr,
    dilucion_por_gap,
    funded_hasta_hito,
    meses_runway,
)


def test_runway_base_y_estres():
    r = meses_runway(1_200e6, -120e6)          # caja 1.2B / quema 10M/mes = 120 meses
    assert r.estado == "COMPUTED" and abs(r.valor - 120) < 0.5
    r2 = meses_runway(1_200e6, -120e6, estres=1.5)   # quema 15M/mes → 80 meses
    assert abs(r2.valor - 80) < 0.5


def test_runway_unknown_sin_insumos_o_sin_quema():
    assert meses_runway(None, -1).estado == "UNKNOWN"
    assert meses_runway(1e9, 50e6).estado == "UNKNOWN"   # flujo positivo: no quema


def test_funded_hasta_hito_cubre_y_gap():
    cubre = funded_hasta_hito(1_000e6, -100e6, meses_al_hito=12)   # runway ~92m (estrés 1.3) >> 12+6
    assert cubre.estado == "COMPUTED" and cubre.valor > 0 and "cubre" in cubre.detalle
    gap = funded_hasta_hito(100e6, -100e6, meses_al_hito=18)       # runway ~9m < 18+6 → gap
    assert gap.valor < 0 and "GAP" in gap.detalle


def test_funded_unknown_sin_hito():
    assert funded_hasta_hito(1e9, -1e8, meses_al_hito=None).estado == "UNKNOWN"


def test_dilucion_por_gap():
    # gap 200M, precio 50, shares 100M → 4M acciones nuevas = 4%
    r = dilucion_por_gap(200e6, 50.0, 100e6)
    assert r.estado == "COMPUTED" and abs(r.valor - 4.0) < 0.1
    # con descuento 20% → emite más barato → más dilución
    r2 = dilucion_por_gap(200e6, 50.0, 100e6, descuento=0.2)
    assert r2.valor > r.valor
    assert dilucion_por_gap(0, 50, 100e6).valor == 0.0           # sin gap
    assert dilucion_por_gap(200e6, None, 100e6).estado == "UNKNOWN"


def test_base_rate_cagr_anti_especulacion():
    # el caso del doc: 60% CAGR por 7 años → fracción muy baja
    r = base_rate_cagr(0.60, 7)
    assert r.estado == "COMPUTED" and r.valor < 1.0             # <1%
    # un crecimiento modesto es mucho más común
    r2 = base_rate_cagr(0.20, 3)
    assert r2.valor > r.valor and r2.valor > 10
    # CAGR por encima de la tabla → extrapola al más alto
    r3 = base_rate_cagr(0.90, 7)
    assert r3.estado == "COMPUTED" and "extrapolado" in r3.detalle


def test_base_rate_unknown():
    assert base_rate_cagr(None, 5).estado == "UNKNOWN"
