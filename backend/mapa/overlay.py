"""Overlay de datos de la brújula — los cuellos que DESCUBRE el sistema (doc 76, write-back al mapa).

`brujula.py` es la semilla curada a mano (inmutable, en código). Cuando el agente de discovery propone un
cuello NUEVO y el agente CURADOR lo valida, el nodo se agrega acá (JSONL append-only, patrón ledger). NO se
toca el código: `territorios_activos()` une la semilla + este overlay. Así el mapa crece solo, con el humano
fuera del lazo (lo valida un agente, no una persona).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from backend.mapa.brujula import EstadoTerritorio, Territorio

_OVERLAY_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "brujula_overlay_v2.jsonl"


def _path() -> Path:
    return _OVERLAY_PATH


def _registros() -> list[dict]:
    p = _path()
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def cargar_overlay() -> list[Territorio]:
    """Los cuellos descubiertos como Territorio ACTIVO (proyección: último por nombre; patrón append-only)."""
    por_nombre: dict[str, dict] = {}
    for r in _registros():
        por_nombre[r["nombre"]] = r                      # el último gana (permite corregir/retirar luego)
    return [Territorio(nombre=r["nombre"], cluster=r.get("cluster", "descubierto"),
                       factor_macro=r.get("factor_macro"), estado=EstadoTerritorio.ACTIVO,
                       subnodos=list(r.get("subnodos") or []),
                       nota=r.get("nota")) for r in por_nombre.values() if not r.get("retirado")]


def nombres_overlay() -> set[str]:
    return {t.nombre for t in cargar_overlay()}


def agregar_overlay(*, nombre: str, cluster: str = "descubierto", factor_macro: str | None = None,
                    subnodos: list[str] | None = None, nota: str | None = None) -> None:
    """Agrega un cuello descubierto al mapa (lo llama la promoción de nodos, tras el visto del curador-agente)."""
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    reg = {"nombre": nombre, "cluster": cluster, "factor_macro": factor_macro,
           "subnodos": list(subnodos or []), "nota": nota,
           "ts": datetime.now(timezone.utc).isoformat()}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(reg, ensure_ascii=False) + "\n")
