"""P1 (doc 91 §8, review IA1+IA2) — clasificador de ARQUETIPO económico. MODO SOMBRA: computa el arquetipo
PROPUESTO desde señales deterministas del pack; NO aplica nada. El Analista confirma o hace override con fuente.

Precedencia: infra → pre_revenue → ciclica → compounder (primera señal true gana). Robustez (review):
- Clave de revenue UNIFICADA (`revenue_ltm` o `revenue`): antes infra leía una y pre_revenue otra → CIFR caía en pre_revenue.
- El capex se toma en VALOR ABSOLUTO (muchos feeds lo traen negativo = salida de caja) → no apaga la señal de infra.
- AUSENCIA ≠ CERO: si `contratado_firme` es None (el scanner no corrió), la señal de infra es UNEVALUABLE → NO se deja
  caer la vía OCF<0+runway (que solapa con infra) a pre_revenue; queda UNCLASSIFIED y lo resuelve el Analista.

CAVEAT (IA2, pendiente para la fase del schema del Analista): la señal de infra usa `contratado/EV`, que depende del
PRECIO (circularidad: una empresa cambiaría de arquetipo si sube la acción). El fix estructural (controla activos de
larga vida + revenue contratado material) necesita un campo estructural del dossier. Determinista, $0.
"""
from __future__ import annotations

import math

ARQUETIPOS = ("infra", "pre_revenue", "ciclica", "compounder")
SECTORES_CICLICOS = {"e&p", "mineria", "minería", "ipp", "quimica", "química", "shipping", "semis_equipos",
                     "oil_gas", "gas", "uranio", "cobre", "commodities"}


def _num(x):
    """Valor numérico finito o None (rechaza NaN/inf y no-números)."""
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _rev(d: dict):
    r = _num(d.get("revenue_ltm"))
    return r if r is not None else _num(d.get("revenue"))


def _frac(a, b):
    a, b = _num(a), _num(b)
    if a is None or b is None or b <= 0:
        return None
    return a / b


def _señal_infra(d: dict):
    """True/False/None. None = UNEVALUABLE (no se escaneó `contratado_firme`) → no es "no-infra"."""
    if d.get("contratado_firme") is None:
        return None
    cob = _frac(d.get("contratado_firme"), d.get("ev"))
    capex = _num(d.get("capex"))
    capint = _frac(abs(capex) if capex is not None else None, _rev(d))   # capex en valor absoluto
    if cob is None or capint is None:
        return None
    return cob >= 0.5 and capint >= 0.5


def _señal_pre_revenue(d: dict, *, infra_evaluable: bool) -> bool:
    rev = _rev(d)
    if rev is not None and rev < 50e6:
        return True                                   # señal definitiva
    gm = _num(d.get("margen_bruto_ltm"))
    if gm is not None and gm <= 0:
        return True                                   # señal definitiva
    # vía OCF<0 + runway corto: SOLAPA con infra → solo si infra pudo evaluarse (y dio no-infra)
    ocf, runway = _num(d.get("ocf_ltm")), _num(d.get("runway_meses"))
    if infra_evaluable and ocf is not None and ocf < 0 and runway is not None and runway < 36:
        return True
    return False


def _señal_ciclica(d: dict) -> bool:
    if (d.get("sector") or "").strip().lower() in SECTORES_CICLICOS:
        return True
    cv = _num(d.get("cv_margen_op_10a"))
    if cv is not None and cv > 0.5:
        return True
    m_ltm, m_med = _num(d.get("margen_op_ltm")), _num(d.get("margen_op_mediana_10a"))
    return m_ltm is not None and m_med is not None and m_med > 0 and m_ltm > 1.5 * m_med


def _señal_compounder(d: dict) -> bool:
    fcf_a, roic_a = _num(d.get("fcf_pos_anios_de5")), _num(d.get("roic_gt15_anios_de5"))
    return fcf_a is not None and roic_a is not None and fcf_a >= 4 and roic_a >= 4


def clasificar_arquetipo(datos: dict) -> str | None:
    """Arquetipo PROPUESTO (precedencia infra→pre_revenue→ciclica→compounder) o None (UNCLASSIFIED)."""
    infra = _señal_infra(datos)
    if infra is True:
        return "infra"
    if _señal_pre_revenue(datos, infra_evaluable=(infra is not None)):
        return "pre_revenue"
    if _señal_ciclica(datos):
        return "ciclica"
    if _señal_compounder(datos):
        return "compounder"
    return None
