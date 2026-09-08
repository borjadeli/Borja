"""Ruteo de dos ejes (doc 42 §2, D2): test de DERIVADA separa 'escala' de 'muere'. Todo XBRL."""
from backend.nucleo import ruteo as R


def _gp_opex(gp_growth, opex_growth, base_gp=25.0, base_opex=30.0, n=11):
    """`n` trimestres (≥11: el ruteo lag-ea el GP 3Q y aún necesita 8 para el Δ8Q, doc 47). GP y OpEx
    creciendo a las tasas dadas por trimestre."""
    gp = [base_gp * (1 + gp_growth) ** i for i in range(n)]
    opex = [base_opex * (1 + opex_growth) ** i for i in range(n)]
    return gp, opex


def test_apalancamiento_operativo():
    # GP crece más rápido que OpEx → apalancamiento > 1 (escala)
    gp, opex = _gp_opex(0.15, 0.05)
    assert R.apalancamiento_operativo(gp, opex) > 1.0
    # GP crece más lento → < 1 (no escala)
    gp2, opex2 = _gp_opex(0.03, 0.15)
    assert R.apalancamiento_operativo(gp2, opex2) < 1.0


def test_maduro_owner_fcf_positivo():
    gp, opex = _gp_opex(0.05, 0.05)
    r = R.rutear("X", revenue_ttm=1000, gp_qtrs=gp, opex_qtrs=opex, owner_fcf=50,
                 sbc_ttm=10, cfo_ttm=60, capex_ttm=0)
    assert r.estado == R.COMERCIAL_MADURO


def test_good_loser_escalando():
    # comercial, owner-FCF<0 (SBC alto), PERO GM alto + apalancamiento demostrado → ESCALANDO (no BURDEN)
    gp, opex = _gp_opex(0.18, 0.06, base_gp=200, base_opex=250)   # GP crece rápido
    r = R.rutear("SAAS", revenue_ttm=1000, gp_qtrs=gp, opex_qtrs=opex, owner_fcf=-50,
                 sbc_ttm=150, cfo_ttm=100, capex_ttm=0, runway_meses=36)   # GM 200/250... ajustar
    # gross margin = sum(gp[-4:])/rev; con base 200 y rev 1000 → GM alto. apalancamiento >1.
    assert r.estado == R.COMERCIAL_ESCALANDO
    assert r.apalancamiento > 1.0


def test_muere_no_escala_es_burden():
    # comercial, owner-FCF<0, y SIN apalancamiento (OpEx crece más que GP) → BURDEN ('muere')
    gp, opex = _gp_opex(0.02, 0.20, base_gp=200, base_opex=250)
    r = R.rutear("DYING", revenue_ttm=1000, gp_qtrs=gp, opex_qtrs=opex, owner_fcf=-50,
                 sbc_ttm=100, cfo_ttm=50, capex_ttm=0, runway_meses=36)
    assert r.estado == R.BURDEN


def test_sbc_excesivo_es_burden():
    # SBC/revenue > 25% → motor comercial ficticio → BURDEN aunque tenga apalancamiento
    gp, opex = _gp_opex(0.18, 0.06, base_gp=200, base_opex=250)
    r = R.rutear("SBCHEAVY", revenue_ttm=1000, gp_qtrs=gp, opex_qtrs=opex, owner_fcf=-50,
                 sbc_ttm=300, cfo_ttm=100, capex_ttm=0, runway_meses=36)   # SBC 300/1000 = 30%
    assert r.estado == R.BURDEN and "ficticio" in r.motivo


def test_pre_revenue_con_hito_y_base_rate_es_binario():
    r = R.rutear("BIO", revenue_ttm=0, gp_qtrs=[], opex_qtrs=[], owner_fcf=-40,
                 sbc_ttm=5, cfo_ttm=-40, capex_ttm=0, hito_binario=True, base_rate_n=30)
    assert r.estado == R.PRE_REVENUE_BINARIO


def test_pre_revenue_sin_base_rate_es_burden_floor():
    # pre-revenue sin tabla auditable → quinto estado (floor-only) → BURDEN
    r = R.rutear("PHOTONIC", revenue_ttm=0, gp_qtrs=[], opex_qtrs=[], owner_fcf=-40,
                 sbc_ttm=5, cfo_ttm=-40, capex_ttm=0, hito_binario=True, base_rate_n=5)
    assert r.estado == R.BURDEN and "floor-only" in r.motivo
