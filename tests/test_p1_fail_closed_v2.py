"""Tests de aceptación P1 — v2 (reemplaza a test_p1_antes_de_autoridad.py).

Principio: FAIL-CLOSED para lo que AUMENTA riesgo; para lo que lo REDUCE, un dato faltante DIFIERE (temporal),
nunca BLOQUEA (permanente) — si no, "fail-closed" en una venta significa quedar atrapado en la posición.

Cambios respecto de v1 (los marca [v1→v2]):
  - comparar_rotacion tiene 3 estados: PERMITIDA / BLOQUEADA (inválida conocida) / INDETERMINADA (falta info → DIFERIR).
  - evidencia_mecanica es un dict verificable {id, ticker, gatillado, consecuencia}, no un string cualquiera.
[SPEC] = claves nuevas del contexto que proponemos como contrato.
"""
import math

import pytest

from backend.agentes.arquetipo import clasificar_arquetipo
from backend.agentes.banda import banda_ciclica, banda_compounder, banda_infra
from backend.agentes.caps_posicion import cap_posicion
from backend.agentes.comparacion_rotacion import comparar_rotacion
from backend.agentes.evaluar_sombra import evaluar_sombra
from backend.agentes.harness_sombra import insumos_de_dossier
from backend.agentes.permiso_ejecucion import execution_permission

NAN = float("nan")
TIERS = {
    "OPTIONALITY": {"min": 0.015, "max": 0.025},
    "CORE": {"min": 0.05, "max": 0.10},
    "HIGH_CONVICTION": {"min_exclusive": 0.10, "max": 0.15},
    "EXCEPTIONAL": {"min_exclusive": 0.15, "max": 0.20},
}
CFG = {
    "tiers": TIERS,
    "cap_por_arquetipo": {"compounder": 0.15, "ciclica": 0.10, "infra": 0.10, "pre_revenue": 0.0},
    "cap_por_banda": {"COMPRA_FUERTE": 0.15, "COMPRA": 0.10, "MANTENER": 0.0, "RECORTE": 0.0},
    "cap_por_evidencia_opcionalidad": {"PASS": 0.025, "REVIEW": 0.015, "FAIL": 0.0},
}
FALSADOR_OK = {"falsador_id": "f1", "falsador_sobre_metrica": True}

# Apertura con TODOS los hechos explícitos (lo que el harness tiene que poder armar).
APERTURA_OK = {
    "accion": "abrir", "motivo_accion": "discrecional", "ticker": "XYZ",
    "verificacion": "PASS", "tier": "CORE", "tiers_cfg": TIERS, "arquetipo": "ciclica",
    "peso_objetivo": 0.05, "cap": 0.10, **FALSADOR_OK,
    "metrica_obligatoria_null": False, "flags_alta_sin_responder": False,
    "bloqueo_datos": [], "crea_stub_o_viola_ips": False,
}
# Venta a caja con TODOS los hechos explícitos.
VENTA_OK = {
    "accion": "salir", "motivo_accion": "discrecional", "ticker": "XYZ", "fondos": "caja",
    "peso_objetivo": 0.0, "tier": "CORE", "tiers_cfg": TIERS,
    "comparacion": "PERMITIDA", "metrica_A_null": False, "dossier_del_ciclo": True, "bloqueo_datos": [],
}


# ════════════════════════════════════ v1 (se mantienen) ═══════════════════════════════════════════
def test_cap_arquetipo_es_solo_de_nucleo():
    assert cap_posicion(tier="OPTIONALITY", arquetipo="pre_revenue", banda=None, verificacion="PASS", cfg=CFG)[0] == 0.025


def test_cap_banda_es_solo_dinero_nuevo_de_nucleo():
    assert cap_posicion(tier="OPTIONALITY", arquetipo="infra", banda="MANTENER", verificacion="PASS", cfg=CFG)[0] == 0.025


def test_opcionalidad_no_admite_recorte_ni_banda_desconocida_salvo_pre_revenue():
    assert cap_posicion(tier="OPTIONALITY", arquetipo="infra", banda="RECORTE", verificacion="PASS", cfg=CFG)[0] == 0.0
    assert cap_posicion(tier="OPTIONALITY", arquetipo="ciclica", banda=None, verificacion="PASS", cfg=CFG)[0] == 0.0


def test_evidencia_review_liga_en_opcionalidad():
    assert cap_posicion(tier="OPTIONALITY", arquetipo="ciclica", banda="COMPRA", verificacion="REVIEW", cfg=CFG) == (0.015, "evidencia")


@pytest.mark.parametrize("tier", ["CORE", "HIGH_CONVICTION", "EXCEPTIONAL"])
def test_banda_desconocida_en_nucleo_es_cap_cero(tier):
    assert cap_posicion(tier=tier, arquetipo="ciclica", banda=None, verificacion="PASS", cfg=CFG)[0] == 0.0


@pytest.mark.parametrize("tier", ["CORE", "HIGH_CONVICTION", "EXCEPTIONAL"])
def test_arquetipo_desconocido_en_nucleo_es_cap_cero(tier):
    assert cap_posicion(tier=tier, arquetipo=None, banda="COMPRA_FUERTE", verificacion="PASS", cfg=CFG)[0] == 0.0


def test_ninguna_combinacion_supera_15():
    for arq in [None, "compounder", "ciclica", "infra", "pre_revenue"]:
        for banda in [None, "COMPRA_FUERTE", "COMPRA", "MANTENER", "RECORTE"]:
            cap, _ = cap_posicion(tier="EXCEPTIONAL", arquetipo=arq, banda=banda, verificacion="PASS", cfg=CFG)
            assert cap <= 0.15 + 1e-9


@pytest.mark.parametrize("accion", ["aumenta", "", None, "comprar"])
def test_accion_desconocida_bloquea(accion):
    assert execution_permission({"accion": accion, "motivo_accion": "discrecional"})[0] == "BLOQUEAR"


@pytest.mark.parametrize("motivo", ["", None, "transicion_typo"])
def test_reduccion_con_motivo_desconocido_no_ejecuta_libre(motivo):
    assert execution_permission({"accion": "reducir", "motivo_accion": motivo})[0] != "EJECUTAR"


def test_salida_mecanica_sin_evidencia_no_es_mecanica():
    assert execution_permission({"accion": "salir", "motivo_accion": "falsador_duro"})[0] != "EJECUTAR"


def test_apertura_sin_verificacion_bloquea():
    assert execution_permission({"accion": "abrir", **FALSADOR_OK})[0] == "BLOQUEAR"


def test_review_no_entra_a_nucleo():
    assert execution_permission({**APERTURA_OK, "verificacion": "REVIEW"})[0] == "BLOQUEAR"


def test_peso_sobre_cap_bloquea():
    assert execution_permission({**APERTURA_OK, "peso_objetivo": 0.08, "cap": 0.0})[0] == "BLOQUEAR"


def test_venta_discrecional_sin_comparacion_difiere():
    assert execution_permission({**VENTA_OK, "comparacion": None})[0] == "DIFERIR"


def test_venta_discrecional_con_metrica_de_A_null_difiere():
    assert execution_permission({**VENTA_OK, "metrica_A_null": True})[0] == "DIFERIR"


def test_comparacion_bloqueada_bloquea_la_venta():
    assert execution_permission({**VENTA_OK, "comparacion": "BLOQUEADA"})[0] == "BLOQUEAR"


def test_rango_invertido_es_none():
    assert banda_ciclica(60, 80, 40) is None


def test_clasificador_no_depende_del_nombre_de_la_clave_revenue():
    cifr = {"contratado_firme": 14.6e9, "ev": 7.8e9, "capex": 2.0e9, "revenue_ltm": 0.27e9, "ocf_ltm": -10e6, "runway_meses": 14}
    assert clasificar_arquetipo(cifr) == "infra"


def test_capex_negativo_del_cash_flow_no_apaga_infra():
    cifr = {"contratado_firme": 14.6e9, "ev": 7.8e9, "capex": -2.0e9, "revenue": 0.27e9}
    assert clasificar_arquetipo(cifr) == "infra"


def test_infra_no_evaluable_no_cae_silenciosamente_a_pre_revenue():
    d = {"ev": 7.8e9, "capex": 2.0e9, "revenue": 0.27e9, "ocf_ltm": -10e6, "runway_meses": 14}
    assert clasificar_arquetipo(d) is None


# [v1→v2] rotación / caja con info faltante: no PERMITIDA (ahora INDETERMINADA, no BLOQUEADA)
def test_rotacion_con_banda_de_A_desconocida_no_se_permite():
    a = {"verificacion": "PASS", "banda": None}
    b = {"verificacion": "PASS", "banda": "COMPRA", "dossier_del_ciclo": True}
    assert comparar_rotacion(a, b)[0] != "PERMITIDA"


def test_rotacion_sin_verificacion_en_B_no_se_permite():
    a = {"banda": "MANTENER"}
    b = {"banda": "COMPRA", "dossier_del_ciclo": True}
    assert comparar_rotacion(a, b)[0] != "PERMITIDA"


def test_venta_a_caja_por_review_no_se_permite():
    assert comparar_rotacion({"banda": None, "no_elegible_tier": True}, {"es_caja": True})[0] != "PERMITIDA"


# ════════════════════════════════════ v2: controles positivos ═════════════════════════════════════
def test_apertura_completa_ejecuta():
    """Sin esto, 'bloquear todo' pasaría todos los tests."""
    assert execution_permission(APERTURA_OK) == ("EJECUTAR", [])


def test_venta_a_caja_completa_ejecuta():
    assert execution_permission(VENTA_OK)[0] == "EJECUTAR"


def test_salida_mecanica_con_evidencia_verificable_ejecuta():
    """[v1→v2][SPEC] evidencia = dict verificable; la consecuencia tiene que coincidir con la acción."""
    ev = {"id": "RES-1", "ticker": "XYZ", "gatillado": True, "consecuencia": "RECORTE_50"}
    ctx = {"accion": "reducir", "motivo_accion": "falsador_duro", "ticker": "XYZ", "evidencia_mecanica": ev}
    assert execution_permission(ctx)[0] == "EJECUTAR"


# ════════════════════════════════════ v2: BANDA — validar insumos ═════════════════════════════════
@pytest.mark.parametrize("precio", [0, -5, NAN, None])
def test_ciclica_precio_no_positivo_o_nan_no_da_banda(precio):
    """precio=0 (faltante rellenado) hoy da COMPRA_FUERTE → cap 15%. NaN da RECORTE → habilita vender a caja."""
    assert banda_ciclica(precio, 40, 80) is None


def test_ciclica_escala_incoherente_no_da_banda():
    """precio 95 vs rango 40.000-80.000 (otra unidad) hoy da COMPRA_FUERTE. Ratio precio/medio fuera de [0.2, 5] → None."""
    assert banda_ciclica(95, 40_000, 80_000) is None


@pytest.mark.parametrize("c", [30, True, NAN, -0.1, 4.0])
def test_infra_cobertura_fuera_de_rango_no_da_banda(c):
    """30 (=30% en porcentaje) y True hoy dan COMPRA_FUERTE. Cobertura válida: fracción finita en [0, 3]."""
    assert banda_infra(c) is None


@pytest.mark.parametrize("g,lo,hi", [(0.05, 8, 12), (NAN, 0.08, 0.12), (True, 0.08, 0.12)])
def test_compounder_unidades_incoherentes_no_dan_banda(g, lo, hi):
    """g en fracción y rango en % hoy da COMPRA_FUERTE. Todo en fracción, |x| <= 1."""
    assert banda_compounder(g, lo, hi) is None


# ════════════════════════════════════ v2: CAPS ════════════════════════════════════════════════════
def test_opcionalidad_banda_con_string_invalido_es_cero():
    assert cap_posicion(tier="OPTIONALITY", arquetipo="ciclica", banda="compra", verificacion="PASS", cfg=CFG)[0] == 0.0


# ════════════════════════════════════ v2: PERMISO — aperturas ═════════════════════════════════════
@pytest.mark.parametrize("tier,peso", [("CORE", 0.03), ("OPTIONALITY", 0.005), ("CORE", 0.0)])
def test_apertura_bajo_el_minimo_del_tier_bloquea(tier, peso):
    """[SPEC tiers_cfg] hoy CORE 3% y OPTIONALITY 0.5% dan EJECUTAR: el permiso crea stubs."""
    cap = 0.10 if tier == "CORE" else 0.025
    assert execution_permission({**APERTURA_OK, "tier": tier, "peso_objetivo": peso, "cap": cap})[0] == "BLOQUEAR"


def test_apertura_sin_tiers_cfg_bloquea():
    ctx = dict(APERTURA_OK); ctx.pop("tiers_cfg")
    assert execution_permission(ctx)[0] == "BLOQUEAR"


def test_peso_nan_bloquea():
    assert execution_permission({**APERTURA_OK, "peso_objetivo": NAN})[0] == "BLOQUEAR"


@pytest.mark.parametrize("clave", ["metrica_obligatoria_null", "flags_alta_sin_responder", "bloqueo_datos", "crea_stub_o_viola_ips"])
def test_apertura_sin_un_hecho_explicito_bloquea(clave):
    """Clave ausente = 'no se chequeó', no 'está bien'. bloqueo_datos: [] = chequeado sin bloqueos; None = no chequeado."""
    ctx = dict(APERTURA_OK); ctx.pop(clave)
    assert execution_permission(ctx)[0] == "BLOQUEAR"


def test_pre_revenue_en_opcionalidad_sin_p_implicita_bloquea():
    """[SPEC] hoy pre_revenue entra a OPTIONALITY 2.5% sin evaluar p_implícita < p_razonada."""
    ctx = {**APERTURA_OK, "tier": "OPTIONALITY", "arquetipo": "pre_revenue", "peso_objetivo": 0.025, "cap": 0.025}
    assert execution_permission(ctx)[0] == "BLOQUEAR"


def test_pre_revenue_en_opcionalidad_con_margen_ejecuta():
    ctx = {**APERTURA_OK, "tier": "OPTIONALITY", "arquetipo": "pre_revenue", "peso_objetivo": 0.025, "cap": 0.025,
           "p_implicita_alto": 0.10, "p_razonada_bajo": 0.20}
    assert execution_permission(ctx)[0] == "EJECUTAR"


def test_pre_revenue_sin_margen_bloquea():
    ctx = {**APERTURA_OK, "tier": "OPTIONALITY", "arquetipo": "pre_revenue", "peso_objetivo": 0.025, "cap": 0.025,
           "p_implicita_alto": 0.30, "p_razonada_bajo": 0.20}
    assert execution_permission(ctx)[0] == "BLOQUEAR"


# ════════════════════════════════════ v2: PERMISO — mecánica ══════════════════════════════════════
@pytest.mark.parametrize("ev", [
    "x",                                                                                   # string cualquiera
    {"id": "RES-1", "ticker": "OTRA", "gatillado": True, "consecuencia": "SALIDA"},        # otro ticker
    {"id": "RES-1", "ticker": "XYZ", "gatillado": False, "consecuencia": "SALIDA"},        # no gatilló
    {"id": "RES-1", "ticker": "XYZ", "gatillado": True, "consecuencia": "RECORTE_50"},     # RECORTE_50 no autoriza SALIR
])
def test_evidencia_mecanica_no_verificable_no_ejecuta(ev):
    ctx = {"accion": "salir", "motivo_accion": "falsador_duro", "ticker": "XYZ", "evidencia_mecanica": ev}
    assert execution_permission(ctx)[0] != "EJECUTAR"


# ════════════════════════════════════ v2: PERMISO — ventas ════════════════════════════════════════
@pytest.mark.parametrize("comp", ["permitida", "OK", "SI"])
def test_comparacion_es_enum_cerrado(comp):
    """Hoy cualquier string distinto de 'BLOQUEADA' termina en EJECUTAR."""
    assert execution_permission({**VENTA_OK, "comparacion": comp})[0] != "EJECUTAR"


def test_reduccion_que_deja_stub_se_rechaza():
    """CORE 8%→3% hoy da EJECUTAR. Decisión de ustedes: rechazar y reformular."""
    ctx = {**VENTA_OK, "accion": "reducir", "peso_objetivo": 0.03}
    assert execution_permission(ctx)[0] == "BLOQUEAR"


def test_reduccion_sin_peso_objetivo_no_ejecuta():
    ctx = dict(VENTA_OK, accion="reducir"); ctx.pop("peso_objetivo")
    assert execution_permission(ctx)[0] != "EJECUTAR"


def test_venta_sin_dossier_del_ciclo_explicito_difiere():
    ctx = dict(VENTA_OK); ctx.pop("dossier_del_ciclo")
    assert execution_permission(ctx)[0] == "DIFERIR"


def test_venta_en_rotacion_sin_estado_de_la_compra_difiere():
    """El bug del 25-nov: la venta de A sale aunque la compra de B esté bloqueada. Si fondos=<ticker>,
    par_compra_bloqueada tiene que venir explícito (el orquestador evalúa la compra ANTES que la venta)."""
    assert execution_permission({**VENTA_OK, "fondos": "EME"})[0] == "DIFERIR"
    assert execution_permission({**VENTA_OK, "fondos": "EME", "par_compra_bloqueada": True})[0] == "DIFERIR"
    assert execution_permission({**VENTA_OK, "fondos": "EME", "par_compra_bloqueada": False})[0] == "EJECUTAR"


# ════════════════════════════════════ v2: COMPARACIÓN — 3 estados ═════════════════════════════════
def test_cadena_iesc_difiere_no_bloquea():
    """A con banda desconocida vendida a caja: hoy la cadena da BLOQUEAR (permanente). Debe DIFERIR (falta info)."""
    comp, _ = comparar_rotacion({"banda": None}, {"es_caja": True})
    assert comp == "INDETERMINADA"
    assert execution_permission({**VENTA_OK, "comparacion": comp, "metrica_A_null": True})[0] == "DIFERIR"


def test_pre_revenue_que_perdio_elegibilidad_se_puede_vender_a_caja():
    """[SPEC] hoy un pre_revenue en cartera no se puede vender nunca a caja (banda siempre None)."""
    a = {"arquetipo": "pre_revenue", "banda": None, "elegible_opcionalidad": False}
    assert comparar_rotacion(a, {"es_caja": True})[0] == "PERMITIDA"


def test_pre_revenue_con_elegibilidad_desconocida_es_indeterminada():
    a = {"arquetipo": "pre_revenue", "banda": None}
    assert comparar_rotacion(a, {"es_caja": True})[0] == "INDETERMINADA"


def test_B_con_fail_es_bloqueada_no_indeterminada():
    a = {"verificacion": "PASS", "banda": "MANTENER"}
    b = {"verificacion": "FAIL", "banda": "COMPRA", "dossier_del_ciclo": True}
    assert comparar_rotacion(a, b)[0] == "BLOQUEADA"


def test_rotacion_dominada_se_bloquea():
    """B peor o igual en TODO (banda, evidencia, bear): no hay mérito posible que compensar."""
    a = {"verificacion": "PASS", "banda": "COMPRA", "bear_severidad": "media"}
    b = {"verificacion": "REVIEW", "banda": "COMPRA", "bear_severidad": "severa", "dossier_del_ciclo": True}
    assert comparar_rotacion(a, b)[0] == "BLOQUEADA"


def test_rotacion_no_dominada_queda_al_pm():
    """El caso '137% vs 25% con bear más severo': mejor banda, peor bear → válida, decide el PM."""
    a = {"verificacion": "PASS", "banda": "MANTENER", "bear_severidad": "media"}
    b = {"verificacion": "PASS", "banda": "COMPRA_FUERTE", "bear_severidad": "severa", "dossier_del_ciclo": True}
    assert comparar_rotacion(a, b)[0] == "PERMITIDA"


# ════════════════════════════════════ v2: ORQUESTADOR / HARNESS ═══════════════════════════════════
BASE_D = {"verif": "PASS", "accion": "abrir", "motivo": "discrecional", "tier_declarado": "CORE",
          "falsador_estructurado": True, "falsador_id": "f1", "falsador_sobre_metrica": True,
          "metrica_obligatoria_presente": True, "flags_alta_sin_responder": False, "bloqueo_datos": [],
          "crea_stub_o_viola_ips": False, "dossier_del_ciclo": True}


def test_override_de_arquetipo_no_agranda_el_cap():
    """Pack: E&P (cíclica, tope 10%). Analista: 'compounder' (tope 15%). Hoy: HIGH_CONVICTION 15% EJECUTAR."""
    d = {**BASE_D, "sig": {"sector": "E&P"}, "arquetipo_confirmado": "compounder", "tier_declarado": "HIGH_CONVICTION",
         "banda_in": {"g_exigido": 0.02, "g_sost_bajo": 0.08, "g_sost_alto": 0.12}, "peso_objetivo": 0.15}
    v = evaluar_sombra(d, cfg=CFG)
    assert v.cap <= 0.10 + 1e-9 and v.permiso == "BLOQUEAR"


def test_orquestador_no_lanza_excepcion_con_insumos_malformados():
    """Un string en lugar de número hoy tira TypeError: en el run real eso tumba la corrida, no solo la sombra."""
    d = {**BASE_D, "arquetipo_confirmado": "ciclica", "peso_objetivo": 0.05,
         "banda_in": {"precio": "95", "valor_mitad_ciclo_bajo": 40, "valor_mitad_ciclo_alto": 80}}
    v = evaluar_sombra(d, cfg=CFG)
    assert v.permiso == "BLOQUEAR"


def test_pre_revenue_sin_p_reporta_campos_faltantes():
    d = {**BASE_D, "arquetipo_confirmado": "pre_revenue", "tier_declarado": "OPTIONALITY", "peso_objetivo": 0.025}
    v = evaluar_sombra(d, cfg=CFG)
    assert v.permiso == "BLOQUEAR" and v.missing_fields


class _NS:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _dossier(arq="ciclica", metrica_falsador="ppa_firmado_gw", fid=None, banda_inputs=None, precio_ref=None):
    vara = _NS(metrica=metrica_falsador)
    fals = _NS(afirmacion="texto libre", vara_externa=vara, **({"id": fid} if fid else {}))
    uw = _NS(arquetipo_confirmado=arq, metrica_obligatoria_bajo=1.0, metrica_obligatoria_alto=2.0,
             banda_inputs=banda_inputs or {"precio": 95, "valor_mitad_ciclo_bajo": 100, "valor_mitad_ciclo_alto": 140},
             precio_referencia=precio_ref)
    return _NS(underwriting=uw, falsador=fals)


def test_harness_falsador_tiene_que_medir_un_insumo_del_arquetipo():
    """El falsador de VST sobre el PPA (la 'opción gratis') hoy pasa como ligado a la métrica de una cíclica."""
    d = insumos_de_dossier(_dossier(metrica_falsador="ppa_firmado_gw", fid="F1"), verif="PASS", accion="aumentar")
    assert d["falsador_sobre_metrica"] is False
    d = insumos_de_dossier(_dossier(metrica_falsador="fcf_a_curva", fid="F1"), verif="PASS", accion="aumentar")
    assert d["falsador_sobre_metrica"] is True


def test_harness_falsador_id_no_es_el_texto_libre():
    d = insumos_de_dossier(_dossier(metrica_falsador="fcf_a_curva", fid=None), verif="PASS", accion="aumentar")
    assert d["falsador_id"] is None
    d = insumos_de_dossier(_dossier(metrica_falsador="fcf_a_curva", fid="F-VST-1"), verif="PASS", accion="aumentar")
    assert d["falsador_id"] == "F-VST-1"


def test_harness_el_precio_de_la_banda_es_el_del_pack():
    """[SPEC precio_pack] la banda se recalcula con el precio del día, no con el que escribió el Analista."""
    d = insumos_de_dossier(_dossier(fid="F1"), verif="PASS", accion="aumentar", precio_pack=120)
    assert d["banda_in"]["precio"] == 120
    d = insumos_de_dossier(_dossier(fid="F1"), verif="PASS", accion="aumentar")
    assert d["banda_in"].get("precio") is None


def test_harness_descarta_insumos_dependientes_del_precio_si_el_precio_se_movio():
    """g_exigido / cobertura / p_implícita dependen del precio. Si el precio se movió >10% desde que el Analista
    los escribió (precio_referencia), no se usan: hay que recalcularlos."""
    bi = {"g_exigido": 0.02, "g_sost_bajo": 0.08, "g_sost_alto": 0.12}
    d = insumos_de_dossier(_dossier(arq="compounder", fid="F1", banda_inputs=bi, precio_ref=100),
                           verif="PASS", accion="aumentar", precio_pack=130)
    assert d["banda_in"].get("g_exigido") is None
    d = insumos_de_dossier(_dossier(arq="compounder", fid="F1", banda_inputs=bi, precio_ref=100),
                           verif="PASS", accion="aumentar", precio_pack=104)
    assert d["banda_in"].get("g_exigido") == 0.02


def test_clasificador_no_lanza_con_sector_no_string():
    assert clasificar_arquetipo({"sector": 7}) is None
