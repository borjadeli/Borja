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


def fuente_mercado(ticker: str, as_of: date, *, snapshot_fn: Callable | None = None,
                   fx_fn: Callable | None = None) -> list[DataPoint]:
    """Precio, market cap, ADV y shares del feed de mercado (ORIGINAL). Deriva market_cap = precio×shares
    si el feed no lo trae (DERIVED, con sus insumos).

    Soporte extranjero (doc 76): el feed da los AGREGADOS en moneda de cotización. market_cap y ADV se
    CONVIERTEN a USD (todo el sistema razona en USD: banda del IPS, sizing). El precio por acción queda en
    moneda local con su etiqueta `currency` (es un quote nativo, no un agregado USD)."""
    if snapshot_fn is None:
        from backend.services.market_data import get_price_snapshot
        snapshot_fn = get_price_snapshot
    if fx_fn is None:
        from backend.services.market_data import fx_a_usd
        fx_fn = fx_a_usd
    snap = snapshot_fn(ticker)
    if snap is None:
        return []
    tk = ticker.upper()
    src = Source(name="Yahoo Finance", document_type="api")
    cur = getattr(snap, "currency", "USD") or "USD"
    fx = fx_fn(cur) if cur != "USD" else 1.0        # USD por 1 unidad de la moneda local
    nota_fx = None if (cur == "USD" or not fx) else f"convertido de {cur} a USD (fx={fx:.6g})"
    out: list[DataPoint] = []

    def add(metric: str, value, unit: str, *, currency: str = "USD", kind: DataKind = DataKind.ORIGINAL,
            inputs=None, note: str | None = None) -> None:
        if value is None:
            return
        out.append(DataPoint(entity=tk, metric=metric, value=float(value), unit=unit, currency=currency,
                             kind=kind, source=src, known_at=as_of, inputs=inputs or [], note=note))

    add("precio", snap.precio_actual, cur, currency=cur)        # per-share: queda en moneda nativa
    # agregados → USD (si no hay FX, se deja en moneda local CLARAMENTE etiquetada para no leerlo como USD)
    adv = snap.volumen_diario_promedio_30d
    add("adv_30d_usd", adv * fx if (adv is not None and fx) else adv, "USD",
        currency="USD" if fx else cur, note=nota_fx)
    add("shares_outstanding", snap.shares_outstanding, "shares")
    if snap.market_cap is not None:
        add("market_cap", snap.market_cap * fx if fx else snap.market_cap, "USD",
            currency="USD" if fx else cur, note=nota_fx)
    elif snap.precio_actual and snap.shares_outstanding:
        mc_local = snap.precio_actual * snap.shares_outstanding
        add("market_cap", mc_local * fx if fx else mc_local, "USD", currency="USD" if fx else cur,
            kind=DataKind.DERIVED, inputs=["precio", "shares_outstanding"], note=nota_fx)
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
    # r7 §1 (doc 78): lente de valuación por BACKLOG CONTRATADO. RPO = ingresos de performance obligations
    # pendientes (backlog contratado, ASC 606); contract_liability = anticipos cobrados de clientes. Son
    # ORIGINAL (hecho de filing, no volátil) → entran al hash. Cobertura real a medir (Gate A, doc 78).
    ("rpo", "RevenueRemainingPerformanceObligation", "USD"),
    ("contract_liability", "ContractWithCustomerLiability", "USD"),
    # r9 mapa vivo (doc 80 §B): inventarios → señal de DISOLUCIÓN del cuello (capex↑ + inventarios↑ + margen↓
    # aparece en el tablero XBRL ANTES que en la narrativa — insight de IA3).
    ("inventarios", "InventoryNet", "USD"),
]
_XBRL_ANUAL = [
    ("operating_income_loss", "OperatingIncomeLoss", "USD"),
    ("cash_used_ops", "NetCashProvidedByUsedInOperatingActivities", "USD"),
    # capex (salida de caja, valor positivo) → la quema REAL en capital-intensivas (doc 72, bug del smoke).
    ("capex", "PaymentsToAcquirePropertyPlantAndEquipment", "USD"),
    ("gross_profit", "GrossProfit", "USD"),
    ("cost_of_revenue", "CostOfRevenue", "USD"),
    # evidencia de instrumentos dilutivos (preferidas convertibles / warrants): su CONVERSIÓN a acciones NO
    # está en companyfacts (vive en las notas, Fase 2). Sirven para disparar la señal de overhang (doc 72 B1).
    ("convertible_pref_proceeds", "ProceedsFromIssuanceOfConvertiblePreferredStock", "USD"),
    ("warrant_proceeds", "ProceedsFromIssuanceOfWarrants", "USD"),
]

# Recursos líquidos: caja + valores negociables. Los emisores TAGEAN DISTINTO lo mismo (fragmentación XBRL):
# se resuelve por candidatos, primero-encontrado. El combinado ya incluye caja+ST (MP); si no, caja + ST
# current (OKLO/RGTI) + securities noncurrent (ladder de tesorería, igual de líquido para financiar la op).
# Arregla el bug del smoke: tomábamos solo CashAndCashEquivalents ($429M en MP vs $1.452,6M reales). doc 72.
_LIQ_COMBINADO = ["CashCashEquivalentsAndShortTermInvestments"]
_MKT_SEC_CURRENT = ["DebtSecuritiesAvailableForSaleExcludingAccruedInterestCurrent",
                    "AvailableForSaleSecuritiesDebtSecuritiesCurrent", "ShortTermInvestments",
                    "MarketableSecuritiesCurrent"]
_MKT_SEC_NONCURRENT = ["DebtSecuritiesAvailableForSaleExcludingAccruedInterestNoncurrent",
                       "MarketableSecuritiesNoncurrent", "LongTermInvestments"]
# deuda de largo plazo (r5 item 3: parte del set dorado; también insumo futuro del equity bridge).
_DEUDA_LP = ["LongTermDebtNoncurrent", "LongTermDebt", "LongTermDebtAndCapitalLeaseObligations"]


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
        cur_fy = _pit(rev, as_of, anual=True)
        emit("revenue", cur_fy, "USD", "FY")
        emit("revenue_q", _pit(rev, as_of, anual=False, dur_dias=_Q), "USD", "Q")
        # revenue del FY ANTERIOR → crecimiento YoY en la lente de valuación (r7 §1). Entre las anuales, la
        # que termina más cerca de (cierre actual − 1 año). Si no hay dos FY, simplemente no se emite.
        if cur_fy and _d(cur_fy.get("end")):
            from datetime import timedelta as _td
            anuales = [e for e in rev if _d(e.get("start")) and _d(e.get("end"))
                       and 350 <= (_d(e["end"]) - _d(e["start"])).days <= 380]
            emit("revenue_fy_prev", _pit_cercano(anuales, as_of, _d(cur_fy["end"]) - _td(days=365)), "USD", "FY")
    # Acciones de hace ~1 año (insumo de dilución); separado para no colisionar con el latest.
    sh = _extract_concept(facts, "EntityCommonStockSharesOutstanding", unit="shares")
    from datetime import timedelta
    emit("shares_outstanding_1y", _pit_cercano(sh, as_of, as_of - timedelta(days=365)), "shares", "instant")
    # Valores negociables (componentes crudos de liquidez) — primero-encontrado entre tags equivalentes. Se
    # emiten como ORIGINAL (un tag) para la lineage; la suma (liquidez) la deriva fuente_calculadoras. doc 72.
    def emit_primero(metric: str, tags: list[str]) -> None:
        for t in tags:
            e = _pit(_extract_concept(facts, t, unit="USD"), as_of, anual=False)
            if e and e.get("val") is not None:
                emit(metric, e, "USD", "instant")
                return
    emit_primero("cash_and_sti", _LIQ_COMBINADO)
    emit_primero("short_term_investments", _MKT_SEC_CURRENT)
    emit_primero("long_term_investments", _MKT_SEC_NONCURRENT)
    emit_primero("long_term_debt", _DEUDA_LP)
    emit("warrants_outstanding",                        # conteo de warrants vigentes (cuando está tageado)
         _pit(_extract_concept(facts, "ClassOfWarrantOrRightOutstanding", unit="shares"), as_of, anual=False),
         "shares", "instant")
    return out


# --------------------------------------------------------------------------- fuente derivada (calculadoras)

def fuente_calculadoras(ticker: str, as_of: date, puntos: list[DataPoint]) -> list[DataPoint]:
    """Calculadoras P1-A como DERIVED sobre los DataPoints del pack (NO re-pega a edgar; doc 59). Emite
    SIEMPRE un DataPoint explícito (COMPUTED / MISSING / NOT_APPLICABLE) para que el Analista no invente."""
    tk = ticker.upper()
    idx = {p.metric: p for p in puntos}
    cash, burn = idx.get("cash"), idx.get("cash_used_ops")
    combined, sti, lti = idx.get("cash_and_sti"), idx.get("short_term_investments"), idx.get("long_term_investments")
    capex = idx.get("capex")
    sh, sh1y = idx.get("shares_outstanding"), idx.get("shares_outstanding_1y")
    out: list[DataPoint] = []

    # liquidez = recursos líquidos reales = (combinado caja+ST | caja + ST) + valores negociables noncurrent
    # (ladder de tesorería). Arregla el bug del smoke: MP salía $429M (solo caja) vs $1.452,6M reales. doc 72.
    liq_comp = [combined] if (combined and combined.value is not None) else \
               [p for p in (cash, sti) if p and p.value is not None]
    if lti and lti.value is not None:
        liq_comp.append(lti)
    liq_val = sum(p.value for p in liq_comp) if liq_comp else None
    if liq_val is not None:
        out.append(DataPoint.derivado(tk, "liquidez", round(liq_val, 0), unit="USD", formula_id="liquidez:v1",
                                      insumos=liq_comp, note="caja + valores negociables (ST + ladder de tesorería)"))

    # quema REAL de caja = flujo operativo − capex (capex positivo = salida). En capital-intensivas el capex
    # DOMINA la quema; medir solo con opex sobreestima la pista (bug del smoke MP/OKLO, doc 72). El runway usa
    # la liquidez completa como numerador y la quema FCF (op−capex) como divisor; lineage = componentes crudos.
    burn_total = None
    if burn and burn.value is not None:
        burn_total = burn.value - (capex.value if (capex and capex.value is not None) else 0.0)
    run_ins = liq_comp + [p for p in (burn, capex) if p and p.value is not None]

    if liq_val is None or burn_total is None:
        falta = "liquidez" if liq_val is None else "cash_used_ops"
        out.append(DataPoint.derivado(tk, "cash_runway_months", None, unit="meses", formula_id="runway:v2",
                                      insumos=run_ins, estado="MISSING", note=f"falta insumo: {falta}"))
    elif burn_total >= 0:
        out.append(DataPoint.derivado(tk, "cash_runway_months", None, unit="meses", formula_id="runway:v2",
                                      insumos=run_ins, estado="NOT_APPLICABLE",
                                      note="flujo libre (operativo − capex) no-negativo: no quema caja"))
    else:
        meses = round(liq_val / (abs(burn_total) / 12.0), 1)
        cap = capex.value if (capex and capex.value is not None) else 0.0
        sin_capex = "" if (capex and capex.value is not None) else "  ⚠ capex no disponible: solo opex"
        out.append(DataPoint.derivado(tk, "cash_runway_months", meses, unit="meses", formula_id="runway:v2",
                                      insumos=run_ins,
                                      note=(f"liquidez {liq_val:,.0f} / quema FCF {abs(burn_total):,.0f}/año "
                                            f"(operativo {burn.value:,.0f} − capex {cap:,.0f}){sin_capex}")))

    # dilucion_12m_pct = (acciones hoy / acciones -1y − 1). Dilución REALIZADA TTM (cover-page SEC), con la
    # ventana EXPLÍCITA. NO incluye el overhang de convertibles/warrants (ver dilucion_overhang). doc 72 B1.
    if sh and sh.value and sh1y and sh1y.value:
        dil = round((sh.value / sh1y.value - 1.0) * 100, 2)
        out.append(DataPoint.derivado(tk, "dilucion_12m_pct", dil, unit="pct", formula_id="dilucion_12m:v1",
                                      insumos=[sh, sh1y],
                                      note=(f"ventana {sh1y.period_end}→{sh.period_end}; dilución REALIZADA, "
                                            f"NO incluye conversión de preferidas/warrants")))
    else:
        out.append(DataPoint.derivado(tk, "dilucion_12m_pct", None, unit="pct", formula_id="dilucion_12m:v1",
                                      insumos=[p for p in (sh, sh1y) if p], estado="MISSING",
                                      note="falta serie de acciones (actual o −1y)"))

    # overhang dilutivo que companyfacts NO cuantifica a nivel de acciones (preferidas convertibles, warrants):
    # su conversión vive en las NOTAS (Fase 2). Señal binaria para que un dilucion_12m_pct bajo NO se lea como
    # "dilución baja" — el bug del smoke: MP (DoD preferred+warrants ITM, ~9%) salía con 0,49%. doc 72 B1.
    conv, warr, warr_out = idx.get("convertible_pref_proceeds"), idx.get("warrant_proceeds"), idx.get("warrants_outstanding")
    evid = [p for p in (conv, warr, warr_out) if p and p.value]
    if evid:
        detalle = ", ".join(f"{p.metric}={p.value:,.0f}" for p in evid)
        out.append(DataPoint.derivado(tk, "dilucion_overhang", 1.0, unit="flag", formula_id="overhang:v1",
                                      insumos=evid,
                                      note=(f"instrumentos convertibles/warrants presentes ({detalle}); su "
                                            f"CONVERSIÓN a acciones NO está en XBRL → dilucion_12m_pct (realizada) "
                                            f"NO lo incluye. El Analista debe leer las notas del filing")))

    # runway bajo ESTRÉS (doc 70 D4): la quema puede ser peor que la histórica → escenario de supervivencia.
    # Sobre la liquidez completa y la quema FCF (op−capex), igual que el runway base (doc 72).
    if liq_val is not None and burn_total is not None and burn_total < 0:
        from backend.agentes.futuro import meses_runway
        r = meses_runway(liq_val, burn_total, estres=1.3)
        if r.valor is not None:
            out.append(DataPoint.derivado(tk, "cash_runway_months_stress", r.valor, unit="meses",
                                          formula_id="runway_stress:v2", insumos=run_ins,
                                          note="estrés 1.3x la quema FCF (operativo − capex)"))
    return out


def fuente_valuacion(ticker: str, as_of: date, puntos: list[DataPoint]) -> list[DataPoint]:
    """Lente de valuación (r7 §1, doc 78): la valuación PRIORIZA, no solo frena. EV + múltiplos + FCF yield +
    crecimiento + cobertura de backlog contratado, como DERIVED sobre los puntos del pack (no re-pega). TODO
    depende de precio/market_cap → DERIVED, queda FUERA del hash de reutilización (hash_pack ya lo excluye).
    Cada métrica emite COMPUTED / MISSING / NOT_APPLICABLE para que el Analista no invente. Los PERCENTILES
    por cuello NO van acá (necesitan la sección transversal del universo → embudo, r7 §3)."""
    tk = ticker.upper()
    idx = {p.metric: p for p in puntos}
    out: list[DataPoint] = []

    def val(m):
        p = idx.get(m)
        return p.value if (p and p.value is not None) else None

    def emit(metric, value, unit, fid, insumos, *, estado="COMPUTED", note=None):
        out.append(DataPoint.derivado(tk, metric, value, unit=unit, formula_id=fid,
                                      insumos=[p for p in insumos if p], estado=estado, note=note))

    mc, liq, debt = idx.get("market_cap"), idx.get("liquidez"), idx.get("long_term_debt")
    mc_v, liq_v, debt_v = val("market_cap"), val("liquidez"), (val("long_term_debt") or 0.0)

    # EV = market cap + deuda LP − liquidez (caja + valores negociables). Falta deuda CORRIENTE en el pack →
    # se nota. Si la caja supera deuda, el EV puede ser < market cap (correcto: valen la caja neta).
    ev = None
    if mc_v is not None and liq_v is not None:
        ev = mc_v + debt_v - liq_v
        nota_debt = "" if (debt and debt.value is not None) else "  ⚠ sin deuda LP en XBRL: EV usa deuda=0"
        emit("enterprise_value", round(ev, 0), "USD", "ev:v1", [mc, debt, liq],
             note=f"market_cap {mc_v:,.0f} + deuda {debt_v:,.0f} − liquidez {liq_v:,.0f}{nota_debt}")
    else:
        emit("enterprise_value", None, "USD", "ev:v1", [mc, debt, liq], estado="MISSING",
             note=f"falta insumo: {'market_cap' if mc_v is None else 'liquidez'}")

    rev, rev_v = idx.get("revenue"), val("revenue")
    gross, gross_v = idx.get("gross_profit"), val("gross_profit")

    # EV/revenue y EV/gross: NOT_APPLICABLE si no hay denominador positivo (pre-revenue → mandan backlog
    # contratado y caja, no el múltiplo de ventas). MISSING si falta el EV.
    def multiplo(metric, denom_p, denom_v, label, fid):
        if ev is None:
            emit(metric, None, "x", fid, [mc, debt, liq, denom_p], estado="MISSING", note="falta EV")
        elif denom_v is None:
            emit(metric, None, "x", fid, [denom_p], estado="MISSING", note=f"falta {label}")
        elif denom_v <= 0:
            emit(metric, None, "x", fid, [denom_p], estado="NOT_APPLICABLE",
                 note=f"{label} ≤ 0 (pre-revenue / sin margen): el múltiplo de ventas no aplica")
        else:
            emit(metric, round(ev / denom_v, 2), "x", fid, [mc, debt, liq, denom_p],
                 note=f"EV {ev:,.0f} / {label} {denom_v:,.0f}")
    multiplo("ev_revenue", rev, rev_v, "revenue FY", "ev_revenue:v1")
    multiplo("ev_gross_profit", gross, gross_v, "gross profit FY", "ev_gross:v1")

    # FCF yield = FCF / market cap, FCF = flujo operativo − capex (mismo FCF que usa el runway). NOT_APPLICABLE
    # si FCF ≤ 0 (quema): no hay yield; ahí manda el runway, no la valuación por caja.
    op, op_v = idx.get("cash_used_ops"), val("cash_used_ops")
    capex, capex_v = idx.get("capex"), (val("capex") or 0.0)
    if op_v is None or mc_v is None or mc_v <= 0:
        emit("fcf_yield", None, "pct", "fcf_yield:v1", [op, capex, mc], estado="MISSING",
             note="falta flujo operativo o market cap")
    else:
        fcf = op_v - capex_v
        if fcf <= 0:
            emit("fcf_yield", None, "pct", "fcf_yield:v1", [op, capex, mc], estado="NOT_APPLICABLE",
                 note=f"FCF {fcf:,.0f} ≤ 0 (quema caja): sin yield positivo")
        else:
            emit("fcf_yield", round(fcf / mc_v * 100, 2), "pct", "fcf_yield:v1", [op, capex, mc],
                 note=f"FCF {fcf:,.0f} (op {op_v:,.0f} − capex {capex_v:,.0f}) / market cap {mc_v:,.0f}")

    # crecimiento de revenue YoY (FY vs FY previo). Proxy determinista; el 4Q-vs-4Q necesita serie (diferido).
    rev_prev, rev_prev_v = idx.get("revenue_fy_prev"), val("revenue_fy_prev")
    if rev_v is not None and rev_prev_v and rev_prev_v > 0:
        emit("revenue_growth_yoy", round((rev_v / rev_prev_v - 1) * 100, 1), "pct", "rev_growth_yoy:v1",
             [rev, rev_prev], note=f"revenue FY {rev_v:,.0f} vs FY previo {rev_prev_v:,.0f}")
    else:
        emit("revenue_growth_yoy", None, "pct", "rev_growth_yoy:v1", [rev, rev_prev], estado="MISSING",
             note="falta revenue de dos años fiscales")

    # backlog contratado (RPO): EV/RPO, cobertura (RPO/revenue) y valor contratado ajustado por margen bruto
    # (insumo del margen de seguridad, §4). RPO ausente = MISSING explícito (el modo de falla a medir, Gate A).
    rpo, rpo_v = idx.get("rpo"), val("rpo")
    if ev is not None and rpo_v and rpo_v > 0:
        emit("ev_rpo", round(ev / rpo_v, 2), "x", "ev_rpo:v1", [mc, debt, liq, rpo],
             note=f"EV {ev:,.0f} / RPO {rpo_v:,.0f}")
    elif rpo_v is None:
        emit("ev_rpo", None, "x", "ev_rpo:v1", [rpo], estado="MISSING", note="sin RPO en XBRL (backlog no tageado)")
    if rpo_v and rev_v and rev_v > 0:
        emit("backlog_coverage", round(rpo_v / rev_v, 2), "x", "backlog_cov:v1", [rpo, rev],
             note=f"RPO {rpo_v:,.0f} / revenue FY {rev_v:,.0f} = años de revenue contratados")
    if rpo_v and rev_v and rev_v > 0 and gross_v is not None:
        margen = gross_v / rev_v
        emit("valor_contratado_ajustado", round(rpo_v * margen, 0), "USD", "valor_contratado:v1",
             [rpo, gross, rev], note=f"RPO {rpo_v:,.0f} × margen bruto {margen:.0%}")
    elif rpo_v:
        emit("valor_contratado_ajustado", None, "USD", "valor_contratado:v1", [rpo, gross, rev],
             estado="MISSING", note="RPO presente pero sin margen bruto (gross/revenue) para ajustar")

    return out


# 8-K que CAMBIAN el balance (deuda/acciones) y NO están en companyfacts hasta el próximo 10-Q:
# 2.01 = adquisición/disposición completada · 2.03 = obligación financiera directa (deuda nueva) ·
# 1.01 = acuerdo material (suele ser el acuerdo de compra/financiamiento). Si hay uno POSTERIOR al último
# XBRL, el balance del pack puede estar desactualizado (el agujero que mordió en IESC/DBM, 2026-11).
_ITEMS_8K_BALANCE = {"2.01", "2.03", "1.01"}


def fuente_consistencia(ticker: str, as_of: date, puntos: list[DataPoint],
                        filings_fn=None) -> list[DataPoint]:
    """Chequeos de consistencia AUTOMÁTICOS sobre cada pack (r6 #4 'verificar siempre'): sin leer el filing,
    cruza las fuentes que tenemos y marca banderas CONFLICTED que el Analista/Verificador ven. Barato,
    determinista, para TODOS los nombres. NO reemplaza al set dorado (métricas solo-XBRL sin contraparte).
    `filings_fn` (inyectable para test) lista filings recientes para el check de frescura del balance (#5)."""
    tk = ticker.upper()
    src = Source(name="consistencia:v1", document_type="calculadora")
    out: list[DataPoint] = []

    def flag(nombre: str, nota: str) -> None:
        out.append(DataPoint(entity=tk, metric=f"flag_{nombre}", value=1.0, unit="flag",
                             kind=DataKind.DERIVED, estado="CONFLICTED", source=src, known_at=as_of, note=nota))

    def _es_xbrl(p):
        return "xbrl" in (p.source.name or "").lower()

    # 1) ACCIONES: feed (Yahoo) vs XBRL. Divergencia alta → dilución no capturada o error de extracción.
    shares = [p for p in puntos if p.metric == "shares_outstanding" and p.value]
    feed_sh = next((p.value for p in shares if not _es_xbrl(p)), None)
    xbrl_sh = next((p.value for p in shares if _es_xbrl(p)), None)
    if feed_sh and xbrl_sh:
        div = abs(feed_sh - xbrl_sh) / max(feed_sh, xbrl_sh)
        if div > 0.25:
            flag("shares_divergentes", f"acciones feed={feed_sh:,.0f} vs XBRL={xbrl_sh:,.0f} "
                 f"(dif {div:.0%}) → posible dilución no capturada o error de extracción")

    # 2) ESCALA: un market cap sospechosamente chico ⇒ error de escala (el mismo que mordió en el puente).
    mc = next((p.value for p in puntos if p.metric == "market_cap" and p.value is not None), None)
    if mc is not None and 0 < mc < 1e6:
        flag("market_cap_escala", f"market cap ${mc:,.0f} sospechosamente chico → ¿error de escala/moneda?")

    # 3) FRESCURA: el último filing XBRL es viejo → los fundamentales pueden estar vencidos.
    knowns = [p.known_at for p in puntos if p.known_at and _es_xbrl(p)]
    if knowns and (as_of - max(knowns)).days > 400:
        flag("datos_viejos", f"último filing XBRL {max(knowns)} (> 400 días) → fundamentales posiblemente vencidos")

    # 4) REVENUE SOSPECHOSO (r7a, hallazgo del dry-run con GLXY): revenue FY desproporcionado vs market cap.
    # GLXY mostraba $60B de "revenue" (ventas crypto grossed-up / notional, no ventas económicas) con market
    # cap $9B → EV/revenue de ganga falsa que el PM podría leer mal. Umbral 5×: un revenue > 5 veces el market
    # cap es muy raro legítimamente (un distribuidor de bajo margen llega a ~3-4×). NO gatea; bandera CONFLICTED
    # advisory para que el Analista/Verificador lo miren (un falso positivo cuesta 2 segundos de revisión).
    rev = next((p.value for p in puntos if p.metric == "revenue" and p.value is not None), None)
    if rev is not None and mc is not None and mc > 0 and rev > 5 * mc:
        flag("revenue_sospechoso", f"revenue FY ${rev:,.0f} > 5× market cap ${mc:,.0f} ({rev/mc:.0f}×) → "
             f"¿revenue grossed-up/notional, no ventas económicas? (EV/revenue sería una ganga falsa)")

    # 5) BALANCE DESACTUALIZADO (2026-11, hallazgo IESC/DBM): el balance (deuda/acciones) sale de XBRL
    # periódico, cuyo último punto es el 10-Q/K. Un 8-K con ítem 2.01/2.03/1.01 POSTERIOR a ese XBRL cambia el
    # balance y NO aparece en companyfacts hasta el próximo 10-Q → la deuda/acciones del pack están vencidas.
    # Caza el agujero que un LLM+web externo vio y nuestro comité no (ningún agente re-mira EDGAR por el balance).
    if knowns:
        ref = max(knowns)                                    # fecha del último XBRL (el balance del pack)
        try:
            if filings_fn is None:
                from backend.services.edgar import get_recent_filings
                filings_fn = lambda t: get_recent_filings(t, tipos=("8-K",), dias=300)  # noqa: E731
            posteriores = []
            for f in filings_fn(tk):
                its = set((getattr(f, "items", "") or "").replace(" ", "").split(","))
                fdt = getattr(f, "fecha", None)
                fd = fdt.date() if hasattr(fdt, "date") else fdt
                if (its & _ITEMS_8K_BALANCE) and fd and fd > ref:
                    posteriores.append((fd, its & _ITEMS_8K_BALANCE, getattr(f, "accession_number", "")))
            if posteriores:
                posteriores.sort(reverse=True)
                det = "; ".join(f"{d} ítems {sorted(i)} ({a})" for d, i, a in posteriores[:3])
                flag("balance_desactualizado",
                     f"hay 8-K material POSTERIOR al último XBRL ({ref}): {det} → la deuda/acciones del pack "
                     f"pueden estar vencidas (adquisición/deuda nueva fuera de companyfacts); RECONCILIAR antes de comprar")
        except Exception as e:  # noqa: BLE001 — sin red igual devuelve el resto de los checks
            log.warning("check de frescura del balance falló para %s: %s", tk, e)

    return out


FuenteDerivada = Callable[[str, date, list[DataPoint]], list[DataPoint]]

# Fuentes ORIGINAL (traen datos crudos) y DERIVADAS (calculadoras sobre esos datos). Dos fases: las
# derivadas reciben los puntos ya reunidos (consumen DataPoints del pack, no re-pegan a la fuente; doc 59).
FUENTES_DEFAULT: list[Fuente] = [fuente_mercado, fuente_xbrl]
# Orden: calculadoras (liquidez/runway) → valuación (usa liquidez para el EV) → consistencia AL FINAL
# (consume los puntos de todas las demás).
FUENTES_DERIVADAS_DEFAULT: list[FuenteDerivada] = [fuente_calculadoras, fuente_valuacion, fuente_consistencia]


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
