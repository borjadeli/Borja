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


_EJECUTADAS = Path("data/salidas_ejecutadas.json")
_MOTIVOS_NOTIF = Path("data/motivos_notificados.json")


def _dedup_motivos(motivos: list, hoy: date, ventana_dias: int = 7) -> list:
    """P0-2b (review r11): un mismo motivo no despierta dos veces dentro de `ventana_dias` (el mismo 8-K en el
    lookback de 7 días, o un falsador SUSPECTED persistente). Re-despierta si reaparece tras la ventana (recordatorio
    semanal). PURO salvo la persistencia en `_MOTIVOS_NOTIF`."""
    try:
        notif = json.loads(_MOTIVOS_NOTIF.read_text())
    except Exception:  # noqa: BLE001
        notif = {}
    nuevos = []
    for m in motivos:
        last = notif.get(m)
        if last is None or (hoy - date.fromisoformat(last)).days >= ventana_dias:
            nuevos.append(m)
            notif[m] = hoy.isoformat()          # el timestamp se actualiza SOLO cuando despierta
    notif = {k: v for k, v in notif.items() if (hoy - date.fromisoformat(v)).days <= 30}   # prune >30d
    _MOTIVOS_NOTIF.parent.mkdir(parents=True, exist_ok=True)
    _MOTIVOS_NOTIF.write_text(json.dumps(notif, ensure_ascii=False, indent=2), encoding="utf-8")
    return nuevos


def _ya_ejecutadas() -> set:
    try:
        return set(json.loads(_EJECUTADAS.read_text()))
    except Exception:  # noqa: BLE001
        return set()


def _marcar_ejecutadas(claves: set) -> None:
    _EJECUTADAS.parent.mkdir(parents=True, exist_ok=True)
    _EJECUTADAS.write_text(json.dumps(sorted(_ya_ejecutadas() | claves), ensure_ascii=False, indent=2))


def _clave(s) -> str:
    return f"{s.ticker}:{s.fuente}"


def _planear_salidas(duras, ya: set, pesos_actuales: dict) -> tuple:
    """PURO (testeable): dadas las salidas DURAS, las claves YA ejecutadas (ticker:fuente) y los pesos actuales
    de la cartera, devuelve (pesos_finales, claves_nuevas). SOLO SALIDA_TOTAL cuenta (tier B/C despiertan al PM,
    no se auto-ejecutan); IDEMPOTENTE (una salida ya disparada no se repite); toca SOLO el ticker de la salida (el
    resto de la cartera queda igual). Sin salidas nuevas → (None, set())."""
    from backend.agentes.reglas_salida import pesos_tras_salidas
    nuevas = [s for s in duras if s.accion == "SALIDA_TOTAL" and _clave(s) not in ya]
    if not nuevas:
        return None, set()
    return pesos_tras_salidas(pesos_actuales, nuevas), {_clave(s) for s in nuevas}


def _ejecutar_salidas(duras) -> list:
    """Ejecuta SOLO las salidas tier A (SALIDA_TOTAL → vende la posición) en el paper. r10: el determinismo se
    limita a lo catastrófico; tier B/C despiertan al PM. IDEMPOTENTE: una salida ya disparada (por accession/id)
    no se repite. Pesos = valor de mercado / equity; toca SOLO el ticker de la salida (no rebalancea el resto).
    La lógica pura (filtro + idempotencia + pesos) está en `_planear_salidas`; acá va solo el IO."""
    from backend.agentes.datos_reales import abrir_paper, precios_de, recolectar_snapshots
    from backend.agentes.orquestador_decision import ResultadoDecision
    from backend.agentes.paper_pm import ejecutar as ejecutar_paper
    from backend.ledger import core
    ya = _ya_ejecutadas()
    if not any(s.accion == "SALIDA_TOTAL" and _clave(s) not in ya for s in duras):   # nada nuevo → no abrir el paper
        return []
    paper = abrir_paper(capital_inicial=100_000.0, fecha=date.today())
    try:
        tks_pos = list(core.proyectar(paper, {})["posiciones"].keys())
        tks = sorted(set(tks_pos) | {s.ticker.upper() for s in duras if s.accion == "SALIDA_TOTAL"})
        precios = precios_de(recolectar_snapshots(tks))
        proy = core.proyectar(paper, precios)
        equity = proy["equity"] or 1.0
        pesos = {t.upper(): round((pp.shares * precios.get(t.upper(), 0.0)) / equity, 6)
                 for t, pp in proy["posiciones"].items()}        # peso = valor de mercado / equity (.upper: patrón del runner)
        finales, claves = _planear_salidas(duras, ya, pesos)
        if finales is None:
            return []
        res = ResultadoDecision(pesos_objetivo=finales, pesos_finales=finales,
                                caja_final=round(1.0 - sum(finales.values()), 6), clip="none", no_action=False)
        rp = ejecutar_paper(paper, res, precios=precios, fecha_fill=date.today())
        paper.commit()                                         # P0-1: sin commit, close() hace ROLLBACK → la salida
        _marcar_ejecutadas(claves)                             # se perdía. Marcar idempotencia SOLO tras commitear OK.
        return getattr(rp, "fills", [])
    finally:
        paper.close()


def correr(drenar_presupuesto: float = 6.0, con_drenaje: bool = True, despertar_pm: bool = True) -> None:
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
            from backend.agentes.datos_reales import valor_fn_falsadores
            from backend.services.edgar import get_recent_filings
            store = StoreFichas(); fichas = store.todos()
            rp = pollear(fichas, filings_fn=lambda tk: get_recent_filings(
                tk, tipos=("8-K", "10-Q", "10-K", "S-1", "S-3"), dias=7), hoy=date.today())
            for tk in rp.en_revision:
                store.set(fichas[tk])
            store.guardar()
            PipelineEstado().marcar("poller")
            from ops.poller import _posiciones
            salidas = evaluar_reglas_salida(
                rp.eventos, posiciones=_posiciones(),
                falsadores_confirmados=confirmados_para_salida(
                    fichas, valor_fn=valor_fn_falsadores(), hoy=date.today()))   # P0-2a: no despertar por OK diario
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

        # AUTO-EJECUCIÓN: SOLO tier A catastrófico (SALIDA_TOTAL por quiebra/restatement). r10: tier B/C despiertan
        # al PM (él + Auditor deciden); el determinismo se limita a lo inequívoco. Idempotente.
        salidas = res.poller.get("salidas") or []
        duras = [s for s in salidas if s.accion == "SALIDA_TOTAL"]
        if duras:
            try:
                _fills = _ejecutar_salidas(duras)
                print(f"⚙️  salidas ejecutadas en el paper: {_fills}")
            except Exception as e:  # noqa: BLE001 — una ejecución que falla no tumba el ciclo
                print(f"⚠️  no pude ejecutar salidas: {e}")

        print(f"EN_REVISION: {res.poller.get('en_revision')} · cambios de zona: {len(res.cambios_zona)} · "
              f"deeps: {len(res.deeps_hechos)}")
        motivos_nuevos = _dedup_motivos(res.motivos_despertar, date.today())   # P0-2b: no repetir el mismo motivo
        if motivos_nuevos:
            _DESPERTAR.write_text(json.dumps({"fecha": date.today().isoformat(),
                                              "motivos": motivos_nuevos}, ensure_ascii=False, indent=2))
            print("🔔 DESPERTAR AL PM:")
            for m in motivos_nuevos:
                print(f"  - {m}")
            if despertar_pm:          # r10 P0-3: el DESPERTAR corre SOLO el PM (su packet), no el comité completo.
                from backend.agentes.disparar_comite import disparar_comite    # los análisis nuevos van por la cola.
                r = disparar_comite(solo_pm=True)
                print(f"\n=== PM DESPERTADO (solo-PM, ok={r['ok']}) ===\n{r['resumen']}")
        elif res.motivos_despertar:
            print(f"motivos ya notificados en los últimos 7 días ({len(res.motivos_despertar)}): no se re-despierta.")
        else:
            print("sin motivo para despertar al PM (válido: no hacer nada).")
    finally:
        _soltar_lock()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--presupuesto", type=float, default=6.0)
    ap.add_argument("--sin-drenaje", action="store_true")
    ap.add_argument("--sin-despertar", action="store_true", help="computa el despertar pero NO dispara el comité")
    a = ap.parse_args()
    correr(a.presupuesto, con_drenaje=not a.sin_drenaje, despertar_pm=not a.sin_despertar)
