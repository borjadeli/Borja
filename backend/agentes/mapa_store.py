"""Persistencia point-in-time del tablero de cuello (doc 89 §9.1 / doc 90 — pieza 1 del mapa MVP).

Guarda una FOTO del tablero por cuello por fecha (cierre trimestral). Habilita las dos piezas que necesitan
historia:
  - la comparación de DISOLUCIÓN (`senal_disolucion` necesita el tablero `previo`),
  - el panel SAME-STORE (el crecimiento se calcula solo con las empresas presentes en los DOS períodos →
    se persiste también el `revenue` por empresa de cada foto; sin esto, agregar un nombre con `ops.solicitar`
    se leería como "crecimiento", doc 89 §3.2).

JSON (como `ficha_store` / el cache de dossiers; son ~142 cuellos × pocas fotos → no hace falta SQLite).
Determinista, $0 LLM. Append-por-fecha: una foto de la MISMA fecha se reemplaza (idempotente ante re-corridas).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from backend.agentes.mapa_vivo import EstadoCuello, TableroCuello

_MAPA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "mapa_tableros_v2.json"
_ESTADOS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "mapa_estados_v2.json"


@dataclass
class SnapshotCuello:
    """Una foto del cuello en una fecha: el tablero agregado + el revenue por empresa (para same-store)."""
    tablero: TableroCuello
    empresas_revenue: dict[str, float] = field(default_factory=dict)

    @property
    def fecha(self) -> str:
        return self.tablero.fecha

    def to_dict(self) -> dict:
        return {"tablero": self.tablero.to_dict(), "empresas_revenue": self.empresas_revenue}

    @classmethod
    def from_dict(cls, d: dict) -> "SnapshotCuello":
        return cls(tablero=TableroCuello(**d["tablero"]),
                   empresas_revenue={k: float(v) for k, v in (d.get("empresas_revenue") or {}).items()})


class StoreMapa:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else _MAPA_PATH
        self._s: dict[str, list[SnapshotCuello]] = {}
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self._s = {c: [SnapshotCuello.from_dict(x) for x in lst] for c, lst in data.items()}
            except (OSError, json.JSONDecodeError, TypeError, KeyError):
                self._s = {}

    def guardar(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({c: [s.to_dict() for s in lst] for c, lst in self._s.items()},
                                        ensure_ascii=False, indent=2), encoding="utf-8")

    def set(self, tablero: TableroCuello, *, empresas_revenue: dict[str, float] | None = None) -> None:
        """Guarda la foto del tablero para (cuello, fecha). Una foto de la MISMA fecha se REEMPLAZA (idempotente)."""
        snap = SnapshotCuello(tablero=tablero, empresas_revenue=dict(empresas_revenue or {}))
        serie = [s for s in self._s.get(tablero.cuello, []) if s.fecha != tablero.fecha]
        serie.append(snap)
        serie.sort(key=lambda s: s.fecha)
        self._s[tablero.cuello] = serie

    def serie(self, cuello: str) -> list[SnapshotCuello]:
        """Todas las fotos del cuello, ordenadas por fecha ascendente."""
        return list(self._s.get(cuello, []))

    def ultimo(self, cuello: str) -> SnapshotCuello | None:
        serie = self._s.get(cuello)
        return serie[-1] if serie else None

    def previo(self, cuello: str, *, antes_de: str | None = None) -> SnapshotCuello | None:
        """La foto más reciente ESTRICTAMENTE anterior a `antes_de` (o la penúltima si `antes_de` es None).
        Es el `previo` para comparar disolución y para el panel same-store."""
        serie = self._s.get(cuello) or []
        if not serie:
            return None
        if antes_de is None:
            return serie[-2] if len(serie) >= 2 else None
        anteriores = [s for s in serie if s.fecha < antes_de]
        return anteriores[-1] if anteriores else None

    def cuellos(self) -> list[str]:
        return sorted(self._s.keys())


def guardar_estados(estados: dict[str, EstadoCuello], *, path: Path | str | None = None) -> None:
    """Persiste el estado CLASIFICADO vigente por cuello (lo lee el packet del PM + la detección de cambios)."""
    p = Path(path) if path else _ESTADOS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({c: e.to_dict() for c, e in estados.items()}, ensure_ascii=False, indent=2),
                 encoding="utf-8")


def cargar_estados(*, path: Path | str | None = None) -> dict[str, EstadoCuello]:
    """Carga los estados vigentes por cuello ({cuello: EstadoCuello}); {} si no hay archivo."""
    p = Path(path) if path else _ESTADOS_PATH
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return {c: EstadoCuello.from_dict(d) for c, d in data.items()}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
