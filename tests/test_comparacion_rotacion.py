"""P1 (doc 91 §8) — comparación de rotación: VALIDEZ (código) vs MÉRITO (PM) (review IA2 §1.6 + fail-closed IA1).
PERMITIDA = la comparación es válida y el PM decide el mérito. BLOQUEADA = inválida (fail-closed)."""
from backend.agentes.comparacion_rotacion import comparar_rotacion


# ── fail-closed: la ausencia de info NO habilita la rotación ──
def test_rotacion_con_banda_de_A_desconocida_bloquea():
    a = {"verificacion": "PASS", "banda": None, "bear_severidad": "media"}
    b = {"verificacion": "PASS", "banda": "RECORTE", "bear_severidad": "leve", "dossier_del_ciclo": True}
    assert comparar_rotacion(a, b)[0] == "BLOQUEADA"


def test_rotacion_sin_verificacion_en_B_bloquea():
    a = {"banda": "MANTENER", "bear_severidad": "media"}
    b = {"banda": "COMPRA", "bear_severidad": "leve", "dossier_del_ciclo": True}   # sin verificación
    assert comparar_rotacion(a, b)[0] == "BLOQUEADA"


def test_rotacion_con_dossier_de_B_viejo_bloquea():
    a = {"verificacion": "PASS", "banda": "MANTENER", "bear_severidad": "media"}
    b = {"verificacion": "PASS", "banda": "COMPRA", "bear_severidad": "leve", "dossier_del_ciclo": False}
    assert comparar_rotacion(a, b)[0] == "BLOQUEADA"


def test_iesc_a_eme_bloqueada_eme_sin_dossier():
    a = {"verificacion": "REVIEW", "banda": "RECORTE", "bear_severidad": "media"}
    b = {"verificacion": "REVIEW", "banda": "MANTENER", "bear_severidad": "media",
         "nulls_portantes": ["metrica_obligatoria"], "dossier_del_ciclo": False}
    assert comparar_rotacion(a, b)[0] == "BLOQUEADA"


# ── el MÉRITO económico NO lo veta el código (corrección clave IA2) ──
def test_comparacion_valida_la_decide_el_pm_no_el_codigo():
    # misma banda, o B con mejor banda pero bear más severo: NO se veta — es válida y el PM juzga.
    a = {"verificacion": "PASS", "banda": "COMPRA", "bear_severidad": "leve", "dossier_del_ciclo": True}
    b = {"verificacion": "PASS", "banda": "COMPRA", "bear_severidad": "leve", "dossier_del_ciclo": True}
    assert comparar_rotacion(a, b)[0] == "PERMITIDA"


def test_B_mejor_retorno_con_mayor_riesgo_no_se_veta():
    # el caso power-law: B con mejor banda pero bear más severo → VÁLIDA (antes la vetaba el código). El PM decide.
    a = {"verificacion": "PASS", "banda": "MANTENER", "bear_severidad": "leve", "dossier_del_ciclo": True}
    b = {"verificacion": "PASS", "banda": "COMPRA_FUERTE", "bear_severidad": "severa", "dossier_del_ciclo": True}
    assert comparar_rotacion(a, b)[0] == "PERMITIDA"


# ── venta a caja ──
def test_venta_a_caja_valida_solo_por_razon_clara():
    assert comparar_rotacion({"banda": "RECORTE"}, {"es_caja": True})[0] == "PERMITIDA"
    assert comparar_rotacion({"banda": "MANTENER"}, {"es_caja": True})[0] == "BLOQUEADA"
    assert comparar_rotacion({"banda": "MANTENER", "flag_alta_no_opera": True}, {"es_caja": True})[0] == "PERMITIDA"


def test_venta_a_caja_con_banda_de_A_desconocida_por_review_no_se_permite():
    # REVIEW ruidoso → pierde elegibilidad → TRANSICIÓN, no venta a caja.
    a = {"banda": None, "no_elegible_tier": True, "motivo_no_elegible": "REVIEW"}
    assert comparar_rotacion(a, {"es_caja": True})[0] == "BLOQUEADA"


def test_bandas_invalidas_no_son_comparables():
    # review-2 IA1: bandas desconocidas ('foo'/'bar') daban PERMITIDA → ahora BLOQUEADA.
    assert comparar_rotacion({"banda": "foo"}, {"banda": "bar", "verificacion": "PASS", "dossier_del_ciclo": True})[0] == "BLOQUEADA"
