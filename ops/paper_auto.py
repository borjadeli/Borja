"""Ciclo de trading AUTOMÁTICO en paper del núcleo nuevo (sin confirmación humana).

Plata simulada, libro propio del núcleo nuevo. Lee los hechos cacheados
(data/nucleo_hechos/), corre el núcleo, y ejecuta compras/ventas en el libro paper
(data/nucleo_paper/libro.json). NO toca el sistema viejo ni capital real.

Uso:
    python -m ops.paper_auto                 # ciclo sobre todas las fichas vivas
    python -m ops.paper_auto --tickers NABL,VRNS,S
    python -m ops.paper_auto --dry-run       # muestra qué haría, no persiste
"""
from __future__ import annotations

import argparse
import sys

from backend.seleccion.universo import tickers_vivos as _tickers_vivos
from backend.seleccion import paper_trader as pt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", help="Lista separada por comas (default: fichas vivas)")
    ap.add_argument("--dry-run", action="store_true", help="No persistir; solo mostrar")
    args = ap.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",")] if args.tickers else _tickers_vivos()
    print(f"Tickers: {len(tickers)} | construyendo evaluaciones desde hechos cacheados...")
    evaluaciones = pt.evaluaciones_desde_cache(tickers)
    print(f"Evaluaciones: {len(evaluaciones)} "
          f"({sum(1 for e in evaluaciones if e.get('decision')=='candidata')} candidatas)\n")

    libro = pt.cargar_libro()
    print(f"Libro paper ANTES: {len(libro.posiciones)} posiciones, {libro.invertido():.0%} invertido")

    r = pt.correr_ciclo(evaluaciones, libro=libro, persistir=not args.dry_run)

    print(f"\n=== CICLO {'(DRY-RUN)' if args.dry_run else 'EJECUTADO'} ===")
    for v in r["ventas"]:
        print(f"  VENDER  {v['ticker']:<7} (vía {v.get('via')}, {v['sizing']:.0%})")
    for v in r["recortes"]:
        print(f"  RECORTAR {v['ticker']:<7} {v['de']:.0%} → {v['a']:.0%}")
    for t in r.get("topeos", []):
        print(f"  TOPEAR  {t['ticker']:<7} {t['de']:.0%} → {t['a']:.0%} "
              f"(+{t['incremento']:.0%}, mérito {t['merito']:.1f})")
    for c in r["compras"]:
        print(f"  COMPRAR {c['ticker']:<7} {c['sizing']:.0%} (mérito {c['merito']:.1f}, {c['arquetipo']})")
    if not (r["ventas"] or r["recortes"] or r.get("topeos") or r["compras"]):
        print("  (sin operaciones este ciclo)")

    print(f"\nLibro paper DESPUÉS: {r['n_posiciones']} posiciones, {r['invertido']:.0%} invertido")
    if not args.dry_run:
        print(f"Guardado en {pt.LIBRO_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
