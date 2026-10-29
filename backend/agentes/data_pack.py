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


def _pit(entries: list[dict], as_of: date, *, anual: bool, dur_dias: tuple[int, int] | None = None) -> dict | None:
    """Entry POINT-IN-TIME: el más reciente con `filed <= as_of` (anti look-ahead + trae lo ÚLTIMO, no lo
    viejo — doc 60). `anual`: solo duraciones ~1 año fiscal (350-380d). `dur_dias=(lo,hi)`: filtra por
    duración (p.ej. trimestral ~80-100d). Sin ninguno: el último instant."""
    rango = (350, 380) if anual else dur_dias
    cand = []
    for e in entries:
        f = _d(e.get("filed"))
        end = _d(e.get("end"))
        if not f or not end or f > as_of:
            continue
        if rango is not None:
            start = _d(e.get("start"))
            if not start or not (rango[0] <= (end - start).days <= rango[1]):
                continue
        cand.append(e)
    return max(cand, key=lambda e: (e["end"], e["filed"])) if cand else None


def _pit_cercano(entries: list[dict], as_of: date, objetivo: date) -> dict | None:
    """Instant con `filed <= as_of` cuyo `end` esté MÁS CERCA de `objetivo` (para la foto de hace ~1 año)."""
    cand = [e for e in entries if _d(e.get("filed")) and _d(e.get("end"))
            and _d(e["filed"]) <= as_of]
    return min(cand, key=lambda e: abs((_d(e["end"]) - objetivo).days)) if cand else None


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
    _Q = (80, 100)   # duración trimestral ~90d
    for metric, tag, unit in _XBRL_INSTANT:
        emit(metric, _pit(_extract_concept(facts, tag, unit=unit), as_of, anual=False), unit, "instant")
    for metric, tag, unit in _XBRL_ANUAL:
        ents = _extract_concept(facts, tag, unit=unit)
        emit(metric, _pit(ents, as_of, anual=True), unit, "FY")
        # versión TRIMESTRAL (Q) del mismo flujo → contrasta claims de earnings (revenue/burn del trimestre),
        # que antes caían a REVIEW por "período distinto" (smoke #3). metric_q para no colisionar con el FY.
        emit(f"{metric}_q", _pit(ents, as_of, anual=False, dur_dias=_Q), unit, "Q")
    if rev_fn is not None:                            # revenue concatena tags (ASC 606); solo en modo real
        rev = rev_fn(facts)
        emit("revenue", _pit(rev, as_of, anual=True), "USD", "FY")
        emit("revenue_q", _pit(rev, as_of, anual=False, dur_dias=_Q), "USD", "Q")
    # Acciones de hace ~1 año (insumo de dilución); separado para no colisionar con el latest.
    sh = _extract_concept(facts, "EntityCommonStockSharesOutstanding", unit="shares")
    from datetime import timedelta
    emit("shares_outstanding_1y", _pit_cercano(sh, as_of, as_of - timedelta(days=365)), "shares", "instant")
    return out


# --------------------------------------------------------------------------- fuente derivada (calculadoras)

def fuente_calculadoras(ticker: str, as_of: date, puntos: list[DataPoint]) -> list[DataPoint]:
    """Calculadoras P1-A como DERIVED sobre los DataPoints del pack (NO re-pega a edgar; doc 59). Emite
    SIEMPRE un DataPoint explícito (COMPUTED / MISSING / NOT_APPLICABLE) para que el Analista no invente."""
    tk = ticker.upper()
    idx = {p.metric: p for p in puntos}
    cash, burn = idx.get("cash"), idx.get("cash_used_ops")
    sh, sh1y = idx.get("shares_outstanding"), idx.get("shares_outstanding_1y")
    out: list[DataPoint] = []

    # cash_runway_months = caja / (quema mensual). burn (cash_used_ops anual) negativo = quema.
    if not (cash and cash.value is not None) or not (burn and burn.value is not None):
        falta = "cash" if not (cash and cash.value is not None) else "cash_used_ops"
        out.append(DataPoint.derivado(tk, "cash_runway_months", None, unit="meses", formula_id="runway:v1",
                                      insumos=[p for p in (cash, burn) if p], estado="MISSING",
                                      note=f"falta insumo: {falta}"))
    elif burn.value >= 0:
        out.append(DataPoint.derivado(tk, "cash_runway_months", None, unit="meses", formula_id="runway:v1",
                                      insumos=[cash, burn], estado="NOT_APPLICABLE",
                                      note="flujo operativo no-negativo: no quema caja"))
    else:
        meses = round(cash.value / (abs(burn.value) / 12.0), 1)
        out.append(DataPoint.derivado(tk, "cash_runway_months", meses, unit="meses", formula_id="runway:v1",
                                      insumos=[cash, burn]))

    # dilucion_12m_pct = (acciones hoy / acciones -1y − 1). Requiere la serie de acciones.
    if sh and sh.value and sh1y and sh1y.value:
        dil = round((sh.value / sh1y.value - 1.0) * 100, 2)
        out.append(DataPoint.derivado(tk, "dilucion_12m_pct", dil, unit="pct", formula_id="dilucion_12m:v1",
                                      insumos=[sh, sh1y]))
    else:
        out.append(DataPoint.derivado(tk, "dilucion_12m_pct", None, unit="pct", formula_id="dilucion_12m:v1",
                                      insumos=[p for p in (sh, sh1y) if p], estado="MISSING",
                                      note="falta serie de acciones (actual o −1y)"))
    return out


FuenteDerivada = Callable[[str, date, list[DataPoint]], list[DataPoint]]

# Fuentes ORIGINAL (traen datos crudos) y DERIVADAS (calculadoras sobre esos datos). Dos fases: las
# derivadas reciben los puntos ya reunidos (consumen DataPoints del pack, no re-pegan a la fuente; doc 59).
FUENTES_DEFAULT: list[Fuente] = [fuente_mercado, fuente_xbrl]
FUENTES_DERIVADAS_DEFAULT: list[FuenteDerivada] = [fuente_calculadoras]


def ensamblar(ticker: str, *, as_of: date | None = None, fuentes: list[Fuente] | None = None,
              fuentes_derivadas: list[FuenteDerivada] | None = None) -> DataPack:
    """Reúne el DataPack en dos fases: ORIGINAL (mercado, XBRL) y luego DERIVADAS (calculadoras sobre los
    puntos ya reunidos). Una fuente que falla NO tumba el pack (se loguea) — best-effort, declara lo que tiene."""
    as_of = as_of or date.today()
    fuentes = fuentes if fuentes is not None else FUENTES_DEFAULT
    fuentes_derivadas = fuentes_derivadas if fuentes_derivadas is not None else FUENTES_DERIVADAS_DEFAULT
    puntos: list[DataPoint] = []
    for f in fuentes:
        try:
            puntos.extend(f(ticker, as_of))
        except Exception as e:  # noqa: BLE001 — una fuente rota no debe tumbar el pack
            log.warning("fuente %s falló para %s: %s", getattr(f, "__name__", f), ticker, e)
    for fd in fuentes_derivadas:
        try:
            puntos.extend(fd(ticker, as_of, puntos))
        except Exception as e:  # noqa: BLE001
            log.warning("fuente derivada %s falló para %s: %s", getattr(fd, "__name__", fd), ticker, e)
    return DataPack(ticker=ticker.upper(), as_of=as_of, puntos=puntos)
