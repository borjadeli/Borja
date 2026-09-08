"""Log de decisiones — la semilla del LOOP DE MEDICIÓN (doc 26 §12, nivel 2 del 'aprender').

Guarda el VECTOR DE BANDAS en el MOMENTO de la decisión (no reconstruido después). Con el tiempo
se cruza con el retorno forward por decil de cada pilar → qué dimensiones REALMENTE discriminan →
recalibración con datos, no con intuición. Append-only, auditable. Sin esto, la calibración es opinión.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from backend.nucleo.evaluacion import Evaluacion

LOG_DEFAULT = Path(__file__).resolve().parent.parent.parent / "data" / "mediciones" / "bandas.jsonl"


def registrar_decision(ev: Evaluacion, *, fecha: date, path: str | Path | None = None) -> dict:
    """Anexa el vector de bandas + tier + Δ de una decisión al log de medición."""
    p = Path(path) if path else LOG_DEFAULT
    p.parent.mkdir(parents=True, exist_ok=True)
    fila = {
        "fecha": str(fecha), "ticker": ev.ticker, "tier": ev.tier,
        "arquetipo": ev.arquetipo, "hard_cap": ev.hard_cap, "delta": ev.delta_evidencia,
        "pilar_limitante": ev.pilar_limitante,
        "bandas": {pl.nombre: int(pl.banda_efectiva()) for pl in ev.pilares},
        "confianza": {pl.nombre: pl.confianza for pl in ev.pilares},
    }
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(fila, ensure_ascii=False) + "\n")
    return fila
