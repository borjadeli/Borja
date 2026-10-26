"""Data pack assembler (Capa A, v2 doc 51 §3A / doc 52 Fase 3).

Ensambla el `DataPack` de una empresa desde las fuentes DETERMINISTAS de BORJA, cada número con
procedencia (fuente, known_at, kind). El data pack es INPUT de los agentes — nunca un veredicto ni
un ranking (anti-anchoring: el Analista ve cálculos, no "lo que opina el sistema").

Arquitectura de fuentes enchufables: una `Fuente` es `(ticker, as_of) -> list[DataPoint]`. Hoy está
cableada la capa de MERCADO (market_data). Las calculadoras (owner-FCF, dilución, runway, CRR, g_D,
reverse-DCF/T*, burden) se enchufan como fuentes adicionales a medida que se conectan sus insumos
(hechos extraídos) — ver `FUENTES_DEFAULT`.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date

from backend.agentes.provenance import DataKind, DataPack, DataPoint, Source

log = logging.getLogger("agentes.data_pack")

Fuente = Callable[[str, date], list[DataPoint]]


def fuente_mercado(ticker: str, as_of: date, *, snapshot_fn: Callable | None = None) -> list[DataPoint]:
    """Precio, market cap, ADV y shares del feed de mercado (ORIGINAL). Deriva market_cap = precio×shares
    si el feed no lo trae (DERIVED, con sus insumos)."""
    if snapshot_fn is None:
        from backend.services.market_data import get_price_snapshot
        snapshot_fn = get_price_snapshot
    snap = snapshot_fn(ticker)
    if snap is None:
        return []
    tk = ticker.upper()
    src = Source(name="Yahoo Finance", document_type="api")
    cur = getattr(snap, "currency", "USD")
    out: list[DataPoint] = []

    def add(metric: str, value, unit: str, kind: DataKind = DataKind.ORIGINAL, inputs=None) -> None:
        if value is None:
            return
        out.append(DataPoint(entity=tk, metric=metric, value=float(value), unit=unit, currency=cur,
                             kind=kind, source=src, known_at=as_of, inputs=inputs or []))

    add("precio", snap.precio_actual, "USD")
    add("adv_30d_usd", snap.volumen_diario_promedio_30d, "USD")
    add("shares_outstanding", snap.shares_outstanding, "shares")
    if snap.market_cap is not None:
        add("market_cap", snap.market_cap, "USD")
    elif snap.precio_actual and snap.shares_outstanding:
        # fallback DERIVED: deja rastro de que es cálculo, no dato del feed.
        add("market_cap", snap.precio_actual * snap.shares_outstanding, "USD",
            kind=DataKind.DERIVED, inputs=["precio", "shares_outstanding"])
    return out


# Fuentes que se ejecutan por default. Las calculadoras deterministas se agregan acá cuando se
# conectan sus insumos (hechos del fact store); cada una devuelve DataPoints kind=DERIVED con `inputs`.
FUENTES_DEFAULT: list[Fuente] = [fuente_mercado]


def ensamblar(ticker: str, *, as_of: date | None = None,
              fuentes: list[Fuente] | None = None) -> DataPack:
    """Corre cada fuente y junta sus DataPoints en un DataPack. Una fuente que falla NO tumba el pack
    (se loguea y se sigue) — el data pack es best-effort y declara lo que tiene."""
    as_of = as_of or date.today()
    fuentes = fuentes if fuentes is not None else FUENTES_DEFAULT
    puntos: list[DataPoint] = []
    for f in fuentes:
        try:
            puntos.extend(f(ticker, as_of))
        except Exception as e:  # noqa: BLE001 — una fuente rota no debe tumbar el pack
            log.warning("fuente %s falló para %s: %s", getattr(f, "__name__", f), ticker, e)
    return DataPack(ticker=ticker.upper(), as_of=as_of, puntos=puntos)
