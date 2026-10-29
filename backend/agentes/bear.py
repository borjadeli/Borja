"""Agente Bear / Red team (v2 Fase 3, doc 54 §4.4).

Sonnet 5.5 + web_search + tool cliente `emitir_ataque` (strict). Ve el Dossier SIN la convicción
(anti-anclaje) + hechos crudos, y busca contra-evidencia (omisiones, declaraciones tratadas como hechos,
contradicciones). La RÉPLICA del Analista la coordina el orquestador (turno nuevo en el hilo del Analista);
este agente solo produce las objeciones.
"""
from __future__ import annotations

from datetime import date

from pathlib import Path

from backend.agentes.base import Agente
from backend.agentes.schemas import BearAttack, Dossier

PROMPT_VERSION = "bear_v1"
_PROMPT = (Path(__file__).resolve().parent.parent.parent / "prompts" / "bear_v1.md").read_text()

WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 3}

_SEV = ["alta", "media", "baja"]
_VERIF = ["confirmed_by_filing", "company_statement", "media_report", "search_summary",
          "analyst_prior", "hypothesis"]
_S = {"type": "string"}


def _obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


EMITIR_ATAQUE_TOOL = {
    "name": "emitir_ataque",
    "description": "Emití tus objeciones a la tesis. Es tu única salida; llamala cuando terminaste.",
    "strict": True,
    "input_schema": _obj({
        "objeciones": {"type": "array", "items": _obj({
            "afirmacion_atacada": _S,
            "contraevidencia": _S,
            "citas": {"type": "array", "items": _obj({
                "claim": _S, "source_url": _S, "source_date": _S,
                "verification": {"type": "string", "enum": _VERIF}})},
            "severidad": {"type": "string", "enum": _SEV},
        })},
    }),
}


def _render_dossier_sin_conviccion(d: Dossier) -> str:
    """El Bear ve el dossier SIN la convicción (anti-anclaje, doc 54 §4.4)."""
    claims = "\n".join(f"  [{c.claim_id}|{c.tipo}|{c.materiality}] {c.contenido} ({c.source_url or 's/fuente'})"
                       for c in d.claims)
    return (f"Negocio/cuello: {d.negocio_y_posicion_cuello}\n"
            f"Valuación (qué exige el precio): {d.valuacion_que_exige_el_precio}\n"
            f"Bull: {d.bull.tesis} | supuestos: {', '.join(d.bull.supuestos)}\n"
            f"Bear (del analista): {d.bear.tesis}\n"
            f"Falsador: {d.falsador.afirmacion} (límite {d.falsador.fecha_limite})\n"
            f"Claims:\n{claims}")


class Bear:
    def __init__(self, agente: Agente):
        self.ag = agente

    def atacar(self, dossier: Dossier, *, hechos_crudos: str = "", max_tokens: int = 4096) -> BearAttack:
        user = (
            f"Fecha de hoy: {date.today().isoformat()}\n"
            f"Empresa: {dossier.ticker}\n\n=== DOSSIER DEL ANALISTA (sin convicción) ===\n"
            f"{_render_dossier_sin_conviccion(dossier)}\n\n=== HECHOS CRUDOS ===\n"
            f"{hechos_crudos or '(sin hechos adicionales)'}\n\n"
            f"Buscá contra-evidencia y llamá a emitir_ataque."
        )
        payload, _fuentes, meta = self.ag.agentico(
            system=_PROMPT, user=user, tools=[WEB_SEARCH_TOOL, EMITIR_ATAQUE_TOOL],
            emisor="emitir_ataque", max_tokens=max_tokens,
        )
        objeciones = (payload or {}).get("objeciones", [])
        return BearAttack(meta=meta, ticker=dossier.ticker, objeciones=objeciones, replica_analista=None)
