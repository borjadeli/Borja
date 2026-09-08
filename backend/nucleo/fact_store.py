"""Fact store — persistencia de hechos fundados (doc 22 §4, componentes F/G del MVP).

Append-only e inmutable, identidad lógica = (cik, fact_key). Tres operaciones:
  - guardar(): inserta un hecho; dedup idempotente (misma accession+hash+valor → confirma,
    no duplica) y supersesión (una key nueva marca superseded la vigente anterior).
  - snapshot_vigente(): compila el estado vigente (point-in-time por accepted_at).
  - diff(): el DELTA de evidencia entre dos accessions (la señal, no solo auditoría).

El motor determinista lee del snapshot vigente; nunca de una extracción cruda.
"""
from __future__ import annotations

import json
from datetime import date

from sqlalchemy import select

from backend.ledger.models import NxFact
from backend.utils import get_logger

log = get_logger(__name__)


def _enc(v) -> str | None:
    return json.dumps(v, ensure_ascii=False, sort_keys=True) if v is not None else None


def _dec(s):
    try:
        return json.loads(s) if s is not None else None
    except (json.JSONDecodeError, TypeError):
        return s


def guardar(session, *, cik: str, ticker: str, fact_key: str, value,
            support_type: str = "UNKNOWN", fact_type: str = "SNAPSHOT",
            estado: str | None = None, fuente: str | None = None,
            quote: str | None = None, quote_start: int | None = None,
            quote_end: int | None = None, chunk_id: str | None = None,
            source_accession: str | None = None, source_url: str | None = None,
            accepted_at: date | None = None, period_end: date | None = None,
            valid_from: date | None = None, valid_until: date | None = None,
            document_hash: str | None = None, model_id: str | None = None,
            prompt_version: str | None = None, retriever_version: str | None = None,
            schema_version: str | None = None, registrado: date | None = None) -> NxFact:
    """Inserta un hecho fundado. Dedup idempotente + supersesión de la vigente anterior."""
    val = _enc(value)
    # Dedup: misma (cik, fact_key, accession, hash) con mismo valor → re-extracción idempotente.
    existente = session.execute(
        select(NxFact).where(
            NxFact.cik == cik, NxFact.fact_key == fact_key,
            NxFact.source_accession == source_accession, NxFact.document_hash == document_hash,
        )
    ).scalars().first()
    if existente is not None and existente.value == val and existente.support_type == support_type:
        existente.last_confirmed_at = registrado or accepted_at
        session.flush()
        return existente

    # Vigente anterior de la misma key (para supersesión).
    prev = session.execute(
        select(NxFact).where(
            NxFact.cik == cik, NxFact.fact_key == fact_key, NxFact.superseded_by.is_(None),
        ).order_by(NxFact.accepted_at.desc())
    ).scalars().first()

    f = NxFact(
        cik=cik, ticker=ticker.upper(), fact_key=fact_key, value=val,
        support_type=support_type, estado=estado, fact_type=fact_type, fuente=fuente,
        quote=quote, quote_start=quote_start, quote_end=quote_end, chunk_id=chunk_id,
        source_accession=source_accession, source_url=source_url,
        accepted_at=accepted_at, period_end=period_end,
        valid_from=valid_from or accepted_at, valid_until=valid_until,
        document_hash=document_hash, model_id=model_id, prompt_version=prompt_version,
        retriever_version=retriever_version, schema_version=schema_version,
        last_confirmed_at=registrado or accepted_at, registrado=registrado,
    )
    session.add(f)
    session.flush()

    # La nueva supersede a la anterior solo si es igual o más reciente (no revivir hacia atrás).
    if prev is not None and prev.id != f.id:
        if accepted_at is None or prev.accepted_at is None or prev.accepted_at <= accepted_at:
            prev.superseded_by = f.id
            if prev.valid_until is None:
                prev.valid_until = accepted_at
    session.flush()
    return f


def snapshot_vigente(session, ticker: str | None = None, *, cik: str | None = None,
                     as_of: date | None = None) -> dict[str, NxFact]:
    """Compila el estado vigente: por fact_key, el hecho de mayor accepted_at (≤ as_of si se pasa).

    Point-in-time correcto: filtrar por accepted_at ≤ as_of y quedarse con el último por key
    reconstruye lo que se sabía en `as_of` sin depender de la cadena de supersesión.
    """
    q = select(NxFact)
    if cik:
        q = q.where(NxFact.cik == cik)
    if ticker:
        q = q.where(NxFact.ticker == ticker.upper())
    if as_of:
        q = q.where(NxFact.accepted_at <= as_of)
    mejor: dict[str, NxFact] = {}
    for f in session.execute(q).scalars().all():
        cur = mejor.get(f.fact_key)
        fa, ca = (f.accepted_at or date.min), (cur.accepted_at or date.min if cur else date.min)
        if cur is None or fa > ca or (fa == ca and f.id > cur.id):
            mejor[f.fact_key] = f
    return mejor


def diff(session, ticker: str, acc_a: str, acc_b: str) -> list[dict]:
    """DELTA de evidencia entre dos accessions (la señal): ADDED/REMOVED/VALUE_CHANGED/
    SUPPORT_CHANGED/CONFIRMED_AGAIN por fact_key."""
    def por_acc(acc: str) -> dict[str, NxFact]:
        filas = session.execute(
            select(NxFact).where(NxFact.ticker == ticker.upper(),
                                 NxFact.source_accession == acc)
        ).scalars().all()
        return {f.fact_key: f for f in filas}

    a, b = por_acc(acc_a), por_acc(acc_b)
    cambios: list[dict] = []
    for k in sorted(set(a) | set(b)):
        fa, fb = a.get(k), b.get(k)
        if fa is None:
            cambios.append({"fact_key": k, "tipo": "ADDED", "new": _dec(fb.value)})
        elif fb is None:
            cambios.append({"fact_key": k, "tipo": "REMOVED", "old": _dec(fa.value)})
        elif fa.value != fb.value:
            cambios.append({"fact_key": k, "tipo": "VALUE_CHANGED",
                            "old": _dec(fa.value), "new": _dec(fb.value)})
        elif fa.support_type != fb.support_type:
            cambios.append({"fact_key": k, "tipo": "SUPPORT_CHANGED",
                            "old": fa.support_type, "new": fb.support_type})
        else:
            cambios.append({"fact_key": k, "tipo": "CONFIRMED_AGAIN"})
    return cambios
