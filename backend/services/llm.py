"""Anthropic Claude wrapper — núcleo de los agentes cualitativos (Analista, Mapa, Discovery).

Responsabilidades:
- Envío de prompts con caching ephemeral del system prompt (reduce costo 5-10x).
- Parser JSON estricto — si el output no es parseable, levanta LLMInvalidJSON.
- Tracking de tokens y costo por llamada (log estructurado).
- Modo dry-run para tests sin gasto real.
- Retry automático en errores transitorios.

Modelo por default: claude-opus-4-7 (configurable vía ANTHROPIC_MODEL).
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from backend.config import get_settings
from backend.utils import get_logger, utcnow

log = get_logger(__name__)


# Precios por millón de tokens (Opus 4.7, actualizar cuando cambie).
# Mantener sincronizado con docs.anthropic.com/pricing.
PRICING_PER_M = {
    "claude-opus-4-7": {
        "input": 15.0,
        "output": 75.0,
        "cache_write_5m": 18.75,
        "cache_read": 1.50,
    },
    "claude-sonnet-4-6": {
        "input": 3.0,
        "output": 15.0,
        "cache_write_5m": 3.75,
        "cache_read": 0.30,
    },
    "claude-haiku-4-5-20251001": {
        "input": 1.0,
        "output": 5.0,
        "cache_write_5m": 1.25,
        "cache_read": 0.10,
    },
}

# Web search tool: ~$10 por 1000 búsquedas (server-side tool Anthropic).
WEB_SEARCH_COST_PER_CALL = 0.01
WEB_SEARCH_TOOL_NAME = "web_search"
WEB_SEARCH_TOOL_TYPE = "web_search_20250305"


class LLMError(Exception):
    """Base para errores del wrapper LLM."""


class LLMInvalidJSON(LLMError):
    """El output no es JSON válido o no cumple el schema."""


class LLMNoAPIKey(LLMError):
    """Falta ANTHROPIC_API_KEY."""


@dataclass
class LLMCallResult:
    text: str
    parsed_json: dict | list | None
    model: str
    tokens_input: int
    tokens_output: int
    tokens_cache_read: int = 0
    tokens_cache_write: int = 0
    cost_usd: float = 0.0
    latency_s: float = 0.0
    stop_reason: str | None = None
    metadata: dict = field(default_factory=dict)


# ---------- Cliente ----------

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise LLMNoAPIKey("ANTHROPIC_API_KEY no configurada en .env")
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def _calculate_cost(model: str, usage: dict) -> float:
    prices = PRICING_PER_M.get(model)
    if not prices:
        # default a Opus si el modelo no está en la tabla
        prices = PRICING_PER_M["claude-opus-4-7"]
    cost = 0.0
    cost += (usage.get("input_tokens", 0) / 1_000_000) * prices["input"]
    cost += (usage.get("output_tokens", 0) / 1_000_000) * prices["output"]
    cost += (usage.get("cache_read_input_tokens", 0) / 1_000_000) * prices["cache_read"]
    cost += (usage.get("cache_creation_input_tokens", 0) / 1_000_000) * prices["cache_write_5m"]
    return round(cost, 4)


# ---------- Llamada principal ----------

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type((anthropic.APIStatusError, anthropic.APIConnectionError, anthropic.RateLimitError)),
    reraise=True,
)
def call_llm_json(
    system_prompt: str,
    user_message: str,
    *,
    model: str | None = None,
    max_tokens: int = 8192,
    temperature: float = 0.3,
    cache_system: bool = True,
    dry_run: bool = False,
    extra_metadata: dict | None = None,
) -> LLMCallResult:
    """Llama a Claude esperando JSON en el output.

    Args:
        system_prompt: instrucciones estáticas del agente (se cachea).
        user_message: datos específicos del ticker / sector (dinámico).
        cache_system: si True, aplica cache_control ephemeral al system.
        dry_run: si True, no llama a la API — devuelve un mock vacío con el prompt.
        extra_metadata: dict adicional para guardar junto con el resultado.
    """
    settings = get_settings()
    model = model or settings.anthropic_model
    t0 = time.time()

    if dry_run:
        return LLMCallResult(
            text="",
            parsed_json=None,
            model=model,
            tokens_input=0,
            tokens_output=0,
            cost_usd=0.0,
            latency_s=0.0,
            metadata={
                "dry_run": True,
                "system_prompt_preview": system_prompt[:200],
                "user_message_preview": user_message[:200],
                **(extra_metadata or {}),
            },
        )

    client = _get_client()

    system_param: Any = system_prompt
    if cache_system:
        system_param = [{
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }]

    # Opus 4.7 no acepta `temperature` (deprecated en modelos con extended thinking).
    # Omitimos el parámetro si el modelo es Opus 4.7+; temperature=0.3 quedó como
    # vestigio de iteraciones previas pero el prompt ya fuerza determinismo.
    create_kwargs = dict(
        model=model,
        max_tokens=max_tokens,
        system=system_param,
        messages=[{"role": "user", "content": user_message}],
    )
    if not model.startswith("claude-opus-4"):   # Opus 4.x deprecó `temperature`
        create_kwargs["temperature"] = temperature

    response = client.messages.create(**create_kwargs)

    text = "".join(block.text for block in response.content if hasattr(block, "text"))

    # Calcular costo + persistir SIEMPRE que la API haya respondido — los tokens
    # ya fueron consumidos. NO mover esto después del parse JSON: si el output es
    # inválido, igual hay que trackear el costo (bug histórico 2026-04-21).
    usage_dict = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_read_input_tokens": getattr(response.usage, "cache_read_input_tokens", 0) or 0,
        "cache_creation_input_tokens": getattr(response.usage, "cache_creation_input_tokens", 0) or 0,
    }
    cost = _calculate_cost(model, usage_dict)

    parsed = _safe_parse_json(text)

    result = LLMCallResult(
        text=text,
        parsed_json=parsed,
        model=model,
        tokens_input=usage_dict["input_tokens"],
        tokens_output=usage_dict["output_tokens"],
        tokens_cache_read=usage_dict["cache_read_input_tokens"],
        tokens_cache_write=usage_dict["cache_creation_input_tokens"],
        cost_usd=cost,
        latency_s=round(time.time() - t0, 2),
        stop_reason=response.stop_reason,
        metadata={**(extra_metadata or {}), "json_parse_ok": parsed is not None},
    )

    log.info(
        "LLM call — model=%s latency=%.2fs tokens=%d/%d cache=%d/%d cost=$%.4f json_ok=%s",
        model, result.latency_s,
        result.tokens_input, result.tokens_output,
        result.tokens_cache_read, result.tokens_cache_write,
        result.cost_usd, parsed is not None,
    )
    _persistir_llm_call(result, web_searches=0)

    if parsed is None:
        log.error("LLM output no parseable — modelo=%s stop_reason=%s", model, response.stop_reason)
        log.debug("Output crudo:\n%s", text[:1000])
        raise LLMInvalidJSON(
            f"Output del modelo no es JSON válido. stop_reason={response.stop_reason}. "
            f"Primeros 300 chars: {text[:300]}"
        )

    return result


# ---------- JSON parser ----------

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)


def _safe_parse_json(text: str) -> dict | list | None:
    """Intenta parsear JSON — primero directo, luego extrayendo de bloque ```json, luego primer {...}."""
    if not text:
        return None
    text = text.strip()

    # 1) parse directo
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # 2) extraer de bloque ```json ... ```
    m = _JSON_BLOCK_RE.search(text)
    if m:
        try:
            return json.loads(m.group(1))
        except (json.JSONDecodeError, ValueError):
            pass

    # 3) buscar primer objeto o array JSON válido por estructura
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start == -1:
            continue
        depth = 0
        for i in range(start, len(text)):
            if text[i] == opener:
                depth += 1
            elif text[i] == closer:
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        return json.loads(candidate)
                    except (json.JSONDecodeError, ValueError):
                        break
    return None


def ping() -> bool:
    """Verifica que la API key está configurada (no llama al modelo)."""
    try:
        _get_client()
        return True
    except LLMNoAPIKey:
        return False


# ---------- Llamada con web_search (para Mapa Sectorial y Discovery) ----------

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type((anthropic.APIStatusError, anthropic.APIConnectionError, anthropic.RateLimitError)),
    reraise=True,
)
def call_llm_json_with_web_search(
    system_prompt: str,
    user_message: str,
    *,
    model: str | None = None,
    max_tokens: int = 16384,
    temperature: float = 0.3,
    max_searches: int = 5,
    allowed_domains: list[str] | None = None,
    cache_system: bool = False,
    dry_run: bool = False,
    extra_metadata: dict | None = None,
) -> LLMCallResult:
    """Llama a Claude con la tool web_search habilitada, esperando JSON final.

    La tool `web_search_20250305` es server-side — Claude ejecuta búsquedas internamente
    y devuelve el texto final con citas. No requiere loop de tool_use del cliente.

    Args:
        max_searches: máximo de búsquedas permitidas por llamada (control de costo).
        allowed_domains: lista opcional de dominios permitidos (whitelist).
        cache_system: por default False — web_search rara vez se beneficia de caching
            porque cada sector/semana cambia.
    """
    settings = get_settings()
    model = model or settings.anthropic_model
    t0 = time.time()

    if dry_run:
        return LLMCallResult(
            text="",
            parsed_json=None,
            model=model,
            tokens_input=0,
            tokens_output=0,
            cost_usd=0.0,
            latency_s=0.0,
            metadata={
                "dry_run": True,
                "web_search": True,
                "max_searches": max_searches,
                "system_prompt_preview": system_prompt[:200],
                "user_message_preview": user_message[:200],
                **(extra_metadata or {}),
            },
        )

    client = _get_client()

    system_param: Any = system_prompt
    if cache_system:
        system_param = [{
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }]

    tool_def: dict[str, Any] = {
        "type": WEB_SEARCH_TOOL_TYPE,
        "name": WEB_SEARCH_TOOL_NAME,
        "max_uses": max_searches,
    }
    if allowed_domains:
        tool_def["allowed_domains"] = allowed_domains

    # Opus 4.7 no acepta `temperature` — omitir para ese modelo.
    create_kwargs = dict(
        model=model,
        max_tokens=max_tokens,
        system=system_param,
        tools=[tool_def],
        messages=[{"role": "user", "content": user_message}],
    )
    if not model.startswith("claude-opus-4"):   # Opus 4.x deprecó `temperature`
        create_kwargs["temperature"] = temperature

    response = client.messages.create(**create_kwargs)

    # Contar búsquedas realizadas y recolectar texto final
    web_searches_usadas = 0
    urls_citadas: list[str] = []
    text_blocks: list[str] = []
    for block in response.content:
        btype = getattr(block, "type", None)
        if btype == "server_tool_use":
            if getattr(block, "name", "") == WEB_SEARCH_TOOL_NAME:
                web_searches_usadas += 1
        elif btype == "web_search_tool_result":
            # Extraer URLs de resultados (para auditoría en fuentes_resumen)
            content = getattr(block, "content", None) or []
            if isinstance(content, list):
                for r in content:
                    url = (r.get("url") if isinstance(r, dict) else getattr(r, "url", None))
                    if url:
                        urls_citadas.append(url)
        elif btype == "text" or hasattr(block, "text"):
            text_blocks.append(getattr(block, "text", ""))

    text = "\n".join(tb for tb in text_blocks if tb)

    # Calcular costo + persistir SIEMPRE — los tokens y web searches ya fueron
    # consumidos. NO mover esto después del parse JSON (bug histórico 2026-04-21).
    usage_dict = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_read_input_tokens": getattr(response.usage, "cache_read_input_tokens", 0) or 0,
        "cache_creation_input_tokens": getattr(response.usage, "cache_creation_input_tokens", 0) or 0,
    }
    cost_tokens = _calculate_cost(model, usage_dict)
    cost_searches = web_searches_usadas * WEB_SEARCH_COST_PER_CALL
    cost_total = round(cost_tokens + cost_searches, 4)

    parsed = _safe_parse_json(text)

    extra_md = dict(extra_metadata or {})
    extra_md.update({
        "web_searches_usadas": web_searches_usadas,
        "urls_citadas": urls_citadas[:20],  # truncar
        "cost_searches_usd": round(cost_searches, 4),
        "json_parse_ok": parsed is not None,
    })

    result = LLMCallResult(
        text=text,
        parsed_json=parsed,
        model=model,
        tokens_input=usage_dict["input_tokens"],
        tokens_output=usage_dict["output_tokens"],
        tokens_cache_read=usage_dict["cache_read_input_tokens"],
        tokens_cache_write=usage_dict["cache_creation_input_tokens"],
        cost_usd=cost_total,
        latency_s=round(time.time() - t0, 2),
        stop_reason=response.stop_reason,
        metadata=extra_md,
    )

    log.info(
        "LLM+web_search — model=%s latency=%.2fs tokens=%d/%d searches=%d/%d cost=$%.4f json_ok=%s",
        model, result.latency_s,
        result.tokens_input, result.tokens_output,
        web_searches_usadas, max_searches,
        result.cost_usd, parsed is not None,
    )
    _persistir_llm_call(result, web_searches=web_searches_usadas)

    if parsed is None:
        log.error("LLM web_search output no parseable — modelo=%s stop_reason=%s", model, response.stop_reason)
        log.debug("Output crudo:\n%s", text[:1500])
        raise LLMInvalidJSON(
            f"Output no es JSON válido después de {web_searches_usadas} búsquedas. "
            f"stop_reason={response.stop_reason}. Primeros 300 chars: {text[:300]}"
        )
    return result


# ---------- Persistencia de costo ----------

def _persistir_llm_call(result: "LLMCallResult", web_searches: int = 0) -> None:
    """Registra la llamada en tabla llm_calls. Falla silenciosa (no bloquea agente)."""
    try:
        from backend.database import session_scope
        from backend.models import LLMCall

        md = result.metadata or {}
        with session_scope() as s:
            s.add(LLMCall(
                agent=md.get("agent", "unknown"),
                model=result.model,
                ticker_o_sector=md.get("ticker") or md.get("sector") or md.get("semana"),
                tokens_input=result.tokens_input,
                tokens_output=result.tokens_output,
                tokens_cache_read=result.tokens_cache_read,
                tokens_cache_write=result.tokens_cache_write,
                web_searches=web_searches,
                cost_usd=result.cost_usd,
                latency_s=result.latency_s,
                stop_reason=result.stop_reason,
                metadata_json={
                    "prompt_version": md.get("prompt_version"),
                    "urls_citadas": md.get("urls_citadas", [])[:5] if md.get("urls_citadas") else None,
                },
            ))
    except Exception as e:  # noqa: BLE001
        log.warning("no pude persistir llm_call: %s", e)
