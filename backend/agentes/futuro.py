"""Calculadoras de futuro DETERMINISTAS (v2 doc 70 D4) — el "qué exige el precio" y "¿llega al hito?" que
hoy el LLM improvisa.

Principio (doc 70 D4, ambas IAs): una fórmula determinista alimentada con un supuesto optimista NO convierte
el supuesto en hecho. Por eso acá: (a) solo se computa con insumos REALES del pack; si falta algo →
**UNKNOWN**, no se fabrica; (b) escenarios base + estrés; (c) por ACCIÓN con dilución; (d) **base rates** —
la pieza anti-especulación: contrastar el crecimiento que el precio exige contra la clase de referencia.
Son funciones PURAS y testeables; `fuente_futuro` las enchufa al data pack como DataPoints DERIVED.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Resultado:
    valor: float | None          # None = UNKNOWN (faltan insumos)
    estado: str                  # COMPUTED | UNKNOWN
    detalle: str


def _unknown(motivo: str) -> Resultado:
    return Resultado(None, "UNKNOWN", motivo)


# --------------------------------------------------------------------------- funded critical path

def meses_runway(cash: float | None, burn_anual: float | None, *, estres: float = 1.0) -> Resultado:
    """Meses de pista = caja / (quema mensual × estrés). `burn_anual` NEGATIVO = quema (flujo op. del pack).
    `estres`>1 sube la quema (p.ej. 1.3 = 30% peor). UNKNOWN si falta un insumo o no quema."""
    if cash is None or burn_anual is None:
        return _unknown(f"falta insumo: {'cash' if cash is None else 'burn'}")
    if burn_anual >= 0:
        return Resultado(None, "UNKNOWN", "flujo operativo no-negativo: no quema caja")
    mensual = abs(burn_anual) / 12.0 * estres
    return Resultado(round(cash / mensual, 1), "COMPUTED", f"caja {cash:.0f} / quema {mensual:.0f}/mes (estrés {estres:g})")


def funded_hasta_hito(cash: float | None, burn_anual: float | None, meses_al_hito: int | None, *,
                      estres: float = 1.3, colchon_meses: int = 6) -> Resultado:
    """¿La caja alcanza hasta el próximo hito + colchón, bajo estrés? (doc 70 D2 test 2). valor = holgura en
    meses (positivo = cubre; negativo = gap). UNKNOWN si falta un insumo."""
    if meses_al_hito is None:
        return _unknown("falta meses_al_hito")
    rw = meses_runway(cash, burn_anual, estres=estres)
    if rw.valor is None:
        return rw
    holgura = round(rw.valor - (meses_al_hito + colchon_meses), 1)
    cubre = holgura >= 0
    return Resultado(holgura, "COMPUTED",
                     f"runway {rw.valor:.0f}m {'≥' if cubre else '<'} hito {meses_al_hito}m + colchón "
                     f"{colchon_meses}m (estrés {estres:g}) → {'cubre' if cubre else 'GAP'}")


# --------------------------------------------------------------------------- dilución para financiar el gap

def dilucion_por_gap(gap_usd: float | None, precio: float | None, shares: float | None, *,
                     descuento: float = 0.0) -> Resultado:
    """% de dilución de financiar un gap de capital emitiendo al precio actual (con `descuento` opcional).
    valor = dilución en %. doc 70 D4: el burden/valor se evalúa POR ACCIÓN, no solo por EV."""
    if gap_usd is None or precio is None or shares is None:
        return _unknown("faltan insumos (gap/precio/shares)")
    if gap_usd <= 0:
        return Resultado(0.0, "COMPUTED", "sin gap: no requiere emitir")
    precio_emision = precio * (1 - descuento)
    if precio_emision <= 0 or shares <= 0:
        return _unknown("precio o shares no válidos")
    nuevas = gap_usd / precio_emision
    return Resultado(round(nuevas / shares * 100, 1), "COMPUTED",
                     f"emitir {nuevas:.0f} acc @ {precio_emision:.2f} s/ {shares:.0f} = dilución")


# --------------------------------------------------------------------------- base rates (anti-especulación)

# Fracción APROXIMADA de empresas que SOSTIENEN un CAGR de revenue durante N años (patrón tipo Mauboussin:
# la persistencia de alto crecimiento decae fuerte). Es orientativa (calibrar con datos reales), pero el
# ORDEN DE MAGNITUD es el punto: "60% CAGR por 7 años" es rarísimo. Interpola lineal entre breakpoints.
_BASE_RATE = {   # (cagr_umbral, años) -> fracción histórica
    (0.20, 3): 0.30, (0.20, 5): 0.18, (0.20, 7): 0.10,
    (0.30, 3): 0.17, (0.30, 5): 0.08, (0.30, 7): 0.04,
    (0.40, 3): 0.09, (0.40, 5): 0.035, (0.40, 7): 0.015,
    (0.60, 3): 0.03, (0.60, 5): 0.01, (0.60, 7): 0.004,
}


def base_rate_cagr(cagr: float | None, anios: int | None) -> Resultado:
    """Fracción histórica (orientativa) de empresas que SOSTUVIERON ese CAGR de revenue por N años. La pieza
    anti-especulación: 'el precio exige 60% CAGR/7a' → '<0.5% lo logró'. UNKNOWN si falta insumo."""
    if cagr is None or anios is None:
        return _unknown("falta cagr o años")
    umbrales = sorted({u for u, _ in _BASE_RATE})
    anios_bp = sorted({a for _, a in _BASE_RATE})
    u = min(umbrales, key=lambda x: abs(x - cagr)) if cagr <= max(umbrales) else max(umbrales)
    a = min(anios_bp, key=lambda x: abs(x - anios))
    frac = _BASE_RATE[(u, a)]
    nota = "extrapolado (CAGR > tabla)" if cagr > max(umbrales) else "aprox."
    return Resultado(round(frac * 100, 2), "COMPUTED",
                     f"~{frac*100:.1f}% sostuvo ≥{u:.0%} CAGR por {a}a ({nota}); exigido {cagr:.0%}/{anios}a")


# --------------------------------------------------------------------------- D1: el puente económico al precio

@dataclass
class Escenario:
    """Un escenario del ANALISTA (juicio): métrica terminal + múltiplo de salida + horizonte + probabilidad.
    El determinismo NO los inventa — los pone el Analista; acá solo se hace la aritmética (doc 73 D1)."""
    nombre: str                  # bull | base | bear (o lo que use el analista)
    metrica_terminal: float      # p.ej. EBITDA o revenue terminal (USD), al nivel del múltiplo
    multiplo_salida: float       # x (EV/EBITDA, EV/ventas, …)
    anios: int                   # horizonte hasta el valor terminal
    prob: float                  # probabilidad del escenario (0-1)


@dataclass
class RetornoEscenarios:
    filas: list[dict]            # por escenario: nombre, valor_terminal, cagr_accionista, vp, prob
    vp_esperado: float | None    # Σ prob × VP descontado (ajustado por dilución), en USD
    ratio_vp_precio: float | None  # vp_esperado / valor_hoy: >1 atractivo · <1 se paga de más
    estado: str                  # COMPUTED | UNKNOWN
    detalle: str


def retorno_por_escenario(valor_hoy: float | None, escenarios: list[Escenario], *,
                          tasa: float = 0.15, dilucion_pct: float = 0.0) -> RetornoEscenarios:
    """Lleva los escenarios del Analista al PRECIO DE HOY (doc 73 D1). `valor_hoy` = EV o market cap (al MISMO
    nivel que el múltiplo). Por escenario: `valor_terminal = métrica × múltiplo`; CAGR del accionista (por
    acción, ajustado por dilución) y VP descontado a `tasa`. Devuelve el VP ESPERADO ponderado por probabilidad
    y su ratio contra el precio (>1 = el valor descontado esperado supera lo que se paga hoy; <1 = se paga de
    más por el crecimiento). Aritmética PURA: si faltan insumos → UNKNOWN, no se fabrica. `dilucion_pct` =
    dilución acumulada esperada hasta el terminal (0.20 = +20% de acciones → cada acción vale 1/1.2)."""
    if valor_hoy is None or valor_hoy <= 0:
        return RetornoEscenarios([], None, None, "UNKNOWN", "falta valor_hoy (EV o market cap) válido")
    vivos = [e for e in escenarios if e is not None and e.metrica_terminal is not None
             and e.multiplo_salida is not None and e.anios and e.anios > 0 and e.prob is not None]
    if not vivos:
        return RetornoEscenarios([], None, None, "UNKNOWN", "sin escenarios con métrica/múltiplo/años/prob")
    factor_dil = 1.0 + max(0.0, dilucion_pct)                      # cada acción vale 1/(1+dilución)
    suma_prob = sum(max(0.0, e.prob) for e in vivos) or 1.0        # normaliza si no suma ~1 (se avisa)
    filas: list[dict] = []
    vp_esperado = 0.0
    for e in vivos:
        valor_terminal = e.metrica_terminal * e.multiplo_salida
        vp = (valor_terminal / factor_dil) / ((1.0 + tasa) ** e.anios)     # VP por-acción-equivalente (USD)
        ratio = (valor_terminal / valor_hoy) / factor_dil                  # múltiplo de capital por acción
        cagr = ratio ** (1.0 / e.anios) - 1.0 if ratio > 0 else None
        p = max(0.0, e.prob) / suma_prob
        vp_esperado += p * vp
        filas.append({"nombre": e.nombre, "valor_terminal": round(valor_terminal, 0),
                      "cagr_accionista": round(cagr, 4) if cagr is not None else None,
                      "vp": round(vp, 0), "prob": round(p, 3)})
    ratio_vp = vp_esperado / valor_hoy
    aviso = "" if 0.98 <= sum(max(0.0, e.prob) for e in vivos) <= 1.02 else " (probs renormalizadas: no sumaban 1)"
    veredicto = "atractivo al precio" if ratio_vp >= 1.0 else "se paga de más por el crecimiento"
    return RetornoEscenarios(
        filas, round(vp_esperado, 0), round(ratio_vp, 3), "COMPUTED",
        f"VP esperado {vp_esperado:,.0f} vs precio {valor_hoy:,.0f} → ratio {ratio_vp:.2f} "
        f"({veredicto}); tasa {tasa:.0%}, dilución {dilucion_pct:.0%}{aviso}")


# --------------------------------------------------------------------------- D1 INVERSO: qué exige el precio

@dataclass
class ReverseBurden:
    metrica_requerida: float | None          # métrica terminal (EBITDA/revenue) que el precio exige para la hurdle
    equity_terminal_requerida: float | None  # valor de equity terminal necesario
    multiplo_requerido: float | None         # si se fija la métrica del escenario: a qué múltiplo habría que salir
    estado: str                              # COMPUTED | UNKNOWN
    detalle: str


def metrica_requerida_por_precio(valor_hoy: float | None, multiplo: float | None, anios: int | None, *,
                                 tasa: float = 0.15, dilucion_pct: float = 0.0,
                                 caja_neta_terminal: float = 0.0,
                                 metrica_escenario: float | None = None) -> ReverseBurden:
    """INVERSO de D1 (doc 74 §0 — reverse burden / expectations investing). Dado el PRECIO DE HOY (`valor_hoy`
    = market cap / equity), ¿qué métrica terminal (EBITDA o revenue) exige el precio para que comprar hoy rinda
    la hurdle?
        equity_terminal_requerida = valor_hoy × (1+tasa)^anios × (1+dilución)
        EV_terminal_requerido      = equity_terminal_requerida − caja_neta_terminal   (equity = EV + caja − deuda)
        métrica_requerida          = EV_terminal_requerido / múltiplo
    Si se pasa `metrica_escenario`, devuelve además a qué MÚLTIPLO habría que salir manteniéndola. Aritmética
    pura; UNKNOWN si faltan insumos. `caja_neta_terminal` = caja − deuda del año terminal (puede ser negativa).
    NO decide: informa qué exige el precio para que el PM lo confronte con la tesis (no con su propia historia)."""
    if valor_hoy is None or valor_hoy <= 0 or multiplo is None or multiplo <= 0 or not anios or anios <= 0:
        return ReverseBurden(None, None, None, "UNKNOWN", "faltan insumos (valor_hoy/múltiplo/años)")
    factor_dil = 1.0 + max(0.0, dilucion_pct)
    equity_req = valor_hoy * (1.0 + tasa) ** anios * factor_dil
    ev_req = equity_req - caja_neta_terminal
    metrica_req = ev_req / multiplo
    mult_req = (ev_req / metrica_escenario) if (metrica_escenario and metrica_escenario > 0) else None
    extra = f"; o manteniendo {metrica_escenario:,.0f} habría que salir a {mult_req:.1f}x" if mult_req else ""
    return ReverseBurden(
        round(metrica_req, 0), round(equity_req, 0), round(mult_req, 1) if mult_req else None, "COMPUTED",
        f"a {tasa:.0%}/año por {anios}a: equity terminal {equity_req:,.0f} → métrica terminal exigida "
        f"{metrica_req:,.0f} a {multiplo:g}x (dilución {dilucion_pct:.0%}){extra}")


@dataclass
class ProbImplicita:
    p_bull: float | None         # probabilidad de bull que el PRECIO implica para alcanzar la hurdle
    moic_bull: float | None
    moic_resto: float | None     # MOIC ponderado del resto (base/bear), con sus probs relativas
    target_moic: float | None    # (1+tasa)^anios: el MOIC que hay que batir
    estado: str                  # COMPUTED | UNKNOWN
    detalle: str


def _moic(valor_hoy: float, e: "Escenario", caja_neta_terminal: float, dilucion_pct: float) -> float:
    """MOIC por acción de un escenario: (equity terminal / equity hoy) / (1+dilución). equity = EV + caja neta."""
    equity_terminal = e.metrica_terminal * e.multiplo_salida + caja_neta_terminal
    return (equity_terminal / valor_hoy) / (1.0 + max(0.0, dilucion_pct))


def probabilidad_implicita_bull(valor_hoy: float | None, bull: "Escenario | None",
                                resto: list["Escenario"], *, tasa: float = 0.15, anios: int | None = None,
                                dilucion_pct: float = 0.0, caja_neta_terminal: float = 0.0) -> ProbImplicita:
    """¿Qué probabilidad de bull IMPLICA el precio de hoy para batir la hurdle? (doc 74 §0 — expectations
    investing, Mauboussin/Rappaport). Con el bull y el resto (base/bear) de MOIC fijo, resuelve:
        p_bull × MOIC_bull + (1−p_bull) × MOIC_resto = (1+tasa)^anios
    El PM no juzga si el '25%' del analista es correcto, sino si el precio exige una probabilidad de bull
    razonable. p_bull>1 → ni con 100% bull alcanza (caro); p_bull<0 → hasta el downside bate la hurdle (barato).
    Todos los escenarios deben compartir horizonte (MOICs comparables); UNKNOWN si no, o si faltan insumos."""
    if valor_hoy is None or valor_hoy <= 0 or bull is None or not resto:
        return ProbImplicita(None, None, None, None, "UNKNOWN", "faltan insumos (valor_hoy/bull/resto)")
    anios = anios if anios is not None else bull.anios
    if not anios or anios <= 0:
        return ProbImplicita(None, None, None, None, "UNKNOWN", "falta horizonte")
    if any(e.anios != anios for e in [bull, *resto]):
        return ProbImplicita(None, None, None, None, "UNKNOWN", "escenarios con horizontes distintos: MOIC no comparable")
    target = (1.0 + tasa) ** anios
    m_bull = _moic(valor_hoy, bull, caja_neta_terminal, dilucion_pct)
    suma_p = sum(max(0.0, e.prob) for e in resto) or float(len(resto))
    pesos = [(max(0.0, e.prob) or 1.0) / suma_p for e in resto] if sum(max(0.0, e.prob) for e in resto) > 0 \
        else [1.0 / len(resto)] * len(resto)
    m_resto = sum(w * _moic(valor_hoy, e, caja_neta_terminal, dilucion_pct) for w, e in zip(pesos, resto))
    if abs(m_bull - m_resto) < 1e-9:
        return ProbImplicita(None, round(m_bull, 2), round(m_resto, 2), round(target, 2), "UNKNOWN",
                             "bull y resto con el mismo MOIC: la probabilidad no está determinada")
    p = (target - m_resto) / (m_bull - m_resto)
    if p > 1.0:
        nota = f"ni con 100% bull alcanza {tasa:.0%}/año (precio exige MOIC {target:.2f}, bull da {m_bull:.2f}): caro"
    elif p < 0.0:
        nota = f"hasta el downside bate {tasa:.0%}/año (resto MOIC {m_resto:.2f} ≥ {target:.2f}): barato"
    else:
        nota = f"el precio exige P(bull) ≥ {p:.0%} para {tasa:.0%}/año en {anios}a (MOIC bull {m_bull:.2f} / resto {m_resto:.2f})"
    return ProbImplicita(round(p, 3), round(m_bull, 2), round(m_resto, 2), round(target, 2), "COMPUTED", nota)
