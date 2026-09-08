"""Precomputa la hoja de evidencia rankeada del universo → data/hoja_evidencia.json.

rankear() hace llamadas de red por ticker (EDGAR + feed) → lento para un request web. Este script
lo corre offline y persiste el resultado; la vista /hoja lee el JSON (patrón precompute+render, como
paper_pnl). Correr: .venv/bin/python -m ops.generar_hoja
"""
from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone
from pathlib import Path

from backend.database import session_scope
from backend.nucleo.hoja_evidencia import rankear

# Universo de trabajo (industrias del futuro). Ampliable.
UNIVERSO = [
    "CRWD", "ZS", "OKTA", "NET", "TENB", "VRNS", "RBRK", "S", "NABL",           # ciber/software
    "CLS", "MRVL", "CRDO", "ALAB", "AEHR", "MTSI", "LITE", "COHR", "AAOI",      # semis/fotónica
    "TER", "VCYT", "TEM", "RXRX", "SDGR",                                        # robótica/healthtech
    "OKLO", "SMR", "NNE", "LTBR", "UEC", "UUUU", "LEU",                          # nuclear/uranio
    "RKLB", "ASTS",                                                              # espacio
    "MP", "BWXT", "KTOS", "AVAV", "MRCY",                                        # minerales/defensa
]


def main() -> None:
    # READ-ONLY y barato: lee la demanda citada del fact store (transacción de solo lectura, no traba).
    # La EXTRACCIÓN LLM (escritura) es un job aparte → ops/extraer_demanda.py (transacción corta por
    # ticker). Así este script sigue siendo una instantánea de segundos, sin dependencia LLM ni lock.
    with session_scope() as s:
        res = rankear(UNIVERSO, session=s)
    out = {
        "generado": datetime.now(timezone.utc).isoformat(),
        "universo_n": len(UNIVERSO),
        "rankeado": [dataclasses.asdict(h) for h in res["rankeado"]],
        "descriptivo": {est: [dataclasses.asdict(h) for h in hs] for est, hs in res["descriptivo"].items()},
    }
    path = Path(__file__).resolve().parent.parent / "data" / "hoja_evidencia.json"
    path.write_text(json.dumps(out, indent=2, default=str))
    n_rank = len(out["rankeado"])
    n_desc = sum(len(v) for v in out["descriptivo"].values())
    print(f"hoja → {path} · {n_rank} rankeados + {n_desc} descriptivos ({len(UNIVERSO)} nombres)")


if __name__ == "__main__":
    main()
