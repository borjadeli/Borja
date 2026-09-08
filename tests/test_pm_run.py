"""pm_run (productor del LibroPM): arma items, corre orquestar_pm, serializa/persiste. Sin API ni EDGAR."""
import json

from backend.nucleo import juicio
from backend.nucleo.juicio import Banda
from backend.nucleo.juicio_llm import MemoJuicio
from backend.seleccion import pm_run


class _Cand:
    def __init__(self, ticker, cap):
        self.ticker, self.cap = ticker, cap


class _Hoja:
    def __init__(self, ticker):
        self.ticker = ticker
        self.a_carril_burden = False
        self.size_burden = None
        self.flags = []


def _judge_stub(ticker, ev, **kw):
    # PM promueve al techo si el ticker es RBRK; PASS conservador en el resto
    if ticker == "RBRK":
        return MemoJuicio(ticker=ticker, etiqueta="PRIORITY_HIGH", bull="b", bear="be",
                          falsador="si pierde cliente ancla", fecha_falsador="2026-12-31", razon="calidad")
    return MemoJuicio(ticker=ticker, etiqueta="PASS", valido=True)


def test_correr_produce_libropm_sin_api(monkeypatch):
    items = {"RBRK": (_Cand("RBRK", 0.08), _Hoja("RBRK")), "MP": (_Cand("MP", 0.06), _Hoja("MP"))}
    monkeypatch.setattr(pm_run, "construir_item", lambda s, t: items.get(t))
    libro = pm_run.correr(None, ["RBRK", "MP"], "2026-09-08", judge=_judge_stub, usar_web=False)
    sizes = libro.sizes()
    assert sizes["RBRK"] == 0.08                 # PRIORITY_HIGH → sube al techo (dentro de banda)
    assert sizes["MP"] <= 0.04 + 1e-9            # PASS → se queda en la base (piso)
    assert libro.promos_usadas == 1


def test_serializar_incluye_memo_auditable():
    memo = MemoJuicio(ticker="RBRK", etiqueta="PRIORITY_HIGH", bull="b", bear="be",
                      falsador="X", fecha_falsador="2026-12-31", fuentes=[{"fuente": "10-Q", "hecho": "NRR 120%"}],
                      web_searches=3)
    iv = juicio.Intervencion(ticker="RBRK", etiqueta="PRIORITY_HIGH", fecha="2026-09-08", memo_hash="abc123")
    from backend.nucleo.flujo_pm import DecisionPM, LibroPM
    d = DecisionPM(ticker="RBRK", etiqueta="PRIORITY_HIGH", banda=Banda(0.0, 0.04, 0.08),
                   size_final=0.08, memo=memo, intervencion=iv, motivo="promovido")
    blob = pm_run.serializar(LibroPM(decisiones=[d], promos_usadas=1, presupuesto=3, fecha="2026-09-08"))
    assert blob["n"] == 1 and blob["promos_usadas"] == 1
    dec = blob["decisiones"][0]
    assert dec["ticker"] == "RBRK" and dec["promovido"] is True
    assert dec["falsador"] == "X" and dec["fuentes"][0]["hecho"] == "NRR 120%" and dec["web_searches"] == 3
    # serializable a JSON de verdad
    assert json.loads(json.dumps(blob))["decisiones"][0]["memo_hash"] == "abc123"


def test_persistir_y_cargar(tmp_path):
    from backend.nucleo.flujo_pm import LibroPM
    p = tmp_path / "libro_pm.json"
    pm_run.persistir(LibroPM(decisiones=[], promos_usadas=0, presupuesto=3, fecha="2026-09-08"), path=p)
    assert pm_run.cargar(p)["fecha"] == "2026-09-08"
    assert pm_run.cargar(tmp_path / "no_existe.json") is None
