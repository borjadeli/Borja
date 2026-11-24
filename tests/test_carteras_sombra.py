"""Tests de carteras sombra (v2 Fase 5). Sin API — precios inyectados."""
from backend.agentes.carteras_sombra import LedgerSombras, SnapshotSombra, pesos_equal_weight


def test_equal_weight():
    assert pesos_equal_weight(["OKLO", "MP"]) == {"OKLO": 0.5, "MP": 0.5}
    assert pesos_equal_weight([]) == {}


def test_curva_encadena_retorno_ponderado(tmp_path):
    ld = LedgerSombras(path=tmp_path / "s.jsonl")
    # pm: 3% OKLO; OKLO sube 10% entre ciclos → equity +0.3%
    ld.registrar(SnapshotSombra(fecha="2026-10-27", cartera="pm", pesos={"OKLO": 0.03},
                                precios={"OKLO": 26.5}))
    ld.registrar(SnapshotSombra(fecha="2026-11-03", cartera="pm", pesos={"OKLO": 0.03},
                                precios={"OKLO": 29.15}))   # +10%
    curva = ld.curva("pm")
    assert curva[0] == ("2026-10-27", 1.0)
    assert abs(curva[1][1] - (1 + 0.03 * 0.10)) < 1e-6      # caja rinde 0


def test_curva_etf_full_weight(tmp_path):
    ld = LedgerSombras(path=tmp_path / "s.jsonl")
    ld.registrar(SnapshotSombra(fecha="2026-10-27", cartera="spy", pesos={"SPY": 1.0}, precios={"SPY": 600}))
    ld.registrar(SnapshotSombra(fecha="2026-11-03", cartera="spy", pesos={"SPY": 1.0}, precios={"SPY": 606}))
    assert abs(ld.curva("spy")[-1][1] - 1.01) < 1e-6        # +1%


def test_guard_descarta_print_malo(tmp_path):
    # un print corrupto (ITA $213→$71, split fantasma) NO debe corromper el índice: la pata se descarta → la
    # curva se queda en el nivel previo en vez de un falso −66% (visto en vivo 2026-11-18).
    ld = LedgerSombras(path=tmp_path / "s.jsonl")
    ld.registrar(SnapshotSombra(fecha="2026-11-04", cartera="etf_ita", pesos={"ITA": 1.0}, precios={"ITA": 213.70}))
    ld.registrar(SnapshotSombra(fecha="2026-11-13", cartera="etf_ita", pesos={"ITA": 1.0}, precios={"ITA": 71.73}))
    ld.registrar(SnapshotSombra(fecha="2026-11-16", cartera="etf_ita", pesos={"ITA": 1.0}, precios={"ITA": 71.51}))
    idx = ld.curva("etf_ita")[-1][1]
    assert idx > 0.9      # NO el 0.33 corrupto: el salto −66% se descartó


def test_guard_respeta_movimiento_real_grande(tmp_path):
    # un movimiento real dentro del umbral (p.ej. −40% de un small-cap) SÍ cuenta (no sobre-filtra)
    ld = LedgerSombras(path=tmp_path / "s.jsonl")
    ld.registrar(SnapshotSombra(fecha="2026-11-04", cartera="pm", pesos={"ACHR": 1.0}, precios={"ACHR": 10.0}))
    ld.registrar(SnapshotSombra(fecha="2026-11-13", cartera="pm", pesos={"ACHR": 1.0}, precios={"ACHR": 6.5}))
    assert abs(ld.curva("pm")[-1][1] - 0.65) < 1e-6      # −35% real pasa


def test_registrar_ciclo_crea_las_carteras_estandar(tmp_path):
    ld = LedgerSombras(path=tmp_path / "s.jsonl")
    ld.registrar_ciclo("2026-10-28", pm_pesos={"OKLO": 0.03}, pass_nombres=["OKLO", "ACHR"],
                       precios={"OKLO": 26.5, "ACHR": 12.0, "SMH": 300, "SPY": 600,
                                "URA": 40, "ITA": 180, "COPX": 50})
    cs = ld.carteras()
    assert "pm" in cs and "ew_pass" in cs and "spy" in cs and "etf_smh" in cs
    # ew_pass = equal weight de OKLO/ACHR
    ew = [s for s in ld._snapshots("ew_pass")][0]
    assert ew.pesos == {"OKLO": 0.5, "ACHR": 0.5}


def test_resumen_indices(tmp_path):
    ld = LedgerSombras(path=tmp_path / "s.jsonl")
    ld.registrar(SnapshotSombra(fecha="a", cartera="pm", pesos={"X": 1.0}, precios={"X": 100}))
    ld.registrar(SnapshotSombra(fecha="b", cartera="pm", pesos={"X": 1.0}, precios={"X": 120}))
    assert abs(ld.resumen()["pm"] - 1.2) < 1e-6


def test_p1_4_pm_solo_en_zona_excluye_fuera_de_zona(tmp_path):
    from backend.agentes.carteras_sombra import LedgerSombras
    led = LedgerSombras(tmp_path / "s.jsonl")
    led.registrar_ciclo("2026-11-24", pm_pesos={"MP": 0.10, "OKLO": 0.05},
                        pass_nombres=["MP", "OKLO"], precios={"MP": 50.0, "OKLO": 20.0},
                        etfs={}, fuera_de_zona={"OKLO"})
    assert "pm" in led.carteras() and "pm_solo_en_zona" in led.carteras()
    solo = led._snapshots("pm_solo_en_zona")[-1]
    assert "OKLO" not in solo.pesos and solo.pesos.get("MP") == 0.10   # la entrada fuera de zona queda afuera
