"""Filtro 0 (Art. 6.5) — ¿vale la pena el deep research (caro)?

Determinista y SIN LLM (el pre-screen busca RECALL; un LLM mete varianza invisible).
Hechos inyectados → uno de 3 veredictos: 'descartar' | 'esperar-evidencia' |
'investigar'. Cada veredicto lleva el motivo (para taguear la descartada y el
re-chequeo dirigido).

Ajustes tras revisión externa:
  - Dato faltante NO es descarte definitivo → 'esperar-evidencia' (protege recall).
  - Una sola métrica débil NO descarta (matriz: descartar solo si AMBAS feas).
  - Riesgo de runway SEPARADO de deuda; None de deuda no se asume 0.
  - Validación barata de unidades / valores absurdos.
  - Contrato 'vinculante material' (semántica dura, no LOI/MOU).
"""
from __future__ import annotations

from dataclasses import dataclass

# Umbrales (calibrables — registro 14).
CREC_OK = 0.20            # crecimiento YoY "bueno"
CREC_NEARMISS = 0.10      # 10-20% → casi
CREC_EXCEPCIONAL = 0.50   # ≥50% → sobresaliente (arrastra un near-miss del margen)
MARGEN_OK = 0.30          # margen bruto "bueno"
MARGEN_NEARMISS = 0.20    # 20-30% → casi
MARGEN_EXCEPCIONAL = 0.60  # ≥60% → sobresaliente (arrastra un near-miss del crecimiento)
DEUDA_ALTA = 2.0        # deuda/revenue
RUNWAY_CRITICO = 6      # meses: por debajo y sin financiación → descartar
RUNWAY_HOLGADO = 12     # meses: por debajo → esperar-evidencia

VEREDICTOS = ("descartar", "esperar-evidencia", "investigar")


@dataclass
class HechosFiltro0:
    es_prerevenue: bool = False
    # Vinculante + contraparte solvente + material para la empresa. NO una LOI/MOU/pipeline.
    tiene_contrato_vinculante_material: bool = False
    tiene_traccion_comercial: bool = False
    crecimiento_yoy: float | None = None
    margen_bruto: float | None = None
    deuda_sobre_revenue: float | None = None
    quema_caja: bool = False              # solo relevante si runway_meses es None
    runway_meses: float | None = None
    financiacion_comprometida: bool = False


@dataclass
class ResultadoFiltro0:
    veredicto: str
    motivo: str


def _r(veredicto: str, motivo: str) -> ResultadoFiltro0:
    return ResultadoFiltro0(veredicto, motivo)


def _nivel(valor: float | None, ok: float, near: float, exc: float) -> str:
    """missing | feo | near | ok | exceptional. Faltante es 'missing', NO 'feo' (recall)."""
    if valor is None:
        return "missing"
    if valor >= exc:
        return "exceptional"
    if valor >= ok:
        return "ok"
    if valor >= near:
        return "near"
    return "feo"


def evaluar_filtro0(h: HechosFiltro0) -> ResultadoFiltro0:
    """Veredicto barato de 'vale el deep research'. Determinista."""
    # 0. Validación de unidades / valores absurdos → esperar (dato sospechoso, no descarte).
    if h.margen_bruto is not None and not (-1.0 <= h.margen_bruto <= 1.0):
        return _r("esperar-evidencia", f"margen fuera de rango ({h.margen_bruto}) — ¿unidades?")
    if h.crecimiento_yoy is not None and not (-1.0 <= h.crecimiento_yoy <= 20.0):
        return _r("esperar-evidencia", f"crecimiento fuera de rango ({h.crecimiento_yoy}) — ¿unidades?")
    if h.runway_meses is not None and h.runway_meses < 0:
        return _r("esperar-evidencia", "runway inválido (<0)")

    # 1. Riesgo financiero — runway separado de deuda. Financiación comprometida lo neutraliza.
    if not h.financiacion_comprometida:
        if h.runway_meses is not None:      # runway finito ⇒ quema caja
            if h.runway_meses < RUNWAY_CRITICO:
                return _r("descartar",
                          f"runway crítico {h.runway_meses:.0f}m sin financiación comprometida")
            if h.runway_meses < RUNWAY_HOLGADO:
                return _r("esperar-evidencia", f"runway ajustado {h.runway_meses:.0f}m")
        elif h.quema_caja:
            return _r("esperar-evidencia", "quema caja, runway desconocido")
    # Deuda alta como señal adicional (None NO se asume 0; solo se actúa sobre deuda CONOCIDA).
    if h.deuda_sobre_revenue is not None and h.deuda_sobre_revenue > DEUDA_ALTA:
        return _r("esperar-evidencia", f"deuda/rev {h.deuda_sobre_revenue:.1f}x alta")

    # 2. Pre-revenue: exige contrato vinculante material.
    if h.es_prerevenue:
        if h.tiene_contrato_vinculante_material:
            return _r("investigar", "pre-revenue con contrato vinculante material")
        if h.tiene_traccion_comercial:
            return _r("esperar-evidencia",
                      "pre-revenue sin contrato vinculante, con tracción → esperar hecho")
        return _r("descartar", "pre-revenue sin evidencia comercial")

    # 3. Con revenue: matriz de calidad (recall-friendly).
    nc = _nivel(h.crecimiento_yoy, CREC_OK, CREC_NEARMISS, CREC_EXCEPCIONAL)
    nm = _nivel(h.margen_bruto, MARGEN_OK, MARGEN_NEARMISS, MARGEN_EXCEPCIONAL)
    crec_s = f"{h.crecimiento_yoy:.0%}" if h.crecimiento_yoy is not None else "N/D"
    margen_s = f"{h.margen_bruto:.0%}" if h.margen_bruto is not None else "N/D"
    bueno = {"ok", "exceptional"}

    if "missing" in (nc, nm):
        return _r("esperar-evidencia", f"falta dato (crecimiento {crec_s}, margen {margen_s})")
    if nc in bueno and nm in bueno:
        return _r("investigar", f"crecimiento {crec_s} y margen {margen_s} ok")
    if nc == "feo" and nm == "feo":
        return _r("descartar", f"sin crecimiento ni margen (crecimiento {crec_s}, margen {margen_s})")
    # Regla de dimensión EXCEPCIONAL: una sobresaliente arrastra un near-miss de la otra.
    if (nc == "exceptional" and nm == "near") or (nm == "exceptional" and nc == "near"):
        return _r("investigar",
                  f"dimensión excepcional arrastra el near-miss (crecimiento {crec_s}, margen {margen_s})")
    # Cualquier otra combinación (una feo/near con otra mejor) → esperar, no descartar.
    return _r("esperar-evidencia", f"calidad mixta (crecimiento {crec_s}, margen {margen_s}) → esperar print")
