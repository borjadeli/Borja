"""Tests del agente PM (v2 Fase 4, doc 55). Sin API — ScriptedLLM + IPS inyectado."""
import json

from backend.agentes.base import Agente, FakeUsage, ScriptedLLM, resp_sin_emitir, resp_tool
from backend.agentes.ips import IPS, ContextoTicker
from backend.agentes.pm import PM
from backend.agentes.schemas import (
    AgentMeta,
    Dossier,
    Escenario,
    Falsador,
    VerificationReport,
)

_U = FakeUsage(input_tokens=1000, output_tokens=200)


def _ips(**over):
    cfg = {"max_posiciones": 12, "peso_max_nombre": 0.20, "max_por_sector": 0.30, "max_por_cuello": 0.35,
           "caja_min": 0.0, "caja_max": 1.0, "max_ops_semana": 2, "market_cap_min_usd": 150e6,
           "market_cap_max_usd": 60e9, "adv_min_usd": 3e6, "cap_flag_supervivencia": 0.04}
    cfg.update(over)
    return IPS(cfg)


def _esc(t="t"):
    return Escenario(tesis=t, supuestos=["a"], contraste_con_calculadoras="c")


def _dossier(ticker="OKLO", conv=0.7):
    meta = AgentMeta(agent="analista", prompt_version="v1", model="claude-opus-5-5")
    return Dossier(meta=meta, ticker=ticker, negocio_y_posicion_cuello="SMR",
                   valuacion_que_exige_el_precio="exige 40% CAGR", bull=_esc("bull"), bear=_esc("bear"),
                   falsador=Falsador(afirmacion="pierde offtake", fecha_limite="2027-01-01", que_lo_mataria="x"),
                   conviccion_0_1=conv)


def _verif(ticker="OKLO", veredicto="pass", flags=None):
    return VerificationReport(meta=AgentMeta(agent="verificador", prompt_version="v1", model="claude-sonnet-5-5"),
                              ticker=ticker, veredicto=veredicto, flags_supervivencia=flags or [])


def _accion_payload(ticker="OKLO", peso=0.1, conv=0.7):
    return {"ticker": ticker, "accion": "comprar", "peso_objetivo": peso, "conviccion_0_1": conv,
            "por_que_ese_tamano": "convicción media", "tesis": "SMRs con offtake",
            "falsador": {"afirmacion": "pierde contrato", "fecha_limite": "2027-01-01", "que_lo_mataria": "x"},
            "que_me_haria_vender": "dilución"}


def _decision_payload(acciones):
    return {"acciones": acciones, "respuestas_flags": [], "operar_ahora": True, "razon_timing": "evento"}


def _pm(respuestas, ips=None):
    ag = Agente("pm", "pm_v1", "claude-opus-5-5", cliente=ScriptedLLM(respuestas))
    return PM(ag, ips or _ips())


def _ctx():
    return {"OKLO": ContextoTicker(sector="energia", cuello="smr", market_cap=5e9, adv_usd=10e6)}


def test_pm_usa_dryrun_y_emite():
    cli_resps = [
        resp_tool("validar_ips", {"pesos": {"OKLO": 0.1}, "ops_semana": 1}, _U),
        resp_tool("emitir_decision", _decision_payload([_accion_payload()]), _U),
    ]
    pm = _pm(cli_resps)
    dec = pm.decidir(dossiers=[(_dossier(), _verif())], cartera_actual={}, caja_actual=1.0, contexto=_ctx())
    assert dec.operar_ahora is True and len(dec.acciones) == 1
    assert dec.acciones[0].ticker == "OKLO" and dec.acciones[0].peso_objetivo == 0.1
    # el dry-run corrió: hubo 2 llamadas y la 2a lleva un tool_result en los mensajes
    cli = pm.ag._cliente
    assert len(cli.llamadas) == 2
    bloques = [b for m in cli.llamadas[1]["messages"] if isinstance(m["content"], list) for b in m["content"]]
    assert any(isinstance(b, dict) and b.get("type") == "tool_result" for b in bloques)


def test_pm_clampa_peso_fuera_de_rango():
    resps = [resp_tool("emitir_decision", _decision_payload([_accion_payload(peso=1.5, conv=2.0)]), _U)]
    dec = _pm(resps).decidir(dossiers=[(_dossier(), _verif())], cartera_actual={}, caja_actual=1.0, contexto=_ctx())
    assert dec.acciones[0].peso_objetivo == 1.0 and dec.acciones[0].conviccion_0_1 == 1.0


def test_pm_no_emite_devuelve_noaction():
    # no emite ni tras el empujón (2 respuestas sin tool) → NO_ACTION explícito
    resps = [resp_sin_emitir(_U), resp_sin_emitir(_U)]
    dec = _pm(resps).decidir(dossiers=[(_dossier(), _verif())], cartera_actual={}, caja_actual=1.0, contexto=_ctx())
    assert dec.operar_ahora is False and dec.acciones == []


def test_dryrun_handler_detecta_violacion_de_cap():
    pm = _pm([])                      # no se llama al LLM; se testea el handler directo
    handler = pm._handler_validar(_ctx(), 0)
    out = json.loads(handler({"pesos": {"OKLO": 0.25}, "ops_semana": 0}))
    assert out["admisible"] is False
    assert any(v["regla"] == "peso_max_nombre" and v["tipo"] == "local_simple" for v in out["violaciones"])
    assert abs(out["caja_resultante"] - 0.75) < 1e-9


def test_dryrun_handler_cartera_limpia():
    pm = _pm([])
    out = json.loads(pm._handler_validar(_ctx(), 0)({"pesos": {"OKLO": 0.1}}))
    assert out["admisible"] is True and out["violaciones"] == []


def test_flags_supervivencia_van_al_prompt():
    resps = [resp_tool("emitir_decision", _decision_payload([_accion_payload()]), _U)]
    pm = _pm(resps)
    pm.decidir(dossiers=[(_dossier(), _verif(flags=["material_weakness"]))],
               cartera_actual={}, caja_actual=1.0, contexto=_ctx())
    user_msg = pm.ag._cliente.llamadas[0]["messages"][0]["content"]
    assert "OKLO:material_weakness" in user_msg


def test_r2_feedback_y_alertas_previas_en_el_prompt():
    resps = [resp_tool("emitir_decision", _decision_payload([_accion_payload()]), _U)]
    pm = _pm(resps)
    pm.decidir(dossiers=[(_dossier(), _verif())], cartera_actual={}, caja_actual=1.0, contexto=_ctx(),
               alertas_previas=["OKLO: inadmisible"], feedback="max_por_sector: energia 40% > 30%")
    msg = pm.ag._cliente.llamadas[0]["messages"][0]["content"]
    assert "OKLO: inadmisible" in msg and "RECHAZÓ TU PROPUESTA" in msg and "max_por_sector" in msg


def test_r2_dryrun_usa_ops_del_ledger_no_del_input():
    # ops_previas=2 + 1 propuesta = 3 > max_ops 2 → viola; ignora el ops_semana=0 del input del PM
    pm = _pm([], ips=_ips(max_ops_semana=2))
    out = json.loads(pm._handler_validar(_ctx(), 2)({"pesos": {"OKLO": 0.1}, "ops_semana": 0}))
    assert any(v["regla"] == "max_ops_semana" for v in out["violaciones"])
