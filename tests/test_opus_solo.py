"""Tests del baseline Opus+web solo (v2 Fase 5). Sin API — ScriptedLLM."""
from backend.agentes.base import Agente, FakeUsage, ScriptedLLM, resp_sin_emitir, resp_tool
from backend.agentes.opus_solo import OpusSolo

_U = FakeUsage(input_tokens=2000, output_tokens=200)


def _os(resps):
    return OpusSolo(Agente("opus_solo", "opus_solo_v1", "claude-opus-5-5", cliente=ScriptedLLM(resps)))


def test_elige_pesos_y_clampa_al_cap():
    payload = {"posiciones": [{"ticker": "OKLO", "peso_objetivo": 0.1, "tesis": "x"},
                              {"ticker": "MP", "peso_objetivo": 0.5, "tesis": "y"}],  # excede cap 0.20
               "razon_caja": "resto en caja"}
    r = _os([resp_tool("emitir_cartera", payload, _U)]).elegir(["OKLO", "MP"], peso_max=0.20)
    assert r.pesos == {"OKLO": 0.1, "MP": 0.20}        # MP clampeado al cap


def test_sin_emitir_queda_en_caja():
    r = _os([resp_sin_emitir(_U), resp_sin_emitir(_U)]).elegir(["OKLO"])
    assert r.pesos == {}                                # 100% caja


def test_max_web_configura_el_presupuesto_de_busquedas():
    # r3 #3: paridad — el max_web del caller setea max_uses del tool de web search
    cli = ScriptedLLM([resp_tool("emitir_cartera", {"posiciones": [], "razon_caja": "x"}, _U)])
    OpusSolo(Agente("opus_solo", "v1", "claude-opus-5-5", cliente=cli)).elegir(["OKLO"], max_web=27)
    tools = cli.llamadas[0]["tools"]
    web = next(t for t in tools if t.get("name") == "web_search")
    assert web["max_uses"] == 27
