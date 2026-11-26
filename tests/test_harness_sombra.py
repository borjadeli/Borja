"""P1 (doc 91 §8) — harness: mapeo Dossier→orquestador, consumiendo el bloque económico estructurado. Determinista."""
from types import SimpleNamespace

from backend.agentes.harness_sombra import evaluar_decision_sombra, insumos_de_dossier
from backend.agentes.schemas import Underwriting

_CFG = {"tiers": {"OPTIONALITY": {"min": 0.015, "max": 0.025}, "CORE": {"min": 0.05, "max": 0.10}},
        "cap_por_arquetipo": {"compounder": 0.15, "ciclica": 0.10, "infra": 0.10, "pre_revenue": 0.0},
        "cap_por_banda": {"COMPRA_FUERTE": 0.15, "COMPRA": 0.10, "MANTENER": 0.0, "RECORTE": 0.0},
        "cap_por_evidencia_opcionalidad": {"PASS": 0.025, "REVIEW": 0.015, "FAIL": 0.0}}


def _dossier(uw=None, con_vara=True):
    vara = SimpleNamespace(metrica="normalized_owner_fcf_per_share") if con_vara else None
    fals = SimpleNamespace(afirmacion="HH<3 en 12m", vara_externa=vara)
    return SimpleNamespace(falsador=fals, underwriting=uw)


def test_dossier_completo_se_puede_autorizar():
    # el Analista confirmó arquetipo + métrica + rango de banda → el harness lo consume → EJECUTAR.
    uw = Underwriting(arquetipo_confirmado="ciclica", metrica_obligatoria_bajo=1.8e9, metrica_obligatoria_alto=2.2e9,
                      banda_inputs={"precio": 30, "valor_mitad_ciclo_bajo": 40, "valor_mitad_ciclo_alto": 80},
                      status="COMPLETE")
    r = evaluar_decision_sombra(_dossier(uw), cfg=_CFG, verif="PASS", accion="abrir",
                                peso_objetivo=0.07, tier_declarado="CORE")
    assert r.arquetipo == "ciclica" and r.banda == "COMPRA_FUERTE" and r.permiso == "EJECUTAR" and r.missing_fields == []


def test_dossier_legacy_sin_underwriting_es_fail_closed():
    # sin bloque económico → métrica ausente + sin rango → apertura BLOQUEAR + missing_fields.
    r = evaluar_decision_sombra(_dossier(None), cfg=_CFG, verif="PASS", accion="abrir",
                                peso_objetivo=0.07, tier_declarado="CORE", sig_pack={"sector": "E&P", "revenue_ltm": 7e9})
    assert r.permiso == "BLOQUEAR"
    assert "métrica obligatoria del arquetipo" in r.missing_fields


def test_mapeo_usa_arquetipo_confirmado_sobre_las_senales_del_pack():
    uw = Underwriting(arquetipo_confirmado="compounder", status="INCOMPLETE")
    d = insumos_de_dossier(_dossier(uw), verif="PASS", accion="mantener", sig_pack={"sector": "E&P"})
    assert d["arquetipo_confirmado"] == "compounder"       # gana el confirmado, no la señal cíclica del pack


def test_underwriting_es_opcional_en_dossier():
    # backward-compat: un Dossier sin el bloque sigue siendo válido (campo None).
    from backend.agentes.schemas import Underwriting as U
    assert U().status == "INCOMPLETE" and U().arquetipo_confirmado is None
