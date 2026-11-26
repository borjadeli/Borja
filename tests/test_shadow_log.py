"""P1 (doc 91 §8) — registro de decisión en sombra (IA2 §3.5/3.6 + review-2). Determinista."""
from types import SimpleNamespace

import pytest

from backend.agentes.shadow_log import (categoria_motivo, construir_shadow_decision, registrar_corrida,
                                         registrar_shadow, resumen_sombra)

def _ver(permiso, missing=(), arq="ciclica", cap=0.0, motivos=("m",), liga="tier"):
    return SimpleNamespace(arquetipo=arq, banda=None, tier="CORE", cap=cap, liga=liga, permiso=permiso,
                           motivos=list(motivos), missing_fields=list(missing))

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


# ── review-2: categoría de motivo, ACHICA por tamaño, invariante registros==decisiones ──
@pytest.mark.parametrize("motivo,cat", [
    ("verificación FAIL", "VERIF"),
    ("hecho 'bloqueo_datos' no chequeado", "DATO"),
    ("peso 3% por debajo del mínimo del tier CORE (crea stub)", "IPS"),
    ("B está DOMINADA por A — sin mérito que compensar", "ECONOMIA"),
])
def test_categoria_motivo(motivo, cat):
    assert categoria_motivo(motivo) == cat


def test_achica_cuando_p1_ejecuta_pero_el_cap_es_menor_que_el_peso_propuesto():
    # P1 deja EJECUTAR pero con un cap por debajo de lo que pedía el PM → cambia (achica), no es "igual".
    r = construir_shadow_decision(ciclo="c", ticker="x", accion_pm="aumentar",
                                  veredicto=_ver("EJECUTAR", cap=0.06), peso_propuesto=0.10)
    assert r["tipo_cambio"] == "ACHICA" and r["cambiaria_la_decision"] is True
    assert r["shadow"]["peso_permitido"] == 0.06 and r["peso_propuesto"] == 0.10


def test_ejecuta_sin_achicar_no_cambia():
    r = construir_shadow_decision(ciclo="c", ticker="x", accion_pm="aumentar",
                                  veredicto=_ver("EJECUTAR", cap=0.10), peso_propuesto=0.07)
    assert r["tipo_cambio"] is None and r["cambiaria_la_decision"] is False


def test_dedup_key_y_registrar_corrida_invariante(tmp_path):
    p = tmp_path / "s.jsonl"
    recs = [construir_shadow_decision(ciclo="c", ticker=t, accion_pm="abrir", veredicto=_ver("BLOQUEAR", ["x"]),
                                      peso_propuesto=0.05) for t in ("A", "B", "C")]
    assert recs[0]["dedup_key"] == "c|A|p1-v1"
    escritos = registrar_corrida(recs, path=p)
    assert escritos == 3 and len(p.read_text().splitlines()) == 3


def test_gate0_dryrun_corre_sin_autoridad():
    # smoke: el ensayo en seco completo corre $0 y respeta fail-closed + atomicidad + invariante del log.
    from ops.gate0_dryrun import main
    assert main() == 0
