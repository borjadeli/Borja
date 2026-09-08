"""Ledger de hit-rate del juicio (doc 39 §2.6, Bloque 3.3): registro dedup + achique de presupuesto."""
from backend.nucleo import ledger_juicio as LJ
from backend.nucleo.juicio import Intervencion


def _iv(t, etiqueta="PRIORITY_HIGH", fecha="2026-01-01"):
    return Intervencion(t, etiqueta, fecha, falsador="x", fecha_falsador="2026-06")


def test_registra_solo_intervenciones_reales(tmp_path):
    p = tmp_path / "lj.json"
    ivs = [_iv("A"), _iv("B", "PASS"), _iv("C", "VETO")]      # PASS no es intervención de juicio
    n = LJ.registrar(ivs, precios={"A": 10, "B": 10, "C": 10}, path=p)
    assert n == 2                                            # A (promo) + C (veto), NO B (pass)


def test_dedup(tmp_path):
    p = tmp_path / "lj.json"
    LJ.registrar([_iv("A")], precios={"A": 10}, path=p)
    assert LJ.registrar([_iv("A")], precios={"A": 10}, path=p) == 0


def test_hit_rate_gana_baseline(tmp_path):
    p = tmp_path / "lj.json"
    LJ.registrar([_iv("A"), _iv("B")], precios={"A": 10, "B": 10}, path=p)
    # A subió (promo acertó), B bajó
    m = LJ.hit_rate({"A": 20, "B": 8}, path=p, baseline_ret={"A": 0.0, "B": 0.0})
    assert m["n"] == 2 and m["hit_rate"] == 0.5


def test_achica_presupuesto_si_no_gana(tmp_path):
    p = tmp_path / "lj.json"
    # 8 promos, todas peor que baseline → recomienda achicar presupuesto
    ivs = [_iv(f"T{i}") for i in range(8)]
    LJ.registrar(ivs, precios={f"T{i}": 10 for i in range(8)}, path=p)
    precios_baja = {f"T{i}": 5 for i in range(8)}           # todas bajaron
    m = LJ.hit_rate(precios_baja, path=p, baseline_ret={f"T{i}": 0.5 for i in range(8)})  # baseline habría subido
    assert m["gana_baseline"] == 0.0 and m["recomendacion_presupuesto"] < 3
