"""Backfill de trades históricos (S, LEU, TENB) — 21-abril.

LEU se cierra al precio_mtm más reciente con motivo='rotar' (rotación 2026-04-27).
S y TENB siguen abiertos.

Idempotente: si ya hay trade para un ticker, lo skipea.
"""
from __future__ import annotations

from datetime import datetime

from backend.database import session_scope
from backend.models import Ficha, Trade
from backend.utils import utcnow

# Datos verificados desde memoria + backups
HISTORICO = [
    {
        "ticker": "S",
        "fecha_apertura": "2026-04-21T11:04:46",
        "precio_entrada": 14.32,
        "sizing_pct": 4.9,
        "rec_id_apertura": 13,
        "sector_apertura": "Ciberseguridad",
        "status": "open",
    },
    {
        "ticker": "TENB",
        "fecha_apertura": "2026-04-21T12:59:10",
        "precio_entrada": 19.52,
        "sizing_pct": 4.9,
        "rec_id_apertura": 50,
        "sector_apertura": "Ciberseguridad",
        "status": "open",
    },
    {
        "ticker": "LEU",
        "fecha_apertura": "2026-04-21T10:46:02",
        "precio_entrada": 199.61,
        "sizing_pct": 3.5,
        "rec_id_apertura": 3,
        "sector_apertura": "Minerales críticos",
        "status": "closed",
        # Cierre: rotación 2026-04-27 disparada por batch v4.2 (rec_id=219)
        "fecha_cierre": "2026-04-27T17:22:00",
        "precio_cierre_fallback": None,  # toma precio_mtm si está disponible
        "rec_id_cierre": 219,
        "motivo_cierre": "rotar",
    },
]

CAPITAL_TOTAL = 100_000.0


def main() -> None:
    creados: list[str] = []
    skipped: list[str] = []
    cerrados: list[str] = []

    for spec in HISTORICO:
        ticker = spec["ticker"]
        with session_scope() as s:
            existente = s.query(Trade).filter_by(ticker=ticker).first()
            if existente:
                skipped.append(f"{ticker} (ya existe trade id={existente.id})")
                continue

            fecha_apertura = datetime.fromisoformat(spec["fecha_apertura"])
            sizing_pct = spec["sizing_pct"]
            cap_deployado = round((sizing_pct / 100.0) * CAPITAL_TOTAL, 2)

            t = Trade(
                ticker=ticker,
                status=spec["status"],
                fecha_apertura=fecha_apertura,
                precio_entrada=spec["precio_entrada"],
                sizing_pct_apertura=sizing_pct,
                capital_deployado_usd=cap_deployado,
                rec_id_apertura=spec.get("rec_id_apertura"),
                sector_apertura=spec.get("sector_apertura"),
                notas="backfill 2026-04-27 — datos verificados memoria + backup pre_mtm",
            )

            if spec["status"] == "closed":
                # Tomar precio_mtm de la ficha (último valor confiable)
                ficha = s.query(Ficha).filter_by(ticker=ticker).first()
                precio_cierre = (
                    spec.get("precio_cierre_fallback")
                    or (ficha.precio_mtm if ficha else None)
                    or (ficha.precio_ultima_actualizacion_ficha if ficha else None)
                )
                if not precio_cierre:
                    raise ValueError(f"sin precio_cierre disponible para {ticker}")

                valor_cierre = cap_deployado * (precio_cierre / spec["precio_entrada"])
                pnl_usd = valor_cierre - cap_deployado
                pnl_pct = (precio_cierre - spec["precio_entrada"]) / spec["precio_entrada"] * 100.0

                t.fecha_cierre = datetime.fromisoformat(spec["fecha_cierre"])
                t.precio_cierre = float(precio_cierre)
                t.valor_cierre_usd = round(valor_cierre, 2)
                t.pnl_realizado_usd = round(pnl_usd, 2)
                t.pnl_realizado_pct = round(pnl_pct, 2)
                t.motivo_cierre = spec["motivo_cierre"]
                t.rec_id_cierre = spec.get("rec_id_cierre")
                cerrados.append(f"{ticker} pnl=${pnl_usd:+.2f}")

            s.add(t)
            s.flush()
            creados.append(f"{ticker} id={t.id} status={t.status}")

    print("=== Backfill trades ===")
    print(f"Creados: {creados}")
    print(f"Cerrados: {cerrados}")
    print(f"Skipped: {skipped}")


if __name__ == "__main__":
    main()
