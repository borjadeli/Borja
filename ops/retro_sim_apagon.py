"""Retro-simulación del evaluador horario durante un apagón del servicio.

Replay determinista: para cada marca horaria perdida (L-V 10:15-16:15 ET) corre
el pipeline real Portfolio → Juez con el precio histórico de Yahoo inyectado
(bar 60m que contiene la marca, aproximación ±15 min). Las fichas se asumen
congeladas (sin corridas de Analista en la ventana — verificar antes en llm_calls).

Dry-run por defecto: imprime las decisiones que el sistema hubiese tomado.
Con --ejecutar aplica los trades resultantes vía recomendacion_runner con
timestamps retroactivos (uso: reconstruir el ledger tras downtime).

Uso:
    .venv/bin/python -m ops.retro_sim_apagon --marcas-archivo /tmp/marcas.json
    .venv/bin/python -m ops.retro_sim_apagon --marcas-archivo /tmp/marcas.json --ejecutar
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone

from backend.agents import juez as juez_agent
from backend.agents import portfolio as portfolio_agent
from backend.services.market_data import _fetch_yahoo_chart

ET = timezone(timedelta(hours=-4))  # EDT (junio)


def cargar_precios_horarios(tickers: list[str], range_: str = "1mo") -> dict[str, list[tuple[datetime, float]]]:
    out: dict[str, list[tuple[datetime, float]]] = {}
    for tk in tickers:
        payload = _fetch_yahoo_chart(tk, range_=range_, interval="60m")
        r0 = payload["chart"]["result"][0]
        ts = r0.get("timestamp") or []
        closes = (r0["indicators"]["quote"][0].get("close")) or []
        rows = [
            (datetime.fromtimestamp(t, tz=ET), float(c))
            for t, c in zip(ts, closes)
            if c is not None
        ]
        out[tk] = rows
    return out


def precio_en_marca(serie: list[tuple[datetime, float]], marca: datetime) -> float | None:
    """Close del bar 60m que contiene la marca (último bar con inicio <= marca)."""
    candidatos = [(dt, c) for dt, c in serie if dt <= marca and (marca - dt) <= timedelta(hours=1)]
    if not candidatos:
        return None
    return candidatos[-1][1]


def simular(marcas: list[datetime], tickers: list[str], ejecutar: bool) -> list[dict]:
    precios = cargar_precios_horarios(tickers)
    decisiones: list[dict] = []

    precio_inyectado: dict[str, float | None] = {}

    def _precio_patch(ticker: str) -> float | None:
        return precio_inyectado.get(ticker.upper())

    original = portfolio_agent._get_precio_actual
    portfolio_agent._get_precio_actual = _precio_patch
    try:
        for marca in marcas:
            for tk in tickers:
                px = precio_en_marca(precios[tk], marca)
                if px is None:
                    continue
                precio_inyectado[tk] = px
                rec = portfolio_agent.generar_recomendacion(tk)
                estado_rec, motivo = juez_agent.validar_recomendacion(rec)
                accionable = rec.accion in ("entrar", "rotar", "salir", "piramidacion", "aumentar", "bucket")
                decisiones.append({
                    "marca_et": marca.strftime("%Y-%m-%d %H:%M"),
                    "ticker": tk,
                    "precio": px,
                    "accion": rec.accion,
                    "asimetria": rec.asimetria_vigente,
                    "estado_rec": estado_rec,
                    "motivo_cuestionada": motivo,
                    "accionable": accionable and estado_rec == "VALIDADA",
                    "justificacion": rec.justificacion,
                })
                if accionable and estado_rec == "VALIDADA" and ejecutar:
                    _aplicar_retro(tk, rec, px, marca)
    finally:
        portfolio_agent._get_precio_actual = original
    return decisiones


def _aplicar_retro(ticker: str, rec, precio: float, marca: datetime) -> None:
    """Aplica una decisión accionable con timestamp retroactivo (marca en UTC)."""
    from backend.agents.recomendacion_runner import aprobar_recomendacion, ejecutar_recomendacion
    from backend.database import session_scope
    from backend.models import Recomendacion, Trade

    res = ejecutar_recomendacion(ticker)
    rec_id = res.get("rec_id")
    if not res.get("auto_aprobada"):
        aprobar_recomendacion(rec_id, precio_entrada=precio)
    marca_utc = marca.astimezone(timezone.utc).replace(tzinfo=None)
    with session_scope() as s:
        row = s.get(Recomendacion, rec_id)
        row.timestamp_juez = marca_utc
        nota = f"retro-sim apagón — decisión reconstruida a precio {precio} de la marca {marca.isoformat()}"
        row.justificacion = (row.justificacion or "") + " | " + nota
        t = (
            s.query(Trade)
            .filter((Trade.rec_id_apertura == rec_id) | (Trade.rec_id_cierre == rec_id))
            .first()
        )
        if t is not None:
            if t.rec_id_apertura == rec_id:
                t.fecha_apertura = marca_utc
                t.precio_entrada = precio
            else:
                t.fecha_cierre = marca_utc
                t.precio_cierre = precio
            t.notas = ((t.notas or "") + " | retro-sim apagón").strip(" |")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--marcas-archivo", required=True, help="JSON con lista de marcas ET 'YYYY-MM-DD HH:MM'")
    ap.add_argument("--ejecutar", action="store_true", help="aplica los trades (default: dry-run)")
    args = ap.parse_args()

    marcas = [
        datetime.strptime(m, "%Y-%m-%d %H:%M").replace(tzinfo=ET)
        for m in json.load(open(args.marcas_archivo))
    ]

    from backend.database import session_scope
    from backend.models import Ficha
    with session_scope() as s:
        tickers = [
            f.ticker for f in s.query(Ficha).filter(
                Ficha.estado.in_(["Portfolio_Activo", "WL_Prioritaria"])
            ).all()
        ]

    decisiones = simular(marcas, tickers, ejecutar=args.ejecutar)

    accionables = [d for d in decisiones if d["accionable"]]
    print(f"\n{'='*80}\nmarcas={len(marcas)} tickers={len(tickers)} evaluaciones={len(decisiones)} accionables={len(accionables)} modo={'EJECUTAR' if args.ejecutar else 'dry-run'}\n")
    for d in accionables:
        print(f"  >>> {d['marca_et']} {d['ticker']} @ {d['precio']}: {d['accion'].upper()} (asim {d['asimetria']}) — {d['justificacion'][:120]}")
    if not accionables:
        print("  Sin acciones de capital — BORJA hubiese mantenido el portfolio intacto en todas las marcas.")

    # Resumen por ticker: rango de asimetría observado y por qué no accionó
    print(f"\n{'-'*80}\nResumen por ticker (rango asimetría en las marcas / motivo dominante):")
    por_tk: dict[str, list[dict]] = {}
    for d in decisiones:
        por_tk.setdefault(d["ticker"], []).append(d)
    for tk, ds in sorted(por_tk.items()):
        asims = [d["asimetria"] for d in ds if d["asimetria"] is not None]
        rango = f"{min(asims):.2f}x–{max(asims):.2f}x" if asims else "N/D"
        ultimo = ds[-1]
        print(f"  {tk:6s} asim {rango:14s} accion={ultimo['accion']:15s} {ultimo['justificacion'][:110]}")

    json.dump(decisiones, open("/tmp/retro_sim_decisiones.json", "w"), indent=1)
    print("\nDetalle completo: /tmp/retro_sim_decisiones.json")


if __name__ == "__main__":
    main()
