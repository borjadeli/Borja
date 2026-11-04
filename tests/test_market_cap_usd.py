"""market_cap en USD con FX (soporte extranjero, doc 76). Sin red — monkeypatch de get_price_snapshot."""
from types import SimpleNamespace

import backend.services.market_data as md
from backend.agentes.descubrimiento import PropuestaEmpresa, validar_propuesta

_IPS = {"market_cap_min_usd": 150e6, "market_cap_max_usd": 60e9}


def _snap(mc, currency="USD", precio=None):
    return SimpleNamespace(ticker="X", precio_actual=precio, volumen_diario_promedio_30d=None,
                           market_cap=mc, shares_outstanding=None, currency=currency)


def test_fx_usd_es_identidad():
    assert md.fx_a_usd("USD") == 1.0


def test_fx_convierte_desde_local(monkeypatch):
    # el par USDKRW=X cotiza 1390 KRW por 1 USD → 1 KRW = 1/1390 USD
    monkeypatch.setattr(md, "get_price_snapshot", lambda tk: _snap(None, precio=1390.0))
    r = md.fx_a_usd("KRW")
    assert abs(r - 1 / 1390) < 1e-12


def test_market_cap_usd_convierte_cap_local(monkeypatch):
    # 17.652B KRW a 1390 KRW/USD ≈ $12.7B (NO $17 billones)
    def fake(tk):
        return _snap(17_652.1e9, currency="KRW") if not tk.endswith("=X") else _snap(None, precio=1390.0)
    monkeypatch.setattr(md, "get_price_snapshot", fake)
    usd = md.market_cap_usd("042700.KS")
    assert 12e9 < usd < 13e9                      # en banda $150M-$60B una vez convertido


def test_market_cap_usd_none_si_no_hay_dato(monkeypatch):
    monkeypatch.setattr(md, "get_price_snapshot", lambda tk: None)
    assert md.market_cap_usd("ZZZ.XX") is None


def test_gate_de_banda_con_cap_convertido():
    # con el cap ya en USD (como lo deja _verificar_caps), el validador de discovery gatea bien
    p_ok = PropuestaEmpresa(ticker="042700.KS", cuello="HBM", tesis_corta="t", por_que_ahora="x",
                            fuentes=["u"], market_cap=12.7e9)
    ok, _ = validar_propuesta(p_ok, ips_cfg=_IPS, universo_actual=set(), nodos_conocidos={"HBM"})
    assert ok
    p_gigante = PropuestaEmpresa(ticker="BIG", cuello="HBM", tesis_corta="t", por_que_ahora="x",
                                 fuentes=["u"], market_cap=200e9)
    ok2, m2 = validar_propuesta(p_gigante, ips_cfg=_IPS, universo_actual=set(), nodos_conocidos={"HBM"})
    assert not ok2 and any("fuera del rango" in x for x in m2)
