"""Agent base — transporte + costo + salida estructurada + ScriptedLLM (v2 Fase 3, doc 54 §4.8).

Reusa `services.llm._get_client()` como transporte. Los agentes SIN web (Triage/Bear/Verificador) usan
`output_config.format` (structured outputs). El cliente es INYECTABLE → `ScriptedLLM` para tests sin API.

Tabla de precios propia (la de llm.py es vieja, sin 5.5). Cache-read por modelo según doc 54: 5% en
Opus/Sonnet 5.5, 10% en Haiku 5.5 (si se hardcodea 5% se subestima Haiku).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from backend.agentes.schemas import AgentMeta

_log = logging.getLogger("agentes.base")


def _persistir_costo(meta: AgentMeta) -> None:
    """Registra una invocación de agente en `llm_calls` (para /costos + presupuesto mensual). Fail-silent.
    Solo se llama con el cliente REAL (no en tests con ScriptedLLM) — ver Agente._log_costo."""
    try:
        from backend.database import session_scope
        from backend.models import LLMCall
        with session_scope() as s:
            s.add(LLMCall(agent=meta.agent, model=meta.model, tokens_input=meta.input_tokens,
                          tokens_output=meta.output_tokens, web_searches=meta.web_searches,
                          cost_usd=meta.cost_usd,
                          metadata_json={"prompt_version": meta.prompt_version}))
    except Exception as e:  # noqa: BLE001 — el tracking no debe tumbar al agente
        _log.warning("no pude registrar costo del agente %s: %s", meta.agent, e)

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


def _buscar_tool_use(resp: Any, nombre: str) -> Any | None:
    for b in resp.content:
        if getattr(b, "type", None) == "tool_use" and getattr(b, "name", None) == nombre:
            return b
    return None


def _urls_de(resp: Any) -> list[str]:
    """URLs que trajo web_search en esta respuesta (procedencia para el Verificador)."""
    urls: list[str] = []
    for b in resp.content:
        if getattr(b, "type", None) == "web_search_tool_result":
            for item in (getattr(b, "content", None) or []):
                u = getattr(item, "url", None)
                if u:
                    urls.append(u)
    return urls


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
        meta = construir_meta(self.nombre, self.prompt_version, resp)
        self._log_costo(meta)
        return payload, meta

    def agentico(self, *, system: str, user: str, tools: list, emisor: str,
                 max_tokens: int = 8192, max_nudges: int = 1) -> tuple[dict | None, list[str], AgentMeta]:
        """Loop agéntico (Analista/Bear): corre el LLM con web_search + un tool cliente `emisor` (strict).
        Maneja `pause_turn` (reenvía el turno pausado sin cambios), reintenta UNA vez si termina sin emitir
        (no se puede forzar tool_choice con thinking always-on), y junta las URLs de web_search (procedencia).
        Devuelve (input del tool emisor | None, fuentes_urls, meta acumulada de TODO el loop)."""
        cli = self._cli()
        messages: list[dict] = [{"role": "user", "content": user}]
        acc = {"in": 0, "out": 0, "searches": 0, "cost": 0.0, "model": self.model}
        fuentes: list[str] = []
        nudges = 0
        while True:
            resp = cli.messages.create(model=self.model, max_tokens=max_tokens, system=system,
                                       messages=messages, tools=tools)
            u = resp.usage
            stu = getattr(u, "server_tool_use", None)
            acc["in"] += _u(u, "input_tokens"); acc["out"] += _u(u, "output_tokens")
            acc["searches"] += int(getattr(stu, "web_search_requests", 0) or 0) if stu else 0
            acc["cost"] += costo_usd(getattr(resp, "model", self.model), u)
            acc["model"] = getattr(resp, "model", self.model)
            fuentes.extend(_urls_de(resp))

            tu = _buscar_tool_use(resp, emisor)
            if tu is not None:
                return tu.input, list(dict.fromkeys(fuentes)), self._meta_acc(acc)
            if getattr(resp, "stop_reason", None) == "pause_turn":
                messages.append({"role": "assistant", "content": resp.content})
                continue
            if nudges < max_nudges:                       # terminó sin emitir → empujón (cache-hit, barato)
                messages.append({"role": "assistant", "content": resp.content})
                messages.append({"role": "user",
                                 "content": f"Emití el dossier ahora llamando a la tool {emisor}."})
                nudges += 1
                continue
            return None, list(dict.fromkeys(fuentes)), self._meta_acc(acc)

    def conversacion_tools(self, *, system: str, user: str, tools: list, emisor: str,
                           manejadores: dict, max_tokens: int = 4096,
                           max_nudges: int = 1) -> tuple[dict | None, AgentMeta]:
        """Loop con tools CLIENTE (sin web): cuando el LLM llama a una tool de `manejadores` (nombre→fn(dict)->str)
        se ejecuta y se le devuelve el resultado como `tool_result`; cuando llama a `emisor` se devuelve su input.
        Responde a TODOS los tool_use del turno (lo exige la API). Maneja pause_turn y empuja si no emite.
        Devuelve (input del emisor | None, meta acumulada). Usado por el PM (IPS como dry-run)."""
        cli = self._cli()
        messages: list[dict] = [{"role": "user", "content": user}]
        acc = {"in": 0, "out": 0, "searches": 0, "cost": 0.0, "model": self.model}
        nudges = 0
        while True:
            resp = cli.messages.create(model=self.model, max_tokens=max_tokens, system=system,
                                       messages=messages, tools=tools)
            u = resp.usage
            acc["in"] += _u(u, "input_tokens"); acc["out"] += _u(u, "output_tokens")
            acc["cost"] += costo_usd(getattr(resp, "model", self.model), u)
            acc["model"] = getattr(resp, "model", self.model)

            usos = [b for b in resp.content
                    if getattr(b, "type", None) == "tool_use"]
            emit = next((b for b in usos if getattr(b, "name", None) == emisor), None)
            if emit is not None:
                return emit.input, self._meta_acc(acc)
            if getattr(resp, "stop_reason", None) == "pause_turn":
                messages.append({"role": "assistant", "content": resp.content})
                continue
            if usos:                                   # tools cliente → ejecutar y devolver resultados
                messages.append({"role": "assistant", "content": resp.content})
                resultados = []
                for b in usos:
                    fn = manejadores.get(getattr(b, "name", ""))
                    salida = fn(b.input) if fn else f"tool desconocida: {getattr(b, 'name', '?')}"
                    resultados.append({"type": "tool_result", "tool_use_id": b.id, "content": salida})
                messages.append({"role": "user", "content": resultados})
                continue
            if nudges < max_nudges:                     # terminó sin emitir → empujón
                messages.append({"role": "assistant", "content": resp.content})
                messages.append({"role": "user",
                                 "content": f"Emití la decisión ahora llamando a la tool {emisor}."})
                nudges += 1
                continue
            return None, self._meta_acc(acc)

    def _meta_acc(self, acc: dict) -> AgentMeta:
        meta = AgentMeta(agent=self.nombre, prompt_version=self.prompt_version, model=acc["model"],
                         cost_usd=round(acc["cost"], 6), input_tokens=acc["in"],
                         output_tokens=acc["out"], web_searches=acc["searches"])
        self._log_costo(meta)
        return meta

    def _log_costo(self, meta: AgentMeta) -> None:
        """Registra el costo en llm_calls SOLO con el cliente real (self._cliente is None → usa _get_client).
        Con ScriptedLLM inyectado (tests) no toca la DB."""
        if self._cliente is None:
            _persistir_costo(meta)


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
class _ToolUseBlock:
    name: str
    input: dict
    id: str = "tu_1"
    type: str = "tool_use"


@dataclass
class _WSItem:
    url: str
    title: str = ""
    type: str = "web_search_result"


@dataclass
class _WSResultBlock:
    content: list
    type: str = "web_search_tool_result"


@dataclass
class _FakeResp:
    content: list
    model: str
    usage: FakeUsage
    stop_reason: str = "end_turn"


def resp_texto(texto: str, usage: FakeUsage, model: str = "fake") -> _FakeResp:
    return _FakeResp(content=[_TextBlock(texto)], model=model, usage=usage, stop_reason="end_turn")


def resp_tool(nombre: str, entrada: dict, usage: FakeUsage, *, urls: list[str] | None = None,
              model: str = "fake") -> _FakeResp:
    """Respuesta que EMITE el tool `nombre` (stop_reason tool_use), opcionalmente con URLs de búsqueda."""
    content: list = []
    if urls:
        content.append(_WSResultBlock(content=[_WSItem(url=u) for u in urls]))
    content.append(_ToolUseBlock(name=nombre, input=entrada))
    return _FakeResp(content=content, model=model, usage=usage, stop_reason="tool_use")


def resp_sin_emitir(usage: FakeUsage, *, urls: list[str] | None = None, model: str = "fake",
                    stop_reason: str = "end_turn") -> _FakeResp:
    """Respuesta que NO emite el tool (para probar el nudge / pause_turn)."""
    content: list = []
    if urls:
        content.append(_WSResultBlock(content=[_WSItem(url=u) for u in urls]))
    content.append(_TextBlock("..."))
    return _FakeResp(content=content, model=model, usage=usage, stop_reason=stop_reason)


class ScriptedLLM:
    """Fake de `anthropic.Anthropic` para tests sin API. Se le pasa una cola de respuestas; cada una es
    un `_FakeResp` (usar `resp_tool`/`resp_texto`/`resp_sin_emitir`) o un `(texto, FakeUsage)` (atajo texto).
    Cada `messages.create(...)` devuelve la siguiente y registra los kwargs en `.llamadas`."""

    def __init__(self, respuestas: list):
        self._q = list(respuestas)
        self.llamadas: list[dict] = []

    @property
    def messages(self):  # noqa: D401 — imita client.messages
        return self

    def create(self, **kwargs) -> _FakeResp:
        self.llamadas.append(kwargs)
        if not self._q:
            raise AssertionError("ScriptedLLM sin respuestas en cola")
        item = self._q.pop(0)
        if isinstance(item, _FakeResp):
            return item
        texto, usage = item                      # atajo (texto, usage)
        return _FakeResp(content=[_TextBlock(texto)], model=kwargs.get("model", "fake"), usage=usage)
