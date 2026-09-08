"""Contrato de admisibilidad fact store → scenario compiler (doc 27 §5/§6).

Verifica que la ELEGIBILIDAD la decide la regla (no el extractor) y que la fuerza de fuente
gobierna qué entra al bull operable — con el caso AAOI/Amazon como ancla.
"""
from backend.nucleo import admisibilidad as AD


def test_management_claim_no_es_admisible():
    # AAOI / warrant Amazon $4B: hecho correctamente citado, pero es una expectativa de management
    # (compras futuras discrecionales) → 0 en el bull operable. Va al option ledger, no a la valuación.
    r = AD.es_admisible("respaldo_backlog", AD.MANAGEMENT_CLAIM)
    assert r["valuation_eligible"] is False
    assert r["haircut"] is None


def test_promocional_no_es_admisible():
    assert AD.es_admisible("hechos_comerciales", AD.PROMOTIONAL)["valuation_eligible"] is False


def test_revenue_reportado_es_admisible_sin_haircut():
    r = AD.es_admisible("demanda_realizada", AD.REPORTED_AUDITED)
    assert r["valuation_eligible"] is True
    assert r["haircut"] == AD.SIN_HAIRCUT


def test_backlog_contratado_lleva_haircut():
    # Backlog con contraparte → entra, pero con conversión histórica (no al 100%).
    r = AD.es_admisible("respaldo_backlog", AD.CONTRACT_COUNTERPARTY)
    assert r["valuation_eligible"] is True
    assert r["haircut"] == AD.CONVERSION_HISTORICA


def test_sin_clase_no_es_admisible():
    # Conservador: sin evidence_class reconocida, no se valúa (no se inventa elegibilidad).
    assert AD.es_admisible("x", None)["valuation_eligible"] is False
    assert AD.es_admisible("x", "inventada")["valuation_eligible"] is False


def test_override_manda_sobre_default():
    # Un override por (fact_key, evidence_class) pisa el default de la clase.
    AD._OVERRIDES[("caso_x", AD.GUIDANCE)] = {"valuation_eligible": True, "haircut": AD.SOLO_IRREVOCABLE}
    try:
        r = AD.es_admisible("caso_x", AD.GUIDANCE)
        assert r["valuation_eligible"] is True
        assert r["haircut"] == AD.SOLO_IRREVOCABLE
        assert "override" in r["motivo"]
        # otro fact_key con la misma clase sigue con el default (no admisible)
        assert AD.es_admisible("otro", AD.GUIDANCE)["valuation_eligible"] is False
    finally:
        del AD._OVERRIDES[("caso_x", AD.GUIDANCE)]
