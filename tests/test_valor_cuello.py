"""Señal de valor del embudo (r7 §3, doc 78): lo barato dentro de su cuello sube en la fila del deep research."""
from datetime import date

from backend.agentes.embudo import percentiles_valor_por_cuello, ratio_valor, top_por_valor
from backend.agentes.provenance import DataKind, DataPack, DataPoint, Source
from backend.agentes.triage import SenalesTriage, prioridad
from backend.agentes.universo import valor_del_universo


def test_ratio_valor_usa_contratado_mas_revenue():
    # EV 1.6e9 / (valor contratado 4.8e8 + revenue 4e8) = 1.6e9 / 8.8e8
    r = ratio_valor({"enterprise_value": 1.6e9, "valor_contratado_ajustado": 4.8e8, "revenue": 4e8})
    assert r == round(1.6e9 / 8.8e8, 4)


def test_ratio_valor_none_si_pre_revenue_sin_backlog():
    # opción pura: EV presente pero sin contratado ni revenue → sin señal de valor (no se le exige, §6)
    assert ratio_valor({"enterprise_value": 1e9, "valor_contratado_ajustado": None, "revenue": None}) is None


def test_ratio_valor_none_sin_ev():
    assert ratio_valor({"enterprise_value": None, "revenue": 4e8}) is None


def test_percentil_el_mas_barato_es_1():
    ratios = {"A": 2.0, "B": 5.0, "C": 10.0}      # A el más barato
    cuellos = {"A": "nuclear", "B": "nuclear", "C": "nuclear"}
    pct = percentiles_valor_por_cuello(ratios, cuellos)
    assert pct["A"] == 1.0 and pct["C"] == 0.0 and 0 < pct["B"] < 1


def test_percentil_none_si_cuello_de_uno():
    pct = percentiles_valor_por_cuello({"A": 2.0, "B": 3.0}, {"A": "x", "B": "y"})
    assert pct["A"] is None and pct["B"] is None       # cada uno solo en su cuello


def test_percentil_solo_compara_dentro_del_cuello():
    ratios = {"A": 2.0, "B": 9.0, "C": 1.0, "D": 8.0}
    cuellos = {"A": "nuclear", "B": "nuclear", "C": "semis", "D": "semis"}
    pct = percentiles_valor_por_cuello(ratios, cuellos)
    assert pct["A"] == 1.0 and pct["B"] == 0.0       # dentro de nuclear
    assert pct["C"] == 1.0 and pct["D"] == 0.0       # dentro de semis


def test_prioridad_sube_con_valor_barato():
    base = SenalesTriage(dias_desde_dossier=30, hechos_nuevos=0, dias_a_evento=None,
                         precio_vs_tesis_pct=None)
    barato = SenalesTriage(dias_desde_dossier=30, hechos_nuevos=0, dias_a_evento=None,
                           precio_vs_tesis_pct=None, valor_percentil_cuello=0.9)
    assert prioridad(barato, 0.0) == prioridad(base, 0.0) + 1


def test_prioridad_no_sube_con_valor_caro():
    base = SenalesTriage(dias_desde_dossier=30, hechos_nuevos=0, dias_a_evento=None, precio_vs_tesis_pct=None)
    caro = SenalesTriage(dias_desde_dossier=30, hechos_nuevos=0, dias_a_evento=None,
                         precio_vs_tesis_pct=None, valor_percentil_cuello=0.3)
    assert prioridad(caro, 0.0) == prioridad(base, 0.0)


def test_valor_del_universo_integra_lente_y_cuello():
    # dos nombres del mismo cuello: A más barato (EV/(contratado+rev) menor) → percentil 1.0.
    def _pack(tk):
        datos = {
            "A": {"enterprise_value": 1e9, "revenue": 5e8, "valor_contratado_ajustado": 5e8},   # ratio 1.0
            "B": {"enterprise_value": 3e9, "revenue": 5e8, "valor_contratado_ajustado": None},   # ratio 6.0
        }[tk]
        pts = [DataPoint(entity=tk, metric=m, value=v, unit="USD", kind=DataKind.DERIVED,
                         source=Source(name="scripted"), known_at=date(2026, 1, 1))
               for m, v in datos.items() if v is not None]
        return DataPack(ticker=tk, as_of=date(2026, 1, 1), puntos=pts)

    cuellos = {"A": "nuclear", "B": "nuclear"}
    pct, met, ratios, _c = valor_del_universo(["A", "B"], pack_fn=_pack, cuello_fn=lambda tk: cuellos[tk])
    assert ratios["A"] == 1.0 and ratios["B"] == 6.0
    assert pct["A"] == 1.0 and pct["B"] == 0.0
    assert met["A"]["enterprise_value"] == 1e9


def test_valor_del_universo_best_effort_si_pack_falla():
    def _pack(tk):
        raise RuntimeError("sin red")
    pct, met, ratios, _c = valor_del_universo(["X"], pack_fn=_pack, cuello_fn=lambda tk: "c")
    assert ratios["X"] is None and met["X"] == {} and pct["X"] is None


def test_top_por_valor_ordena_barato_primero():
    ratios = {"A": 2.0, "B": 5.0, "C": 10.0}
    cuellos = {k: "nuclear" for k in ratios}
    met = {"A": {"enterprise_value": 2e9, "revenue": 1e9, "valor_contratado_ajustado": None}}
    top = top_por_valor(ratios, cuellos, met, n=2)
    assert [f["ticker"] for f in top] == ["A", "B"]      # más barato primero
    assert top[0]["percentil_valor"] == 1.0
