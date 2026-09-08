"""Corrida real del núcleo nuevo: extrae hechos (LLM) → cachea → shadow entrada+salida.

Una llamada LLM por ticker (cacheada en data/nucleo_hechos/), reusada para entrada,
salida y el dashboard. NO ejecuta capital — es sombra: muestra qué decidiría el
núcleo nuevo vs el viejo.

Uso:
    python -m ops.correr_nucleo_real --tickers NABL          # canary
    python -m ops.correr_nucleo_real                          # todas las vivas
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback

from backend.nucleo.extractor import extraer_deterministas, extraer_hechos_llm
from backend.nucleo.shadow import HECHOS_DIR, _tickers_vivos, correr_shadow


def cachear_hechos(tickers: list[str]) -> dict:
    HECHOS_DIR.mkdir(parents=True, exist_ok=True)
    ok, fallo = [], []
    for t in tickers:
        try:
            det = extraer_deterministas(t)
            hechos = extraer_hechos_llm(t, det)
            if hechos:
                (HECHOS_DIR / f"{t.upper()}.json").write_text(
                    json.dumps(hechos, indent=2, ensure_ascii=False), encoding="utf-8")
                rev = (hechos.get("revenue") or {}).get("revenue_elegible_usd")
                print(f"  {t}: hechos OK (revenue elegible: {rev})")
                ok.append(t)
            else:
                print(f"  {t}: extractor devolvió None (LLM/EDGAR sin datos)")
                fallo.append(t)
        except Exception as e:  # noqa: BLE001
            print(f"  {t}: ERROR {e}")
            traceback.print_exc()
            fallo.append(t)
    return {"ok": ok, "fallo": fallo}


def _tabla(out: dict, modo: str):
    print(f"\n--- {modo.upper()} (núcleo nuevo vs viejo) ---")
    print(f"{'TICKER':<8} {'VIEJO':<14} {'NUEVO':<14} {'coinc':<6} detalle")
    for c in out["comparaciones"]:
        nuevo = c.get("new_decision") or c.get("new_accion")
        detalle = (c.get("new_motivo") or c.get("new_arquetipo")
                   or (f"vía {c.get('new_via')}" if c.get("new_via") else "") or "")
        coinc = {True: "sí", False: "NO", None: "—"}[c.get("coinciden")]
        print(f"{c['ticker']:<8} {str(c.get('old_accion')):<14} {str(nuevo):<14} {coinc:<6} {str(detalle)[:40]}")
    r = out["resumen"]
    ac = f"{r['tasa_acuerdo']:.0%}" if r["tasa_acuerdo"] is not None else "N/A"
    print(f"  → acuerdo {r['coinciden']}/{r['comparables']} ({ac}), sin_hechos {r['sin_hechos']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", help="Lista separada por comas (default: todas las vivas)")
    ap.add_argument("--skip-extract", action="store_true", help="No re-extraer; usar hechos cacheados")
    args = ap.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",")] if args.tickers else _tickers_vivos()
    print(f"Tickers: {tickers}\n")

    if not args.skip_extract:
        print("=== 1. Extrayendo hechos (LLM, 1 llamada/ticker) ===")
        res = cachear_hechos(tickers)
        print(f"\nExtracción: {len(res['ok'])} OK, {len(res['fallo'])} fallaron\n")

    print("=== 2. Shadow (sin ejecutar capital) ===")
    ent = correr_shadow(tickers, modo="entrada")
    sal = correr_shadow(tickers, modo="salida")
    _tabla(ent, "entrada")
    _tabla(sal, "salida")

    # Guarda el resultado para que el dashboard lo muestre rápido (sin red en el request).
    from datetime import datetime as _dt
    out_path = HECHOS_DIR.parent / "batches" / "shadow_nucleo_latest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "generado": _dt.now().isoformat(timespec="seconds"),
        "tickers": tickers,
        "entrada": ent, "salida": sal,
        "prompt_version": "extractor_hechos_v2",
    }, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\nResultado guardado: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
