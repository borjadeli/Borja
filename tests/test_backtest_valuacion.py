"""Backtest point-in-time de valuación (doc 40 Bloque 0.2): reconstrucción as-of, precio as-of, separación."""
from datetime import datetime
from backend.nucleo import backtest_valuacion as BT


def test_precio_asof_toma_el_mas_reciente_previo():
    rows = [{"date": datetime(2023, 1, 1), "close": 10.0},
            {"date": datetime(2023, 6, 1), "close": 20.0},
            {"date": datetime(2024, 1, 1), "close": 30.0}]
    assert BT._precio_asof(rows, "2023-07-01") == 20.0     # el más reciente ≤ fecha
    assert BT._precio_asof(rows, "2024-06-01") == 30.0
    assert BT._precio_asof(rows, "2022-01-01") is None     # nada previo


def test_filed_hasta_filtra_look_ahead():
    from backend.services import edgar
    entries = [{"end": "2022-03-31", "val": 1, "filed": "2022-05-01"},
               {"end": "2022-06-30", "val": 2, "filed": "2022-08-01"}]
    # as_of 2022-06-15: solo se conocía el Q1 (filed 2022-05), NO el Q2 (filed 2022-08)
    r = edgar._filed_hasta(entries, "2022-06-15")
    assert len(r) == 1 and r[0]["end"] == "2022-03-31"
    assert len(edgar._filed_hasta(entries, None)) == 2     # sin filtro = todas


def test_resumen_agrega():
    r = BT._resumen([0.1, 0.5, -0.2])
    assert r["n"] == 3 and abs(r["media"] - 0.1333) < 0.001 and r["mediana"] == 0.1


def test_correr_separacion(monkeypatch):
    # 2 casos COVERED que suben, 2 NON_UNDERWRITABLE que bajan → separación positiva
    def fake_eval(t, d, **k):
        c = BT.CasoBacktest(ticker=t, as_of=d)
        m = {"A": ("COVERED", 0.8), "B": ("STRETCH", 0.4), "C": ("NON_UNDERWRITABLE", -0.3),
             "D": ("OPTION_PRICED", -0.1)}[t]
        c.estado, c.retorno_fwd = m
        return c
    monkeypatch.setattr(BT, "evaluar_caso", fake_eval)
    r = BT.correr([("A", "2022-01-01"), ("B", "2022-01-01"), ("C", "2022-01-01"), ("D", "2022-01-01")])
    assert r["n_evaluables"] == 4
    assert r["compra"]["n"] == 2 and r["rechazo"]["n"] == 2
    assert r["separacion"] > 0                             # compra (0.6) > rechazo (−0.2)


def test_correr_ignora_sin_estado_o_sin_retorno(monkeypatch):
    def fake_eval(t, d, **k):
        c = BT.CasoBacktest(ticker=t, as_of=d)
        if t == "OK":
            c.estado, c.retorno_fwd = "COVERED", 0.5
        # "BAD" queda sin estado/retorno
        return c
    monkeypatch.setattr(BT, "evaluar_caso", fake_eval)
    r = BT.correr([("OK", "2022-01-01"), ("BAD", "2022-01-01")])
    assert r["n_evaluables"] == 1
