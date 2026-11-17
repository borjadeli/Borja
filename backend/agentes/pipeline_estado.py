"""Estado del pipeline + DEAD MAN'S SWITCH (doc 85 F1).

Cada etapa del pipeline diario (poller, latido, drenaje de cola, zonas, despertar) escribe su timestamp. El
candado del gate consulta `fresco()`: si el poller/pipeline no corrió en `max_horas` (26h), **no se confía en
ninguna vigencia** y el gate pasa a fail-closed para compras. Un candado sin poller vivo es decorativo.

Persistencia JSON simple (atómica), gitignored en `data/`. Sin red ni LLM.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

_DEFAULT_PATH = Path("data/pipeline_estado.json")
DEAD_MAN_HORAS = 26.0          # doc 85: pasado esto sin correr → fail-closed para compras


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


class PipelineEstado:
    """Timestamps por etapa del pipeline. `marcar(etapa)` al completar; `fresco(etapa)` para el dead-man's-switch."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else _DEFAULT_PATH
        self._estado: dict[str, str] = {}
        if self.path.exists():
            try:
                self._estado = json.loads(self.path.read_text())
            except Exception:  # noqa: BLE001 — estado corrupto → se trata como vacío (fail-closed)
                self._estado = {}

    def marcar(self, etapa: str, *, cuando: datetime | None = None) -> None:
        self._estado[etapa] = (cuando or _ahora()).isoformat()
        self._guardar()

    def ultimo(self, etapa: str) -> datetime | None:
        s = self._estado.get(etapa)
        if not s:
            return None
        try:
            dt = datetime.fromisoformat(s)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:  # noqa: BLE001
            return None

    def fresco(self, etapa: str = "poller", *, max_horas: float = DEAD_MAN_HORAS,
               ahora: datetime | None = None) -> bool:
        """¿La etapa corrió dentro de las últimas `max_horas`? None/corrupto/viejo → False (fail-closed)."""
        u = self.ultimo(etapa)
        if u is None:
            return False
        return (ahora or _ahora()) - u <= timedelta(hours=max_horas)

    def _guardar(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump(self._estado, fh, indent=2)
            os.replace(tmp, self.path)       # atómico
        except Exception:  # noqa: BLE001
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise


def pipeline_fresco(*, path: Path | str | None = None, etapa: str = "poller",
                    max_horas: float = DEAD_MAN_HORAS) -> bool:
    """Atajo para el gate/runner: ¿el pipeline está vivo? (dead-man's-switch)."""
    return PipelineEstado(path).fresco(etapa, max_horas=max_horas)
