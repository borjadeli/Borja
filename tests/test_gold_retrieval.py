"""Tests del harness de medición del retrieval (Bloque 0, gold_retrieval; diseño IA1+IA2).

Sin red, sin LLM: verifica la MECÁNICA de la métrica revisada — recall a presupuesto, CAUSA del
miss (A/B/C/D), grupos OR/AND, período/answerability y el negativo-en-denominador — con corpus y
regiones sintéticas. NO fija el recall del gold real (ese se mueve a propósito al tunear en 0c).
"""
import pytest

from backend.nucleo import gold_retrieval as G
from backend.nucleo.gold_retrieval import (
    DERIVABLE, EIGHTK, NOT_DISCLOSED, PRIMARY, STATED_SINGLE, GoldCase, medir_caso,
)

GOLD_TXT = "revenues from Digicomm were approximately $147.0 million, representing 42.8%"
TEXTO = f"boilerplate previo bla bla {GOLD_TXT} y mas texto de relleno al final aca"
OFF = TEXTO.find(GOLD_TXT)
SPAN = (OFF, OFF + len(GOLD_TXT))


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "CORPUS_DIR", tmp_path)
    (tmp_path / "AAOI_ACC.html").write_text(TEXTO, encoding="utf-8")
    return tmp_path


def _regiones(capadas, sincap=None, pos=None):
    """Monkeypatch de las regiones para forzar HIT/MISS deterministas (ignora anchors reales)."""
    def fake(texto, anchors):
        return capadas, (sincap if sincap is not None else capadas), (pos if pos is not None else [OFF])
    return fake


def _caso(**kw):
    base = dict(ticker="AAOI", accession="ACC", fact_key="demanda_realizada", location=PRIMARY,
                answerability=STATED_SINGLE, gold_answer=True, evidence=[[GOLD_TXT]])
    base.update(kw)
    return GoldCase(**base)


def test_hit_cuando_una_region_capada_cubre_el_span(entorno, monkeypatch):
    monkeypatch.setattr(G, "analisis_regiones", _regiones([(0, len(TEXTO))]))
    r = medir_caso(_caso())
    assert r.hit is True and r.motivo == "HIT" and r.evaluable


def test_region_precision_penaliza_ventanas_ruidosas(entorno, monkeypatch):
    # 4 regiones, solo 1 contiene el span gold → precisión 0.25 (recall no es gratis)
    ruido = [(0, 3), (4, 7), (8, 11), (OFF - 1, SPAN[1] + 1)]
    monkeypatch.setattr(G, "analisis_regiones", _regiones(ruido))
    r = medir_caso(_caso())
    assert r.hit is True and r.region_precision == 0.25


def test_miss_c_cuando_sincap_cubre_pero_capada_no(entorno, monkeypatch):
    # el span solo lo cubre la región sin_cap → lo tiró el cap de max_regs
    monkeypatch.setattr(G, "analisis_regiones",
                        _regiones(capadas=[(0, 5)], sincap=[(0, 5), (OFF - 1, SPAN[1] + 1)], pos=[OFF]))
    r = medir_caso(_caso())
    assert r.hit is False and r.motivo == "MISS_C_CAP"


def test_miss_b_cuando_la_ventana_no_cubre_todo_el_span(entorno, monkeypatch):
    # hay región cerca pero solapa parcial (no cubre el span completo) → ventana ±w corta
    monkeypatch.setattr(G, "analisis_regiones",
                        _regiones(capadas=[(OFF - 2, OFF + 3)], sincap=[(OFF - 2, OFF + 3)], pos=[OFF]))
    r = medir_caso(_caso())
    assert r.hit is False and r.motivo == "MISS_B_SPAN_TRUNC"


def test_miss_a_cuando_ningun_anchor_cerca(entorno, monkeypatch):
    # región lejana, sin overlap, y las posiciones de anchor lejos del span → vocabulario incompleto
    monkeypatch.setattr(G, "analisis_regiones",
                        _regiones(capadas=[(0, 5)], sincap=[(0, 5)], pos=[0]))
    r = medir_caso(_caso())
    assert r.hit is False and r.motivo == "MISS_A_NO_ANCHOR"


def test_miss_a_cuando_no_hay_regiones(entorno, monkeypatch):
    monkeypatch.setattr(G, "analisis_regiones", _regiones(capadas=[], sincap=[], pos=[]))
    r = medir_caso(_caso())
    assert r.hit is False and r.motivo == "MISS_A_NO_ANCHOR"


def test_miss_d_cuando_el_verbatim_no_esta_en_el_texto(entorno):
    # el span etiquetado no aparece en el texto extraído → perdido en extracción / drift
    r = medir_caso(_caso(evidence=[["este pasaje no existe en el filing congelado"]]))
    assert r.hit is False and r.motivo == "MISS_D_LOST"


def test_distractor_en_ventana(entorno, monkeypatch):
    dist = "boilerplate previo"
    monkeypatch.setattr(G, "analisis_regiones", _regiones([(0, len(TEXTO))]))
    r = medir_caso(_caso(distractors=[dist]))
    assert r.distractor_en_ventana is True


def test_or_una_alternativa_cubierta_alcanza(entorno, monkeypatch):
    # OR: dos alternativas, solo la 2ª está en el texto y cubierta → HIT
    monkeypatch.setattr(G, "analisis_regiones", _regiones([(0, len(TEXTO))]))
    r = medir_caso(_caso(evidence=[["frase alternativa ausente"], [GOLD_TXT]]))
    assert r.hit is True


def test_and_dos_spans_requeridos_uno_sin_cubrir_no_es_hit(entorno, monkeypatch):
    # AND: alternativa con 2 spans; la región solo cubre el 1º → no HIT
    s2 = "mas texto de relleno"
    monkeypatch.setattr(G, "analisis_regiones", _regiones([(OFF - 1, SPAN[1] + 1)]))
    r = medir_caso(_caso(evidence=[[GOLD_TXT, s2]]))
    assert r.hit is False


def test_no_evaluable_derivable(entorno):
    # el % hay que calcularlo → no es problema de retrieval, no entra al denominador
    r = medir_caso(_caso(answerability=DERIVABLE))
    assert r.evaluable is False and r.motivo == DERIVABLE


def test_no_evaluable_si_no_es_primary(entorno):
    r = medir_caso(_caso(location=EIGHTK))
    assert r.evaluable is False and r.motivo.startswith("COVERAGE_")


def test_negativo_explicito_es_evaluable(entorno, monkeypatch):
    # NOT_DISCLOSED explícito ("no customer > 10%") SÍ cuenta: mide falsos positivos
    monkeypatch.setattr(G, "analisis_regiones", _regiones([(0, len(TEXTO))]))
    r = medir_caso(_caso(answerability=NOT_DISCLOSED, gold_answer=False))
    assert r.evaluable is True and r.hit is True


def test_case_id_incluye_periodo(entorno):
    c = _caso(period="6mo-2026-06-30")
    assert c.case_id == "AAOI:demanda_realizada:6mo-2026-06-30"


def test_gold_set_real_bien_formado():
    for c in G.GOLD:
        assert c.accession and c.fact_key and c.ticker
        if c.answerability in G._EVALUABLE_ANS and c.location == PRIMARY:
            assert c.evidence, f"{c.case_id}: evaluable sin evidence"
        assert c.split in ("dev", "holdout", "random")
