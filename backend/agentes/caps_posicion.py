"""P1 (doc 91 §7, blueprint IA2 §1 + review fail-closed IA1) — CAP de posición. MODO SOMBRA: computa el techo
económico y REGISTRA qué cap ligó; no aplica nada.

**FAIL-CLOSED (review IA1):** un dato faltante/desconocido NUNCA agranda el cap. En NÚCLEO, un arquetipo o una banda
desconocidos → cap 0 (no "cap ausente"). En OPTIONALITY NO aplican los caps de NÚCLEO (arquetipo/banda de dinero
nuevo): la manga es la razón de existir del tamaño chico — pre_revenue es elegible, y la banda actúa como GATE de
elegibilidad (RECORTE o desconocida → no elegible), no como cap de dinero nuevo. El tier se nombra con UNA
representación canónica (las claves del IPS, p.ej. "OPTIONALITY"). Determinista, $0.

OJO (IA2): esto es un cap de DINERO NUEVO / techo de concentración, NO un piso de tenencia — un activo no-comprable
NO es un activo que haya que vender (eso lo decide la ficha viva / el PM, no este módulo).
"""
from __future__ import annotations


def cap_posicion(*, tier: str, arquetipo: str | None, banda: str | None, verificacion: str | None,
                 cfg: dict) -> tuple[float, str]:
    """Devuelve (cap, liga). `liga` = el cap más restrictivo o el motivo del 0 (fail-closed)."""
    tiers = cfg.get("tiers") or {}
    tier_max = (tiers.get(tier) or {}).get("max")
    if tier_max is None:
        return 0.0, "tier_desconocido"                      # fail-closed: tier no reconocido

    # ── OPTIONALITY: NO usa los caps de núcleo. Elegibilidad + cap por evidencia. ──
    if tier == "OPTIONALITY":
        ev = (cfg.get("cap_por_evidencia_opcionalidad") or {}).get((verificacion or "").upper())
        if ev is None:
            return 0.0, "sin_evidencia"                     # fail-closed: sin verificación no hay cap de opcionalidad
        cap = min(tier_max, ev)
        liga = "evidencia" if ev <= tier_max else "tier"
        if arquetipo == "pre_revenue":
            return cap, liga                                # pre_revenue es elegible por p_implícita, no por banda
        # WHITELIST (review-2 IA1): solo bandas CONOCIDAS y elegibles; RECORTE/None/desconocida ("FOO") → 0 (fail-closed).
        if banda not in ("COMPRA_FUERTE", "COMPRA", "MANTENER"):
            return 0.0, "banda_no_elegible_opcionalidad"
        return cap, liga

    # ── NÚCLEO: cap = min(tier, arquetipo, banda de dinero nuevo). Desconocido → 0. ──
    ca = (cfg.get("cap_por_arquetipo") or {}).get(arquetipo)
    if ca is None:
        return 0.0, "arquetipo_desconocido"
    cb = (cfg.get("cap_por_banda") or {}).get(banda)
    if cb is None:
        return 0.0, "banda_desconocida"
    caps = {"tier": tier_max, "arquetipo": ca, "banda": cb}
    liga = min(caps, key=lambda k: caps[k])
    return caps[liga], liga
