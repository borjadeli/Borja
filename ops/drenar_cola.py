"""Drenaje de la Research Queue (doc 85 F2) — el job que corre los deeps pedidos y produce fichas.

    .venv/bin/python -m ops.drenar_cola [--presupuesto 8] [--max 3]

Para cada solicitud PENDIENTE (por prioridad), corre el comité (Analista + backfill de la ficha), cachea el
dossier y marca la solicitud HECHO con la zona resultante. GASTA LLM (Opus+web por nombre). El motivo del PM/
operador NO se le pasa al Analista (pedido ciego). Pensado para el drenaje diario del scheduler.
"""
from __future__ import annotations

import argparse
from datetime import date

from backend.agentes.drenaje import drenar
from backend.agentes.research_queue import ResearchQueue

M_OPUS = "claude-opus-5-5"


def _deep_real(ticker: str, *, ciego: bool = False) -> dict:
    """Corre el deep de UN nombre: data pack → Analista (Opus+web) → cache del dossier → ficha viva. Devuelve
    {estado_ficha, zona, costo}. El motivo NO llega acá (pedido ciego). `ciego` = deep en frío (F3, aún no usado)."""
    from backend.agentes import data_pack as dp
    from backend.agentes.analista import Analista, PROMPT_VERSION
    from backend.agentes.base import Agente
    from backend.agentes.ficha import backfill_desde_dossier
    from backend.agentes.ficha_store import StoreFichas
    from ops.backfill_fichas import _datos_de_pack

    pack = dp.ensamblar(ticker, as_of=date.today())
    r = Analista(Agente("analista", PROMPT_VERSION, M_OPUS)).analizar(ticker, data_pack=pack,
                                                                      contexto_cuello="", memo_macro="")
    costo = float(getattr(r.meta, "cost_usd", 0.0) or 0.0)
    if r.dossier is None:
        return {"estado_ficha": None, "zona": None, "costo": costo}
    datos = _datos_de_pack(ticker, as_of=date.today()) or {}
    f = backfill_desde_dossier(ticker, r.dossier, deuda_neta=float(datos.get("deuda_neta") or 0.0),
                               acciones=float(datos.get("acciones") or 0.0) or 1.0, precio=datos.get("precio"),
                               caja=datos.get("caja"), cuello=datos.get("cuello"),
                               datos_conflicted=bool(datos.get("datos_conflicted")))
    store = StoreFichas()
    store.set(f)
    store.guardar()
    zona = f.latido.zona if f.latido else None
    return {"estado_ficha": f.estado, "zona": zona, "costo": costo}


def correr(presupuesto: float = 8.0, max_n: int | None = None) -> None:
    q = ResearchQueue()
    pend = q.pendientes()
    if not pend:
        print("cola vacía — nada que drenar")
        return
    print(f"pendientes: {[(r.ticker, r.prioridad, r.origen) for r in pend]}")
    res = drenar(q, deep_fn=_deep_real, presupuesto_disponible=presupuesto, costo_estimado=2.0, max_n=max_n)
    print(f"\ndrenaje: {len(res.corridos)} corridos · costo ${res.costo_total:.4f}")
    for c in res.corridos:
        print(f"  {c['ticker']:6} → {c['estado_ficha']}/{c['zona']}  (${c['costo']:.2f})")
    for s in res.saltados:
        print(f"  {s['ticker']:6} SALTADO: {s['motivo']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--presupuesto", type=float, default=8.0)
    ap.add_argument("--max", type=int, default=None)
    a = ap.parse_args()
    correr(a.presupuesto, a.max)
