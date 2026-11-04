"""Barrido de discovery (ops.cola_propuestas): cursor que avanza + freno por tope de gasto. Sin API ni DB
(monkeypatch de _ctx y _una_corrida: acá se testea el LOOP, no los agentes — esos están en test_descubrimiento)."""
import ops.cola_propuestas as op


def _ctx_fake(n_nodos=5):
    return {"nodos_mapa": [{"nombre": f"cuello{i}", "info": f"cuello{i}"} for i in range(n_nodos)]}


def test_cursor_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(op, "_CURSOR_PATH", tmp_path / "cursor.json")
    assert op._leer_cursor() == 0            # sin archivo → 0
    op._guardar_cursor(7)
    assert op._leer_cursor() == 7


def test_barrer_avanza_cursor_y_envuelve(tmp_path, monkeypatch):
    monkeypatch.setattr(op, "_CURSOR_PATH", tmp_path / "cursor.json")
    monkeypatch.setattr(op, "_ctx", lambda: _ctx_fake(5))
    corridas = []
    monkeypatch.setattr(op, "_una_corrida", lambda ctx, foco, mx: (corridas.append(foco) or
                        {"empresas": [], "cuellos": [], "descartes": [], "costo": 0.1, "busquedas": 1}))
    op._guardar_cursor(3)
    op._barrer(4, max_prop=2, tope_usd=10.0)         # desde #3, 4 cuellos de 5 → 3,4,0,1 → cursor queda en 2
    assert corridas == ["cuello3", "cuello4", "cuello0", "cuello1"]
    assert op._leer_cursor() == 2


def test_barrer_frena_por_tope(tmp_path, monkeypatch):
    monkeypatch.setattr(op, "_CURSOR_PATH", tmp_path / "cursor.json")
    monkeypatch.setattr(op, "_ctx", lambda: _ctx_fake(10))
    corridas = []
    monkeypatch.setattr(op, "_una_corrida", lambda ctx, foco, mx: (corridas.append(foco) or
                        {"empresas": [], "cuellos": [], "descartes": [], "costo": 0.8, "busquedas": 5}))
    op._barrer(10, max_prop=2, tope_usd=2.0)          # cada corrida $0.8 → frena tras 3 (2.4 ≥ 2.0 antes de la 4ª)
    assert len(corridas) == 3                          # 0,1,2 → tras la 3ª gastado=2.4 ≥ tope → no corre la 4ª
    assert op._leer_cursor() == 3                      # cursor avanzó solo por lo efectivamente corrido