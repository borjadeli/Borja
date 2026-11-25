"""P1 (doc 91 §8) — execution_permission FAIL-CLOSED (tests de aceptación de IA1). Determinista, sin LLM.
El módulo computa desde HECHOS CRUDOS; un dato faltante/desconocido nunca habilita la transacción."""
import pytest

from backend.agentes.permiso_ejecucion import execution_permission

FALSADOR_OK = {"falsador_id": "f1", "falsador_sobre_metrica": True}


# ── enums cerrados ──
@pytest.mark.parametrize("accion", ["aumenta", "", None, "comprar"])
def test_accion_desconocida_bloquea(accion):
    assert execution_permission({"accion": accion, "motivo_accion": "discrecional"})[0] == "BLOQUEAR"


@pytest.mark.parametrize("motivo", ["", None, "transicion_typo", "Discrecional "])
def test_reduccion_con_motivo_desconocido_no_ejecuta_libre(motivo):
    assert execution_permission({"accion": "reducir", "motivo_accion": motivo})[0] != "EJECUTAR"


# ── lo mecánico se prueba, no se declara ──
def test_salida_mecanica_sin_evidencia_no_es_mecanica():
    assert execution_permission({"accion": "salir", "motivo_accion": "falsador_duro"})[0] != "EJECUTAR"


def test_salida_mecanica_con_evidencia_ejecuta():
    ctx = {"accion": "salir", "motivo_accion": "falsador_duro", "evidencia_mecanica": "RES-VST-2027-12-31"}
    assert execution_permission(ctx)[0] == "EJECUTAR"


def test_salida_mecanica_con_datos_de_ejecucion_inseguros_bloquea():
    ctx = {"accion": "salir", "motivo_accion": "falsador_duro", "evidencia_mecanica": "RES-1", "ejecucion_insegura": True}
    assert execution_permission(ctx)[0] == "BLOQUEAR"


# ── aperturas fail-closed ──
def test_apertura_sin_verificacion_bloquea():
    assert execution_permission({"accion": "abrir", **FALSADOR_OK})[0] == "BLOQUEAR"


def test_apertura_con_fail_bloquea():
    ctx = {"accion": "abrir", "verificacion": "FAIL", "tier": "CORE", "peso_objetivo": 0.05, "cap": 0.10, **FALSADOR_OK}
    assert execution_permission(ctx)[0] == "BLOQUEAR"


def test_review_no_entra_a_nucleo():
    ctx = {"accion": "abrir", "verificacion": "REVIEW", "tier": "CORE", "peso_objetivo": 0.05, "cap": 0.10, **FALSADOR_OK}
    assert execution_permission(ctx)[0] == "BLOQUEAR"


def test_peso_sobre_cap_bloquea_calculado_por_el_modulo():
    ctx = {"accion": "aumentar", "verificacion": "PASS", "tier": "CORE", "peso_objetivo": 0.08, "cap": 0.0, **FALSADOR_OK}
    assert execution_permission(ctx)[0] == "BLOQUEAR"


def test_apertura_limpia_ejecuta():
    ctx = {"accion": "abrir", "verificacion": "PASS", "tier": "CORE", "peso_objetivo": 0.07, "cap": 0.10, **FALSADOR_OK}
    assert execution_permission(ctx)[0] == "EJECUTAR"


def test_apertura_sin_cap_bloquea():
    # fail-closed: sin cap computado no se abre, aunque el resto esté bien.
    ctx = {"accion": "abrir", "verificacion": "PASS", "tier": "CORE", "peso_objetivo": 0.07, **FALSADOR_OK}
    assert execution_permission(ctx)[0] == "BLOQUEAR"


# ── ventas discrecionales ──
def test_venta_discrecional_sin_comparacion_difiere():
    assert execution_permission({"accion": "salir", "motivo_accion": "discrecional", "verificacion": "PASS"})[0] == "DIFERIR"


def test_venta_discrecional_con_metrica_de_A_null_difiere():
    ctx = {"accion": "salir", "motivo_accion": "discrecional", "comparacion": "PERMITIDA", "metrica_A_null": True}
    assert execution_permission(ctx)[0] == "DIFERIR"


def test_comparacion_bloqueada_bloquea_la_venta():
    ctx = {"accion": "salir", "motivo_accion": "discrecional", "comparacion": "BLOQUEADA", "metrica_A_null": False}
    assert execution_permission(ctx)[0] == "BLOQUEAR"


def test_venta_discrecional_valida_ejecuta():
    ctx = {"accion": "salir", "motivo_accion": "discrecional", "comparacion": "PERMITIDA", "metrica_A_null": False,
           "dossier_del_ciclo": True}
    assert execution_permission(ctx)[0] == "EJECUTAR"
