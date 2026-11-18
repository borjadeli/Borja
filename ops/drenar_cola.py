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


M_SONNET = "claude-sonnet-5-5"


def _deep_real(ticker: str, *, ciego: bool = False) -> dict:
    """Corre el deep de UN nombre con EL MISMO COMITÉ que el semanal (r10 P0-2: un solo camino de análisis):
    data pack → Analista → Bear → Verificador → cache + ficha. **DELTA-DEEP (doc 76):** si ya hay un dossier previo
    en el cache, hace el re-análisis BARATO (`Analista.actualizar`, ~2 búsquedas vs 6; el Bear solo corre si los
    escenarios se movieron) en vez del deep completo. Un nombre NUEVO → deep full. La ficha queda VIGENTE SOLO si el
    Verificador NO da FAIL (un FAIL → ROTA, no compromete capital). Persiste el dossier al cache (así un deep pedido
    por el PM llega al wake). Devuelve {estado_ficha, zona, costo, veredicto, modo}. `ciego` = deep en frío (F3)."""
    from datetime import date as _d

    from backend.agentes import bear as m_bear, data_pack as dp
    from backend.agentes.analista import Analista, PROMPT_VERSION
    from backend.agentes.base import Agente
    from backend.agentes.bear import Bear
    from backend.agentes.ficha import backfill_desde_dossier
    from backend.agentes.ficha_store import StoreFichas
    from backend.agentes.orquestador import CacheDossiers, _CACHE_PATH, _escenarios_cambiaron, hash_pack
    from backend.agentes.verificador import verificar
    from ops.backfill_fichas import _datos_de_pack
    from ops.correr_semana_v2 import _contexto_mapa_fn

    hoy = _d.today()
    pack = dp.ensamblar(ticker, as_of=hoy)
    h = hash_pack(pack)
    cache = CacheDossiers(_CACHE_PATH)
    prev = None if ciego else cache.ultimo(ticker)   # en frío (F3) se ignora el previo a propósito
    analista = Analista(Agente("analista", PROMPT_VERSION, M_OPUS))
    if prev is not None and prev.dossier is not None:          # DELTA-DEEP: refresco barato sobre la tesis previa
        r = analista.actualizar(ticker, prev.dossier, data_pack=pack,
                                contexto_cuello=_contexto_mapa_fn(ticker), memo_macro="")
        modo = "delta"
    else:                                                      # nombre nuevo → deep completo
        r = analista.analizar(ticker, data_pack=pack, contexto_cuello=_contexto_mapa_fn(ticker), memo_macro="")
        modo = "full"
    costo = float(getattr(r.meta, "cost_usd", 0.0) or 0.0)
    if r.dossier is None:
        return {"estado_ficha": None, "zona": None, "costo": costo, "veredicto": "sin_dossier", "modo": modo}
    # Bear: en un refresco cuyos escenarios NO se movieron se SALTEA (doc 80 §E); nuevo o escenarios movidos → corre.
    es_refresh = prev is not None and prev.dossier is not None
    if (not es_refresh) or _escenarios_cambiaron(prev.dossier, r.dossier):
        atk = Bear(Agente("bear", m_bear.PROMPT_VERSION, M_SONNET)).atacar(r.dossier)
        costo += float(getattr(atk.meta, "cost_usd", 0.0) or 0.0)
    knowns = [p.known_at for p in pack.puntos if p.known_at and "xbrl" in (p.source.name or "").lower()]
    verif = verificar(r.dossier, r.fuentes, pack={p.metric: p for p in pack.puntos},
                      ultimo_filing_periodico=max(knowns) if knowns else None, hoy=hoy)
    costo += float(getattr(verif.meta, "cost_usd", 0.0) or 0.0)
    if verif.veredicto == "fail":     # FAIL → NO vigente: no se compromete capital con un dossier que no pasó
        return {"estado_ficha": "ROTA", "zona": None, "costo": costo, "veredicto": "fail", "modo": modo}
    cache.guardar(ticker, h, r.dossier, verif, hoy)   # persiste → el dossier llega al wake y es base del próximo delta
    datos = _datos_de_pack(ticker, as_of=hoy) or {}
    f = backfill_desde_dossier(ticker, r.dossier, deuda_neta=float(datos.get("deuda_neta") or 0.0),
                               acciones=float(datos.get("acciones") or 0.0) or 1.0, precio=datos.get("precio"),
                               caja=datos.get("caja"), cuello=datos.get("cuello"),
                               datos_conflicted=bool(datos.get("datos_conflicted")))
    store = StoreFichas()
    store.set(f)
    store.guardar()
    zona = f.latido.zona if f.latido else None
    return {"estado_ficha": f.estado, "zona": zona, "costo": costo, "veredicto": verif.veredicto, "modo": modo}


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
