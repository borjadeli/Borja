"""Pieza 6-real: extractor de métricas del pack (puro)."""
from types import SimpleNamespace

from ops.mapa_job import metricas_de_pack


def _dp(metric, value, period_type="FY"):
    return SimpleNamespace(metric=metric, value=value, period_type=period_type)


def test_metricas_de_pack_extrae_y_deriva_crecimiento():
    pack = SimpleNamespace(puntos=[
        _dp("revenue", 1200.0), _dp("revenue_fy_prev", 1000.0),
        _dp("gross_profit", 400.0), _dp("operating_income_loss", 84.0),
        _dp("capex", 100.0), _dp("inventarios", 150.0), _dp("rpo", 500.0),
        _dp("revenue_q", 300.0, "Q"),          # ruido: no es una métrica del tablero
    ])
    m = metricas_de_pack(pack)
    assert m["revenue"] == 1200.0
    assert m["operating_income_loss"] == 84.0
    assert m["revenue_growth_yoy"] == 0.2       # (1200/1000 − 1), como FRACCIÓN


def test_prefiere_fy_sobre_q():
    pack = SimpleNamespace(puntos=[_dp("revenue", 300.0, "Q"), _dp("revenue", 1200.0, "FY")])
    assert metricas_de_pack(pack)["revenue"] == 1200.0


def test_sin_prev_revenue_crecimiento_none():
    pack = SimpleNamespace(puntos=[_dp("revenue", 1200.0)])
    assert metricas_de_pack(pack)["revenue_growth_yoy"] is None
