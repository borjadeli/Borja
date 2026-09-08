"""Jobs del scheduler para el núcleo nuevo en paper (autónomo).

Tres jobs, cableados en backend/scheduler.py:
  - job_paper_ciclo        — opera (compra/vende) sin confirmación. Diario, GRATIS
                             (sin LLM: usa hechos cacheados + precios frescos).
  - job_paper_snapshot     — marca a mercado + snapshot de equity. Diario, GRATIS.
  - job_paper_reextraccion — re-extrae hechos con LLM (refresca bull/bear/gate).
                             Semanal, ~$3.5/corrida (el único costo recurrente).

Plata SIMULADA, libro propio. No toca el sistema viejo ni capital real.
"""
from __future__ import annotations

from backend.utils import get_logger

log = get_logger(__name__)


def job_paper_ciclo() -> dict:
    """Ciclo de trading automático en paper (salida + entrada). Sin LLM."""
    from backend.nucleo.shadow import _tickers_vivos
    from backend.seleccion import paper_trader as pt
    tickers = _tickers_vivos()
    evs = pt.evaluaciones_desde_cache(tickers)
    libro = pt.cargar_libro()
    # Vías 2 y 3 de salida (CRR-crítico + red flags) sobre las posiciones vivas. Sin LLM.
    eventos = pt.eventos_red_flags(list(libro.posiciones.keys()))
    r = pt.correr_ciclo(evs, eventos=eventos, libro=libro, persistir=True)
    log.info("paper_ciclo — compras=%d topeos=%d ventas=%d recortes=%d invertido=%.0f%% eventos=%d",
             len(r["compras"]), len(r["topeos"]), len(r["ventas"]), len(r["recortes"]),
             r["invertido"] * 100, len(eventos))
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
