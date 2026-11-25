"""P1 (doc 91 §7, blueprint IA2 §2) — BANDA por arquetipo. MODO SOMBRA: computa COMPRA_FUERTE/COMPRA/MANTENER/
RECORTE desde la métrica del arquetipo (rango del dossier) + el precio del día; NO aplica nada. Se recalcula CADA
ciclo y NUNCA se persiste → mata de raíz las "zonas viejas" (el bug que hizo que el PM operara sobre fichas de
días previos). Usa SIEMPRE el extremo DESFAVORABLE del rango del analista. Bordes versionados (cambiarlos = cambio
de sistema). Determinista, $0.

- infra        → cobertura del EV con contratos IG (extremo BAJO del rango).
- ciclica      → precio vs valor de mitad de ciclo / a la curva [bajo, alto].
- compounder   → g exigido por el precio vs g sostenible [bajo, alto].
- pre_revenue  → NO tiene banda de núcleo; elegible a opcionalidad si p_implícita.alto < p_razonada.bajo.
"""
from __future__ import annotations

BANDAS = ("COMPRA_FUERTE", "COMPRA", "MANTENER", "RECORTE")
_G_HOLGURA = 0.03   # 3pp: margen extra de COMPRA_FUERTE del compounder (versionado)


def banda_infra(cobertura_ig_bajo: float | None) -> str | None:
    c = cobertura_ig_bajo                       # extremo BAJO (desfavorable) del rango de cobertura
    if c is None:
        return None
    if c >= 1.0:
        return "COMPRA_FUERTE"
    if c >= 0.8:
        return "COMPRA"
    if c >= 0.5:
        return "MANTENER"
    return "RECORTE"


def banda_ciclica(precio: float | None, valor_bajo: float | None, valor_alto: float | None) -> str | None:
    if precio is None or valor_bajo is None or valor_alto is None:
        return None
    medio = (valor_bajo + valor_alto) / 2.0
    if precio < valor_bajo:
        return "COMPRA_FUERTE"
    if precio <= medio:
        return "COMPRA"
    if precio <= valor_alto:
        return "MANTENER"
    return "RECORTE"                            # precio por ENCIMA del rango de mitad de ciclo (caso EXE a la curva)


def banda_compounder(g_exigido: float | None, g_sost_bajo: float | None, g_sost_alto: float | None) -> str | None:
    if g_exigido is None or g_sost_bajo is None or g_sost_alto is None:
        return None
    if g_exigido < g_sost_bajo - _G_HOLGURA:
        return "COMPRA_FUERTE"
    if g_exigido < g_sost_bajo:
        return "COMPRA"
    if g_exigido <= g_sost_alto:
        return "MANTENER"
    return "RECORTE"                            # el precio exige MÁS crecimiento del que el negocio sostiene


def pre_revenue_elegible_opcionalidad(p_implicita_alto: float | None, p_razonada_bajo: float | None) -> bool:
    """pre_revenue NO va a núcleo; solo a opcionalidad si el precio implica MENOS éxito del razonado (margen)."""
    if p_implicita_alto is None or p_razonada_bajo is None:
        return False
    return p_implicita_alto < p_razonada_bajo


def calcular_banda(arquetipo: str, datos: dict) -> str | None:
    """Dispatcher. `datos` trae los insumos del dossier (rangos) + precio del día. pre_revenue → None (no hay banda
    de núcleo); su elegibilidad a opcionalidad se evalúa con `pre_revenue_elegible_opcionalidad`."""
    if arquetipo == "infra":
        return banda_infra(datos.get("cobertura_ig_bajo"))
    if arquetipo == "ciclica":
        return banda_ciclica(datos.get("precio"), datos.get("valor_mitad_ciclo_bajo"), datos.get("valor_mitad_ciclo_alto"))
    if arquetipo == "compounder":
        return banda_compounder(datos.get("g_exigido"), datos.get("g_sost_bajo"), datos.get("g_sost_alto"))
    return None   # pre_revenue o arquetipo desconocido: sin banda de núcleo
