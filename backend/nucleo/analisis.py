"""Orquestador vertical — un nombre punta a punta (doc 22 §7, wireo de las piezas).

`analizar_ticker` ata el motor de evidencia: resolver el filing más reciente → por cada
`fact_key` del registry, ubicar el pasaje (retrieval dirigido), extraer con cita (D),
verificar (E) y persistir en el fact store (F). Devuelve el snapshot vigente. NO decide nada
(no toca gate ni sizing): deja los HECHOS fundados listos para el motor determinista.

La capa generadora (§7bis) puede sumar fact_keys/leads dinámicos; acá corre el set base.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from backend.nucleo import cuarentena
from backend.nucleo import extractor_citado as EX
from backend.nucleo import fact_store as FS
from backend.nucleo import retrieval
from backend.nucleo.extractor import extraer_deterministas
from backend.nucleo.fact_keys import FACT_KEYS, FactKeySpec
from backend.utils import get_logger

log = get_logger(__name__)

# Términos FTS para buscar la demanda en 8-K/exhibits (los contratos materiales viven ahí).
_DEMANDA_8K = {
    "demanda_minimo": ['"take-or-pay"', '"minimum purchase"', '"non-cancelable"'],
    "demanda_realizada": ['"accounted for"', '"revenue from"'],
}


def construir_regiones(texto: str, anchors: list[str], *, w: int = 550, pre: int = 150,
                       max_regs: int = 4) -> tuple[list[tuple[int, int]], list[tuple[int, int]], list[int]]:
    """Devuelve (regiones_capadas, regiones_sin_cap, posiciones_anchor) como rangos [start,end)
    de char sobre `texto`.

    `_window` usa SOLO las capadas (comportamiento del pipeline). El harness de retrieval
    (gold_retrieval) usa las tres para diagnosticar la CAUSA de un miss: sin_cap - capadas revela
    los que tira el cap de max_regs (miss tipo C, IA2); posiciones_anchor revela si NINGÚN anchor
    matcheó cerca del gold (miss tipo A). Fuente única de la lógica de regiones."""
    pos = sorted({m.start() for a in anchors for m in re.finditer(a, texto, re.I)})
    if not pos:
        return [], [], []

    # 1) agrupar TODAS las posiciones en regiones contiguas (sin cap), contando cuántos anchors caen
    #    en cada una (densidad = señal de "esta es la divulgación real", no un match suelto).
    grupos: list[list[int]] = [[pos[0], pos[0], 1]]  # [start, end, n_anchors]
    for p in pos[1:]:
        if p - grupos[-1][1] <= w:                   # cerca → extender y sumar densidad
            grupos[-1][1], grupos[-1][2] = p, grupos[-1][2] + 1
        else:
            grupos.append([p, p, 1])
    sincap = [(max(0, s - pre), e + w) for s, e, _ in grupos]

    # 2) capada = top max_regs por DENSIDAD (no por posición): antes se tiraba la buena solo por venir
    #    más tarde en el doc (miss tipo C, ej. AAOI Digicomm / OKTA RPO). Desempate por posición; se
    #    devuelve ordenada por posición para que el extractor lea en orden natural.
    top = sorted(grupos, key=lambda g: (-g[2], g[0]))[:max_regs]
    capadas = [(max(0, s - pre), e + w) for s, e, _ in sorted(top, key=lambda g: g[0])]
    return capadas, sincap, pos


def _window(texto: str, anchors: list[str], *, w: int = 550, pre: int = 150,
            max_regs: int = 4) -> str | None:
    """Junta hasta max_regs REGIONES relevantes (todos los matches de los anchors, no solo el
    primero) → el extractor ve las secciones que importan, no un boilerplate suelto. Una llamada."""
    capadas, _, _ = construir_regiones(texto, anchors, w=w, pre=pre, max_regs=max_regs)
    if not capadas:
        return None
    return "\n…\n".join(texto[s:e] for s, e in capadas)


def _fecha(s) -> date | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s)).date()
    except ValueError:
        try:
            return date.fromisoformat(str(s)[:10])
        except ValueError:
            return None


# Los 3 hechos binarios citados de los que se DERIVA la tier de demanda (VALIDATED/COMMITTED/REALIZED,
# doc 22 §8bis). Subconjunto barato del registry: NO pasa por el compiler/haircuts (aún vacíos).
DEMANDA_FACT_KEYS = ("cliente_nombrado", "demanda_minimo", "demanda_realizada")


def extraer_demanda(session, ticker: str, *, model: str | None = None) -> dict:
    """Extrae SOLO los 3 hechos de demanda citados y persiste. Devuelve el snapshot vigente.

    Cache-guard: si el snapshot ya tiene los 3 hechos para la accession del filing vigente, NO re-llama
    al LLM (dedup por filing, como el paper con nucleo_hechos). Tajada mínima buildable (doc 32 §5, B1a).
    """
    corpus = retrieval.resolver_corpus(ticker, forms=("10-Q", "10-K"), con_exhibits=False)
    if corpus is None:
        log.warning("extraer_demanda — %s: sin corpus", ticker)
        return FS.snapshot_vigente(session, ticker)
    snap = FS.snapshot_vigente(session, ticker)
    fresco = all(
        (f := snap.get(fk)) is not None and getattr(f, "source_accession", None) == corpus.accession
        for fk in DEMANDA_FACT_KEYS
    )
    if fresco:                                # ya extraído para este filing → no re-gastar LLM
        return snap
    specs = [s for s in FACT_KEYS if s.fact_key in DEMANDA_FACT_KEYS]
    return analizar_ticker(session, ticker, specs=specs, model=model, resolver_8k=False)


def extraer_e1(session, ticker: str, *, model: str | None = None) -> dict:
    """E1 (doc 14 §E1): extrae SOLO `backlog_no_cancelable` (el tipo de contrato del RPO) y persiste.

    Guard PROPIO por accession → no re-gasta lo ya extraído para el filing vigente, y NO re-corre los 3
    hechos de demanda (que tienen su propio guard en `extraer_demanda`). Barato: 1 fact_key targeted.
    Con esto `/hoja` usa el tipo de contrato REAL (firm_po 0.85 / cancelable 0.60) en vez del `cancelable
    ASUMIDO` conservador que aplica cuando el hecho no está en el fact store (doc 14 §E1, compilador §E1)."""
    corpus = retrieval.resolver_corpus(ticker, forms=("10-Q", "10-K"), con_exhibits=False)
    if corpus is None:
        log.warning("extraer_e1 — %s: sin corpus", ticker)
        return FS.snapshot_vigente(session, ticker)
    snap = FS.snapshot_vigente(session, ticker)
    f = snap.get("backlog_no_cancelable")
    if f is not None and getattr(f, "source_accession", None) == corpus.accession:
        return snap                            # ya extraído para este filing → no re-gastar LLM
    specs = [s for s in FACT_KEYS if s.fact_key == "backlog_no_cancelable"]
    return analizar_ticker(session, ticker, specs=specs, model=model, resolver_8k=False)


def extraer_carril(session, ticker: str, *, model: str | None = None) -> dict:
    """Extrae los hechos del carril especulativo (`FACT_KEYS_CARRIL`, doc 29 §2 gate + §3 rúbrica) y persiste.

    Solo tiene sentido para candidatos de OPCIONALIDAD (elegibles fuera del libro duro por valuación). Guard
    propio por accession → no re-gasta. Costo LLM aparte (7 fact_keys con entailment). Con esto `carril.
    construir_hechos_carril` arma el `HechosCarril` real y el gate §2 puede admitir (hoy admite 0 sin esto)."""
    from backend.nucleo.fact_keys import FACT_KEYS_CARRIL
    corpus = retrieval.resolver_corpus(ticker, forms=("10-Q", "10-K"), con_exhibits=False)
    if corpus is None:
        log.warning("extraer_carril — %s: sin corpus", ticker)
        return FS.snapshot_vigente(session, ticker)
    snap = FS.snapshot_vigente(session, ticker)
    claves = [s.fact_key for s in FACT_KEYS_CARRIL]
    fresco = all(
        (f := snap.get(fk)) is not None and getattr(f, "source_accession", None) == corpus.accession
        for fk in claves
    )
    if fresco:
        return snap
    return analizar_ticker(session, ticker, specs=list(FACT_KEYS_CARRIL), model=model, resolver_8k=True)


def analizar_ticker(session, ticker: str, *, specs: list[FactKeySpec] | None = None,
                    model: str | None = None, forms: tuple[str, ...] = ("10-Q", "10-K"),
                    resolver_8k: bool = False) -> dict:
    """Corre el motor de evidencia sobre `ticker` y persiste los hechos. Devuelve el snapshot vigente.

    resolver_8k: si un hecho de demanda que ESCALA tier no está afirmativo en el 10-Q, busca la
    evidencia en 8-K/exhibits (los contratos materiales viven ahí — caso AAOI/Amazon). Con entailment.
    """
    specs = specs or FACT_KEYS
    corpus = retrieval.resolver_corpus(ticker, forms=forms, con_exhibits=False)
    if corpus is None:
        log.warning("analisis — %s: sin corpus", ticker)
        return {}
    texto = corpus.primary.texto or ""
    det = extraer_deterministas(ticker)
    acc_date = _fecha(corpus.accepted_at)

    for spec in specs:
        base = dict(cik=corpus.cik, ticker=ticker, fact_key=spec.fact_key,
                    fact_type=spec.fact_type, source_accession=corpus.accession,
                    source_url=corpus.primary.url, accepted_at=acc_date,
                    document_hash=corpus.primary.sha256, model_id=model or EX.MODELO_EXTRACCION,
                    prompt_version=EX.PROMPT_VERSION, retriever_version="retrieval_v1")
        win = _window(texto, spec.anchors)
        if win is None:                       # el pasaje no está → NO se inventa
            FS.guardar(session, value=None, support_type="UNKNOWN",
                       estado="UNKNOWN_NOT_DISCLOSED", **base)
            continue
        xbrl_v = None
        if spec.xbrl == "margen_bruto" and det.get("margen_bruto") is not None:
            xbrl_v = det["margen_bruto"] / 100.0
        h = EX.extraer_hecho(win, fact_key=spec.fact_key, pregunta=spec.pregunta,
                             model=model, xbrl_value=xbrl_v)
        h = EX.verificar_cita(h, texto)       # offsets sobre el filing completo
        # Entailment: si el hecho ESCALA una tier y su valor es afirmativo, el pasaje tiene que
        # SOSTENER el claim estricto (no solo existir verbatim). Si no → se baja a False (conservador).
        if spec.entailment and h.grounded and h.value not in (None, False):
            if not EX.verificar_entailment(spec.entailment, h.quote, model=model):
                h.value = False
                h.derivacion = "entailment: el pasaje no sostiene el claim estricto → False"
        FS.guardar(session, value=h.value, support_type=h.support_type, fuente="A",
                   quote=h.quote, quote_start=h.quote_start, quote_end=h.quote_end, **base)

    # Resolución de demanda en 8-K/exhibits: los contratos materiales que escalan la tier no
    # están en el 10-Q sino en un 8-K (caso AAOI/Amazon). Con entailment (no inflar desde el 8-K).
    if resolver_8k:
        snap = FS.snapshot_vigente(session, ticker)
        for fk, terms in _DEMANDA_8K.items():
            f = snap.get(fk)
            if f is not None and FS._dec(f.value) is True:
                continue                       # ya afirmativo en el 10-Q
            spec = next((s for s in specs if s.fact_key == fk), None)
            if spec is None:
                continue
            cuarentena.resolver_item(session, ticker=ticker, cik=corpus.cik, fact_key=fk,
                                     search_terms=terms, pregunta=spec.pregunta, anchors=spec.anchors,
                                     forms="8-K", entailment=spec.entailment, model=model)
    return FS.snapshot_vigente(session, ticker)
