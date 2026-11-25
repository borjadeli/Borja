"""P1 (doc 91 §7, blueprint IA2) — clasificador de ARQUETIPO económico. MODO SOMBRA: computa el arquetipo
PROPUESTO desde señales deterministas del pack; NO aplica nada. El Analista confirma o hace override con fuente.

Precedencia: infra → pre_revenue → ciclica → compounder (la PRIMERA señal true gana; por eso CIFR cae en infra
aunque tenga OCF<0). Datos insuficientes para toda señal → None (UNCLASSIFIED): el Analista lo asigna, y a núcleo
solo si la métrica obligatoria tiene fuente primaria. Determinista, $0.
"""
from __future__ import annotations

ARQUETIPOS = ("infra", "pre_revenue", "ciclica", "compounder")

# sectores/tags estructuralmente cíclicos (IA2 §2.ciclica)
SECTORES_CICLICOS = {"e&p", "mineria", "minería", "ipp", "quimica", "química", "shipping", "semis_equipos",
                     "oil_gas", "gas", "uranio", "cobre", "commodities"}


def _frac(a, b):
    """a/b seguro: None si falta algún dato o b no es positivo."""
    if a is None or b is None or b <= 0:
        return None
    return a / b


def _señal_infra(d: dict) -> bool:
    # contratado_firme = valor TOTAL contratado firme (RPO XBRL + backlog de leasing + 8-K 1.01 con monto), NO anual.
    cob = _frac(d.get("contratado_firme"), d.get("ev"))
    capint = _frac(d.get("capex"), d.get("revenue"))
    return cob is not None and capint is not None and cob >= 0.5 and capint >= 0.5


def _señal_pre_revenue(d: dict) -> bool:
    rev, gm, ocf, runway = d.get("revenue_ltm"), d.get("margen_bruto_ltm"), d.get("ocf_ltm"), d.get("runway_meses")
    if rev is not None and rev < 50e6:
        return True
    if gm is not None and gm <= 0:
        return True
    if ocf is not None and ocf < 0 and runway is not None and runway < 36:
        return True
    return False


def _señal_ciclica(d: dict) -> bool:
    sector = (d.get("sector") or "").strip().lower()
    if sector in SECTORES_CICLICOS:
        return True
    cv = d.get("cv_margen_op_10a")
    if cv is not None and cv > 0.5:
        return True
    m_ltm, m_med = d.get("margen_op_ltm"), d.get("margen_op_mediana_10a")
    if m_ltm is not None and m_med is not None and m_med > 0 and m_ltm > 1.5 * m_med:
        return True
    return False


def _señal_compounder(d: dict) -> bool:
    fcf_a, roic_a = d.get("fcf_pos_anios_de5"), d.get("roic_gt15_anios_de5")
    return fcf_a is not None and roic_a is not None and fcf_a >= 4 and roic_a >= 4


def clasificar_arquetipo(datos: dict) -> str | None:
    """Arquetipo PROPUESTO (precedencia infra→pre_revenue→ciclica→compounder) o None si ninguna señal da true."""
    if _señal_infra(datos):
        return "infra"
    if _señal_pre_revenue(datos):
        return "pre_revenue"
    if _señal_ciclica(datos):
        return "ciclica"
    if _señal_compounder(datos):
        return "compounder"
    return None
