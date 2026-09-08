"""Mark-to-market diario del libro paper + snapshot de equity (para la curva).

Trae precios actuales de las posiciones del libro, computa P&L/equity, y persiste
el snapshot + el último MtM en el libro (la home lo lee sin tocar red). Pensado
para correr como cron diario tras el cierre.

Uso: python -m ops.paper_snapshot
"""
from __future__ import annotations

import sys

from backend.seleccion import paper_pnl


def main() -> int:
    mtm = paper_pnl.correr_snapshot()
    if mtm is None:
        print("Libro paper vacío — nada que marcar.")
        return 0
    print(f"Equity: ${mtm['equity']:,.0f} | P&L: ${mtm['pnl_total']:,.0f} "
          f"({mtm['pnl_total_pct']:+.2%}) | invertido {mtm['invertido_pct']:.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
