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
