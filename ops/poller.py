"""Poller de filings (doc 85 F1) — el job de vigilancia. Corre el núcleo puro sobre los nombres vigilados
(posiciones + banca), persiste las fichas que pasan a EN_REVISION, y MARCA su corrida (dead-man's-switch).

    .venv/bin/python -m ops.poller [--dias 7]

$0 LLM. Pega a EDGAR (cacheado). Pensado para correr cada hora / diario desde el scheduler.
"""
from __future__ import annotations

import argparse
from datetime import date

from backend.agentes.ficha_store import StoreFichas
from backend.agentes.pipeline_estado import PipelineEstado
from backend.agentes.poller import pollear
from backend.agentes.reglas_salida import evaluar_reglas_salida


def _posiciones() -> set[str]:
    """Tickers en cartera del paper (best-effort; vacío si no se puede abrir)."""
    try:
        from datetime import date as _d

        from backend.agentes.datos_reales import abrir_paper
        from backend.ledger import core
        paper = abrir_paper(capital_inicial=100_000.0, fecha=_d.today())
        try:
            return set(core.proyectar(paper, {})["posiciones"].keys())
        finally:
            paper.close()
    except Exception:  # noqa: BLE001
        return set()


def correr(dias: int = 7) -> None:
    from backend.services.edgar import get_recent_filings
    store = StoreFichas()
    fichas = store.todos()
    if not fichas:
        print("sin fichas que vigilar")
        PipelineEstado().marcar("poller")   # igual marca: el pipeline corrió
        return
    filings_fn = lambda tk: get_recent_filings(tk, tipos=("8-K", "10-Q", "10-K", "S-1", "S-3"), dias=dias)  # noqa: E731
    res = pollear(fichas, filings_fn=filings_fn, hoy=date.today())
    for tk in res.en_revision:              # persistir las que pasaron a EN_REVISION
        store.set(fichas[tk]) if tk in fichas else None
    store.guardar()
    PipelineEstado().marcar("poller")       # dead-man's-switch: el poller está vivo

    # F2: reglas de salida — si un DURO pega en una POSICIÓN → acción urgente (tier A salida / B recorte / C despertar)
    posiciones = _posiciones()
    salidas = evaluar_reglas_salida(res.eventos, posiciones=posiciones)

    print(f"vigilados: {len(fichas)} · posiciones: {sorted(posiciones)} · eventos materiales: {len(res.eventos)} · "
          f"EN_REVISION: {res.en_revision}")
    if salidas:
        print("🔴🔴 REGLAS DE SALIDA DISPARADAS (sobre posiciones):")
        for a in salidas:
            print(f"  {a.ticker} → {a.accion} (tier {a.tier}) — {a.motivo}")
    elif res.duros:
        print("DUROS detectados pero NO en posiciones (solo alerta):")
        for e in res.duros:
            print(f"  {e.ticker} {e.items} — {e.nota}")
    for e in res.eventos:
        if e.tier != "DURO":
            print(f"  {e.ticker:6} [{e.tier}] {e.tipo} {e.items} ({e.fecha})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int, default=7)
    ap.parse_args()
    correr(ap.parse_args().dias)
