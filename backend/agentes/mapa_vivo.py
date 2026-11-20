"""Mapa vivo — tablero de cuello + detección de DISOLUCIÓN (r9, doc 80 §B · P3).

Un cuello (bottleneck / picks-and-shovels) es TEMPORAL: se disuelve cuando la capacidad alcanza la demanda. Y
eso aparece en el TABLERO XBRL agregado del cuello —capex subiendo, inventarios acumulándose, margen cediendo—
ANTES que en la narrativa (insight de IA3). Este módulo agrega el tablero de forma determinista ($0 LLM) y, al
comparar contra el tablero del período anterior, emite una señal de estado para el Curador de cuello.

Determinista y puro (testeable). El Curador-agente (LLM) CONFIRMA el cambio de estado; el tablero lo DETECTA."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date


@dataclass
class TableroCuello:
    cuello: str
    fecha: str
    n_empresas: int
    ventas_total: float | None
    margen_bruto_pond: float | None         # gross_profit/ventas, ponderado por ventas
    capex_sobre_ventas: float | None        # señal de expansión de capacidad
    inventario_sobre_ventas: float | None   # señal de acumulación (demanda que se enfría)
    rpo_total: float | None
    crecimiento_pond: float | None          # revenue YoY, ponderado por ventas
    op_sobre_ventas: float | None = None    # margen OPERATIVO ponderado — el gate que separa real de especulación

    def to_dict(self) -> dict:
        return asdict(self)


def tablero_cuello(cuello: str, metricas_por_empresa: dict[str, dict], *, fecha: date | None = None) -> TableroCuello:
    """Agrega el tablero XBRL del cuello desde las métricas por empresa (fuente_valuacion/pack). Ponderaciones
    por ventas; None cuando no hay insumos."""
    emp = [m for m in metricas_por_empresa.values() if m]
    ventas = [m.get("revenue") for m in emp if m.get("revenue")]
    ventas_total = sum(ventas) if ventas else None

    def _pond(num_key, den_key="revenue"):
        pares = [(m.get(num_key), m.get(den_key)) for m in emp if m.get(num_key) is not None and m.get(den_key)]
        tot_den = sum(d for _n, d in pares)
        return (sum(n for n, _d in pares) / tot_den) if tot_den else None

    def _suma(key):
        vals = [m.get(key) for m in emp if m.get(key) is not None]
        return sum(vals) if vals else None

    crec = [(m.get("revenue_growth_yoy"), m.get("revenue")) for m in emp
            if m.get("revenue_growth_yoy") is not None and m.get("revenue")]
    tot_v = sum(v for _g, v in crec)
    crec_pond = (sum(g * v for g, v in crec) / tot_v) if tot_v else None

    # margen operativo ponderado — acepta `operating_income` u `operating_income_loss` (tag XBRL del pack)
    def _op(m):
        return m.get("operating_income", m.get("operating_income_loss"))
    op_pares = [(_op(m), m.get("revenue")) for m in emp if _op(m) is not None and m.get("revenue")]
    tot_op = sum(r for _o, r in op_pares)
    op_sv = (sum(o for o, _r in op_pares) / tot_op) if tot_op else None

    return TableroCuello(
        cuello=cuello, fecha=(fecha or date.today()).isoformat(), n_empresas=len(emp),
        ventas_total=ventas_total,
        margen_bruto_pond=_pond("gross_profit"),
        capex_sobre_ventas=_pond("capex"),
        inventario_sobre_ventas=_pond("inventarios"),
        rpo_total=_suma("rpo"),
        crecimiento_pond=(round(crec_pond, 2) if crec_pond is not None else None),
        op_sobre_ventas=(round(op_sv, 4) if op_sv is not None else None))


# Estados del cuello (doc 80 §B): promesa → vigilancia → confirmado → resolviéndose → resuelto.
def senal_disolucion(actual: TableroCuello, previo: TableroCuello | None = None, *,
                     umbral: float = 0.05) -> tuple[str | None, str]:
    """Señal de que el cuello se DISUELVE (capacidad alcanzando a la demanda). Compara el tablero actual vs el
    previo: capex/ventas SUBE + inventario/ventas SUBE + margen CEDE + crecimiento desacelera = 'resolviendose'.
    Devuelve (estado_sugerido|None, razón). `None` = sin señal de cambio (o sin tablero previo para comparar)."""
    if previo is None:
        return None, "sin tablero previo para comparar (primera foto)"

    def _sube(a, b):   # a (actual) materialmente mayor que b (previo)
        return a is not None and b is not None and a > b * (1 + umbral)

    def _cede(a, b):   # a materialmente menor que b
        return a is not None and b is not None and a < b * (1 - umbral)

    capex_sube = _sube(actual.capex_sobre_ventas, previo.capex_sobre_ventas)
    inv_sube = _sube(actual.inventario_sobre_ventas, previo.inventario_sobre_ventas)
    margen_cede = _cede(actual.margen_bruto_pond, previo.margen_bruto_pond)
    crec_cede = _cede(actual.crecimiento_pond, previo.crecimiento_pond)
    señales = sum([capex_sube, inv_sube, margen_cede, crec_cede])
    detalle = (f"capex/ventas{'↑' if capex_sube else '—'} · inventario/ventas{'↑' if inv_sube else '—'} · "
               f"margen{'↓' if margen_cede else '—'} · crecimiento{'↓' if crec_cede else '—'}")
    if señales >= 3:
        return "resolviendose", f"3+ señales de disolución: {detalle}"
    if señales >= 2 and (inv_sube and margen_cede):
        return "resolviendose", f"inventario↑ + margen↓ (capacidad alcanzando demanda): {detalle}"
    return None, f"sin señal de disolución ({señales}/4): {detalle}"


# --------------------------------------------------------------------------- clasificación de estado (doc 89 §3)
# "Confirmado" exige ECONOMÍA REAL (no solo revenue), medida sobre el revenue ATRIBUIBLE (no el ecosistema).
# Sin el gate de pérdida operativa, quantum pasa como confirmado (lo probamos: −506% op). Umbrales en USD crudo
# (lo que da el pack XBRL). El operador puede moverlos a config; acá viven los defaults del test de $0 (doc 89 §1).
@dataclass
class UmbralesEstado:
    min_atribuible: float = 100_000_000.0   # ventas atribuibles TTM ≥ ~$100M (materialidad)
    min_empresa: float = 25_000_000.0       # ≥2 empresas con ≥$25M atribuibles
    min_empresas: int = 2
    op_min: float = -0.50                   # pérdida operativa ≤ 50% de ventas (margen op ≥ −0.50)
    cobertura_min: float = 0.50             # bajo esto, el aviso de cobertura (no cambia el estado, lo matiza)


@dataclass
class EstadoCuello:
    cuello: str
    estado: str                 # promesa | confirmado | resolviendose | no_medible
    razon: str
    cobertura: float | None = None
    cobertura_baja: bool = False
    checks: dict = None          # auditabilidad: cada gate y su valor
    economia: dict = None        # los números usados (atribuible, margen bruto/op, crecimiento)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "EstadoCuello":
        return cls(**d)


def crecimiento_same_store(rev_actual: dict[str, float], rev_previo: dict[str, float]) -> float | None:
    """Crecimiento calculado SOLO con las empresas presentes en los DOS períodos (doc 89 §3.2). Así agregar un
    nombre nuevo al cuello NO se lee como 'crecimiento'. `None` si no hay empresas comunes o base previa 0."""
    comunes = [tk for tk in rev_actual if tk in rev_previo and rev_previo.get(tk)]
    if not comunes:
        return None
    ahora = sum(rev_actual[tk] for tk in comunes)
    previo = sum(rev_previo[tk] for tk in comunes)
    return round((ahora - previo) / previo, 4) if previo else None


def clasificar_estado(tablero: TableroCuello, atribuible, *, previo: TableroCuello | None = None,
                      crec_same_store: float | None = None, sostenido_2t: bool | None = None,
                      umbrales: UmbralesEstado | None = None) -> EstadoCuello:
    """Clasifica el cuello en promesa / confirmado / resolviendose / no_medible (doc 89 §3). `atribuible` es el
    `Atribuible` de la pieza 2 (economía MEDIDA sobre lo atribuible, no el ecosistema). `crec_same_store` tiene
    prioridad sobre el crecimiento crudo del tablero; `sostenido_2t=False` veta el gate de crecimiento."""
    u = umbrales or UmbralesEstado()
    cobertura = atribuible.cobertura
    cobertura_baja = cobertura is not None and cobertura < u.cobertura_min
    crec = crec_same_store if crec_same_store is not None else tablero.crecimiento_pond

    economia = {"revenue_atribuible": atribuible.revenue_atribuible, "revenue_total": atribuible.revenue_total,
                "margen_bruto": tablero.margen_bruto_pond, "op_sobre_ventas": tablero.op_sobre_ventas,
                "crecimiento": crec, "n_empresas": tablero.n_empresas}

    # no_medible: nadie del cuello presenta en la SEC → no se puede medir (≠ promesa, que SÍ se ve sin revenue)
    if tablero.n_empresas == 0:
        return EstadoCuello(cuello=tablero.cuello, estado="no_medible",
                            razon="ninguna empresa del cuello presenta en la SEC (A-shares / privadas)",
                            cobertura=cobertura, cobertura_baja=cobertura_baja, checks={}, economia=economia)

    # disolución: tiene prioridad (una empresa barata en un cuello que se disuelve es value-trap, doc 89 §3.4)
    if previo is not None:
        est, raz = senal_disolucion(tablero, previo)
        if est == "resolviendose":
            return EstadoCuello(cuello=tablero.cuello, estado="resolviendose", razon=raz,
                                cobertura=cobertura, cobertura_baja=cobertura_baja, checks={}, economia=economia)

    n_materiales = sum(1 for v in atribuible.atribuible_por_empresa.values() if v >= u.min_empresa)
    checks = {
        "materialidad": (atribuible.revenue_atribuible is not None
                         and atribuible.revenue_atribuible >= u.min_atribuible
                         and n_materiales >= u.min_empresas),
        "margen_bruto_positivo": tablero.margen_bruto_pond is not None and tablero.margen_bruto_pond > 0,
        "op_no_catastrofica": tablero.op_sobre_ventas is not None and tablero.op_sobre_ventas >= u.op_min,
        "crecimiento_positivo": crec is not None and crec > 0 and sostenido_2t is not False,
    }
    if all(checks.values()):
        razon = (f"economía real atribuible: ${atribuible.revenue_atribuible/1e6:,.0f}M, "
                 f"margen op {tablero.op_sobre_ventas:+.0%}, crecimiento {crec:+.0%}")
        estado = "confirmado"
    else:
        faltan = [k for k, v in checks.items() if not v]
        razon = f"promesa — falta(n): {', '.join(faltan)}"
        estado = "promesa"
    return EstadoCuello(cuello=tablero.cuello, estado=estado, razon=razon, cobertura=cobertura,
                        cobertura_baja=cobertura_baja, checks=checks, economia=economia)


# --------------------------------------------------------------------------- el cuello como FILTRO (doc 89 §3.4/§9.4)
# El cuello NUNCA suma valor (sería doble conteo con futuro.py). Entra como GUÍA que CUESTIONA/RESPALDA los
# escenarios — se le surfacea al PM, NO muta la matemática. Sin bonus, nunca cambia el tamaño.
_GUIA = {
    "confirmado": ("contexto", "economía de cuello confirmada: el PM mira el nombre por SU economía; el cuello es contexto favorable"),
    "promesa": ("watchlist", "sin tesis de cuello (economía no confirmada): el nombre queda en WATCHLIST, no se invierte POR el cuello"),
    "resolviendose": ("normalizar_margenes", "cuello en DISOLUCIÓN: normalizá los márgenes ANTES de llamar barata a la empresa (posible value-trap cíclico)"),
    "no_medible": ("manual", "cuello no medible (sus jugadores no presentan en la SEC): tratar a mano, sin inferir economía"),
}


def guia_de_cuello(estado: EstadoCuello) -> dict:
    """Traduce el estado del cuello en una GUÍA para el PM (acción + nota). No cambia size ni score — informa.
    Si la cobertura es baja, lo agrega como advertencia (separar 'promesa' de 'no medible', doc 89 §3.3)."""
    accion, nota = _GUIA.get(estado.estado, ("contexto", ""))
    if estado.cobertura_baja:
        nota += f" · ⚠ cobertura baja ({estado.cobertura:.0%} del revenue es atribuible con certeza)"
    return {"cuello": estado.cuello, "estado": estado.estado, "accion": accion, "nota": nota}


# --------------------------------------------------------------------------- el JOB (pieza 6): correr sobre los cuellos
def correr_mapa(cuellos_empresas: dict[str, list[str]], metricas_por_tk: dict[str, dict], *, store,
                atrib=None, estados_previos: dict | None = None, umbrales: "UmbralesEstado | None" = None,
                hoy: date | None = None) -> tuple[dict, list]:
    """Corre el tablero sobre cada cuello → clasifica → persiste la foto point-in-time → detecta cambios de
    estado. PURO salvo el `store` (inyectable, `StoreMapa`). `cuellos_empresas`: {cuello: [tickers]}. `metricas_
    por_tk`: {ticker: dict del pack}. `estados_previos`: {cuello: EstadoCuello|dict} de la corrida anterior (para
    los cambios). Devuelve ({cuello: EstadoCuello}, [cambios]). El `previo` para disolución/same-store = la última
    foto ESTRICTAMENTE anterior a hoy (idempotente ante re-corridas del mismo día)."""
    from backend.agentes.mapa_atribucion import MapaAtribucion, revenue_atribuible
    atrib = atrib or MapaAtribucion()
    estados_previos = estados_previos or {}
    hoy = hoy or date.today()
    estados: dict[str, EstadoCuello] = {}
    cambios: list[dict] = []
    for cuello, tickers in cuellos_empresas.items():
        sub = {tk: metricas_por_tk.get(tk) for tk in tickers if metricas_por_tk.get(tk)}
        tab = tablero_cuello(cuello, sub, fecha=hoy)
        emp_rev = {tk.upper(): m.get("revenue") for tk, m in sub.items() if m.get("revenue")}
        atribuible = revenue_atribuible(cuello, emp_rev, atrib)
        prev = store.previo(cuello, antes_de=hoy.isoformat())
        prev_tab = prev.tablero if prev else None
        crec_ss = crecimiento_same_store(emp_rev, prev.empresas_revenue) if prev else None
        est = clasificar_estado(tab, atribuible, previo=prev_tab, crec_same_store=crec_ss, umbrales=umbrales)
        store.set(tab, empresas_revenue=emp_rev)
        estados[cuello] = est
        ant = estados_previos.get(cuello)
        ant_estado = getattr(ant, "estado", None) if ant is not None else None
        if ant is not None and isinstance(ant, dict):
            ant_estado = ant.get("estado")
        if ant_estado and ant_estado != est.estado:
            cambios.append({"cuello": cuello, "de": ant_estado, "a": est.estado, "razon": est.razon})
    return estados, cambios
