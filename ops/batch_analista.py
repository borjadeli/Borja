"""Batch genérico del Analista — componible, reusable.

Casos de uso:

    # Tickers explícitos (crea ficha en Universo si no existe)
    python -m ops.batch_analista --tickers AAPL,MSFT,NVDA

    # Por estado (múltiple)
    python -m ops.batch_analista --estado Portfolio_Activo --estado WL_Prioritaria

    # Por sector
    python -m ops.batch_analista --sector "AI infra — Fotónica + conectividad"

    # Por rango de score
    python -m ops.batch_analista --score-min 5.5 --score-max 6.5

    # Excluir los ya evaluados hace <N días (anti-redundancia)
    python -m ops.batch_analista --estado WL_Prioritaria --excluir-evaluados-hace 7

    # Combinable
    python -m ops.batch_analista --sector "Defensa" --score-min 5.5 --score-max 6.5

    # Dry-run: solo estimar costo sin gastar API
    python -m ops.batch_analista --tickers AAPL,MSFT --solo-estimar-costo

Output:
- Stdout: progreso por ticker + tabla final
- JSON guardado en data/batches/batch_<timestamp>.json
- Cada call queda en llm_calls + decision_journal
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import or_

from backend.agents.analista import ejecutar_analisis
from backend.agents.analista_writer import escribir_ficha
from backend.agents.recomendacion_runner import ejecutar_recomendacion
from backend.database import session_scope
from backend.models import EstadoFicha, Ficha, Recomendacion


COSTO_PROMEDIO_USD = 0.40  # Opus 4.7 con cache, observado en producción


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Batch Analista genérico — filtros componibles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--tickers", default="",
        help="Lista separada por coma. Ej: AAPL,MSFT. Si no existe la ficha, se crea.",
    )
    p.add_argument(
        "--estado", action="append", default=[],
        help="Filtrar por estado. Repetible. Ej: --estado Portfolio_Activo --estado WL_Prioritaria",
    )
    p.add_argument(
        "--sector", action="append", default=[],
        help="Filtrar por sector. Repetible.",
    )
    p.add_argument(
        "--score-min", type=float, default=None,
        help="Score mínimo (inclusivo)",
    )
    p.add_argument(
        "--score-max", type=float, default=None,
        help="Score máximo (inclusivo)",
    )
    p.add_argument(
        "--excluir-evaluados-hace", type=int, default=0,
        help="Excluir fichas con fecha_ultimo_deep_research <N días (default 0 = sin filtro).",
    )
    p.add_argument(
        "--sector-default-nuevo", default="(sin asignar)",
        help="Sector que se asigna a tickers nuevos creados.",
    )
    p.add_argument(
        "--solo-estimar-costo", action="store_true",
        help="Imprime cuántos tickers + costo estimado y sale (sin llamar al LLM).",
    )
    p.add_argument(
        "--max-tickers", type=int, default=None,
        help="Cap de seguridad (corta la lista). Útil con filtros amplios.",
    )
    p.add_argument(
        "--output-dir", default="data/batches",
        help="Carpeta donde guardar el resumen JSON.",
    )
    return p.parse_args()


def _crear_ficha_si_no_existe(s, ticker: str, sector_default: str) -> Ficha:
    """Crea una ficha en estado Universo si no existe. Retorna la ficha."""
    f = s.query(Ficha).filter_by(ticker=ticker).first()
    if f is not None:
        return f
    # Verificar que el sector existe (FK)
    from backend.models import Sector
    sec = s.query(Sector).filter_by(nombre=sector_default).first()
    if sec is None:
        # Crear sector "(sin asignar)" si no existe
        s.add(Sector(nombre=sector_default, momentum_origen="manual"))
        s.flush()
    f = Ficha(
        ticker=ticker,
        nombre=ticker,
        sector=sector_default,
        estado=EstadoFicha.UNIVERSO.value,
        origen="batch_analista",
    )
    s.add(f)
    s.flush()
    return f


def construir_lista_tickers(args, crear_fichas: bool = True) -> list[str]:
    """Aplica los filtros y devuelve la lista final de tickers.

    Si crear_fichas=False, no inserta tickers nuevos en la DB (útil para dry-run).
    """
    tickers_finales: set[str] = set()

    # 1) Tickers explícitos (--tickers)
    if args.tickers:
        explicitos = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        if crear_fichas:
            with session_scope() as s:
                for t in explicitos:
                    _crear_ficha_si_no_existe(s, t, args.sector_default_nuevo)
        tickers_finales.update(explicitos)

    # 2) Filtros (estado / sector / score range / fecha)
    if args.estado or args.sector or args.score_min is not None or args.score_max is not None:
        with session_scope() as s:
            q = s.query(Ficha)
            if args.estado:
                q = q.filter(Ficha.estado.in_(args.estado))
            if args.sector:
                q = q.filter(Ficha.sector.in_(args.sector))
            if args.score_min is not None:
                q = q.filter(Ficha.score_vigente >= args.score_min)
            if args.score_max is not None:
                q = q.filter(Ficha.score_vigente <= args.score_max)
            if args.excluir_evaluados_hace > 0:
                cutoff = datetime.utcnow() - timedelta(days=args.excluir_evaluados_hace)
                q = q.filter(or_(
                    Ficha.fecha_ultimo_deep_research < cutoff,
                    Ficha.fecha_ultimo_deep_research.is_(None),
                ))
            tickers_filtrados = [f.ticker for f in q.all()]
        tickers_finales.update(tickers_filtrados)

    # Si no se especificó nada, error
    if not tickers_finales:
        return []

    # Cap
    out = sorted(tickers_finales)
    if args.max_tickers:
        out = out[: args.max_tickers]
    return out


def correr_uno(ticker: str) -> dict:
    """Corre el pipeline Analista → Writer → Portfolio para un ticker.

    Devuelve dict con resumen (no levanta excepción — captura y reporta).
    """
    t0 = time.time()
    try:
        with session_scope() as s:
            f = s.query(Ficha).filter_by(ticker=ticker).first()
            score_antes = f.score_vigente if f else None
            estado_antes = f.estado if f else None

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
            justificacion_rec = rec_row.justificacion if rec_row else None
            f2 = s.query(Ficha).filter_by(ticker=ticker).first()
            cfj = f2.confidence_y_fuentes_json if f2 else None
            sector_final = f2.sector if f2 else None

            # Detalle rico del análisis (todo lo que el Analista escribió)
            criterios_detalle = []
            if f2:
                ev_favor = f2.evidencia_favor_json or {}
                ev_contra = f2.evidencia_contra_json or {}
                justifs = f2.justificacion_json or {}
                cfj_local = cfj or {}
                NOMBRES = {
                    1: "Asimetría R/R", 2: "Captura de Valor", 3: "Catalizadores",
                    4: "Moat + Validación", 5: "TAM + Share", 6: "Calidad Revenue",
                    7: "Balance", 8: "Márgenes", 9: "Management", 10: "Precio vs Asimetría",
                }
                for i in range(1, 11):
                    score_i = getattr(f2, f"score_criterio_{i}", None)
                    info = cfj_local.get(str(i)) or {}
                    criterios_detalle.append({
                        "n": i,
                        "nombre": NOMBRES.get(i),
                        "es_central": i in (1, 2, 3, 4, 6),
                        "score": score_i,
                        "confidence": info.get("confidence"),
                        "fuente_nivel": info.get("fuente_nivel"),
                        "evidencia_favor": (ev_favor.get(str(i)) or "")[:280],
                        "evidencia_contra": (ev_contra.get(str(i)) or "")[:280],
                        "justificacion": (justifs.get(str(i)) or "")[:200],
                    })

            # Checklist de filtros BORJA — cada uno pass/fail con detalle
            filtros_borja = []
            if f2:
                from backend.agents.portfolio import (
                    SCORE_MIN_ENTRADA, SLOT_PORTFOLIO_MAX, MAX_POR_SECTOR, MAX_POR_DRIVER,
                    asimetria_min_para_momentum,
                    concentracion_sectorial, concentracion_driver,
                    contar_slots_portfolio,
                    verificar_checklist_entrada,
                    cluster_driver_de_ficha,
                    claims_centrales_con_confidence_baja,
                )
                from backend.models import Sector

                sec_row = s.query(Sector).filter_by(nombre=f2.sector).first()
                momentum = sec_row.momentum if sec_row else None
                asim_min = asimetria_min_para_momentum(momentum)
                cluster = cluster_driver_de_ficha(s, f2)

                # 1. Score mínimo
                score_n = f2.score_vigente or 0
                filtros_borja.append({
                    "n": 1, "regla": "Score mínimo",
                    "umbral": f">= {SCORE_MIN_ENTRADA}",
                    "valor": f"{score_n}",
                    "ok": score_n >= SCORE_MIN_ENTRADA,
                })
                # 2. Asimetría dinámica
                if asim_min is None:
                    filtros_borja.append({
                        "n": 2, "regla": "Asimetría",
                        "umbral": f"momentum {momentum or 'null'} → no entrar",
                        "valor": f"{asim if asim is not None else 'N/D'}x",
                        "ok": False,
                    })
                else:
                    filtros_borja.append({
                        "n": 2, "regla": "Asimetría dinámica",
                        "umbral": f">= {asim_min}x ({momentum or 'null→conservador'})",
                        "valor": f"{asim if asim is not None else 'N/D'}x",
                        "ok": (asim is not None and asim >= asim_min),
                    })
                # 3. Confidence Baja en claim central
                bajas = claims_centrales_con_confidence_baja(f2)
                filtros_borja.append({
                    "n": 3, "regla": "Confidence claims centrales (1,2,3,4,6)",
                    "umbral": "ninguno con Confidence Baja (fuente A/B)",
                    "valor": f"baja en c{bajas}" if bajas else "OK",
                    "ok": len(bajas) == 0,
                })
                # 4. CRR
                crr = f2.capital_raise_risk
                ok_crr = crr in (None, "Bajo", "Medio")
                filtros_borja.append({
                    "n": 4, "regla": "Capital Raise Risk",
                    "umbral": "Bajo o Medio",
                    "valor": crr or "N/D",
                    "ok": ok_crr,
                })
                # 5. Concentración sector
                conc_sec = concentracion_sectorial(s, f2.sector, excluir_ticker=f2.ticker)
                filtros_borja.append({
                    "n": 5, "regla": "Concentración sectorial",
                    "umbral": f"< {MAX_POR_SECTOR} en '{f2.sector}'",
                    "valor": f"{conc_sec}/{MAX_POR_SECTOR}",
                    "ok": conc_sec < MAX_POR_SECTOR,
                })
                # 6. Concentración driver compartido
                conc_drv = concentracion_driver(s, cluster, excluir_ticker=f2.ticker)
                filtros_borja.append({
                    "n": 6, "regla": "Driver compartido",
                    "umbral": f"< {MAX_POR_DRIVER} en cluster '{cluster or 'N/A'}'" if cluster else "no aplica (sin cluster)",
                    "valor": f"{conc_drv}/{MAX_POR_DRIVER}" if cluster else "—",
                    "ok": (not cluster) or conc_drv < MAX_POR_DRIVER,
                })
                # 7. Slot Portfolio disponible
                slots = contar_slots_portfolio(s)
                filtros_borja.append({
                    "n": 7, "regla": "Slot Portfolio",
                    "umbral": f"< {SLOT_PORTFOLIO_MAX}",
                    "valor": f"{slots}/{SLOT_PORTFOLIO_MAX}",
                    "ok": slots < SLOT_PORTFOLIO_MAX,
                })
                # 8. Liquidez
                filtros_borja.append({
                    "n": 8, "regla": "Liquidez",
                    "umbral": "volumen diario > $1M",
                    "valor": "✓ suficiente" if f2.liquidez_suficiente else "✗ insuficiente",
                    "ok": bool(f2.liquidez_suficiente),
                })
                # 9. Checklist de entrada
                chk = verificar_checklist_entrada(f2)
                faltantes = [k for k, v in chk.items() if not k.startswith("_") and not v]
                filtros_borja.append({
                    "n": 9, "regla": "Checklist entrada",
                    "umbral": "triggers + plan_salida + tipo_catalizador + mgmt + liquidez + nivel_R",
                    "valor": "completo" if not faltantes else f"falta: {faltantes}",
                    "ok": chk["_todos_ok"],
                })
                # 10. Red flags
                rf = f2.red_flags_count or 0
                filtros_borja.append({
                    "n": 10, "regla": "Red flags governance",
                    "umbral": "< 2 (con 2 no aumentar, con 3 kill switch)",
                    "valor": f"{rf}/3",
                    "ok": rf < 2,
                })

            analisis_detalle = {
                "tesis_vigente": f2.tesis_vigente if f2 else None,
                "filtros_borja": filtros_borja,
                "nivel_r": f2.nivel_r if f2 else None,
                "posicion_ciclo": f2.posicion_ciclo if f2 else None,
                "duracion_edge": f2.duracion_edge if f2 else None,
                "duracion_edge_justificacion": f2.duracion_edge_justificacion if f2 else None,
                "bull_case_precio": f2.bull_case_precio if f2 else None,
                "bear_case_precio": f2.bear_case_precio if f2 else None,
                "estimacion_crecimiento": f2.estimacion_crecimiento if f2 else None,
                "crecimiento_implicito_precio": f2.crecimiento_implicito_precio if f2 else None,
                "tipo_catalizador": f2.tipo_catalizador if f2 else None,
                "catalizador_descripcion": f2.catalizador_descripcion if f2 else None,
                "catalizador_fecha": f2.catalizador_fecha if f2 else None,
                "catalizador_impacto": f2.catalizador_impacto if f2 else None,
                "management_track_record": f2.management_track_record if f2 else None,
                "management_alignment": f2.management_alignment if f2 else None,
                "management_alignment_evidencia": f2.management_alignment_evidencia if f2 else None,
                "invalidation_triggers": list(f2.invalidation_triggers or []) if f2 else [],
                "plan_salida": f2.plan_salida if f2 else None,
                "liquidez_suficiente": f2.liquidez_suficiente if f2 else None,
                "criterios": criterios_detalle,
            }

        centrales_baja: list[int] = []
        if cfj:
            for c in (1, 2, 3, 4, 6):
                info = cfj.get(str(c)) or {}
                if (info.get("confidence") or "").lower() == "baja":
                    centrales_baja.append(c)

        # Veredicto agregado: ENTRA / BLOQUEADO / SCORE_BAJO
        score_n = wr.score_nuevo or 0
        if rec.get("accion") == "entrar":
            veredicto = "ENTRA"
        elif score_n < 6.0:
            veredicto = "SCORE_BAJO"
        else:
            veredicto = "BLOQUEADO"

        return {
            "ticker": ticker,
            "ok": True,
            "score_antes": score_antes,
            "score_nuevo": wr.score_nuevo,
            "estado_antes": estado_antes,
            "estado_nuevo": wr.estado_sugerido,
            "sector": sector_final,
            "precio": precio,
            "asimetria": asim,
            "accion_rec": rec.get("accion", "N/A"),
            "centrales_baja": centrales_baja,
            "veredicto": veredicto,
            "motivo": justificacion_rec,
            "analisis_detalle": analisis_detalle,
            "drift": wr.drift_detectado,
            "dt_s": round(time.time() - t0, 1),
        }

    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        return {
            "ticker": ticker,
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "dt_s": round(time.time() - t0, 1),
        }


def imprimir_resumen(resultados: list[dict]) -> None:
    print("\n" + "=" * 130)
    print(f"RESUMEN BATCH — {len(resultados)} tickers procesados")
    print("=" * 130)
    print(f"{'Ticker':<8} {'Antes':>6} {'→':^3} {'Nuevo':>6} {'Δ':>6} | "
          f"{'Estado':<18} {'Asim':>6} {'Rec':<14} {'CfBaja':<8} {'Seg':>5}")
    print("-" * 130)

    sorted_res = sorted(
        [r for r in resultados if r.get("ok")],
        key=lambda r: -((r["score_nuevo"] or 0) - (r["score_antes"] or 0)),
    )
    for r in sorted_res:
        delta = (r["score_nuevo"] or 0) - (r["score_antes"] or 0)
        cfb = ",".join(str(c) for c in r["centrales_baja"]) if r["centrales_baja"] else "-"
        marker = " ⭐" if (r["score_nuevo"] or 0) >= 6.0 and not r["centrales_baja"] else ""
        print(
            f"{r['ticker']:<8} "
            f"{str(r['score_antes']):>6} {'→':^3} {str(r['score_nuevo']):>6} {delta:>+6.2f} | "
            f"{str(r['estado_nuevo']):<18} {str(r['asimetria']):>6} "
            f"{str(r['accion_rec']):<14} {cfb:<8} {r['dt_s']:>5}{marker}"
        )

    errores = [r for r in resultados if not r.get("ok")]
    if errores:
        print("\n--- ERRORES ---")
        for r in errores:
            print(f"  {r['ticker']}: {r.get('error')}")

    candidatos = [
        r for r in sorted_res
        if (r["score_nuevo"] or 0) >= 6.0 and not r["centrales_baja"]
    ]
    print("\n" + "=" * 130)
    print(f"CANDIDATOS A PORTFOLIO (score ≥6 + sin Confidence Baja en claim central): {len(candidatos)}")
    print("=" * 130)
    for r in candidatos:
        print(f"  ⭐ {r['ticker']:8s} score={r['score_nuevo']} asim={r['asimetria']} rec={r['accion_rec']}")


def main() -> int:
    args = parse_args()
    # En dry-run no crear fichas nuevas (no contaminar DB)
    tickers = construir_lista_tickers(args, crear_fichas=not args.solo_estimar_costo)

    if not tickers:
        print("ERROR: ningún ticker selecionado. Pasá --tickers o algún filtro.", file=sys.stderr)
        return 1

    costo_est = len(tickers) * COSTO_PROMEDIO_USD
    print(f"\n{'='*70}")
    print(f"BATCH ANALISTA — {len(tickers)} tickers")
    print(f"{'='*70}")
    print(f"Tickers: {', '.join(tickers[:20])}{' …' if len(tickers) > 20 else ''}")
    print(f"Costo estimado: ~${costo_est:.2f} USD (${COSTO_PROMEDIO_USD}/call promedio)")
    print(f"Tiempo estimado: ~{len(tickers)*70//60} min ({len(tickers)*70}s)")
    print()

    if args.solo_estimar_costo:
        print("(--solo-estimar-costo: salida sin llamar al LLM)")
        return 0

    t_start = time.time()
    resultados: list[dict] = []
    for i, ticker in enumerate(tickers, 1):
        print(f"\n[{i}/{len(tickers)}] {ticker}", flush=True)
        r = correr_uno(ticker)
        resultados.append(r)
        if r.get("ok"):
            delta = (r["score_nuevo"] or 0) - (r["score_antes"] or 0)
            print(
                f"  score {r['score_antes']} → {r['score_nuevo']} ({delta:+.2f}) | "
                f"estado {r['estado_antes']} → {r['estado_nuevo']} | "
                f"asim {r['asimetria']} | rec {r['accion_rec']} | {r['dt_s']}s",
                flush=True,
            )
        else:
            print(f"  FALLO: {r['error']}", flush=True)

    imprimir_resumen(resultados)

    # Guardar JSON
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fname = f"batch_{datetime.now().strftime('%Y%m%dT%H%M%S')}.json"
    outpath = output_dir / fname
    outpath.write_text(json.dumps({
        "timestamp": datetime.now().isoformat(),
        "args": vars(args),
        "resultados": resultados,
    }, indent=2, default=str))

    dt_total = round(time.time() - t_start, 1)
    print(f"\nTotal: {len(resultados)} tickers en {dt_total}s ({round(dt_total/60,1)} min)")
    print(f"Resumen JSON: {outpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
