"""Test del agente Macro (v2 Fase 3). ScriptedLLM — reusa el patrón agéntico ya validado en vivo."""
from backend.agentes.base import Agente, FakeUsage, ScriptedLLM, resp_tool
from backend.agentes.macro import Macro


def test_macro_emite_memo_y_clampea_prioridad():
    payload = {
        "ciclo_capex_ia": "hyperscalers sostienen pedidos", "energia": "demanda firme 24/7 escasea",
        "commodities": "uranio ajustado", "tasas": "altas, castigan pre-revenue",
        "cuellos_prioridad": [{"cuello": "Enriquecimiento (SWU)", "prioridad_0_3": 5,  # fuera de rango → clamp 3
                               "delta_vs_anterior": "sube", "razon": "restricción de oferta occidental"}],
        "resumen": "El cuello de energía/combustible nuclear se aprieta.",
        "evidencia": [{"claim": "déficit de SWU occidental", "source_url": "https://x.com/y",
                       "source_date": "2026-10-01", "verification": "media_report"}],
    }
    scripted = ScriptedLLM([resp_tool("emitir_memo", payload, FakeUsage(input_tokens=30000, output_tokens=800))])
    m = Macro(Agente("macro", "macro_v1", "claude-opus-5-5", cliente=scripted))
    memo = m.evaluar()
    assert memo is not None
    assert memo.cuellos_prioridad[0].prioridad_0_3 == 3        # clampeado de 5
    assert memo.cuellos_prioridad[0].delta_vs_anterior == "sube"
    assert memo.meta.cost_usd > 0 and len(scripted.llamadas) == 1
