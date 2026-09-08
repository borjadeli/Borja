"""Escalera de add-on (doc 46, CERRADA por triangulación) — la MECÁNICA determinista (funciones puras).

Reframe (IA1+IA2 idéntico): la escalera NO es un módulo — es un `stage` que escala el techo del `min()` que ya
existe: `w_target = STAGE_FRACTION[stage] × live_cap`. `stage` sube SOLO por hechos citados (triggers). Acá viven
las funciones puras (w_target, gate de add A1-A6, regla de TRIM). El wire a posiciones stateful + la extracción
de los hechos de milestone (triggers) es Bloque 4.

Las DOS reglas de oro (doc 46):
- **Evidencia DISPARA · valuación VETEA · precio NUNCA dispara.** Un add exige trigger citado + estado admisible al
  precio de EJECUCIÓN + margen de falsación NO deteriorado (derivada, anti "sapo hervido") + target > peso.
- **La valuación CONGELA, no VENDE** (modo de falla #1: cortar al ganador). Trim SOLO por PESO (drift) o FALSACIÓN,
  NUNCA por caro ni por % de ganancia. El ganador puede redefinir la cartera, no destruirla.
"""
from __future__ import annotations

from backend.nucleo import politica

_ADMISIBLE_ADD = {"COVERED", "STRETCH"}          # OPTION_PRICED solo binaria 0→1; NON_UNDERWRITABLE nunca


def stage_fraction(stage: int, *, binaria: bool = False) -> float:
    """Fracción del techo autorizada por el `stage` (doc 46 §2). Discreta y fija. stage fuera de rango → clamp."""
    tabla = politica.STAGE_FRACTION_BINARIA if binaria else politica.STAGE_FRACTION_COMERCIAL
    if stage < 0:
        return 0.0
    return tabla[min(stage, len(tabla) - 1)]


def w_target(stage: int, live_cap: float, *, binaria: bool = False) -> float:
    """Peso objetivo = STAGE_FRACTION[stage] × LIVE_CAP (doc 46 §0). El techo (min de caps) es de siempre; la
    escalera decide cuánto de ese techo se despliega."""
    return stage_fraction(stage, binaria=binaria) * (live_cap or 0.0)


def probe_f0(n_triggers_4q: int, meses_prox_trigger: float | None, hay_trigger_falsable: bool) -> float:
    """Fracción del techo para el PROBE inicial, por DENSIDAD de triggers (doc 46 §4, IA1). Sin trigger falsable →
    1.0 (entrás al techo o no entrás; un probe con triggers vagos es 'una posición chica con una historia encima')."""
    if not hay_trigger_falsable:
        return 1.0
    if n_triggers_4q >= 2:
        return 0.30
    if meses_prox_trigger is not None and meses_prox_trigger > 12:
        return 0.50
    return 0.30


def puede_add(*, trigger_cumplido: bool, estado_val: str, es_binaria_0a1: bool,
              margen_actual: float | None, margen_previo: float | None,
              w_actual: float, w_target_next: float, techo: float,
              add_ons_usados: int, max_add_ons: int) -> dict:
    """Gate de ADD (doc 46 §1, A1-A6). Determinista. Devuelve {permite, motivo}. Jerarquía: evidencia dispara
    (A1), valuación vetea (A2), margen de falsación no deteriorado (A3), target>peso (A4), presupuesto (A6)."""
    if not trigger_cumplido:                                          # A1 — evidencia dispara
        return {"permite": False, "motivo": "sin trigger citado cumplido (el precio NUNCA dispara)"}
    admisible = estado_val in _ADMISIBLE_ADD or (es_binaria_0a1 and estado_val == "OPTION_PRICED")
    if not admisible:                                                 # A2 — valuación vetea
        return {"permite": False, "motivo": f"valuación {estado_val} no admisible para add (veto de precio)"}
    if margen_actual is not None and margen_previo is not None:       # A3 — margen de falsación (derivada)
        if margen_actual < margen_previo - politica.TOL_MARGEN_FALSACION_A:
            return {"permite": False, "motivo": f"margen de falsación deteriorado ({margen_actual:.1f}<{margen_previo:.1f}−tol) → sapo hervido"}
    if w_target_next <= w_actual + politica.HISTERESIS_ADD * (techo or 0.0):   # A4 — target > peso + histéresis
        return {"permite": False, "motivo": "target ≤ peso actual (+histéresis) → SATISFIED_BY_DRIFT, sin orden"}
    if add_ons_usados >= max_add_ons:                                 # A6 — presupuesto del nombre
        return {"permite": False, "motivo": f"presupuesto de add-ons agotado ({max_add_ons})"}
    return {"permite": True, "motivo": "add admisible: evidencia + valuación + margen + target > peso"}


def regla_trim(*, w_actual: float, cap_anchor: float, estado_val: str, tesis_falsificada: bool,
               supervivencia_falla: bool, nav_cap: float | None = None) -> dict:
    """Regla de TRIM (doc 46 §5) — LA guarda contra el modo de falla #1 (cortar al ganador). La valuación CONGELA,
    NO vende. Devuelve {accion, w_objetivo, motivo}. accion ∈ {KILL, TRIM, HOLD}.
      · falsación/supervivencia rota → KILL (salida, NO es trim).
      · peso > DRIFT_LIMIT → TRIM a TRIM_TARGET (el ganador puede redefinir la cartera, no destruirla).
      · si NO → HOLD. NUNCA trim por valuación cara ni por % de ganancia."""
    if tesis_falsificada or supervivencia_falla:
        return {"accion": "KILL", "w_objetivo": 0.0, "motivo": "tesis falsificada / supervivencia rota → salida (no trim)"}
    abs_cap = nav_cap if nav_cap is not None else politica.ABSOLUTE_SINGLE_NAME_CAP
    drift_limit = min(politica.DRIFT_MULT * (cap_anchor or 0.0), abs_cap)
    if w_actual > drift_limit:
        objetivo = politica.TRIM_TARGET_FRAC * drift_limit
        return {"accion": "TRIM", "w_objetivo": round(objetivo, 4),
                "motivo": f"peso {w_actual:.1%} > DRIFT_LIMIT {drift_limit:.1%} (concentración) → trim a {objetivo:.1%}"}
    # NON_UNDERWRITABLE por PRECIO / OPTION_PRICED → congela, NO vende (deja correr al ganador).
    return {"accion": "HOLD", "w_objetivo": round(w_actual, 4),
            "motivo": f"HOLD: peso ≤ DRIFT_LIMIT; valuación {estado_val} CONGELA adds pero NO vende (no cortar al ganador)"}
