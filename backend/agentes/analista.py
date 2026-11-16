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
# delta-deep (doc 76): re-análisis barato → menos búsquedas (solo valida lo nuevo, no re-investiga de cero).
DELTA_WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 2}

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
        # cash bridge por escenario (doc 83 F1): fuentes y usos hasta el año terminal, en USD. 0 si no aplica.
        "fcf_cumulative": {"type": "number"},              # FCF acumulado a T (incluye CAPEX; negativo = quema)
        "new_equity_proceeds": {"type": "number"},         # caja neta por emisión primaria
        "new_equity_shares": {"type": "number"},           # acciones nuevas emitidas
        "new_debt": {"type": "number"}, "debt_repaid": {"type": "number"},
        "distributions": {"type": "number"},               # dividendos + recompras
        "dilucion_sbc": {"type": ["number", "null"]},      # dilución SBC del escenario (null → usa dilucion_esperada_pct)
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


def _finalizar(payload, fuentes, meta, ticker: str) -> ResultadoAnalista:
    """Post-procesa el payload del Analista (clamps + normalización de escala + validación) → ResultadoAnalista.
    Compartido por `analizar` (full) y `actualizar` (delta) para que el delta herede las mismas garantías."""
    if payload is None:
        return ResultadoAnalista(dossier=None, fuentes=fuentes, meta=meta)
    payload["conviccion_0_1"] = max(0.0, min(1.0, float(payload.get("conviccion_0_1", 0.0))))
    inv = payload.get("invertibilidad")
    if isinstance(inv, dict) and "traccion_0_4" in inv:
        inv["traccion_0_4"] = max(0, min(4, int(inv.get("traccion_0_4") or 0)))
    for e in (payload.get("escenarios") or []):
        if isinstance(e, dict):
            if e.get("prob") is not None:
                e["prob"] = max(0.0, min(1.0, float(e["prob"])))
            if e.get("anios") is not None:
                e["anios"] = max(1, int(e["anios"]))
    dsp = payload.get("dilucion_esperada_pct")                  # % → fracción (smoke 2026-11-03)
    if dsp is not None:
        payload["dilucion_esperada_pct"] = (float(dsp) / 100.0) if float(dsp) > 1.0 else float(dsp)
    try:
        dossier = Dossier.model_validate({"meta": meta.model_dump(), "ticker": ticker.upper(), **payload})
    except Exception as e:  # noqa: BLE001 — dossier incompleto → sin_dossier, no crash
        _log.warning("analista: dossier inválido para %s (%s) → sin_dossier", ticker, e)
        return ResultadoAnalista(dossier=None, fuentes=fuentes, meta=meta)
    return ResultadoAnalista(dossier=dossier, fuentes=fuentes, meta=meta)


def _render_previo(d: Dossier) -> str:
    """Render COMPACTO del dossier previo para el delta-deep (no re-manda todo; lo esencial de la tesis)."""
    inv = d.invertibilidad
    esc = " · ".join(f"{e.nombre} {e.metrica_terminal:.2e}×{e.multiplo_salida}@{e.anios}a p={e.prob}"
                     for e in d.escenarios) or "(sin escenarios)"
    return (f"Negocio/cuello: {d.negocio_y_posicion_cuello}\n"
            f"Qué exige el precio: {d.valuacion_que_exige_el_precio}\n"
            f"Bull: {d.bull.tesis}\nBear: {d.bear.tesis}\n"
            f"Falsador: {d.falsador.afirmacion} (límite {d.falsador.fecha_limite})\n"
            f"Clasificación: {inv.analyst_classification if inv else '?'} · tracción "
            f"{inv.traccion_0_4 if inv else '?'}/4\nEscenarios: {esc}\nConvicción previa: {d.conviccion_0_1}")


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
        return _finalizar(payload, fuentes, meta, ticker)

    def actualizar(self, ticker: str, dossier_previo: Dossier, *, data_pack: DataPack,
                   evento_resumen: str = "", contexto_cuello: str = "", memo_macro: str = "",
                   max_tokens: int = 16384) -> ResultadoAnalista:
        """DELTA-DEEP (doc 76): re-análisis BARATO sobre la tesis previa + lo nuevo. Menos web (2 vs 6): no
        re-investiga desde cero, solo valida el evento/los números nuevos y ACTUALIZA lo que cambió. Emite el
        dossier COMPLETO y actualizado (mismo schema → el Verificador/PM lo tratan igual)."""
        user = (
            f"Fecha de hoy: {date.today().isoformat()}\n"
            f"Empresa: {ticker} — ACTUALIZACIÓN (delta) de un dossier previo, NO análisis desde cero.\n\n"
            f"=== TU DOSSIER PREVIO ===\n{_render_previo(dossier_previo)}\n\n"
            f"=== QUÉ CAMBIÓ (evento/filings nuevos desde ese dossier) ===\n{evento_resumen or '(sin resumen)'}\n\n"
            f"=== DATA PACK ACTUALIZADO (números deterministas) ===\n{_render_pack(data_pack)}\n\n"
            f"=== CONTEXTO DEL CUELLO ===\n{contexto_cuello or '(sin contexto)'}\n\n"
            f"=== MEMO MACRO ===\n{memo_macro or '(sin memo)'}\n\n"
            f"=== TASAS BASE (ancla de la P(bull)) ===\n{_tabla_tasas_base()}\n\n"
            f"Verificá SOLO lo nuevo con web_search (pocas búsquedas) y volvé a emitir el dossier COMPLETO "
            f"con lo que cambió actualizado y lo que sigue válido conservado. Si el evento ROMPE la tesis, "
            f"decílo en bull/bear/falsador. Llamá a emitir_dossier."
        )
        payload, fuentes, meta = self.ag.agentico(
            system=_PROMPT, user=user, tools=[DELTA_WEB_SEARCH_TOOL, EMITIR_DOSSIER_TOOL],
            emisor="emitir_dossier", max_tokens=max_tokens,
        )
        return _finalizar(payload, fuentes, meta, ticker)
