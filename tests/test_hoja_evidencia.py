"""Hoja de evidencia + ranking (doc 31 §7 v2) — datos inyectados, sin red. Shares/mcap del feed."""
from types import SimpleNamespace
import backend.nucleo.hoja_evidencia as HE


def _snap(precio=30.0, shares=100e6, mcap=3000e6):
    return SimpleNamespace(precio_actual=precio, shares_outstanding=shares, market_cap=mcap)


def _stub(fin_map, snap=None):
    HE.edgar.get_financials_quarterly = lambda t, periodos=8: fin_map[t] if isinstance(fin_map, dict) else fin_map
    HE.market_data.get_price_snapshot = lambda t: snap if snap is not None else _snap()
    HE.extraer_deterministas = lambda t: {}
    HE._clasificar_arquetipo = lambda d: "Growth"


def _fin(**kw):
    base = dict(revenue_ttm=None, fcf_ttm=None, sbc_ttm=None, capex_ttm=100e6,
                shares_outstanding=100e6, cash=200e6, total_debt=0.0, quarters=[])
    base.update(kw)
    return SimpleNamespace(**base)


def test_shares_cero_manual_data_check():
    # sin shares en el feed y 0 en XBRL → MANUAL_DATA_CHECK.
    _stub(_fin(shares_outstanding=0.0, revenue_ttm=1000e6, fcf_ttm=100e6),
          snap=_snap(precio=50.0, shares=None, mcap=None))
    assert HE.hoja("TEM").estado == "MANUAL_DATA_CHECK"


def test_shares_del_feed_se_usan():
    q = [{"gross_profit": 200e6, "operating_income": 50e6, "ocf": 120e6} for _ in range(4)]
    # XBRL dice 999 (mal), el feed dice 100M → se usa el feed.
    _stub(_fin(revenue_ttm=1000e6, fcf_ttm=120e6, sbc_ttm=10e6, shares_outstanding=999.0, quarters=q),
          snap=_snap(precio=30.0, shares=100e6, mcap=3000e6))
    h = HE.hoja("X")
    assert h.estado == "RANKEABLE"           # no MANUAL pese al 999 de XBRL
    # FCFE_OPERABLE lo ancla el operable, NO el reverse underwriting (doc 31 §2 escapa a R1-R4):
    # anchor status ANCHORED pero sin reverse burden (burden_gp None, tipo NA).
    assert h.route == "FCFE_OPERABLE"
    assert h.price_anchor_status == "ANCHORED"
    assert h.reverse_burden_type == "NA" and h.burden_gp is None


def test_pre_revenue_non_fcfe_recibe_reverse_burden():
    # GP>0 pero owner-FCF<0 (route NON_FCFE) → NO lo ancla el operable → reverse underwriting.
    q = [{"gross_profit": 200e6, "operating_income": -30e6, "ocf": 60e6} for _ in range(4)]
    _stub(_fin(revenue_ttm=1000e6, fcf_ttm=-50e6, sbc_ttm=10e6, cash=200e6, quarters=q),
          snap=_snap(precio=10.0, shares=100e6, mcap=3000e6))
    h = HE.hoja("PRE")
    assert h.route == "NON_FCFE"
    assert h.estado == "UNANCHORED"
    assert h.price_anchor_status == "ANCHORED"
    assert h.reverse_burden_type == "GP_MULTIPLE" and h.burden_gp is not None
    assert h.capital_risk_tier in ("A", "B", "C")


def test_rankear_solo_ordena_fcfe():
    q = [{"gross_profit": 200e6, "operating_income": 50e6, "ocf": 120e6} for _ in range(4)]
    fin_ok = _fin(revenue_ttm=1000e6, fcf_ttm=120e6, sbc_ttm=10e6, quarters=q)
    fin_bad = _fin(shares_outstanding=0.0, revenue_ttm=1000e6, fcf_ttm=100e6)
    HE.edgar.get_financials_quarterly = lambda t, periodos=8: fin_bad if t == "BAD" else fin_ok
    HE.market_data.get_price_snapshot = lambda t: _snap(shares=None, mcap=None) if t == "BAD" else _snap()
    HE.extraer_deterministas = lambda t: {}
    HE._clasificar_arquetipo = lambda d: "Growth"
    res = HE.rankear(["X", "BAD"])
    assert [h.ticker for h in res["rankeado"]] == ["X"]
    assert "MANUAL_DATA_CHECK" in res["descriptivo"]


def test_bull_contratado_rpo_prende_spread_y_marca_evidencia_insuficiente():
    # RPO (tipo ASUMIDO) → retención cancelable_backlog 0.60 + es_piso → evidencia_insuficiente (doc 14 §E1)
    det = {"revenue_ttm": 100e6, "rpo": 200e6, "rpo_as_of": "2026-06-30"}
    contratado, evid_insuf, src = HE._bull_contratado("X", det, "Growth")
    assert contratado == 200e6 * 0.60
    assert evid_insuf is True and "cancelable_backlog(asumido)" in src


def test_bull_contratado_sin_rpo_no_aporta():
    contratado, evid_insuf, src = HE._bull_contratado("X", {"revenue_ttm": 100e6}, "Growth")
    assert contratado == 0.0 and evid_insuf is False and src == ""


def test_bull_contratado_no_cancelable_usa_firm_y_apaga_evidencia_insuficiente():
    # E1: con el hecho citado (firme) → retención firm_po 0.85 y el flag asumido se apaga
    det = {"revenue_ttm": 100e6, "rpo": 200e6, "rpo_as_of": "2026-06-30"}
    contratado, evid_insuf, src = HE._bull_contratado("X", det, "Growth", no_cancelable=True)
    assert contratado == 200e6 * 0.85 and src == "firm_po" and evid_insuf is False
