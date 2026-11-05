"""Gate A (r7 §1, doc 78) — ¿la lente de valuación tiene DATOS en nuestro universo?

Antes de construir el margen de seguridad sobre el backlog contratado hay que MEDIR si el dato existe: RPO
(RevenueRemainingPerformanceObligation) y ContractWithCustomerLiability viven en companyfacts pero con
cobertura despareja en small caps / extranjeros (el techo estructural de companyfacts, doc 60). Si la cobertura
es pobre, la lente RPO queda n/a justo donde hace falta → decidir alcance antes de construir sobre ella.

Corre sobre el universo real (nx_empresa) o sobre los tickers pasados. **Hits de red (companyfacts + market
data)** → lo corre el OPERADOR en el server, no la consola sandboxeada. No gasta API de LLM.

    .venv/bin/python -m ops.medir_cobertura_valuacion            # todo el universo nx_empresa
    .venv/bin/python -m ops.medir_cobertura_valuacion MP OKLO    # nombres puntuales
"""
from __future__ import annotations

import sys
from collections import Counter
from datetime import date

from backend.agentes import data_pack as dp

# Métricas que miramos: ORIGINAL de contrato (RPO/anticipos) + los insumos del EV + las derivadas de la lente.
_INSUMOS_EV = ["market_cap", "liquidez", "long_term_debt", "revenue"]
_CONTRATO = ["rpo", "contract_liability"]
_LENTE = ["enterprise_value", "ev_revenue", "ev_rpo", "backlog_coverage", "valor_contratado_ajustado",
          "fcf_yield", "revenue_growth_yoy"]


def _tickers_universo() -> list[str]:
    from backend.database import session_scope
    from backend.ledger.models import NxEmpresa
    with session_scope() as s:
        return [e.ticker.upper() for e in s.query(NxEmpresa).order_by(NxEmpresa.ticker).all()]


def medir(tickers: list[str], as_of: date, *, ensamblar=dp.ensamblar) -> dict:
    """Devuelve, por ticker, el estado (COMPUTED/MISSING/NOT_APPLICABLE/ausente) de cada métrica, y el
    agregado de cobertura. `ensamblar` es inyectable para test offline."""
    filas: dict[str, dict[str, str]] = {}
    for tk in tickers:
        tk = tk.upper()
        try:
            pack = ensamblar(tk, as_of=as_of)
        except Exception as e:  # noqa: BLE001 — un nombre que falla no tumba la medición
            filas[tk] = {"__error__": str(e)[:80]}
            continue
        idx = {p.metric: p for p in pack.puntos}
        fila: dict[str, str] = {}
        for m in _INSUMOS_EV + _CONTRATO + _LENTE:
            p = idx.get(m)
            if p is None:
                fila[m] = "ausente"
            elif p.value is None:
                fila[m] = p.estado or "MISSING"
            else:
                fila[m] = p.estado or "COMPUTED"
        filas[tk] = fila
    # agregado: cuántos nombres tienen cada métrica CON valor (COMPUTED)
    n = len([t for t in filas if "__error__" not in filas[t]])
    cobertura = {}
    for m in _INSUMOS_EV + _CONTRATO + _LENTE:
        c = Counter(f.get(m, "ausente") for f in filas.values() if "__error__" not in f)
        cobertura[m] = {"computed": c.get("COMPUTED", 0), "n": n, "detalle": dict(c)}
    return {"as_of": as_of.isoformat(), "n": n, "filas": filas, "cobertura": cobertura}


def main() -> int:
    tickers = sys.argv[1:] or _tickers_universo()
    if not tickers:
        print("universo vacío — pasá tickers o poblá nx_empresa")
        return 1
    print(f"midiendo cobertura de valuación sobre {len(tickers)} nombres (hits de red)…\n")
    res = medir(tickers, date.today())
    print(f"=== COBERTURA (n={res['n']} nombres) ===")
    print(f"{'métrica':28}{'con valor':>12}{'%':>7}   detalle")
    for m, c in res["cobertura"].items():
        pct = (100 * c["computed"] / c["n"]) if c["n"] else 0
        det = " · ".join(f"{k}={v}" for k, v in sorted(c["detalle"].items()))
        print(f"{m:28}{c['computed']:>8}/{c['n']:<3}{pct:>6.0f}%   {det}")
    errores = {t: f["__error__"] for t, f in res["filas"].items() if "__error__" in f}
    if errores:
        print(f"\n{len(errores)} nombres con error:")
        for t, e in list(errores.items())[:10]:
            print(f"  {t}: {e}")
    print("\nLectura: si 'rpo' computa en pocos nombres, el backlog contratado (r7 §2/§7) sirve solo en un "
          "subconjunto → decidir alcance antes de construir el margen de seguridad sobre él.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
