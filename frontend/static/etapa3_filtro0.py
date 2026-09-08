"""Filtro 0 (Art. 6.5) — ¿vale la pena el deep research (caro)?

Determinista y SIN LLM (el pre-screen busca recall; un LLM mete varianza invisible).
Hechos inyectados → uno de 3 veredictos: 'descartar' | 'esperar-evidencia' |
'investigar'. Cada veredicto lleva el motivo (para taguear la descartada y el
re-chequeo dirigido). Reforma barata del screener de 5 filtros ya existente.
"""
from __future__ import annotations

from dataclasses import dataclass

# Umbrales (calibrables — registro 14). Espíritu del screener viejo + constitución.
CREC_OK = 0.20          # crecimiento YoY "bueno"
CREC_NEARMISS = 0.10    # 10-20% → casi
MARGEN_OK = 0.30        # margen bruto "bueno"
MARGEN_NEARMISS = 0.20  # 20-30% → casi
DEUDA_ALTA = 2.0        # deuda/revenue
RUNWAY_MIN_MESES = 6    # financiación mínima antes de considerar riesgo crítico

VEREDICTOS = ("descartar", "esperar-evidencia", "investigar")


@dataclass
class HechosFiltro0:
    es_prerevenue: bool = False
    tiene_contrato_firme: bool = False       # pre-revenue: contrato/LOI económica firme
    tiene_traccion_comercial: bool = False   # señal comercial no-firme (design-in, pipeline)
    crecimiento_yoy: float | None = None
    margen_bruto: float | None = None
    deuda_sobre_revenue: float | None = None
    runway_meses: float | None = None


@dataclass
class ResultadoFiltro0:
    veredicto: str
    motivo: str


def _nivel(valor: float | None, ok: float, near: float) -> str:
    """ok | near | feo. Valor faltante → feo (default conservador)."""
    if valor is None:
        return "feo"
    if valor >= ok:
        return "ok"
    if valor >= near:
        return "near"
    return "feo"


def evaluar_filtro0(h: HechosFiltro0) -> ResultadoFiltro0:
    """Veredicto barato de 'vale el deep research'. Determinista."""
    # 1. Riesgo financiero duro → descartar (el deep research solo confirmaría la muerte).
    if (h.runway_meses is not None and h.runway_meses < RUNWAY_MIN_MESES
            and (h.deuda_sobre_revenue or 0.0) > DEUDA_ALTA):
        return ResultadoFiltro0(
            "descartar",
            f"riesgo financiero: runway {h.runway_meses:.0f}m (<{RUNWAY_MIN_MESES}m) "
            f"+ deuda/rev {h.deuda_sobre_revenue:.1f}x",
        )

    # 2. Pre-revenue: exige evidencia comercial firme (Art. 2.1).
    if h.es_prerevenue:
        if h.tiene_contrato_firme:
            return ResultadoFiltro0("investigar", "pre-revenue con contrato firme")
        if h.tiene_traccion_comercial:
            return ResultadoFiltro0(
                "esperar-evidencia",
                "pre-revenue sin contrato firme, con tracción → esperar el hecho")
        return ResultadoFiltro0("descartar", "pre-revenue sin evidencia comercial")

    # 3. Con revenue: calidad mínima (crecimiento + margen).
    nc = _nivel(h.crecimiento_yoy, CREC_OK, CREC_NEARMISS)
    nm = _nivel(h.margen_bruto, MARGEN_OK, MARGEN_NEARMISS)
    niveles = {nc, nm}
    crec_s = f"{h.crecimiento_yoy:.0%}" if h.crecimiento_yoy is not None else "N/D"
    margen_s = f"{h.margen_bruto:.0%}" if h.margen_bruto is not None else "N/D"

    if niveles == {"ok"}:
        return ResultadoFiltro0("investigar", f"crecimiento {crec_s} y margen {margen_s} ok")
    if "feo" in niveles:
        return ResultadoFiltro0(
            "descartar", f"calidad insuficiente (crecimiento {crec_s}, margen {margen_s})")
    # Solo 'near' (ninguno feo) → casi; esperar el próximo print.
    return ResultadoFiltro0(
        "esperar-evidencia", f"cerca en crecimiento/margen ({crec_s}/{margen_s}) → esperar print")
