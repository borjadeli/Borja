"""Clasificación de arquetipo — Núcleo consolidado v3, §4.

Tres piezas en orden de ejecución, cero scores nuevos:
  Pieza 1 — Revenue elegible (descomposición ASC 606, default-exclude). El LLM
            trae los hechos del filing con etiqueta; acá ya llegan como números.
  Pieza 2 — Cliente dominante (regla ex-top) y su excepción contrato-en-firme.
  Pieza 3 — Tabla de asignación (primer match gana).

Principio rector: el LLM copia etiquetas, NO clasifica. El revenue ambiguo no
existe para la asignación (regla de oro, §4.1). Esta función es determinista y
pura: recibe hechos ya extraídos y devuelve el arquetipo + la traza de por qué.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.nucleo.constantes import (
    CRECIMIENTO_GROWTH,
    EXTOP_TOP1,
    EXTOP_TOP1_TOP2,
    UMBRAL_GROWTH,
    UMBRAL_PREREV,
)


@dataclass
class HechosArquetipo:
    """Hechos fechados ya extraídos del último 10-K/10-Q (el LLM los trae con
    fuente; acá llegan como datos para que la tabla decida).

    - revenue_elegible: suma del revenue whitelist ASC 606 (product sales,
      subscription, recurring, contract revenue de entrega bajo contrato firmado).
      Ya excluye NRE/grants/upfronts/milestones (default-exclude de §4.1).
    - clientes_pct: % de cada cliente divulgado ≥10% (fuente A), de mayor a menor.
    - crecimiento_elegible_yoy: crecimiento YoY del revenue ELEGIBLE (no headline).
    - fcf_ttm: free cash flow TTM.
    - es_binary: respuesta binaria forzada del Red Team (§4.3 fila 1): ¿un único
      evento NO-COMERCIAL deja el equity con recuperación residual ~nula?
    - contrato_en_firme_dominante: el revenue del cliente dominante está bajo
      contrato FIRMADO multi-año vigente (take-or-pay / compra en firme), por
      etiqueta de filing → conserva arquetipo por tamaño (excepción §4.2).
    - recurrencia_etiquetada_dominante: el revenue con el cliente dominante es
      product/subscription/recurring ETIQUETADO como recurrente en el filing
      (costura ex-top↔residual §4.2, ruta (a)).
    """
    revenue_elegible: float | None
    clientes_pct: list[float] = field(default_factory=list)
    crecimiento_elegible_yoy: float | None = None
    fcf_ttm: float | None = None
    es_binary: bool = False
    contrato_en_firme_dominante: bool = False
    recurrencia_etiquetada_dominante: bool = False


def _aplica_ex_top(clientes_pct: list[float]) -> tuple[bool, float]:
    """Pieza 2 (§4.2): ¿dispara ex-top? Devuelve (dispara, fraccion_dominante).

    Dispara si top-1 > 50% O top-1 + top-2 > 66%. La fracción dominante a restar
    es el/los cliente(s) que activaron la regla.
    """
    cs = sorted([c for c in clientes_pct if c is not None], reverse=True)
    if not cs:
        return False, 0.0
    top1 = cs[0]
    top2 = cs[1] if len(cs) > 1 else 0.0
    if top1 > EXTOP_TOP1:
        return True, top1
    if top1 + top2 > EXTOP_TOP1_TOP2:
        return True, top1 + top2
    return False, 0.0


def _tabla_asignacion(revenue_base: float | None, crecimiento: float | None,
                      fcf_ttm: float | None, es_binary: bool) -> tuple[str, int]:
    """Pieza 3 (§4.3): tabla de asignación, primer match gana. Devuelve
    (arquetipo, numero_de_fila)."""
    # Fila 1 — Binary por consecuencia (Red Team), antes que todo.
    if es_binary:
        return "Binary", 1
    rev = revenue_base if revenue_base is not None else 0.0
    # Fila 2 — < $10M → Pre-revenue.
    if rev < UMBRAL_PREREV:
        return "Pre-revenue", 2
    # Fila 3 — $10M–$50M → Tracción.
    if rev < UMBRAL_GROWTH:
        return "Tracción", 3
    # rev ≥ $50M:
    crec = crecimiento if crecimiento is not None else 0.0
    # Fila 4 — ≥$50M con crecimiento ≥25% → Growth.
    if crec >= CRECIMIENTO_GROWTH:
        return "Growth", 4
    # Fila 5 — ≥$50M, crecimiento <25% y FCF positivo → Madura.
    if fcf_ttm is not None and fcf_ttm > 0:
        return "Madura", 5
    # Fila 6 — Residuo: ≥$50M, sin crecimiento, FCF negativo → Tracción.
    return "Tracción", 6


def clasificar_arquetipo(h: HechosArquetipo) -> dict:
    """Clasifica el arquetipo según §4. Determinista y puro.

    Devuelve dict con:
      arquetipo, fila, ex_top_aplicado, revenue_base, conserva_por_excepcion,
      traza (lista de strings explicando cada paso).
    """
    traza: list[str] = []
    rev_elegible = h.revenue_elegible if h.revenue_elegible is not None else 0.0

    # Pieza 2 — ex-top.
    dispara_extop, fraccion = _aplica_ex_top(h.clientes_pct)
    conserva = False
    revenue_base = rev_elegible

    if dispara_extop:
        # Excepción contrato-en-firme O recurrencia etiquetada (costura §4.2 ruta a):
        # conserva arquetipo por tamaño. La concentración se cobra entera en
        # Fragility (típicamente Frag 2), no acá.
        if h.contrato_en_firme_dominante or h.recurrencia_etiquetada_dominante:
            conserva = True
            motivo = ("contrato en firme multi-año" if h.contrato_en_firme_dominante
                      else "revenue recurrente etiquetado")
            traza.append(
                f"ex-top dispara (concentración {fraccion:.0%}) pero conserva arquetipo "
                f"por tamaño: {motivo}. Concentración se cobra en Fragility."
            )
        else:
            revenue_base = rev_elegible * (1.0 - fraccion)
            traza.append(
                f"ex-top dispara (concentración {fraccion:.0%}): revenue base "
                f"${rev_elegible/1e6:.1f}M → ${revenue_base/1e6:.1f}M (ex-dominante)."
            )
    else:
        traza.append(f"ex-top no dispara; revenue base = revenue elegible ${rev_elegible/1e6:.1f}M.")

    # Pieza 3 — tabla de asignación.
    arquetipo, fila = _tabla_asignacion(
        revenue_base, h.crecimiento_elegible_yoy, h.fcf_ttm, h.es_binary
    )
    traza.append(f"tabla de asignación: fila {fila} → {arquetipo}.")

    return {
        "arquetipo": arquetipo,
        "fila": fila,
        "ex_top_aplicado": dispara_extop and not conserva,
        "ex_top_disparo": dispara_extop,
        "conserva_por_excepcion": conserva,
        "revenue_base": revenue_base,
        "revenue_elegible": rev_elegible,
        "fraccion_dominante": fraccion,
        "traza": traza,
    }
