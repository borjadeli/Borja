"""Pre-screen determinista de candidatos a deep (doc 90 §8, keystone del discovery)."""
from __future__ import annotations

import textwrap

from backend.agentes.mapa_atribucion import MapaAtribucion
from backend.agentes.mapa_vivo import EstadoCuello
from backend.agentes.prescreen import prescreen

M = 1_000_000.0


def _atrib(tmp_path):
    p = tmp_path / "a.yaml"
    p.write_text(textwrap.dedent("""
        optica:
          CHEAP: {peso_pureza: 0.80}
          RICH:  {peso_pureza: 0.80}
          IMPURE: {peso_pureza: 0.10}
    """), encoding="utf-8")
    return MapaAtribucion(p)


def _cand(tk, cuello, *, rev=500 * M, growth=0.3, gross=0.35, op=0.05, ev_rev=3.0, ficha=False):
    return {"ticker": tk, "cuello": cuello, "revenue": rev, "revenue_growth_yoy": growth,
            "gross_profit": rev * gross, "operating_income_loss": rev * op, "ev_revenue": ev_rev,
            "tiene_ficha_reciente": ficha}


def _confirmado(cuello="optica"):
    return {cuello: EstadoCuello(cuello, "confirmado", "", 0.9, False, {}, {})}


def test_apto_pasa_las_cinco_puertas(tmp_path):
    cands = [_cand("CHEAP", "optica", ev_rev=2.0), _cand("RICH", "optica", ev_rev=6.0)]  # mediana 4.0
    r = prescreen(cands, estados_cuello=_confirmado(), atrib=_atrib(tmp_path))
    d = {c.ticker: c for c in r}
    assert d["CHEAP"].apto is True          # barata (2.0 < mediana 4.0)
    assert d["RICH"].gates["barata"] is False   # cara (6.0 > 4.0)


def test_cuello_promesa_sin_primer_hecho_no_pasa(tmp_path):
    estados = {"optica": EstadoCuello("optica", "promesa", "", 0.9, False, {}, {})}
    # op NEGATIVO → no es "primer hecho" → cuello falla
    cands = [_cand("CHEAP", "optica", op=-0.1, ev_rev=2.0), _cand("RICH", "optica", ev_rev=6.0)]
    r = {c.ticker: c for c in prescreen(cands, estados_cuello=estados, atrib=_atrib(tmp_path))}
    assert r["CHEAP"].gates["cuello"] is False


def test_primer_hecho_en_promesa_si_pasa(tmp_path):
    estados = {"optica": EstadoCuello("optica", "promesa", "", 0.9, False, {}, {})}
    # op POSITIVO + ventas materiales en un cuello promesa = la empresa que cruza (la ventana de alpha)
    cands = [_cand("CHEAP", "optica", op=0.05, ev_rev=2.0), _cand("RICH", "optica", ev_rev=6.0)]
    r = {c.ticker: c for c in prescreen(cands, estados_cuello=estados, atrib=_atrib(tmp_path))}
    assert r["CHEAP"].gates["cuello"] is True
    assert r["CHEAP"].apto is True


def test_pureza_baja_descarta(tmp_path):
    cands = [_cand("IMPURE", "optica", ev_rev=2.0), _cand("CHEAP", "optica", ev_rev=2.5), _cand("RICH", "optica", ev_rev=6.0)]
    r = {c.ticker: c for c in prescreen(cands, estados_cuello=_confirmado(), atrib=_atrib(tmp_path))}
    assert r["IMPURE"].gates["pureza"] is False   # peso 0.10 < 0.25
    assert r["IMPURE"].apto is False


def test_ficha_reciente_descarta(tmp_path):
    cands = [_cand("CHEAP", "optica", ev_rev=2.0, ficha=True), _cand("RICH", "optica", ev_rev=6.0)]
    r = {c.ticker: c for c in prescreen(cands, estados_cuello=_confirmado(), atrib=_atrib(tmp_path))}
    assert r["CHEAP"].gates["sin_ficha"] is False


def test_orden_por_brecha_aptos_primero(tmp_path):
    # dos aptos: el más barato (mayor brecha) va primero; un no-apto va al final
    cands = [_cand("CHEAP", "optica", growth=0.3, ev_rev=2.0),
             _cand("MID", "optica", growth=0.3, ev_rev=3.0),
             _cand("RICH", "optica", growth=0.3, ev_rev=6.0)]   # cara → no apto
    r = prescreen(cands, estados_cuello=_confirmado(), atrib=_atrib(tmp_path))
    assert r[0].ticker == "CHEAP"           # mayor brecha (más barato vs mediana)
    assert r[-1].ticker == "RICH" and r[-1].apto is False
