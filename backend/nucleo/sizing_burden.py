"""Sizing CONTINUO del bucket growth / owner-FCF<0 (doc 47 — triangulación 3 voces + medición 2026-09-03).

Reemplaza el modo de falla "todo lo que rutea BURDEN → OPTION_PRICED (masa puntual ~2%)" por un **techo con
distribución debajo** (las 3 IAs convergieron: *"no estás equivocado en castigar owner-FCF<0, estás equivocado en
castigarlo de manera binaria"*). El gate `owner-FCF post-SBC < 0` se queda como CLASIFICADOR DE RÉGIMEN (define el
techo del bucket), NO como sizer. Dentro del techo, el tamaño escala con MAGNITUD:

    SIZE = CAP × f_val(T) × q_GM × q_apal × q_ps × d_sbc      (multiplicativo, NO-compensatorio)

- **f_val(T):** años de compounding que EXIGE el precio (T, no burden crudo — la #3 demostró que el burden ordena
  al revés: RKLB burden 41× exige MENOS años que NET 16.6× porque crece más). Menos T = más barato = más tamaño.
- **q_GM / q_apal:** calidad de margen + apalancamiento operativo DEMOSTRADO (apal ya viene con lag 3Q, doc 47).
- **q_ps (acretividad):** ΔGP/acción ≥ 12% ⇒ la dilución financia algo (compounder), no un diluidor serial. Es
  el mejor test anti-diluidor (la #3). Medido: S +16.7%, NET +23.5% (acretivos); VRNS +7.4% (modesto).
- **d_sbc:** impuesto CONTINUO de dilución (no el cliff SBC>25%). El SBC en $ ya lo cobra el reverse-DCF vía
  owner-FCF (chequeo doble-conteo, doc 47), así que acá es un tax suave adicional por SBC/rev alto.

**IMPORTANTE (doc 39, sándwich):** esto produce un **CAP (techo)**, NO el tamaño final. La SELECCIÓN y el size los
hace el PM DENTRO del cap — el determinismo solo pone el LÍMITE. Por eso el cap tiene PISO (`CAP_FLOOR`, 4%): un
nombre elegible nunca recibe cap 0, porque eso le prohibiría al PM una tesis de ACELERACIÓN de crecimiento (el
determinismo solo ve g DEMOSTRADO; el futuro lo juzga el PM). El mérito sube el techo hacia `CAP_MAX` (8%).

Reglas: cap de CLUSTER a nivel cartera (Σ ≤ 2×CAP, riesgo de financiamiento correlacionado — N_eff: ρ≈0.7 ⇒ 5
nombres ≈ 1.3 apuestas). RKLB-type (pre-profit + pura opción) NO va acá: carril (doc 29), base-rate de hito.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from backend.nucleo import politica


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def t_fade(burden: float | None, g: float | None, *, g_terminal: float = 0.08,
           t_ramp_ini: int = 5, t_ramp_fin: int = 10, t_max: int = 30) -> float | None:
    """Años de compounding que EXIGE el precio, con FADE (doc 47 IA#3). Cuántos años de crecer el gross profit
    a `g` (con g→`g_terminal` entre los años t_ramp_ini y t_ramp_fin) hasta cubrir el `burden` (×GP que el precio
    demanda). Es la variable de sizing CORRECTA: normaliza el burden por crecimiento (RKLB 41× exige MENOS años
    que NET 16.6× porque crece más). None (no cubre en `t_max`) → no underwriteable. burden≤1 → 0 (ya cubierto)."""
    if burden is None or g is None or burden <= 1.0:
        return 0.0 if (burden is not None and burden <= 1.0) else None
    prod, prev = 1.0, 1.0
    for T in range(1, t_max + 1):
        if T <= t_ramp_ini:
            g_t = g
        elif T >= t_ramp_fin:
            g_t = g_terminal
        else:
            g_t = g + (g_terminal - g) * (T - t_ramp_ini) / (t_ramp_fin - t_ramp_ini)
        prod *= (1.0 + g_t)
        if prod >= burden:                       # interpola dentro del año para suavizar
            frac = (burden - prev) / (prod - prev) if prod > prev else 0.0
            return round(T - 1 + frac, 2)
        prev = prod
    return None


def f_val(t_star: float | None) -> float:
    """Factor de VALUACIÓN por T (años de compounding que exige el precio). Continuo, sin acantilado.
    T ≤ T_min → 1.0 (barato); T ≥ T_max → 0.0 (no underwriteable). None (sin raíz) → 0.0."""
    if t_star is None:
        return 0.0
    tmin, tmax = politica.UMBRAL_T_COVERED, politica.UMBRAL_T_OPTION
    return _clip((tmax - t_star) / (tmax - tmin), 0.0, 1.0)


def q_gm(gross_margin: float | None) -> float:
    """Calidad de margen bruto. <35% → piso 0.20; 75% → 1.0. El GM alto es condición para que el
    apalancamiento futuro pueda existir."""
    if gross_margin is None:
        return 0.20
    return _clip((gross_margin - 0.35) / (0.75 - 0.35), 0.20, 1.0)


def q_apal(apal_lag: float | None) -> float:
    """Apalancamiento operativo (ya con lag 3Q). Rampa, NO acantilado en 1.0. None (no medible) → 0.70
    (neutral penalizado, no 'cadáver'). apal 0.5 → 0.4; 1.0 → 0.7; 1.5 → 1.0 (cap 1.2)."""
    if apal_lag is None:
        return 0.70
    return _clip(0.40 + 0.60 * (apal_lag - 0.5) / (1.2 - 0.5), 0.40, 1.20)


def q_ps(g_gp_por_accion: float | None) -> float:
    """Gate de ACRETIVIDAD (el mejor anti-diluidor, doc 47 IA#3): ΔGP/acción(8Q anual). ≥12% → 1.0 (la
    dilución financia algo acretivo = compounder); 0-12% → 0.60; <0 → 0.25 (diluidor: pagás la fiesta)."""
    if g_gp_por_accion is None:
        return 0.60
    if g_gp_por_accion >= politica.ACRETIVIDAD_MIN:
        return 1.00
    if g_gp_por_accion >= 0.0:
        return 0.60
    return 0.25


@dataclass
class SizeBurden:
    ticker: str
    size: float                 # CAP (techo) del nombre — el PM elige el tamaño real DENTRO de este cap (doc 39/47).
                                # Rango [CAP_FLOOR, CAP_MAX]; 0 solo si va al carril. NO es el tamaño final.
    factores: dict              # trazabilidad de cada factor
    a_carril: bool = False      # pre-profit + pura opción → carril (doc 29), NO libro duro
    motivo: str = ""


def size_burden(ticker: str, *, t_star: float | None, gross_margin: float | None, apal_lag: float | None,
                g_gp_por_accion: float | None, fcf_pre_sbc: float | None, burden: float | None = None,
                runway_meses: float | None = None, cap: float | None = None) -> SizeBurden:
    """Tamaño continuo del bucket (doc 47, v2.2). Producto de 4 factores (SIN impuesto SBC: la dilución ya se cobra
    2× vía burden+acretividad; un 3er factor = triple conteo, la IA#3 lo marcó). Gate A: pre-profit (fcf_pre_sbc<0)
    con burden ALTO (pura opción, tipo RKLB) → carril; con burden moderado (comercial-que-invierte, tipo KTOS) →
    libro duro CHICO por T (no al sleeve especulativo)."""
    CAP_MAX = cap if cap is not None else politica.CAP_BURN_BUCKET
    CAP_FLOOR = politica.CAP_FLOOR_BURN
    # Gate A (régimen, doc 47 Q4 — convexidad): pre-profit (no genera cash ni antes de pagar en acciones) va al
    # carril SOLO si además el precio es PURA OPCIÓN (burden > umbral, RKLB 41×): ahí vive el 10×, sizeado por
    # base-rate de hito. Un comercial-que-invierte con burden moderado (KTOS 7.5×) NO es una lotería → libro duro.
    if fcf_pre_sbc is not None and fcf_pre_sbc < 0 and (burden is None or burden > politica.BURDEN_CARRIL_MIN):
        return SizeBurden(ticker, 0.0, {"fcf_pre_sbc": round(fcf_pre_sbc / 1e6, 1), "burden": burden}, a_carril=True,
                          motivo=f"pre-profit + pura opción (burden {burden}) → carril (base-rate), no libro duro")
    # MÉRITO ∈ [0,1] (producto no-compensatorio de los 4 factores). El CAP interpola en [FLOOR, MAX]: un nombre
    # elegible NUNCA baja de FLOOR (el PM puede tener tesis de aceleración de crecimiento que el determinismo, que
    # solo usa g DEMOSTRADO, no ve). El mérito sube el techo; NO es el tamaño (eso lo elige el PM adentro del cap).
    fv, qg, qa, qp = f_val(t_star), q_gm(gross_margin), q_apal(apal_lag), q_ps(g_gp_por_accion)
    merito = fv * qg * qa * qp
    cap_val = CAP_FLOOR + (CAP_MAX - CAP_FLOOR) * merito
    factores = {"f_val": round(fv, 3), "q_gm": round(qg, 3), "q_apal": round(qa, 3),
                "q_ps": round(qp, 3), "merito": round(merito, 3)}
    return SizeBurden(ticker, round(cap_val, 4), factores,
                      motivo=f"cap = {CAP_FLOOR:.0%} + ({CAP_MAX:.0%}−{CAP_FLOOR:.0%})×mérito({merito:.2f}) = {cap_val:.1%}")


def aplicar_cap_cluster(sizes: list[SizeBurden], cap: float | None = None) -> list[SizeBurden]:
    """Cap de CLUSTER (doc 47 Q4): Σ del bucket ≤ CLUSTER_CAP_MULT × CAP. Riesgo de ventana de financiamiento
    correlacionado — todos los owner-FCF<0 comparten el factor 'acceso a capital barato'; en un repricing caen
    juntos (N_eff≈1.3, no 5). Si Σ excede, escala TODO el bucket pro-rata."""
    CAP = cap if cap is not None else politica.CAP_BURN_BUCKET
    limite = politica.CLUSTER_CAP_MULT * CAP
    total = sum(s.size for s in sizes)
    if total <= limite or total <= 0:
        return sizes
    factor = limite / total
    for s in sizes:
        if s.size > 0:
            s.size = round(s.size * factor, 4)
            s.motivo += f" · cap-cluster ×{factor:.2f} (Σ {total:.1%} > {limite:.1%})"
    return sizes
