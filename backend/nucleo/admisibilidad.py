"""Reglas de admisibilidad — el contrato fact store → scenario compiler (doc 27 §5, §6).

La ELEGIBILIDAD de un hecho para el bull/base/bear operable NO la decide el LLM ni la extracción:
la decide una TABLA determinista, keyed por (fact_key, evidence_class). El extractor solo aporta
un atributo clasificable y citado — `evidence_class` = fuerza de fuente (doc 27 §6.6) —; esta capa
decide si eso entra a la valuación y con qué política de haircut. Así el LLM nunca decide un valor
(doc 27 §1): el punto más peligroso del sistema (hecho→bull/bear) queda gobernado por regla.

El CONTENIDO de la tabla (haircuts, excepciones) se puebla/triangula aparte; acá está el mecanismo
y un default conservador por clase.
"""
from __future__ import annotations

# --- Fuerza de fuente (doc 27 §6.6), de más fuerte a más débil ---
REPORTED_AUDITED = "reported_audited"            # resultado reportado/auditado
CONTRACT_COUNTERPARTY = "contract_counterparty"  # contrato o dato de contraparte
REGULATORY_THIRDPARTY = "regulatory_thirdparty"  # dato regulatorio o de tercero
GUIDANCE = "guidance"                            # guidance formal
MANAGEMENT_CLAIM = "management_claim"            # afirmación de management
PROMOTIONAL = "promotional"                      # presentación promocional
EVIDENCE_CLASSES = (REPORTED_AUDITED, CONTRACT_COUNTERPARTY, REGULATORY_THIRDPARTY,
                    GUIDANCE, MANAGEMENT_CLAIM, PROMOTIONAL)

# --- Missingness (doc 27 §6.4): "sin evidencia" ≠ "cero". Vocabulario de `estado`. ---
REPORTED_ZERO = "reported_zero"        # el filing dice explícitamente 0
NOT_APPLICABLE = "not_applicable"      # no aplica a este negocio
NOT_DISCLOSED = "not_disclosed"        # existe pero no se divulga
NOT_FOUND = "not_found"                # no se encontró en el retrieval
CONTRADICTORY = "contradictory"        # fuentes en conflicto
MISSINGNESS = (REPORTED_ZERO, NOT_APPLICABLE, NOT_DISCLOSED, NOT_FOUND, CONTRADICTORY)

# --- Política de haircut (doc 27 §5): de dónde sale el recorte. NUNCA "juicio razonable". ---
SIN_HAIRCUT = "sin_haircut"                     # revenue reconocido = 100%
CONVERSION_HISTORICA = "conversion_historica"   # backlog → conversión histórica empresa/cohorte
SOLO_IRREVOCABLE = "solo_irrevocable"           # award con condiciones → solo la parte irrevocable

# Default por clase: qué entra al bull operable (doc 27 §3: Realizado + Contratado).
# Guidance / management claim / promocional = 0 en el bull (van al option ledger).
_DEFECTO: dict[str, dict] = {
    REPORTED_AUDITED:      {"valuation_eligible": True,  "haircut": SIN_HAIRCUT},
    CONTRACT_COUNTERPARTY: {"valuation_eligible": True,  "haircut": CONVERSION_HISTORICA},
    REGULATORY_THIRDPARTY: {"valuation_eligible": True,  "haircut": SIN_HAIRCUT},
    GUIDANCE:              {"valuation_eligible": False, "haircut": None},
    MANAGEMENT_CLAIM:      {"valuation_eligible": False, "haircut": None},
    PROMOTIONAL:           {"valuation_eligible": False, "haircut": None},
}

# Excepciones por (fact_key, evidence_class) — manda sobre el default. Se puebla con triangulación
# (ahí vive el único grado de libertad discrecional del sistema, doc 27 §5 / IA 2).
_OVERRIDES: dict[tuple[str, str], dict] = {}


def es_admisible(fact_key: str, evidence_class: str | None) -> dict:
    """¿El hecho entra al bull operable, y con qué haircut? Determinista.

    Sin `evidence_class` reconocida → NO admisible (conservador: sin clase, no se valúa).
    Devuelve {valuation_eligible, haircut, motivo}.
    """
    if evidence_class not in EVIDENCE_CLASSES:
        return {"valuation_eligible": False, "haircut": None,
                "motivo": f"evidence_class no reconocida: {evidence_class!r} → no valuable"}
    regla = _OVERRIDES.get((fact_key, evidence_class)) or _DEFECTO[evidence_class]
    origen = "override" if (fact_key, evidence_class) in _OVERRIDES else "default por clase"
    return {"valuation_eligible": regla["valuation_eligible"], "haircut": regla["haircut"],
            "motivo": f"{origen}: {evidence_class}"}
