"""Chequeos de consistencia automáticos del pack (r6 #4 'verificar siempre'). Determinista, sin red."""
from datetime import date, timedelta

from backend.agentes.data_pack import fuente_consistencia
from backend.agentes.provenance import DataKind, DataPoint, Source

HOY = date(2026, 11, 5)
_FEED = Source(name="Yahoo Finance", document_type="api")
_XBRL = Source(name="EDGAR XBRL companyfacts", document_type="xbrl")


def _p(metric, value, *, source, known_at=HOY, unit="shares"):
    return DataPoint(entity="X", metric=metric, value=value, unit=unit, source=source, known_at=known_at)


def _flags(puntos):
    return {p.metric: p for p in fuente_consistencia("X", HOY, puntos)}


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
