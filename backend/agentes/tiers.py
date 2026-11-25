"""P1.3 (doc 91 §7) — IPS por TIERS: 4 categorías ECONÓMICAS que reemplazan al piso rígido de 5%.

IA1 it.2: OPTIONALITY 1-3% · CORE 5-10% · HIGH_CONVICTION >10-15% · EXCEPTIONAL >15-20% · EXIT 0%. SIN tier 3-5%
(la opcionalidad es una categoría económica distinta, no un CORE chico → evita que toda posición chica sea una
excepción al piso). El tier NO da derecho a usar todo su rango: aguas arriba siempre gana el cap más restrictivo
(liquidez/supervivencia/sector/cuello). Determinista, $0. Los números viven en `ips.yaml` (`tiers:`).
"""
from __future__ import annotations

TIERS_ORDEN = ("OPTIONALITY", "CORE", "HIGH_CONVICTION", "EXCEPTIONAL")
_EPS = 1e-9


def _en_banda(weight: float, banda: dict) -> bool:
    """¿`weight` cae en la banda? Soporta `min` (inclusivo), `min_exclusive` (exclusivo) y `max` (inclusivo)."""
    hi = banda.get("max")
    if hi is None or weight > hi + _EPS:
        return False
    if banda.get("min") is not None:
        return weight >= banda["min"] - _EPS
    if banda.get("min_exclusive") is not None:
        return weight > banda["min_exclusive"] + _EPS
    return False


def valid_target_weight(weight: float, tier: str, tiers_cfg: dict) -> bool:
    """¿`weight` es un peso objetivo VÁLIDO para el `tier` declarado? (regla exacta de IA1 §1.2). EXIT → 0."""
    if tier == "EXIT":
        return abs(weight) < _EPS
    banda = (tiers_cfg or {}).get(tier)
    return _en_banda(weight, banda) if banda else False


def tier_de_peso(weight: float, tiers_cfg: dict) -> str | None:
    """El tier al que pertenece `weight`, o None si cae en una zona INVÁLIDA (p.ej. 4% o 3.5% — entre tiers)."""
    if abs(weight) < _EPS:
        return "EXIT"
    for t in TIERS_ORDEN:
        if valid_target_weight(weight, t, tiers_cfg):
            return t
    return None


def peso_valido(weight: float, tiers_cfg: dict) -> bool:
    """¿`weight` cae en ALGÚN tier válido (o es 0)? Lo que reemplaza al chequeo del piso rígido."""
    return tier_de_peso(weight, tiers_cfg) is not None
