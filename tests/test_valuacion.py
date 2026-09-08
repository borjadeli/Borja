"""Tests del motor de valuación (Etapa 4b.1). Determinista, sin datos externos."""
import math

import pytest

from backend.nucleo.valuacion import HechosValuacion, merito_ranking, valuar


def _h(**kw):
    base = dict(
        arquetipo="Growth", metrica="EV/Sales", pares_multiplos=[3, 4, 5, 6, 7],
        fund_bear=80.0, fund_base=100.0, fund_bull=150.0, deuda_neta=50.0,
        acciones_diluidas=100.0, dilucion_cagr=0.05, horizon_years=3.0,
        convencion_fundamento="NTM", convencion_multiplo="NTM",
    )
    base.update(kw)
    return HechosValuacion(**base)


def test_ordering_y_multiplos():
    r = valuar(_h())
    assert r.multiplo_base == pytest.approx(5.0)   # P50 de [3..7]
    assert r.multiplo_bear == pytest.approx(4.0)   # P25
    assert r.bull > r.base > r.bear > 0


def test_bull_no_expande_multiplo():
    # EV bull = fund_bull × múltiplo BASE (no P75) → upside solo del fundamento.
    r = valuar(_h())
    assert r.detalle["ev_bull"] == pytest.approx(150.0 * 5.0)


def test_convencion_no_matchea_levanta():
    with pytest.raises(ValueError, match="convención"):
        valuar(_h(convencion_multiplo="LTM"))


def test_pocos_pares_flag():
    r = valuar(_h(pares_multiplos=[5, 6]))
    assert any("baja confianza" in f for f in r.flags)


def test_dispersion_alta_flag():
    r = valuar(_h(pares_multiplos=[1, 2, 20]))
    assert any("dispersión" in f for f in r.flags)


def test_techo_p90_capa_el_multiplo():
    r = valuar(_h(techo_multiplo_propio=4.0))   # P50=5 pero su propio techo es 4
    assert r.multiplo_base == pytest.approx(4.0)


def test_implausibilidad_flag():
    r = valuar(_h(tam=100.0))   # EV bull = 750 > TAM 100
    assert any("implausible" in f for f in r.flags)


def test_descuento_reduce_precio():
    corto = valuar(_h(horizon_years=1.0)).bull
    largo = valuar(_h(horizon_years=5.0)).bull
    assert largo < corto   # más lejos → más descontado


def test_dilucion_reduce_precio():
    sin = valuar(_h(dilucion_cagr=0.0)).bull
    con = valuar(_h(dilucion_cagr=0.10)).bull
    assert con < sin


def test_puente_exacto():
    # arquetipo Madura (tasa 0.10), sin dilución, horizonte 1 → chequeo del puente.
    r = valuar(_h(arquetipo="Madura", dilucion_cagr=0.0, horizon_years=1.0))
    # ev_bull=750, equity=700, /100 acciones = 7.0, /1.10 = 6.3636
    assert r.bull == pytest.approx(700 / 100 / 1.10)


def test_merito_ranking_concavo():
    # √20 / √5 = 2, no 4 (lineal) → preserva cola sin premiar linealmente.
    assert merito_ranking(1, 20) / merito_ranking(1, 5) == pytest.approx(2.0)
    assert merito_ranking(2, 4) == pytest.approx(2 * math.sqrt(4))
    assert merito_ranking(3, 0) is None
    assert merito_ranking(3, None) is None
