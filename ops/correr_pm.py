"""Corre el PM-LLM oficial sobre el universo del paper → persiste el LibroPM (data/nucleo_paper/libro_pm.json).

    .venv/bin/python -m ops.correr_pm [TICKER ...]

Sin args: usa las posiciones vigentes del libro paper. Cadencia real: evento + semanal (jobs.py).
Costo: llama al PM-LLM (web search) por nombre elegible — no lo corras a lo loco. Aditivo: NO toca libro.json.
"""
from __future__ import annotations

import sys

from backend.database import session_scope
from backend.seleccion import pm_run
from backend.seleccion.paper_trader import _hoy, cargar_libro
from backend.utils import get_logger

log = get_logger(__name__)


def _universo_default() -> list[str]:
    try:
        libro = cargar_libro()
        return list(libro.posiciones.keys())
    except Exception:  # noqa: BLE001
        return []


def main(argv: list[str]) -> int:
    tickers = [t.upper() for t in argv] or _universo_default()
    if not tickers:
        print("Sin tickers (ni args ni posiciones en el libro paper). Nada que correr.")
        return 1
    fecha = _hoy()
    with session_scope() as s:
        libro_pm = pm_run.correr(s, tickers, fecha, usar_web=True)
    ruta = pm_run.persistir(libro_pm)
    print(f"LibroPM {fecha}: {libro_pm.promos_usadas}/{libro_pm.presupuesto} promos · {len(libro_pm.decisiones)} decisiones → {ruta}")
    for d in libro_pm.decisiones:
        flag = " ⬆" if (d.etiqueta in ("PRIORITY_HIGH", "PRIORITY_MEDIUM", "PRIORITY_LOW") and d.size_final > d.banda.base + 1e-9) else ""
        print(f"  {d.ticker:7} {d.etiqueta:16} size {d.size_final:.1%} (base {d.banda.base:.1%} · techo {d.banda.techo:.1%}){flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
