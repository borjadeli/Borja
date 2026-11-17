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

    print(f"vigilados: {len(fichas)} · eventos materiales: {len(res.eventos)} · EN_REVISION: {res.en_revision}")
    if res.duros:
        print("🔴 DUROS (regla de salida, F2):")
        for e in res.duros:
            print(f"  {e.ticker} {e.tipo} {e.items} ({e.fecha}) — {e.nota}")
    for e in res.eventos:
        if e.tier != "DURO":
            print(f"  {e.ticker:6} [{e.tier}] {e.tipo} {e.items} ({e.fecha})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int, default=7)
    ap.parse_args()
    correr(ap.parse_args().dias)
