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

    return TableroCuello(
        cuello=cuello, fecha=(fecha or date.today()).isoformat(), n_empresas=len(emp),
        ventas_total=ventas_total,
        margen_bruto_pond=_pond("gross_profit"),
        capex_sobre_ventas=_pond("capex"),
        inventario_sobre_ventas=_pond("inventarios"),
        rpo_total=_suma("rpo"),
        crecimiento_pond=(round(crec_pond, 2) if crec_pond is not None else None))


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
