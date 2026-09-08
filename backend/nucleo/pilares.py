"""Evaluadores de PILARES — hechos → banda (doc 26 v3 §3).

Cada pilar mapea hechos ya extraídos/verificados a una Banda (CRÍTICO/DÉBIL/SUFICIENTE/FUERTE)
+ confianza + la evidencia citada (para la ficha del PM). Determinista y puro.

Estado:
  - demanda_cuello → reusa el tier de demanda del gate (VALIDATED/COMMITTED/REALIZED) + nodo. LISTO.
  - economia      → reusa quality.py (márgenes, crecimiento, recurrencia, wins). LISTO.
  - ejecucion     → GAP (management por evidencia: Form 4, guidance-vs-actuals, dilución por acción).
  - valuacion_asim→ GAP (expectativas implícitas + bear por dilución).
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.nucleo.evaluacion import Banda, Pilar
from backend.nucleo.quality import HechosQuality, calcular_quality_tier

# quality tier 1-4 → banda. tier 1 = DÉBIL (no CRÍTICO: pasó el gate, hay negocio mínimo);
# CRÍTICO se reserva para economía ROTA (margen negativo), no para "poca calidad".
_QUALITY_A_BANDA = {4: Banda.FUERTE, 3: Banda.SUFICIENTE, 2: Banda.DEBIL, 1: Banda.DEBIL}

# tier de madurez de demanda (gate_evidencia): 0 UNKNOWN · 1 VALIDATED · 2 COMMITTED · 3 REALIZED
# UNKNOWN(0) NO es CRÍTICO (doc 34 §3bis, triangulado): auto-vetar por AUSENCIA de evidencia = "el peor error"
# (un falso-negativo del retrieval con cara de objetividad). "No sé" ≠ "no hay demanda". → DÉBIL + conf.
# insuficiente (interino). El TARGET es ABSTENCIÓN determinista (EVIDENCIA_INSUFICIENTE → fuera del ciclo), que
# requiere el estado de abstención de primera clase (build pendiente). Solo FALSE_EXPLÍCITO auto-vetea.
_DEMANDA_A_BANDA = {3: Banda.FUERTE, 2: Banda.SUFICIENTE, 1: Banda.DEBIL, 0: Banda.DEBIL}
_DEMANDA_NOMBRE = {3: "REALIZED", 2: "COMMITTED", 1: "VALIDATED", 0: "UNKNOWN"}


def pilar_economia(h: HechosQuality) -> Pilar:
    """Economía + captura de valor (Pilar 2). Reusa el quality tier."""
    q = calcular_quality_tier(h)
    banda = _QUALITY_A_BANDA.get(q["tier"], Banda.DEBIL)
    if h.margen_bruto is not None and h.margen_bruto < 0:
        banda = Banda.CRITICO                       # unit economics rotas → topea
    conf = ("suficiente" if h.margen_bruto is not None and h.crecimiento_organico_elegible is not None
            else "insuficiente")
    hechos = [{"claim": m, "fuente_tier": "auditado/XBRL"} for m in q["motivos"]]
    return Pilar("economia", banda, conf, hechos=hechos,
                 nota=f"quality tier {q['tier']} ({q['puntos']} pts)")


def pilar_demanda(tier_demanda: int, *, en_nodo: bool, materialidad: str = "UNKNOWN",
                  hechos: list | None = None) -> Pilar:
    """Demanda + posición en el cuello (Pilar 1). Usa el tier de madurez del gate + nodo.

    materialidad: 'ALTA'|'MEDIA'|'BAJA'|'UNKNOWN' (determinista si hay número; UNKNOWN → conf. insuf.).
    """
    banda = _DEMANDA_A_BANDA.get(tier_demanda, Banda.CRITICO)
    if not en_nodo and banda == Banda.FUERTE:
        banda = Banda.SUFICIENTE                    # sin posición de cuello no llega a fuerte
    conf = "suficiente" if materialidad != "UNKNOWN" else "insuficiente"
    return Pilar("demanda_cuello", banda, conf, hechos=hechos or [],
                 nota=f"demanda {_DEMANDA_NOMBRE.get(tier_demanda, '?')}, "
                      f"en_nodo={en_nodo}, materialidad={materialidad}")


@dataclass
class HechosEjecucion:
    """Ejecución/management por EVIDENCIA (Pilar 3, doc 26). NADA de "buen equipo": solo hechos.
    Dilución acá es TRACK RECORD (histórica); la dilución como RIESGO forward vive en CRR/caps.
    """
    guidance_cumplido_ratio: float | None = None   # fracción de últimos N trim con guidance cumplido
    insider_net_usd: float | None = None           # compras − ventas netas de insiders (Form 4), 6-12m
    dilucion_3y: float | None = None               # crecimiento REALIZADO de share count 3y (fracción)
    crecimiento_por_accion: float | None = None    # crecimiento de revenue/FCF POR ACCIÓN (no agregado)
    restatement_reciente: bool = False             # integridad rota
    sbc_pct_revenue: float | None = None           # SBC / revenue (dilución silenciosa)


def pilar_ejecucion(h: HechosEjecucion) -> Pilar:
    """Ejecución + creación de valor POR ACCIÓN (Pilar 3). Todo desde evidencia dura."""
    hechos: list[dict] = []
    puntos = 0

    # Críticos: integridad rota, o dilución masiva SIN crecimiento por acción (destrucción de valor).
    critico = h.restatement_reciente or (
        h.dilucion_3y is not None and h.dilucion_3y > 0.40
        and (h.crecimiento_por_accion is None or h.crecimiento_por_accion <= 0))
    if h.restatement_reciente:
        hechos.append({"claim": "restatement/material weakness reciente", "fuente_tier": "filing", "signo": "-"})

    if h.guidance_cumplido_ratio is not None:      # promesa falsable (guidance-vs-actuals)
        r = h.guidance_cumplido_ratio
        if r >= 0.75:
            puntos += 2; hechos.append({"claim": f"guidance cumplido {r:.0%} de los trimestres", "fuente_tier": "filing", "signo": "+"})
        elif r >= 0.50:
            puntos += 1
        else:
            puntos -= 1; hechos.append({"claim": f"guidance cumplido solo {r:.0%}", "fuente_tier": "filing", "signo": "-"})

    if h.insider_net_usd is not None:              # Form 4: compras con plata propia
        if h.insider_net_usd > 0:
            puntos += 1; hechos.append({"claim": f"insiders compraron neto ${h.insider_net_usd/1e6:.1f}M", "fuente_tier": "Form 4", "signo": "+"})
        elif h.insider_net_usd < 0:
            puntos -= 1; hechos.append({"claim": f"insiders vendieron neto ${-h.insider_net_usd/1e6:.1f}M", "fuente_tier": "Form 4", "signo": "-"})

    if h.dilucion_3y is not None:
        if h.dilucion_3y < 0.10:
            puntos += 1; hechos.append({"claim": f"dilución 3y {h.dilucion_3y:.0%} (baja)", "fuente_tier": "XBRL", "signo": "+"})
        elif h.dilucion_3y > 0.40:
            puntos -= 2; hechos.append({"claim": f"dilución 3y {h.dilucion_3y:.0%} (alta)", "fuente_tier": "XBRL", "signo": "-"})

    if h.sbc_pct_revenue is not None:              # SBC/revenue: dilución SILENCIOSA (no aparece en cash)
        if h.sbc_pct_revenue > 0.20:
            puntos -= 1; hechos.append({"claim": f"SBC {h.sbc_pct_revenue:.0%} del revenue (dilución silenciosa alta)", "fuente_tier": "XBRL", "signo": "-"})
        elif h.sbc_pct_revenue < 0.05:
            puntos += 1; hechos.append({"claim": f"SBC {h.sbc_pct_revenue:.0%} del revenue (baja)", "fuente_tier": "XBRL", "signo": "+"})

    if h.crecimiento_por_accion is not None:
        if h.crecimiento_por_accion > 0.10:
            puntos += 1; hechos.append({"claim": f"crecimiento POR ACCIÓN {h.crecimiento_por_accion:.0%}", "fuente_tier": "XBRL", "signo": "+"})
        elif h.crecimiento_por_accion < 0:
            puntos -= 1; hechos.append({"claim": f"crecimiento por acción NEGATIVO {h.crecimiento_por_accion:.0%}", "fuente_tier": "XBRL", "signo": "-"})

    if critico:
        banda = Banda.CRITICO
    elif puntos >= 3:
        banda = Banda.FUERTE
    elif puntos >= 1:
        banda = Banda.SUFICIENTE
    else:
        banda = Banda.DEBIL

    # Confianza: alcanza con dilución + crecimiento por acción (señales duras de XBRL).
    # Guidance-vs-actuals queda diferido (no está en XBRL) — mejora la banda cuando esté.
    conf = ("suficiente" if h.dilucion_3y is not None and h.crecimiento_por_accion is not None
            else "insuficiente")
    # El CRÍTICO de ejecución es de SUPERVIVENCIA/INTEGRIDAD (restatement/material weakness · dilución tóxica
    # que destruye valor por acción) → veto DURO legítimo (doc 39 §2.1). NO es "no va a funcionar".
    return Pilar("ejecucion", banda, conf, hechos=hechos,
                 nota=f"{puntos} pts, restatement={h.restatement_reciente}",
                 es_veto_supervivencia=bool(critico))


@dataclass
class HechosValuacion:
    """Valuación + asimetría (Pilar 4, doc 26 §6). Expectativas IMPLÍCITAS (no price target del LLM)
    + bear por DILUCIÓN (no compresión de múltiplo). Todo determinista."""
    ev_actual: float | None = None
    revenue_ltm: float | None = None
    multiplo_terminal: float | None = None       # EV/Revenue de comparables MADUROS (P50 de datos, no opinión)
    horizonte_anios: int = 5
    tasa_descuento: float = 0.14                  # por arquetipo
    revenue_max_capacidad: float | None = None    # capacidad × utilización × precio (techo físico del cuello)
    respaldo_backlog: bool = False                # backlog/contratos respaldan el crecimiento implícito
    bear_downside_pct: float | None = None        # downside en el bear por DILUCIÓN (negativo, ej. -0.40)


def _cagr_implicito(h: HechosValuacion):
    """Reverse: ¿qué revenue exige el precio? R = EV × (1+d)^h / múltiplo_terminal → CAGR implícito."""
    if not (h.ev_actual and h.revenue_ltm and h.multiplo_terminal and h.revenue_ltm > 0):
        return None, None
    r_implied = h.ev_actual * (1 + h.tasa_descuento) ** h.horizonte_anios / h.multiplo_terminal
    cagr = (r_implied / h.revenue_ltm) ** (1 / h.horizonte_anios) - 1
    return r_implied, cagr


def pilar_valuacion(h: HechosValuacion) -> Pilar:
    """RETIRADO del flujo (doc 33/34): valuación dejó de ser Pilar 4 y pasó a GATE SEPARADO (el falsador
    CAGR cohort-free de `bridge.py`). Esta función usa comparables (`multiplo_terminal`), que quedaron
    diferidos (doc 28 §2 cohort-free). Ya NO la llama `ranking.evaluar_ticker`. Se conserva como
    referencia hasta cablear el gate (doc 34 §4 paso 3); no usar en la composición de elegibilidad.

    El precio ENUNCIA la hipótesis (CAGR implícito); los filings la TESTEAN (capacidad/backlog).
    El bear (dilución) ajusta la banda por downside."""
    r_implied, cagr = _cagr_implicito(h)
    if cagr is None:
        return Pilar("valuacion_asim", Banda.DEBIL, "insuficiente",
                     nota="faltan inputs de valuación (EV/revenue/múltiplo)")
    hechos = [{"claim": f"el precio exige {cagr:.0%} CAGR de revenue a {h.horizonte_anios}a "
                        f"(≈${r_implied/1e6:.0f}M)", "fuente_tier": "derivado"}]
    excede = h.revenue_max_capacidad is not None and r_implied > h.revenue_max_capacidad

    # Exigencia del precio → componente de upside (cuánto techo queda).
    if cagr >= 0.50 and (excede or not h.respaldo_backlog):
        exig, banda = "imposible (priced for perfection)", Banda.CRITICO
    elif cagr >= 0.35:
        exig, banda = "difícil", Banda.DEBIL
    elif cagr >= 0.15:
        exig, banda = "razonable", Banda.SUFICIENTE
    else:
        exig, banda = "poco / barato", Banda.FUERTE
    hechos.append({"claim": f"exigencia del precio: {exig}"
                            + (" — excede capacidad instalada" if excede else ""), "fuente_tier": "derivado"})

    # Downside: bear por DILUCIÓN ajusta la banda.
    if h.bear_downside_pct is not None:
        hechos.append({"claim": f"bear por dilución {h.bear_downside_pct:.0%}", "fuente_tier": "derivado (CRR)"})
        if h.bear_downside_pct <= -0.60:
            banda = Banda(max(int(Banda.CRITICO), int(banda) - 1))   # downside profundo baja
        elif h.bear_downside_pct >= -0.20:
            banda = Banda(min(int(Banda.FUERTE), int(banda) + 1))    # downside protegido sube

    conf = "suficiente" if (h.multiplo_terminal is not None and h.bear_downside_pct is not None) else "insuficiente"
    return Pilar("valuacion_asim", banda, conf, hechos=hechos,
                 nota=f"CAGR implícito {cagr:.0%}, exigencia {exig}")
