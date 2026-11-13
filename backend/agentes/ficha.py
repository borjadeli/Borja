"""Ficha viva (r9, doc 80 §F) — la PRIMITIVA CENTRAL del sistema (reemplaza al dossier como objeto principal).

DOS RELOJES:
- **Lento** (tesis, escenarios, falsadores, clase): solo lo cambia el comité citando un hecho con `known_at` nuevo.
- **Rápido** (puente de valuación + zonas/gatillos + latido): 100% determinista, recalculado a diario y en cada
  filing, a costo $0. Los gatillos se DERIVAN de los escenarios con la aritmética del doc 80 — **ningún agente
  escribe un precio** (anti price-target libre).

El dossier (pydantic, inmutable, cacheado) es la EVIDENCIA que origina la ficha; la ficha es la VISTA VIVA que lo
envuelve y lo trasciende. Este módulo es PURO y determinista (testeable sin red ni LLM).

Aritmética del puente (doc 80 §1.F):
    V_i  = (métrica_i × múltiplo_i − deuda_neta) / (acciones × (1 + dilución_total))     # equity bridge / acción
    E[V] = Σ prob_i · V_i
    r(P) = (E[V] / P)^(1/T) − 1
    COMPRA  ⇔ r(P) ≥ hurdle[clase]  Y  V_bear/P − 1 ≥ −piso[clase]
    RECORTE ⇔ r(P) < hurdle_min
    SALIDA  ⇔ P > V_bull / (1 + hurdle_min)^T
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date

# Política por clase (hurdles/pisos), aprobada por el operador 2026-11-12 (doc 80 §3). Se puede pasar desde el
# ips.yaml; estos son los defaults. piso None = sin piso (especulativa: la limita el tamaño, no el downside).
# r9a #1 (calibración): hurdles bajados (el bear ya está en E[V] → sin doble-castigo); el piso es PÉRDIDA
# ESPERADA (prob_bear × pérdida_bear ≤ piso), no peor-caso; especulativa exige V_bull ≥ 5×P en vez de piso.
HURDLES_DEFAULT = {"core": 0.12, "satelite": 0.15, "especulativa": 0.20, "watchlist": 0.20}
PISOS_DEFAULT = {"core": 0.35, "satelite": 0.50, "especulativa": None, "watchlist": None}
HURDLE_MIN_DEFAULT = 0.08
_INF = float("inf")


@dataclass
class EscenarioF:
    nombre: str          # bull | base | bear
    metrica_terminal: float
    multiplo_salida: float
    anios: int
    prob: float


@dataclass
class Puente:
    valor_accion: dict[str, float]      # por escenario (bear/base/bull)
    e_v: float                          # E[V] = Σ prob·V_i (equity por acción esperado)
    precio: float
    retorno_esperado: float             # r(P) anualizado
    perdida_bear: float                 # V_bear/P − 1
    horizonte: int
    exige_el_precio: str                # reverse: qué métrica/retorno pide el precio de hoy


@dataclass
class Gatillos:
    compra: float | None                # precio_equiv: P ≤ esto → zona COMPRA
    recorte: float | None               # P > esto → r(P) < hurdle_min
    salida: float | None                # P > esto → ni el bull paga el mínimo


@dataclass
class Latido:
    zona: str                           # COMPRA | MANTENER | RECORTE | SALIDA
    dist_a_compra: float | None         # precio/compra − 1 (cuán arriba de la zona de compra)
    eventos_abiertos: list[str] = field(default_factory=list)
    ultima_revision_llm: str | None = None


@dataclass
class Ficha:
    ticker: str
    nivel: str                          # CARTERA | BANCA | RADAR | COLA | ARCHIVO
    clase_d4: str                       # core | satelite | especulativa | watchlist
    cuello: str | None
    cobertura_datos: str                # FULL | PARCIAL
    # reloj LENTO (del comité)
    tesis_resumen: str
    dossier_id: str | None
    visto_hasta: str | None             # p.ej. "10-Q 2026Q2"
    estado: str                         # VIGENTE | EN_REVISION | VENCIDA | ROTA
    tope_duro: str | None               # YYYY-MM-DD (re-suscripción obligatoria)
    escenarios: list[EscenarioF]
    dilucion_total: float               # acumulada al terminal (PISO de Tier A)
    deuda_neta: float                   # deuda − caja (puede ser negativa = caja neta)
    acciones: float
    falsadores: list[dict] = field(default_factory=list)
    conocido_hasta: str | None = None   # known_at del hecho más nuevo que vio la tesis (vigencia por evento)
    datos_conflicted: bool = False      # r9: banderas CONFLICTED (acciones feed≠XBRL, etc.) → NO comprable sin re-verificar
    # reloj RÁPIDO (del código) — None hasta recalcular
    puente: Puente | None = None
    gatillos: Gatillos | None = None
    latido: Latido | None = None
    historial: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Ficha":
        d = dict(d)
        d["escenarios"] = [EscenarioF(**e) for e in d.get("escenarios", [])]
        d["puente"] = Puente(**d["puente"]) if d.get("puente") else None
        d["gatillos"] = Gatillos(**d["gatillos"]) if d.get("gatillos") else None
        d["latido"] = Latido(**d["latido"]) if d.get("latido") else None
        return cls(**d)


def evaluar_vigencia(ficha: Ficha, *, ultimo_filing: str | None = None, hoy: date | None = None) -> str:
    """Vigencia por EVENTO (doc 80 §F), no TTL. Devuelve el estado nuevo (no lo fuerza): VENCIDA si pasó el tope
    duro; EN_REVISION si apareció un 10-Q/10-K POSTERIOR a lo que vio la tesis (comprar exige revisión posterior
    al último filing). Si no, conserva el estado. `ultimo_filing`/`conocido_hasta` = fechas ISO (YYYY-MM-DD)."""
    hoy = (hoy or date.today()).isoformat()
    if ficha.estado in ("ROTA",):
        return ficha.estado
    if ficha.tope_duro and hoy > ficha.tope_duro:
        return "VENCIDA"
    if ultimo_filing and ficha.conocido_hasta and ultimo_filing > ficha.conocido_hasta:
        return "EN_REVISION"
    return ficha.estado


# --------------------------------------------------------------------------- puente + zonas (puro)

def valor_accion(e: EscenarioF, *, deuda_neta: float, acciones: float, dilucion_total: float) -> float | None:
    """Equity por acción diluida en el escenario `e`: (métrica×múltiplo − deuda_neta) / (acciones×(1+dilución))."""
    if acciones is None or acciones <= 0:
        return None
    equity_terminal = e.metrica_terminal * e.multiplo_salida - (deuda_neta or 0.0)
    acc_dil = acciones * (1.0 + max(0.0, dilucion_total or 0.0))
    return equity_terminal / acc_dil if acc_dil > 0 else None


def _por_nombre(escenarios: list[EscenarioF], *, deuda_neta, acciones, dilucion_total) -> dict[str, float]:
    out: dict[str, float] = {}
    for e in escenarios:
        v = valor_accion(e, deuda_neta=deuda_neta, acciones=acciones, dilucion_total=dilucion_total)
        if v is not None:
            out[e.nombre] = round(v, 4)
    return out


def calcular_puente(escenarios: list[EscenarioF], *, precio: float, deuda_neta: float, acciones: float,
                    dilucion_total: float, clase: str,
                    hurdles=None, pisos=None, hurdle_min: float = HURDLE_MIN_DEFAULT,
                    bull_min_especulativa: float = 5.0
                    ) -> tuple[Puente, Gatillos, Latido] | None:
    """Corazón del reloj rápido: de los escenarios (reloj lento) + el precio de hoy → puente, zonas y latido.
    Puro. None si faltan insumos (precio/acciones/escenarios). `clase` elige hurdle y piso."""
    hurdles = hurdles or HURDLES_DEFAULT
    pisos = pisos or PISOS_DEFAULT
    vivos = [e for e in escenarios if e and e.metrica_terminal is not None and e.multiplo_salida is not None
             and e.anios and e.anios > 0 and e.prob is not None]
    if not vivos or precio is None or precio <= 0 or not acciones or acciones <= 0:
        return None
    por = _por_nombre(vivos, deuda_neta=deuda_neta, acciones=acciones, dilucion_total=dilucion_total)
    if not por:
        return None
    suma_prob = sum(max(0.0, e.prob) for e in vivos) or 1.0
    e_v = sum((max(0.0, e.prob) / suma_prob) * por.get(e.nombre, 0.0) for e in vivos)
    T = max(e.anios for e in vivos)                               # horizonte compartido (el mayor si difieren)
    hurdle = float(hurdles.get(clase) if hurdles.get(clase) is not None else HURDLES_DEFAULT.get(clase, 0.30))
    piso = pisos.get(clase)                                        # None = sin piso
    v_bear = por.get("bear")
    v_bull = por.get("bull")
    prob_bear = next((max(0.0, e.prob) / suma_prob for e in vivos if e.nombre == "bear"), 0.0)

    r_p = (e_v / precio) ** (1.0 / T) - 1.0 if e_v > 0 else -1.0
    perdida_bear = (v_bear / precio - 1.0) if v_bear is not None else None

    # precios equivalentes de cada gatillo (la condición es política; el precio es su equivalente de hoy):
    p_compra_ret = e_v / ((1.0 + hurdle) ** T) if e_v > 0 else None
    # piso = pérdida ESPERADA máxima (r9a #1): prob_bear × (1 − V_bear/P) ≤ piso → P ≤ V_bear/(1 − piso/prob_bear)
    if v_bear is not None and piso is not None and piso < 1 and prob_bear > 0:
        k = 1.0 - piso / prob_bear
        p_compra_piso = (v_bear / k) if k > 0 else _INF           # k≤0 → la pérdida esperada nunca excede el piso
    else:
        p_compra_piso = _INF
    # especulativa: además exige V_bull ≥ bull_min × precio → P ≤ V_bull / bull_min (doc 80 §3)
    p_compra_bull = (v_bull / bull_min_especulativa) if (clase == "especulativa" and v_bull is not None
                                                         and bull_min_especulativa) else _INF
    compra = None if p_compra_ret is None else round(min(p_compra_ret, p_compra_piso, p_compra_bull), 4)
    recorte = round(e_v / ((1.0 + hurdle_min) ** T), 4) if e_v > 0 else None
    salida = round(v_bull / ((1.0 + hurdle_min) ** T), 4) if v_bull is not None else None

    # zona (de más barato a más caro: COMPRA ≤ compra < MANTENER ≤ recorte < RECORTE ≤ salida < SALIDA)
    if compra is not None and precio <= compra:
        zona = "COMPRA"
    elif recorte is not None and precio > recorte and (salida is None or precio <= salida):
        zona = "RECORTE"
    elif salida is not None and precio > salida:
        zona = "SALIDA"
    else:
        zona = "MANTENER"
    dist = round(precio / compra - 1.0, 4) if compra and compra > 0 else None

    exige = (f"rendir {hurdle:.0%} a {T}a pide ≤ ${p_compra_ret:,.2f}; hoy ${precio:,.2f} "
             f"(retorno esperado {r_p:.0%})") if p_compra_ret else "sin insumos para el reverse"
    puente = Puente(valor_accion=por, e_v=round(e_v, 4), precio=round(precio, 4),
                    retorno_esperado=round(r_p, 4), perdida_bear=round(perdida_bear, 4) if perdida_bear is not None else None,
                    horizonte=T, exige_el_precio=exige)
    gatillos = Gatillos(compra=compra, recorte=recorte, salida=salida)
    latido = Latido(zona=zona, dist_a_compra=dist)
    return puente, gatillos, latido


# --------------------------------------------------------------------------- backfill desde el dossier

def backfill_desde_dossier(ticker: str, dossier, *, deuda_neta: float, acciones: float, precio: float | None,
                           cuello: str | None = None, nivel: str = "BANCA", cobertura: str = "FULL",
                           visto_hasta: str | None = None, conocido_hasta: str | None = None,
                           datos_conflicted: bool = False,
                           dossier_id: str | None = None, hoy: date | None = None, **pol) -> Ficha:
    """Construye la ficha desde un Dossier ya cacheado ($0). Reloj lento = escenarios/clase/falsador del dossier;
    reloj rápido = calculado con el precio actual. `dossier` = schemas.Dossier (o stub con los mismos campos)."""
    hoy = hoy or date.today()
    inv = getattr(dossier, "invertibilidad", None)
    clase = (getattr(inv, "analyst_classification", None) or "especulativa")
    escen = [EscenarioF(nombre=e.nombre, metrica_terminal=e.metrica_terminal, multiplo_salida=e.multiplo_salida,
                        anios=e.anios, prob=e.prob) for e in (getattr(dossier, "escenarios", None) or [])]
    dil = getattr(dossier, "dilucion_esperada_pct", None)
    dil = (float(dil) / 100.0) if (dil is not None and dil > 1.5) else float(dil or 0.0)  # % → fracción si vino en %
    fals = getattr(dossier, "falsador", None)
    falsadores = [{"afirmacion": getattr(fals, "afirmacion", None),
                   "fecha_limite": getattr(fals, "fecha_limite", None), "estado": "pendiente"}] if fals else []
    ficha = Ficha(
        ticker=ticker.upper(), nivel=nivel, clase_d4=clase, cuello=cuello, cobertura_datos=cobertura,
        tesis_resumen=(getattr(dossier, "negocio_y_posicion_cuello", "") or "")[:600],
        dossier_id=dossier_id, visto_hasta=visto_hasta, estado="VIGENTE", tope_duro=None,
        escenarios=escen, dilucion_total=dil, deuda_neta=deuda_neta, acciones=acciones, falsadores=falsadores,
        conocido_hasta=conocido_hasta, datos_conflicted=datos_conflicted,
        historial=[{"fecha": hoy.isoformat(), "evento": "backfill", "motivo_codigo": "DESDE_DOSSIER"}])
    if precio is not None:
        recalcular(ficha, precio=precio, deuda_neta=deuda_neta, acciones=acciones, **pol)
    return ficha


def recalcular(ficha: Ficha, *, precio: float, deuda_neta: float | None = None, acciones: float | None = None,
               **pol) -> Ficha:
    """Recalcula SOLO el reloj rápido (puente/gatillos/latido) sin tocar la tesis. Es el trabajo diario por nombre
    y lo que hace que una caída de precio actualice la zona SIN re-correr el comité (doc 80 §F, caso del operador)."""
    if deuda_neta is not None:
        ficha.deuda_neta = deuda_neta
    if acciones is not None:
        ficha.acciones = acciones
    res = calcular_puente(ficha.escenarios, precio=precio, deuda_neta=ficha.deuda_neta, acciones=ficha.acciones,
                          dilucion_total=ficha.dilucion_total, clase=ficha.clase_d4, **pol)
    if res is not None:
        ficha.puente, ficha.gatillos, ficha.latido = res
    return ficha
