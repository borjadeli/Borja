"""Research Queue (doc 85 F2/§4/§8) — una sola cola de deep con origen + prioridad, drenada a DIARIO.

Toda necesidad de deep es una solicitud con origen (POSICION_EVENTO / REVALIDACION / PM / OPERADOR / OPORTUNIDAD /
TTL / FRIO), prioridad (P0 evento de posición · P1 revalidación/PM/operador · P2 oportunidad) y motivo. El origen
NO determina la calidad; la reserva protege la capacidad de discovery. Dedup por ticker: si dos piden el mismo, se
consolida y sube la prioridad — no se investiga dos veces. Persistencia JSON atómica, $0.
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_PATH = Path("data/research_queue.json")
_PRIOS = ("P0", "P1", "P2")
ORIGENES = ("POSICION_EVENTO", "REVALIDACION", "PM", "OPERADOR", "OPORTUNIDAD", "TTL", "FRIO")


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DeepRequest:
    ticker: str
    origen: list[str]                       # puede acumular varios (consolidación)
    prioridad: str = "P2"                    # P0 | P1 | P2
    motivo: str = ""                         # se guarda; NO se pasa al Analista (pedido ciego)
    ciego_a_ficha_previa: bool = False       # true en el deep en frío (F3)
    estado: str = "PENDIENTE"                # PENDIENTE | CORRIENDO | HECHO | DESCARTADO
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    costo_usd: float = 0.0
    creado: str = field(default_factory=_ahora)
    terminado: str | None = None
    resultado: dict | None = None            # {estado_ficha, zona} tras el deep


def _min_prio(a: str, b: str) -> str:
    """La prioridad MÁS alta (P0 < P1 < P2)."""
    return a if _PRIOS.index(a) <= _PRIOS.index(b) else b


class ResearchQueue:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else _DEFAULT_PATH
        self._reqs: list[DeepRequest] = []
        if self.path.exists():
            try:
                self._reqs = [DeepRequest(**d) for d in json.loads(self.path.read_text())]
            except Exception:  # noqa: BLE001
                self._reqs = []

    def encolar(self, ticker: str, *, origen: str, prioridad: str = "P2", motivo: str = "",
                ciego: bool = False) -> DeepRequest:
        """Agrega o CONSOLIDA (dedup por ticker en estado PENDIENTE/CORRIENDO): suma el origen y sube la prioridad."""
        tk = ticker.upper()
        activa = next((r for r in self._reqs if r.ticker == tk and r.estado in ("PENDIENTE", "CORRIENDO")), None)
        if activa is not None:
            if origen not in activa.origen:
                activa.origen.append(origen)
            activa.prioridad = _min_prio(activa.prioridad, prioridad)
            activa.ciego_a_ficha_previa = activa.ciego_a_ficha_previa or ciego
            self._guardar()
            return activa
        req = DeepRequest(ticker=tk, origen=[origen], prioridad=prioridad, motivo=motivo, ciego_a_ficha_previa=ciego)
        self._reqs.append(req)
        self._guardar()
        return req

    def pendientes(self) -> list[DeepRequest]:
        """Solicitudes PENDIENTE, ordenadas por prioridad (P0 primero), luego por antigüedad (FIFO)."""
        return sorted([r for r in self._reqs if r.estado == "PENDIENTE"],
                      key=lambda r: (_PRIOS.index(r.prioridad), r.creado))

    def marcar(self, req_id: str, estado: str, *, costo_usd: float = 0.0, resultado: dict | None = None) -> None:
        for r in self._reqs:
            if r.id == req_id:
                r.estado = estado
                r.costo_usd = costo_usd
                r.resultado = resultado
                if estado in ("HECHO", "DESCARTADO"):
                    r.terminado = _ahora()
                break
        self._guardar()

    def _guardar(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump([asdict(r) for r in self._reqs], fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except Exception:  # noqa: BLE001
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
