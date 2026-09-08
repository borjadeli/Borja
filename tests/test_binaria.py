"""Gramática binaria skeleton (doc 42 §1, D1): piso V_fracaso (solo XBRL) + quinto estado floor-only."""
from backend.nucleo import binaria as B


def test_v_fracaso_solo_xbrl():
    # cash 500 + ST 100 − debt 200 − burn 10/mes×(12×1.5) − windown 20×2
    v = B.v_fracaso(cash=500, short_term_inv=100, debt=200, burn_mensual=10, meses_al_hito=12, opex_trimestral=20)
    # 600 − 200 − 10×18 − 40 = 600−200−180−40 = 180
    assert abs(v - 180) < 1e-6


def test_v_fracaso_floored_en_cero():
    # deuda + burn > caja → piso 0 (legítimo, frecuente con converts)
    v = B.v_fracaso(cash=100, short_term_inv=0, debt=200, burn_mensual=50, meses_al_hito=12, opex_trimestral=0)
    assert v == 0.0


def test_v_fracaso_sin_burn():
    v = B.v_fracaso(cash=500, short_term_inv=0, debt=0, burn_mensual=None, meses_al_hito=None, opex_trimestral=0)
    assert v == 500.0


def test_quinto_estado_precio_bajo_piso_es_covered():
    # precio ≤ piso → margen de seguridad → COVERED
    r = B.estado_binario(P_ops=100, v_fracaso_abs=120)
    assert r["estado"] == "COVERED" and r["ratio_piso"] == 1.2


def test_quinto_estado_cerca_del_piso_es_stretch():
    # ratio entre 1/k (~0.71) y 1 → STRETCH
    r = B.estado_binario(P_ops=100, v_fracaso_abs=80)   # ratio 0.8 ≥ 1/1.4=0.71
    assert r["estado"] == "STRETCH"


def test_quinto_estado_precio_alto_es_non_underwritable():
    # precio muy por encima del piso, sin base-rate → NON_UNDERWRITABLE (carril/probe)
    r = B.estado_binario(P_ops=1000, v_fracaso_abs=100)   # ratio 0.1
    assert r["estado"] == "NON_UNDERWRITABLE"


def test_sin_datos_es_non_underwritable():
    assert B.estado_binario(P_ops=None, v_fracaso_abs=100)["estado"] == "NON_UNDERWRITABLE"
    assert B.estado_binario(P_ops=100, v_fracaso_abs=None)["estado"] == "NON_UNDERWRITABLE"
