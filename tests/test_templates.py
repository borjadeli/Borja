"""Templates de valuación operable (doc 28 §2/§3) — FCF TTM."""
from backend.nucleo import templates as T


def test_genera_caja_produce_bull_finito():
    esc = T.escenario_operable(400e6, fcf_ttm=40e6, arquetipo="Madura",
                               shares=100e6, caja=50e6, deuda=0.0, precio=5.0)
    assert esc.con_terminal is True
    # EV = 400M×10%/0.12 ≈ 333M; +caja 50M; /100M ≈ $3.83 — finito, no explota.
    assert esc.bull_price is not None and 0 < esc.bull_price < 10
    assert esc.multiplo_sobre_operable is not None and esc.multiplo_sobre_operable > 0


def test_no_genera_caja_cae_al_piso():
    # FCF TTM negativo → sin terminal → operable = (caja − deuda)/shares.
    esc = T.escenario_operable(400e6, fcf_ttm=-20e6, arquetipo="Growth",
                               shares=100e6, caja=120e6, deuda=20e6)
    assert esc.con_terminal is False
    piso = (120e6 - 20e6) / 100e6                       # = $1.00
    assert esc.bull_price == piso == esc.bear_price
    assert "opcionalidad" in esc.nota


def test_margen_bajo_no_explota():
    # El caso COHR: margen FCF chico pero positivo → número finito (no $659B).
    esc = T.escenario_operable(6571e6, fcf_ttm=6571e6 * 0.012, arquetipo="Growth",
                               shares=155e6, caja=0.0, deuda=0.0)
    assert esc.bull_price is not None and esc.bull_price < 50


def test_contratado_sube_el_bull():
    sin = T.escenario_operable(400e6, fcf_ttm=40e6, arquetipo="Madura", shares=100e6, caja=0.0, deuda=0.0)
    con = T.escenario_operable(400e6, fcf_ttm=40e6, arquetipo="Madura", shares=100e6, caja=0.0, deuda=0.0,
                               revenue_contratado=100e6)
    assert con.bull_price > sin.bull_price


def test_multiplo_sobre_operable():
    esc = T.escenario_operable(400e6, fcf_ttm=40e6, arquetipo="Madura",
                               shares=100e6, caja=0.0, deuda=0.0, precio=10.0)
    assert abs(esc.multiplo_sobre_operable - 10.0 / esc.base_price) < 1e-6


def test_no_doble_conteo_de_deuda_en_terminal():
    # Con terminal (genera caja), la deuda NO se resta (ya está en el FCF levered vía intereses).
    con = T.escenario_operable(400e6, fcf_ttm=40e6, arquetipo="Madura", shares=100e6, caja=50e6, deuda=200e6)
    sin = T.escenario_operable(400e6, fcf_ttm=40e6, arquetipo="Madura", shares=100e6, caja=50e6, deuda=0.0)
    assert con.base_price == sin.base_price


def test_piso_si_resta_deuda():
    # En el piso (no genera caja) la deuda SÍ se resta (net liquid value).
    esc = T.escenario_operable(400e6, fcf_ttm=-10e6, arquetipo="Growth", shares=100e6, caja=200e6, deuda=100e6)
    assert esc.bear_price == (200e6 - 100e6) / 100e6


def test_asimetria_operable():
    assert T.asimetria_operable(bull=15.0, precio=10.0, bear=5.0) == 1.0
    assert T.asimetria_operable(bull=15.0, precio=5.0, bear=5.0) is None   # denom 0
