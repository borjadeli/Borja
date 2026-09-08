"""Resolución de cuarentena (doc 22 §3, §8bis) — la búsqueda dirigida que dispara NO_EVALUABLE.

Cuando el gate deja un ítem en NO_EVALUABLE, esto corre UNA búsqueda acotada apuntada a la
pregunta: FTS con los términos → el mejor hit → extraer el hecho citado → persistir → (re-gate).
Si no encuentra, el ítem queda en cuarentena hasta el próximo filing o el vencimiento. NO es un
loop ni un agente perpetuo: es una pasada, event-driven.
"""
from __future__ import annotations

import re
from datetime import date

from backend.nucleo import extractor_citado as EX
from backend.nucleo import fact_store as FS
from backend.nucleo import retrieval
from backend.nucleo.extractor_citado import HechoCitado
from backend.utils import get_logger

log = get_logger(__name__)


def _fecha(s) -> date | None:
    try:
        return date.fromisoformat(str(s)[:10])
    except (ValueError, TypeError):
        return None


def resolver_item(session, *, ticker: str, cik: str, fact_key: str,
                  search_terms: list[str], pregunta: str, anchors: list[str],
                  forms: str | None = None, fact_type: str = "EVENT",
                  entailment: str | None = None,
                  model: str | None = None, max_hits: int = 4) -> HechoCitado | None:
    """Una búsqueda dirigida para resolver UN ítem en cuarentena. Persiste y devuelve el hecho
    fundado, o None si la evidencia no aparece (queda en cuarentena)."""
    # 1. FTS: ¿dónde está la evidencia? (consultar, no crawlear)
    hits: list = []
    for term in search_terms:
        hits += retrieval.buscar_fts(f'"{term}"', cik=cik, forms=forms, limite=2)
        if len(hits) >= max_hits:
            break
    if not hits:
        log.info("cuarentena %s/%s: FTS sin hits para %s", ticker, fact_key, search_terms)
        return None

    # 2. bajar cada hit y ubicar el pasaje relevante; 3. extraer + verificar
    for h in hits[:max_hits]:
        doc = retrieval.bajar(retrieval.Documento(nombre=h.filename, url=h.url, tipo="hit"))
        texto = doc.texto or ""
        win = None
        for a in anchors:
            m = re.search(a, texto, re.I)
            if m:
                win = texto[max(0, m.start() - 150): m.start() + 700]
                break
        if win is None:
            continue
        hecho = EX.extraer_hecho(win, fact_key=fact_key, pregunta=pregunta, model=model)
        hecho = EX.verificar_cita(hecho, texto)
        # Entailment: en el exhibit tampoco se acepta una cita generosa (no inflar desde el 8-K).
        if entailment and hecho.grounded and hecho.value not in (None, False):
            if not EX.verificar_entailment(entailment, hecho.quote, model=model):
                continue                                        # no sostiene el claim → probar otro hit
        if hecho.grounded and hecho.value is not None:
            # 4. persistir (linaje = la accession donde SÍ estaba la evidencia)
            FS.guardar(session, cik=cik, ticker=ticker, fact_key=fact_key, value=hecho.value,
                       support_type=hecho.support_type, fact_type=fact_type, fuente="A",
                       quote=hecho.quote, quote_start=hecho.quote_start, quote_end=hecho.quote_end,
                       source_accession=h.accession, source_url=h.url, accepted_at=_fecha(h.fecha),
                       model_id=model or EX.MODELO_EXTRACCION, prompt_version=EX.PROMPT_VERSION,
                       retriever_version="cuarentena_v1")
            log.info("cuarentena %s/%s: resuelto = %s (%s) desde %s",
                     ticker, fact_key, hecho.value, hecho.support_type, h.accession)
            return hecho
    return None
