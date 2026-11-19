"""Tests del data pack assembler (v2 Fase 3). Sin red — se inyecta el snapshot/fuentes."""
from dataclasses import dataclass
from datetime import date

from backend.agentes import data_pack as dp
from backend.agentes.provenance import DataKind

AS_OF = date(2026, 10, 26)


@dataclass
class FakeSnap:
    ticker: str
    precio_actual: float | None
    volumen_diario_promedio_30d: float | None
    market_cap: float | None
    shares_outstanding: float | None = None
    currency: str = "USD"


def _fuente_fake(snap):
    return lambda tk, as_of: dp.fuente_mercado(tk, as_of, snapshot_fn=lambda _t: snap)


def test_fuente_mercado_tagea_procedencia():
    snap = FakeSnap("OKLO", precio_actual=50.0, volumen_diario_promedio_30d=3e7,
                    market_cap=4.9e9, shares_outstanding=1e8)
    pack = dp.ensamblar("oklo", as_of=AS_OF, fuentes=[_fuente_fake(snap)], fuentes_derivadas=[])
    metrics = {p.metric: p for p in pack.puntos}
    assert pack.ticker == "OKLO"
    assert metrics["market_cap"].value == 4.9e9
    assert metrics["market_cap"].kind == DataKind.ORIGINAL        # vino del feed
    assert all(p.known_at == AS_OF for p in pack.puntos)          # point-in-time
    assert metrics["precio"].source.document_type == "api"


def test_market_cap_derivado_si_falta_en_el_feed():
    snap = FakeSnap("X", precio_actual=10.0, volumen_diario_promedio_30d=2e6,
                    market_cap=None, shares_outstanding=5e8)
    pack = dp.ensamblar("X", as_of=AS_OF, fuentes=[_fuente_fake(snap)])
    mc = next(p for p in pack.puntos if p.metric == "market_cap")
    assert mc.value == 10.0 * 5e8
    assert mc.kind == DataKind.DERIVED
    assert mc.inputs == ["precio", "shares_outstanding"]          # deja rastro de insumos


def test_snapshot_none_no_rompe():
    pack = dp.ensamblar("X", as_of=AS_OF, fuentes=[_fuente_fake(None)], fuentes_derivadas=[])
    assert pack.puntos == []


def test_fuente_que_falla_no_tumba_el_pack():
    def rota(tk, as_of):
        raise RuntimeError("boom")
    snap = FakeSnap("X", 10.0, 2e6, 1e9, 1e8)
    pack = dp.ensamblar("X", as_of=AS_OF, fuentes=[rota, _fuente_fake(snap)])
    assert any(p.metric == "market_cap" for p in pack.puntos)     # la buena igual entró


def test_datapoint_no_defaultea_a_confirmed_filing():
    # auditoría P1: un DataPoint sin `verification` NO debe quedar como confirmed_by_filing (marcaría datos de
    # mercado como "confirmados por filing"). Default seguro = None (no aseverado).
    from backend.agentes.provenance import DataPoint, Source
    p = DataPoint(entity="OKLO", metric="precio", value=27.37, source=Source(name="Yahoo", document_type="api"))
    assert p.verification is None


def test_fuente_mercado_no_queda_confirmada_por_filing():
    snap = FakeSnap("OKLO", precio_actual=27.37, volumen_diario_promedio_30d=1e7,
                    market_cap=5e9, shares_outstanding=1.8e8)
    pts = dp.fuente_mercado("OKLO", date(2026, 10, 27), snapshot_fn=lambda _t: snap)
    assert pts and all(p.verification is None for p in pts)   # precios/market cap NO son confirmed_by_filing


# --------------------------------------------------------------------------- fuente_xbrl (P1 paso 1)
def _facts():
    inst = lambda val, end, filed, form, fy, fp, accn: {  # noqa: E731
        "val": val, "end": end, "filed": filed, "form": form, "fy": fy, "fp": fp, "accn": accn}
    dur = lambda val, start, end, filed, form, fy, fp, accn: {  # noqa: E731
        "val": val, "start": start, "end": end, "filed": filed, "form": form, "fy": fy, "fp": fp, "accn": accn}
    return {"facts": {
        "us-gaap": {
            "CashAndCashEquivalentsAtCarryingValue": {"units": {"USD": [
                inst(1000, "2025-12-31", "2026-03-01", "10-K", 2025, "FY", "a-fy25"),
                inst(1644, "2026-06-30", "2026-08-01", "10-Q", 2026, "Q2", "a-q2"),
            ]}},
            "OperatingIncomeLoss": {"units": {"USD": [
                dur(-139, "2025-01-01", "2025-12-31", "2026-03-01", "10-K", 2025, "FY", "a-fy25"),   # FY ~365d
                dur(-73, "2026-04-01", "2026-06-30", "2026-08-01", "10-Q", 2026, "Q2", "a-q2"),       # Q ~90d
            ]}},
        },
        "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [
            inst(186_000_000, "2026-08-04", "2026-08-05", "10-Q", 2026, "Q2", "a-q2")]}}},
    }}


def _xbrl(ticker, as_of):
    return dp.fuente_xbrl(ticker, as_of, companyfacts_fn=lambda _c: _facts(), cik_fn=lambda _t: "0000000000")


def test_xbrl_point_in_time_trae_lo_ultimo():
    pts = {p.metric: p for p in _xbrl("OKLO", date(2026, 10, 27))}
    assert pts["cash"].value == 1644 and pts["cash"].known_at == date(2026, 8, 1)       # Q2-26, no FY25
    assert pts["cash"].kind == DataKind.ORIGINAL and "a-q2" in pts["cash"].note
    assert pts["shares_outstanding"].value == 186_000_000


def _facts_deuda_stale():
    inst = lambda val, end, filed, form, fy, fp, accn: {  # noqa: E731
        "val": val, "end": end, "filed": filed, "form": form, "fy": fy, "fp": fp, "accn": accn}
    return {"facts": {"us-gaap": {
        # el tag PRIORITARIO (LongTermDebtNoncurrent) quedó VIEJO (2022); otro de MENOR prioridad tiene dato FRESCO
        "LongTermDebtNoncurrent": {"units": {"USD": [
            inst(723_000, "2022-03-31", "2022-03-23", "10-K", 2021, "FY", "stale")]}},
        "LongTermDebt": {"units": {"USD": [
            inst(11_901_000, "2026-09-30", "2026-11-02", "10-Q", 2026, "Q3", "fresco")]}},
    }}}


def test_xbrl_emit_primero_prefiere_fresco_sobre_stale():
    # guard de frescura (destapado por el A/B con RXRX, 2026-11): un tag prioritario STALE (2022) NO debe tapar
    # uno fresco (2026). Antes emit_primero tomaba el primero-con-dato (el stale).
    pts = {p.metric: p for p in dp.fuente_xbrl("RXRX", date(2026, 11, 19),
                                               companyfacts_fn=lambda _c: _facts_deuda_stale(), cik_fn=lambda _t: "0")}
    assert pts["long_term_debt"].value == 11_901_000            # el FRESCO, no el stale de 2022
    assert pts["long_term_debt"].known_at == date(2026, 11, 2)


def test_xbrl_anti_look_ahead():
    # as_of antes del filing del Q2 → solo se ve FY25 (filed 2026-03-01 <= as_of)
    pts = {p.metric: p for p in _xbrl("OKLO", date(2026, 5, 1))}
    assert pts["cash"].value == 1000 and pts["cash"].known_at == date(2026, 3, 1)


def test_xbrl_duracion_toma_el_ano_fiscal_no_el_trimestre():
    pts = {p.metric: p for p in _xbrl("OKLO", date(2026, 10, 27))}
    assert pts["operating_income_loss"].value == -139 and pts["operating_income_loss"].period_type == "FY"


def test_xbrl_de_un_filing_es_confirmed_filing():
    from backend.agentes.provenance import Verification
    pts = _xbrl("OKLO", date(2026, 10, 27))
    assert all(p.verification == Verification.CONFIRMED_FILING for p in pts)   # vs Yahoo=None


# --------------------------------------------------------------------------- fuente_calculadoras (P1 paso 2)
def _dp_in(metric, value, known, unit="USD"):
    from backend.agentes.provenance import DataKind, DataPoint, Source, Verification
    return DataPoint(entity="OKLO", metric=metric, value=value, unit=unit, kind=DataKind.ORIGINAL,
                     verification=Verification.CONFIRMED_FILING, source=Source(name="SEC"),
                     known_at=known, note=f"accn={metric}")


def test_calc_runway_y_dilucion_con_linaje():
    pts = [_dp_in("cash", 1644e6, date(2026, 8, 7)), _dp_in("cash_used_ops", -82.2e6, date(2026, 3, 17)),
           _dp_in("shares_outstanding", 186e6, date(2026, 8, 7), unit="shares"),
           _dp_in("shares_outstanding_1y", 150e6, date(2025, 8, 7), unit="shares")]
    der = {p.metric: p for p in dp.fuente_calculadoras("OKLO", date(2026, 10, 27), pts)}
    rw = der["cash_runway_months"]
    assert rw.estado == "COMPUTED" and abs(rw.value - 1644e6 / (82.2e6 / 12)) < 1
    assert rw.kind == DataKind.DERIVED
    assert rw.known_at == date(2026, 8, 7)              # max(insumos) — NO look-ahead
    assert rw.stalest_input_at == date(2026, 3, 17)     # min(insumos)
    assert set(rw.inputs) == {"cash", "cash_used_ops"} and "accn=cash" in rw.input_refs
    dil = der["dilucion_12m_pct"]
    assert dil.estado == "COMPUTED" and abs(dil.value - (186 / 150 - 1) * 100) < 0.1


def test_calc_missing_emite_datapoint_explicito():
    der = {p.metric: p for p in dp.fuente_calculadoras("OKLO", date(2026, 10, 27),
                                                        [_dp_in("cash", 1000e6, date(2026, 8, 7))])}
    assert der["cash_runway_months"].value is None and der["cash_runway_months"].estado == "MISSING"


def test_calc_not_applicable_si_genera_caja():
    pts = [_dp_in("cash", 1000e6, date(2026, 8, 7)), _dp_in("cash_used_ops", 50e6, date(2026, 3, 17))]
    der = {p.metric: p for p in dp.fuente_calculadoras("OKLO", date(2026, 10, 27), pts)}
    assert der["cash_runway_months"].estado == "NOT_APPLICABLE" and der["cash_runway_months"].value is None


def test_ensamblar_dos_fases_corre_derivadas():
    orig = lambda tk, ao: [_dp_in("cash", 1200e6, date(2026, 8, 7)),  # noqa: E731
                           _dp_in("cash_used_ops", -120e6, date(2026, 3, 17))]
    pack = dp.ensamblar("OKLO", as_of=date(2026, 10, 27), fuentes=[orig])   # derivadas = default
    m = {p.metric: p for p in pack.puntos}
    assert m["cash_runway_months"].value == 120.0 and m["cash_runway_months"].kind == DataKind.DERIVED


def test_calc_liquidez_suma_valores_negociables():
    # OKLO/RGTI-style: sin tag combinado → liquidez = caja + ST current + securities noncurrent (ladder).
    # Bug del smoke (doc 72): tomábamos solo `cash` ($27,8M en RGTI) en vez de $541,3M reales.
    pts = [_dp_in("cash", 27.763e6, date(2026, 8, 7)),
           _dp_in("short_term_investments", 365.946e6, date(2026, 8, 7)),
           _dp_in("long_term_investments", 147.586e6, date(2026, 8, 7)),
           _dp_in("cash_used_ops", -58.543e6, date(2026, 3, 17)),
           _dp_in("capex", 18.676e6, date(2026, 3, 17))]
    der = {p.metric: p for p in dp.fuente_calculadoras("RGTI", date(2026, 10, 27), pts)}
    assert abs(der["liquidez"].value - 541.295e6) < 1e4
    rw = der["cash_runway_months"]                               # capex SUMA a la quema (op−capex)
    assert rw.estado == "COMPUTED"
    assert abs(rw.value - 541.295e6 / ((58.543e6 + 18.676e6) / 12)) < 0.5
    assert {"cash", "short_term_investments", "long_term_investments", "cash_used_ops", "capex"} <= set(rw.inputs)


def test_calc_liquidez_prefiere_combinado_sin_doble_contar_caja():
    # MP-style: el tag combinado ya incluye caja+ST → NO sumar `cash` otra vez (sería doble conteo).
    pts = [_dp_in("cash", 429.075e6, date(2026, 8, 7)),
           _dp_in("cash_and_sti", 1452.639e6, date(2026, 8, 7)),
           _dp_in("cash_used_ops", -155.755e6, date(2026, 3, 17)),
           _dp_in("capex", 172.375e6, date(2026, 3, 17))]
    der = {p.metric: p for p in dp.fuente_calculadoras("MP", date(2026, 10, 27), pts)}
    assert abs(der["liquidez"].value - 1452.639e6) < 1e4        # NO 429 + 1452
    assert abs(der["cash_runway_months"].value - 1452.639e6 / ((155.755e6 + 172.375e6) / 12)) < 0.5


def test_calc_runway_sin_capex_usa_solo_opex_y_avisa():
    # Si el emisor no tagea capex, no se silencia: runway sobre opex PERO la nota marca el hueco.
    pts = [_dp_in("cash", 1000e6, date(2026, 8, 7)), _dp_in("cash_used_ops", -120e6, date(2026, 3, 17))]
    rw = {p.metric: p for p in dp.fuente_calculadoras("X", date(2026, 10, 27), pts)}["cash_runway_months"]
    assert abs(rw.value - 1000e6 / (120e6 / 12)) < 0.5          # 100 meses, solo opex
    assert "capex no disponible" in rw.note


def test_calc_dilucion_overhang_marca_convertibles_invisibles():
    # doc 72 B1: un dilucion_12m_pct BAJO no debe leerse como "dilución baja" si hay convertibles/warrants
    # cuya conversión NO está en XBRL (MP: DoD preferred+warrants ITM ~9% salían con 0,49% realizado).
    pts = [_dp_in("shares_outstanding", 178.1e6, date(2026, 8, 7), unit="shares"),
           _dp_in("shares_outstanding_1y", 177.2e6, date(2025, 10, 31), unit="shares"),
           _dp_in("convertible_pref_proceeds", 299.4e6, date(2026, 3, 1)),
           _dp_in("warrant_proceeds", 189.0e6, date(2026, 3, 1))]
    der = {p.metric: p for p in dp.fuente_calculadoras("MP", date(2026, 10, 27), pts)}
    assert abs(der["dilucion_12m_pct"].value - 0.51) < 0.1                  # realizada, baja
    assert "NO incluye" in der["dilucion_12m_pct"].note                     # ventana + caveat explícito
    assert der["dilucion_overhang"].value == 1.0                           # pero la señal de overhang salta
    assert "notas del filing" in der["dilucion_overhang"].note


def test_calc_sin_overhang_no_inventa_la_senal():
    # OKLO-style: dilución por equity directo (sin convertibles/warrants) → NO se emite la señal (no falso +)
    pts = [_dp_in("shares_outstanding", 186e6, date(2026, 8, 7), unit="shares"),
           _dp_in("shares_outstanding_1y", 156e6, date(2025, 11, 7), unit="shares")]
    der = {p.metric: p for p in dp.fuente_calculadoras("OKLO", date(2026, 10, 27), pts)}
    assert abs(der["dilucion_12m_pct"].value - 19.23) < 0.3                 # dilución realizada visible
    assert "dilucion_overhang" not in der


def test_xbrl_resuelve_valores_negociables_por_candidatos():
    facts = _facts()
    g = facts["facts"]["us-gaap"]
    g["DebtSecuritiesAvailableForSaleExcludingAccruedInterestCurrent"] = {"units": {"USD": [
        {"val": 820, "end": "2026-06-30", "filed": "2026-08-01", "form": "10-Q", "fy": 2026, "fp": "Q2", "accn": "c"}]}}
    g["DebtSecuritiesAvailableForSaleExcludingAccruedInterestNoncurrent"] = {"units": {"USD": [
        {"val": 541, "end": "2026-06-30", "filed": "2026-08-01", "form": "10-Q", "fy": 2026, "fp": "Q2", "accn": "n"}]}}
    pts = {p.metric: p for p in dp.fuente_xbrl("OKLO", date(2026, 10, 27),
                                               companyfacts_fn=lambda _c: facts, cik_fn=lambda _t: "0")}
    assert pts["short_term_investments"].value == 820 and pts["long_term_investments"].value == 541
    from backend.agentes.provenance import Verification
    assert pts["short_term_investments"].verification == Verification.CONFIRMED_FILING   # ORIGINAL de un tag


def test_xbrl_emite_version_trimestral_de_flujos():
    facts = _facts()
    # agrego un op-loss trimestral (~90d) al fake
    facts["facts"]["us-gaap"]["OperatingIncomeLoss"]["units"]["USD"].append(
        {"val": -73, "start": "2026-04-01", "end": "2026-06-30", "filed": "2026-08-01",
         "form": "10-Q", "fy": 2026, "fp": "Q2", "accn": "a-q2b"})
    pts = {(p.metric, p.period_type): p for p in dp.fuente_xbrl(
        "OKLO", date(2026, 10, 27), companyfacts_fn=lambda _c: facts, cik_fn=lambda _t: "0")}
    assert ("operating_income_loss", "FY") in pts        # FY (−139, del 10-K)
    assert ("operating_income_loss_q", "Q") in pts       # Q (−73, del 10-Q)
    assert pts[("operating_income_loss_q", "Q")].value == -73
