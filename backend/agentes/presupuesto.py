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

from dataclasses import dataclass
from datetime import date, datetime

from backend.agentes.base import PRECIOS


def peor_caso_usd(model: str, *, max_tokens: int, max_uses: int, input_estimado: int) -> float:
    """Costo de peor caso de una llamada (para reservar antes de ejecutar)."""
    p = PRECIOS.get(model) or PRECIOS["claude-opus-5-5"]
    return round(input_estimado / 1e6 * p["input"]
                 + max_tokens / 1e6 * p["output"]
                 + max_uses * 0.01, 6)


@dataclass
class LedgerPresupuesto:
    sobre_semanal: float                 # ej. 9.0 (de $40/mes)
    reserva_eventos_pct: float = 0.22     # 20-25% reservado para eventos tardíos
    gastado: float = 0.0                  # costo real confirmado
    reservado: float = 0.0                # peor-caso de llamadas en vuelo

    def _tope(self, para_evento: bool) -> float:
        # el trabajo AGENDADO solo accede a (1 - reserva); los EVENTOS pueden usar el sobre completo.
        return self.sobre_semanal if para_evento else self.sobre_semanal * (1 - self.reserva_eventos_pct)

    def disponible(self, *, para_evento: bool = False) -> float:
        return round(self._tope(para_evento) - self.gastado - self.reservado, 6)

    def nivel(self) -> float:
        """Fracción del sobre consumida (gastado + reservado). 0..1+."""
        return (self.gastado + self.reservado) / self.sobre_semanal if self.sobre_semanal > 0 else 1.0

    def modo(self) -> str:
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

def gastado_mes_usd(hoy: date | None = None, *, session=None) -> float:
    """Gasto LLM acumulado en el MES CALENDARIO de `hoy`, leído de `llm_calls` (persistente, TODOS los
    agentes). 0.0 si no hay DB disponible (fail-silent). `session` inyectable para tests."""
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
    except Exception:  # noqa: BLE001 — sin DB, el presupuesto arranca de cero (no bloquea)
        return 0.0


def ledger_mensual(presupuesto_usd_mes: float, hoy: date | None = None, *,
                   reserva_eventos_pct: float = 0.22, session=None) -> LedgerPresupuesto:
    """Ledger para ESTA corrida con tope MENSUAL persistente: el 'sobre' disponible = lo que queda del mes
    (`presupuesto_usd_mes` − gastado del mes, de `llm_calls`). Así el gasto sobrevive al reinicio y respeta
    el tope mensual del IPS, cubriendo a todos los agentes que loguean su costo."""
    restante = max(0.0, round(presupuesto_usd_mes - gastado_mes_usd(hoy, session=session), 6))
    return LedgerPresupuesto(sobre_semanal=restante, reserva_eventos_pct=reserva_eventos_pct)
