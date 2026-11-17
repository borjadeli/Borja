"""Research Queue (doc 85 F2): cola única con prioridad + dedup/consolidación."""
from backend.agentes.research_queue import ResearchQueue


def test_encolar_y_prioridad(tmp_path):
    q = ResearchQueue(tmp_path / "q.json")
    q.encolar("OKLO", origen="PM", prioridad="P2", motivo="posible sustituto")
    q.encolar("MP", origen="POSICION_EVENTO", prioridad="P0", motivo="8-K material")
    q.encolar("VST", origen="OPERADOR", prioridad="P1")
    pend = q.pendientes()
    assert [r.ticker for r in pend] == ["MP", "VST", "OKLO"]      # P0 < P1 < P2


def test_dedup_consolida_origen_y_sube_prioridad(tmp_path):
    q = ResearchQueue(tmp_path / "q.json")
    r1 = q.encolar("OKLO", origen="PM", prioridad="P2")
    r2 = q.encolar("OKLO", origen="POSICION_EVENTO", prioridad="P0")   # mismo ticker → consolida
    assert r1.id == r2.id                                          # no se duplica
    assert set(r2.origen) == {"PM", "POSICION_EVENTO"} and r2.prioridad == "P0"   # sube a la más alta
    assert len(q.pendientes()) == 1


def test_marcar_y_persistencia(tmp_path):
    p = tmp_path / "q.json"
    q = ResearchQueue(p)
    req = q.encolar("MP", origen="PM")
    q.marcar(req.id, "HECHO", costo_usd=0.7, resultado={"estado_ficha": "VIGENTE", "zona": "COMPRA"})
    # recargar de disco
    q2 = ResearchQueue(p)
    assert q2.pendientes() == []                                  # ya no está pendiente
    done = next(r for r in q2._reqs if r.id == req.id)
    assert done.estado == "HECHO" and done.resultado["zona"] == "COMPRA" and done.terminado is not None


def test_dedup_no_revive_una_hecha(tmp_path):
    q = ResearchQueue(tmp_path / "q.json")
    req = q.encolar("MP", origen="PM")
    q.marcar(req.id, "HECHO")
    nuevo = q.encolar("MP", origen="OPERADOR")                    # ya HECHA → crea una NUEVA solicitud
    assert nuevo.id != req.id and len(q.pendientes()) == 1
