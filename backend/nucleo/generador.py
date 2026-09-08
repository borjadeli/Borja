"""Capa generadora — la memoria del LLM como MARCO/hipótesis, no como hecho (doc 22 §7bis).

Dado un ticker, K llamadas con framings DISTINTOS generan LEADS (cosas a verificar) y se toma
la UNIÓN (recall). Cada lead se verifica después contra la fuente (FTS + cita). La memoria
propone QUÉ buscar; NUNCA afirma un hecho. Es el opuesto del extractor (precisión por
intersección/unanimidad): acá la varianza es un feature — un fino que un framing olvida, otro
lo trae, y un lead falso no cuesta nada (la búsqueda no encuentra).

En opus-4-8 (sin temperature) la diversidad sale de los FRAMINGS, no de re-samplear.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.nucleo import retrieval
from backend.services.llm import call_llm_json
from backend.utils import get_logger

log = get_logger(__name__)

# Ángulos distintos → leads distintos. Loop-until-dry en producción; acá set base.
FRAMINGS = {
    "cuello": "¿En qué cuello de botella de su industria opera y qué la hace difícil de sustituir "
              "(capex, IP, lead-time, qualification cycle, insumo escaso)? ¿Qué evidencia primaria "
              "(capacidad vendida, lead-times, precios) habría que verificar?",
    "clientes": "¿Quiénes son sus clientes clave y qué evidencia de compromiso económico habría que "
                "buscar en filings (contratos materiales, órdenes, take-or-pay, concentración >10%)?",
    "cadena": "¿De qué proveedores/insumos críticos upstream depende su oferta, y quiénes son sus "
              "competidores nombrados? ¿Qué habría que verificar sobre expansiones de capacidad de ese set?",
    "riesgos": "¿Qué mataría la tesis? ¿Qué chequearía un short-seller (dilución, runway, "
               "concentración, dependencia de un cliente, sustitución tecnológica, restatements)?",
    "eventos": "¿Qué eventos o filings recientes (8-K de contratos, financiación, expansión de "
               "capacidad, cambios regulatorios) habría que traer y verificar?",
}

_SYSTEM = (
    "Sos un GENERADOR DE LEADS para un sistema de inversión determinista. Tu trabajo NO es "
    "afirmar hechos — es proponer QUÉ VERIFICAR y con qué términos de búsqueda, a partir de lo "
    "que sabés de la empresa. Cada lead es una HIPÓTESIS a chequear contra filings primarios "
    "(EDGAR full-text). NUNCA afirmes un número o un hecho como cierto: proponé la búsqueda que "
    "lo confirmaría o lo refutaría. Los `search_terms` deben ser frases que buscarías en el "
    "full-text de EDGAR: nombres de clientes/contrapartes, tipos de contrato, términos técnicos "
    "del insumo/cuello, nombres de competidores. MÁXIMO 5 leads, concisos (lead ≤ 20 palabras, "
    "por_que ≤ 15 palabras). Devolvé EXACTAMENTE este JSON:\n"
    '{"leads": [{"lead": "qué verificar", "search_terms": ["frase1", "frase2"], '
    '"por_que": "por qué importa"}]}'
)


@dataclass
class Lead:
    lead: str
    search_terms: list[str]
    por_que: str
    framing: str
    fts_hits: int | None = None      # corroboración: nº de filings que contienen el término


def generar_leads(ticker: str, *, nombre: str | None = None,
                  framings: dict | None = None, model: str | None = None) -> list[Lead]:
    """K llamadas (una por framing) → lista de leads SIN deduplicar (unión cruda)."""
    fr = framings or FRAMINGS
    who = f"{ticker} ({nombre})" if nombre else ticker
    leads: list[Lead] = []
    for clave, pregunta in fr.items():
        res = call_llm_json(
            system_prompt=_SYSTEM, user_message=f"Empresa: {who}\n\n{pregunta}",
            model=model, max_tokens=2500,
            extra_metadata={"ticker": ticker, "agent": "generador_leads", "framing": clave},
        )
        data = res.parsed_json if isinstance(res.parsed_json, dict) else {}
        for l in (data.get("leads") or []):
            terms = [t for t in (l.get("search_terms") or []) if isinstance(t, str) and t.strip()]
            leads.append(Lead(lead=l.get("lead", ""), search_terms=terms,
                              por_que=l.get("por_que", ""), framing=clave))
    return leads


def unir_leads(leads: list[Lead]) -> list[Lead]:
    """UNIÓN: dedup por término de búsqueda principal normalizado (un fino de un framing se
    conserva aunque otro no lo haya traído)."""
    vistos: dict[str, Lead] = {}
    for l in leads:
        clave = (l.search_terms[0].lower().strip() if l.search_terms else l.lead.lower().strip())
        if clave and clave not in vistos:
            vistos[clave] = l
    return list(vistos.values())


def verificar_leads(leads: list[Lead], *, cik: str, forms: str | None = None) -> list[Lead]:
    """Cada lead → FTS contra los filings del emisor. fts_hits>0 = corroborado en fuente primaria.

    OJO: fts_hits==0 = "no encontrado CON ESTA FRASE" (UNKNOWN), NO "no hay evidencia" (FALSE).
    Un 0 se reintenta con términos más amplios o queda 'sin resolver' — nunca se auto-descarta
    (ej.: el warrant de Amazon existe pero 'Amazon.com warrant' literal no matchea).
    """
    for l in leads:
        total = 0
        for term in l.search_terms[:2]:
            total += len(retrieval.buscar_fts(f'"{term}"', cik=cik, forms=forms, limite=3))
        l.fts_hits = total
    return leads
