"""Pre-screen determinista de candidatos a DEEP (doc 90 §8, keystone del discovery).

El deep (Opus) es el cuello de botella del presupuesto. Este filtro $0 decide QUÉ nombre merece gastarlo, SIN
correr el deep: un nombre sólo pasa si (1) su cuello está confirmado o la empresa es el "primer hecho" de un
cuello aún no confirmado, (2) tiene economía propia (ventas materiales creciendo + margen bruto positivo),
(3) pureza — el cuello es parte importante de sus ventas (no el 10%), (4) todavía está barata (EV/ventas por
DEBAJO de la mediana de su cuello = más barata que sus pares), (5) no tiene ficha reciente. Se ordenan por la
BRECHA: crecimiento propio vs lo que su múltiplo (relativo al cuello) ya exige. El deep PRUEBA la hipótesis que
los números ya sugieren; no descubre. Determinista y puro (testeable).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median


@dataclass
class UmbralesPrescreen:
    revenue_material: float = 25_000_000.0   # ventas mínimas para "economía propia" (USD)
    pureza_min: float = 0.25                 # el cuello debe pesar ≥25% de las ventas (si no, el viento no la mueve)


@dataclass
class CandidatoDeep:
    ticker: str
    cuello: str | None
    gates: dict = field(default_factory=dict)
    apto: bool = False
    brecha: float | None = None              # crecimiento propio − (EV/ventas relativo a la mediana del cuello − 1)
    motivo: str = ""


def _ev_rev_medianas(cands: list[dict]) -> dict[str, float]:
    """Mediana de EV/ventas por cuello, sobre los candidatos con dato (la 'vara' de barato dentro del cuello)."""
    por_cuello: dict[str, list[float]] = {}
    for c in cands:
        er, cuello = c.get("ev_revenue"), c.get("cuello")
        if cuello and er is not None and er > 0:
            por_cuello.setdefault(cuello, []).append(er)
    return {k: median(v) for k, v in por_cuello.items() if v}


def prescreen(cands: list[dict], *, estados_cuello: dict, atrib=None,
              umbrales: UmbralesPrescreen | None = None) -> list[CandidatoDeep]:
    """`cands`: [{ticker, cuello, revenue, revenue_growth_yoy, gross_profit, operating_income_loss, ev_revenue,
    tiene_ficha_reciente}]. `estados_cuello`: {cuello: EstadoCuello}. `atrib`: MapaAtribucion (pureza). Devuelve
    los candidatos evaluados, los APTOS primero y ordenados por brecha descendente."""
    from backend.agentes.mapa_atribucion import MapaAtribucion
    u = umbrales or UmbralesPrescreen()
    atrib = atrib or MapaAtribucion()
    medianas = _ev_rev_medianas(cands)
    out: list[CandidatoDeep] = []
    for c in cands:
        tk, cuello = c["ticker"].upper(), c.get("cuello")
        rev = c.get("revenue")
        gross = c.get("gross_profit")
        op = c.get("operating_income_loss")
        growth = c.get("revenue_growth_yoy")
        er = c.get("ev_revenue")
        est = estados_cuello.get(cuello) if cuello else None
        estado = getattr(est, "estado", None) if est is not None else None

        # (1) cuello: confirmado, o la empresa es el "primer hecho" de un cuello aún en promesa (op propio > 0 +
        # ventas materiales = la ventana antes de que el cuello se confirme, doc 90 §4)
        primer_hecho = (estado == "promesa" and op is not None and op > 0
                        and rev is not None and rev >= u.revenue_material)
        cuello_ok = estado == "confirmado" or primer_hecho
        # (2) economía propia
        economia = (rev is not None and rev >= u.revenue_material and growth is not None and growth > 0
                    and gross is not None and rev and (gross / rev) > 0)
        # (3) pureza
        peso = atrib.get(cuello, tk).peso_pureza if cuello else None
        pureza = peso is not None and peso >= u.pureza_min
        # (4) todavía barata: EV/ventas por debajo de la mediana del cuello
        med = medianas.get(cuello) if cuello else None
        barata = er is not None and er > 0 and med is not None and er < med
        # (5) sin ficha reciente
        sin_ficha = not c.get("tiene_ficha_reciente", False)

        gates = {"cuello": cuello_ok, "economia_propia": economia, "pureza": pureza,
                 "barata": barata, "sin_ficha": sin_ficha}
        apto = all(gates.values())
        # brecha: crecimiento propio MENOS lo que exige el múltiplo (relativo al cuello). Cheaper vs pares → suma.
        brecha = None
        if growth is not None and er is not None and med:
            brecha = round(growth - (er / med - 1), 4)
        motivo = ("apto para deep" if apto
                  else "falta: " + ", ".join(k for k, v in gates.items() if not v))
        out.append(CandidatoDeep(ticker=tk, cuello=cuello, gates=gates, apto=apto, brecha=brecha, motivo=motivo))

    out.sort(key=lambda x: (x.apto, x.brecha if x.brecha is not None else -1e9), reverse=True)
    return out
