"""r12 #9 — test de UN DÍA: el circuito CONECTA de punta a punta sobre stores en tmp, sin red ni LLM.
Cubre las piezas que r12 cableó: ficha del comité (#5) → decisión → gate (caps #1/#2) → paper con COMMIT (#3)
→ ledger de decisiones (zona, P1-4) → salida tier A que persiste (#3) → dedup de despertares (P0-2b).
No es el poller/Analista reales (ésos pegan a EDGAR/LLM); es la cadena de DECISIÓN+EJECUCIÓN con objetos reales."""
from datetime import date

import ops.ciclo_diario as cd
from backend.agentes import datos_reales
from backend.agentes.ficha_store import StoreFichas, escribir_ficha_desde_dossier
from backend.agentes.paper_pm import ejecutar as ejecutar_paper
from backend.agentes.reglas_salida import AccionSalida
from backend.ledger import core
from tests.test_orquestador_decision import _accion, _ctx, _decision, _orq
from tests.test_packet_pm import _ESC, _Dossier, _E, _Fals, _Inv


def _pos(session, tk, precios):
    p = core.proyectar(session, precios)["posiciones"].get(tk)
    return 0 if p is None else int(round(p.shares))


def test_un_dia_conecta_de_punta_a_punta(tmp_path, monkeypatch):
    db = tmp_path / "paper.db"

    # 1) COMITÉ ESCRIBE FICHA (#5): un dossier PASS → ficha VIGENTE (lo que el candado exige para comprar)
    fstore = StoreFichas(tmp_path / "f.json")
    dossier = _Dossier(_Inv("satelite"), [_E(**e) for e in _ESC], _Fals("x", "2027-06-30"))
    f = escribir_ficha_desde_dossier("OKLO", dossier, "pass",
                                     datos={"acciones": 100e6, "precio": 18.0}, store=fstore)
    assert f is not None and f.estado == "VIGENTE"

    # 2) DECISIÓN → GATE (caps) → PAPER con COMMIT → el fill PERSISTE al reabrir (#3)
    paper = datos_reales.abrir_paper(db, capital_inicial=100_000.0, fecha=date(2026, 1, 1))
    orq = _orq(tmp_path)
    res = orq.procesar(_decision([_accion("OKLO", 0.05, "comprar")]), cartera_actual={}, caja_actual=1.0,
                       contexto=_ctx(), ciclo="2026-01-02", precios={"OKLO": 18.0},
                       comprable_por_ticker={"OKLO": True}, clase_por_ticker={"OKLO": "satelite"},
                       zonas_por_ticker={"OKLO": "COMPRA"})
    ejecutar_paper(paper, res, precios={"OKLO": 18.0}, fecha_fill=date(2026, 1, 2))
    paper.commit()
    paper.close()
    paper2 = datos_reales.abrir_paper(db, fecha=date(2026, 1, 3))
    assert _pos(paper2, "OKLO", {"OKLO": 18.0}) > 0            # el fill quedó persistido
    paper2.close()
    # la decisión quedó en el ledger (con zona)
    regs = [e for e in orq.ledger._eventos() if e.get("tipo") == "decision" and e.get("ticker") == "OKLO"]
    assert regs and regs[-1]["zona_al_entrar"] == "COMPRA" and regs[-1]["fuera_de_zona"] is False

    # 3) SALIDA TIER A (#3): quiebra de OKLO → _ejecutar_salidas → la posición queda en 0 al reabrir
    orig = datos_reales.abrir_paper
    monkeypatch.setattr(datos_reales, "abrir_paper", lambda **k: orig(db, **k))
    monkeypatch.setattr(datos_reales, "recolectar_snapshots", lambda tks: {t: {} for t in tks})
    monkeypatch.setattr(datos_reales, "precios_de", lambda s: {"OKLO": 18.0})
    monkeypatch.setattr(cd, "_EJECUTADAS", tmp_path / "ejec.json")
    cd._ejecutar_salidas([AccionSalida("OKLO", "A", "SALIDA_TOTAL", "quiebra", "8-K:acc1")])
    paper3 = orig(db, fecha=date(2026, 1, 5))
    assert _pos(paper3, "OKLO", {"OKLO": 18.0}) == 0          # la venta catastrófica persistió
    paper3.close()

    # 4) DEDUP de despertares (P0-2b): el mismo motivo no despierta dos veces en la ventana
    monkeypatch.setattr(cd, "_MOTIVOS_NOTIF", tmp_path / "m.json")
    assert cd._dedup_motivos(["OKLO regla de salida tier A"], date(2026, 1, 5)) == ["OKLO regla de salida tier A"]
    assert cd._dedup_motivos(["OKLO regla de salida tier A"], date(2026, 1, 6)) == []
