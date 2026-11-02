"""Tests del agente Auditor (v2 Fase 4 + D5 doc 74). Sin API — ScriptedLLM agéntico (web + emisor tool)."""
from backend.agentes.auditor import Auditor
from backend.agentes.base import Agente, FakeUsage, ScriptedLLM, resp_tool
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
    cli = ScriptedLLM([resp_tool("emitir_auditoria", payload, _U)])
    return Auditor(Agente("auditor", "auditor_v1", "claude-sonnet-5-5", cliente=cli))


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


def test_auditor_recibe_analisis_de_cartera():
    aud = _auditor({"objeciones": [], "devuelve_al_pm": False})
    aud.auditar(_decision([_accion()]), cartera_actual={"OKLO": 0.1}, caja_actual=0.9,
                cartera_analisis="CONCENTRACIÓN POR FACTOR: cuello:SMR 40% (OKLO, SMR, NNE)")
    msg = aud.ag._cliente.llamadas[0]["messages"][0]["content"]
    assert "cuello:SMR 40%" in msg and "ANÁLISIS DE CARTERA" in msg


# --------------------------------------------------------------------------- D5: web + checklist + materialidad

def test_auditor_capa_a_tres_objeciones():
    objs = [{"tipo": "omision_material", "detalle": f"hallazgo {i} (url, consecuencia)", "severidad": "media"}
            for i in range(6)]
    aud = _auditor({"objeciones": objs, "devuelve_al_pm": True})
    rep = aud.auditar(_decision([_accion()]), cartera_actual={}, caja_actual=1.0)
    assert len(rep.objeciones) == 3                      # materialidad: cap duro


def test_auditor_acepta_tipos_de_hallazgo_web():
    aud = _auditor({"objeciones": [
        {"tipo": "evento_proximo", "detalle": "vencimiento chino 10/11 a 8 días (url)", "severidad": "alta"},
        {"tipo": "clausula_filing", "detalle": "clawback 30% sobre $110/kg en el 10-K (url)", "severidad": "alta"}],
        "devuelve_al_pm": True})
    rep = aud.auditar(_decision([_accion()]), cartera_actual={}, caja_actual=1.0)
    assert {o.tipo for o in rep.objeciones} == {"evento_proximo", "clausula_filing"}


def test_auditor_user_trae_el_checklist_web():
    aud = _auditor({"objeciones": [], "devuelve_al_pm": False})
    aud.auditar(_decision([_accion()]), cartera_actual={}, caja_actual=1.0)
    user_msg = aud.ag._cliente.llamadas[0]["messages"][0]["content"]
    assert "REFUTAR" in user_msg and "checklist" in user_msg.lower()
