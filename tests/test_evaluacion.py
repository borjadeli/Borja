"""Evaluación NO-COMPENSATORIA con scoring (doc 39 §2.1, rebalanceo 2026-08). Sin LLM.
El veto de SUPERVIVENCIA es la única exclusión dura; un CRÍTICO de 'no funciona' pisa el score a C
pero NO excluye (candidato PROBE); UNKNOWN ≠ negativo."""
from backend.nucleo.evaluacion import (
    Banda, Pilar, asignar_tier, evaluar, clave_prioridad,
)


def _p(nombre, banda, confianza="suficiente", veto=False):
    return Pilar(nombre=nombre, banda=banda, confianza=confianza, es_veto_supervivencia=veto)


def _tres(d, e, ej, **kw):
    return [_p("demanda_cuello", d, kw.get("cd", "suficiente")),
            _p("economia", e), _p("ejecucion", ej, veto=kw.get("veto_ej", False))]


def test_tier_a_todo_fuerte():
    tier, lim, _, veto = asignar_tier(_tres(Banda.FUERTE, Banda.FUERTE, Banda.SUFICIENTE))
    assert tier == "A" and lim is None and veto is False


def test_veto_supervivencia_excluye():
    # ejecución CRÍTICA marcada como veto de supervivencia (restatement) → C + veto=True (única exclusión dura)
    tier, lim, _, veto = asignar_tier(_tres(Banda.FUERTE, Banda.FUERTE, Banda.CRITICO, veto_ej=True))
    assert tier == "C" and lim == "ejecucion" and veto is True


def test_critico_no_supervivencia_NO_excluye():
    # economía CRÍTICA (unit economics rotas, 'no va a funcionar') SIN veto → C DÉBIL pero candidato (veto=False)
    tier, lim, motivo, veto = asignar_tier(_tres(Banda.FUERTE, Banda.CRITICO, Banda.SUFICIENTE))
    assert tier == "C" and veto is False and lim == "economia"
    assert "PROBE" in motivo or "no va a funcionar" in motivo


def test_elegible_es_sobrevivir_no_score_alto():
    # un tier C sin veto SIGUE siendo elegible (sobrevivió) — gates→scoring
    ev = evaluar("X", _tres(Banda.FUERTE, Banda.CRITICO, Banda.SUFICIENTE))
    assert ev.tier == "C" and ev.elegible is True
    # con veto de supervivencia → NO elegible
    ev2 = evaluar("Y", _tres(Banda.FUERTE, Banda.FUERTE, Banda.CRITICO, veto_ej=True))
    assert ev2.tier == "C" and ev2.elegible is False


def test_un_pilar_debil_es_b():
    tier, lim, _, _ = asignar_tier(_tres(Banda.FUERTE, Banda.SUFICIENTE, Banda.DEBIL))
    assert tier == "B" and lim == "ejecucion"


def test_unknown_no_es_negativo():
    # un pilar FUERTE pero confianza insuficiente (UNKNOWN) → cuenta SUFICIENTE, no CRÍTICO → sigue elegible
    pilares = _tres(Banda.FUERTE, Banda.FUERTE, Banda.SUFICIENTE)
    pilares[1].confianza = "insuficiente"
    tier, _, _, veto = asignar_tier(pilares)
    assert tier == "B" and veto is False


def test_cobertura_incompleta_no_llega_a_a():
    tier, _, _, veto = asignar_tier([_p("demanda_cuello", Banda.FUERTE), _p("economia", Banda.FUERTE)])
    assert tier == "B" and veto is False


def test_prioridad_por_delta_dentro_del_tier():
    a_sube = evaluar("X", _tres(Banda.FUERTE, Banda.FUERTE, Banda.SUFICIENTE), delta="sube")
    a_estable = evaluar("Y", _tres(Banda.FUERTE, Banda.FUERTE, Banda.SUFICIENTE), delta="estable")
    b_sube = evaluar("Z", _tres(Banda.FUERTE, Banda.SUFICIENTE, Banda.DEBIL), delta="sube")
    orden = sorted([a_estable, b_sube, a_sube], key=clave_prioridad)
    assert [e.ticker for e in orden] == ["X", "Y", "Z"]
