"""P1 (doc 91 §8) — HARNESS de sombra: mapea un Dossier (+ la decisión del PM + el pack) a los insumos del
orquestador `evaluar_sombra`, CONSUMIENDO el bloque económico estructurado del Analista (`dossier.underwriting`) —
no lo reinterpreta de la narrativa (IA2 §3.2). Lo que el Analista no emitió queda None → fail-closed.

Esta es la pieza que conecta el circuito real con la capa P1 en sombra: dada una decisión del comité, computa "qué
habría decidido P1" sin aplicarlo. Determinista, $0. (El logging del shadow_decision + el registro de contrafactuales
bloqueados — IA2 §3.5/3.6 — es el siguiente paso; este módulo es el consumidor.)
"""
from __future__ import annotations

from backend.agentes.evaluar_sombra import VeredictoSombra, evaluar_sombra


def _falsador_liga_metrica(dossier, uw) -> bool:
    """¿El falsador DURO mide la métrica obligatoria del arquetipo o un insumo? (IA2: no exigir la métrica EXACTA,
    sí que esté ligado al mecanismo.) Aproximación: hay vara externa con una métrica declarada."""
    fals = getattr(dossier, "falsador", None)
    vara = getattr(fals, "vara_externa", None) if fals else None
    return bool(vara and getattr(vara, "metrica", None))


def insumos_de_dossier(dossier, *, verif: str, accion: str, motivo: str = "discrecional",
                       peso_objetivo: float | None = None, tier_declarado: str | None = None,
                       comparacion: str | None = None, bloqueo_datos=None, sig_pack: dict | None = None) -> dict:
    """Arma el `d` que consume `evaluar_sombra` desde un Dossier verificado + la decisión del PM. `sig_pack` =
    señales de arquetipo del data pack (fallback si el Analista no confirmó el arquetipo)."""
    uw = getattr(dossier, "underwriting", None)
    banda_inputs = dict(getattr(uw, "banda_inputs", None) or {})
    metrica_presente = bool(uw and getattr(uw, "metrica_obligatoria_bajo", None) is not None)
    falsador_ok = _falsador_liga_metrica(dossier, uw)
    return {
        "arquetipo_confirmado": getattr(uw, "arquetipo_confirmado", None) if uw else None,
        "sig": sig_pack or {},                     # fallback: el código propone desde el pack si no hay confirmado
        "banda_in": banda_inputs,
        "verif": verif,
        "accion": accion,
        "motivo": motivo,
        "peso_objetivo": peso_objetivo,
        "tier_declarado": tier_declarado,
        "metrica_obligatoria_presente": metrica_presente,
        "falsador_estructurado": falsador_ok,
        "falsador_id": (getattr(getattr(dossier, "falsador", None), "afirmacion", None) or None) if falsador_ok else None,
        "falsador_sobre_metrica": falsador_ok,
        "comparacion": comparacion,
        "bloqueo_datos": list(bloqueo_datos) if bloqueo_datos else None,
    }


def evaluar_decision_sombra(dossier, *, cfg: dict, verif: str, accion: str, **kw) -> VeredictoSombra:
    """Conveniencia: mapea el dossier y corre el orquestador en un paso."""
    return evaluar_sombra(insumos_de_dossier(dossier, verif=verif, accion=accion, **kw), cfg=cfg)
