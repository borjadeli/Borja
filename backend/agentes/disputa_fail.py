"""Canal de disputa del FAIL (v2 Fase 4, doc 55 §4.1) — el FAIL es el nuevo VRNS.

Principio rector del doc 55: un límite DURO con un input de LLM (acá el veredicto FAIL del Verificador)
necesita un **canal de disputa que NO es override**. El PM presenta una objeción estructurada (qué claim,
por qué el dato es artefacto, qué fuente lo contradice) y el Verificador **re-corre en contexto fresco**:

- Quien decide NO es el PM: es un **re-chequeo independiente** (`refetch_fn`) que confirma (o no) la fuente
  propuesta. En producción es una búsqueda web fresca que valida que la URL existe y respalda el claim; acá
  es inyectable. Solo las URLs que el re-chequeo CONFIRMA se agregan como trazables → el PM nunca overridea.
- Con las fuentes confirmadas agregadas, se re-verifica. Si el veredicto mejora (sale del FAIL) la disputa la
  gana el PM; si el FAIL se sostiene, queda FAIL y se registra.
- `LedgerDisputas`: contador append-only ganadas/perdidas. Si el PM gana muchas → el Verificador está fallando;
  si pierde casi todas → se usa como lobby (ambas señales salen de las métricas).
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from backend.agentes.schemas import Dossier, VerificationReport
from backend.agentes.verificador import verificar

_DISPUTAS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "ledger_disputas_v2.jsonl"


class DisputaFAIL(BaseModel):
    """Objeción estructurada del PM a un claim que causó FAIL (doc 55 §4.1)."""
    claim_id: str
    por_que_artefacto: str                   # por qué el dato es un artefacto / está mal
    fuente_propuesta: str                    # URL que, según el PM, contradice el dato o respalda el claim
    cited_text: str | None = None            # texto citado de esa fuente


@dataclass
class ResultadoDisputa:
    report: VerificationReport               # veredicto re-corrido (puede seguir siendo fail)
    a_favor_pm: bool                         # True si el veredicto salió del FAIL
    veredicto_previo: str
    veredicto_nuevo: str
    fuentes_confirmadas: list[str]           # URLs que el re-chequeo independiente confirmó


def disputar(dossier: Dossier, fuentes_previas: list[str], disputa: DisputaFAIL, *,
             refetch_fn: Callable[[DisputaFAIL], list[str]],
             hechos_store: list[str] | None = None,
             consistencia_fn: Callable | None = None) -> ResultadoDisputa:
    """Re-corre la verificación con la objeción del PM. `refetch_fn` es el re-chequeo INDEPENDIENTE que
    confirma (o no) la fuente propuesta; devuelve las URLs trazables confirmadas (vacío = no confirmó)."""
    previo = verificar(dossier, fuentes_previas, hechos_store=hechos_store)
    confirmadas = [u for u in (refetch_fn(disputa) or []) if u]
    nuevas = list(dict.fromkeys([*fuentes_previas, *confirmadas]))
    report = verificar(dossier, nuevas, hechos_store=hechos_store, consistencia_fn=consistencia_fn)
    a_favor = previo.veredicto == "fail" and report.veredicto != "fail"
    return ResultadoDisputa(report=report, a_favor_pm=a_favor, veredicto_previo=previo.veredicto,
                            veredicto_nuevo=report.veredicto, fuentes_confirmadas=confirmadas)


# --------------------------------------------------------------------------- contador (append-only)

class RegistroDisputa(BaseModel):
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ticker: str
    claim_id: str
    a_favor_pm: bool
    veredicto_previo: str
    veredicto_nuevo: str


class MetricasDisputas(BaseModel):
    total: int = 0
    ganadas_pm: int = 0                      # el PM sacó el dossier del FAIL
    perdidas_pm: int = 0                     # el FAIL se sostuvo
    ratio_ganadas: float | None = None       # ganadas / total (None si no hay disputas)


class LedgerDisputas:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path or _DISPUTAS_PATH)

    def registrar(self, ticker: str, disputa: DisputaFAIL, res: ResultadoDisputa) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        reg = RegistroDisputa(ticker=ticker.upper(), claim_id=disputa.claim_id, a_favor_pm=res.a_favor_pm,
                              veredicto_previo=res.veredicto_previo, veredicto_nuevo=res.veredicto_nuevo)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(reg.model_dump_json() + "\n")

    def metricas(self) -> MetricasDisputas:
        if not self.path.exists():
            return MetricasDisputas()
        regs = [RegistroDisputa.model_validate_json(l) for l in self.path.read_text(
            encoding="utf-8").splitlines() if l.strip()]
        ganadas = sum(1 for r in regs if r.a_favor_pm)
        total = len(regs)
        return MetricasDisputas(total=total, ganadas_pm=ganadas, perdidas_pm=total - ganadas,
                                ratio_ganadas=round(ganadas / total, 4) if total else None)
