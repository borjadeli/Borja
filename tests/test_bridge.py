"""Bridge mínimo + CAGR implícito falsador (doc 28 §2/§4)."""
from backend.nucleo import bridge


def test_forward_inverso_roundtrip():
    # precio_desde_revenue e revenue_implicito son inversos exactos.
    p = bridge.precio_desde_revenue(750e6, margen=0.20, r=0.15, shares=100e6, caja_neta=0.0)
    assert p is not None
    rev = bridge.revenue_implicito(p, margen=0.20, r=0.15, shares=100e6, caja_neta=0.0)
    assert abs(rev - 750e6) < 1.0


def test_falsador_detecta_bull_ya_priceado():
    # precio $10 × 100M = $1B equity; margen 20%, Growth (r=15%) → revenue implícito $750M.
    # bull operable $500M < $750M → el mercado ya paga el bull entero.
    f = bridge.falsador_cagr(precio=10.0, revenue_bull_operable=500e6, margen=0.20,
                             arquetipo="Growth", shares=100e6)
    assert abs(f.revenue_implicito - 750e6) < 1.0
    assert f.ya_priceado is True
    assert "option ledger" in f.veredicto


def test_falsador_deja_aire():
    # mismo precio, pero bull operable $1000M > $750M implícito → hay aire.
    f = bridge.falsador_cagr(precio=10.0, revenue_bull_operable=1000e6, margen=0.20,
                             arquetipo="Growth", shares=100e6)
    assert f.ya_priceado is False
    assert f.ratio == round(750e6 / 1000e6, 3)


def test_guarda_margen_bajo_no_emite_numero():
    # COHR real: 1.2% de FCF margin hacía explotar el revenue implícito a $659B. La guarda lo frena.
    f = bridge.falsador_cagr(precio=266.0, revenue_bull_operable=6571e6, margen=0.012,
                             arquetipo="Growth", shares=155e6)
    assert f.revenue_implicito is None
    assert "no_evaluable" in f.veredicto and "margen" in f.veredicto


def test_guarda_ratio_absurdo_no_emite_numero():
    # Margen ok (>5%) pero el implícito sale absurdamente alto vs el operable → backstop.
    f = bridge.falsador_cagr(precio=1000.0, revenue_bull_operable=1e6, margen=0.10,
                             arquetipo="Growth", shares=100e6)
    assert f.revenue_implicito is None
    assert "implausible" in f.veredicto


def test_falsador_no_evaluable_sin_datos():
    f = bridge.falsador_cagr(precio=10.0, revenue_bull_operable=None, margen=0.20,
                             arquetipo="Growth", shares=100e6)
    assert f.veredicto == "no_evaluable"


def test_bridge_devuelve_none_con_inputs_malos():
    assert bridge.precio_desde_revenue(100e6, margen=None, r=0.15, shares=100e6) is None
    assert bridge.revenue_implicito(10.0, margen=0.0, r=0.15, shares=100e6) is None
