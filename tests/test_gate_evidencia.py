"""Tests del gate sobre evidencia (doc 22 §3, §8bis): FALSE→no_pasa, UNKNOWN→NO_EVALUABLE,
existencia-abre + tier de magnitud. Snapshots sintéticos (sin LLM)."""
from backend.nucleo.gate_evidencia import evaluar_desde_evidencia


def _f(value, support="DIRECT"):
    return {"value": value, "support_type": support}


def test_todo_ok_pasa_con_tier():
    snap = {"organic_growth_available": _f(True, "DERIVED"),
            "growth_hecho_continuidad": _f("COMMITTED")}
    r = evaluar_desde_evidencia(snap, "Growth")
    assert r["estado"] == "pasa"
    assert r["tier_magnitud"] == 2          # COMMITTED


def test_hecho_false_rechaza():
    # organic explícitamente FALSE (fundado) → no_pasa (rechazo real, no cuarentena)
    snap = {"organic_growth_available": _f(False, "DIRECT"),
            "growth_hecho_continuidad": _f("REALIZED")}
    r = evaluar_desde_evidencia(snap, "Growth")
    assert r["estado"] == "no_pasa"
    assert "organic_growth_available" in r["fallos"]


def test_estructura_unknown_es_no_evaluable():
    # organic no está (UNKNOWN) → NO_EVALUABLE con la pregunta, NO rechazo
    snap = {"growth_hecho_continuidad": _f("VALIDATED")}
    r = evaluar_desde_evidencia(snap, "Growth")
    assert r["estado"] == "NO_EVALUABLE"
    assert any(p["item"] == "organic_growth_available" for p in r["preguntas"])


def test_demanda_unknown_es_no_evaluable():
    # estructura ok pero demanda UNKNOWN → NO_EVALUABLE (cuarentena de AAOI), no rechazo
    snap = {"organic_growth_available": _f(True, "DERIVED")}
    r = evaluar_desde_evidencia(snap, "Growth")
    assert r["estado"] == "NO_EVALUABLE"
    assert any(p["item"] == "growth_hecho_continuidad" for p in r["preguntas"])


def test_demanda_solo_validated_abre_con_tier_bajo():
    # existencia de la relación (True→VALIDATED) ABRE el nodo con el cap más duro (tier 1)
    snap = {"organic_growth_available": _f(True, "DERIVED"),
            "growth_hecho_continuidad": _f(True, "DIRECT")}
    r = evaluar_desde_evidencia(snap, "Growth")
    assert r["estado"] == "pasa"
    assert r["tier_magnitud"] == 1          # VALIDATED: abre pero cap duro


def test_inferred_no_alimenta_hard_item():
    # un hecho INFERRED no cuenta como fundado → el ítem estructural queda NO_EVALUABLE
    snap = {"organic_growth_available": _f(True, "INFERRED"),
            "growth_hecho_continuidad": _f("COMMITTED")}
    r = evaluar_desde_evidencia(snap, "Growth")
    assert r["estado"] == "NO_EVALUABLE"
