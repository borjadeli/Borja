"""Cross-validator de datos financieros (auditoría 2026-08)."""
from types import SimpleNamespace

from backend.nucleo.validacion_datos import flags_plausibilidad


def _fin(**kw):
    base = dict(revenue_ttm=None, fcf_ttm=None, capex_ttm=None, shares_outstanding=None, cash=None)
    base.update(kw)
    return SimpleNamespace(**base)


def test_capex_faltante_flaggea():
    # Caso CLS: revenue material pero capex no encontrado → alta.
    fl = flags_plausibilidad(_fin(revenue_ttm=15e9, fcf_ttm=1e9, capex_ttm=None))
    assert any(f.campo == "capex_ttm" and f.severidad == "alta" for f in fl)


def test_margen_fcf_alto_flaggea():
    # Caso VRNS: margen FCF implícito 60% → probable inflación.
    fl = flags_plausibilidad(_fin(revenue_ttm=100e6, fcf_ttm=60e6, capex_ttm=5e6))
    assert any(f.campo == "fcf_ttm" for f in fl)


def test_caja_sobre_market_cap_flaggea():
    # Caso LEU (shares stale): caja 60% del market cap.
    fl = flags_plausibilidad(_fin(shares_outstanding=100e6, cash=600e6), precio=10.0)
    assert any(f.campo == "cash" for f in fl)


def test_shares_stale_por_antiguedad_flaggea():
    # Caso LEU: dato de shares de 2022, último Q de 2026 → stale por ANTIGÜEDAD (no por dilución).
    fl = flags_plausibilidad(_fin(shares_outstanding=13.67e6, shares_as_of="2022-12-31",
                                  quarters=[{"fecha": "2026-06-30"}]))
    assert any(f.campo == "shares" and f.severidad == "media" for f in fl)


def test_shares_recientes_no_flaggean():
    # Dato de shares del mismo trimestre → no stale (aunque haya diluido, la FECHA es reciente).
    fl = flags_plausibilidad(_fin(shares_outstanding=100e6, shares_as_of="2026-06-30",
                                  quarters=[{"fecha": "2026-06-30"}]))
    assert not any(f.campo == "shares" for f in fl)


def test_datos_sanos_no_flaggean():
    fl = flags_plausibilidad(
        _fin(revenue_ttm=1000e6, fcf_ttm=100e6, capex_ttm=50e6, shares_outstanding=100e6, cash=100e6),
        precio=20.0)
    assert fl == []
