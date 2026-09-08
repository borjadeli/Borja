"""Re-correr Analista sobre los 24 borderline (score 5.0-5.99) con prompt v2.

Foco: descubrir candidatos ocultos para Portfolio. Si alguno sube a ≥6 con
asimetría >= 2.0x + concentración libre + sin Confidence Baja en claim central +
sin CRR Alto/Crítico, queda elegible para entrar.

Costo estimado: ~$10 (24 × ~$0.40).
"""
from __future__ import annotations

import time
import traceback

from backend.agents.analista import ejecutar_analisis
from backend.agents.analista_writer import escribir_ficha
from backend.agents.recomendacion_runner import ejecutar_recomendacion
from backend.database import session_scope
from backend.models import Ficha, Recomendacion


# Tickers con score 5.0-5.99 (excluyendo S, TENB, LEU ya tradeadas).
# NABL está en Ciberseguridad, ya bloqueado por concentración aun si sube — incluido igual
# para tener data fresca de la ficha.
TICKERS_BORDERLINE = [
    # 5.7-5.99 (más cerca)
    "AEIS", "CGNX", "LITE", "CW", "RKLB", "AVAV", "LUNR", "MP", "NABL",
    "MTSI", "UEC", "BWXT",
    # 5.0-5.69
    "CLS", "SYM", "DRS", "KTOS", "TER", "TMC",
    "AAOI", "CACI", "PL", "MRCY", "SAIC", "RDW",
]


def main() -> None:
    print(f"Re-evaluando {len(TICKERS_BORDERLINE)} fichas borderline con prompt v2…\n")

    resultados: list[dict] = []
    t_start = time.time()

    for i, ticker in enumerate(TICKERS_BORDERLINE, 1):
        print(f"\n[{i}/{len(TICKERS_BORDERLINE)}] {ticker}", flush=True)
        t0 = time.time()
        try:
            with session_scope() as s:
                f = s.query(Ficha).filter_by(ticker=ticker).first()
                if f is None:
                    print(f"  SKIP — no existe", flush=True)
                    continue
                score_antes = f.score_vigente
                estado_antes = f.estado
                sector = f.sector

            result = ejecutar_analisis(ticker, dry_run=False)
            precio = result["context"].get("precio_actual")
            wr = escribir_ficha(
                ticker=ticker, output=result["output"],
                context_dict=result["context"], precio_actual=precio,
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
                cfj = f2.confidence_y_fuentes_json if f2 else None

            centrales_baja = []
            if cfj:
                for c in (1, 2, 3, 4, 6):
                    info = cfj.get(str(c)) or {}
                    if (info.get("confidence") or "").lower() == "baja":
                        centrales_baja.append(c)

            resultados.append({
                "ticker": ticker, "sector": sector,
                "score_antes": score_antes, "score_nuevo": wr.score_nuevo,
                "estado_antes": estado_antes, "estado_nuevo": wr.estado_sugerido,
                "precio": precio, "asimetria": asim,
                "accion_rec": rec.get("accion", "N/A"),
                "centrales_baja": centrales_baja,
                "dt_s": round(time.time() - t0, 1),
            })
            delta = (wr.score_nuevo or 0) - (score_antes or 0)
            print(
                f"  score {score_antes} → {wr.score_nuevo} ({delta:+.2f}) | "
                f"estado {estado_antes} → {wr.estado_sugerido} | "
                f"asim {asim} | rec {rec.get('accion','N/A')} | {round(time.time()-t0,1)}s",
                flush=True,
            )
            if (wr.score_nuevo or 0) >= 6.0:
                print(f"  *** SCORE >=6 — candidato a evaluar para Portfolio ***", flush=True)

        except Exception as e:  # noqa: BLE001
            print(f"  FALLO: {type(e).__name__}: {e}", flush=True)
            traceback.print_exc()
            resultados.append({"ticker": ticker, "error": str(e), "dt_s": round(time.time()-t0,1)})

    # Resumen
    print("\n" + "=" * 130)
    print("RESUMEN BORDERLINE — score antes/nuevo + acción del Portfolio agent")
    print("=" * 130)
    print(f"{'Ticker':<6} {'Sector':<28} {'Antes':>6} {'→':^3} {'Nuevo':>6} {'Δ':>6} | "
          f"{'Estado':<18} {'Asim':>6} {'Rec':<14} {'CfBaja':<8}")
    print("-" * 130)

    # Ordenar por delta de score (mayores subidas primero)
    sorted_res = sorted(
        [r for r in resultados if "error" not in r],
        key=lambda r: -((r["score_nuevo"] or 0) - (r["score_antes"] or 0)),
    )
    for r in sorted_res:
        delta = (r["score_nuevo"] or 0) - (r["score_antes"] or 0)
        cfb = ",".join(str(c) for c in r["centrales_baja"]) if r["centrales_baja"] else "-"
        marker = " ⭐" if (r["score_nuevo"] or 0) >= 6.0 else ""
        print(
            f"{r['ticker']:<6} {str(r['sector'])[:28]:<28} "
            f"{str(r['score_antes']):>6} {'→':^3} {str(r['score_nuevo']):>6} {delta:>+6.2f} | "
            f"{str(r['estado_nuevo']):<18} {str(r['asimetria']):>6} "
            f"{str(r['accion_rec']):<14} {cfb:<8}{marker}"
        )

    # Errores
    errores = [r for r in resultados if "error" in r]
    if errores:
        print("\n--- ERRORES ---")
        for r in errores:
            print(f"  {r['ticker']}: {r['error']}")

    # Candidatos finales
    candidatos = [r for r in sorted_res if (r["score_nuevo"] or 0) >= 6.0 and not r["centrales_baja"]]
    print("\n" + "=" * 130)
    print(f"CANDIDATOS A PORTFOLIO (score ≥6 + sin Confidence Baja en claim central): {len(candidatos)}")
    print("=" * 130)
    for r in candidatos:
        print(f"  ⭐ {r['ticker']:6s} score={r['score_nuevo']} asim={r['asimetria']} rec={r['accion_rec']}")

    dt_total = round(time.time() - t_start, 1)
    print(f"\nTotal: {len(resultados)} tickers en {dt_total}s ({round(dt_total/60,1)} min)")


if __name__ == "__main__":
    main()
