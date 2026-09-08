"""One-shot: re-corre Analista + Portfolio+Juez sobre los 12 de WL_Prioritaria.

Se salta la capa HTTP/auth — llama al pipeline directamente.
Imprime tabla final: score antes/después, estado, asimetría, recomendación.
"""
from __future__ import annotations

import time
import traceback

from backend.agents.analista import ejecutar_analisis
from backend.agents.analista_writer import escribir_ficha
from backend.agents.recomendacion_runner import ejecutar_recomendacion
from backend.database import session_scope
from backend.models import Ficha, Recomendacion


TICKERS = [
    "ALAB", "VRNS", "CRDO", "VRT", "RBRK", "RKLB",
    "COHR", "CVLT", "QLYS", "KLIC", "UEC", "ALGM",
]


def main() -> None:
    resultados: list[dict] = []
    t_start = time.time()

    for i, ticker in enumerate(TICKERS, 1):
        print(f"\n[{i}/{len(TICKERS)}] {ticker} — arrancando…", flush=True)
        t0 = time.time()
        try:
            with session_scope() as s:
                f = s.query(Ficha).filter_by(ticker=ticker).first()
                score_antes = f.score_vigente if f else None
                estado_antes = f.estado if f else None

            result = ejecutar_analisis(ticker, dry_run=False)
            precio = result["context"].get("precio_actual")

            wr = escribir_ficha(
                ticker=ticker,
                output=result["output"],
                context_dict=result["context"],
                precio_actual=precio,
            )

            try:
                rec = ejecutar_recomendacion(ticker)
            except Exception as e:  # noqa: BLE001
                rec = {"accion": "ERROR", "error": str(e)}

            with session_scope() as s:
                rec_row = (
                    s.query(Recomendacion)
                    .filter_by(ticker=ticker)
                    .order_by(Recomendacion.timestamp_juez.desc())
                    .first()
                )
                asim = rec_row.asimetria_vigente if rec_row else None
                reglas = rec_row.reglas_verificadas if rec_row else None

            resultados.append({
                "ticker": ticker,
                "score_antes": score_antes,
                "score_nuevo": wr.score_nuevo,
                "estado_antes": estado_antes,
                "estado_nuevo": wr.estado_sugerido,
                "precio": precio,
                "asimetria": asim,
                "reglas": reglas,
                "accion_rec": rec.get("accion", "N/A"),
                "drift": wr.drift_detectado,
                "dt_s": round(time.time() - t0, 1),
            })
            print(
                f"  OK — score {score_antes} → {wr.score_nuevo} | estado {estado_antes} → {wr.estado_sugerido} "
                f"| precio ${precio} | asim {asim} | rec {rec.get('accion','N/A')} | {resultados[-1]['dt_s']}s",
                flush=True,
            )

        except Exception as e:  # noqa: BLE001
            print(f"  FALLO: {type(e).__name__}: {e}", flush=True)
            traceback.print_exc()
            resultados.append({
                "ticker": ticker,
                "error": f"{type(e).__name__}: {e}",
                "dt_s": round(time.time() - t0, 1),
            })

    print("\n" + "=" * 120)
    print("RESUMEN BARRIDA WL_PRIORITARIA")
    print("=" * 120)
    print(f"{'Ticker':<6} {'Antes':>6} {'→':^3} {'Nuevo':>6} {'Δ':>6} | "
          f"{'Estado antes':<18} → {'Estado nuevo':<18} | {'Precio':>8} {'Asim':>6} {'Rec':<14} {'Drift':<6} {'Seg':>5}")
    print("-" * 120)
    for r in resultados:
        if "error" in r:
            print(f"{r['ticker']:<6}  ERROR: {r['error']}  ({r['dt_s']}s)")
            continue
        delta = (r["score_nuevo"] or 0) - (r["score_antes"] or 0)
        print(
            f"{r['ticker']:<6} {str(r['score_antes']):>6} {'→':^3} {str(r['score_nuevo']):>6} {delta:>+6.2f} | "
            f"{str(r['estado_antes']):<18} → {str(r['estado_nuevo']):<18} | "
            f"${str(r['precio']):>7} {str(r['asimetria']):>6} {str(r['accion_rec']):<14} {str(r['drift']):<6} {r['dt_s']:>5}"
        )
    dt_total = round(time.time() - t_start, 1)
    print("-" * 120)
    print(f"Total: {len(resultados)} tickers en {dt_total}s ({round(dt_total/60,1)} min)")


if __name__ == "__main__":
    main()
