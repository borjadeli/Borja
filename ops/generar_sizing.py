"""Precomputa el ledger de SIZING del bucket growth/BURDEN (doc 47, Fase 1) → data/sizing_book.json.

    .venv/bin/python -m ops.generar_sizing [TICKER ...]

Corre la superficie de sizing (`sizing_burden`) sobre los nombres comerciales owner-FCF<0 y persiste el techo (cap)
que el determinismo pone a cada uno, con el desglose de factores. La vista /sizing lo lee (patrón de ops.generar_hoja:
cálculo caro → JSON cacheado). NO es el tamaño final: el PM elige dentro del cap (doc 39).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from backend.database import session_scope
from backend.nucleo import politica, ruteo
from backend.nucleo import sizing_burden as SB
from backend.nucleo.hoja_evidencia import hoja
from backend.services import edgar
from backend.utils import get_logger, utcnow

log = get_logger(__name__)

# Bucket por defecto: los nombres growth/BURDEN ya extraídos. Overridable por argv.
MUESTRA = ["S", "NET", "VRNS", "PL", "KTOS", "LEU", "SDGR", "AAOI", "RKLB"]
OUT = Path(__file__).resolve().parent.parent / "data" / "sizing_book.json"


def _fila(session, t: str) -> dict | None:
    fin = edgar.get_financials_quarterly(t, periodos=16)
    q = fin.quarters
    gp = [x.get("gross_profit") for x in q]
    opex = [(x["gross_profit"] - x["operating_income"])
            if (x.get("gross_profit") is not None and x.get("operating_income") is not None) else None
            for x in q]
    dsh = [x for x in (fin.diluted_shares_qtrs or []) if x]
    rev = fin.revenue_ttm
    gp_ttm = sum([x for x in gp if x is not None][-4:]) if any(x is not None for x in gp) else None
    gm = (gp_ttm / rev) if (rev and gp_ttm is not None) else None
    apal = ruteo.apalancamiento_operativo(gp, opex, lag_q=politica.APAL_LAG_Q)
    gpv = [x for x in gp if x is not None]
    ggps = None
    if len(gpv) >= 12 and len(dsh) >= 8 and dsh[-8] and dsh[-1] and sum(gpv[-12:-8]) > 0:
        ggps = ((sum(gpv[-4:]) / dsh[-1]) / (sum(gpv[-12:-8]) / dsh[-8])) ** 0.5 - 1
    h = hoja(t, session=session)
    burden = getattr(h, "burden_gp", None)
    g = getattr(h, "g_D_reverse", None)
    T = SB.t_fade(burden, g)
    sb = SB.size_burden(t, t_star=T, gross_margin=gm, apal_lag=apal, g_gp_por_accion=ggps,
                        fcf_pre_sbc=fin.fcf_ttm, burden=burden, runway_meses=48)
    f = sb.factores
    return {
        "t": t, "dest": "carril" if sb.a_carril else "hb",
        "rev_m": round(rev / 1e6) if rev else None,
        "burden": round(burden, 1) if burden is not None else None,
        "g": round(g, 3) if g is not None else None,
        "T": round(T, 1) if T is not None else None,
        "gm": round(gm, 3) if gm is not None else None,
        "apal": round(apal, 2) if apal is not None else None,
        "ggps": round(ggps, 3) if ggps is not None else None,
        "fcf_pre_m": round((fin.fcf_ttm or 0) / 1e6),
        "f_val": f.get("f_val"), "q_gm": f.get("q_gm"), "q_apal": f.get("q_apal"),
        "q_ps": f.get("q_ps"), "merito": f.get("merito"),
        "cap": sb.size, "carril": sb.a_carril, "motivo": sb.motivo,
    }


def main(argv: list[str]) -> int:
    tickers = [t.upper() for t in argv] or MUESTRA
    rows = []
    with session_scope() as s:
        for t in tickers:
            try:
                fila = _fila(s, t)
                if fila:
                    rows.append(fila)
                    log.info("sizing %s: cap=%.1f%% dest=%s", t, fila["cap"] * 100, fila["dest"])
            except Exception as e:  # noqa: BLE001
                log.warning("sizing %s: %s", t, e)
    # orden: libro duro por cap desc, carril al final
    rows.sort(key=lambda r: (r["dest"] == "carril", -(r["cap"] or 0)))
    payload = {
        "generado": utcnow().isoformat(),
        "politica": politica.VERSION,
        "cap_floor": politica.CAP_FLOOR_BURN,
        "cap_max": politica.CAP_BURN_BUCKET,
        "cluster_cap": politica.CLUSTER_CAP_MULT * politica.CAP_BURN_BUCKET,
        "rows": rows,
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"sizing_book.json: {len(rows)} nombres → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
