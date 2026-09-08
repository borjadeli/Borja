"""Shadow-runner CLI — núcleo nuevo (rediseño) vs Portfolio viejo, lado a lado.

Corre el núcleo determinista nuevo EN SOMBRA contra el Portfolio viejo sobre las
fichas vivas y compara las decisiones de ENTRADA. No ejecuta capital. Es el gate
de corte de Fase 1: cuando la tasa de acuerdo / PASS_RATE valide el núcleo nuevo,
se le corta el paso al score viejo.

Uso:
    # Todas las fichas vivas, usando hechos override de data/nucleo_hechos/
    python -m ops.shadow_nucleo

    # Tickers explícitos
    python -m ops.shadow_nucleo --tickers NABL,LITE,MTSI

    # Llamar al extractor LLM cuando no hay override (GASTA API)
    python -m ops.shadow_nucleo --tickers NABL --usar-llm

Output: tabla por ticker (viejo vs nuevo + coinciden) + resumen, y JSON en
data/batches/shadow_<timestamp>.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from backend.nucleo.shadow import clasificar_posiciones_vivas, correr_shadow

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "batches"


def _fmt_bool(b):
    return {True: "sí", False: "no", None: "—"}[b]


def main() -> int:
    ap = argparse.ArgumentParser(description="Shadow-runner núcleo nuevo vs Portfolio viejo")
    ap.add_argument("--tickers", help="Lista separada por comas (default: todas las fichas vivas)")
    ap.add_argument("--usar-llm", action="store_true",
                    help="Si no hay override, llama al extractor LLM (gasta API)")
    ap.add_argument("--modo", choices=["entrada", "salida"], default="entrada",
                    help="entrada = gate+mérito vs score; salida = 5 vías vs rotación")
    ap.add_argument("--clasificar", action="store_true",
                    help="Solo clasifica el arquetipo de las posiciones vivas (riesgo migración §6.1)")
    args = ap.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",")] if args.tickers else None

    if args.clasificar:
        print(f"\n{'TICKER':<8} {'ARQUETIPO':<14} fuente")
        print("-" * 50)
        for c in clasificar_posiciones_vivas(usar_llm=args.usar_llm):
            print(f"{c['ticker']:<8} {c['arquetipo']:<14} {c['fuente_hechos']}")
        return 0

    out = correr_shadow(tickers, usar_llm=args.usar_llm, modo=args.modo)
    r = out["resumen"]
    print(f"\n=== SHADOW {args.modo.upper()} ===")

    print(f"\n{'TICKER':<8} {'VIEJO':<14} {'NUEVO':<14} {'coinc':<6} detalle")
    print("-" * 80)
    for c in out["comparaciones"]:
        nuevo = c.get("new_decision") or c.get("new_accion")
        detalle = (c.get("new_motivo") or c.get("new_arquetipo")
                   or (f"vía {c.get('new_via')}" if c.get("new_via") else "") or "")
        print(f"{c['ticker']:<8} {str(c.get('old_accion')):<14} {str(nuevo):<14} "
              f"{_fmt_bool(c.get('coinciden')):<6} {str(detalle)[:36]}")

    acuerdo = f"{r['tasa_acuerdo']:.0%}" if r["tasa_acuerdo"] is not None else "N/A"
    print("-" * 80)
    print(f"Total={r['total']}  Comparables={r['comparables']}  "
          f"Acuerdo={r['coinciden']}/{r['comparables']} ({acuerdo})  "
          f"Discrepan={r['discrepan']}  Sin hechos={r['sin_hechos']}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    path = OUT_DIR / f"shadow_{ts}.json"
    path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"\nJSON: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
