"""Tests del orquestador de decisión (v2 Fase 4, doc 55 §4). Sin API — auditor stub + ledger en tmp."""
from backend.agentes.ips import IPS, ContextoTicker
from backend.agentes.ledger_decisiones import LedgerDecisiones
from backend.agentes.orquestador_decision import OrquestadorDecision, aplicar_decision
from backend.agentes.schemas import (
    AgentMeta,
    AuditObjecion,
    AuditReport,
    Falsador,
    PMAccion,
    PMDecision,
)


def _ips(**over):
    cfg = {"max_posiciones": 12, "peso_max_nombre": 0.20, "max_por_sector": 0.30, "max_por_cuello": 0.35,
           "caja_min": 0.0, "caja_max": 1.0, "max_ops_semana": 9, "market_cap_min_usd": 150e6,
           "market_cap_max_usd": 60e9, "adv_min_usd": 3e6, "cap_flag_supervivencia": 0.04}
    cfg.update(over)
    return IPS(cfg)


def _accion(ticker="OKLO", peso=0.1, accion="comprar"):
    return PMAccion(ticker=ticker, accion=accion, peso_objetivo=peso, conviccion_0_1=0.7,
                    por_que_ese_tamano="x", tesis="t",
                    falsador=Falsador(afirmacion="a", fecha_limite="2027-01-01", que_lo_mataria="b"),
                    que_me_haria_vender="c")


def _decision(acciones):
    return PMDecision(meta=AgentMeta(agent="pm", prompt_version="pm_v1", model="claude-opus-5-5"),
                      acciones=acciones, operar_ahora=True, razon_timing="evento")


def _ctx(**over):
    base = {"OKLO": ContextoTicker(sector="energia", cuello="smr", market_cap=5e9, adv_usd=10e6),
            "MP": ContextoTicker(sector="energia", cuello="tierras_raras", market_cap=8e9, adv_usd=10e6)}
    base.update(over)
    return base


class _FakeAuditor:
    def __init__(self, objeciones=None):
        self._rep = AuditReport(meta=AgentMeta(agent="auditor", prompt_version="auditor_v1",
                                               model="claude-opus-5-5"),
                                objeciones=objeciones or [], devuelve_al_pm=bool(objeciones))

    def auditar(self, *a, **k):
        return self._rep


def _orq(tmp_path, auditor=None):
    return OrquestadorDecision(_ips(), LedgerDecisiones(path=tmp_path / "ld.jsonl"), auditor=auditor)


def test_aplicar_decision_fija_objetivo_y_saca_ventas():
    pesos = aplicar_decision({"MP": 0.1, "SMR": 0.05}, [_accion("OKLO", 0.1), _accion("MP", 0.0, "vender")])
    assert pesos == {"SMR": 0.05, "OKLO": 0.1}       # MP vendida, OKLO abierta, SMR intacta


def test_decision_limpia_clip_none(tmp_path):
    res = _orq(tmp_path).procesar(_decision([_accion("OKLO", 0.1)]), cartera_actual={}, caja_actual=1.0,
                                  contexto=_ctx(), ciclo="2026-10-27")
    assert res.clip == "none" and res.no_action is False
    assert res.pesos_finales == {"OKLO": 0.1} and abs(res.caja_final - 0.9) < 1e-9


def test_local_simple_recorta_a_cap_sin_redistribuir(tmp_path):
    res = _orq(tmp_path).procesar(_decision([_accion("OKLO", 0.30)]), cartera_actual={}, caja_actual=1.0,
                                  contexto=_ctx(), ciclo="c")
    assert res.clip == "local_simple" and res.no_action is False
    assert res.pesos_finales == {"OKLO": 0.20}        # recortado al cap
    assert abs(res.caja_final - 0.80) < 1e-9          # el excedente fue a cash


def test_violacion_agregada_es_no_action(tmp_path):
    # dos nombres del mismo sector (energia) 0.2+0.2=0.4 > cap sector 0.30 → agregada → NO_ACTION
    cartera = {"SMR": 0.5}
    res = _orq(tmp_path).procesar(_decision([_accion("OKLO", 0.2), _accion("MP", 0.2)]),
                                  cartera_actual=cartera, caja_actual=0.5, contexto=_ctx(), ciclo="c")
    assert res.no_action is True and res.clip == "agregada"
    assert res.pesos_finales == {"SMR": 0.5} and res.caja_final == 0.5   # cartera sin cambios


def test_objecion_alta_demora_aumentos(tmp_path):
    aud = _FakeAuditor([AuditObjecion(tipo="concentracion", detalle="1 apuesta macro", severidad="alta")])
    res = _orq(tmp_path, auditor=aud).procesar(
        _decision([_accion("OKLO", 0.1, "comprar"), _accion("MP", 0.0, "vender")]),
        cartera_actual={"MP": 0.1}, caja_actual=0.9, contexto=_ctx(), ciclo="c")
    assert res.demoradas == ["OKLO"]                  # el aumento se demora; la venta NO
    assert res.auditoria is not None and res.auditoria.devuelve_al_pm is True


def test_ledger_registra_hash_y_procedencia(tmp_path):
    orq = _orq(tmp_path)
    orq.procesar(_decision([_accion("OKLO", 0.1)]), cartera_actual={}, caja_actual=1.0, contexto=_ctx(),
                 ciclo="2026-10-27", precios={"OKLO": 42.0},
                 dossier_hash_por_ticker={"OKLO": "deadbeef"}, verif_por_ticker={"OKLO": "pass"})
    ds = orq.ledger.decisiones()
    assert len(ds) == 1
    d = ds[0]
    assert d.dossier_hash == "deadbeef" and d.precio == 42.0 and d.verif_veredicto == "pass"
    assert d.ips_hash == orq.ips.hash() and d.peso_resultante == 0.1 and d.ciclo == "2026-10-27"
