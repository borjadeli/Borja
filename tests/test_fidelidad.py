"""Tests del guard de fidelidad (unidad canónica + plausibilidad). Sin red."""
from backend.nucleo.fidelidad import canon


def test_convierte_pct_a_fraccion():
    assert canon(37.66, tipo="margen", es_pct=True) == 37.66 / 100.0   # 0.3766


def test_dilucion_real_pasa():
    # COHR: 40.37% de dilución → fracción 0.4037, en rango → pasa
    assert canon(40.37, tipo="dilucion", es_pct=True) == 40.37 / 100.0


def test_dilucion_absurda_se_descarta():
    # un valor de dilución imposible (4037% → 40.37 fracción) → fuera de rango → None
    assert canon(4037.0, tipo="dilucion", es_pct=True) is None


def test_margen_fuera_de_rango_es_none():
    assert canon(150.0, tipo="margen", es_pct=True) is None            # 1.5 > 1.0
    assert canon(-2.0, tipo="margen") is None


def test_positivo_rechaza_negativo():
    assert canon(-5.0, tipo="positivo") is None
    assert canon(100.0, tipo="positivo") == 100.0


def test_no_numerico_es_none():
    assert canon("N/D", tipo="monto") is None
    assert canon(None, tipo="monto") is None


def test_monto_acepta_negativo():
    assert canon(-1e6, tipo="monto") == -1e6                            # FCF negativo es válido
