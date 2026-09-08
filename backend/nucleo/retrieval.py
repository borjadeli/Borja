"""Recuperación de evidencia primaria (P1 del motor de evidencia, doc 22 §7).

Resuelve el corpus de una empresa a partir de EDGAR y baja el TEXTO REAL —incluidos los
EXHIBITS (Ex-10 contratos materiales, Ex-99 press releases), que es donde viven los
take-or-pay/órdenes/design-wins y que el extractor viejo ignoraba por completo.

No decide nada, no llama al LLM: solo trae documentos fechados con su linaje (accession,
accepted_at, period_end, hash). Es la capa 1-2-3 del pipeline (resolver → descargar →
seccionar la puede consumir aguas abajo).
"""
from __future__ import annotations

import hashlib
import html
import re
import urllib.parse
from dataclasses import dataclass, field

from backend.services import edgar
from backend.utils import get_logger

log = get_logger(__name__)

# Exhibits que importan para tesis de cuellos (doc 22): contratos materiales y press releases.
EXHIBITS_RELEVANTES = ("ex10", "ex-10", "ex99", "ex-99", "ex1", "ex2")

FTS_URL = "https://efts.sec.gov/LATEST/search-index"


@dataclass
class HitFTS:
    accession: str
    filename: str
    form: str
    fecha: str
    url: str


@dataclass
class Documento:
    nombre: str
    url: str
    tipo: str = ""            # 'primary' | 'exhibit'
    texto: str | None = None
    sha256: str | None = None
    n_tokens_aprox: int = 0


@dataclass
class Corpus:
    ticker: str
    cik: str
    accession: str
    form: str
    accepted_at: str | None
    period_end: str | None
    primary: Documento | None = None
    exhibits: list[Documento] = field(default_factory=list)


def _limpiar(bruto: str) -> str:
    """Quita tags, DECODIFICA entidades HTML (&#8220; → "), colapsa whitespace.
    Decodificar es clave: sin esto los regex de extracción fallan sobre comillas/guiones."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", bruto))).strip()


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", "ignore")).hexdigest()


def _carpeta(url: str) -> str:
    """De la URL del primary_doc deriva la carpeta de la accession (para el index.json)."""
    return url.rsplit("/", 1)[0]


def listar_documentos(url_primary: str) -> list[dict]:
    """Enumera los documentos de una accession vía su index.json (name, type, size)."""
    idx = edgar._fetch(f"{_carpeta(url_primary)}/index.json")
    if not idx:
        return []
    return idx.get("directory", {}).get("item", [])


def _es_exhibit_relevante(nombre: str) -> bool:
    n = nombre.lower().replace("_", "").replace("-", "")
    return any(k.replace("-", "") in n for k in EXHIBITS_RELEVANTES) and n.endswith((".htm", ".html", ".txt"))


def bajar(doc: Documento) -> Documento:
    """Baja y limpia el texto de un documento; setea texto/sha256/tokens."""
    html = edgar._fetch_text(doc.url)
    if html:
        doc.texto = _limpiar(html)
        doc.sha256 = _hash(doc.texto)
        doc.n_tokens_aprox = len(doc.texto) // 4
    return doc


# Pre-filtro por TÍTULO (doc 22): clasifica gratis leyendo el encabezado del documento, NO
# contando palabras del cuerpo (la lección AAOI: 'warrant' ×179 era garantía legal). Solo los
# AMBIGUO/DESCONOCIDO pasan al LLM.
CLASIF_PATRONES = {
    "CAPACIDAD": [r"design[\s-]?build", r"\bconstruction\b", r"engineering,?\s+procurement",
                  r"\bE\.?P\.?C\.?\b", r"facility (?:agreement|lease)"],
    "DILUCION_FINANCIACION": [r"note purchase", r"\bindenture\b", r"credit agreement",
                              r"loan agreement", r"securities purchase", r"\bconvertible\b",
                              r"at[\s-]?the[\s-]?market", r"underwriting", r"registration rights",
                              r"\bwarrant(?!ies|y|s to)\b"],
    "COMPENSACION": [r"equity incentive", r"incentive plan", r"employment agreement",
                     r"\bseverance\b", r"restricted stock"],
    "DEMANDA_COMERCIAL": [r"supply agreement", r"master (?:purchase|supply)",
                          r"manufacturing and supply", r"purchase and supply",
                          r"commercial agreement", r"statement of work"],
    "GOBERNANZA": [r"\bbylaws\b", r"certificate of (?:incorporation|designation|amendment)",
                   r"indemnification agreement"],
}
# Títulos genéricos que NO clasifican solos (el caso Amazon: bundlea comercial + warrant).
AMBIGUO_TITULO = [r"transaction agreement", r"strategic agreement", r"framework agreement"]


@dataclass
class Clasificacion:
    tipo: str            # CAPACIDAD | DILUCION_FINANCIACION | DEMANDA_COMERCIAL | COMPENSACION | GOBERNANZA | AMBIGUO | DESCONOCIDO
    titulo: str
    needs_llm: bool
    señales: dict = field(default_factory=dict)


def clasificar_por_titulo(doc: Documento, *, largo_titulo: int = 300) -> Clasificacion:
    """Clasifica un documento por su TÍTULO/encabezado (determinista, gratis).

    Devuelve needs_llm=True para los ambiguos o desconocidos → solo esos gastan LLM.
    """
    titulo = (doc.texto or "")[:largo_titulo]
    señales = {cat: [p for p in pats if re.search(p, titulo, re.I)]
               for cat, pats in CLASIF_PATRONES.items()}
    señales = {c: v for c, v in señales.items() if v}
    if any(re.search(p, titulo, re.I) for p in AMBIGUO_TITULO):
        return Clasificacion("AMBIGUO", titulo, True, señales)
    if len(señales) == 1:
        return Clasificacion(next(iter(señales)), titulo, False, señales)
    if len(señales) > 1:
        return Clasificacion("AMBIGUO", titulo, True, señales)
    return Clasificacion("DESCONOCIDO", titulo, True, señales)


def buscar_fts(query: str, *, cik: str | None = None, forms: str | None = None,
               limite: int = 10) -> list[HitFTS]:
    """Full-text search de EDGAR — CONSULTAR en vez de crawlear (doc 22, productividad).

    `query` como frase exacta va entre comillas ('"take-or-pay"'). Devuelve los filings/
    exhibits que CONTIENEN la frase, sin bajar nada. Es el linchpin que evita leer todo el
    historial: apunta al 1-2 documentos que importan.
    """
    edgar._rate_limit()
    params = {"q": query}
    if cik:
        params["ciks"] = str(cik).zfill(10)
    if forms:
        params["forms"] = forms
    try:
        r = edgar._get_session().get(f"{FTS_URL}?{urllib.parse.urlencode(params)}", timeout=20)
        if r.status_code != 200:
            log.warning("FTS %r -> HTTP %s", query, r.status_code)
            return []
        data = r.json()
    except Exception as e:  # noqa: BLE001
        log.warning("FTS %r falló: %s", query, e)
        return []
    hits: list[HitFTS] = []
    for h in data.get("hits", {}).get("hits", [])[:limite]:
        src = h.get("_source", {})
        acc_dash, _, fname = h.get("_id", "").partition(":")
        cikn = str((src.get("ciks") or [cik or ""])[0] or "").lstrip("0")
        url = (f"https://www.sec.gov/Archives/edgar/data/{cikn}/{acc_dash.replace('-', '')}/{fname}"
               if cikn and fname else "")
        hits.append(HitFTS(accession=acc_dash, filename=fname, form=src.get("file_type", ""),
                           fecha=src.get("file_date", ""), url=url))
    return hits


def resolver_corpus(ticker: str, *, forms: tuple[str, ...] = ("10-Q", "10-K"),
                    con_exhibits: bool = True, bajar_texto: bool = True) -> Corpus | None:
    """Resuelve el filing periódico MÁS RECIENTE de `ticker` y arma su corpus.

    Trae el primary_doc y (con_exhibits) los exhibits relevantes (Ex-10/Ex-99).
    NO aplica point-in-time todavía (as_of_ts): usa el último disponible hoy.
    """
    cik = edgar.get_cik(ticker)
    # Ventana amplia (no los 90d default): buscamos el filing periódico MÁS RECIENTE, que puede tener
    # hasta ~135d (10-Q con lag) o ~1 año (10-K). Con 90d, un nombre con muchos Form 4 recientes pero
    # 10-Q >90d (ej. RKLB) devolvía vacío. fils[0] sigue siendo el más nuevo (submissions ya viene DESC).
    fils = edgar.get_recent_filings(ticker, tipos=forms, dias=400)
    if not cik or not fils:
        log.warning("retrieval — %s: sin CIK/filings", ticker)
        return None
    f = fils[0]
    corpus = Corpus(
        ticker=ticker.upper(), cik=cik, accession=f.accession_number, form=f.tipo,
        accepted_at=str(getattr(f, "accepted_at", f.fecha)), period_end=None,
        primary=Documento(nombre=f.primary_doc, url=f.url, tipo="primary"),
    )
    if con_exhibits:
        for it in listar_documentos(f.url):
            nombre = it.get("name", "")
            if nombre == f.primary_doc or not _es_exhibit_relevante(nombre):
                continue
            url = f"{_carpeta(f.url)}/{nombre}"
            corpus.exhibits.append(Documento(nombre=nombre, url=url, tipo="exhibit"))
    if bajar_texto:
        bajar(corpus.primary)
        for ex in corpus.exhibits:
            bajar(ex)
    return corpus
