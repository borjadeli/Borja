"""P2.1 (doc 91) — corre el contrafactual de rotación sobre el ledger real y lo imprime.

  .venv/bin/python -m ops.contrafactual_rotacion

¿Cada vez que BORJA vendió A para comprar B, mejoró? Compara el forward-return de lo VENDIDO (si se hubiera
mantenido) vs lo COMPRADO, a 30/90/180/365 días. $0 (sin LLM). Las decisiones recientes quedan pendientes.
"""
from __future__ import annotations

from datetime import date

from backend.agentes.contrafactual_rotacion import contrafactual
from backend.agentes.ledger_decisiones import LedgerDecisiones


def _hist(ticker: str) -> dict:
    try:
        from backend.services.market_data import historico_diario
        return historico_diario(ticker, period="2y") or {}
    except Exception:  # noqa: BLE001 — sin red, el horizonte queda pendiente (no rompe)
        return {}


def main() -> int:
    decisiones = LedgerDecisiones().decisiones()
    res = contrafactual(decisiones, hist_fn=_hist, hoy=date.today())
    print("=== CONTRAFACTUAL DE ROTACIÓN (P2.1) — ¿la rotación mejoró vs mantener? ===")
    print(f"decisiones ejecutadas en el ledger: {sum(1 for d in decisiones if getattr(d, 'ejecutada', True))}\n")
    print(f"{'horizonte':>10} {'n_vend':>7} {'n_comp':>7} {'ret_vend':>9} {'ret_comp':>9} {'edge':>8}")
    for r in res:
        rv = f"{r.ret_ventas:+.1%}" if r.ret_ventas is not None else "—"
        rc = f"{r.ret_compras:+.1%}" if r.ret_compras is not None else "—"
        ed = f"{r.edge:+.1%}" if r.edge is not None else "pendiente"
        print(f"{r.dias:>8}d {r.n_ventas:>7} {r.n_compras:>7} {rv:>9} {rc:>9} {ed:>8}")
    print("\nedge POSITIVO = la rotación agregó (compró mejor de lo que vendió) · NEGATIVO = vendió ganadores temprano.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
