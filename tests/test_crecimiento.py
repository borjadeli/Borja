"""Crecimiento demostrado g_D (doc 36 §3/§4): min(rev,GP) per-share + castigos unidireccionales + fade."""
from backend.services.edgar import SerieCrecimiento
from backend.nucleo import crecimiento as C


def _serie(g_rev, g_gp=None, n=16, rev0=100e6, shares0=1e6, gp_frac=0.70, shares_growth=0.0):
    """Serie trimestral sintética que crece al CAGR anual g (compuesto por trimestre)."""
    g_gp = g_rev if g_gp is None else g_gp
    s = SerieCrecimiento(ticker="X")
    for i in range(n):
        yr = i / 4.0
        s.fechas.append(f"2022Q{i}")
        s.revenue.append(rev0 * (1 + g_rev) ** yr)
        s.gross_profit.append(rev0 * gp_frac * (1 + g_gp) ** yr)
        s.diluted_shares.append(shares0 * (1 + shares_growth) ** yr)
    return s


def test_grower_limpio_30pct():
    r = C.crecimiento_demostrado(_serie(0.30), "Growth")
    assert abs(r["g_D"] - 0.30) < 0.02 and r["es_per_share"] is True


def test_min_rev_gp_gp_manda():
    # revenue crece 30% pero gross profit solo 20% (margen comprado) → g_D lo fija el GP
    r = C.crecimiento_demostrado(_serie(0.30, g_gp=0.20), "Growth")
    assert abs(r["g_D"] - 0.20) < 0.02


def test_cap_por_arquetipo_madura():
    # una madura no recibe crédito por >15% aunque haya crecido 30%
    r = C.crecimiento_demostrado(_serie(0.30), "Madura")
    assert r["g_D"] == 0.15


def test_cap_base_chica():
    # revenue TTM < 50M (rev0=2M/trim → TTM ~27M) → cap 0.30 aunque crezca 40%
    r = C.crecimiento_demostrado(_serie(0.40, rev0=2e6), "Growth")
    assert r["g_D"] == 0.30


def test_margen_comprado_castiga():
    base = C.crecimiento_demostrado(_serie(0.30), "Growth")["g_D"]
    cast = C.crecimiento_demostrado(_serie(0.30), "Growth", delta_gm_3y=-0.05)["g_D"]
    assert cast < base and abs(cast - base * 0.75) < 0.01


def test_inorganico_castiga():
    base = C.crecimiento_demostrado(_serie(0.30), "Growth")["g_D"]
    cast = C.crecimiento_demostrado(_serie(0.30), "Growth", ma_intensity=0.5)["g_D"]
    assert abs(cast - base * 0.50) < 0.01


def test_per_share_descuenta_emision():
    # mismo revenue agregado, pero emitiendo 15%/año → el crecimiento per-share es menor
    con_emision = C.crecimiento_demostrado(_serie(0.30, shares_growth=0.15), "Growth")["g_D"]
    sin_emision = C.crecimiento_demostrado(_serie(0.30, shares_growth=0.0), "Growth")["g_D"]
    assert con_emision < sin_emision


def test_serie_insuficiente_devuelve_none():
    s = SerieCrecimiento(ticker="X", revenue=[1, 2, 3], gross_profit=[1, 1, 1], diluted_shares=[1, 1, 1])
    assert C.crecimiento_demostrado(s, "Growth")["g_D"] is None


def test_fade_hacia_g_terminal():
    assert abs(C.fade(0.30, 1) - 0.30) < 1e-9           # año 1 = sin fade (base)
    assert C.fade(0.30, 4) < 0.30 and C.fade(0.30, 4) > 0.03   # decae hacia g_∞
    assert C.fade(0.30, 1, estres=True) < 0.30          # estrés: shock inicial


def test_concentracion_castiga_crecimiento_fragil():
    # crecimiento concentrado (>30% en un cliente) → frágil, no durable → g_D descontado (validación 2026-08)
    base = C.crecimiento_demostrado(_serie(0.30), "Growth")["g_D"]
    cast = C.crecimiento_demostrado(_serie(0.30), "Growth", concentracion=0.63)["g_D"]
    assert cast < base and abs(cast - base * 0.70) < 0.01


def test_concentracion_baja_no_castiga():
    base = C.crecimiento_demostrado(_serie(0.30), "Growth")["g_D"]
    igual = C.crecimiento_demostrado(_serie(0.30), "Growth", concentracion=0.15)["g_D"]
    assert igual == base
