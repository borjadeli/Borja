"""Agente Analista (v2 Fase 3, doc 54 §4.1/§4.2) — la pieza central, validada en spike.

Opus 5.5 + `web_search` + tool cliente `emitir_dossier` (strict). Investiga agénticamente y emite el
Dossier como el `input` de ese tool (NO `output_config.format`, que es incompatible con las citas de
web search). No se puede forzar `tool_choice` con thinking always-on → `base.agentico` reintenta una vez.
Las URLs que trajo web_search se devuelven como `fuentes` (procedencia para el Verificador).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from backend.agentes.base import Agente
from backend.agentes.provenance import DataPack
from backend.agentes.schemas import AgentMeta, Dossier
from backend.agentes.tasas_base import render_tabla as _tabla_tasas_base

_log = logging.getLogger("agentes.analista")
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
        # claim NUMÉRICO: a qué métrica del data pack se contrasta (por id). "" / null si no es numérico.
        "ref_metrica": _S, "valor_num": {"type": ["number", "null"]}, "escala": _S, "periodo": _S,
    })
    evidencia = _obj({"claim": _S, "source_url": _S, "source_date": _S,
                      "verification": {"type": "string", "enum": _VERIF}})
    escenario = _obj({"tesis": _S, "supuestos": {"type": "array", "items": _S},
                      "contraste_con_calculadoras": _S})
    catalizador = _obj({"descripcion": _S, "fecha_esperada": _S,
                        "tipo": {"type": "string", "enum": _CAT_TIPO}})
    red_flag = _obj({"tipo": _S, "severidad": {"type": "string", "enum": _SEV}, "cita": evidencia})
    vara_externa = _obj({
        "tipo": {"type": "string", "enum": ["hito_tercero", "economico", "competitivo"]},
        "metrica": _S, "umbral": _S, "comparador": _S, "fuente_medicion": _S,
        "accion_si_dispara": _S, "no_aplica": {"type": "boolean"}, "razon_no_aplica": _S,
    })
    falsador = _obj({"afirmacion": _S, "fecha_limite": _S, "que_lo_mataria": _S, "vara_externa": vara_externa})
    # ficha de invertibilidad temporal (doc 70 D2) — el análisis de FUTURO
    invertibilidad = _obj({
        "riesgo_remanente": {"type": "string", "enum": ["cientifico", "ingenieria", "comercial", "escala"]},
        "next_value_inflection": _S, "months_to_inflection": {"type": ["integer", "null"]},
        "fundamental_impact_if_successful": _S, "independent_evidence": _S,
        "traccion_0_4": {"type": "integer"},
        "milestone_funding_coverage": _S, "stress_funding_gap": _S, "subsequent_capital_need": _S,
        "dilution_exposure": _S, "price_implied_requirements": _S, "dependencia_politica_publica": _S,
        "critical_unverified_assumption": _S, "test_de_atraso": _S,
        "analyst_classification": {"type": "string", "enum": ["core", "satelite", "especulativa", "watchlist"]},
    })
    # escenarios NUMÉRICOS del puente económico (doc 74 D1): el analista pone métrica/múltiplo/año/prob; el
    # bear debe ser "la tesis FALLA" (≈ caja remanente). Comparten horizonte (MOIC comparable).
    escenario_val = _obj({
        "nombre": {"type": "string", "enum": ["bull", "base", "bear"]},
        "metrica_terminal": {"type": "number"},
        "tipo_metrica": {"type": "string", "enum": ["revenue", "ebitda"]},
        "multiplo_salida": {"type": "number"},
        "margen_terminal_pct": {"type": ["number", "null"]},
        "anios": {"type": "integer"},
        "prob": {"type": "number"},
        "ancla_tasa_base": {"type": ["string", "null"]},   # D3: id de fila de tasas base, o "sin_muestra"
    })
    return _obj({
        "negocio_y_posicion_cuello": _S,
        "claims": {"type": "array", "items": claim},
        "tesis_claims_soporte": {"type": "array", "items": _S},
        "valuacion_que_exige_el_precio": _S,
        "bull": escenario, "bear": escenario,
        "catalizadores": {"type": "array", "items": catalizador},
        "red_flags": {"type": "array", "items": red_flag},
        "falsador": falsador,
        "invertibilidad": invertibilidad,
        "escenarios": {"type": "array", "items": escenario_val},
        "caja_neta_terminal": {"type": ["number", "null"]},
        "dilucion_esperada_pct": {"type": ["number", "null"]},
        "conviccion_0_1": {"type": "number"},
    })


EMITIR_DOSSIER_TOOL = {
    "name": "emitir_dossier",
    "description": "Emití el dossier final de la empresa. Es tu única salida; llamala cuando terminaste de investigar.",
    # NO strict: con la ficha de invertibilidad el schema supera el límite de grammar de la API strict
    # ("compiled grammar too large", detectado en el smoke). La garantía de formato la da la validación
    # pydantic post-hoc (Dossier.model_validate → sin_dossier si no cumple), más robusta y sin límite de tamaño.
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
    # muestra known_at (point-in-time) de cada dato → el Analista ve qué tan fresca es su evidencia (r3 #1b).
    lineas = [f"- {p.metric} = {p.value} {p.unit} [{p.kind.value}, {p.source.name}, known_at={p.known_at}]"
              for p in pack.puntos]
    # "último filing periódico": solo known_at de datos XBRL/filing — NO del mercado (Yahoo, known_at=hoy),
    # que contaminaría la fecha (mismo bug que se corrigió en el Verificador; r4 #3).
    knowns = [p.known_at for p in pack.puntos
              if p.known_at is not None and "xbrl" in (p.source.name or "").lower()]
    if knowns:
        lineas.append(f"(último filing periódico disponible: {max(knowns)})")
    return "\n".join(lineas)


class Analista:
    def __init__(self, agente: Agente):
        self.ag = agente

    def analizar(self, ticker: str, *, data_pack: DataPack, contexto_cuello: str = "",
                 memo_macro: str = "", max_tokens: int = 16384) -> ResultadoAnalista:
        user = (
            f"Fecha de hoy: {date.today().isoformat()}\n"
            f"Empresa a analizar: {ticker}\n\n"
            f"=== DATA PACK (números deterministas, con procedencia) ===\n{_render_pack(data_pack)}\n\n"
            f"=== CONTEXTO DEL CUELLO DE BOTELLA ===\n{contexto_cuello or '(sin contexto de mapa)'}\n\n"
            f"=== MEMO MACRO ===\n{memo_macro or '(sin memo macro)'}\n\n"
            f"=== TASAS BASE DISPONIBLES (ancla de la P(bull); elegí UNA id o 'sin_muestra') ===\n"
            f"{_tabla_tasas_base()}\n\n"
            f"Investigá con web_search y después llamá a emitir_dossier."
        )
        payload, fuentes, meta = self.ag.agentico(
            system=_PROMPT, user=user, tools=[WEB_SEARCH_TOOL, EMITIR_DOSSIER_TOOL],
            emisor="emitir_dossier", max_tokens=max_tokens,
        )
        if payload is None:
            return ResultadoAnalista(dossier=None, fuentes=fuentes, meta=meta)
        payload["conviccion_0_1"] = max(0.0, min(1.0, float(payload.get("conviccion_0_1", 0.0))))
        inv = payload.get("invertibilidad")
        if isinstance(inv, dict) and "traccion_0_4" in inv:     # acotar el entero (el schema no fija rango)
            inv["traccion_0_4"] = max(0, min(4, int(inv.get("traccion_0_4") or 0)))
        for e in (payload.get("escenarios") or []):             # acotar prob/años de los escenarios (doc 74 D1)
            if isinstance(e, dict):
                if e.get("prob") is not None:
                    e["prob"] = max(0.0, min(1.0, float(e["prob"])))
                if e.get("anios") is not None:
                    e["anios"] = max(1, int(e["anios"]))
        try:
            dossier = Dossier.model_validate({"meta": meta.model_dump(), "ticker": ticker.upper(), **payload})
        except Exception as e:  # noqa: BLE001 — dossier incompleto (p.ej. sin falsador) → sin_dossier, no crash
            _log.warning("analista: dossier inválido para %s (%s) → sin_dossier", ticker, e)
            return ResultadoAnalista(dossier=None, fuentes=fuentes, meta=meta)
        return ResultadoAnalista(dossier=dossier, fuentes=fuentes, meta=meta)
