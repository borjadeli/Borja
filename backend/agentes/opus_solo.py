"""Baseline "Opus+web SOLO" (v2 Fase 5, doc 59 §6b) — la vara que dice si el COMITÉ agrega valor.

Un ÚNICO Opus 5.5 + web elige la cartera directamente, SIN el pipeline (sin Triage/Analista/Bear/
Verificador/contraste XBRL/IPS-gate). Se le dan el universo, los límites del IPS (como texto, para que sea
una comparación justa) y la caja; investiga y emite pesos-objetivo. Sus pesos se registran como la cartera
sombra `opus_solo` y su curva se compara contra la del PM (comité completo). doc 49 midió que el valor es
Opus investigando agénticamente; esto testea si ADEMÁS el comité le gana a ese Opus pelado.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from backend.agentes.base import Agente
from backend.agentes.schemas import AgentMeta

PROMPT_VERSION = "opus_solo_v1"
_PROMPT = (Path(__file__).resolve().parent.parent.parent / "prompts" / "opus_solo_v1.md").read_text()

WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 6}
_S = {"type": "string"}


def _obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


EMITIR_CARTERA_TOOL = {
    "name": "emitir_cartera",
    "description": "Emití tu cartera-objetivo final (pesos por nombre). Es tu única salida.",
    "strict": True,
    "input_schema": _obj({
        "posiciones": {"type": "array", "items": _obj({
            "ticker": _S, "peso_objetivo": {"type": "number"}, "tesis": _S})},
        "razon_caja": _S,
    }),
}


@dataclass
class ResultadoOpusSolo:
    pesos: dict[str, float] = field(default_factory=dict)      # ticker → fracción (0-1)
    meta: AgentMeta | None = None


class OpusSolo:
    def __init__(self, agente: Agente):
        self.ag = agente

    def elegir(self, tickers: list[str], *, caps_texto: str = "", peso_max: float = 0.20,
               max_tokens: int = 6144) -> ResultadoOpusSolo:
        user = (
            f"Universo del ciclo: {', '.join(t.upper() for t in tickers)}\n"
            f"Límites del operador (IPS): {caps_texto or f'peso máx {peso_max:.0%}/nombre'}\n"
            f"Elegí tu cartera-objetivo: investigá con web_search y después llamá a emitir_cartera. "
            f"Podés quedarte parcial o 100% en caja si no hay convicción."
        )
        payload, _fuentes, meta = self.ag.agentico(
            system=_PROMPT, user=user, tools=[WEB_SEARCH_TOOL, EMITIR_CARTERA_TOOL],
            emisor="emitir_cartera", max_tokens=max_tokens)
        if payload is None:
            return ResultadoOpusSolo(pesos={}, meta=meta)       # no emitió → 100% caja
        pesos: dict[str, float] = {}
        for a in payload.get("posiciones", []):
            w = max(0.0, min(peso_max, float(a.get("peso_objetivo", 0.0) or 0.0)))   # clamp al cap, comparación justa
            if w > 0 and a.get("ticker"):
                pesos[a["ticker"].upper()] = w
        return ResultadoOpusSolo(pesos=pesos, meta=meta)
