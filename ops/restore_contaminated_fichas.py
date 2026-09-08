"""Restore quirúrgico de fichas contaminadas por tests pre-aislación.

Usa sqlite3 directo (no ORM) para evitar issues de typing con datetime —
el backup los almacena como strings y eso matchea el formato interno SQLite.

Detectadas 4 fichas contaminadas: NVTS, CRDO, COHR, VRT.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from backend import panic


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLEAN_DB = PROJECT_ROOT / "data" / "backups" / "borja_20260421T133041.db"
LIVE_DB = PROJECT_ROOT / "data" / "borja.db"
CONTAMINATED = ["NVTS", "CRDO", "COHR", "VRT"]


def _fetch_clean_row(ticker: str) -> dict | None:
    con = sqlite3.connect(str(CLEAN_DB))
    con.row_factory = sqlite3.Row
    try:
        cur = con.execute("SELECT * FROM fichas WHERE ticker = ?", (ticker,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def _fetch_current_row(ticker: str) -> dict | None:
    con = sqlite3.connect(str(LIVE_DB))
    con.row_factory = sqlite3.Row
    try:
        cur = con.execute("SELECT * FROM fichas WHERE ticker = ?", (ticker,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def main() -> None:
    if not CLEAN_DB.exists():
        raise SystemExit(f"backup limpio no encontrado: {CLEAN_DB}")

    print("== Pausando sistema ==")
    panic.pausar(motivo="restore quirúrgico fichas contaminadas", by="admin")

    try:
        now_iso = datetime.utcnow().isoformat()
        motivo = "restauración post-contaminación tests — fila completa desde backup 13:30"

        con = sqlite3.connect(str(LIVE_DB))
        con.row_factory = sqlite3.Row
        try:
            for ticker in CONTAMINATED:
                clean = _fetch_clean_row(ticker)
                if clean is None:
                    print(f"  WARNING {ticker}: no está en backup limpio — skip")
                    continue

                current = _fetch_current_row(ticker)
                if current is None:
                    print(f"  WARNING {ticker}: no está en DB actual — skip")
                    continue

                # Preservar historial: append al de la DB actual.
                cambios_estado = list(json.loads(current.get("cambios_estado") or "[]"))
                cambios_score = list(json.loads(current.get("cambios_score") or "[]"))
                cambios_estado.append({
                    "timestamp": now_iso,
                    "estado_anterior": current.get("estado"),
                    "estado_nuevo": clean.get("estado"),
                    "motivo": motivo,
                })

                # Preparar payload: todas las cols del limpio excepto PK y las de historial
                # (que ya construimos con merge).
                cols = [k for k in clean.keys() if k != "ticker"]
                values = []
                for col in cols:
                    if col == "cambios_estado":
                        values.append(json.dumps(cambios_estado))
                    elif col == "cambios_score":
                        values.append(json.dumps(cambios_score))
                    else:
                        values.append(clean[col])

                set_clause = ", ".join(f"{c} = ?" for c in cols)
                sql = f"UPDATE fichas SET {set_clause} WHERE ticker = ?"
                con.execute(sql, (*values, ticker))

                print(
                    f"  {ticker}: estado {current.get('estado')} → {clean.get('estado')} | "
                    f"score {current.get('score_vigente')} → {clean.get('score_vigente')} | "
                    f"bull ${current.get('bull_case_precio')} → ${clean.get('bull_case_precio')}"
                )

            con.commit()
        finally:
            con.close()

        print("\n== Verificación ==")
        for ticker in CONTAMINATED:
            row = _fetch_current_row(ticker)
            if row:
                tesis = (row.get("tesis_vigente") or "")[:70]
                print(f"  {ticker:6} estado={row['estado']:20} score={row['score_vigente']} tesis='{tesis}...'")

    finally:
        print("\n== Reanudando sistema ==")
        panic.reanudar(by="admin")


if __name__ == "__main__":
    main()
