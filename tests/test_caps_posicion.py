"""P1 (doc 91 §7) — cap de posición FAIL-CLOSED (review IA1 + blueprint IA2 §1). Determinista.

Los tests de aceptación de IA1: un dato faltante/desconocido NUNCA agranda el cap. OPTIONALITY no usa los caps de
núcleo. (Reemplazan a los tests viejos que codificaban el comportamiento fail-open.)"""
import pytest

from backend.agentes.caps_posicion import cap_posicion

_CFG = {"tiers": {"OPTIONALITY": {"min": 0.015, "max": 0.025}, "CORE": {"min": 0.05, "max": 0.10},
                  "HIGH_CONVICTION": {"min_exclusive": 0.10, "max": 0.15},
                  "EXCEPTIONAL": {"min_exclusive": 0.15, "max": 0.20}},
        "cap_por_arquetipo": {"compounder": 0.15, "ciclica": 0.10, "infra": 0.10, "pre_revenue": 0.0},
        "cap_por_banda": {"COMPRA_FUERTE": 0.15, "COMPRA": 0.10, "MANTENER": 0.0, "RECORTE": 0.0},
        "cap_por_evidencia_opcionalidad": {"PASS": 0.025, "REVIEW": 0.015, "FAIL": 0.0}}


# ── alcance por tier: el cap de núcleo NO aplica a la manga ──
def test_cap_arquetipo_es_solo_de_nucleo():
    # pre_revenue tiene cap 0 en NÚCLEO; en OPTIONALITY tiene que poder existir (es la razón de la manga).
    assert cap_posicion(tier="OPTIONALITY", arquetipo="pre_revenue", banda=None, verificacion="PASS", cfg=_CFG)[0] == 0.025


def test_cap_banda_es_solo_dinero_nuevo_de_nucleo():
    # MANTENER = 0 de dinero nuevo en núcleo; en opcionalidad MANTENER es elegible.
    assert cap_posicion(tier="OPTIONALITY", arquetipo="infra", banda="MANTENER", verificacion="PASS", cfg=_CFG)[0] == 0.025


def test_opcionalidad_rechaza_recorte_y_banda_desconocida_salvo_pre_revenue():
    assert cap_posicion(tier="OPTIONALITY", arquetipo="infra", banda="RECORTE", verificacion="PASS", cfg=_CFG)[0] == 0.0
    assert cap_posicion(tier="OPTIONALITY", arquetipo="ciclica", banda=None, verificacion="PASS", cfg=_CFG)[0] == 0.0


def test_evidencia_review_liga_en_opcionalidad():
    # antes comparaba contra 'opcionalidad' (minúscula) y nunca aplicaba → REVIEW daba 2.5% en vez de 1.5%.
    assert cap_posicion(tier="OPTIONALITY", arquetipo="ciclica", banda="COMPRA", verificacion="REVIEW", cfg=_CFG) == (0.015, "evidencia")


def test_opcionalidad_sin_verificacion_es_cero():
    assert cap_posicion(tier="OPTIONALITY", arquetipo="ciclica", banda="COMPRA", verificacion=None, cfg=_CFG)[0] == 0.0


# ── fail-closed en núcleo ──
@pytest.mark.parametrize("tier", ["CORE", "HIGH_CONVICTION", "EXCEPTIONAL"])
def test_banda_desconocida_en_nucleo_es_cap_cero(tier):
    assert cap_posicion(tier=tier, arquetipo="ciclica", banda=None, verificacion="PASS", cfg=_CFG)[0] == 0.0


@pytest.mark.parametrize("tier", ["CORE", "HIGH_CONVICTION", "EXCEPTIONAL"])
def test_arquetipo_desconocido_en_nucleo_es_cap_cero(tier):
    assert cap_posicion(tier=tier, arquetipo=None, banda="COMPRA_FUERTE", verificacion="PASS", cfg=_CFG)[0] == 0.0


def test_tier_desconocido_es_cero():
    assert cap_posicion(tier="opcionalidad", arquetipo="ciclica", banda="COMPRA", verificacion="PASS", cfg=_CFG)[0] == 0.0


def test_ninguna_combinacion_supera_15():
    # EXCEPTIONAL (>15%) es inalcanzable con los caps actuales (arquetipo/banda ≤15). Queda decorativo (IA1+IA2: remover).
    for arq in [None, "compounder", "ciclica", "infra", "pre_revenue"]:
        for banda in [None, "COMPRA_FUERTE", "COMPRA", "MANTENER", "RECORTE"]:
            cap, _ = cap_posicion(tier="EXCEPTIONAL", arquetipo=arq, banda=banda, verificacion="PASS", cfg=_CFG)
            assert cap <= 0.15 + 1e-9, (arq, banda, cap)


# ── núcleo: min no-compensatorio ──
def test_nucleo_liga_el_mas_restrictivo():
    assert cap_posicion(tier="CORE", arquetipo="compounder", banda="MANTENER", verificacion="PASS", cfg=_CFG) == (0.0, "banda")
    assert cap_posicion(tier="CORE", arquetipo="pre_revenue", banda="COMPRA", verificacion="PASS", cfg=_CFG) == (0.0, "arquetipo")
    assert cap_posicion(tier="HIGH_CONVICTION", arquetipo="compounder", banda="COMPRA_FUERTE", verificacion="PASS", cfg=_CFG)[0] == 0.15


def test_opcionalidad_rechaza_banda_desconocida_no_solo_recorte():
    # review-2 IA1: una banda desconocida ("FOO") daba 2.5%. Ahora solo COMPRA_FUERTE/COMPRA/MANTENER son elegibles.
    assert cap_posicion(tier="OPTIONALITY", arquetipo="infra", banda="FOO", verificacion="PASS", cfg=_CFG)[0] == 0.0
