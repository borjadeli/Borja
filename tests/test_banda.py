"""P1 (doc 91 §7) — banda por arquetipo (blueprint IA2 §2). Determinista, sin LLM."""
from backend.agentes.banda import (banda_ciclica, banda_compounder, banda_infra, calcular_banda,
                                    pre_revenue_elegible_opcionalidad)


def test_infra_usa_extremo_bajo_de_cobertura():
    assert banda_infra(1.1) == "COMPRA_FUERTE"
    assert banda_infra(0.85) == "COMPRA"
    assert banda_infra(0.6) == "MANTENER"
    assert banda_infra(0.2) == "RECORTE"           # GLXY: CoreWeave no-IG → cobertura ~0 → RECORTE
    assert banda_infra(None) is None


def test_ciclica_precio_vs_mitad_de_ciclo():
    # valor mitad de ciclo [40, 80], medio 60.
    assert banda_ciclica(30, 40, 80) == "COMPRA_FUERTE"   # bien abajo del rango
    assert banda_ciclica(55, 40, 80) == "COMPRA"          # ≤ medio
    assert banda_ciclica(75, 40, 80) == "MANTENER"        # ≤ alto
    assert banda_ciclica(95, 40, 80) == "RECORTE"         # EXE: precio por encima del rango a la curva → RECORTE


def test_compounder_g_exigido_vs_sostenible():
    # g sostenible [0.08, 0.12].
    assert banda_compounder(0.04, 0.08, 0.12) == "COMPRA_FUERTE"   # < 0.08 - 3pp = 0.05
    assert banda_compounder(0.07, 0.08, 0.12) == "COMPRA"          # < 0.08 pero no < 0.05
    assert banda_compounder(0.11, 0.08, 0.12) == "MANTENER"        # dentro del rango sostenible
    assert banda_compounder(0.18, 0.08, 0.12) == "RECORTE"         # el precio exige más de lo sostenible


def test_pre_revenue_sin_banda_de_nucleo_pero_elegible_opcionalidad():
    assert calcular_banda("pre_revenue", {"precio": 10}) is None        # NO va a núcleo
    assert pre_revenue_elegible_opcionalidad(0.15, 0.25) is True        # p_implícita.alto < p_razonada.bajo → margen
    assert pre_revenue_elegible_opcionalidad(0.30, 0.25) is False       # el precio ya implica más éxito que lo razonado


def test_dispatcher_y_datos_faltantes():
    assert calcular_banda("ciclica", {"precio": 30, "valor_mitad_ciclo_bajo": 40, "valor_mitad_ciclo_alto": 80}) == "COMPRA_FUERTE"
    assert calcular_banda("ciclica", {"precio": 30}) is None            # faltan los rangos → None (no inventa banda)
    assert calcular_banda("infra", {"cobertura_ig_bajo": 0.9}) == "COMPRA"


def test_rango_invertido_o_nan_es_none():
    from backend.agentes.banda import banda_ciclica, banda_compounder
    assert banda_ciclica(60, 80, 40) is None            # bajo > alto → None (antes daba COMPRA_FUERTE)
    assert banda_ciclica(60, float("nan"), 80) is None
    assert banda_compounder(0.10, 0.12, 0.08) is None    # g_sost invertido → None


def test_dominios_numericos_invalidos_son_none():
    from backend.agentes.banda import banda_infra, banda_ciclica, banda_compounder, pre_revenue_elegible_opcionalidad
    assert banda_infra(float("inf")) is None            # cobertura inf → None (antes COMPRA_FUERTE)
    assert banda_infra(-0.5) is None                    # cobertura negativa → None
    assert banda_ciclica(-1, 40, 80) is None            # precio negativo → None (antes COMPRA_FUERTE)
    assert banda_ciclica(float("nan"), 40, 80) is None
    assert banda_compounder(float("-inf"), 0.10, 0.20) is None
    assert pre_revenue_elegible_opcionalidad(-0.5, 1.5) is False   # probabilidades fuera de [0,1] → False
    assert pre_revenue_elegible_opcionalidad(0.15, 0.25) is True   # sigue andando el caso válido
