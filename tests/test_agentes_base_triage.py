"""Tests del agent base + Triage (v2 Fase 3). Sin API — se usa ScriptedLLM."""
import json

from backend.agentes.base import Agente, FakeUsage, ScriptedLLM, costo_usd
from backend.agentes.triage import SenalesTriage, Triage, incertidumbre, prioridad


# ---- costo por modelo (cache-read 5% Opus / 10% Haiku) ----

def test_costo_haiku_cache_read_10pct():
    u = FakeUsage(input_tokens=1_000_000, output_tokens=0, cache_read_input_tokens=1_000_000)
    # input 1M×$0.10 + cache_read 1M×($0.10×10%)=$0.01 → $0.11
    assert costo_usd("claude-haiku-5-5", u) == 0.11


def test_costo_opus_cache_read_5pct():
    u = FakeUsage(input_tokens=1_000_000, output_tokens=1_000_000, cache_read_input_tokens=1_000_000)
    # 1M×$4 + 1M×$20 + cache_read 1M×($4×5%=$0.20) = $24.20
    assert costo_usd("claude-opus-5-5", u) == 24.20


# ---- agent base ----

def test_estructurado_parsea_payload_y_computa_meta():
    scripted = ScriptedLLM([(json.dumps({"materialidad_0_1": 0.7, "motivo": "contrato"}),
                             FakeUsage(input_tokens=500, output_tokens=50))])
    ag = Agente("triage", "triage_v1", "claude-haiku-5-5", cliente=scripted)
    payload, meta = ag.estructurado(system="s", user="u", payload_schema={"type": "object"})
    assert payload["materialidad_0_1"] == 0.7
    assert meta.model == "claude-haiku-5-5" and meta.input_tokens == 500 and meta.cost_usd > 0
    assert scripted.llamadas[0]["output_config"]["format"]["type"] == "json_schema"


# ---- triage: fórmulas deterministas ----

def test_prioridad_e_incertidumbre():
    nunca = SenalesTriage(dias_desde_dossier=None, hechos_nuevos=0, dias_a_evento=None, precio_vs_tesis_pct=None)
    assert incertidumbre(nunca, 0.0) == 0.8          # nunca analizada → mucha incertidumbre
    assert prioridad(nunca, 0.0) == 1                 # merece una mirada
    pos = SenalesTriage(dias_desde_dossier=10, hechos_nuevos=0, dias_a_evento=None,
                        precio_vs_tesis_pct=None, es_posicion=True)
    assert prioridad(pos, 0.0) >= 2                    # posiciones no bajan de media


# ---- triage: integración con ScriptedLLM ----

def test_triage_sin_hechos_nuevos_no_llama_llm():
    scripted = ScriptedLLM([])                         # cola vacía: si llamara, explotaría
    t = Triage(Agente("triage", "triage_v1", "claude-haiku-5-5", cliente=scripted))
    s = SenalesTriage(dias_desde_dossier=30, hechos_nuevos=0, dias_a_evento=None, precio_vs_tesis_pct=None)
    d = t.evaluar("OKLO", s)
    assert scripted.llamadas == []                     # disciplina de costo: sin hechos, sin LLM
    assert d.ticker == "OKLO" and d.meta.cost_usd == 0.0


def test_triage_posicion_forzada_sin_llm():
    scripted = ScriptedLLM([])
    t = Triage(Agente("triage", "triage_v1", "claude-haiku-5-5", cliente=scripted))
    s = SenalesTriage(dias_desde_dossier=10, hechos_nuevos=0, dias_a_evento=None,
                      precio_vs_tesis_pct=None, es_posicion=True)
    d = t.evaluar("MP", s)
    assert d.research_profundo is True and d.prioridad_0_3 >= 2
    assert scripted.llamadas == []


def test_triage_con_hechos_llama_y_prioriza():
    scripted = ScriptedLLM([(json.dumps({"materialidad_0_1": 0.9, "motivo": "contrato DOE firmado"}),
                             FakeUsage(input_tokens=600, output_tokens=40))])
    t = Triage(Agente("triage", "triage_v1", "claude-haiku-5-5", cliente=scripted))
    s = SenalesTriage(dias_desde_dossier=None, hechos_nuevos=3, dias_a_evento=7, precio_vs_tesis_pct=None)
    d = t.evaluar("NNE", s, resumen_hechos_nuevos="firmó contrato con el DOE")
    assert len(scripted.llamadas) == 1                 # hubo hechos → se llamó al LLM
    assert d.research_profundo is True and d.prioridad_0_3 == 3
    assert d.motivo == "contrato DOE firmado" and d.meta.cost_usd > 0
