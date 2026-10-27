"""Tests del agente Auditor (v2 Fase 4, doc 55). Sin API — ScriptedLLM + salida estructurada."""
import json

from backend.agentes.auditor import Auditor
from backend.agentes.base import Agente, FakeUsage, ScriptedLLM
from backend.agentes.ips import Violacion
from backend.agentes.schemas import AgentMeta, Falsador, PMAccion, PMDecision

_U = FakeUsage(input_tokens=800, output_tokens=150)


def _decision(acciones=None, operar=True):
    return PMDecision(meta=AgentMeta(agent="pm", prompt_version="pm_v1", model="claude-opus-5-5"),
                      acciones=acciones or [], operar_ahora=operar, razon_timing="evento")


def _accion(ticker="OKLO", peso=0.1, conv=0.7):
    return PMAccion(ticker=ticker, accion="comprar", peso_objetivo=peso, conviccion_0_1=conv,
                    por_que_ese_tamano="x", tesis="SMRs con offtake",
                    falsador=Falsador(afirmacion="a", fecha_limite="2027-01-01", que_lo_mataria="b"),
                    que_me_haria_vender="dilución")


def _auditor(payload):
    cli = ScriptedLLM([(json.dumps(payload), _U)])
    return Auditor(Agente("auditor", "auditor_v1", "claude-opus-5-5", cliente=cli))


def test_auditor_emite_objecion_y_devuelve():
    aud = _auditor({"objeciones": [{"tipo": "concentracion", "detalle": "3 nombres = 1 apuesta nuclear",
                                    "severidad": "alta"}], "devuelve_al_pm": True})
    rep = aud.auditar(_decision([_accion()]), cartera_actual={}, caja_actual=1.0)
    assert rep.devuelve_al_pm is True and len(rep.objeciones) == 1
    assert rep.objeciones[0].tipo == "concentracion" and rep.objeciones[0].severidad == "alta"


def test_auditor_sin_objeciones_no_devuelve():
    aud = _auditor({"objeciones": [], "devuelve_al_pm": False})
    rep = aud.auditar(_decision([_accion()]), cartera_actual={"MP": 0.1}, caja_actual=0.9)
    assert rep.devuelve_al_pm is False and rep.objeciones == []


def test_auditor_recibe_fail_y_ips_en_el_prompt():
    aud = _auditor({"objeciones": [], "devuelve_al_pm": False})
    aud.auditar(_decision([_accion("OKLO")]), cartera_actual={}, caja_actual=1.0,
                verif_por_ticker={"OKLO": "fail", "MP": "pass"},
                ips_violaciones=[Violacion("peso_max_nombre", "OKLO: 25% > 20%", -0.05, "local_simple")])
    user_msg = aud.ag._cliente.llamadas[0]["messages"][0]["content"]
    assert "OKLO" in user_msg.split("VERIFICACIÓN FALLIDA")[1].split("VIOLACIONES")[0]  # OKLO listado como FAIL
    assert "peso_max_nombre" in user_msg


def test_auditor_meta_se_computa_no_la_da_el_llm():
    aud = _auditor({"objeciones": [], "devuelve_al_pm": False})
    rep = aud.auditar(_decision(), cartera_actual={}, caja_actual=1.0)
    assert rep.meta.agent == "auditor" and rep.meta.prompt_version == "auditor_v1"
