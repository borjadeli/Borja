"""Quality — motor de calidad de negocio (Núcleo consolidado v3, §8).

Quality mide SOLO calidad de negocio y ventaja competitiva. Toda métrica
financiera (runway, dilución, shelf, balance) sale de Quality y vive ENTERA en
CRR (separación de motores anti doble conteo). Quality NO incorpora la
probabilidad de que la tesis se cumpla (eso vive en Fragility / el cap).

Forma elegida (decisión del operador 2026-06-24): TIER ORDINAL derivado
determinísticamente de los hechos del gate/arquetipo — NO un score 0-10 nuevo
(§20 audita "scores nuevos: CERO"). El LLM trae los hechos (márgenes, recurrencia,
wins comerciales, posición de pala) con fuente; una tabla los convierte en tier;
el LLM nunca asigna el número.

mérito = Quality(tier) × Asimetría. El tier ordena; no es probabilidad.

[CALIBRACIÓN PENDIENTE]: los puntos por señal y los cortes tier son primera
aproximación, a afinar con tracking histórico (familia "calibración de
constantes", §18). La FORMA (tier ordinal de hechos de negocio sin balance) es
la decisión cerrada; los números finos no.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HechosQuality:
    """Señales de calidad de NEGOCIO (sin balance). El LLM las trae con fuente A
    del filing/transcript; acá llegan como datos.

    Todas son operativas/comerciales — ninguna toca el balance (que es CRR):
    - margen_bruto: gross margin último (fracción 0-1).
    - margen_en_expansion: tendencia de gross margin sostenida al alza (fuente A).
    - crecimiento_organico_elegible: crecimiento YoY del revenue elegible orgánico.
    - revenue_recurrente: hay revenue recurrente/subscription material o backlog
      definido como obligación pendiente (calidad de demanda).
    - hechos_comerciales_independientes: nº de wins comerciales con fuente mínima
      (contratos firmados, design-ins económicos, expansiones) — los del gate.
    - ventaja_estructural: posición de cuello/pala documentada (captura de renta
      observable, no narrativa).
    """
    margen_bruto: float | None = None
    margen_en_expansion: bool = False
    crecimiento_organico_elegible: float | None = None
    revenue_recurrente: bool = False
    hechos_comerciales_independientes: int = 0
    ventaja_estructural: bool = False


def calcular_quality_tier(h: HechosQuality) -> dict:
    """Convierte hechos de negocio en un tier ordinal 1-4 (4 = mejor). Determinista.

    Devuelve {tier, puntos, motivos}. El tier se usa como factor del mérito
    (mérito = tier × asimetría).
    """
    puntos = 0
    motivos: list[str] = []

    mb = h.margen_bruto
    if mb is not None:
        if mb >= 0.50:
            puntos += 2
            motivos.append(f"margen bruto {mb:.0%} (≥50%)")
        elif mb >= 0.30:
            puntos += 1
            motivos.append(f"margen bruto {mb:.0%} (≥30%)")
    if h.margen_en_expansion:
        puntos += 1
        motivos.append("margen en expansión sostenida")

    cg = h.crecimiento_organico_elegible
    if cg is not None:
        if cg >= 0.25:
            puntos += 2
            motivos.append(f"crecimiento orgánico {cg:.0%} (≥25%)")
        elif cg >= 0.10:
            puntos += 1
            motivos.append(f"crecimiento orgánico {cg:.0%} (≥10%)")

    if h.revenue_recurrente:
        puntos += 1
        motivos.append("demanda recurrente / backlog como obligación")

    n = h.hechos_comerciales_independientes
    if n >= 3:
        puntos += 2
        motivos.append(f"{n} hechos comerciales independientes (≥3)")
    elif n >= 1:
        puntos += 1
        motivos.append(f"{n} hecho(s) comercial(es) independiente(s)")

    if h.ventaja_estructural:
        puntos += 1
        motivos.append("ventaja estructural / posición de cuello documentada")

    # Cortes tier (calibrables). Piso en tier 1: una empresa que pasó el gate
    # tiene al menos negocio mínimo; Quality nunca es 0 (mérito 0 mataría una
    # tesis que el gate ya aceptó — eso lo hace el piso de 5% vía mérito bajo).
    if puntos >= 6:
        tier = 4
    elif puntos >= 4:
        tier = 3
    elif puntos >= 2:
        tier = 2
    else:
        tier = 1

    return {"tier": tier, "puntos": puntos, "motivos": motivos}
