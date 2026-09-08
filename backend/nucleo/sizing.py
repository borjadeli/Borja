"""Mérito, Hard Cap y sizing — Núcleo consolidado v3, §8, §9.

Separación estricta de motores (§8):
  - Quality  → SOLO calidad de negocio / ventaja competitiva. Sin balance.
  - Asimetría → PURA: R/R al precio actual + opcionalidad ya priceada. SIN
    probabilidad de que la tesis se cumpla.
  - mérito = Quality × Asimetría → ordena (Selector). La fragilidad NO entra acá.
  - sizing = mérito normalizado, recortado a [5%, Hard Cap].

Hard Cap = min(cap_arquetipo/celda, cap_CRR, techo_absoluto). Es techo, no veto;
ningún cap de arquetipo baja de 5%. CRR entra como CAP, nunca como multiplicador
(se eliminan los 0.70/0.85 del sistema viejo — doble castigo).

[GAP DE DISEÑO — pendiente de decisión del operador]: el doc define Quality como
un MOTOR ("solo negocio, sin balance") y mérito = Quality × Asimetría, pero NO
fija la forma numérica de Quality ni cómo se normaliza el mérito a capital bruto
(§20 audita "scores nuevos: CERO", así que Quality NO es un score 0-10 nuevo).
Por eso acá Quality llega como INPUT inyectado y la normalización del mérito es
explícita y reemplazable. Ver nota al final del módulo.
"""
from __future__ import annotations

from backend.nucleo.constantes import PISO_POSICION, TECHO_POSICION


def asimetria_vigente(bull: float, precio: float, bear: float) -> float | None:
    """Asimetría pura al precio actual (§13.2): (bull − precio) / (precio − bear).

    Devuelve None si el denominador es ≤0 (precio ≤ bear: sin downside definido
    o ya por debajo del bear → la asimetría no es calculable de forma estándar).
    Al bull solo entran hechos OCURRIDOS (dieta anti-IONQ); eso es responsabilidad
    de quien arma bull/bear, no de esta aritmética.
    """
    denom = precio - bear
    if denom <= 0:
        return None
    return (bull - precio) / denom


def hard_cap(cap_celda: float, cap_crr: float | None = None,
             techo_absoluto: float = TECHO_POSICION) -> float:
    """Hard Cap = min(cap_celda, cap_CRR, techo_absoluto) (§9).

    Manda la restricción más severa; NO se multiplican ni promedian las fuentes.
    cap_crr None = CRR no impone cap (Bajo). CRR-Crítico NO llega acá: rechaza
    upstream (es una de las dos vías de rechazo, §3).

    [CALIBRACIÓN PENDIENTE]: los valores de cap_CRR para Medio/Alto no están en
    el doc (el viejo usaba multiplicadores 0.70/0.85, ahora prohibidos). Quedan
    como input calibrable; mientras tanto cap_crr=None no restringe.
    """
    candidatos = [cap_celda, techo_absoluto]
    if cap_crr is not None:
        candidatos.append(cap_crr)
    return min(candidatos)


def merito(quality: float, asimetria: float | None) -> float | None:
    """mérito = Quality × Asimetría (§8). None si la asimetría no es calculable."""
    if asimetria is None:
        return None
    return quality * asimetria


def sizing_final(merito_normalizado: float, cap: float) -> dict:
    """Sizing = mérito normalizado recortado a [5%, Hard Cap] (§9).

    merito_normalizado: capital bruto pedido por el mérito, ya normalizado a
    fracción de cartera (la normalización es relativa al universo rankeado y
    vive en el Selector — ver nota de diseño).

    Si el mérito normalizado < 5% → NO entra, va a watchlist (mata «migajas que
    queman slots», §7). El cap es techo; el piso de 5% corta abajo.
    """
    if merito_normalizado < PISO_POSICION:
        return {
            "entra": False,
            "sizing": 0.0,
            "destino": "watchlist",
            "motivo": f"mérito normalizado {merito_normalizado:.1%} < piso {PISO_POSICION:.0%}",
        }
    sizing = min(merito_normalizado, cap)
    sizing = max(sizing, PISO_POSICION)  # ningún cap de arquetipo baja de 5%.
    capeado = merito_normalizado > cap
    return {
        "entra": True,
        "sizing": sizing,
        "destino": "cartera",
        "capeado_por_hardcap": capeado,
        "motivo": (f"recortado por Hard Cap {cap:.0%}" if capeado
                   else f"sizing por mérito {sizing:.1%}"),
    }


# -----------------------------------------------------------------------------
# NOTA DE DISEÑO — la normalización del mérito y la forma de Quality.
#
# El núcleo (§9) dice "el mérito normalizado pide capital bruto; el Hard Cap lo
# limita". "Normalizado" implica una normalización RELATIVA al conjunto de
# candidatas rankeadas por el Selector (un mérito que es el mejor del universo
# pide más capital que uno mediocre). El doc no fija la fórmula exacta de esa
# normalización ni la escala de Quality.
#
# Dos preguntas abiertas para el operador (no se inventan acá para no violar
# "ningún score nuevo" / "el LLM nunca asigna"):
#   1. Quality: ¿es un tier ordinal derivado determinísticamente de hechos del
#      gate/arquetipo, o un input cualitativo que el humano fija al desempatar?
#   2. Normalización: ¿mérito → % de cartera por ranking relativo (p. ej.
#      proporción del mérito sobre la suma de méritos de las top-N), o por una
#      escala absoluta calibrada?
#
# Hasta cerrar eso, sizing_final() recibe merito_normalizado ya en fracción de
# cartera, y el Selector (pieza separada, pendiente) hará la normalización.
# -----------------------------------------------------------------------------
