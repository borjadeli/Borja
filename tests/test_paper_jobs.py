"""Wiring de los jobs del paper con el PM (tajada 3): el ciclo pasa el libro_pm y el evento dispara el re-juicio."""
from backend.seleccion import jobs
from backend.seleccion import paper_trader as pt
from backend.seleccion import pm_run

_R = {"compras": [], "topeos": [], "ventas": [], "recortes": [],
      "invertido": 0.0, "n_posiciones": 0, "libro": pt.LibroPaper()}


def test_ciclo_pasa_pm_libro_a_correr_ciclo(monkeypatch):
    monkeypatch.setattr("backend.nucleo.shadow._tickers_vivos", lambda: ["RBRK"])
    monkeypatch.setattr(pt, "evaluaciones_desde_cache", lambda tks: [])
    monkeypatch.setattr(pt, "cargar_libro", lambda: pt.LibroPaper())
    monkeypatch.setattr(pt, "eventos_red_flags", lambda tks: {})
    captado = {}
    monkeypatch.setattr(pt, "correr_ciclo",
                        lambda evs, **kw: captado.update(pm_libro=kw.get("pm_libro")) or dict(_R))
    monkeypatch.setattr(pm_run, "cargar", lambda: {"decisiones": [{"ticker": "RBRK", "size_final": 0.08}]})
    jobs.job_paper_ciclo()
    assert captado["pm_libro"]["decisiones"][0]["ticker"] == "RBRK"   # el ciclo enchufa el libro_pm


def test_evento_fuerte_dispara_re_juicio_pm(monkeypatch):
    monkeypatch.setattr("backend.nucleo.shadow._tickers_vivos", lambda: [])
    monkeypatch.setattr(pt, "evaluaciones_desde_cache", lambda tks: [])
    monkeypatch.setattr(pt, "cargar_libro", lambda: pt.LibroPaper(posiciones={"MP": {"sizing": 0.06}}))
    monkeypatch.setattr(pt, "eventos_red_flags", lambda tks: {"MP": {"crr_critico": True}})
    monkeypatch.setattr(pt, "correr_ciclo", lambda evs, **kw: dict(_R))
    monkeypatch.setattr(pm_run, "cargar", lambda: None)
    llamados = {}
    monkeypatch.setattr(jobs, "job_paper_pm",
                        lambda tickers=None, merge=False: llamados.update(t=tickers, m=merge) or {"n": 1})
    jobs.job_paper_ciclo()
    assert llamados["t"] == ["MP"] and llamados["m"] is True          # evento crítico → PM ad-hoc (merge)


def test_sin_evento_no_dispara_pm(monkeypatch):
    monkeypatch.setattr("backend.nucleo.shadow._tickers_vivos", lambda: [])
    monkeypatch.setattr(pt, "evaluaciones_desde_cache", lambda tks: [])
    monkeypatch.setattr(pt, "cargar_libro", lambda: pt.LibroPaper(posiciones={"MP": {"sizing": 0.06}}))
    monkeypatch.setattr(pt, "eventos_red_flags", lambda tks: {"MP": {"soft_red_flags": 1}})  # 1 < umbral 3
    monkeypatch.setattr(pt, "correr_ciclo", lambda evs, **kw: dict(_R))
    monkeypatch.setattr(pm_run, "cargar", lambda: None)
    disparado = {"n": 0}
    monkeypatch.setattr(jobs, "job_paper_pm", lambda *a, **k: disparado.update(n=disparado["n"] + 1))
    jobs.job_paper_ciclo()
    assert disparado["n"] == 0                                        # evento débil → NO gasta LLM
