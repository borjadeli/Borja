"""P1 (doc 91 §8) — orquestador en sombra (fail-closed, encadena los 6 módulos). Determinista."""
from backend.agentes.evaluar_sombra import evaluar_sombra

_CFG = {"tiers": {"OPTIONALITY": {"min": 0.015, "max": 0.025}, "CORE": {"min": 0.05, "max": 0.10}},
        "cap_por_arquetipo": {"compounder": 0.15, "ciclica": 0.10, "infra": 0.10, "pre_revenue": 0.0},
        "cap_por_banda": {"COMPRA_FUERTE": 0.15, "COMPRA": 0.10, "MANTENER": 0.0, "RECORTE": 0.0},
        "cap_por_evidencia_opcionalidad": {"PASS": 0.025, "REVIEW": 0.015, "FAIL": 0.0}}


def test_apertura_con_dossier_historico_incompleto_bloquea():
    # sin banda/falsador/métrica estructurados (histórico) → fail-closed → BLOQUEAR + los lista en missing_fields.
    d = {"sig": {"sector": "E&P", "revenue_ltm": 7e9}, "verif": "PASS", "accion": "abrir",
         "motivo": "discrecional", "peso_objetivo": 0.07}
    r = evaluar_sombra(d, cfg=_CFG)
    assert r.arquetipo == "ciclica" and r.permiso == "BLOQUEAR"
    assert "banda (rango de valuación del dossier)" in r.missing_fields


def test_apertura_con_todos_los_campos_ejecuta():
    # con el schema completo (lo que proveerá el harness real): arquetipo+banda+métrica+falsador → se puede autorizar.
    d = {"sig": {"sector": "E&P", "revenue_ltm": 7e9}, "verif": "PASS", "accion": "abrir", "motivo": "discrecional",
         "banda_in": {"precio": 30, "valor_mitad_ciclo_bajo": 40, "valor_mitad_ciclo_alto": 80},   # COMPRA_FUERTE
         "tier_declarado": "CORE", "peso_objetivo": 0.07, "metrica_obligatoria_presente": True,
         "falsador_estructurado": True, "falsador_id": "f1", "falsador_sobre_metrica": True}
    r = evaluar_sombra(d, cfg=_CFG)
    assert r.arquetipo == "ciclica" and r.banda == "COMPRA_FUERTE" and r.cap == 0.10 and r.permiso == "EJECUTAR"
    assert r.missing_fields == []


def test_mantener_no_necesita_gates():
    r = evaluar_sombra({"sig": {}, "verif": "REVIEW", "accion": "mantener", "motivo": "discrecional"}, cfg=_CFG)
    assert r.permiso == "EJECUTAR"
