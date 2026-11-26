"""P1 (doc 91 §8) — registro de decisión en sombra (IA2 §3.5/3.6). Determinista."""
from types import SimpleNamespace

from backend.agentes.shadow_log import construir_shadow_decision, registrar_shadow, resumen_sombra

def _ver(permiso, missing=(), arq="ciclica"):
    return SimpleNamespace(arquetipo=arq, banda=None, tier="CORE", cap=0.0, permiso=permiso, motivos=["m"], missing_fields=list(missing))

def test_cambiaria_cuando_el_pm_quiere_mover_y_p1_bloquea():
    r = construir_shadow_decision(ciclo="2026-11-25", ticker="exe", accion_pm="aumentar", veredicto=_ver("BLOQUEAR", ["banda"]))
    assert r["cambiaria_la_decision"] is True and r["ticker"] == "EXE"
    assert r["data_quality"]["missing_fields"] == ["banda"]

def test_no_cambia_si_mantener():
    r = construir_shadow_decision(ciclo="c", ticker="wolf", accion_pm="mantener", veredicto=_ver("EJECUTAR"))
    assert r["cambiaria_la_decision"] is False

def test_no_cambia_si_el_pm_mueve_y_p1_ejecuta():
    r = construir_shadow_decision(ciclo="c", ticker="x", accion_pm="salir", veredicto=_ver("EJECUTAR"))
    assert r["cambiaria_la_decision"] is False

def test_persistencia_y_resumen(tmp_path):
    p = tmp_path / "s.jsonl"
    registrar_shadow(construir_shadow_decision(ciclo="c", ticker="A", accion_pm="aumentar", veredicto=_ver("BLOQUEAR", ["x"])), path=p)
    registrar_shadow(construir_shadow_decision(ciclo="c", ticker="B", accion_pm="mantener", veredicto=_ver("EJECUTAR")), path=p)
    import json
    recs = [json.loads(l) for l in p.read_text().splitlines()]
    res = resumen_sombra(recs)
    assert res["n"] == 2 and res["bloqueadas_%"] == 50.0 and res["cambiaria_%"] == 50.0
