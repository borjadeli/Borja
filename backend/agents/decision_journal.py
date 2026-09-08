"""Decision Journal (v4.2 sec 8 + 10) — log estructurado append-only.

Cada decisión de capital o rechazo queda registrada con motivo, decisor
(humano/sistema), y links a la recomendación/evento que la disparó.

Mitiga el failure mode #2 (rubber-stamping humano): al obligar a registrar
motivo de cada decisión, el patrón "ratifica-todo-sin-pensar" queda visible
para revisión retrospectiva.
"""
from __future__ import annotations

from backend.database import session_scope
from backend.models import DecisionJournal
from backend.utils import get_logger, utcnow

log = get_logger(__name__)


def registrar_decision(
    accion: str,
    ticker: str | None = None,
    decisor: str = "humano",
    motivo: str | None = None,
    rec_id: int | None = None,
    evento_id: int | None = None,
    metadata: dict | None = None,
) -> int:
    """Registra una entrada en el decision journal. Retorna el id."""
    with session_scope() as s:
        entry = DecisionJournal(
            timestamp=utcnow(),
            ticker=ticker.upper() if ticker else None,
            accion=accion,
            decisor=decisor,
            motivo=motivo,
            rec_id=rec_id,
            evento_id=evento_id,
            metadata_json=metadata,
        )
        s.add(entry)
        s.flush()
        entry_id = entry.id
    log.info(
        "decision_journal — id=%d accion=%s ticker=%s decisor=%s",
        entry_id, accion, ticker, decisor,
    )
    return entry_id


def listar_decisiones(
    ticker: str | None = None,
    accion: str | None = None,
    desde: str | None = None,
    limit: int = 100,
) -> list[dict]:
    with session_scope() as s:
        q = s.query(DecisionJournal)
        if ticker:
            q = q.filter_by(ticker=ticker.upper())
        if accion:
            q = q.filter_by(accion=accion)
        if desde:
            q = q.filter(DecisionJournal.timestamp >= desde)
        rows = q.order_by(DecisionJournal.id.desc()).limit(limit).all()
        return [
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "ticker": e.ticker,
                "accion": e.accion,
                "decisor": e.decisor,
                "motivo": e.motivo,
                "rec_id": e.rec_id,
                "evento_id": e.evento_id,
                "metadata": e.metadata_json,
                "resultado_post": e.resultado_post,
                "resultado_post_at": e.resultado_post_at.isoformat() if e.resultado_post_at else None,
            }
            for e in rows
        ]


def anotar_resultado(decision_id: int, resultado: str) -> dict:
    """Llena el resultado posterior de una decisión (cuando se conoce)."""
    with session_scope() as s:
        e = s.query(DecisionJournal).filter_by(id=decision_id).first()
        if e is None:
            raise ValueError(f"decision {decision_id} no existe")
        e.resultado_post = resultado
        e.resultado_post_at = utcnow()
        return {"id": e.id, "resultado_post": e.resultado_post}
