"""P1 (doc 91 §7) — comparación antes de rotar (blueprint IA2 §5). Determinista, sin LLM."""
from backend.agentes.comparacion_rotacion import comparar_rotacion


def test_iesc_a_eme_bloqueada_eme_sin_dossier():
    # El caso de la corrida: vender IESC para comprar EME, pero EME no tenía dossier → falla evidencia.
    a = {"verificacion": "REVIEW", "banda": "RECORTE", "bear_severidad": "media"}
    b = {"verificacion": "REVIEW", "banda": "MANTENER", "bear_severidad": "media",
         "nulls_portantes": ["metrica_obligatoria"], "dossier_del_ciclo": False}
    res, motivos = comparar_rotacion(a, b)
    assert res == "BLOQUEADA" and any("nulls portantes" in m or "no es del ciclo" in m for m in motivos)


def test_rotacion_valida_cuando_B_domina():
    a = {"verificacion": "REVIEW", "banda": "MANTENER", "bear_severidad": "media"}
    b = {"verificacion": "PASS", "banda": "COMPRA_FUERTE", "bear_severidad": "leve"}
    assert comparar_rotacion(a, b)[0] == "PERMITIDA"


def test_empate_de_margen_bloquea():
    # misma banda → B no está ≥1 escalón sobre A → BLOQUEADA (default mantener A).
    a = {"verificacion": "PASS", "banda": "COMPRA", "bear_severidad": "leve"}
    b = {"verificacion": "PASS", "banda": "COMPRA", "bear_severidad": "leve"}
    res, motivos = comparar_rotacion(a, b)
    assert res == "BLOQUEADA" and any("margen" in m for m in motivos)


def test_riesgo_no_compensa_margen():
    # B tiene mejor banda pero bear más severo → no compensa (no compensatorio) → BLOQUEADA.
    a = {"verificacion": "PASS", "banda": "MANTENER", "bear_severidad": "leve"}
    b = {"verificacion": "PASS", "banda": "COMPRA_FUERTE", "bear_severidad": "severa"}
    res, motivos = comparar_rotacion(a, b)
    assert res == "BLOQUEADA" and any("riesgo" in m for m in motivos)


def test_venta_a_caja_valida_solo_si_A_en_recorte():
    assert comparar_rotacion({"banda": "RECORTE"}, {"es_caja": True})[0] == "PERMITIDA"
    assert comparar_rotacion({"banda": "MANTENER"}, {"es_caja": True})[0] == "BLOQUEADA"
    assert comparar_rotacion({"banda": "MANTENER", "flag_alta_no_opera": True}, {"es_caja": True})[0] == "PERMITIDA"
