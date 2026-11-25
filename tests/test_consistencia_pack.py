"""Chequeos de consistencia automáticos del pack (r6 #4 'verificar siempre'). Determinista, sin red."""
from datetime import date, timedelta

from backend.agentes.data_pack import fuente_consistencia
from backend.agentes.provenance import DataKind, DataPoint, Source

HOY = date(2026, 11, 5)
_FEED = Source(name="Yahoo Finance", document_type="api")
_XBRL = Source(name="EDGAR XBRL companyfacts", document_type="xbrl")


def _p(metric, value, *, source, known_at=HOY, unit="shares"):
    return DataPoint(entity="X", metric=metric, value=value, unit=unit, source=source, known_at=known_at)


def _flags(puntos, filings_fn=lambda t: []):   # sin red por default (el check #5 no dispara)
    return {p.metric: p for p in fuente_consistencia("X", HOY, puntos, filings_fn=filings_fn)}


def test_shares_divergentes_marca_conflicted():
    # feed 100M vs XBRL 70M → 30% de diferencia → bandera (dilución/extracción)
    puntos = [_p("shares_outstanding", 100e6, source=_FEED), _p("shares_outstanding", 70e6, source=_XBRL)]
    f = _flags(puntos)
    assert "flag_shares_divergentes" in f and f["flag_shares_divergentes"].estado == "CONFLICTED"


def test_shares_parecidas_no_marca():
    puntos = [_p("shares_outstanding", 100e6, source=_FEED), _p("shares_outstanding", 95e6, source=_XBRL)]
    assert "flag_shares_divergentes" not in _flags(puntos)      # 5% < 25% → OK


def test_market_cap_escala_sospechosa():
    puntos = [_p("market_cap", 5.0, source=_FEED, unit="USD")]   # $5 → claramente mal escalado
    assert "flag_market_cap_escala" in _flags(puntos)


def test_p0_5_market_cap_no_reconcilia_con_precio_x_acciones():
    # P0.5 (doc 91): el feed de GLXY daba market cap de TODAS las clases ($6.75B) pero shares_outstanding solo
    # clase A (189M) → mc/precio = 584M ≠ 189M. Se caza SIN XBRL (inconsistencia interna del feed).
    puntos = [DataPoint(entity="X", metric="market_cap", value=6.75e9, unit="USD", source=_FEED, known_at=HOY, currency="USD"),
              DataPoint(entity="X", metric="precio", value=11.55, unit="USD", source=_FEED, known_at=HOY, currency="USD"),
              _p("shares_outstanding", 189e6, source=_FEED)]
    assert "flag_market_cap_no_reconcilia" in _flags(puntos)


def test_p0_5_market_cap_reconcilia_no_marca():
    puntos = [DataPoint(entity="X", metric="market_cap", value=11.55 * 189e6, unit="USD", source=_FEED, known_at=HOY, currency="USD"),
              DataPoint(entity="X", metric="precio", value=11.55, unit="USD", source=_FEED, known_at=HOY, currency="USD"),
              _p("shares_outstanding", 189e6, source=_FEED)]
    assert "flag_market_cap_no_reconcilia" not in _flags(puntos)    # mc = precio×acciones → consistente


def test_p0_5_moneda_distinta_no_marca():
    # precio KRW, market cap USD (extranjera convertida) → NO es inconsistencia, es FX → no debe marcar.
    puntos = [DataPoint(entity="X", metric="market_cap", value=16e9, unit="USD", source=_FEED, known_at=HOY, currency="USD"),
              DataPoint(entity="X", metric="precio", value=40000.0, unit="KRW", source=_FEED, known_at=HOY, currency="KRW"),
              _p("shares_outstanding", 640e6, source=_FEED)]
    assert "flag_market_cap_no_reconcilia" not in _flags(puntos)


def test_datos_xbrl_viejos():
    viejo = HOY - timedelta(days=500)
    puntos = [_p("cash", 1e9, source=_XBRL, known_at=viejo, unit="USD")]
    assert "flag_datos_viejos" in _flags(puntos)


class _F:                                           # mimetiza RecentFiling (items/fecha/accession)
    def __init__(self, items, fecha, accn="0001-26-000001"):
        self.items, self.fecha, self.accession_number = items, fecha, accn


def test_balance_desactualizado_por_8k_posterior():
    # IESC/DBM: XBRL de julio + 8-K 2.01 (adquisición) de octubre → balance del pack vencido → CONFLICTED.
    xbrl_jul = date(2026, 7, 31)
    puntos = [_p("cash", 77e6, source=_XBRL, known_at=xbrl_jul, unit="USD")]
    filings = [_F("1.01,2.01,7.01,9.01", date(2026, 10, 6)),   # adquisición completada, POSTERIOR al XBRL
               _F("2.02,9.01", date(2026, 9, 1))]              # earnings (no de balance) → ignorado
    f = _flags(puntos, filings_fn=lambda t: filings)
    assert "flag_balance_desactualizado" in f and f["flag_balance_desactualizado"].estado == "CONFLICTED"
    assert "2026-10-06" in f["flag_balance_desactualizado"].note


def test_balance_fresco_8k_previo_no_marca():
    # 8-K de balance ANTERIOR al XBRL (ya está incorporado en companyfacts) → no dispara.
    puntos = [_p("cash", 77e6, source=_XBRL, known_at=date(2026, 7, 31), unit="USD")]
    filings = [_F("2.03,9.01", date(2026, 6, 1))]              # deuda, pero previa al 10-Q
    assert "flag_balance_desactualizado" not in _flags(puntos, filings_fn=lambda t: filings)


def test_balance_8k_no_de_balance_no_marca():
    # 8-K posterior pero de ítems NO-balance (8.01 otros eventos) → no dispara.
    puntos = [_p("cash", 77e6, source=_XBRL, known_at=date(2026, 7, 31), unit="USD")]
    filings = [_F("8.01,9.01", date(2026, 10, 1))]
    assert "flag_balance_desactualizado" not in _flags(puntos, filings_fn=lambda t: filings)


def test_balance_8k_solo_101_es_advisory_no_bloquea():
    # precisión (scan 2026-11-17): un 8-K POSTERIOR solo con 1.01 (acuerdo material amplio, puede no tocar el
    # balance) → flag_balance_revisar ADVISORY, NO el flag_balance_desactualizado que bloquea.
    puntos = [_p("cash", 77e6, source=_XBRL, known_at=date(2026, 7, 31), unit="USD")]
    filings = [_F("1.01,9.01", date(2026, 10, 6))]
    f = _flags(puntos, filings_fn=lambda t: filings)
    assert "flag_balance_revisar" in f and "flag_balance_desactualizado" not in f


def test_balance_8k_con_203_si_bloquea():
    # 2.03 (deuda nueva) POSTERIOR → señal DURA → flag_balance_desactualizado (bloquea), aunque venga con 1.01.
    puntos = [_p("cash", 77e6, source=_XBRL, known_at=date(2026, 7, 31), unit="USD")]
    filings = [_F("1.01,2.03,9.01", date(2026, 10, 6))]
    assert "flag_balance_desactualizado" in _flags(puntos, filings_fn=lambda t: filings)


def test_instrumentos_dilutivos_marca():
    # F2 (doc 83): acciones antidilutivas excluidas del EPS significativas vs las básicas → hay instrumentos a
    # inventariar (converts/preferidas/warrants). Es el detector determinista del caso MP.
    puntos = [_p("shares_outstanding", 178e6, source=_XBRL),
              _p("antidilutive_shares", 64e6, source=_XBRL)]            # 36% de las básicas → dispara
    assert "flag_instrumentos_dilutivos" in _flags(puntos)
    # antidilutivas chicas (< 10%) → no dispara
    ok = [_p("shares_outstanding", 178e6, source=_XBRL), _p("antidilutive_shares", 5e6, source=_XBRL)]
    assert "flag_instrumentos_dilutivos" not in _flags(ok)


def test_pack_sano_sin_flags():
    puntos = [_p("shares_outstanding", 100e6, source=_FEED),
              _p("shares_outstanding", 98e6, source=_XBRL),
              _p("market_cap", 5e9, source=_FEED, unit="USD"),
              _p("cash", 1e9, source=_XBRL, unit="USD")]
    assert _flags(puntos) == {}


def test_revenue_sospechoso_marca_conflicted():
    # el caso GLXY: revenue $60B con market cap $5B → 12× → bandera (¿volumen mal tageado?)
    puntos = [_p("market_cap", 5e9, source=_FEED, unit="USD"), _p("revenue", 60e9, source=_XBRL, unit="USD")]
    f = _flags(puntos)
    assert "flag_revenue_sospechoso" in f and f["flag_revenue_sospechoso"].estado == "CONFLICTED"


def test_revenue_normal_no_marca():
    # distribuidor de bajo margen: revenue 2× market cap → normal, sin bandera
    puntos = [_p("market_cap", 20e9, source=_FEED, unit="USD"), _p("revenue", 40e9, source=_XBRL, unit="USD")]
    assert "flag_revenue_sospechoso" not in _flags(puntos)
