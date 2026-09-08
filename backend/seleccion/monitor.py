"""Monitor de precio + recálculo mecánico de vía 4/5 (Bloque C §3.2, traspaso §3.2).

El precio es el SENSOR (barato); la re-derivación de tesis es la REACCIÓN (cara).

  - En CADA snapshot se recalcula MECÁNICAMENTE la vía 4 (asimetría vigente =
    (bull−precio)/(precio−bear)) y la vía 5 (peso vs HardCap×1.25). Es aritmética
    barata; NO espera el umbral del 30%. Así una posición que sube 18% y cruza
    asimetría <0,5x activa la vía 4 a tiempo.
  - El umbral de movimiento (≥30% posiciones; ~20% watchlist) dispara SOLO la
    re-derivación CARA de tesis (re-correr gate, recalcular bull/bear con LLM),
    y solo sobre la que se movió.

Preserva «sin stop de precio»: no se vende por suba/caída sola; el precio es input
de una vía YA escrita. La DECISIÓN de venta la toma salida.evaluar_salida (que
chequea elegibilidad de la vía 4); este monitor solo computa y marca.

[BLOQUEA IBKR]: la FUENTE de precio de calidad de ejecución es IBKR (no está
conectado). La LÓGICA de abajo es pura y agnóstica de la fuente: recibe el precio.
Interinamente puede alimentarse con yfinance (market_data.get_price_snapshot).
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.nucleo.constantes import BANDA_RECORTE, ROTATION_UMBRAL_SALIDA
from backend.nucleo.sizing import asimetria_vigente

# Umbrales de movimiento que disparan la re-derivación CARA (calibrables, §3.2).
UMBRAL_REDERIVACION_POSICION = 0.30
UMBRAL_REDERIVACION_WATCHLIST = 0.20


@dataclass
class PosicionMonitoreada:
    ticker: str
    precio_ref: float          # precio de la última re-derivación cara (mide el movimiento).
    bull: float
    bear: float
    hardcap_vigente: float
    peso_vivo: float
    es_watchlist: bool = False


def recalcular_mecanico(p: PosicionMonitoreada, precio_nuevo: float) -> dict:
    """Recálculo mecánico de vía 4/5 en un snapshot (barato, sin LLM). Devuelve
    señales mecánicas + si el movimiento cruza el umbral de re-derivación cara.

    NO decide la venta (eso es salida.evaluar_salida, que chequea elegibilidad de
    vía 4). Solo computa y marca.
    """
    asim = asimetria_vigente(p.bull, precio_nuevo, p.bear)
    via4_mecanica = asim is not None and asim < ROTATION_UMBRAL_SALIDA
    via5_mecanica = p.peso_vivo > p.hardcap_vigente * BANDA_RECORTE

    movimiento = abs(precio_nuevo - p.precio_ref) / p.precio_ref if p.precio_ref else 0.0
    umbral = UMBRAL_REDERIVACION_WATCHLIST if p.es_watchlist else UMBRAL_REDERIVACION_POSICION
    requiere_rederivacion_cara = movimiento >= umbral

    return {
        "ticker": p.ticker,
        "precio_nuevo": precio_nuevo,
        "asimetria_vigente": asim,
        "via4_mecanica": via4_mecanica,        # asimetría < 0.5x (salida decide si vende).
        "via5_mecanica": via5_mecanica,        # peso > HardCap × 1.25 (recorte).
        "movimiento": movimiento,
        "requiere_rederivacion_cara": requiere_rederivacion_cara,
    }


def snapshot(posiciones: list[PosicionMonitoreada], fuente_precio) -> dict:
    """Corre un snapshot sobre posiciones + watchlist topeada. `fuente_precio` es
    un callable ticker→precio (yfinance interino o IBKR en producción).

    Devuelve {recalculos, a_rederivar} — a_rederivar es la cola CARA (solo las que
    cruzaron el umbral), que entra al freno de presupuesto. Restricción dura: NUNCA
    sobre el universo (por eso MAX_WATCHLIST), solo sobre posiciones + watchlist.
    """
    recalculos = []
    a_rederivar = []
    for p in posiciones:
        precio = fuente_precio(p.ticker)
        if precio is None:
            continue
        r = recalcular_mecanico(p, precio)
        recalculos.append(r)
        if r["requiere_rederivacion_cara"]:
            a_rederivar.append(p.ticker)
    return {"recalculos": recalculos, "a_rederivar": a_rederivar}
