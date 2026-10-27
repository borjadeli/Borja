"""Agente Triage (v2 Fase 3, doc 54 §4.3) — pointwise, barato, disciplinado.

Decide qué nombres merecen el análisis profundo caro de esta semana. Diseño convergido:
- **pointwise** por nombre (no listwise → evita sesgo de posición, reproducible).
- la **incertidumbre se computa DETERMINISTA fuera del LLM** (días desde el último Dossier, hechos
  nuevos desde known_at, distancia a eventos, precio vs tesis).
- Haiku 5.5 **solo juzga la materialidad de los hechos nuevos** — y solo si HAY hechos nuevos (si no,
  no se gasta LLM).
- **posiciones en cartera y nombres con evento fuerte entran siempre** (forzados).
El orquestador toma estas decisiones y selecciona el top-N bajo presupuesto; Triage solo emite la señal.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.agentes.base import Agente
from backend.agentes.schemas import AgentMeta, TriageDecision

PROMPT_VERSION = "triage_v1"
_PROMPT = (Path(__file__).resolve().parent.parent.parent / "prompts" / "triage_v1.md").read_text()

# Schema del payload que juzga Haiku (strict: todo required, additionalProperties false, sin 'razonamiento').
_PAYLOAD_SCHEMA = {
    "type": "object",
    "properties": {
        "materialidad_0_1": {"type": "number"},
        "motivo": {"type": "string"},
    },
    "required": ["materialidad_0_1", "motivo"],
    "additionalProperties": False,
}


@dataclass
class SenalesTriage:
    """Señales DETERMINISTAS por nombre (se calculan fuera del LLM)."""
    dias_desde_dossier: int | None    # None = nunca analizado
    hechos_nuevos: int                # cantidad de hechos nuevos desde el known_at del último Dossier
    dias_a_evento: int | None         # días al próximo catalizador/evento conocido (None = ninguno)
    precio_vs_tesis_pct: float | None  # movimiento de precio vs la tesis (abs %, None = sin dato)
    es_posicion: bool = False
    tiene_evento_fuerte: bool = False  # CRR crítico / ≥N red flags / filing material
    prioridad_cuello: int = 0          # prioridad del cuello de la empresa en el mapa (0-3) — ordena el cupo


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def prioridad(s: SenalesTriage, materialidad: float) -> int:
    """Entero 0–3: qué tan prometedora para análisis profundo esta semana."""
    p = 0.0
    if s.dias_desde_dossier is None:
        p += 1                      # nunca analizada → merece una mirada
    if materialidad >= 0.5:
        p += 1
    if materialidad >= 0.8:
        p += 1
    if s.dias_a_evento is not None and s.dias_a_evento <= 14:
        p += 1
    if s.es_posicion:
        p = max(p, 2)               # las posiciones no bajan de prioridad media
    if s.tiene_evento_fuerte:
        p = max(p, 3)
    return int(max(0, min(3, round(p))))


def incertidumbre(s: SenalesTriage, materialidad: float) -> float:
    """0–1: valor de la información (cuánto cambiaría la visión con más análisis). Determinista."""
    if s.dias_desde_dossier is None:
        base = 0.8                  # nunca analizada → mucho por aprender
    else:
        base = 0.1 + 0.4 * materialidad
        if s.dias_desde_dossier > 90:
            base += 0.2             # dossier viejo → la visión pudo quedar vieja
    if s.precio_vs_tesis_pct is not None:
        base += min(0.3, s.precio_vs_tesis_pct / 100.0)   # precio que se movió fuerte = más incertidumbre
    return round(_clamp01(base), 3)


class Triage:
    def __init__(self, agente: Agente):
        self.ag = agente

    def evaluar(self, ticker: str, senales: SenalesTriage, *,
                resumen_hechos_nuevos: str = "") -> TriageDecision:
        materialidad = 0.0
        motivo_llm = ""
        meta: AgentMeta | None = None
        # LLM SOLO si hay hechos nuevos que juzgar (disciplina de costo).
        if senales.hechos_nuevos > 0 and resumen_hechos_nuevos.strip():
            payload, meta = self.ag.estructurado(
                system=_PROMPT,
                user=f"Empresa: {ticker}\nHechos nuevos desde el último análisis:\n{resumen_hechos_nuevos}",
                payload_schema=_PAYLOAD_SCHEMA, max_tokens=300,
            )
            materialidad = _clamp01(float(payload.get("materialidad_0_1", 0.0)))
            motivo_llm = str(payload.get("motivo", ""))
        if meta is None:
            meta = AgentMeta(agent="triage", prompt_version=PROMPT_VERSION, model=self.ag.model)

        p = prioridad(senales, materialidad)
        inc = incertidumbre(senales, materialidad)
        forzado = senales.es_posicion or senales.tiene_evento_fuerte
        research = forzado or p >= 2

        motivo = motivo_llm or (
            "nunca analizada" if senales.dias_desde_dossier is None else
            "posición en cartera" if senales.es_posicion else
            "evento fuerte" if senales.tiene_evento_fuerte else "sin hechos nuevos materiales")
        return TriageDecision(meta=meta, ticker=ticker.upper(), prioridad_0_3=p,
                              incertidumbre_0_1=inc, research_profundo=research, motivo=motivo)
