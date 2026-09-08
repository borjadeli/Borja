"""Elegibilidad por 3 PILARES CONJUNTIVOS → tier (doc 33 / doc 34 §1, refactor 2026-08).

El output NO es un ranking cardinal (distinguir #7 de #8 es ruido) — es elegibilidad conjuntiva. Los
3 pilares se componen SIN sumar: una debilidad CRÍTICA en cualquiera topea el tier (nada de rescatar
un runway fatal con un TAM lindo). La prioridad DENTRO de la elegibilidad la da el Δ de evidencia.

Los 3 pilares (doc 33; antes eran 4 con valuación — doc 26):
  1. demanda_cuello   — demanda real, materialidad, madurez, posición en el cuello
  2. economia         — márgenes, unit economics, pricing, recurrencia, FCF
  3. ejecucion        — track record, guidance cumplido, capital allocation, dilución (por ACCIÓN)

**VALUACIÓN NO es pilar acá (doc 33/34): es un GATE SEPARADO de falsificación** (el falsador CAGR
cohort-free de `bridge.py`, que mata las tesis ya priceadas → carril). Fragility/CRR/red-flags/liquidez
también quedan FUERA (gates/caps). Este módulo solo compone la ELEGIBILIDAD por los 3 pilares.

Determinista y puro: recibe los pilares ya evaluados (banda + confianza + hechos citados) y
devuelve el tier + qué pilar lo limita. Los motores que producen cada banda se enchufan aparte.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class Banda(IntEnum):
    CRITICO = 0     # debilidad que descalifica (no compensa)
    DEBIL = 1
    SUFICIENTE = 2
    FUERTE = 3


PILARES = ("demanda_cuello", "economia", "ejecucion")   # valuación = gate separado (doc 33/34), no pilar


@dataclass
class Pilar:
    nombre: str
    banda: Banda
    confianza: str = "suficiente"        # "suficiente" | "insuficiente" (cobertura/UNKNOWN)
    hechos: list = field(default_factory=list)  # evidencia citada [{claim, valor, fuente_tier, ...}]
    nota: str = ""
    es_veto_supervivencia: bool = False  # el CRÍTICO es de SUPERVIVENCIA/integridad (restatement, going-concern,
                                         # dilución tóxica) → veto DURO legítimo (doc 39 §2.1). Un CRÍTICO de
                                         # "no va a funcionar" (unit economics, demanda floja) NO va acá.

    def banda_efectiva(self) -> Banda:
        """La banda no puede tener más confianza que su evidencia: confianza insuficiente
        topea en SUFICIENTE (nunca FUERTE) — doc 26 §8/§10."""
        if self.confianza != "suficiente" and self.banda == Banda.FUERTE:
            return Banda.SUFICIENTE
        return self.banda


@dataclass
class Evaluacion:
    ticker: str
    tier: str                      # SCORE no-compensatorio: "A" (core) | "B" (satélite) | "C" (débil, PROBE/watch)
    pilares: list                  # [Pilar]
    delta_evidencia: str           # "sube" | "estable" | "baja" — PRIORIDAD, no tier
    pilar_limitante: str | None    # qué pilar topea el tier
    motivo: str
    arquetipo: str | None = None   # Madura/Growth/Tracción/Pre-revenue/Binary (define caps + tasa)
    hard_cap: float | None = None  # techo de sizing = cap_celda(arquetipo, fragility) [× CRR pendiente]
    veto_supervivencia: bool = False  # ÚNICA exclusión dura (doc 39 §2.1). tier C SIN veto = candidato débil
                                      # (WATCH/PROBE), NO excluido — el determinismo no dice "no va a funcionar".
    veto_facts_completos: bool = True  # ¿los hechos de VETO de supervivencia (restatement…) están EXTRAÍDOS?
                                       # Ausencia de dato ≠ ausencia de veto (lección SYM 2026-08-31): si están
                                       # UNKNOWN, no se puede comprometer capital → abstención (WATCH), no underwrite.

    @property
    def elegible(self) -> bool:
        """Elegibilidad = SOBREVIVIÓ (no hay veto de supervivencia). NO = 'score alto' (doc 39 §2.1: gates→
        scoring). Un tier C sin veto sigue siendo candidato (débil) — se rescata por juicio/PROBE, no se excluye."""
        return not self.veto_supervivencia


def asignar_tier(pilares: list[Pilar]) -> tuple[str, str | None, str, bool]:
    """Composición NO-COMPENSATORIA con SCORING (doc 39 §2.1, rebalanceo 2026-08). Devuelve
    (tier, pilar_limitante, motivo, veto_supervivencia).

    Cambio de paradigma vs el gate conjuntivo viejo:
      · La ÚNICA exclusión dura es el **veto de supervivencia** (restatement/integridad, going-concern,
        dilución tóxica) → tier C + veto=True. El determinismo conserva autoridad TOTAL para decir "no sobrevive".
      · Un CRÍTICO de "NO VA A FUNCIONAR" (unit economics rotas, demanda floja) YA NO excluye: pisa el score a
        C pero el nombre sigue siendo CANDIDATO (débil → WATCH/PROBE). El determinismo tiene CERO autoridad para
        decir "no va a funcionar" (eso lo juzga el canal de juicio, Bloque 3).
      · **UNKNOWN ≠ negativo:** un pilar ausente o con confianza insuficiente NO cuenta como CRÍTICO (no coacciona
        'no sé' a 'no'). Baja la confianza (topea FUERTE→SUFICIENTE), no descalifica."""
    # 1) Veto de supervivencia: la única exclusión dura.
    vetos = [p.nombre for p in pilares if p.es_veto_supervivencia]
    if vetos:
        return "C", vetos[0], f"veto de supervivencia en {vetos[0]}", True

    faltan = [n for n in PILARES if n not in {x.nombre for x in pilares}]
    ef = {p.nombre: p.banda_efectiva() for p in pilares}
    minb = min(ef.values()) if ef else Banda.CRITICO
    n_fuerte = sum(1 for b in ef.values() if b == Banda.FUERTE)
    criticos = [n for n, b in ef.items() if b == Banda.CRITICO]   # CRÍTICOS NO-supervivencia (los de veto ya salieron)

    # 2) Scoring no-compensatorio (sin veto): el peor pilar topea el tier, pero NADIE queda excluido.
    if not faltan and minb >= Banda.SUFICIENTE and n_fuerte >= 2:
        return "A", None, "3 pilares ≥ suficiente, ≥2 fuertes", False
    if minb >= Banda.DEBIL:
        debil = next((n for n, b in ef.items() if b == Banda.DEBIL), None)
        motivo = f"limita: {debil}" if debil else ("cobertura incompleta" if faltan else "no llega a 2 fuertes")
        return "B", debil, motivo, False
    # min == CRÍTICO (no-supervivencia) o cobertura muy pobre → C DÉBIL, pero CANDIDATO (no excluido).
    lim = criticos[0] if criticos else None
    motivo = (f"débil: {lim} (no va a funcionar aún — candidato PROBE, no excluido)" if lim
              else "evidencia insuficiente (candidato WATCH)")
    return "C", lim, motivo, False


def evaluar(ticker: str, pilares: list[Pilar], *, delta: str = "estable") -> Evaluacion:
    """Arma la Evaluacion: tier no-compensatorio (score) + veto de supervivencia + Δ de evidencia (prioridad)."""
    tier, limitante, motivo, veto = asignar_tier(pilares)
    return Evaluacion(ticker=ticker, tier=tier, pilares=pilares, delta_evidencia=delta,
                      pilar_limitante=limitante, motivo=motivo, veto_supervivencia=veto)


# Orden de prioridad para el selector: primero por tier, DENTRO del tier por Δ de evidencia
# (el nivel = elegibilidad/tier; el delta = quién está re-rateando AHORA — doc 26 §5).
_TIER_ORD = {"A": 0, "B": 1, "C": 2}
_DELTA_ORD = {"sube": 0, "estable": 1, "baja": 2}


def clave_prioridad(e: Evaluacion) -> tuple:
    return (_TIER_ORD.get(e.tier, 9), _DELTA_ORD.get(e.delta_evidencia, 9))
