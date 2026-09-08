"""Fragility Score y caps — Núcleo consolidado v3, §10, §11.

La fragilidad NO entra al Selector (no afecta el mérito): SOLO capea el tamaño
vía min() (§8). Tres fuentes separadas de fragilidad desembocan en el Hard Cap:
arquetipo (estructural), CRR (balance; Crítico elimina) y Fragility Score 0-3
(idiosincrática de tesis). El LLM trae hechos fechados; una tabla los convierte
en score; el LLM nunca asigna el número.

Este módulo cubre el Fragility Score (0-3), la tabla de caps arquetipo×Frag y
el cubo agregado de residual-cero (§11.2). Quality y Asimetría viven en sizing.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.nucleo.constantes import (
    CAPS_ARQUETIPO_FRAGILITY,
    CUBO_RESIDUAL_CERO,
)


@dataclass
class HechosFragility:
    """Hechos estructurales de tesis para el Fragility Score (§10).

    El LLM trae cada hecho fechado con fuente; la tabla de abajo asigna el número.
    Las cláusulas ESTRUCTURALES aplican siempre (no se re-cuentan por % tras mover
    arquetipo — costura anti doble conteo §4.4).
    """
    financiacion_completa_cerrada: bool = False   # todo el plan financiado (Frag 0).
    redundancia_comercial_real: bool = False      # clientes sin mecanismo de pago único (Frag 0).
    concentracion_cliente_pct: float | None = None  # cliente único, fracción 0-1.
    dependencia_con_respaldo: bool = False         # contrato marco / LOI con penalidad + plan B (Frag 1).
    bull_depende_evento_discreto: bool = False     # 1-2 eventos sin alternativa (Frag 2).
    financiacion_externa_no_firmada: bool = False  # necesaria para producción (Frag 2).
    punto_unico_de_falla: bool = False             # sin valor residual si falla (Frag 3).
    perfora_negocio_base: bool = False             # el punto de falla contamina el residual (§11 excepción).


def calcular_fragility_score(h: HechosFragility) -> dict:
    """Asigna Frag 0-3 de los hechos estructurales. Determinista.

    Orden de severidad: se evalúa de 3 hacia 0; el primer match de mayor
    severidad gana (la fragilidad es el techo más severo, no un promedio).
    """
    motivos: list[str] = []

    # Frag 3 — quebradiza / binaria: un único punto de falla, sin residual.
    if h.punto_unico_de_falla:
        motivos.append("único punto de falla sin valor residual si falla")
        return {"score": 3, "motivos": motivos}

    # Frag 2 — fragilidad alta.
    conc = h.concentracion_cliente_pct or 0.0
    if h.bull_depende_evento_discreto:
        motivos.append("el bull descansa en 1-2 eventos discretos sin alternativa")
    if conc > 0.50:
        motivos.append(f"cliente único {conc:.0%} (>50%)")
    if h.financiacion_externa_no_firmada:
        motivos.append("financiación externa no firmada necesaria para producción")
    if motivos:
        return {"score": 2, "motivos": motivos}

    # Frag 1 — manejable: una dependencia con respaldo, concentración 30-50%.
    if h.dependencia_con_respaldo:
        motivos.append("dependencia clara con respaldo (contrato marco / LOI con penalidad) + plan B")
    if 0.30 <= conc <= 0.50:
        motivos.append(f"concentración moderada {conc:.0%} (30-50%)")
    if motivos:
        return {"score": 1, "motivos": motivos}

    # Frag 0 — robusta: exige financiación completa Y redundancia real.
    if h.financiacion_completa_cerrada and h.redundancia_comercial_real:
        motivos.append("múltiples caminos comerciales + financiación cerrada para todo el plan")
        return {"score": 0, "motivos": motivos}

    # Sin evidencia suficiente de robustez → no se acredita Frag 0 (la celda más
    # explotable por narrativa, §10). Default conservador a Frag 1.
    motivos.append("sin evidencia de robustez completa (Frag 0 no acreditable) → default Frag 1")
    return {"score": 1, "motivos": motivos}


def cap_celda(arquetipo: str, frag_score: int) -> float:
    """Cap de la celda arquetipo × Fragility (§11). El techo de sizing de esa celda."""
    fila = CAPS_ARQUETIPO_FRAGILITY.get(arquetipo)
    if fila is None:
        raise ValueError(f"arquetipo desconocido: {arquetipo!r}")
    if frag_score not in fila:
        raise ValueError(f"frag_score fuera de rango (0-3): {frag_score!r}")
    return fila[frag_score]


def es_residual_cero(arquetipo: str, frag_score: int) -> bool:
    """Membresía al cubo de residual-cero (§11.2): toda posición cuya tesis de
    ruptura marque pérdida ~total. Default cuando no es clara: Binary (cualquier
    Frag) + Pre-revenue Frag 3."""
    if arquetipo == "Binary":
        return True
    if arquetipo == "Pre-revenue" and frag_score == 3:
        return True
    return False


def exposicion_cubo_excede(pesos_residual_cero: list[float]) -> dict:
    """¿La exposición agregada del cubo residual-cero supera el 8% (§11.2)?

    pesos_residual_cero: pesos (fracción de cartera) de las posiciones que son
    residual-cero. Devuelve {excede, total, exceso}.
    """
    total = sum(pesos_residual_cero)
    exceso = max(0.0, total - CUBO_RESIDUAL_CERO)
    return {"excede": total > CUBO_RESIDUAL_CERO, "total": total, "exceso": exceso}
