"""Verificador ciego (doc 83 F3): reconciliación determinista de la extracción independiente vs el dossier."""
import json

from backend.agentes.base import FakeUsage, ScriptedLLM, resp_texto
from backend.agentes.verificador_ciego import (extraer_desde_edgar, reconciliar, referencia_de_ficha,
                                               verificar_ciego, verificar_decision)


def test_pass_cuando_todo_concilia():
    ref = {"caja": 1.33e9, "deuda_total": 1.0e9, "acciones_basicas": 178e6, "n_instrumentos": 3}
    ciego = {"caja": 1.34e9, "deuda_total": 0.98e9, "acciones_basicas": 178.5e6, "n_instrumentos": 3}  # <5%
    v, discs = reconciliar(ciego, ref)
    assert v == "PASS" and discs == []


def test_fail_por_discrepancia_numerica_material():
    # el caso VST: el motor dice deuda $13,4B, la fuente primaria $19,6B → 32% > 5% → FAIL material
    ref = {"caja": 1e9, "deuda_total": 13.4e9, "acciones_basicas": 350e6, "n_instrumentos": 0}
    ciego = {"caja": 1e9, "deuda_total": 19.6e9, "acciones_basicas": 350e6, "n_instrumentos": 0}
    v, discs = reconciliar(ciego, ref)
    assert v == "FAIL"
    d = next(x for x in discs if x.campo == "deuda_total")
    assert d.severidad == "material" and d.tipo == "numerica"


def test_fail_por_instrumentos_faltantes():
    # el caso MP: el dossier no inventarió converts/preferida/warrant (0) pero el ciego encontró 3 → presencia
    ref = {"caja": 1.3e9, "deuda_total": 1e9, "acciones_basicas": 178e6, "n_instrumentos": 0}
    ciego = {"caja": 1.3e9, "deuda_total": 1e9, "acciones_basicas": 178e6, "n_instrumentos": 3}
    v, discs = reconciliar(ciego, ref)
    assert v == "FAIL"
    assert any(d.campo == "n_instrumentos" and d.severidad == "material" for d in discs)


def test_fail_por_deuda_nueva_posterior_no_reflejada():
    # el caso IESC/DBM: el ciego no pudo leer el balance (nums null) PERO capturó $525M de deuda nueva en un 8-K
    # posterior → la referencia ($0) no la refleja → FAIL temporal (balance stale), aunque los numéricos sean null.
    ref = {"caja": 77.3e6, "deuda_total": 0.0, "acciones_basicas": 19.9e6, "n_instrumentos": 0}
    ciego = {"caja": None, "deuda_total": None, "acciones_basicas": None, "n_instrumentos": None,
             "deuda_nueva_posterior": 525e6, "adquisicion_posterior": True}
    v, discs = reconciliar(ciego, ref)
    assert v == "FAIL"
    assert any(d.campo == "deuda_nueva_posterior" and d.severidad == "material" for d in discs)
    assert any(d.campo == "adquisicion_posterior" for d in discs)


def test_review_por_dato_faltante():
    ref = {"caja": 1e9, "deuda_total": 1e9, "acciones_basicas": 178e6, "n_instrumentos": 2}
    ciego = {"caja": 1e9, "deuda_total": None, "acciones_basicas": 178e6, "n_instrumentos": 2}  # no extrajo deuda
    v, discs = reconciliar(ciego, ref)
    assert v == "REVIEW" and any(d.tipo == "incompleta" for d in discs)


def test_fail_premisa_no_sostenida():
    ref = {"caja": 1e9, "deuda_total": 1e9, "acciones_basicas": 178e6, "n_instrumentos": 0, "premisa": "tiene el contrato"}
    ciego = {"caja": 1e9, "deuda_total": 1e9, "acciones_basicas": 178e6, "n_instrumentos": 0,
             "premisa_sostenida": False, "premisa_nota": "no hay 8-K del contrato"}
    v, discs = reconciliar(ciego, ref)
    assert v == "FAIL" and any(d.campo == "premisa_tesis" for d in discs)


class _F:
    def __init__(self, tipo, items, url):
        self.tipo, self.items, self.fecha, self.url = tipo, items, "2026-11-01", url


def test_extractor_ciego_con_llm_scripted():
    # el extractor baja filings (inyectados) y un modelo (scripted) extrae los hechos SIN ver el dossier
    payload = {"caja": 1.33e9, "deuda_total": 1.0e9, "acciones_basicas": 178e6, "n_instrumentos": 3,
               "instrumentos_nota": "conv 2030, preferida DoD, warrant", "premisa_sostenida": True,
               "premisa_nota": "el 10-Q confirma el PPA", "eventos_posteriores": "ninguno"}
    cli = ScriptedLLM([resp_texto(json.dumps(payload), FakeUsage(input_tokens=5000, output_tokens=200))])
    hechos, costo = extraer_desde_edgar(
        "MP", "2026-11-16", premisa_pregunta="¿tiene el acuerdo con el DoD?", cliente=cli,
        filings_fn=lambda tk: [_F("10-Q", "", "u-10q"), _F("8-K", "1.01", "u-8k")],
        fetch_fn=lambda url: "texto del filing")
    assert hechos["acciones_basicas"] == 178e6 and hechos["n_instrumentos"] == 3 and costo >= 0.0


def test_verificar_decision_solo_sobre_aumentos():
    # el canal ciego corre SOLO sobre los nombres a comprar; devuelve {ticker: VerificacionCiega} para el gate.
    from backend.agentes.ficha import Ficha, Instrumento

    def _ficha(tk, n_instr):
        return Ficha(ticker=tk, nivel="BANCA", clase_d4="satelite", cuello=None, cobertura_datos="FULL",
                     tesis_resumen="proveedor del cuello", dossier_id=None, visto_hasta=None, estado="VIGENTE",
                     tope_duro=None, escenarios=[], dilucion_total=0.0, deuda_neta=1e9, acciones=178e6, caja=0.3e9,
                     instrumentos=[Instrumento(f"i{k}", "convertible") for k in range(n_instr)])
    fichas = {"MP": _ficha("MP", 0), "VST": _ficha("VST", 2)}   # MP inventario vacío (el dossier no los puso)
    # extractor stub: para MP el ciego encuentra 3 instrumentos (el dossier decía 0) → FAIL
    def _extractor(tk, cutoff, premisa):
        n = {"MP": 3, "VST": 2}[tk]
        return {"caja": 0.3e9, "deuda_total": 1.3e9, "acciones_basicas": 178e6, "n_instrumentos": n}, 0.04
    out = verificar_decision(["MP"], fichas, extractor=_extractor)      # solo MP (el aumento)
    assert set(out) == {"MP"} and out["MP"].veredicto == "FAIL"         # 3≠0 → FAIL
    assert referencia_de_ficha(fichas["VST"])["n_instrumentos"] == 2    # referencia bien armada desde la ficha


def test_orquestacion_inyectando_extractor():
    # verificar_ciego NO le pasa los valores de referencia al extractor (anti-anclaje): el extractor solo ve ticker+cutoff
    visto = {}
    def _extraer(ticker, cutoff):
        visto["args"] = (ticker, cutoff)
        return {"caja": 1.3e9, "deuda_total": 1e9, "acciones_basicas": 178e6, "n_instrumentos": 3}, 0.02
    ref = {"caja": 1.3e9, "deuda_total": 1e9, "acciones_basicas": 178e6, "n_instrumentos": 0}
    vc = verificar_ciego("MP", ref, extraer_fn=_extraer, cutoff="2026-11-16")
    assert visto["args"] == ("MP", "2026-11-16")              # el extractor NO recibió la referencia
    assert vc.veredicto == "FAIL" and vc.confiable is False and vc.costo_usd == 0.02
