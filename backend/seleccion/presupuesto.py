"""Freno de presupuesto — el freno único del sistema autónomo (Bloque C §3, traspaso §3.3).

150 USD/mes ideal, 300 máximo. Mientras hay margen, corre. Al tope, se frena y
avisa («se acabó el presupuesto, hay N candidatas en cola»). La cola espera.

Decisiones cerradas que se respetan:
  - NO se mete un cupo de análisis (rechazado en triangulación de B): si el
    presupuesto revienta seguido, el diagnóstico es que el GATE está blando → se
    revisa el gate, no se capa el análisis.
  - El FLUJO DE CAPITAL (venta + opinión del PM al lado de la venta) NO está
    sujeto al freno: corre siempre, es barato, no consume el presupuesto de
    análisis (traspaso §7.3, contradicción interna de C resuelta). Es prioridad
    de seguridad, no cupo.
  - Evento de desfreno por COMPARACIÓN DE FECHAS (traspaso §7.3): el freno avisa
    al tope, pero su disparador es «cada llamada que cuesta»; si la cola está
    frenada no hay llamadas y nunca se entera de que empezó un mes nuevo. Una
    comparación de fechas barata diaria resetea el estado y despierta la cola.

Reusa el reporte de costo LLM existente (se lo convierte en contador en vivo).
Constantes calibrables.
"""
from __future__ import annotations

from dataclasses import dataclass

PRESUPUESTO_IDEAL_USD = 150.0
PRESUPUESTO_MAX_USD = 300.0

# Prioridad de cola en el thread único (traspaso §7.2). Menor índice = más
# prioritario. El flujo de capital (salida/pre-flight) gana; la exploración va al
# final pero con su presupuesto RESERVADO aparte (no compite en deep research).
PRIORIDAD_COLA = [
    "salida",            # ventas + pre-flight + eventos de posición viva.
    "pm_sidecar",        # opinión del PM al lado de la venta (flujo de capital).
    "precio_mecanico",   # recálculo barato de vía 4/5 (no LLM).
    "filings_watchlist", # filings/CRR de la watchlist topeada.
    "gate_barato",       # corte rápido de candidatas.
    "deep_research",     # investigación profunda (cara).
    "exploracion",       # Discovery exploración (presupuesto reservado aparte).
]

# Tipos de trabajo que son FLUJO DE CAPITAL (no sujetos al freno de análisis).
FLUJO_CAPITAL = {"salida", "pm_sidecar"}


@dataclass
class EstadoPresupuesto:
    periodo: str                  # 'YYYY-MM'.
    gasto_usd: float = 0.0
    frenado: bool = False
    en_cola: int = 0              # candidatas esperando al desfreno.


def prioridad(tipo: str) -> int:
    """Índice de prioridad de cola (menor = antes). Desconocido va al final."""
    return PRIORIDAD_COLA.index(tipo) if tipo in PRIORIDAD_COLA else len(PRIORIDAD_COLA)


def ordenar_cola(items: list[dict]) -> list[dict]:
    """Ordena una cola de trabajos por prioridad (traspaso §7.2). items: dicts con
    clave 'tipo'. Estable: respeta el orden de llegada dentro de la misma prioridad."""
    return sorted(items, key=lambda it: prioridad(it.get("tipo", "")))


def puede_gastar(estado: EstadoPresupuesto, tipo: str) -> bool:
    """¿Se permite una llamada que cuesta? El flujo de capital corre SIEMPRE; el
    resto, solo si no está frenado por tope."""
    if tipo in FLUJO_CAPITAL:
        return True
    return not estado.frenado


def registrar_gasto(estado: EstadoPresupuesto, usd: float, tipo: str = "deep_research") -> dict:
    """Suma el gasto y actualiza el freno. El flujo de capital suma gasto pero
    NUNCA frena el sistema (corre igual al tope). Devuelve {frenado, gasto, alerta}."""
    estado.gasto_usd += usd
    alerta = None
    if tipo not in FLUJO_CAPITAL and estado.gasto_usd >= PRESUPUESTO_MAX_USD:
        if not estado.frenado:
            alerta = (f"se acabó el presupuesto (${estado.gasto_usd:.0f} ≥ ${PRESUPUESTO_MAX_USD:.0f}); "
                      f"hay {estado.en_cola} candidatas en cola")
        estado.frenado = True
    return {"frenado": estado.frenado, "gasto": estado.gasto_usd, "alerta": alerta}


def evento_desfreno(estado: EstadoPresupuesto, periodo_hoy: str) -> dict:
    """Comparación de fechas diaria barata: si cambió el período presupuestario,
    resetea el gasto, levanta el freno y despierta la cola (traspaso §7.3).
    Devuelve {desfrenado, periodo_anterior}."""
    if periodo_hoy != estado.periodo:
        anterior = estado.periodo
        estado.periodo = periodo_hoy
        estado.gasto_usd = 0.0
        estado.frenado = False
        return {"desfrenado": True, "periodo_anterior": anterior}
    return {"desfrenado": False, "periodo_anterior": estado.periodo}
