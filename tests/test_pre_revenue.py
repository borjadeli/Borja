"""Tests del motor de reverse underwriting pre-revenue (doc 31 §2, §5, §6)."""
from __future__ import annotations

import math

from backend.nucleo import pre_revenue as pr
from backend.nucleo.dilucion import Dilucion


def _dil(banda="bajo", runway=5.0, critico=False):
    return Dilucion(burn_yield=0.1, banda=banda, runway_anos=runway,
                    runway_critico=critico, forward_dilution_unknown=True, nota="")


# --- FCFE requerido: OP × r_exit × (1+r_hurdle)^t (ρ=1) ---
def test_fcfe_requerido_formula():
    # sin r_exit → retrocompat: usa r_hurdle en ambos factores
    got = pr.fcfe_requerido(100.0, 0.25, 5)
    assert math.isclose(got, 100.0 * 0.25 * 1.25 ** 5, rel_tol=1e-9)


def test_fcfe_requerido_desacopla_r_exit():
    # fix 2026-08: el cap yield terminal (r_exit) desacoplado del descuento del camino (r_hurdle)
    got = pr.fcfe_requerido(100.0, 0.25, 5, r_exit=0.15)
    assert math.isclose(got, 100.0 * 0.15 * 1.25 ** 5, rel_tol=1e-9)
    # r_exit menor ⇒ FCFE requerido menor (menos doble castigo)
    assert got < pr.fcfe_requerido(100.0, 0.25, 5)


def test_fcfe_requerido_op_none_o_cero():
    assert pr.fcfe_requerido(None, 0.25, 5) is None
    assert pr.fcfe_requerido(0.0, 0.25, 5) == 0.0


# --- Opex de caja TTM = (GP − OI) − SBC ---
def test_opex_cash_resta_sbc():
    assert pr.opex_cash_ttm(100.0, -50.0, 20.0) == 130.0     # (100+50)-20


def test_opex_cash_sin_datos_es_none():
    assert pr.opex_cash_ttm(None, -50.0, 20.0) is None
    assert pr.opex_cash_ttm(100.0, None, 20.0) is None


def test_opex_cash_nunca_negativo():
    assert pr.opex_cash_ttm(100.0, 200.0, 0.0) == 0.0        # OI>GP (raro) → clamp a 0


# --- Reverse burden GP-multiple ---
def test_reverse_burden_gp():
    burden = pr.reverse_burden_gp(76.29, 130.0, 100.0)
    assert math.isclose(burden, (130.0 + 76.29) / 100.0, rel_tol=1e-9)


def test_reverse_burden_requiere_gp_positivo():
    assert pr.reverse_burden_gp(50.0, 100.0, 0.0) is None
    assert pr.reverse_burden_gp(50.0, 100.0, -10.0) is None


# --- Tier de riesgo de capital (mecánico) ---
def test_tier_C_por_banda_severa_o_runway_critico():
    assert pr.capital_risk_tier(5.0, "severo", False) == "C"
    assert pr.capital_risk_tier(5.0, "bajo", True) == "C"


def test_tier_A_cash_rich_sin_quema():
    assert pr.capital_risk_tier(None, "bajo", False) == "A"
    assert pr.capital_risk_tier(4.0, "bajo", False) == "A"


def test_tier_B_intermedio():
    assert pr.capital_risk_tier(None, "material", False) == "B"
    assert pr.capital_risk_tier(2.0, "material", False) == "B"


def test_tier_C_runway_corto():
    assert pr.capital_risk_tier(0.8, "material", False) == "C"   # <1.5 y no cae en A/B


# --- evaluar(): ANCHORED con GP_MULTIPLE ---
def test_evaluar_anchored_gp_multiple():
    ru = pr.evaluar(stage="R4", route="NON_FCFE", gross_profit_ttm=200e6,
                    operating_income_ttm=-100e6, sbc_ttm=30e6, operable_por_accion=2.0,
                    precio=10.0, shares=100e6, mcap=1000e6, arquetipo="Tracción", dilucion=_dil())
    assert ru.price_anchor_status == "ANCHORED"
    assert ru.reverse_burden_type == "GP_MULTIPLE"
    # OP = 1000M − 200M = 800M; fcfe = 800M·r_exit·1.2^5 con r_exit=min(0.20,0.15)=0.15; opex = 300M−30M = 270M
    op = 800e6
    fcfe = op * 0.15 * 1.20 ** 5
    esperado = (270e6 + fcfe) / 200e6
    assert math.isclose(ru.reverse_burden, esperado, rel_tol=1e-9)
    assert math.isclose(ru.option_premium, op, rel_tol=1e-9)
    assert ru.t_anios == 5 and math.isclose(ru.r, 0.20) and math.isclose(ru.r_exit, 0.15)


# --- evaluar(): R0 sin economía → PURE_OPTION, sin burden ---
def test_evaluar_pure_option_R0():
    ru = pr.evaluar(stage="R0", route="NON_FCFE", gross_profit_ttm=None,
                    operating_income_ttm=None, sbc_ttm=None, operable_por_accion=1.0,
                    precio=8.0, shares=50e6, mcap=400e6, arquetipo="Pre-revenue", dilucion=_dil())
    assert ru.price_anchor_status == "PURE_OPTION"
    assert ru.reverse_burden is None
    assert any("pure_option" in f for f in ru.flags)


# --- evaluar(): R0 con gross_profit filtrado NO se ancla (scope R2-R5, doc 31 §2) ---
def test_evaluar_R0_con_gp_sigue_pure_option():
    ru = pr.evaluar(stage="R0", route="NON_FCFE", gross_profit_ttm=5e6,
                    operating_income_ttm=-40e6, sbc_ttm=2e6, operable_por_accion=1.0,
                    precio=8.0, shares=50e6, mcap=400e6, arquetipo="Pre-revenue", dilucion=_dil())
    assert ru.price_anchor_status == "PURE_OPTION"
    assert ru.reverse_burden is None
    assert any("revisar revenue" in f for f in ru.flags)


# --- evaluar(): GP>0 pero operating_income desconocido → no computable (NA, no ANCHORED) ---
def test_evaluar_gp_sin_oi_no_computable():
    ru = pr.evaluar(stage="R2", route="NON_FCFE", gross_profit_ttm=100e6,
                    operating_income_ttm=None, sbc_ttm=None, operable_por_accion=1.0,
                    precio=10.0, shares=100e6, mcap=1000e6, arquetipo="Growth", dilucion=_dil())
    assert ru.price_anchor_status == "NA"
    assert ru.reverse_burden is None


# --- evaluar(): route FCFE_OPERABLE → lo ancla el operable, no el reverse underwriting ---
def test_evaluar_fcfe_operable_no_usa_reverse():
    ru = pr.evaluar(stage="R5", route="FCFE_OPERABLE", gross_profit_ttm=500e6,
                    operating_income_ttm=100e6, sbc_ttm=50e6, operable_por_accion=20.0,
                    precio=25.0, shares=100e6, mcap=2500e6, arquetipo="Growth", dilucion=_dil())
    assert ru.price_anchor_status == "ANCHORED"
    assert ru.reverse_burden_type == "NA"
    assert ru.reverse_burden is None


# --- evaluar(): flag cuando mcap es fallback precio×shares ---
def test_evaluar_flag_mcap_fallback():
    ru = pr.evaluar(stage="R4", route="NON_FCFE", gross_profit_ttm=200e6,
                    operating_income_ttm=-100e6, sbc_ttm=30e6, operable_por_accion=2.0,
                    precio=10.0, shares=100e6, mcap=None, arquetipo="Tracción", dilucion=_dil())
    assert any("mcap=precio×shares" in f for f in ru.flags)
    assert math.isclose(ru.option_premium, 10.0 * 100e6 - 2.0 * 100e6, rel_tol=1e-9)


# --- evaluar(): arquetipo desconocido → flag de default r (fix C2, hueco silencioso cerrado) ---
def test_evaluar_flag_arquetipo_default():
    ru = pr.evaluar(stage="R4", route="NON_FCFE", gross_profit_ttm=200e6,
                    operating_income_ttm=-100e6, sbc_ttm=30e6, operable_por_accion=2.0,
                    precio=10.0, shares=100e6, mcap=1000e6, arquetipo="Inexistente", dilucion=_dil())
    assert any("arquetipo_default_r" in f for f in ru.flags)


def test_gap_financiamiento_runway_vs_horizonte():
    from backend.nucleo.pre_revenue import gap_financiamiento
    assert gap_financiamiento(100e6, 10.0, 5) == 0.0          # runway 10 ≥ horizonte 5 → no diluye
    assert gap_financiamiento(100e6, 2.0, 5) == 100e6 * 3     # burn 100M × (5−2) = 300M
    assert gap_financiamiento(None, 2.0, 5) == 0.0            # sin burn → 0


def test_burden_con_rho_infla_al_quemador():
    from backend.nucleo.pre_revenue import burden_con_rho
    assert burden_con_rho(50.0, 1000e6, 0.0) == 50.0         # G=0 (runway cubre) → sin cambio
    assert burden_con_rho(50.0, 1000e6, 1000e6) == 100.0     # ρ=0.5 → burden ×2 (dilución 100%)
    assert burden_con_rho(None, 1000e6, 100e6) is None
