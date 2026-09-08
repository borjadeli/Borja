"""FichaPM sin merito cardinal (doc 33/34): compone tier + rank + cap desde el CandidatoLex."""
from types import SimpleNamespace

from backend.seleccion import pm


def _cand(**kw):
    base = dict(ticker="LEU", tier_capital="A", cap=0.08)
    base.update(kw)
    return SimpleNamespace(**base)


def _hoja(**kw):
    base = dict(arquetipo="Tracción", operable=35.0, option_premium_pct=0.8,
                demanda_quote="RPO no cancelable $0.8B", flags=["concentracion 30%", "runway ok"])
    base.update(kw)
    return SimpleNamespace(**base)


def test_ficha_sin_merito_cardinal():
    f = pm.ficha_desde_candidato(_cand(), _hoja(), rank=1)
    assert f.ticker == "LEU" and f.tier_capital == "A" and f.rank == 1 and f.cap == 0.08
    assert not hasattr(f, "merito")                       # el score cardinal murió (doc 33)
    assert f.precio_base_sin_contratos == 35.0 and f.pct_opcionalidad_priceada == 0.8
    assert f.fragilidad_porque == "concentracion 30%" and any("demanda" in h for h in f.hechos)


def test_proponer_mix_reinyecta_tier_cap_no_merito():
    fichas = [pm.ficha_desde_candidato(_cand(ticker="LEU"), _hoja(), rank=1)]
    out = pm.proponer_mix(fichas, llm_json={"mix": [{"ticker": "LEU", "incluir": True}]})
    linea = out["mix"][0]
    assert linea["tier_nucleo"] == "A" and linea["cap_nucleo"] == 0.08
    assert "merito_nucleo" not in linea and "sizing_nucleo" not in linea


def test_pm_no_puede_inventar_tickers():
    fichas = [pm.ficha_desde_candidato(_cand(ticker="LEU"), _hoja(), rank=1)]
    out = pm.proponer_mix(fichas, llm_json={"mix": [{"ticker": "FAKE", "incluir": True}]})
    assert out["mix"] == []                                # FAKE no está en las candidatas del núcleo


def test_fmt_ficha_renderiza_sin_merito():
    f = pm.ficha_desde_candidato(_cand(), _hoja(), rank=2)
    linea = pm.formatear_user_message([f], "contexto")
    assert "tier=A" in linea and "rank=#2" in linea and "mérito" not in linea
