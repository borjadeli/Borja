"""P1 (doc 91 §7) — clasificador de arquetipo (blueprint IA2). Casos de la corrida del 25-nov. Determinista."""
from backend.agentes.arquetipo import clasificar_arquetipo


def test_infra_gana_por_precedencia_aunque_ocf_negativo():
    # CIFR: contratado firme total >> EV y capex alto → infra, AUNQUE OCF<0 (infra precede a pre_revenue).
    d = {"contratado_firme": 14.6e9, "ev": 7.8e9, "capex": 2.0e9, "revenue": 0.27e9, "ocf_ltm": -10e6}
    assert clasificar_arquetipo(d) == "infra"


def test_pre_revenue_por_margen_bruto_negativo():
    # WOLF: revenue ~$620M (no <$50M) pero margen bruto −22% → pre_revenue.
    assert clasificar_arquetipo({"revenue_ltm": 620e6, "margen_bruto_ltm": -0.22}) == "pre_revenue"


def test_pre_revenue_por_revenue_chico():
    assert clasificar_arquetipo({"revenue_ltm": 30e6}) == "pre_revenue"


def test_ciclica_por_sector():
    # EXE (E&P) y VST (IPP) → cíclica por tag de sector.
    assert clasificar_arquetipo({"sector": "E&P", "revenue_ltm": 7e9}) == "ciclica"
    assert clasificar_arquetipo({"sector": "IPP"}) == "ciclica"


def test_ciclica_por_margen_sobre_mediana():
    # margen LTM > 1.5× la mediana de 10a → cíclica (pico de ciclo).
    assert clasificar_arquetipo({"margen_op_ltm": 0.20, "margen_op_mediana_10a": 0.10}) == "ciclica"


def test_compounder_necesita_fcf_y_roic_sostenidos():
    assert clasificar_arquetipo({"fcf_pos_anios_de5": 5, "roic_gt15_anios_de5": 4}) == "compounder"
    assert clasificar_arquetipo({"fcf_pos_anios_de5": 5, "roic_gt15_anios_de5": 2}) is None   # ROIC flojo → no compounder


def test_datos_insuficientes_es_unclassified():
    assert clasificar_arquetipo({}) is None
    assert clasificar_arquetipo({"revenue_ltm": 5e9}) is None     # rev alto, sin otras señales → el Analista decide


# ── robustez de insumos (review IA1) ──
def test_clasificador_no_depende_del_nombre_de_la_clave_revenue():
    # infra leía 'revenue' y pre_revenue 'revenue_ltm'. Con solo revenue_ltm, CIFR caía en pre_revenue.
    cifr = {"contratado_firme": 14.6e9, "ev": 7.8e9, "capex": 2.0e9, "revenue_ltm": 0.27e9, "ocf_ltm": -10e6, "runway_meses": 14}
    assert clasificar_arquetipo(cifr) == "infra"


def test_capex_negativo_del_cash_flow_no_apaga_infra():
    cifr = {"contratado_firme": 14.6e9, "ev": 7.8e9, "capex": -2.0e9, "revenue": 0.27e9}
    assert clasificar_arquetipo(cifr) == "infra"


def test_infra_no_evaluable_no_cae_silenciosamente_a_pre_revenue():
    # contratado_firme=None (no escaneado) ≠ 0. Con None: UNCLASSIFIED, no pre_revenue (la vía OCF solapa con infra).
    d = {"ev": 7.8e9, "capex": 2.0e9, "revenue": 0.27e9, "revenue_ltm": 0.27e9, "ocf_ltm": -10e6, "runway_meses": 14}
    assert clasificar_arquetipo(d) is None
