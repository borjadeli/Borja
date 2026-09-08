"""Dump de HECHOS CRUDOS por empresa (doc 44 chequeo A) — los inputs que el método consume, para que una IA
externa aplique NUESTRO método a los MISMOS datos.

    .venv/bin/python -m ops.dump_datos CLS RBRK LEU

Sin interpretación: revenue/GP/OpEx por trimestre, owner-FCF, SBC, caja/deuda, shares, precio, RPO, crecimiento
demostrado, dilución, insider. Es la 'materia prima' — el método portable (doc 44 §Método) se aplica ENCIMA."""
from __future__ import annotations

import sys

from backend.database import session_scope
from backend.nucleo import fact_store as FS
from backend.nucleo.crecimiento import crecimiento_demostrado
from backend.nucleo.extractor import extraer_deterministas
from backend.services import edgar, market_data


def _f(x, d=1e6, suf="M"):
    return f"{x/d:,.1f}{suf}" if isinstance(x, (int, float)) else "s/d"


def dump(session, ticker: str) -> None:
    det = extraer_deterministas(ticker)
    fin = edgar.get_financials_quarterly(ticker, periodos=12)
    serie = edgar.serie_crecimiento(ticker, n_q=16)
    snap = market_data.get_price_snapshot(ticker)
    sh = edgar.get_shares_outstanding(ticker)
    ins = edgar.get_insider_activity(ticker, dias=365)
    gd = crecimiento_demostrado(serie, "Growth")
    owner = (fin.fcf_ttm or 0) - (fin.sbc_ttm or 0)

    print("\n" + "═" * 80)
    print(f"  DATOS CRUDOS · {ticker}")
    print("═" * 80)
    print(f"  precio: ${snap.precio_actual if snap else 's/d'} · shares: {_f(sh,1e6,'M')} · "
          f"mktcap: {_f((snap.precio_actual*sh) if (snap and sh) else None,1e9,'B')}")
    print(f"  revenue TTM: {_f(fin.revenue_ttm)} · gross_profit TTM: "
          f"{_f(sum([q['gross_profit'] for q in fin.quarters[-4:] if q.get('gross_profit')]) if fin.quarters else None)}")
    print(f"  CFO−capex (FCF): {_f(fin.fcf_ttm)} · SBC: {_f(fin.sbc_ttm)} · owner-FCF (FCF−SBC): {_f(owner)}")
    sbc_pct = f"{fin.sbc_ttm/fin.revenue_ttm*100:.0f}%" if (fin.sbc_ttm and fin.revenue_ttm) else "s/d"
    print(f"  SBC/revenue: {sbc_pct}")
    print(f"  caja: {_f(fin.cash)} · deuda: {_f(fin.total_debt)} · RPO (backlog contratado): "
          f"{_f(det.get('rpo'))} as_of {det.get('rpo_as_of') or 's/d'}")
    gd_val = gd.get("g_D")
    gd_str = f"{gd_val:.0%}" if gd_val is not None else "s/d"
    traza = "; ".join(gd.get("traza", [])[:4])
    print(f"  crecimiento demostrado g_D: {gd_str} (traza: {traza})")
    print(f"  dilución 3y: {edgar.get_dilution_pct_3y(ticker)}% · insider neto 12m: {_f(ins.net_usd)}")
    # series por trimestre (para Δ8Q(GP)/Δ8Q(OpEx))
    print("  series trimestrales (viejo→nuevo) [revenue / gross_profit / operating_income / diluted_shares]:")
    for q in fin.quarters[-8:]:
        gp, oi = q.get("gross_profit"), q.get("operating_income")
        opex = (gp - oi) if (gp is not None and oi is not None) else None
        print(f"    {q.get('fecha')}: rev {_f(q.get('revenue'))} · GP {_f(gp)} · OI {_f(oi)} · "
              f"OpEx(GP−OI) {_f(opex)}")
    # demanda citada
    snap_fs = FS.snapshot_vigente(session, ticker)
    dem = snap_fs.get("demanda_realizada") or snap_fs.get("cliente_nombrado")
    if dem is not None and getattr(dem, "quote", None):
        print(f"  demanda citada: «{dem.quote[:120]}»")


def main(argv: list[str]) -> int:
    tickers = [t.upper() for t in argv] or ["CLS", "RBRK", "LEU"]
    with session_scope() as s:
        for t in tickers:
            try:
                dump(s, t)
            except Exception as e:  # noqa: BLE001
                print(f"\n  {t}: ERROR {type(e).__name__}: {e}")
    print("\n" + "─" * 80)
    print("Materia prima. Aplicar el MÉTODO PORTABLE (doc 44 §Método) encima → comparar vs ops.ficha_profunda.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
