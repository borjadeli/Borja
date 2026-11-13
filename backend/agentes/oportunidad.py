"""Motor de oportunidad (r9, doc 80 §D · P1) — qué merece el deep caro.

Dos poblaciones, dos lógicas (doc 80 §D):
- **Con ficha vigente:** NO necesita score — tiene la DISTANCIA EXACTA a su zona de compra (del reloj rápido).
- **Sin ficha vigente (ficha-less):** se rankea con un SCORE determinista:

    score = (V · M · C)^(1/3) × A + bonus
    V = pctl(g_entregado − g_exigido)   # BRECHA DE EXPECTATIVAS dentro del cluster (no baratura)
    M = pctl(momentum de fundamentales)  # aceleración de ventas, RPO/ventas, Δ margen
    C = estado_cuello × prioridad_macro × rol_en_cuello
    A = compuerta de supervivencia ∈ {0, 0.5, 0.7, 1}

Media geométrica: un CERO en cualquier pata mata el candidato (no se compra barato-que-muere). Percentiles
DENTRO del cluster (un cuello tiene pocos nombres). 100% determinista — el ranking NO usa ningún insumo escrito
por el Analista. El LLM (Triage) solo elige dentro del top-K; no produce el ranking.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

# --------------------------------------------------------------------------- patas del score (puras)

_ESTADO_CUELLO = {"confirmado": 1.0, "vigilancia": 0.6, "promesa": 0.3, "resolviendose": 0.15, "resuelto": 0.0}
_ROL = {"lider": 1.0, "retador": 0.8, "periferico": 0.5, "periférico": 0.5}


def cuello_score(estado: str | None, *, prioridad_macro: float = 0.75, rol: str | None = None) -> float:
    """C ∈ [0,1]: calidad del cuello × prioridad macro del ciclo × rol de la empresa en el cuello."""
    e = _ESTADO_CUELLO.get((estado or "").lower(), 0.3)
    r = _ROL.get((rol or "").lower(), 0.6)
    return round(e * max(0.0, min(1.0, prioridad_macro)) * r, 4)


def compuerta_supervivencia(*, runway_meses: float | None = None, going_concern: bool = False,
                            dilucion_overhang: bool = False, deuda_neta_sobre_equity: float | None = None) -> float:
    """A ∈ {0, 0.5, 0.7, 1}: gate duro de supervivencia (doc 80 §D, anti value-trap). going_concern o runway muy
    corto → 0 (no es oportunidad, es riesgo). Para la filosofía power-law: una empresa puede 5× sus ventas y
    destruir valor por acción emitiendo — la supervivencia manda."""
    if going_concern:
        return 0.0
    if runway_meses is not None and runway_meses < 6:
        return 0.0
    penal = dilucion_overhang or (deuda_neta_sobre_equity is not None and deuda_neta_sobre_equity > 2.0)
    if runway_meses is not None and runway_meses < 12:
        return 0.5 if penal else 0.7
    return 0.7 if penal else 1.0


def percentiles_cluster(valores: dict[str, float | None]) -> dict[str, float | None]:
    """Percentil [0,1] de cada valor DENTRO del dict (el cluster): 1.0 = el mejor (mayor), 0.0 = el peor. None
    queda None (sin dato). Un cluster de 1 → 0.5 (neutral, no se puede rankear)."""
    vivos = [(tk, v) for tk, v in valores.items() if v is not None]
    out: dict[str, float | None] = {tk: None for tk in valores}
    if not vivos:
        return out
    if len(vivos) == 1:
        out[vivos[0][0]] = 0.5
        return out
    ordenado = sorted(vivos, key=lambda x: x[1])      # ascendente: menor = peor
    n = len(ordenado)
    for i, (tk, _v) in enumerate(ordenado):
        out[tk] = round(i / (n - 1), 4)               # i=0 (peor) → 0.0, i=n-1 (mejor) → 1.0
    return out


def score_ficha_less(*, v: float | None, m: float | None, c: float, a: float, bonus: float = 0.0) -> float | None:
    """(V·M·C)^(1/3) × A + bonus. V None (sin ventas → sin brecha) → score None (compite solo por exploración)."""
    if v is None:
        return None
    m = 0.5 if m is None else m                       # sin momentum medible → neutral
    prod = max(0.0, v) * max(0.0, m) * max(0.0, c)
    base = prod ** (1.0 / 3.0)
    return round(base * a + bonus, 4)


# --------------------------------------------------------------------------- brecha de expectativas (v1)

def g_exigido(*, ev: float | None, revenue: float | None, mult_ref: float = 4.0, anios: int = 4,
              hurdle: float = 0.20) -> float | None:
    """CAGR de ventas que el EV de HOY descuenta: para rendir `hurdle` saliendo a `mult_ref` (EV/ventas) en
    `anios`, las ventas tienen que crecer a esta tasa. g = (EV·(1+hurdle)^anios / (mult_ref·ventas))^(1/anios) − 1.
    v1 con `mult_ref` de referencia (a afinar con la mediana del cuello). None si faltan insumos o ventas ≤ 0."""
    if not ev or ev <= 0 or not revenue or revenue <= 0 or mult_ref <= 0:
        return None
    rev_terminal_req = ev * ((1.0 + hurdle) ** anios) / mult_ref
    ratio = rev_terminal_req / revenue
    return round(ratio ** (1.0 / anios) - 1.0, 4) if ratio > 0 else None


def candidato_desde_metricas(ticker: str, *, cluster: str | None, metricas: dict,
                             cuello_estado: str | None = None, cuello_rol: str | None = None,
                             prioridad_macro: float = 0.75, runway_meses: float | None = None,
                             dilucion_overhang: bool = False, mult_ref: float = 4.0,
                             anios: int = 4, hurdle: float = 0.20) -> CandidatoOportunidad:
    """Arma un CandidatoOportunidad desde la lente de valuación (fuente_valuacion). brecha = g_entregado −
    g_exigido; momentum v1 = crecimiento YoY + señal de backlog (proxy; la aceleración real necesita 2 YoY)."""
    g_ent = metricas.get("revenue_growth_yoy")
    g_ent = (g_ent / 100.0) if g_ent is not None else None                  # viene en % → fracción
    g_exig = g_exigido(ev=metricas.get("enterprise_value"), revenue=metricas.get("revenue"),
                       mult_ref=mult_ref, anios=anios, hurdle=hurdle)
    brecha = (g_ent - g_exig) if (g_ent is not None and g_exig is not None) else None
    cov = metricas.get("backlog_coverage")
    momentum = None if g_ent is None else round(g_ent + (0.1 if (cov and cov >= 1.0) else 0.0), 4)
    return CandidatoOportunidad(
        ticker=ticker.upper(), cluster=cluster, brecha_raw=brecha, momentum_raw=momentum,
        cuello_estado=cuello_estado, cuello_rol=cuello_rol, prioridad_macro=prioridad_macro,
        runway_meses=runway_meses, dilucion_overhang=dilucion_overhang)


# --------------------------------------------------------------------------- ranking de ficha-less

@dataclass
class CandidatoOportunidad:
    ticker: str
    cluster: str | None
    brecha_raw: float | None                          # g_entregado − g_exigido (None = sin ventas)
    momentum_raw: float | None
    cuello_estado: str | None = None
    cuello_rol: str | None = None
    prioridad_macro: float = 0.75
    runway_meses: float | None = None
    going_concern: bool = False
    dilucion_overhang: bool = False
    deuda_neta_sobre_equity: float | None = None
    bonus: float = 0.0


@dataclass
class FilaScore:
    ticker: str
    cluster: str | None
    score: float | None
    v: float | None
    m: float | None
    c: float
    a: float


def rankear_oportunidades(candidatos: list[CandidatoOportunidad]) -> list[FilaScore]:
    """Computa V (brecha) y M (momentum) como PERCENTILES dentro del cluster, luego el score. Ordena desc
    (mejor primero; None al final)."""
    por_cluster: dict[str | None, list[CandidatoOportunidad]] = defaultdict(list)
    for c in candidatos:
        por_cluster[c.cluster].append(c)
    v_pct: dict[str, float | None] = {}
    m_pct: dict[str, float | None] = {}
    for grupo in por_cluster.values():
        vb = percentiles_cluster({c.ticker: c.brecha_raw for c in grupo})
        vm = percentiles_cluster({c.ticker: c.momentum_raw for c in grupo})
        v_pct.update(vb)
        m_pct.update(vm)
    filas: list[FilaScore] = []
    for c in candidatos:
        cs = cuello_score(c.cuello_estado, prioridad_macro=c.prioridad_macro, rol=c.cuello_rol)
        a = compuerta_supervivencia(runway_meses=c.runway_meses, going_concern=c.going_concern,
                                    dilucion_overhang=c.dilucion_overhang,
                                    deuda_neta_sobre_equity=c.deuda_neta_sobre_equity)
        s = score_ficha_less(v=v_pct.get(c.ticker), m=m_pct.get(c.ticker), c=cs, a=a, bonus=c.bonus)
        filas.append(FilaScore(ticker=c.ticker, cluster=c.cluster, score=s,
                               v=v_pct.get(c.ticker), m=m_pct.get(c.ticker), c=cs, a=a))
    filas.sort(key=lambda f: (f.score is None, -(f.score or 0.0)))
    return filas


# --------------------------------------------------------------------------- carriles (doc 80 §D)

@dataclass
class Seleccion:
    tenencias: list[str] = field(default_factory=list)      # obligatorio (post-earnings / ruptura)
    banca: list[str] = field(default_factory=list)          # fichas vigentes en/cerca de zona de compra
    oportunidad: list[str] = field(default_factory=list)    # top score ficha-less + fichas vencidas con gatillo
    exploracion: list[str] = field(default_factory=list)
    espera: list[tuple[str, str]] = field(default_factory=list)


def asignar_carriles(*, posiciones: set[str], fichas_zona: dict[str, str], fichas_estado: dict[str, str],
                     scores: list[FilaScore], cupo_oportunidad: int = 4,
                     blackout: set[str] | None = None) -> Seleccion:
    """Reparte el deep en carriles (doc 80 §D). `fichas_zona`: ticker→zona (COMPRA/MANTENER/RECORTE/SALIDA) de las
    fichas vigentes. `blackout`: nombres YA analizados a ≤14d de earnings (no se re-analizan). Las posiciones van
    siempre (reserva, fuera del cupo). Banca = ficha vigente en zona COMPRA. Oportunidad = top score ficha-less +
    fichas VENCIDAS con gatillo, capeado a `cupo_oportunidad`."""
    posiciones = {t.upper() for t in posiciones}
    blackout = {t.upper() for t in (blackout or set())}
    sel = Seleccion()
    sel.tenencias = sorted(posiciones)
    con_ficha = set(fichas_zona) | set(fichas_estado)

    # Banca: ficha VIGENTE (no posición) cuya zona es COMPRA → va al PM barato (distancia a zona = 0).
    for tk, zona in fichas_zona.items():
        tku = tk.upper()
        if tku in posiciones or tku in blackout:
            continue
        if zona == "COMPRA" and fichas_estado.get(tk, "VIGENTE") == "VIGENTE":
            sel.banca.append(tku)

    # Oportunidad: top score de ficha-less (sin ficha) + fichas VENCIDAS con gatillo en zona de compra.
    vencidas_en_zona = [tk.upper() for tk, z in fichas_zona.items()
                        if z == "COMPRA" and fichas_estado.get(tk) in ("VENCIDA", "EN_REVISION")
                        and tk.upper() not in posiciones and tk.upper() not in blackout]
    ranked_ficha_less = [f.ticker.upper() for f in scores
                         if f.score is not None and f.ticker.upper() not in con_ficha
                         and f.ticker.upper() not in posiciones and f.ticker.upper() not in blackout]
    cola = vencidas_en_zona + ranked_ficha_less
    sel.oportunidad = cola[:max(0, cupo_oportunidad)]
    sel.espera = [(tk, "sobre el cupo de oportunidad") for tk in cola[max(0, cupo_oportunidad):]]
    return sel
