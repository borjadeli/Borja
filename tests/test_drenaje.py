"""Drenaje de la Research Queue (doc 85 F2): cola → deep → ficha, con presupuesto."""
from backend.agentes.drenaje import drenar
from backend.agentes.research_queue import ResearchQueue


def test_drena_por_prioridad_dentro_de_presupuesto(tmp_path):
    q = ResearchQueue(tmp_path / "q.json")
    q.encolar("MP", origen="POSICION_EVENTO", prioridad="P0")
    q.encolar("OKLO", origen="PM", prioridad="P2")
    q.encolar("VST", origen="OPERADOR", prioridad="P1")
    corridos_tk = []
    def _deep(ticker, *, ciego):
        corridos_tk.append(ticker)
        return {"estado_ficha": "VIGENTE", "zona": "COMPRA", "costo": 2.0}
    # presupuesto para 2 deeps ($4.1, costo estimado 2.0)
    res = drenar(q, deep_fn=_deep, presupuesto_disponible=4.1, costo_estimado=2.0)
    assert corridos_tk == ["MP", "VST"]                # P0, P1 corren; P2 (OKLO) sin presupuesto
    assert [c["ticker"] for c in res.corridos] == ["MP", "VST"]
    assert res.saltados[0]["ticker"] == "OKLO" and abs(res.costo_total - 4.0) < 1e-9
    # las corridas quedan HECHO; OKLO sigue PENDIENTE
    assert [r.ticker for r in q.pendientes()] == ["OKLO"]


def test_deep_fallido_descarta_no_tumba(tmp_path):
    q = ResearchQueue(tmp_path / "q.json")
    q.encolar("MP", origen="PM", prioridad="P1")
    q.encolar("OKLO", origen="PM", prioridad="P1")
    def _deep(ticker, *, ciego):
        if ticker == "MP":
            raise RuntimeError("red caída")
        return {"estado_ficha": "VIGENTE", "zona": "MANTENER", "costo": 1.5}
    res = drenar(q, deep_fn=_deep, presupuesto_disponible=10.0)
    assert any(s["ticker"] == "MP" and "falló" in s["motivo"] for s in res.saltados)   # MP descartado, no tumba
    assert [c["ticker"] for c in res.corridos] == ["OKLO"]                             # OKLO sí corrió
    assert q.pendientes() == []                                                        # ambas cerradas (HECHO/DESCARTADO)


def test_error_de_credito_no_descarta_y_frena(tmp_path):
    # el bug del 2026-11-24: sin crédito, cada deep falla igual → NO se descartan; quedan PENDIENTE y se frena.
    q = ResearchQueue(tmp_path / "q.json")
    q.encolar("COHR", origen="OPERADOR", prioridad="P1")
    q.encolar("CIEN", origen="OPERADOR", prioridad="P1")
    def _deep(ticker, *, ciego):
        raise RuntimeError("Error code: 400 - Your credit balance is too low to access the Anthropic API")
    res = drenar(q, deep_fn=_deep, presupuesto_disponible=10.0)
    assert {r.ticker for r in q.pendientes()} == {"COHR", "CIEN"}   # ninguna descartada: quedan para reintentar
    assert res.corridos == []
    assert any("FRENADO" in s["motivo"] for s in res.saltados)      # frenó tras el primer error de crédito


def test_error_transitorio_reintenta_pero_sigue(tmp_path):
    # un timeout puntual deja el nombre PENDIENTE (reintenta) pero NO frena el drenaje.
    q = ResearchQueue(tmp_path / "q.json")
    q.encolar("MP", origen="PM", prioridad="P1")
    q.encolar("OKLO", origen="PM", prioridad="P1")
    def _deep(ticker, *, ciego):
        if ticker == "MP":
            raise RuntimeError("Request timed out")
        return {"estado_ficha": "VIGENTE", "zona": "COMPRA", "costo": 1.0}
    res = drenar(q, deep_fn=_deep, presupuesto_disponible=10.0)
    assert [c["ticker"] for c in res.corridos] == ["OKLO"]          # siguió con la segunda
    assert [r.ticker for r in q.pendientes()] == ["MP"]             # MP quedó para reintentar (no descartado)
