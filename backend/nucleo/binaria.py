"""Gramática binaria — SKELETON (doc 42 §1, Bloque 2 D1). El piso de liquidación + el quinto estado.

Para pre-revenue con payoff BINARIO (aprobación FDA, captura de programa, licencia). La mecánica completa
(P_req@r vs base-rate, V_éxito Tier-A/B/C) está DIFERIDA (necesita tablas externas + extracción de contratos).
Lo buildable-hoy y de alto valor: **`V_fracaso`** (el piso de liquidación, SOLO XBRL, las 2 IAs lo especificaron
idéntico) + el **quinto estado** (doc 42, IA2): sin base-rate table auditable, un binario solo es underwritable
si cotiza cerca del piso (`Precio_ops ≤ V_fracaso × k`) — si no, NON_UNDERWRITABLE (no se puede pricear el evento
sin denominador). Con 70% pre-revenue, este estado se traga mucho del universo — es correcto, no un defecto.

Guardas (doc 42 §Q4): V_fracaso SOLO de XBRL; el texto solo puede RESTAR, nunca sumar; default 0 legítimo y
frecuente (converts). Nunca NOLs/goodwill/IP/PP&E-sin-haircut/ATM.
"""
from __future__ import annotations

from backend.nucleo import politica


def v_fracaso(*, cash: float | None, short_term_inv: float | None, debt: float | None,
              burn_mensual: float | None, meses_al_hito: float | None, opex_trimestral: float | None) -> float:
    """Piso de liquidación por acción-independiente (doc 42 §Q4), SOLO XBRL. `V_fracaso = cash + ST_inv − debt −
    burn×T_P90 − wind_down`; floored en 0. `burn_mensual` = −(CFO−capex)/12 (positivo si quema). `meses_al_hito`
    se estira por el P90 de retrasos. Devuelve el valor absoluto del piso (≥0); dividir por shares afuera."""
    caja = (cash or 0.0) + (short_term_inv or 0.0)
    T = (meses_al_hito or 0.0) * politica.BURN_HORIZONTE_P90
    burn_total = (burn_mensual or 0.0) * T if (burn_mensual and burn_mensual > 0) else 0.0
    wind_down = (opex_trimestral or 0.0) * politica.WIND_DOWN_QTRS
    return max(0.0, caja - (debt or 0.0) - burn_total - wind_down)


def estado_binario(*, P_ops: float | None, v_fracaso_abs: float | None, base_rate_n: int = 0,
                   k: float | None = None) -> dict:
    """Estado de valuación de un binario (doc 42 §1). SKELETON: sin base-rate table (n < mínimo), aplica el
    QUINTO ESTADO — solo underwritable si el precio está protegido por el piso. Con tabla, la mecánica P_req@r
    está diferida → hoy también cae al quinto estado (honesto). Devuelve {estado, ratio_piso, motivo}."""
    k = k if k is not None else politica.K_FLOOR_BINARIA
    if not P_ops or P_ops <= 0 or v_fracaso_abs is None:
        return {"estado": "NON_UNDERWRITABLE", "ratio_piso": None, "motivo": "sin P_ops o V_fracaso"}
    ratio = v_fracaso_abs / P_ops                         # cuánto del precio está cubierto por el piso de liquidación
    if base_rate_n >= politica.BASE_RATE_N_MIN:
        # tabla disponible: la mecánica P_req@r/V_éxito está DIFERIDA → por ahora, mismo quinto estado + nota.
        motivo_extra = " (base-rate disponible pero P_req@r diferido → quinto estado interino)"
    else:
        motivo_extra = " (sin base-rate table → quinto estado: solo a precio de piso)"
    if ratio >= 1.0:
        return {"estado": "COVERED", "ratio_piso": round(ratio, 2),
                "motivo": f"precio ≤ piso de liquidación (ratio {ratio:.2f}) → margen de seguridad{motivo_extra}"}
    if ratio >= 1.0 / k:
        return {"estado": "STRETCH", "ratio_piso": round(ratio, 2),
                "motivo": f"precio cerca del piso (ratio {ratio:.2f} ≥ 1/{k}){motivo_extra}"}
    mult = f"{1/ratio:.1f}× el piso" if ratio > 0 else "piso 0 (sin protección: converts/quema > caja)"
    return {"estado": "NON_UNDERWRITABLE", "ratio_piso": round(ratio, 2),
            "motivo": f"precio {mult}, sin base-rate para pricear el evento → carril/probe{motivo_extra}"}
