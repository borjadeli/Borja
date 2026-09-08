"""Escalera de realización + router de valuación (doc 31 §1 + review build 2026-08)."""
from types import SimpleNamespace

from backend.nucleo.realizacion import etapa_realizacion


def _fin(revenue_ttm=None, fcf_ttm=None, sbc_ttm=None, quarters=None):
    return SimpleNamespace(revenue_ttm=revenue_ttm, fcf_ttm=fcf_ttm, sbc_ttm=sbc_ttm,
                           quarters=quarters or [])


def _q4(gp=None, oi=None, ocf=None):
    return [{"gross_profit": gp, "operating_income": oi, "ocf": ocf} for _ in range(4)]


def test_r0_sin_revenue():
    assert etapa_realizacion(_fin(revenue_ttm=None, fcf_ttm=-50e6, quarters=_q4(gp=-10e6))).stage == "R0"


def test_r1_gross_profit_negativo():
    assert etapa_realizacion(_fin(revenue_ttm=100e6, fcf_ttm=-30e6, quarters=_q4(gp=-5e6))).stage == "R1"


def test_crwd_stage_r2_route_fcfe():
    # CRWD: FCF>0, pero owner_fcf = FCF − SBC sigue > 0 → stage R2 (OI<0) pero route FCFE_OPERABLE.
    r = etapa_realizacion(_fin(revenue_ttm=3000e6, fcf_ttm=1600e6, sbc_ttm=1100e6,
                               quarters=_q4(gp=2000e6, oi=-100e6, ocf=1700e6)))
    assert r.stage == "R2"
    assert r.route == "FCFE_OPERABLE"
    assert any("gaap_operating_loss" in f for f in r.flags)


def test_cash_positive_not_owner_profitable():
    # FCF>0 solo por el add-back de SBC (owner_fcf < 0) → route CASH_POSITIVE_NOT_OWNER_PROFITABLE.
    r = etapa_realizacion(_fin(revenue_ttm=1000e6, fcf_ttm=1000e6, sbc_ttm=1200e6,
                               quarters=_q4(gp=600e6, oi=-200e6, ocf=1100e6)))
    assert r.route == "CASH_POSITIVE_NOT_OWNER_PROFITABLE"


def test_monotona_oi_positivo_infiere_gp():
    # Defensa/servicios sin tag de GrossProfit pero OI>0 → NO queda INDETERMINATE_AT_GP.
    r = etapa_realizacion(_fin(revenue_ttm=3000e6, fcf_ttm=300e6, sbc_ttm=10e6,
                               quarters=_q4(gp=None, oi=200e6, ocf=350e6)))
    assert r.stage == "R5"
    assert any("gp_inferido" in f for f in r.flags)


def test_fcf_breakeven_no_es_r5():
    # FCF = 0 (breakeven) → R4, no R5 (bug corregido: era FCF<0).
    r = etapa_realizacion(_fin(revenue_ttm=1000e6, fcf_ttm=0.0, sbc_ttm=0.0,
                               quarters=_q4(gp=500e6, oi=100e6, ocf=50e6)))
    assert r.stage == "R4"


def test_sbc_desconocida_route_indeterminate():
    # FCF>0 pero SBC None → no se asume SBC=0 → route INDETERMINATE_SBC.
    r = etapa_realizacion(_fin(revenue_ttm=1000e6, fcf_ttm=200e6, sbc_ttm=None,
                               quarters=_q4(gp=500e6, oi=50e6, ocf=250e6)))
    assert r.route == "INDETERMINATE_SBC"
