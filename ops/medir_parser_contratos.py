"""Medición del parser de contratos (Bloque 2, r9a #3d) contra el gold set auditado.

El parser (`backend.agentes.contratos.clasificar_contrato`) y el verificador ciego del gold set
comparten prompt y modelo → la auditoría (`ops/auditar_gold_contratos.py`) YA corrió la predicción
del parser sobre los 35. Por default esta medición REUSA esas predicciones (`auditoria.verificador.label`)
para no re-gastar presupuesto; con `--live` re-corre el parser de verdad.

Reporta: matriz de confusión (gold × parser), accuracy, y precision/recall de la clase que importa
(cuenta = firme|condicional, el contrato de ingresos que dispara bonus/carril).

Uso:
    .venv/bin/python -m ops.medir_parser_contratos [--live]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

GOLD = Path("tests/gold_contratos/gold_contratos.json")
CLASES = ("firme", "condicional", "no_cuenta")


def _cuenta(label: str | None) -> bool:
    return label in ("firme", "condicional")


def medir(live: bool = False) -> dict:
    d = json.loads(GOLD.read_text())
    pares = []   # (gold, pred)
    costo = 0.0
    if live:
        from backend.agentes.contratos import clasificar_contrato
    for ents in d["nombres"].values():
        for e in ents:
            gold = e.get("label")
            if live:
                c = clasificar_contrato(e.get("excerpt", ""), items=e.get("items"), fecha=e.get("fecha"))
                pred = c.label
            else:
                pred = (e.get("auditoria", {}).get("verificador") or {}).get("label")
            if gold and pred:
                pares.append((gold, pred))

    conf: dict[tuple[str, str], int] = defaultdict(int)
    for g, p in pares:
        conf[(g, p)] += 1
    n = len(pares)
    aciertos = sum(1 for g, p in pares if g == p)
    # métricas de la clase 'cuenta' (contrato de ingresos)
    tp = sum(1 for g, p in pares if _cuenta(g) and _cuenta(p))
    fp = sum(1 for g, p in pares if not _cuenta(g) and _cuenta(p))
    fn = sum(1 for g, p in pares if _cuenta(g) and not _cuenta(p))
    prec = tp / (tp + fp) if (tp + fp) else 1.0
    rec = tp / (tp + fn) if (tp + fn) else 1.0

    print(f"n={n}  ·  accuracy={aciertos/n:.1%}  ·  fuente={'LIVE' if live else 'auditoría cacheada'}")
    print("\nmatriz de confusión (filas=gold, cols=parser):")
    print("            " + "".join(f"{c:>13}" for c in CLASES))
    for g in CLASES:
        fila = "".join(f"{conf.get((g, p), 0):>13}" for p in CLASES)
        print(f"{g:>12}{fila}")
    print(f"\nclase 'cuenta' (firme|condicional):  precision={prec:.0%}  recall={rec:.0%}  "
          f"(tp={tp} fp={fp} fn={fn})")
    dist_gold = Counter(g for g, _ in pares)
    print(f"\ndistribución gold: {dict(dist_gold)}  → la clase útil es RALA (el parser filtra 'es revenue')")
    return {"n": n, "accuracy": aciertos / n if n else 0.0, "precision": prec, "recall": rec, "costo": costo}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="re-corre el parser (gasta LLM) en vez de reusar la auditoría")
    args = ap.parse_args()
    medir(live=args.live)
