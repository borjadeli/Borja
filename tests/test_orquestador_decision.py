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
    RespuestaFlag,
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


def _decision(acciones, *, operar=True, respuestas_flags=None):
    return PMDecision(meta=AgentMeta(agent="pm", prompt_version="pm_v1", model="claude-opus-5-5"),
                      acciones=acciones, operar_ahora=operar,
                      respuestas_flags=respuestas_flags or [], razon_timing="evento")


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


# --------------------------------------------------------------------------- regresión P0.1 (auditoría)
from datetime import date  # noqa: E402


def _orq_ips(tmp_path, ips, auditor=None):
    return OrquestadorDecision(ips, LedgerDecisiones(path=tmp_path / "ld.jsonl"), auditor=auditor)


def test_1a_tenencia_inadmisible_no_se_vende_a_la_fuerza(tmp_path):
    # OKLO cruzó $60B; el PM dice mantener → NO se vende, solo alerta (doc 55: admisibilidad no reduce).
    ctx = _ctx(OKLO=ContextoTicker(sector="energia", cuello="smr", market_cap=70e9, adv_usd=10e6))
    res = _orq_ips(tmp_path, _ips()).procesar(_decision([_accion("OKLO", 0.10, "mantener")]),
                                              cartera_actual={"OKLO": 0.10}, caja_actual=0.90,
                                              contexto=ctx, ciclo="c")
    assert res.pesos_finales == {"OKLO": 0.10} and res.no_action is False
    assert any("inadmisible" in a for a in res.alertas)


def test_1a_no_abre_nombre_inadmisible(tmp_path):
    ctx = _ctx(OKLO=ContextoTicker(sector="energia", market_cap=70e9, adv_usd=10e6))
    res = _orq_ips(tmp_path, _ips()).procesar(_decision([_accion("OKLO", 0.10, "comprar")]),
                                              cartera_actual={}, caja_actual=1.0, contexto=ctx, ciclo="c")
    assert res.pesos_finales == {} and any("inadmisible" in a for a in res.alertas)


def test_1b_violacion_agregada_preexistente_no_bloquea_la_venta(tmp_path):
    # A/B/C mismo sector (0.6 > cap 0.3, preexistente). El PM vende C → la venta se ejecuta igual.
    res = _orq_ips(tmp_path, _ips()).procesar(_decision([_accion("C", 0.0, "vender")]),
                                              cartera_actual={"A": 0.2, "B": 0.2, "C": 0.2}, caja_actual=0.4,
                                              contexto=_ctx(A=_ctx()["OKLO"], B=_ctx()["OKLO"], C=_ctx()["OKLO"]),
                                              ciclo="c")
    assert res.no_action is False and res.pesos_finales == {"A": 0.2, "B": 0.2}


def test_1c_drift_dentro_de_banda_no_se_recorta(tmp_path):
    # posición derivó a 22% (cap 20%, banda 3pp) → NO se recorta.
    res = _orq_ips(tmp_path, _ips()).procesar(_decision([]), cartera_actual={"OKLO": 0.22}, caja_actual=0.78,
                                              contexto=_ctx(), ciclo="c")
    assert res.pesos_finales == {"OKLO": 0.22} and res.clip == "none"


def test_1c_drift_fuera_de_banda_se_recorta_al_cap(tmp_path):
    res = _orq_ips(tmp_path, _ips()).procesar(_decision([]), cartera_actual={"OKLO": 0.25}, caja_actual=0.75,
                                              contexto=_ctx(), ciclo="c")
    assert res.pesos_finales == {"OKLO": 0.20} and res.clip == "local_simple"


def test_1d_operar_ahora_false_no_ejecuta(tmp_path):
    res = _orq_ips(tmp_path, _ips()).procesar(_decision([_accion("OKLO", 0.10, "comprar")], operar=False),
                                              cartera_actual={}, caja_actual=1.0, contexto=_ctx(), ciclo="c")
    assert res.pesos_finales == {} and any("no opera" in a.lower() for a in res.alertas)


def test_1e_max_ops_semana_cuenta_SESIONES_por_calendario(tmp_path):
    orq = _orq_ips(tmp_path, _ips(max_ops_semana=2))
    orq.ledger.registrar_decision(_accion("X"), ciclo="c1")   # 2 SESIONES con ops ejecutadas esta semana
    orq.ledger.registrar_decision(_accion("Y"), ciclo="c2")
    res = orq.procesar(_decision([_accion("OKLO", 0.10, "comprar")]), cartera_actual={}, caja_actual=1.0,
                       contexto=_ctx(), ciclo="c3", hoy=date.today())
    assert res.no_action is True and res.pesos_finales == {}   # 2+1 sesiones > 2 → el aumento se cae


def test_1f_turnover_max_bloquea_rotacion(tmp_path):
    # ROTACIÓN: vender A 0.30 (otro sector) y comprar OKLO+MP 0.15 c/u (energia 0.30 = cap) → rotación 0.30 > 0.25
    ctx = _ctx(A=ContextoTicker(sector="defensa", cuello="x", market_cap=8e9, adv_usd=10e6))
    res = _orq_ips(tmp_path, _ips(turnover_max_semana=0.25)).procesar(
        _decision([_accion("A", 0.0, "vender"), _accion("OKLO", 0.15, "comprar"), _accion("MP", 0.15, "comprar")]),
        cartera_actual={"A": 0.30}, caja_actual=0.70, contexto=ctx, ciclo="c")
    assert res.no_action is True and "A" not in res.pesos_finales   # A se vendió; los aumentos cayeron


def test_1f_cap_flag_supervivencia_no_resuelto_topea_el_aumento(tmp_path):
    orq = _orq_ips(tmp_path, _ips())
    res = orq.procesar(_decision([_accion("OKLO", 0.15, "comprar")]), cartera_actual={}, caja_actual=1.0,
                       contexto=_ctx(), ciclo="c", flags_por_ticker={"OKLO": ["material_weakness"]})
    assert res.pesos_finales == {"OKLO": 0.04} and res.clip == "local_simple"


def test_1f_cap_flag_resuelto_no_topea(tmp_path):
    orq = _orq_ips(tmp_path, _ips())
    resp = [RespuestaFlag(flag_id="OKLO:material_weakness", accion="acepta", motivo="falsador fechado")]
    res = orq.procesar(_decision([_accion("OKLO", 0.15, "comprar")], respuestas_flags=resp),
                       cartera_actual={}, caja_actual=1.0, contexto=_ctx(), ciclo="c",
                       flags_por_ticker={"OKLO": ["material_weakness"]})
    assert res.pesos_finales == {"OKLO": 0.15} and res.clip == "none"


# --------------------------------------------------------------------------- regresión P0 r2 (auditoría)
_EN = dict(market_cap=5e9, adv_usd=10e6)


def test_r2_1a_cinco_compras_una_sesion_no_excede_max_ops(tmp_path):
    ctx = {t: ContextoTicker(sector=f"s{i}", **_EN) for i, t in enumerate("ABCDE")}
    res = _orq_ips(tmp_path, _ips(max_ops_semana=2)).procesar(
        _decision([_accion(t, 0.05, "comprar") for t in "ABCDE"]),
        cartera_actual={}, caja_actual=1.0, contexto=ctx, ciclo="c")
    assert res.no_action is False and len(res.pesos_finales) == 5   # 1 sesión ≤ 2


def test_r2_1b_despliegue_desde_caja_no_es_turnover(tmp_path):
    ctx = _ctx(MP=ContextoTicker(sector="commodities", cuello="x", **_EN))
    res = _orq_ips(tmp_path, _ips(turnover_max_semana=0.25)).procesar(
        _decision([_accion("OKLO", 0.15, "comprar"), _accion("MP", 0.15, "comprar")]),
        cartera_actual={}, caja_actual=1.0, contexto=ctx, ciclo="c")
    assert res.no_action is False and res.pesos_finales == {"OKLO": 0.15, "MP": 0.15}


def test_r2_1c_agregado_de_grupo_no_bloquea_otro_sector(tmp_path):
    ctx = {"A": ContextoTicker(sector="energia", **_EN), "B": ContextoTicker(sector="energia", **_EN),
           "C": ContextoTicker(sector="energia", **_EN), "D": ContextoTicker(sector="commodities", **_EN)}
    res = _orq_ips(tmp_path, _ips()).procesar(_decision([_accion("D", 0.10, "comprar")]),
                                              cartera_actual={"A": 0.2, "B": 0.2, "C": 0.2}, caja_actual=0.4,
                                              contexto=ctx, ciclo="c")
    assert res.no_action is False and res.pesos_finales.get("D") == 0.10   # energia excedido no frena a D


def test_r2_1d_repropuesta_una_vez_con_holguras(tmp_path):
    orq = _orq_ips(tmp_path, _ips())
    llamadas = []

    def repro(holguras):
        llamadas.append(holguras)
        return _decision([_accion("OKLO", 0.15, "comprar"), _accion("MP", 0.15, "comprar")])

    res = orq.procesar(_decision([_accion("OKLO", 0.2, "comprar"), _accion("MP", 0.2, "comprar")]),
                       cartera_actual={}, caja_actual=1.0, contexto=_ctx(), ciclo="c", repropuesta_fn=repro)
    assert len(llamadas) == 1 and any(h.regla == "max_por_sector" for h in llamadas[0])
    assert res.no_action is False and res.pesos_finales == {"OKLO": 0.15, "MP": 0.15}


def test_r2_6_operar_ahora_false_no_llama_al_auditor(tmp_path):
    aud = _FakeAuditor([AuditObjecion(tipo="concentracion", detalle="x", severidad="alta")])
    res = _orq_ips(tmp_path, _ips(), auditor=aud).procesar(
        _decision([_accion("OKLO", 0.1, "comprar")], operar=False),
        cartera_actual={}, caja_actual=1.0, contexto=_ctx(), ciclo="c")
    assert res.auditoria is None and res.demoradas == []
