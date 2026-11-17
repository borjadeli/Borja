"""Ficha viva (r9, doc 80 §F) — la PRIMITIVA CENTRAL del sistema (reemplaza al dossier como objeto principal).

DOS RELOJES:
- **Lento** (tesis, escenarios, falsadores, clase): solo lo cambia el comité citando un hecho con `known_at` nuevo.
- **Rápido** (puente de valuación + zonas/gatillos + latido): 100% determinista, recalculado a diario y en cada
  filing, a costo $0. Los gatillos se DERIVAN de los escenarios con la aritmética del doc 80 — **ningún agente
  escribe un precio** (anti price-target libre).

El dossier (pydantic, inmutable, cacheado) es la EVIDENCIA que origina la ficha; la ficha es la VISTA VIVA que lo
envuelve y lo trasciende. Este módulo es PURO y determinista (testeable sin red ni LLM).

Aritmética del puente (doc 83 — cash bridge por escenario; supera al doc 80):
    EV_i = métrica_i × múltiplo_i                                                         # enterprise value terminal
    equity_i = EV_i − deuda_neta₀ + FCF_acum_i + emisión_i − distribuciones_i + deuda_convertida_i − K_i
    V_i  = max(0, equity_i) / (acciones₀ × (1 + dilución_SBC_i) + acciones_nuevas_i + acciones_conversión_i)
    E[V] = Σ prob_i · V_i ;  r(P) = (E[V] / P)^(1/T) − 1
    COMPRA  ⇔ r(P) ≥ hurdle[clase]  Y  pérdida esperada ≤ piso[clase]
    RECORTE ⇔ r(P) < hurdle_min ;  SALIDA ⇔ P > V_bull / (1 + hurdle_min)^T

Cash bridge (doc 83 §2): la deuda ya NO está congelada. Cada escenario lleva sus propios flujos de fuentes y
usos (FCF acumulado, emisión, deuda nueva/repago, distribuciones, conversión de instrumentos). new_debt y
debt_repaid se cancelan entre caja y deuda → el equity usa deuda_neta₀ + los flujos netos. `max(0,…)`: el común
no puede valer menos que cero (responsabilidad limitada). Con todos los flujos en 0 se reduce al puente viejo.
**El LLM aporta los flujos (hipótesis); el código hace la contabilidad** (ningún agente escribe la deuda terminal).
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
    # Cash bridge por escenario (doc 83 F1) — flujos de fuentes y usos. Default 0 → se reduce al puente viejo.
    # Los emite el comité como HIPÓTESIS; el código reconcilia. NO son un modelo de capital markets.
    fcf_cumulative: float = 0.0        # FCF operativo acumulado a T (incluye CAPEX de mantenimiento)
    new_equity_proceeds: float = 0.0   # caja NETA levantada por emisión primaria
    new_equity_shares: float = 0.0     # acciones nuevas emitidas por esa emisión
    new_debt: float = 0.0              # deuda nueva tomada (solo afecta el assert de caja; se cancela en el equity)
    debt_repaid: float = 0.0           # deuda repagada (idem)
    distributions: float = 0.0         # dividendos + recompras (salida de caja)
    debt_converted: float = 0.0        # deuda que convierte a equity (F2): baja deuda → sube equity
    shares_converted: float = 0.0      # acciones emitidas por conversión de instrumentos (F2)
    senior_claims: float = 0.0         # K: claims senior al común que NO están en la deuda (preferidas, F2)
    dilucion_sbc: float | None = None  # dilución SBC específica del escenario (None → usa la de la ficha)


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
    dilucion_total: float               # SBC/baseline al terminal (fallback si el escenario no trae dilucion_sbc)
    deuda_neta: float                   # deuda − caja HOY = D₀ − C₀ (puede ser negativa = caja neta)
    acciones: float
    caja: float | None = None           # C₀ (caja+liquidez hoy) — para el assert de caja del cash bridge (doc 83 F1)
    instrumentos: list[Instrumento] = field(default_factory=list)   # inventario de capital (doc 83 F2)
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
        d["instrumentos"] = [Instrumento(**i) for i in d.get("instrumentos", [])]
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
    """Equity por acción en el escenario `e` vía CASH BRIDGE (doc 83 §2.2). `deuda_neta`/`acciones` son los de
    HOY (D₀−C₀ y acciones₀); los flujos del escenario (FCF/emisión/conversión/distribuciones/K) salen de `e`.
    V_i = max(0, EV − deuda_neta₀ + FCF + emisión − distrib + deuda_convertida − K) / (acc₀×(1+SBC) + nuevas + conv).
    (new_debt y debt_repaid NO entran al equity: se cancelan entre caja y deuda; solo cuentan en el assert de caja.)"""
    if acciones is None or acciones <= 0:
        return None
    equity_terminal, acc_T = _equity_y_acciones(e, deuda_neta=deuda_neta, acciones=acciones,
                                                dilucion_total=dilucion_total)
    if acc_T <= 0:
        return None
    return max(0.0, equity_terminal) / acc_T              # el común no vale menos que cero (responsabilidad limitada)


def _equity_y_acciones(e: EscenarioF, *, deuda_neta, acciones, dilucion_total,
                       dc: float = 0.0, sc: float = 0.0, senior: float = 0.0, wcash: float = 0.0
                       ) -> tuple[float, float]:
    """Numerador (equity terminal) y denominador (acciones terminales) del cash bridge. `dc`/`sc`/`senior`/`wcash`
    son los efectos de los INSTRUMENTOS resueltos para el escenario (F2): deuda convertida, acciones por conversión,
    claims senior no-convertidos, caja por ejercicio de warrants. En 0 = sin resolver instrumentos (solo flujos)."""
    ev = e.metrica_terminal * e.multiplo_salida
    equity = (ev - (deuda_neta or 0.0)
              + (e.fcf_cumulative or 0.0) + (e.new_equity_proceeds or 0.0) - (e.distributions or 0.0)
              + (e.debt_converted or 0.0) + dc + wcash         # deuda que convierte a equity + caja de ejercicio
              - (e.senior_claims or 0.0) - senior)             # claims senior al común (preferidas no convertidas)
    dil = e.dilucion_sbc if e.dilucion_sbc is not None else (dilucion_total or 0.0)
    acc_T = acciones * (1.0 + max(0.0, dil)) + (e.new_equity_shares or 0.0) + (e.shares_converted or 0.0) + sc
    return equity, acc_T


# --------------------------------------------------------------------------- inventario de instrumentos (doc 83 F2)

@dataclass
class Instrumento:
    """Un instrumento de capital material (doc 83 §2.1). El inventario con cita al filing es la pieza que faltaba:
    sin él, un share count 'fully diluted' sumado a mano es engañoso (caso MP). El resolver decide por TÉRMINOS."""
    id: str
    tipo: str                           # convertible | convertible_preferred | warrant | term_debt
    principal: float = 0.0              # nominal (USD)
    conversion_price: float | None = None   # convierte si V_i ≥ este precio (if-converted)
    potential_shares: float = 0.0       # acciones si convierte/ejerce
    en_deuda_xbrl: bool = False         # YA está contado en deuda_neta → al convertir se RESTA (no doble-contar)
    liq_preference: float = 0.0         # preferida: piso de liquidación (USD), senior al común si no convierte
    strike: float | None = None         # warrant: precio de ejercicio (entra caja al ejercer)
    hedge_cap: float | None = None      # capped call: hasta este precio la dilución del convertible se neutraliza
    cita: str | None = None             # accession/filing (procedencia obligatoria)

    def umbral(self) -> float | None:
        """Precio sobre el que el instrumento convierte/se ejerce."""
        return self.strike if self.tipo == "warrant" else self.conversion_price


def _shares_efectivas(j: Instrumento, v: float) -> float:
    """Acciones nuevas al convertir, netas del capped call: si hay hedge_cap y V ≤ cap, la dilución está cubierta."""
    if j.hedge_cap is not None and v <= j.hedge_cap:
        return 0.0
    return j.potential_shares


def resolver_instrumentos(e: EscenarioF, *, deuda_neta: float, acciones: float, dilucion_total: float,
                          instrumentos: list["Instrumento"], iters: int = 16) -> tuple[float | None, dict]:
    """Resuelve los instrumentos POR TÉRMINOS en el escenario `e` (doc 83 §2.4), no por etiqueta: convierte si
    V_i ≥ umbral (if-converted del EPS diluido). Itera a punto fijo (V depende de la resolución y viceversa).
    - convertible/preferida que convierte → + acciones; si en_deuda_xbrl, además −deuda (vuelve al equity).
    - convertible/preferida que NO convierte y NO está en deuda → claim SENIOR = max(principal, liq_preference).
    - warrant in-the-money → + acciones + caja de ejercicio (strike×acciones).
    - term_debt → se maneja en el cash bridge (flujos), no acá.
    Devuelve (V_i, detalle). V_i=None si faltan insumos."""
    if acciones is None or acciones <= 0:
        return None, {}
    reales = [j for j in (instrumentos or []) if j.tipo != "term_debt"]
    convertidos: set[str] = set()
    v = 0.0
    for _ in range(iters):
        dc = sc = senior = wcash = 0.0
        for j in reales:
            if j.id in convertidos:
                s = _shares_efectivas(j, v)
                sc += s
                if j.tipo == "warrant":
                    wcash += (j.strike or 0.0) * s
                elif j.en_deuda_xbrl:
                    dc += j.principal
            elif j.tipo != "warrant" and not j.en_deuda_xbrl:   # no convierte y no está en deuda → senior al común
                senior += max(j.principal, j.liq_preference)
        equity, acc_T = _equity_y_acciones(e, deuda_neta=deuda_neta, acciones=acciones,
                                           dilucion_total=dilucion_total, dc=dc, sc=sc, senior=senior, wcash=wcash)
        if acc_T <= 0:
            return None, {}
        v = max(0.0, equity) / acc_T
        nuevos = {j.id for j in reales if j.umbral() is not None and v >= j.umbral()}
        if nuevos == convertidos:
            break
        convertidos = nuevos
    return round(v, 4), {"convertidos": sorted(convertidos), "deuda_convertida": round(dc, 2),
                         "acciones_nuevas": round(sc, 2), "claims_senior": round(senior, 2)}


def cash_terminal(e: EscenarioF, *, caja_hoy: float) -> float:
    """Caja terminal del escenario C_T = C₀ + FCF_acum + emisión + deuda_nueva − repago − distribuciones (doc 83)."""
    return ((caja_hoy or 0.0) + (e.fcf_cumulative or 0.0) + (e.new_equity_proceeds or 0.0)
            + (e.new_debt or 0.0) - (e.debt_repaid or 0.0) - (e.distributions or 0.0))


def cash_bridge_ok(e: EscenarioF, *, caja_hoy: float, caja_minima: float = 0.0) -> tuple[bool, float]:
    """Assert anti-doble-conteo (doc 83): la caja terminal no puede caer bajo la mínima operativa. Si cae, el
    escenario gastó caja que no tiene (funding_unresolved: el Analista debe explicar cómo se cubre). (ok, C_T)."""
    ct = cash_terminal(e, caja_hoy=caja_hoy)
    return (ct >= (caja_minima or 0.0) - 1e-6, round(ct, 4))


def _por_nombre(escenarios: list[EscenarioF], *, deuda_neta, acciones, dilucion_total,
                instrumentos: list["Instrumento"] | None = None) -> dict[str, float]:
    """Valor por acción de cada escenario. Si hay inventario de instrumentos (F2), los RESUELVE por términos
    (if-converted, iterativo); si no, usa el cash bridge de flujos directo (F1)."""
    out: dict[str, float] = {}
    for e in escenarios:
        if instrumentos:
            v, _det = resolver_instrumentos(e, deuda_neta=deuda_neta, acciones=acciones,
                                            dilucion_total=dilucion_total, instrumentos=instrumentos)
        else:
            v = valor_accion(e, deuda_neta=deuda_neta, acciones=acciones, dilucion_total=dilucion_total)
        if v is not None:
            out[e.nombre] = round(v, 4)
    return out


def calcular_puente(escenarios: list[EscenarioF], *, precio: float, deuda_neta: float, acciones: float,
                    dilucion_total: float, clase: str,
                    hurdles=None, pisos=None, hurdle_min: float = HURDLE_MIN_DEFAULT,
                    bull_min_especulativa: float = 5.0, instrumentos: list["Instrumento"] | None = None
                    ) -> tuple[Puente, Gatillos, Latido] | None:
    """Corazón del reloj rápido: de los escenarios (reloj lento) + el precio de hoy → puente, zonas y latido.
    Puro. None si faltan insumos (precio/acciones/escenarios). `clase` elige hurdle y piso. `instrumentos` (F2):
    inventario que el resolver aplica por escenario (converts/preferidas/warrants)."""
    hurdles = hurdles or HURDLES_DEFAULT
    pisos = pisos or PISOS_DEFAULT
    vivos = [e for e in escenarios if e and e.metrica_terminal is not None and e.multiplo_salida is not None
             and e.anios and e.anios > 0 and e.prob is not None]
    if not vivos or precio is None or precio <= 0 or not acciones or acciones <= 0:
        return None
    por = _por_nombre(vivos, deuda_neta=deuda_neta, acciones=acciones, dilucion_total=dilucion_total,
                      instrumentos=instrumentos)
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
                           datos_conflicted: bool = False, caja: float | None = None,
                           dossier_id: str | None = None, hoy: date | None = None, **pol) -> Ficha:
    """Construye la ficha desde un Dossier ya cacheado ($0). Reloj lento = escenarios/clase/falsador del dossier;
    reloj rápido = calculado con el precio actual. `dossier` = schemas.Dossier (o stub con los mismos campos)."""
    hoy = hoy or date.today()
    inv = getattr(dossier, "invertibilidad", None)
    clase = (getattr(inv, "analyst_classification", None) or "especulativa")
    escen = [EscenarioF(nombre=e.nombre, metrica_terminal=e.metrica_terminal, multiplo_salida=e.multiplo_salida,
                        anios=e.anios, prob=e.prob,
                        fcf_cumulative=getattr(e, "fcf_cumulative", 0.0) or 0.0,
                        new_equity_proceeds=getattr(e, "new_equity_proceeds", 0.0) or 0.0,
                        new_equity_shares=getattr(e, "new_equity_shares", 0.0) or 0.0,
                        new_debt=getattr(e, "new_debt", 0.0) or 0.0,
                        debt_repaid=getattr(e, "debt_repaid", 0.0) or 0.0,
                        distributions=getattr(e, "distributions", 0.0) or 0.0,
                        dilucion_sbc=getattr(e, "dilucion_sbc", None))
             for e in (getattr(dossier, "escenarios", None) or [])]
    dil = getattr(dossier, "dilucion_esperada_pct", None)
    dil = (float(dil) / 100.0) if (dil is not None and dil > 1.5) else float(dil or 0.0)  # % → fracción si vino en %
    instrumentos = [Instrumento(
        id=getattr(i, "id", None) or f"inst_{n}", tipo=getattr(i, "tipo", "convertible"),
        principal=getattr(i, "principal", 0.0) or 0.0, conversion_price=getattr(i, "conversion_price", None),
        potential_shares=getattr(i, "potential_shares", 0.0) or 0.0, en_deuda_xbrl=bool(getattr(i, "en_deuda_xbrl", False)),
        liq_preference=getattr(i, "liq_preference", 0.0) or 0.0, strike=getattr(i, "strike", None),
        hedge_cap=getattr(i, "hedge_cap", None), cita=getattr(i, "cita", None))
        for n, i in enumerate(getattr(dossier, "instrumentos", None) or [])]
    # Reconciliación de deuda (doc 83): si el Analista inventarió term_debt materialmente MAYOR que la deuda del
    # pack (XBRL crudo, que pudo quedar viejo/mal — caso VST: motor $13,4B vs real $21B) → usar la verificada
    # (la mayor, conservadora) + marcar conflicted (no comprable hasta reconciliar). El pack no manda sobre el filing.
    if caja is not None:
        d_pack_gross = (deuda_neta or 0.0) + caja
        d_inv = sum(i.principal for i in instrumentos if i.tipo == "term_debt" and i.en_deuda_xbrl)
        if d_inv > 0 and d_inv > d_pack_gross * 1.20:
            deuda_neta = d_inv - caja
            datos_conflicted = True
    fals = getattr(dossier, "falsador", None)
    falsadores = [{"afirmacion": getattr(fals, "afirmacion", None),
                   "fecha_limite": getattr(fals, "fecha_limite", None), "estado": "pendiente"}] if fals else []
    ficha = Ficha(
        ticker=ticker.upper(), nivel=nivel, clase_d4=clase, cuello=cuello, cobertura_datos=cobertura,
        tesis_resumen=(getattr(dossier, "negocio_y_posicion_cuello", "") or "")[:600],
        dossier_id=dossier_id, visto_hasta=visto_hasta, estado="VIGENTE", tope_duro=None,
        escenarios=escen, dilucion_total=dil, deuda_neta=deuda_neta, acciones=acciones, caja=caja,
        instrumentos=instrumentos,
        falsadores=falsadores, conocido_hasta=conocido_hasta, datos_conflicted=datos_conflicted,
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
                          dilucion_total=ficha.dilucion_total, clase=ficha.clase_d4,
                          instrumentos=ficha.instrumentos, **pol)
    if res is not None:
        ficha.puente, ficha.gatillos, ficha.latido = res
    return ficha
