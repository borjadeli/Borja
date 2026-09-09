"""Jobs del scheduler para el núcleo nuevo en paper (autónomo).

Jobs cableados en backend/scheduler.py:
  - job_paper_ciclo        — opera (compra/vende) sin confirmación. Diario, GRATIS
                             (sin LLM), SALVO que salte un evento fuerte → re-juicio PM.
  - job_paper_snapshot     — marca a mercado + snapshot de equity. Diario, GRATIS.
  - job_paper_reextraccion — re-extrae hechos con LLM (refresca bull/bear/gate).
                             Semanal, ~$3.5/corrida.
  - job_paper_pm           — canal de juicio PM-LLM → libro_pm.json (targets de tamaño).
                             Semanal (tras la re-extracción) + evento. Costoso (LLM+web/nombre).

El PM manda el TAMAÑO dentro del hard_cap determinista (doc 39). Plata SIMULADA, libro
propio. No toca capital real.
"""
from __future__ import annotations

from backend.utils import get_logger

log = get_logger(__name__)

_UMBRAL_RED_FLAGS_EVENTO = 3   # ≥3 soft red flags → evento fuerte que dispara re-juicio del PM


def job_paper_pm(tickers: list[str] | None = None, *, merge: bool = False) -> dict:
    """Corre el PM-LLM (canal de juicio, Bloque 3) sobre `tickers` (default: universo vivo) → persiste libro_pm.json.

    Cadencia: SEMANAL (full, tras la re-extracción del domingo) + EVENTO (merge=True, subset). COSTOSO: llama al
    LLM con web search POR NOMBRE. El ciclo diario NO llama acá salvo que salte un evento fuerte."""
    from backend.database import session_scope
    from backend.seleccion import pm_run
    from backend.seleccion.paper_trader import _hoy
    if tickers is None:
        from backend.nucleo.shadow import _tickers_vivos
        tickers = _tickers_vivos()
    if not tickers:
        return {"n": 0}
    fecha = _hoy()
    with session_scope() as s:
        libro_pm = pm_run.correr(s, tickers, fecha, usar_web=True)
    (pm_run.persistir_merge if merge else pm_run.persistir)(libro_pm)
    log.info("paper_pm — %s · %d decisiones · %d/%d promos · merge=%s",
             fecha, len(libro_pm.decisiones), libro_pm.promos_usadas, libro_pm.presupuesto, merge)
    return {"n": len(libro_pm.decisiones), "promos": libro_pm.promos_usadas}


def job_paper_ciclo() -> dict:
    """Ciclo de trading automático en paper (salida + entrada). Sin LLM, SALVO disparo por evento fuerte."""
    from backend.nucleo.shadow import _tickers_vivos
    from backend.seleccion import paper_trader as pt
    from backend.seleccion import pm_run
    tickers = _tickers_vivos()
    evs = pt.evaluaciones_desde_cache(tickers)
    libro = pt.cargar_libro()
    # Vías 2 y 3 de salida (CRR-crítico + red flags) sobre las posiciones vivas. Sin LLM.
    eventos = pt.eventos_red_flags(list(libro.posiciones.keys()))
    # Disparo por EVENTO: nombres con evento fuerte (CRR crítico o ≥N soft red flags) → re-juicio PM ad-hoc (LLM).
    afectados = [tk for tk, e in eventos.items()
                 if e.get("crr_critico") or (e.get("soft_red_flags") or 0) >= _UMBRAL_RED_FLAGS_EVENTO]
    if afectados:
        log.info("paper_ciclo — evento fuerte en %s → re-juicio PM ad-hoc", afectados)
        try:
            job_paper_pm(afectados, merge=True)
        except Exception as e:  # noqa: BLE001 — el re-juicio por evento no debe tumbar el ciclo
            log.warning("paper_ciclo — re-juicio PM por evento falló: %s", e)
    pm_libro = pm_run.cargar()   # targets del PM (semanal + eventos). None → sizing por mérito (fallback seguro).
    r = pt.correr_ciclo(evs, eventos=eventos, libro=libro, persistir=True, pm_libro=pm_libro)
    log.info("paper_ciclo — compras=%d topeos=%d ventas=%d recortes=%d invertido=%.0f%% eventos=%d pm=%s",
             len(r["compras"]), len(r["topeos"]), len(r["ventas"]), len(r["recortes"]),
             r["invertido"] * 100, len(eventos), "sí" if pm_libro else "no")
    return r


def job_paper_snapshot() -> dict | None:
    """Mark-to-market diario + punto en la curva de equity. Sin LLM."""
    from backend.seleccion import paper_pnl
    mtm = paper_pnl.correr_snapshot()
    if mtm:
        log.info("paper_snapshot — equity=$%.0f pnl=%.2f%%", mtm["equity"], mtm["pnl_total_pct"] * 100)
    return mtm


def job_paper_reextraccion() -> dict:
    """Re-extracción semanal de hechos con LLM (refresca bull/bear/gate). Costoso."""
    from backend.nucleo.extractor import reextraer_a_cache
    from backend.nucleo.shadow import _tickers_vivos
    return reextraer_a_cache(_tickers_vivos())
