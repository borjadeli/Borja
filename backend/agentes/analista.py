"""Agente Analista (v2 Fase 3, doc 54 §4.1/§4.2) — la pieza central, validada en spike.

Opus 5.5 + `web_search` + tool cliente `emitir_dossier` (strict). Investiga agénticamente y emite el
Dossier como el `input` de ese tool (NO `output_config.format`, que es incompatible con las citas de
web search). No se puede forzar `tool_choice` con thinking always-on → `base.agentico` reintenta una vez.
Las URLs que trajo web_search se devuelven como `fuentes` (procedencia para el Verificador).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.agentes.base import Agente
from backend.agentes.provenance import DataPack
from backend.agentes.schemas import AgentMeta, Dossier

PROMPT_VERSION = "analista_v1"
_PROMPT = (Path(__file__).resolve().parent.parent.parent / "prompts" / "analista_v1.md").read_text()

WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 6}

_TIPO_CLAIM = ["hecho", "declaracion_empresa", "estimacion", "inferencia"]
_MATERIALITY = ["central", "soporte", "secundaria"]
_VERIF = ["confirmed_by_filing", "company_statement", "media_report", "search_summary",
          "analyst_prior", "hypothesis"]
_CAT_TIPO = ["earnings", "contrato", "capacidad", "producto", "regulatorio", "financiamiento", "otro"]
_SEV = ["alta", "media", "baja"]


def _obj(props: dict, required: list[str] | None = None) -> dict:
    # strict: todo required, additionalProperties false (doc 54 §4.1)
    return {"type": "object", "properties": props, "required": required or list(props),
            "additionalProperties": False}


_S = {"type": "string"}


def _emitir_dossier_schema() -> dict:
    claim = _obj({
        "claim_id": _S, "contenido": _S, "tipo": {"type": "string", "enum": _TIPO_CLAIM},
        "source_url": _S, "cited_text": _S, "source_date": _S, "known_at": _S,
        "materiality": {"type": "string", "enum": _MATERIALITY},
        "verification": {"type": "string", "enum": _VERIF},
    })
    evidencia = _obj({"claim": _S, "source_url": _S, "source_date": _S,
                      "verification": {"type": "string", "enum": _VERIF}})
    escenario = _obj({"tesis": _S, "supuestos": {"type": "array", "items": _S},
                      "contraste_con_calculadoras": _S})
    catalizador = _obj({"descripcion": _S, "fecha_esperada": _S,
                        "tipo": {"type": "string", "enum": _CAT_TIPO}})
    red_flag = _obj({"tipo": _S, "severidad": {"type": "string", "enum": _SEV}, "cita": evidencia})
    falsador = _obj({"afirmacion": _S, "fecha_limite": _S, "que_lo_mataria": _S})
    return _obj({
        "negocio_y_posicion_cuello": _S,
        "claims": {"type": "array", "items": claim},
        "tesis_claims_soporte": {"type": "array", "items": _S},
        "valuacion_que_exige_el_precio": _S,
        "bull": escenario, "bear": escenario,
        "catalizadores": {"type": "array", "items": catalizador},
        "red_flags": {"type": "array", "items": red_flag},
        "falsador": falsador,
        "conviccion_0_1": {"type": "number"},
    })


EMITIR_DOSSIER_TOOL = {
    "name": "emitir_dossier",
    "description": "Emití el dossier final de la empresa. Es tu única salida; llamala cuando terminaste de investigar.",
    "strict": True,
    "input_schema": _emitir_dossier_schema(),
}


@dataclass
class ResultadoAnalista:
    dossier: Dossier | None            # None si el modelo no emitió el dossier (tras el reintento)
    fuentes: list[str]                 # URLs que trajo web_search (procedencia del Verificador)
    meta: AgentMeta


def _render_pack(pack: DataPack) -> str:
    if not pack.puntos:
        return "(sin datos deterministas)"
    return "\n".join(f"- {p.metric} = {p.value} {p.unit} [{p.kind.value}, {p.source.name}]"
                     for p in pack.puntos)


class Analista:
    def __init__(self, agente: Agente):
        self.ag = agente

    def analizar(self, ticker: str, *, data_pack: DataPack, contexto_cuello: str = "",
                 memo_macro: str = "", max_tokens: int = 8192) -> ResultadoAnalista:
        user = (
            f"Empresa a analizar: {ticker}\n\n"
            f"=== DATA PACK (números deterministas, con procedencia) ===\n{_render_pack(data_pack)}\n\n"
            f"=== CONTEXTO DEL CUELLO DE BOTELLA ===\n{contexto_cuello or '(sin contexto de mapa)'}\n\n"
            f"=== MEMO MACRO ===\n{memo_macro or '(sin memo macro)'}\n\n"
            f"Investigá con web_search y después llamá a emitir_dossier."
        )
        payload, fuentes, meta = self.ag.agentico(
            system=_PROMPT, user=user, tools=[WEB_SEARCH_TOOL, EMITIR_DOSSIER_TOOL],
            emisor="emitir_dossier", max_tokens=max_tokens,
        )
        if payload is None:
            return ResultadoAnalista(dossier=None, fuentes=fuentes, meta=meta)
        payload["conviccion_0_1"] = max(0.0, min(1.0, float(payload.get("conviccion_0_1", 0.0))))
        dossier = Dossier.model_validate({"meta": meta.model_dump(), "ticker": ticker.upper(), **payload})
        return ResultadoAnalista(dossier=dossier, fuentes=fuentes, meta=meta)
