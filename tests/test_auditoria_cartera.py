"""Tests de los chequeos de cartera del Auditor (v2 doc 70 D3). Puros, sin API."""
from backend.agentes.auditoria_cartera import exposicion_por_factor, render_para_auditor, tesis_cambiada


def test_exposicion_por_factor_detecta_concentracion_oculta():
    pesos = {"OKLO": 0.1, "SMR": 0.1, "NNE": 0.1, "MP": 0.1}   # 3 del mismo cuello nuclear
    factores = {"OKLO": ["cuello:SMR"], "SMR": ["cuello:SMR"], "NNE": ["cuello:SMR"],
                "MP": ["cuello:tierras_raras"]}
    exp = exposicion_por_factor(pesos, factores, umbral=0.25)
    assert len(exp) == 1 and exp[0].factor == "cuello:SMR" and abs(exp[0].peso - 0.3) < 1e-9
    assert set(exp[0].tickers) == {"OKLO", "SMR", "NNE"}


def test_exposicion_ignora_bajo_umbral():
    pesos = {"A": 0.1, "B": 0.1}
    factores = {"A": ["f1"], "B": ["f2"]}
    assert exposicion_por_factor(pesos, factores, umbral=0.30) == []


class _Dec:
    def __init__(self, ticker, accion, tesis, ts):
        self.ticker, self.accion, self.tesis = ticker, accion, tesis
        from datetime import datetime
        self.ts = datetime.fromisoformat(ts)


class _Ledger:
    def __init__(self, decs): self._d = decs
    def decisiones(self): return self._d


def test_tesis_cambiada_detecta_el_switch():
    led = _Ledger([
        _Dec("OKLO", "comprar", "opción regulatoria sobre SMR para data centers", "2026-10-01T00:00:00"),
        _Dec("OKLO", "mantener", "ahora el valor está en el negocio de isótopos", "2026-11-01T00:00:00"),
    ])
    out = tesis_cambiada(led, {"OKLO"})
    assert len(out) == 1 and out[0]["ticker"] == "OKLO"
    assert "isótopos" in out[0]["tesis_actual"]


def test_tesis_estable_no_se_marca():
    led = _Ledger([
        _Dec("OKLO", "comprar", "misma tesis", "2026-10-01T00:00:00"),
        _Dec("OKLO", "mantener", "misma tesis", "2026-11-01T00:00:00"),
    ])
    assert tesis_cambiada(led, {"OKLO"}) == []


def test_render_para_auditor():
    from backend.agentes.auditoria_cartera import ExposicionFactor
    txt = render_para_auditor([ExposicionFactor("cuello:SMR", 0.3, ["OKLO", "SMR"])],
                              [{"ticker": "X", "tesis_entrada": "a", "tesis_actual": "b"}])
    assert "cuello:SMR" in txt and "TESIS CAMBIADA" in txt
