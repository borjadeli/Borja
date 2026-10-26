"""Agente Macro/Tesis (v2 Fase 3, doc 54 §4; doc 52 agente 1).

Opus 5.5 + web_search + tool cliente `emitir_memo` (strict). Semanal. Evalúa el ciclo (capex IA, energía,
commodities, tasas) y qué cuellos se aprietan/aflojan → MacroMemo. Reusa el patrón agéntico ya validado
en vivo por el Analista (base.agentico). NO elige empresas ni tamaños; da el marco para Triage/Analista/PM.
"""
from __future__ import annotations

from pathlib import Path

from backend.agentes.base import Agente
from backend.agentes.schemas import MacroMemo

PROMPT_VERSION = "macro_v1"
_PROMPT = (Path(__file__).resolve().parent.parent.parent / "prompts" / "macro_v1.md").read_text()

WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 6}

_DELTA = ["sube", "baja", "igual", "nuevo"]
_VERIF = ["confirmed_by_filing", "company_statement", "media_report", "search_summary",
          "analyst_prior", "hypothesis"]
_S = {"type": "string"}


def _obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


EMITIR_MEMO_TOOL = {
    "name": "emitir_memo",
    "description": "Emití el memo macro de la semana. Es tu única salida; llamalo cuando terminaste.",
    "strict": True,
    "input_schema": _obj({
        "ciclo_capex_ia": _S, "energia": _S, "commodities": _S, "tasas": _S,
        "cuellos_prioridad": {"type": "array", "items": _obj({
            "cuello": _S,
            "prioridad_0_3": {"type": "integer"},
            "delta_vs_anterior": {"type": "string", "enum": _DELTA},
            "razon": _S})},
        "resumen": _S,
        "evidencia": {"type": "array", "items": _obj({
            "claim": _S, "source_url": _S, "source_date": _S,
            "verification": {"type": "string", "enum": _VERIF}})},
    }),
}


class Macro:
    def __init__(self, agente: Agente):
        self.ag = agente

    def evaluar(self, *, prioridades_previas: str = "", max_tokens: int = 6144) -> MacroMemo | None:
        user = (
            "Evaluá el estado macro de esta semana para el universo de BORJA (small/mid caps de industrias "
            "del futuro).\n\n=== PRIORIDADES DE CUELLOS DE LA SEMANA ANTERIOR ===\n"
            f"{prioridades_previas or '(primera corrida — no hay previa)'}\n\n"
            "Investigá con web_search y después llamá a emitir_memo."
        )
        payload, _fuentes, meta = self.ag.agentico(
            system=_PROMPT, user=user, tools=[WEB_SEARCH_TOOL, EMITIR_MEMO_TOOL],
            emisor="emitir_memo", max_tokens=max_tokens,
        )
        if payload is None:
            return None
        # clamp de prioridad_0_3 (structured outputs no expresa rangos numéricos)
        for cp in payload.get("cuellos_prioridad", []):
            cp["prioridad_0_3"] = max(0, min(3, int(cp.get("prioridad_0_3", 0))))
        return MacroMemo.model_validate({"meta": meta.model_dump(), **payload})
