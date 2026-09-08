"""One-shot: re-corre Analista + Portfolio+Juez sobre las 14 fichas activas
(Portfolio_Activo + WL_Prioritaria) con prompt v2 y Sprints A-E aplicados.

Imprime tabla final con cambios de score, estado, asimetría, recomendación.
"""
from __future__ import annotations

import time
import traceback

from backend.agents.analista import ejecutar_analisis
from backend.agents.analista_writer import escribir_ficha
from backend.agents.recomendacion_runner import ejecutar_recomendacion
from backend.database import session_scope
from backend.models import EstadoFicha, Ficha, Recomendacion


def cargar_tickers_activos() -> list[str]:
    with session_scope() as s:
        rows = (
            s.query(Ficha)
            .filter(Ficha.estado.in_([
                EstadoFicha.PORTFOLIO_ACTIVO.value,
                EstadoFicha.WL_PRIORITARIA.value,
                EstadoFicha.BUCKET_EXPLORATORIO.value,
            ]))
            .order_by(Ficha.estado, Ficha.ticker)
            .all()
        )
        return [f.ticker for f in rows]


def main() -> None:
    tickers = cargar_tickers_activos()
    print(f"Re-evaluando {len(tickers)} fichas activas (Portfolio + WLP + Bucket)…\n")

    resultados: list[dict] = []
    t_start = time.time()

    for i, ticker in enumerate(tickers, 1):
        print(f"\n[{i}/{len(tickers)}] {ticker} — arrancando…", flush=True)
        t0 = time.time()
        try:
            with session_scope() as s:
                f = s.query(Ficha).filter_by(ticker=ticker).first()
                score_antes = f.score_vigente if f else None
                estado_antes = f.estado if f else None
                cfj_antes = f.confidence_y_fuentes_json if f else None

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
                f2 = s.query(Ficha).filter_by(ticker=ticker).first()
                cfj_nuevo = f2.confidence_y_fuentes_json if f2 else None

            # ¿Hay claims centrales con confidence Baja? (señal de bloqueo Portfolio v4.2)
            centrales_baja = []
            if cfj_nuevo:
                for c in (1, 2, 3, 4, 6):
                    info = cfj_nuevo.get(str(c)) or {}
                    if (info.get("confidence") or "").lower() == "baja":
                        centrales_baja.append(c)

            resultados.append({
                "ticker": ticker,
                "score_antes": score_antes,
                "score_nuevo": wr.score_nuevo,
                "estado_antes": estado_antes,
                "estado_nuevo": wr.estado_sugerido,
                "precio": precio,
                "asimetria": asim,
                "accion_rec": rec.get("accion", "N/A"),
                "centrales_baja": centrales_baja,
                "tenia_v2": cfj_antes is not None,
                "tiene_v2_ahora": cfj_nuevo is not None,
                "dt_s": round(time.time() - t0, 1),
            })
            extra = ""
            if centrales_baja:
                extra = f" | confidence_baja_centrales={centrales_baja}"
            print(
                f"  OK — score {score_antes} → {wr.score_nuevo} | estado {estado_antes} → {wr.estado_sugerido} "
                f"| precio ${precio} | asim {asim} | rec {rec.get('accion','N/A')} | {resultados[-1]['dt_s']}s{extra}",
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

    print("\n" + "=" * 130)
    print("RESUMEN BARRIDA — 14 FICHAS ACTIVAS (v4.2 prompt v2 con confidence + fuente_nivel)")
    print("=" * 130)
    print(f"{'Ticker':<6} {'Antes':>6} {'→':^3} {'Nuevo':>6} {'Δ':>6} | "
          f"{'Estado antes':<18} → {'Estado nuevo':<18} | {'Precio':>8} {'Asim':>6} {'Rec':<14} {'CfBaja':<10} {'Seg':>5}")
    print("-" * 130)
    for r in resultados:
        if "error" in r:
            print(f"{r['ticker']:<6}  ERROR: {r['error']}  ({r['dt_s']}s)")
            continue
        delta = (r["score_nuevo"] or 0) - (r["score_antes"] or 0)
        cfb = ",".join(str(c) for c in r["centrales_baja"]) if r["centrales_baja"] else "-"
        print(
            f"{r['ticker']:<6} {str(r['score_antes']):>6} {'→':^3} {str(r['score_nuevo']):>6} {delta:>+6.2f} | "
            f"{str(r['estado_antes']):<18} → {str(r['estado_nuevo']):<18} | "
            f"${str(r['precio']):>7} {str(r['asimetria']):>6} {str(r['accion_rec']):<14} {cfb:<10} {r['dt_s']:>5}"
        )
    dt_total = round(time.time() - t_start, 1)
    print("-" * 130)
    print(f"Total: {len(resultados)} tickers en {dt_total}s ({round(dt_total/60,1)} min)")


if __name__ == "__main__":
    main()
