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

from backend.agentes.provenance import DataKind, DataPack, DataPoint, Source, Verification

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


# --------------------------------------------------------------------------- fuente XBRL (companyfacts)

# Conceptos XBRL de primera clase (P1, doc 60: companyfacts cubre el backbone financiero point-in-time).
# INSTANT = dato de balance (último instant); ANUAL = flujo del último año fiscal (~365d).
_XBRL_INSTANT = [
    ("cash", "CashAndCashEquivalentsAtCarryingValue", "USD"),
    ("stockholders_equity", "StockholdersEquity", "USD"),
    ("goodwill", "Goodwill", "USD"),
    ("intangibles_ex_goodwill", "IntangibleAssetsNetExcludingGoodwill", "USD"),
    ("shares_outstanding", "EntityCommonStockSharesOutstanding", "shares"),
]
_XBRL_ANUAL = [
    ("operating_income_loss", "OperatingIncomeLoss", "USD"),
    ("cash_used_ops", "NetCashProvidedByUsedInOperatingActivities", "USD"),
    ("gross_profit", "GrossProfit", "USD"),
    ("cost_of_revenue", "CostOfRevenue", "USD"),
]


def _d(s: str | None) -> date | None:
    try:
        return date.fromisoformat(s) if s else None
    except (TypeError, ValueError):
        return None


def _pit(entries: list[dict], as_of: date, *, anual: bool) -> dict | None:
    """Entry POINT-IN-TIME: el más reciente con `filed <= as_of` (anti look-ahead + trae lo ÚLTIMO, no lo
    viejo — doc 60). `anual`: solo duraciones ~1 año fiscal; si no, el último instant."""
    cand = []
    for e in entries:
        f = _d(e.get("filed"))
        end = _d(e.get("end"))
        if not f or not end or f > as_of:
            continue
        if anual:
            start = _d(e.get("start"))
            if not start or not (350 <= (end - start).days <= 380):
                continue
        cand.append(e)
    return max(cand, key=lambda e: (e["end"], e["filed"])) if cand else None


def fuente_xbrl(ticker: str, as_of: date, *, companyfacts_fn=None, cik_fn=None) -> list[DataPoint]:
    """XBRL de SEC companyfacts como DataPoints ORIGINAL point-in-time (P1 paso 1, doc 59/60). Cada punto
    lleva `known_at`=fecha de filing (public), período y la accession en `note` (linaje). Toma SIEMPRE lo
    último disponible al `as_of` (arregla el freshness del smoke: usaba Q4-25 teniendo Q2-26)."""
    if companyfacts_fn is None or cik_fn is None:
        from backend.services.edgar import _get_companyfacts, _revenue_concept, get_cik
        cik_fn = cik_fn or get_cik
        companyfacts_fn = companyfacts_fn or _get_companyfacts
        rev_fn = _revenue_concept
    else:
        rev_fn = None
    cik = cik_fn(ticker)
    facts = companyfacts_fn(cik) if cik else None
    if not facts:
        return []
    tk = ticker.upper()
    out: list[DataPoint] = []

    def emit(metric: str, entry: dict | None, unit: str, period_type: str) -> None:
        if entry is None or entry.get("val") is None:
            return
        out.append(DataPoint(
            entity=tk, metric=metric, value=float(entry["val"]), unit=unit, currency="USD",
            period_end=_d(entry.get("end")), period_type=period_type,
            fiscal_label=f"{entry.get('fp') or ''} {entry.get('fy') or ''}".strip() or None,
            # XBRL SÍ es un filing → CONFIRMED_FILING honesto (caso legítimo, a diferencia de Yahoo=None).
            kind=DataKind.ORIGINAL, verification=Verification.CONFIRMED_FILING,
            source=Source(name="SEC XBRL (companyfacts)", document_type=entry.get("form"),
                          published_at=_d(entry.get("end"))),
            known_at=_d(entry.get("filed")), note=f"accn={entry.get('accn')}"))

    from backend.services.edgar import _extract_concept
    for metric, tag, unit in _XBRL_INSTANT:
        emit(metric, _pit(_extract_concept(facts, tag, unit=unit), as_of, anual=False), unit, "instant")
    for metric, tag, unit in _XBRL_ANUAL:
        emit(metric, _pit(_extract_concept(facts, tag, unit=unit), as_of, anual=True), unit, "FY")
    if rev_fn is not None:                            # revenue concatena tags (ASC 606); solo en modo real
        emit("revenue", _pit(rev_fn(facts), as_of, anual=True), "USD", "FY")
    return out


# Fuentes que se ejecutan por default. Las calculadoras deterministas se agregan acá cuando se
# conectan sus insumos; cada una devuelve DataPoints kind=DERIVED con `inputs`.
FUENTES_DEFAULT: list[Fuente] = [fuente_mercado, fuente_xbrl]


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
