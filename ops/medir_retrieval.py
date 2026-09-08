"""Mide el retrieval contra el gold set (Bloque 0b, doc 32 §5; diseño triangulado IA1+IA2).

    .venv/bin/python -m ops.medir_retrieval

Corre OFFLINE sobre los HTML crudos congelados (`data/gold/corpus/`). Reporta, por caso:
recall (¿el `_window` cubre el span gold?), CAUSA del miss (A/B/C/D), presupuesto de ventana
(chars) y precisión de región. Es un REGRESSION SEED de nombres difíciles, no un estimador de
producción: con ~N casos el IC95% es ancho → se reporta explícito para no disparar "amesetа"
sobre ruido. Los DERIVABLE/TABLE_ONLY/COVERAGE se listan aparte (no son fallas de retrieval).
"""
from __future__ import annotations

import math

from backend.nucleo.gold_retrieval import GOLD, medir_caso


def _ic95(hits: int, n: int) -> float:
    if n == 0:
        return 0.0
    p = hits / n
    return 1.96 * math.sqrt(p * (1 - p) / n) * 100


def main() -> int:
    res = [medir_caso(c) for c in GOLD]
    ev = [r for r in res if r.evaluable]
    hits = sum(1 for r in ev if r.hit)

    print("=" * 92)
    print("RETRIEVAL — gold set (offline, HTML crudo congelado)")
    print("=" * 92)
    print(f"{'CASE_ID':40} {'RES':16} {'WIN':>6} {'RP':>4} {'DIST':>4} {'SPLIT':>7}")
    print("-" * 92)
    for r in res:
        if not r.evaluable:
            continue
        marca = "HIT" if r.hit else r.motivo
        rp = f"{r.region_precision:.2f}"
        dist = "!" if r.distractor_en_ventana else ""
        print(f"{r.case_id:40} {marca:16} {r.win_chars:>6} {rp:>4} {dist:>4} {r.split:>7}")
    print("-" * 92)

    n = len(ev)
    pct = (hits / n * 100) if n else 0.0
    print(f"RECALL (evaluables): {hits}/{n} = {pct:.0f}%  (IC95 ±{_ic95(hits, n):.0f}pp — seed chico, leer con cuidado)")

    # desglose de causa de miss (accionable: A/B/C/D tienen arreglos distintos)
    causas = {}
    for r in ev:
        if not r.hit:
            causas[r.motivo] = causas.get(r.motivo, 0) + 1
    if causas:
        print("\nCausa de los misses (arreglos distintos):")
        leyenda = {
            "MISS_A_NO_ANCHOR": "A · ningún anchor cerca (vocabulario de regex incompleto)",
            "MISS_B_SPAN_TRUNC": "B · anchor cerca pero la ventana ±w no cubre el span",
            "MISS_C_CAP": "C · la región la tiró el cap de max_regs (ranker sin score)",
            "MISS_D_LOST": "D · el verbatim se perdió en la extracción HTML→texto (tabla/celda)",
        }
        for k, v in sorted(causas.items(), key=lambda x: -x[1]):
            print(f"  {v:>2}  {leyenda.get(k, k)}")

    # no-evaluables: separan límite de COBERTURA / definición de tarea de la falla de retrieval
    no_ev = [r for r in res if not r.evaluable]
    if no_ev:
        print("\nNo evaluables (no cuentan como falla de retrieval):")
        for r in no_ev:
            print(f"  {r.case_id}: {r.motivo}")

    if any(r.distractor_en_ventana for r in ev):
        print("\n! = la ventana trae un pasaje plausible-pero-falso → riesgo de que el LLM lo cite (medir P(correcto|HIT)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
