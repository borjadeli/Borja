"""Ciclo de resolución de predicciones (doc 74) — entrypoint del operador. NO gasta API.

Al vencer la fecha de un falsador o de un escenario bull hay que RESOLVERLO; recién ahí el Brier
(`ledger.metricas()`) mide si el análisis calibra. Este op lista las pendientes y las resuelve.

Uso:
  .venv/bin/python -m ops.resolucion                      # lista predicciones vencidas sin resolver + Brier
  .venv/bin/python -m ops.resolucion --silencio           # marca falsadores vencidos SIN evidencia = disparado
  .venv/bin/python -m ops.resolucion --resolver <id> <falsador|bull> <estado> [--nota "..."]
      estados: falsador = disparado|no_disparado · bull = materializado|no_materializado
"""
from __future__ import annotations

import argparse
from datetime import date

from backend.agentes.ledger_decisiones import LedgerDecisiones
from backend.agentes.resolucion import aplicar_silencio_falsadores, pendientes, render_pendientes, resolver


def _brier(ld: LedgerDecisiones) -> str:
    m = ld.metricas()
    fals = f"falsadores: n={m.n_resueltos} brier={m.brier} hit_rate={m.hit_rate_falsadores}"
    bull = f"bull: n={m.n_bull_resueltos} brier_bull={m.brier_bull}"
    return f"CALIBRACIÓN (proyección del ledger)\n  · {fals}\n  · {bull}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Ciclo de resolución de predicciones (doc 74)")
    ap.add_argument("--silencio", action="store_true",
                    help="regla IA2: falsadores vencidos sin evidencia → disparado (abre revisión del nombre)")
    ap.add_argument("--resolver", nargs=3, metavar=("ID", "TIPO", "ESTADO"),
                    help="resolución explícita con evidencia")
    ap.add_argument("--nota", default=None, help="nota de la resolución explícita")
    args = ap.parse_args()

    ld = LedgerDecisiones()
    hoy = date.today()

    if args.resolver:
        did, tipo, estado = args.resolver
        resolver(ld, did, tipo, estado, nota=args.nota)
        print(f"resuelto: {did} [{tipo}] → {estado}")
        print(_brier(ld))
        return 0

    if args.silencio:
        alertas = aplicar_silencio_falsadores(ld, hoy)
        if not alertas:
            print("sin falsadores vencidos para marcar por silencio.")
        else:
            print(f"{len(alertas)} falsador(es) marcados DISPARADOS por silencio (revisión abierta):")
            for a in alertas:
                print(f"  · {a}")
        print(_brier(ld))
        return 0

    print(render_pendientes(pendientes(ld, hoy)))
    print()
    print(_brier(ld))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
