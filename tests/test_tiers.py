"""P1.3 (doc 91 §7) — validador de tiers del IPS (IA1 it.2 §1.2). Determinista, sin LLM."""
from backend.agentes.tiers import peso_valido, tier_de_peso, valid_target_weight

_CFG = {"OPTIONALITY": {"min": 0.01, "max": 0.03}, "CORE": {"min": 0.05, "max": 0.10},
        "HIGH_CONVICTION": {"min_exclusive": 0.10, "max": 0.15},
        "EXCEPTIONAL": {"min_exclusive": 0.15, "max": 0.20}}


def test_valid_target_weight_por_tier():
    assert valid_target_weight(0.0, "EXIT", _CFG)
    assert valid_target_weight(0.02, "OPTIONALITY", _CFG) and not valid_target_weight(0.04, "OPTIONALITY", _CFG)
    assert valid_target_weight(0.07, "CORE", _CFG) and not valid_target_weight(0.04, "CORE", _CFG)   # el residual 4% de IA1
    assert valid_target_weight(0.12, "HIGH_CONVICTION", _CFG)
    assert not valid_target_weight(0.10, "HIGH_CONVICTION", _CFG)       # min_exclusive: 10% es CORE, no HIGH_CONV
    assert valid_target_weight(0.18, "EXCEPTIONAL", _CFG) and not valid_target_weight(0.21, "EXCEPTIONAL", _CFG)


def test_bordes_inclusivos_y_exclusivos():
    assert tier_de_peso(0.10, _CFG) == "CORE"              # 10% = max inclusivo de CORE (gana sobre HIGH_CONV exclusivo)
    assert tier_de_peso(0.15, _CFG) == "HIGH_CONVICTION"   # 15% = max inclusivo de HIGH_CONV
    assert tier_de_peso(0.20, _CFG) == "EXCEPTIONAL"       # 20% = tope duro
    assert tier_de_peso(0.01, _CFG) == "OPTIONALITY" and tier_de_peso(0.05, _CFG) == "CORE"


def test_zonas_gris_invalidas():
    # NO hay tier 3-5% (decisión IA1): 4% y 3.5% caen entre tiers → inválidos (ni OPTIONALITY ni CORE).
    assert tier_de_peso(0.04, _CFG) is None and not peso_valido(0.04, _CFG)
    assert tier_de_peso(0.035, _CFG) is None
    assert tier_de_peso(0.005, _CFG) is None               # abajo de OPTIONALITY
    assert tier_de_peso(0.25, _CFG) is None                # arriba de EXCEPTIONAL


def test_cero_es_exit_y_valido():
    assert tier_de_peso(0.0, _CFG) == "EXIT" and peso_valido(0.0, _CFG)
