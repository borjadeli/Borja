"""Ledger de presupuesto en USD (v2 Fase 3, doc 54 §4.6) — el freno duro del comité.

Diseño convergido (IA2): `task_budget` NO es tope → el control vive acá, en el orquestador.
- **sobre semanal** (~$9 de los $40/mes) con **reserva 20-25% para eventos** (el trabajo agendado solo
  puede usar el resto; los eventos pueden tocar la reserva).
- **reserva de peor-caso ANTES de cada llamada** (output×max_tokens + web×$0.01 + input estimado), se
  libera la diferencia al confirmar con el costo real. Así un loop largo no se pasa del límite.
- **escalera de degradación** por nivel consumido: 70% restringido (baja max_uses, solo posiciones/eventos),
  90% solo reutilización, 100% corte.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime

from backend.agentes.base import PRECIOS

_plog = logging.getLogger("agentes.presupuesto")


def peor_caso_usd(model: str, *, max_tokens: int, max_uses: int, input_estimado: int) -> float:
    """Costo de peor caso de una llamada (para reservar antes de ejecutar)."""
    p = PRECIOS.get(model) or PRECIOS["claude-opus-5-5"]
    return round(input_estimado / 1e6 * p["input"]
                 + max_tokens / 1e6 * p["output"]
                 + max_uses * 0.01, 6)


@dataclass
class LedgerPresupuesto:
    sobre_semanal: float                 # ritmo agendado de la corrida (ej. presupuesto_mes / semanas restantes)
    reserva_eventos_pct: float = 0.22     # 20-25% reservado para eventos tardíos
    gastado: float = 0.0                  # costo real confirmado
    reservado: float = 0.0                # peor-caso de llamadas en vuelo
    tope_evento_usd: float | None = None  # tope para EVENTOS (ej. todo lo que queda del mes); None = sobre
    modo_forzado: str | None = None       # si está, modo() lo devuelve (fail-closed → "solo_reuso")

    def _tope(self, para_evento: bool) -> float:
        # el trabajo AGENDADO accede a (1 - reserva) del sobre; los EVENTOS pueden tocar `tope_evento_usd`
        # (todo el resto del mes) o el sobre completo si no se fijó.
        if para_evento:
            return self.tope_evento_usd if self.tope_evento_usd is not None else self.sobre_semanal
        return self.sobre_semanal * (1 - self.reserva_eventos_pct)

    def disponible(self, *, para_evento: bool = False) -> float:
        return round(self._tope(para_evento) - self.gastado - self.reservado, 6)

    def nivel(self) -> float:
        """Fracción del sobre consumida (gastado + reservado). 0..1+."""
        return (self.gastado + self.reservado) / self.sobre_semanal if self.sobre_semanal > 0 else 1.0

    def modo(self) -> str:
        if self.modo_forzado:
            return self.modo_forzado
        n = self.nivel()
        if n >= 1.0:
            return "corte"          # 100%: no más llamadas
        if n >= 0.9:
            return "solo_reuso"     # 90%: solo dossiers reutilizados
        if n >= 0.7:
            return "restringido"    # 70%: baja max_uses, solo posiciones/eventos
        return "normal"

    def reservar(self, peor_caso: float, *, para_evento: bool = False) -> bool:
        """Autoriza una llamada reservando su peor-caso. False si no hay margen (no reserva)."""
        if peor_caso <= self.disponible(para_evento=para_evento):
            self.reservado += peor_caso
            return True
        return False

    def confirmar(self, peor_caso: float, real: float) -> None:
        """Libera la reserva de peor-caso y contabiliza el costo REAL."""
        self.reservado = max(0.0, round(self.reservado - peor_caso, 6))
        self.gastado = round(self.gastado + real, 6)


# --------------------------------------------------------------------------- presupuesto MENSUAL persistente

def gastado_mes_usd(hoy: date | None = None, *, session=None) -> float | None:
    """Gasto LLM acumulado en el MES CALENDARIO de `hoy`, leído de `llm_calls` (persistente, TODOS los
    agentes). Devuelve **None si NO se pudo leer** (sin DB / error) → el caller aplica fail-closed
    (auditoría r2 4c). 0.0 = se leyó y no hay gasto. `session` inyectable para tests."""
    hoy = hoy or date.today()
    inicio = datetime(hoy.year, hoy.month, 1)
    try:
        from sqlalchemy import func

        from backend.models import LLMCall

        def _q(s) -> float:
            return float(s.query(func.coalesce(func.sum(LLMCall.cost_usd), 0.0))
                         .filter(LLMCall.timestamp >= inicio).scalar() or 0.0)

        if session is not None:
            return _q(session)
        from backend.database import session_scope
        with session_scope() as s:
            return _q(s)
    except Exception as e:  # noqa: BLE001 — no se pudo leer el gasto → fail-closed en el caller
        _plog.warning("no pude leer el gasto del mes (fail-closed): %s", e)
        return None


def _semanas_restantes_mes(hoy: date) -> int:
    """Semanas (calendario, ≥1) que quedan en el mes de `hoy`, contando la actual."""
    import calendar
    ultimo = calendar.monthrange(hoy.year, hoy.month)[1]
    dias_restantes = ultimo - hoy.day + 1
    return max(1, -(-dias_restantes // 7))        # ceil(dias/7)


def ledger_mensual(presupuesto_usd_mes: float, hoy: date | None = None, *,
                   reserva_eventos_pct: float = 0.22, session=None) -> LedgerPresupuesto:
    """Ledger de ESTA corrida con tope MENSUAL persistente + RITMO SEMANAL (auditoría r2 4a/4c):
    - `gastado del mes` se lee de `llm_calls` (persistente, todos los agentes). Si NO se puede leer →
      **fail-closed**: sobre 0 + modo `solo_reuso` (no se gasta, solo reutilización).
    - el sobre AGENDADO de la corrida = min(restante del mes, presupuesto_mes / semanas restantes del mes);
      los EVENTOS pueden tocar todo el restante del mes (`tope_evento_usd`)."""
    hoy = hoy or date.today()
    gastado = gastado_mes_usd(hoy, session=session)
    if gastado is None:
        return LedgerPresupuesto(sobre_semanal=0.0, reserva_eventos_pct=reserva_eventos_pct,
                                 modo_forzado="solo_reuso")
    restante = max(0.0, round(presupuesto_usd_mes - gastado, 6))
    ritmo = round(min(restante, presupuesto_usd_mes / _semanas_restantes_mes(hoy)), 6)
    return LedgerPresupuesto(sobre_semanal=ritmo, reserva_eventos_pct=reserva_eventos_pct,
                             tope_evento_usd=restante)


def ledger_bootstrap(presupuesto_bootstrap_usd: float, *, reserva_eventos_pct: float = 0.0) -> LedgerPresupuesto:
    """Ledger para la primera pasada del universo (bootstrap): tope PROPIO, separado del mensual
    (auditoría r2 4b; `presupuesto_bootstrap_usd` vive en ips.yaml)."""
    return LedgerPresupuesto(sobre_semanal=max(0.0, presupuesto_bootstrap_usd),
                             reserva_eventos_pct=reserva_eventos_pct)
