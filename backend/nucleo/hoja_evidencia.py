"""Hoja de evidencia por empresa + ranking del universo (doc 31 §7, v2 tras review del build).

Ensambla por nombre: stage (R0-R5) + route + operable (owner-FCF) + option premium + burden_GP (v1) +
burn_yield (dilución forward) + flags. Correcciones del review (2 IAs convergieron, 2026-08-05):
  - SOLO el bucket FCFE_OPERABLE recibe ranking ORDINAL (por menor múltiplo-sobre-operable = menos
    apuesta). El resto (CASH_POSITIVE, NON_FCFE) es "unanchored": se muestra ordenado por el proxy
    PERO sin puestos 1,2,3 (una lista con ordinales se lee como recomendación — doc 31 §6).
  - Separar DATA de ECONOMÍA: `múltiplo>200×` NO es dato malo → `OPERABLE_IMMATERIAL` (precio ≈ todo
    opción), no se excluye como sospechoso. `shares<1M` → `MANUAL_DATA_CHECK` (reverse-splits reales
    existen), no exclusión automática.
  - múltiplo y opción% son la MISMA señal (opción% = 1 − 1/múltiplo) — display, no dos factores.
  - burden_GP correlaciona ~1:1 con el múltiplo dentro del bucket → display con disclaimer t=0/ρ=1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from backend.nucleo import bridge, compilador, fact_store as FS
from backend.nucleo import politica, pre_revenue, ranking, ruteo, sizing_burden, templates, valuacion_reverse
from backend.nucleo.crecimiento import crecimiento_demostrado
from backend.nucleo.dilucion import dilucion_forward
from backend.nucleo.extractor import extraer_deterministas
from backend.nucleo.ranking import _clasificar_arquetipo
from backend.nucleo.realizacion import etapa_realizacion
from backend.nucleo.validacion_datos import flags_plausibilidad
from backend.services import edgar, market_data


@dataclass
class HojaEvidencia:
    ticker: str
    arquetipo: str
    stage: str | None
    route: str
    estado: str                                 # RANKEABLE | OPERABLE_IMMATERIAL | MANUAL_DATA_CHECK | UNANCHORED
    precio: float | None
    operable: float | None
    multiplo_sobre_operable: float | None
    option_premium_pct: float | None            # = 1 − 1/múltiplo (misma señal, para lectura)
    burden_gp: float | None                     # reverse burden (opex_cash+FCFE_req)/GP a t, ρ=1 (doc 31 §2)
    burn_yield: float | None                    # dilución forward: −FCF/mcap
    banda_dilucion: str
    runway_anos: float | None                   # caja / quema anual (financiación, doc 31 §4)
    shares_growth_12m: float | None = None      # dilución REALIZADA 12m (fracción, total clases) (doc 31 §5)
    shares_growth_24m: float | None = None      # dilución REALIZADA 24m
    sbc_over_revenue: float | None = None       # SBC/revenue TTM; None si pre-revenue
    up_c_suspect: bool = False                  # crecimiento de acciones puede ser B→A (no dilución económica)
    demanda_tier: int | None = None             # DEMANDA citada 1-3 (VALIDATED/COMMITTED/REALIZED) — DISPLAY, no rankea
    demanda_quote: str | None = None            # cita verbatim del filing que sostiene el tier gobernante
    price_anchor_status: str = "NA"             # ANCHORED | PURE_OPTION | NA (doc 31 §2)
    reverse_burden_type: str = "NA"             # GP_MULTIPLE | NA
    capital_risk_tier: str = "NA"               # A | B | C (riesgo de capital, doc 31 §6)
    peer_rank: int | None = None                # puesto DENTRO de arquetipo por menor burden (solo ANCHORED)
    # --- Escenario operable + falsador (doc 28, vertical RPO→compiler) ---
    revenue_contratado: float = 0.0             # backlog contratado CON haircut (prende el spread bull real)
    bull_operable: float | None = None          # precio bull (run-rate + contratado)
    bear_operable: float | None = None          # precio bear (piso/run-rate despojado) — para la asimetría
    asimetria_operable: float | None = None     # (bull−precio)/(precio−bear); None si precio≤bear (doc 27 §10)
    haircut_source: str = ""                    # de dónde salió el haircut del contratado (traza; ej. cancelable_backlog(asumido))
    evidencia_insuficiente: bool = False        # bull dominado por piso/tipo-asumido → NO sleeve completo (doc 28 §1)
    falsador_ya_priceado: bool = False          # precio ya paga el bull operable → pura opcionalidad / carril (doc 29)
    falsador_veredicto: str = ""
    # --- Reverse-DCF unificado (doc 36/37, Bloque 1.2/1.3) — estado de valuación growth-aware ---
    estado_reverse: str | None = None           # COVERED|STRETCH|OPTION_PRICED|NON_UNDERWRITABLE (comercial); None=no comercial
    estado_ruteo: str | None = None             # COMERCIAL_MADURO|ESCALANDO|PRE_REVENUE_BINARIO|BURDEN (doc 42 §2)
    revenue_ttm: float | None = None            # revenue TTM (para detectar pre-revenue con ancla inmaterial, #26)
    g_D_reverse: float | None = None            # crecimiento demostrado usado en el reverse-DCF (doc 36 §3)
    t_star_reverse: dict = field(default_factory=dict)  # {P25,P50,P75} años que el precio exige (falsable)
    # --- Sizing continuo del bucket growth/BURDEN (doc 47, Fase 1) — techo con distribución, no masa puntual ---
    size_burden: float | None = None            # fracción de cartera del sizing continuo (None = no aplica: MADURO/pre-rev)
    a_carril_burden: bool = False               # quema caja pre-SBC → pura opción → carril (doc 29), no libro duro
    flags: list[str] = field(default_factory=list)


def _demanda_display(session, ticker: str) -> tuple[int | None, str | None, str | None]:
    """(tier 1-3 | None, quote, nota) de la DEMANDA citada, leído del fact store. DISPLAY-ONLY: NO entra
    al ranking ni al número duro (regla de aislamiento). Reusa la derivación de tier canónica con gates
    (ranking._demanda_de_snapshot); la quote es la del hecho gobernante. `nota` = por qué se excluyó
    evidencia (ej. parte relacionada), para que un 's/d' tenga razón visible. Sin evidencia → (None,None,None)."""
    snap = FS.snapshot_vigente(session, ticker)
    if not snap:
        return None, None, None
    rp_pct = edgar.get_related_party_pct(ticker).get("pct")     # G2 determinista (XBRL, sin LLM)
    tier, _, _ = ranking._demanda_de_snapshot(snap, rp_pct=rp_pct)
    fk = {3: "demanda_realizada", 2: "demanda_minimo", 1: "cliente_nombrado"}.get(tier)
    quote = f.quote if (fk and (f := snap.get(fk)) is not None) else None
    nota = None
    if rp_pct is not None and rp_pct >= ranking.UMBRAL_PARTE_REL_FLAG:
        nota = f"parte_relacionada={rp_pct:.0%}:revisar"     # flag informativo, no auto-excluye
    return (tier or None), quote, nota


def _bull_contratado(ticker: str, det: dict, arq: str,
                     no_cancelable: bool | None = None) -> tuple[float, bool, str]:
    """Backlog contratado (RPO de XBRL) → compiler → retención por tipo (doc 28 §1). Devuelve
    (revenue_contratado_con_haircut, evidencia_insuficiente, haircut_source).

    `no_cancelable` (hecho citado `backlog_no_cancelable`, E1): True firme → firm_po 0.85 · False
    cancelable → cancelable_backlog 0.60 · None (sin extraer) → cancelable_backlog ASUMIDO (penaliza
    sleeve vía evidencia_insuficiente hasta que se extraiga)."""
    rpo = det.get("rpo")
    if not rpo or not det.get("revenue_ttm"):
        return 0.0, False, ""
    try:
        fc = date.fromisoformat(str(det.get("rpo_as_of"))[:10]) if det.get("rpo_as_of") else None
    except ValueError:
        fc = None
    ctype, asumido = compilador.tipo_contrato_rpo(no_cancelable)
    mags = {"backlog_rpo": {"monto": float(rpo), "contract_type": ctype, "tipo_asumido": asumido,
                            "fact_key": "respaldo_backlog",
                            "cita": f"XBRL RemainingPerformanceObligation as of {det.get('rpo_as_of')}"}}
    esc = compilador.compilar_escenario(ticker, {}, det, arq, magnitudes=mags, fecha_corte=fc)
    rev = esc.revenue_por_escenario()
    src = next((t.haircut_source for t in esc.terminos if t.concepto == "backlog_rpo"), "")
    return rev["bull"] - rev["bear"], esc.evidencia_insuficiente, src


def hoja(ticker: str, session=None) -> HojaEvidencia:
    fin = edgar.get_financials_quarterly(ticker, periodos=8)
    snap = market_data.get_price_snapshot(ticker)
    precio = snap.precio_actual if snap else None
    det = extraer_deterministas(ticker)
    arq = _clasificar_arquetipo(det)
    rz = etapa_realizacion(fin)
    # Shares/market cap del FEED de mercado (no de XBRL) — market cap es cantidad de mercado; evita el
    # bug de weighted-avg Class A / stale de XBRL en de-SPAC/Up-C (review 2026-08). Fallback a XBRL con flag.
    shares = (snap.shares_outstanding if (snap and snap.shares_outstanding) else fin.shares_outstanding)
    mcap = (snap.market_cap if (snap and snap.market_cap)
            else (precio * shares if (precio and shares) else None))
    shares_del_feed = bool(snap and snap.shares_outstanding)

    # Escenario operable: el backlog contratado (RPO de XBRL) → compiler → retención por tipo (doc 28 §1).
    # Prende el spread bull real (antes revenue_contratado=0 → bull=base=bear). Todo trazable + versionado.
    # E1: si el hecho citado backlog_no_cancelable está en el fact store → tipo REAL (apaga el asumido).
    nc = None
    if session is not None:
        snap_fs = FS.snapshot_vigente(session, ticker)
        f = snap_fs.get("backlog_no_cancelable") if snap_fs else None
        nc = FS._dec(f.value) if (f is not None and getattr(f, "value", None) is not None) else None
    revenue_contratado, evidencia_insuf, haircut_src = _bull_contratado(ticker, det, arq, no_cancelable=nc)

    esc = templates.escenario_operable(fin.revenue_ttm, fin.fcf_ttm, arq, shares=shares,
                                       caja=fin.cash, deuda=fin.total_debt, precio=precio,
                                       sbc_ttm=fin.sbc_ttm, revenue_contratado=revenue_contratado)
    op = esc.base_price
    mult = esc.multiplo_sobre_operable
    prem = None if mult in (None, 0) else 1.0 - 1.0 / mult          # = (precio−operable)/precio
    # Asimetría solo cuando HAY ancla operable (terminal). Sin terminal (owner-FCF<0 → bull=bear=piso) la
    # asimetría es N/A, NO −1.00: colapsar "no aplica" a un valor bajo es el bug que la triangulación marcó
    # (doc 34 §3bis). En pre-revenue la métrica correcta es el burden, no la asimetría.
    asim_op = templates.asimetria_operable(esc.bull_price, precio, esc.bear_price) if esc.con_terminal else None

    # Falsador CAGR (doc 28 §4): ¿el precio ya paga el bull operable entero? → tesis solo en option ledger.
    caja_neta = (fin.cash or 0.0) - (fin.total_debt or 0.0)
    margen_ufcf = (fin.fcf_ttm / fin.revenue_ttm) if (fin.fcf_ttm is not None and fin.revenue_ttm) else None
    rev_bull_op = (fin.revenue_ttm or 0.0) + revenue_contratado
    fals = bridge.falsador_cagr(precio, rev_bull_op if rev_bull_op > 0 else None,
                                margen_ufcf, arq, shares, caja_neta)

    sg = edgar.get_shares_growth(ticker)                            # dilución REALIZADA + up_c flag (doc 31 §5)
    dil = dilucion_forward(fin, mcap, shares_growth=sg)
    ru = pre_revenue.evaluar(
        stage=rz.stage, route=rz.route, gross_profit_ttm=rz.gross_profit_ttm,
        operating_income_ttm=rz.operating_income_ttm, sbc_ttm=fin.sbc_ttm,
        operable_por_accion=op, precio=precio, shares=shares, mcap=mcap,
        arquetipo=arq, dilucion=dil)
    burden = ru.reverse_burden                                      # (opex_cash+FCFE_req)/GP a t, ρ=1
    dq = flags_plausibilidad(fin, precio)
    flags = list(rz.flags) + [f"{f.campo}:{f.severidad}" for f in dq] + list(ru.flags)
    if dil.runway_critico:
        flags.append(f"runway_critico={dil.runway_anos}a")
    if not shares_del_feed:
        flags.append("shares_de_xbrl (feed no disponible) → verificar mcap")
    if dil.up_c_suspect:
        flags.append("up_c_suspect (multi-clase) → crecimiento de acciones puede ser B→A; anclar en burn_yield")
    if evidencia_insuf:
        flags.append("evidencia_insuficiente: bull sobre backlog de tipo ASUMIDO (RPO) → no sleeve completo "
                     "hasta extraer el tipo de contrato (doc 14 §E1)")
    if fals.ya_priceado:
        flags.append("falsador: el precio YA paga el bull operable → pura opcionalidad, fuera del libro duro "
                     "(option ledger / carril especulativo, doc 29)")

    # Estado: separa problemas de DATO de "el modelo no ancla el precio" (economía, no ruido).
    if not shares or shares < 1e6:
        estado = "MANUAL_DATA_CHECK"
        flags.append(f"shares={shares} → chequeo manual (escala/reverse-split)")
    elif any(f.severidad == "alta" for f in dq):
        estado = "MANUAL_DATA_CHECK"
    elif mult is not None and abs(mult) > 200:
        estado = "OPERABLE_IMMATERIAL"          # operable ≈ 0 → precio es todo opción (info, no ruido)
    elif rz.route == "FCFE_OPERABLE":
        estado = "RANKEABLE"
    else:
        estado = "UNANCHORED"                    # CASH_POSITIVE / NON_FCFE: sin ranking ordinal

    demanda_tier, demanda_quote, demanda_nota = (
        _demanda_display(session, ticker) if session is not None else (None, None, None))
    if demanda_nota:
        flags.append(demanda_nota)

    # --- Ruteo de 2 ejes (doc 42 §2) → gramática de valuación (Bloque 2 D2). El ruteo por DERIVADA
    # (Δ8Q(GP)/Δ8Q(OpEx)) decide: MADURO/ESCALANDO → reverse-DCF (ESCALANDO capado a probe, doc 42 §3);
    # PRE_REVENUE_BINARIO/BURDEN → estado_reverse=None (path binario/burden). Arregla el good-loser (owner-FCF<0
    # que escala ya NO cae a burden). modelo="default" (sector→modelo diferido). g_D del crecimiento demostrado.
    estado_rev, g_D_rev, t_star_rev, estado_ruteo = None, None, {}, None
    size_burden_frac, a_carril_burden = None, False
    try:
        serie = edgar.serie_crecimiento(ticker, n_q=16)
        snap_fs = FS.snapshot_vigente(session, ticker) if session is not None else {}
        conc_f = snap_fs.get("customer_concentration_pct")
        conc = FS._dec(conc_f.value) if (conc_f is not None and getattr(conc_f, "support_type", None) in ("DIRECT", "DERIVED")) else None
        g_D_rev = crecimiento_demostrado(serie, arq, concentracion=conc if isinstance(conc, (int, float)) else None).get("g_D")
        gp_q = [q.get("gross_profit") for q in fin.quarters]
        opex_q = [(q["gross_profit"] - q["operating_income"])
                  if (q.get("gross_profit") is not None and q.get("operating_income") is not None) else None
                  for q in fin.quarters]
        owner_fcf = (fin.fcf_ttm or 0.0) - (fin.sbc_ttm or 0.0)
        rt = ruteo.rutear(ticker, revenue_ttm=fin.revenue_ttm, gp_qtrs=gp_q, opex_qtrs=opex_q,
                          owner_fcf=owner_fcf, sbc_ttm=fin.sbc_ttm, cfo_ttm=None, capex_ttm=fin.capex_ttm,
                          runway_meses=(dil.runway_anos * 12 if dil.runway_anos else None))
        estado_ruteo = rt.estado
        flags.append(f"ruteo: {rt.estado} ({rt.motivo[:44]})")
        rr = valuacion_reverse.estado_por_ruteo(
            ticker, rt.estado, revenue_ttm=fin.revenue_ttm, owner_fcf=owner_fcf, shares=shares,
            precio=precio, cash=fin.cash, g_D=g_D_rev, modelo="default")
        if rr is not None:
            estado_rev, t_star_rev = rr.estado, rr.t_star
            flags.append(f"reverse-DCF: {rr.estado} (g_D={(g_D_rev or 0):.0%}, T*P50={rr.t_star.get('P50')}, r_mkt)")
        # --- Sizing CONTINUO del bucket growth/BURDEN (doc 47, Fase 1): comerciales owner-FCF<0 (BURDEN/ESCALANDO)
        # dejan de aplastarse a OPTION_PRICED. Size = CAP × f_val(T_fade) × q_GM × q_apal × q_ps(acretividad) × d_SBC.
        # MADURO (owner-FCF>0) mantiene su reverse-DCF; pre-revenue (< base-chica) sigue por #26 (carril/NON_UW).
        es_comercial = fin.revenue_ttm and fin.revenue_ttm >= politica.UMBRAL_BASE_CHICA
        if es_comercial and rt.estado in (ruteo.BURDEN, ruteo.COMERCIAL_ESCALANDO):
            gpv = [x for x in gp_q if x is not None]
            dsh = [x for x in (fin.diluted_shares_qtrs or []) if x]
            ggps = None                                    # ΔGP/acción(8Q anual) — el gate de acretividad
            if len(gpv) >= 12 and len(dsh) >= 8 and dsh[-8] and dsh[-1] and sum(gpv[-12:-8]) > 0:
                ggps = ((sum(gpv[-4:]) / dsh[-1]) / (sum(gpv[-12:-8]) / dsh[-8])) ** 0.5 - 1
            t_fade_val = sizing_burden.t_fade(burden, g_D_rev)
            sb = sizing_burden.size_burden(
                ticker, t_star=t_fade_val, gross_margin=rt.gross_margin, apal_lag=rt.apalancamiento,
                g_gp_por_accion=ggps, fcf_pre_sbc=fin.fcf_ttm, burden=burden,
                runway_meses=(dil.runway_anos * 12 if dil.runway_anos else None))
            size_burden_frac, a_carril_burden = sb.size, sb.a_carril
            flags.append(f"sizing_burden: {sb.size:.1%}{' →carril' if sb.a_carril else ''} (T_fade={t_fade_val}, {sb.motivo[:34]})")
    except Exception as e:  # noqa: BLE001 — el reverse-DCF no debe tumbar la hoja
        flags.append(f"reverse-DCF no computado: {type(e).__name__}")

    return HojaEvidencia(
        ticker, arq, rz.stage, rz.route, estado, precio, op, mult, prem, burden,
        dil.burn_yield, dil.banda, dil.runway_anos,
        shares_growth_12m=dil.shares_growth_12m, shares_growth_24m=dil.shares_growth_24m,
        sbc_over_revenue=dil.sbc_over_revenue, up_c_suspect=dil.up_c_suspect,
        demanda_tier=demanda_tier, demanda_quote=demanda_quote,
        price_anchor_status=ru.price_anchor_status, reverse_burden_type=ru.reverse_burden_type,
        capital_risk_tier=ru.capital_risk_tier,
        revenue_contratado=revenue_contratado, bull_operable=esc.bull_price, haircut_source=haircut_src,
        bear_operable=esc.bear_price, asimetria_operable=asim_op,
        evidencia_insuficiente=evidencia_insuf, falsador_ya_priceado=fals.ya_priceado,
        falsador_veredicto=fals.veredicto,
        estado_reverse=estado_rev, estado_ruteo=estado_ruteo, revenue_ttm=fin.revenue_ttm,
        g_D_reverse=g_D_rev, t_star_reverse=t_star_rev,
        size_burden=size_burden_frac, a_carril_burden=a_carril_burden, flags=flags)


def _peer_rank_por_arquetipo(hojas: list[HojaEvidencia]) -> None:
    """Asigna `peer_rank` DENTRO de arquetipo (doc 31 §6) a los pre-revenue ANCHORED, por menor reverse
    burden. Solo el bucket NO rankeable (unanchored/pure_option). Muta las hojas in-place. Los PURE_OPTION
    quedan sin puesto (una lista con puestos se lee como recomendación)."""
    por_arq: dict[str, list[HojaEvidencia]] = {}
    for h in hojas:
        if h.estado != "RANKEABLE":
            por_arq.setdefault(h.arquetipo, []).append(h)
    for grupo in por_arq.values():
        anchored = sorted([h for h in grupo
                           if h.price_anchor_status == "ANCHORED" and h.burden_gp is not None],
                          key=lambda h: h.burden_gp)
        for i, h in enumerate(anchored, start=1):
            h.peer_rank = i


def rankear(tickers: list[str], session=None) -> dict:
    """FCFE rankeable → ranking ORDINAL por menor múltiplo. El resto → grupos DESCRIPTIVOS, con peer_rank
    DENTRO de arquetipo para los pre-revenue ANCHORED (menor reverse burden), pero SIN puesto global.
    `session` (opcional): si se pasa, agrega la columna de demanda citada (display-only) leída del fact store."""
    hojas = [hoja(t, session=session) for t in tickers]
    _peer_rank_por_arquetipo(hojas)
    rankeable = sorted([h for h in hojas if h.estado == "RANKEABLE"],
                       key=lambda h: h.multiplo_sobre_operable if h.multiplo_sobre_operable is not None else 1e9)
    grupos: dict[str, list] = {}
    for h in hojas:
        if h.estado != "RANKEABLE":
            grupos.setdefault(h.estado, []).append(h)
    # dentro del bucket descriptivo: ANCHORED por peer_rank (menor burden), pure_option al final por múltiplo
    for g in grupos.values():
        g.sort(key=lambda h: (h.peer_rank if h.peer_rank is not None else 1e6,
                              h.multiplo_sobre_operable if h.multiplo_sobre_operable is not None else 1e9))
    return {"rankeado": rankeable, "descriptivo": grupos}
