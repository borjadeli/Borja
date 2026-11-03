"""Set DORADO de datos (r5 item 3) — captura las métricas del pack XBRL por nombre para regresión.

Es la red de seguridad que habría atrapado el bug de MP ($429M vs $1.452,6M): si un cambio en la extracción
rompe un número, el test de regresión lo caza. Flujo:
  1. `ops.golden_snapshot TICK1 TICK2 ...`  → arma el pack (hits EDGAR) y escribe `tests/golden/golden_pack.json`.
  2. El OPERADOR o una IA externa VERIFICA cada valor contra el 10-Q/10-K y pone `"verificado": true`.
  3. `tests/test_golden.py` chequea que el pack reproduzca los valores dentro de tolerancia (network-gated).

Captura solo métricas DURAS del XBRL (determinista, point-in-time): caja, caja+ST, inversiones corto/largo,
acciones (hoy y -1y), dilución 12m, revenue FY, flujo operativo, capex FY, runway capex-aware, deuda LP.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from backend.agentes import data_pack as dp

_GOLDEN = Path(__file__).resolve().parent.parent / "tests" / "golden" / "golden_pack.json"
_METRICAS = ["cash", "cash_and_sti", "short_term_investments", "long_term_investments", "liquidez",
             "shares_outstanding", "shares_outstanding_1y", "dilucion_12m_pct", "revenue", "revenue_q",
             "cash_used_ops", "capex", "cash_runway_months", "long_term_debt"]


def capturar(tickers: list[str], as_of: date) -> dict:
    prev = json.loads(_GOLDEN.read_text()) if _GOLDEN.exists() else {}
    prev_vals = {t.upper(): e for t, e in prev.get("nombres", {}).items()}
    nombres: dict[str, dict] = {}
    for tk in tickers:
        tk = tk.upper()
        pts = {p.metric: p for p in dp.fuente_xbrl(tk, as_of)}
        pts.update({p.metric: p for p in dp.fuente_calculadoras(tk, as_of, list(pts.values()))})
        antes = prev_vals.get(tk, {}).get("metricas", {})
        metricas = {}
        for m in _METRICAS:
            p = pts.get(m)
            if p is not None and p.value is not None:
                # conserva el flag "verificado" si ya estaba y el valor no cambió materialmente
                v_antes = antes.get(m, {})
                igual = isinstance(v_antes, dict) and abs((v_antes.get("valor") or 0) - p.value) <= abs(p.value) * 1e-4
                metricas[m] = {"valor": round(p.value, 2), "verificado": bool(v_antes.get("verificado")) and igual}
        nombres[tk] = {"as_of": as_of.isoformat(), "metricas": metricas}
    return {"capturado": date.today().isoformat(), "tolerancia_rel": 0.001, "nombres": nombres}


def main() -> int:
    tickers = sys.argv[1:] or ["MP", "OKLO", "RGTI"]
    out = capturar(tickers, date.today())
    _GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    _GOLDEN.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"golden escrito en {_GOLDEN} ({len(out['nombres'])} nombres)")
    for tk, e in out["nombres"].items():
        pend = [m for m, v in e["metricas"].items() if not v["verificado"]]
        print(f"  {tk}: {len(e['metricas'])} métricas · SIN verificar vs 10-Q: {len(pend)}")
    print("\nPaso siguiente: verificá cada valor contra el 10-Q/10-K y poné \"verificado\": true en el JSON.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
