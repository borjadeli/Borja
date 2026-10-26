"""Agent base — transporte + costo + salida estructurada + ScriptedLLM (v2 Fase 3, doc 54 §4.8).

Reusa `services.llm._get_client()` como transporte. Los agentes SIN web (Triage/Bear/Verificador) usan
`output_config.format` (structured outputs). El cliente es INYECTABLE → `ScriptedLLM` para tests sin API.

Tabla de precios propia (la de llm.py es vieja, sin 5.5). Cache-read por modelo según doc 54: 5% en
Opus/Sonnet 5.5, 10% en Haiku 5.5 (si se hardcodea 5% se subestima Haiku).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from backend.agentes.schemas import AgentMeta

# Precios base por 1M tokens + % de cache_read por modelo (doc 54 §4).
PRECIOS: dict[str, dict[str, float]] = {
    "claude-opus-5-5":   {"input": 4.0,  "output": 20.0, "cache_read_pct": 0.05},
    "claude-sonnet-5-5": {"input": 2.0,  "output": 10.0, "cache_read_pct": 0.05},
    "claude-haiku-5-5":  {"input": 0.10, "output": 0.50, "cache_read_pct": 0.10},
    "claude-fable-5-1":  {"input": 10.0, "output": 50.0, "cache_read_pct": 0.025},
}
WEB_SEARCH_USD = 0.01


def _u(usage, attr: str) -> int:
    return int(getattr(usage, attr, 0) or 0)


def costo_usd(model: str, usage: Any) -> float:
    """Costo en USD de una respuesta a partir del `usage` real (no estimado) — alimenta el ledger."""
    p = PRECIOS.get(model) or PRECIOS["claude-opus-5-5"]
    stu = getattr(usage, "server_tool_use", None)
    searches = int(getattr(stu, "web_search_requests", 0) or 0) if stu else 0
    c = _u(usage, "input_tokens") / 1e6 * p["input"]
    c += _u(usage, "output_tokens") / 1e6 * p["output"]
    c += _u(usage, "cache_read_input_tokens") / 1e6 * (p["input"] * p["cache_read_pct"])
    c += _u(usage, "cache_creation_input_tokens") / 1e6 * (p["input"] * 1.25)   # cache-write 5m ≈ 1.25x
    c += searches * WEB_SEARCH_USD
    return round(c, 6)


def _primer_texto(resp: Any) -> str:
    for b in resp.content:
        if getattr(b, "type", None) == "text":
            return b.text
    return ""


def construir_meta(agente: str, prompt_version: str, resp: Any) -> AgentMeta:
    u = resp.usage
    stu = getattr(u, "server_tool_use", None)
    return AgentMeta(
        agent=agente, prompt_version=prompt_version, model=getattr(resp, "model", "?"),
        cost_usd=costo_usd(getattr(resp, "model", ""), u),
        input_tokens=_u(u, "input_tokens"), output_tokens=_u(u, "output_tokens"),
        web_searches=(int(getattr(stu, "web_search_requests", 0) or 0) if stu else 0),
    )


class Agente:
    """Transporte de un agente: una llamada LLM con salida estructurada → (payload dict, AgentMeta).

    El cliente es inyectable (ScriptedLLM en tests). El schema del payload lo provee cada agente
    (strict-compliant: additionalProperties False + todo required con centinelas; sin campo 'razonamiento'
    — riesgo reasoning_extraction). La `meta` NO la produce el LLM; se computa del `usage` real.
    """

    def __init__(self, nombre: str, prompt_version: str, model: str, *, cliente: Any | None = None):
        self.nombre = nombre
        self.prompt_version = prompt_version
        self.model = model
        self._cliente = cliente

    def _cli(self) -> Any:
        if self._cliente is not None:
            return self._cliente
        from backend.services.llm import _get_client
        return _get_client()

    def estructurado(self, *, system: str, user: str, payload_schema: dict,
                     max_tokens: int = 1024) -> tuple[dict, AgentMeta]:
        resp = self._cli().messages.create(
            model=self.model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": payload_schema}},
        )
        payload = json.loads(_primer_texto(resp))
        return payload, construir_meta(self.nombre, self.prompt_version, resp)


# --------------------------------------------------------------------------- ScriptedLLM (tests)

@dataclass
class FakeUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    server_tool_use: Any = None


@dataclass
class _TextBlock:
    text: str
    type: str = "text"


@dataclass
class _FakeResp:
    content: list
    model: str
    usage: FakeUsage
    stop_reason: str = "end_turn"


class ScriptedLLM:
    """Fake de `anthropic.Anthropic` para tests sin API. Se le pasa una cola de `(texto, FakeUsage)`;
    cada `messages.create(...)` devuelve el siguiente y registra los kwargs recibidos en `.llamadas`."""

    def __init__(self, respuestas: list[tuple[str, FakeUsage]]):
        self._q = list(respuestas)
        self.llamadas: list[dict] = []

    @property
    def messages(self):  # noqa: D401 — imita client.messages
        return self

    def create(self, **kwargs) -> _FakeResp:
        self.llamadas.append(kwargs)
        if not self._q:
            raise AssertionError("ScriptedLLM sin respuestas en cola")
        texto, usage = self._q.pop(0)
        return _FakeResp(content=[_TextBlock(texto)], model=kwargs.get("model", "fake"), usage=usage)
