"""P1 (doc 91 §7) — cap de posición = min(tier, arquetipo, banda, evidencia) (blueprint IA2 §1). Determinista."""
from backend.agentes.caps_posicion import cap_posicion

_CFG = {"tiers": {"CORE": {"min": 0.05, "max": 0.10}, "HIGH_CONVICTION": {"min_exclusive": 0.10, "max": 0.15}},
        "cap_por_arquetipo": {"compounder": 0.15, "ciclica": 0.10, "infra": 0.10, "pre_revenue": 0.0},
        "cap_por_banda": {"COMPRA_FUERTE": 0.15, "COMPRA": 0.10, "MANTENER": 0.0, "RECORTE": 0.0},
        "cap_por_evidencia_opcionalidad": {"PASS": 0.025, "REVIEW": 0.015, "FAIL": 0.0}}


def test_liga_el_cap_mas_restrictivo():
    # CORE (0.10) · cíclica (0.10) · banda COMPRA (0.10) → todas atan en 0.10; da igual la liga, el cap es 0.10.
    cap, _ = cap_posicion(tier="CORE", arquetipo="ciclica", banda="COMPRA", verificacion="PASS", cfg=_CFG)
    assert cap == 0.10


def test_banda_mantener_capea_dinero_nuevo_a_cero():
    # MANTENER no habilita dinero nuevo → cap 0 aunque el tier y el arquetipo permitan más.
    cap, liga = cap_posicion(tier="CORE", arquetipo="compounder", banda="MANTENER", verificacion="PASS", cfg=_CFG)
    assert cap == 0.0 and liga == "banda"


def test_pre_revenue_capea_nucleo_a_cero():
    cap, liga = cap_posicion(tier="CORE", arquetipo="pre_revenue", banda="COMPRA", verificacion="PASS", cfg=_CFG)
    assert cap == 0.0 and liga == "arquetipo"


def test_evidencia_solo_aplica_en_opcionalidad():
    # opcionalidad con REVIEW → cap 1.5% (evidencia liga).
    cap, liga = cap_posicion(tier="opcionalidad", arquetipo="ciclica", banda="COMPRA", verificacion="REVIEW", cfg=_CFG)
    assert cap == 0.015 and liga == "evidencia"


def test_compounder_puede_llegar_mas_alto_por_arquetipo():
    # HIGH_CONVICTION (0.15) · compounder (0.15) · COMPRA_FUERTE (0.15) → 0.15.
    cap, _ = cap_posicion(tier="HIGH_CONVICTION", arquetipo="compounder", banda="COMPRA_FUERTE",
                          verificacion="PASS", cfg=_CFG)
    assert cap == 0.15
