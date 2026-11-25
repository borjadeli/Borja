"""P1 (doc 91 §7, blueprint IA2 §1) — CAP de posición = min(tier, arquetipo, banda, evidencia). MODO SOMBRA:
computa el techo económico de una posición y REGISTRA qué cap ligó; no aplica nada. "Nada compensa nada" —
el tamaño es el mínimo no-compensatorio de todos los caps, más los caps existentes del IPS (liquidez/
supervivencia/sector/cuello) que aplica el gate. Determinista, $0.
"""
from __future__ import annotations


def cap_posicion(*, tier: str, arquetipo: str | None, banda: str | None, verificacion: str | None,
                 cfg: dict) -> tuple[float, str]:
    """Devuelve (cap, liga). `liga` = qué cap fue el más restrictivo (tier/arquetipo/banda/evidencia). Si no hay
    ningún cap aplicable → (0.0, 'sin_caps'). pre_revenue (cap_arquetipo 0) → 0 en núcleo, como corresponde."""
    caps: dict[str, float] = {}

    tcfg = (cfg.get("tiers") or {}).get(tier or "", {})
    if tcfg.get("max") is not None:
        caps["tier"] = float(tcfg["max"])

    if arquetipo is not None:
        ca = (cfg.get("cap_por_arquetipo") or {}).get(arquetipo)
        if ca is not None:
            caps["arquetipo"] = float(ca)

    if banda is not None:
        cb = (cfg.get("cap_por_banda") or {}).get(banda)
        if cb is not None:
            caps["banda"] = float(cb)

    if tier == "opcionalidad" and verificacion is not None:
        ce = (cfg.get("cap_por_evidencia_opcionalidad") or {}).get((verificacion or "").upper())
        if ce is not None:
            caps["evidencia"] = float(ce)

    if not caps:
        return 0.0, "sin_caps"
    liga = min(caps, key=lambda k: caps[k])       # el cap más restrictivo
    return caps[liga], liga
