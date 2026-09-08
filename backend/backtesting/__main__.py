"""CLI del backtest.

Uso:
    python -m backend.backtesting            # mock (gratis)
    python -m backend.backtesting --real     # llama a Claude (~$3.50)
    python -m backend.backtesting --tickers=COHR,VRT   # solo estos
    python -m backend.backtesting --html     # imprime HTML del reporte
"""
from __future__ import annotations

import argparse
import sys

from backend.backtesting.runner import run_backtest
from backend.backtesting.report import render_report_html, confusion_matrix


def main():
    ap = argparse.ArgumentParser(description="Backtest del sistema BORJA")
    ap.add_argument("--real", action="store_true", help="Correr con LLM real (costoso ~$3.50)")
    ap.add_argument("--tickers", default="", help="Lista separada por coma, filtra el dataset")
    ap.add_argument("--html", action="store_true", help="Imprimir HTML del reporte")
    args = ap.parse_args()

    tickers_filter = [t.strip() for t in args.tickers.split(",") if t.strip()] if args.tickers else None
    mock = not args.real

    if not mock:
        print("ATENCIÓN: modo real — consumirá ~$3.50 en LLM de Anthropic (Opus 4.7).")
        print("Continuando en 3s — Ctrl+C para cancelar.")
        import time
        time.sleep(3)

    report = run_backtest(mock=mock, tickers_filter=tickers_filter, persistir=True)

    if args.html:
        import json
        from dataclasses import asdict
        data = asdict(report)
        data["resultados"] = [asdict(r) for r in report.resultados]
        print(render_report_html(data))
        return

    # Texto simple para stdout
    status = "PASS ✓" if report.gate_passed else "FAIL ✗"
    print(f"\n{'=' * 60}")
    print(f"BACKTEST {'MOCK' if mock else 'REAL'} — {status}")
    print(f"{'=' * 60}")
    print(f"Correctos:            {report.correctos}/{report.total} ({report.pass_rate*100:.1f}%)")
    print(f"Winners identificados: {report.winners_correct}/{report.winners_total}")
    print(f"Losers rechazados:     {report.losers_correct}/{report.losers_total}")
    print(f"Costo LLM total:       ${report.cost_usd_total}")
    if report.gate_razones:
        print("\nMotivos de falla del gate:")
        for m in report.gate_razones:
            print(f"  - {m}")
    print("\nDetalle por ticker:")
    for r in report.resultados:
        icon = "OK  " if r.correcto else "FAIL"
        motivo = f" — {r.motivo_fail}" if r.motivo_fail else (f" — ERROR: {r.error}" if r.error else "")
        print(f"  [{icon}] {r.ticker:5} {r.outcome_esperado:6} score={r.score_resultante} estado={r.estado_sugerido}{motivo}")

    sys.exit(0 if report.gate_passed else 1)


if __name__ == "__main__":
    main()
