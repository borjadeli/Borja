"""run_cycle diario (doc 85 §9) — el pipeline autónomo encadenado. Lo corre el scheduler post-cierre.

poller → latido → drenaje → decide DESPERTAR al PM (cambio de zona / deep en COMPRA / regla de salida). Con LOCK
(un solo ciclo a la vez; un reinicio NO duplica) e idempotencia por día. El $0 (poller/latido) + el drenaje
(LLM) corren siempre; el PM se despierta solo si hay motivo (se persiste el motivo para la corrida del PM).
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import date
from pathlib import Path

from backend.agentes.ciclo import correr_ciclo
from backend.agentes.pipeline_estado import PipelineEstado

_LOCK = Path("data/ciclo.lock")
_DESPERTAR = Path("data/despertar_pm.json")
_LOCK_TTL = 3600         # un lock más viejo que esto se considera huérfano (proceso muerto)


def _tomar_lock() -> bool:
    _LOCK.parent.mkdir(parents=True, exist_ok=True)
    if _LOCK.exists() and (time.time() - _LOCK.stat().st_mtime) < _LOCK_TTL:
        return False                       # otro ciclo corriendo (lock vivo)
    _LOCK.write_text(str(os.getpid()))
    return True


def _soltar_lock() -> None:
    try:
        _LOCK.unlink()
    except FileNotFoundError:
        pass


def correr(drenar_presupuesto: float = 6.0, con_drenaje: bool = True) -> None:
    if not _tomar_lock():
        print("⚠️  ya hay un ciclo corriendo (lock vivo) — se saltea para no duplicar")
        return
    try:
        from ops.job_fichas import main as _latido_main
        from ops.poller import correr as _poller_correr

        def _poller():
            # el poller ya persiste EN_REVISION + marca el dead-man's-switch; devolvemos lo que importa al ciclo
            from backend.agentes.ficha_store import StoreFichas
            from backend.agentes.poller import pollear
            from backend.agentes.reglas_salida import evaluar_reglas_salida
            from backend.agentes.falsadores import confirmados_para_salida
            from backend.services.edgar import get_recent_filings
            store = StoreFichas(); fichas = store.todos()
            rp = pollear(fichas, filings_fn=lambda tk: get_recent_filings(
                tk, tipos=("8-K", "10-Q", "10-K", "S-1", "S-3"), dias=7), hoy=date.today())
            for tk in rp.en_revision:
                store.set(fichas[tk])
            store.guardar()
            PipelineEstado().marcar("poller")
            from ops.poller import _posiciones
            salidas = evaluar_reglas_salida(rp.eventos, posiciones=_posiciones(),
                                            falsadores_confirmados=confirmados_para_salida(fichas, hoy=date.today()))
            return {"en_revision": rp.en_revision, "salidas": salidas}

        def _latido():
            _latido_main()                  # recalcula zonas + persiste alertas de cambio de zona
            PipelineEstado().marcar("latido")
            try:
                return list(json.loads((Path("data/alertas_fichas_v2.json")).read_text()).get("alertas", []))
            except Exception:  # noqa: BLE001
                return []

        def _drenar():
            if not con_drenaje:
                return []
            from backend.agentes.drenaje import drenar
            from backend.agentes.research_queue import ResearchQueue
            from ops.drenar_cola import _deep_real
            q = ResearchQueue()
            if not q.pendientes():
                return []
            r = drenar(q, deep_fn=_deep_real, presupuesto_disponible=drenar_presupuesto, costo_estimado=2.0)
            return r.corridos

        res = correr_ciclo(poller_fn=_poller, latido_fn=_latido, drenar_fn=_drenar, pm_fn=None)
        PipelineEstado().marcar("ciclo_diario")

        print(f"EN_REVISION: {res.poller.get('en_revision')} · cambios de zona: {len(res.cambios_zona)} · "
              f"deeps: {len(res.deeps_hechos)}")
        if res.motivos_despertar:
            _DESPERTAR.write_text(json.dumps({"fecha": date.today().isoformat(),
                                              "motivos": res.motivos_despertar}, ensure_ascii=False, indent=2))
            print("🔔 DESPERTAR AL PM:")
            for m in res.motivos_despertar:
                print(f"  - {m}")
        else:
            print("sin motivo para despertar al PM (válido: no hacer nada).")
    finally:
        _soltar_lock()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--presupuesto", type=float, default=6.0)
    ap.add_argument("--sin-drenaje", action="store_true")
    a = ap.parse_args()
    correr(a.presupuesto, con_drenaje=not a.sin_drenaje)
