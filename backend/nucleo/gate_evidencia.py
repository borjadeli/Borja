"""Gate sobre el fact store (doc 22 §3 y §8bis) — el 🔒 que conecta evidencia → decisión.

Lee del SNAPSHOT del fact store y aplica la vara con la semántica nueva:
  - solo DIRECT/DERIVED alimentan hard items (UNKNOWN/INFERRED no),
  - distingue `no_pasa` (un hecho gate-crítico es FALSE) de `NO_EVALUABLE` (es UNKNOWN →
    cuarentena, con la pregunta que lo resolvería),
  - la dimensión DEMANDA usa existencia-abre + tier de magnitud (VALIDATED/COMMITTED/REALIZED),
    NO pasa/no-pasa: la magnitud gobierna el cap, no la puerta (§8bis).

Compone con `gate.py` (el checklist estructural determinista se mantiene); esta capa lo
alimenta desde la evidencia y post-procesa el resultado. Determinista y puro.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.nucleo import fact_store as FS

# Tier de magnitud de la demanda (§8bis): la existencia abre; la magnitud fija el cap.
TIER_MAGNITUD = {"UNKNOWN": 0, "VALIDATED": 1, "COMMITTED": 2, "REALIZED": 3}


@dataclass
class ItemSpec:
    fact_key: str
    arquetipos: tuple[str, ...]
    dimension: str          # "estructura" (binario) | "demanda" (existencia+tier)
    pregunta: str           # para NO_EVALUABLE (la que dispara la búsqueda dirigida)


# Set base (se amplía con el gold set / gate.py). fact_key ↔ ítem del gate.
ITEMS: list[ItemSpec] = [
    ItemSpec("organic_growth_available", ("Growth",), "estructura",
             "¿el crecimiento es orgánico ≥50% con fuente A?"),
    ItemSpec("madura_hecho_vigente", ("Madura",), "estructura",
             "¿hay un hecho ocurrido vigente en el último filing/transcript?"),
    ItemSpec("growth_hecho_continuidad", ("Growth", "Tracción"), "demanda",
             "¿hay continuidad/compromiso de demanda (RPO/backlog/contrato/orden de cliente)?"),
]


def _fact(snapshot: dict, key: str):
    """(value, support_type) del snapshot. Acepta NxFact o dict. Ausente → (None, UNKNOWN)."""
    f = snapshot.get(key)
    if f is None:
        return None, "UNKNOWN"
    if hasattr(f, "support_type"):
        return FS._dec(f.value), f.support_type
    return f.get("value"), (f.get("support_type") or "UNKNOWN")


def evaluar_desde_evidencia(snapshot: dict, arquetipo: str,
                            items: list[ItemSpec] | None = None) -> dict:
    """Corre la vara sobre el snapshot. Devuelve estado + tier de magnitud + preguntas abiertas.

    estado: 'pasa' | 'no_pasa' | 'NO_EVALUABLE'.
    tier_magnitud: 0-3 (gobierna el cap; None si el arquetipo no tiene dimensión demanda).
    preguntas: lista {item, pregunta} para la cuarentena (NO_EVALUABLE).
    """
    items = items or ITEMS
    fallos: list[str] = []
    preguntas: list[dict] = []
    tier: int | None = None

    for it in items:
        if arquetipo not in it.arquetipos:
            continue
        val, sup = _fact(snapshot, it.fact_key)
        fundado = sup in ("DIRECT", "DERIVED") and val is not None

        if it.dimension == "demanda":
            tier = tier or 0            # el arquetipo tiene dimensión demanda
            if not fundado or val is False:
                # existencia no acreditada → NO_EVALUABLE (cuarentena), NO rechazo
                preguntas.append({"item": it.fact_key, "pregunta": it.pregunta})
            else:
                estado_dem = val if isinstance(val, str) and val in TIER_MAGNITUD else "VALIDATED"
                tier = max(tier, TIER_MAGNITUD.get(estado_dem, 1))
            continue

        # estructura: binario, solo DIRECT/DERIVED
        if not fundado:
            preguntas.append({"item": it.fact_key, "pregunta": it.pregunta})  # UNKNOWN → NO_EVALUABLE
        elif val is False:
            fallos.append(it.fact_key)                                         # FALSE → no_pasa

    if fallos:
        estado = "no_pasa"
    elif preguntas:
        estado = "NO_EVALUABLE"       # falta evidencia → cuarentena, no rechazo
    else:
        estado = "pasa"
    return {"estado": estado, "tier_magnitud": tier, "fallos": fallos,
            "preguntas": preguntas, "arquetipo": arquetipo}
