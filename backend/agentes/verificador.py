"""Agente Verificador (v2 Fase 3, doc 54 §4.5) — determinista-primero por PROCEDENCIA, 3 estados.

Núcleo determinista (sin API, testeable):
- **procedencia**: la `source_url` de cada claim tiene que estar entre las URLs que trajo web_search en el
  loop del Analista (`fuentes`) o en el fact store. NO se chequea que la URL "resuelva" por HTTP (frágil:
  paywalls, 403 a bots) — se chequea que sea TRAZABLE. Elimina URLs inventadas a costo cero.
- regla de la tesis: cualquier claim en `tesis_claims_soporte` (central) sin procedencia → **FAIL**.
  Claim no-central sin procedencia, o claim central que es declaración de empresa tratada como hecho → **REVIEW**.
- `flags_supervivencia`: going concern / material weakness / restatement detectados en las red flags → el
  PM DEBE responderlos (doc 54 §4.7); no vetan por sí solos.

Un pase LLM opcional (`consistencia_fn`, Sonnet 5.5) puede DEGRADAR el veredicto por inconsistencia
narrativa↔números; nunca lo mejora. El chequeo numérico fino (cited_text vs fuente) queda como mejora futura.
"""
from __future__ import annotations

from collections.abc import Callable
from urllib.parse import urlparse

from backend.agentes.contraste import contrastar_numero
from backend.agentes.schemas import AgentMeta, Check, Dossier, VerificationReport

# Clase epistémica DERIVADA DEL CÓDIGO (de la URL), no de lo que declare el Analista (auditoría P1, corr. 4).
_DOM_REGULADOR = ("sec.gov", "nrc.gov", "fda.gov", "ferc.gov", "federalregister.gov", "uspto.gov",
                  "energy.gov", "treasury.gov", "cftc.gov", "europa.eu")
_MARCA_PR = ("globenewswire", "prnewswire", "businesswire", "newswire", "accesswire", "/press-release",
             "ir.", "investors.", "/investors")


def clase_por_url(url: str | None) -> str:
    """Clase epistémica de una fuente SEGÚN SU URL (no según la etiqueta del LLM):
    `primaria_regulatoria` (SEC/NRC/FDA…) · `company_statement` (press release / IR) · `media_o_busqueda` ·
    `sin_fuente`. Un central que NO es primaria no cuenta como hecho verificado → REVIEW."""
    if not url:
        return "sin_fuente"
    dom = urlparse(url).netloc.lower()
    u = url.lower()
    if any(d in dom for d in _DOM_REGULADOR):
        return "primaria_regulatoria"
    if any(m in u for m in _MARCA_PR):
        return "company_statement"
    return "media_o_busqueda"

PROMPT_VERSION = "verificador_v1"

_PALABRAS_SUPERVIVENCIA = {
    "going_concern": ("going concern", "going_concern", "empresa en marcha"),
    "material_weakness": ("material weakness", "material_weakness", "debilidad material"),
    "restatement": ("restatement", "restate", "reexpresión", "reexpresion"),
}


def flags_supervivencia(red_flags) -> list[str]:
    """Detecta red flags de supervivencia por palabra clave en el tipo/cita (case-insensitive)."""
    out: list[str] = []
    for rf in red_flags:
        texto = f"{getattr(rf, 'tipo', '')} {getattr(getattr(rf, 'cita', None), 'claim', '')}".lower()
        for flag, claves in _PALABRAS_SUPERVIVENCIA.items():
            if flag not in out and any(k in texto for k in claves):
                out.append(flag)
    return out


def verificar(dossier: Dossier, fuentes: list[str], *, hechos_store: list[str] | None = None,
              pack: dict | None = None,
              consistencia_fn: Callable[[Dossier], tuple[str | None, list[str], AgentMeta | None]] | None = None,
              model: str = "claude-sonnet-5-5") -> VerificationReport:
    trazables = set(fuentes) | set(hechos_store or [])
    central = set(dossier.tesis_claims_soporte)
    checks: list[Check] = []
    motivos: list[str] = []
    falla_central = False
    hay_review = False

    # Un dossier sin claims centrales, o con centrales COLGANTES (ids que no existen en `claims`), no tiene
    # respaldo verificable para su tesis → FAIL (antes daba PASS; auditoría P1 §2-B / bug IA 1).
    ids_existentes = {c.claim_id for c in dossier.claims}
    colgantes = central - ids_existentes
    if not central:
        falla_central = True
        motivos.append("sin claims centrales (tesis_claims_soporte vacío): la tesis no tiene respaldo")
    if colgantes:
        falla_central = True
        motivos.append(f"tesis_claims_soporte referencia ids inexistentes: {sorted(colgantes)}")

    for c in dossier.claims:
        es_central = c.claim_id in central
        clase = clase_por_url(c.source_url)
        no_primaria = clase in ("company_statement", "media_o_busqueda", "sin_fuente")
        proc_url = bool(c.source_url) and c.source_url in trazables

        # Contraste NUMÉRICO contra nuestro XBRL del pack (paso 3): si el claim referencia una métrica y
        # tenemos ese DataPoint, la fuente primaria la tenemos NOSOTROS → vale sin importar la URL citada.
        contraste = None
        if pack is not None and c.ref_metrica and c.valor_num is not None:
            contraste = contrastar_numero(c.valor_num, pack.get(c.ref_metrica),
                                          escala=(c.escala or 1.0), periodo=c.periodo)

        numeros_ok = not (contraste is not None and contraste.contradice)
        proc = (contraste.ok if contraste is not None else False) or proc_url
        motivo = (f"XBRL: {contraste.detalle}" if contraste is not None
                  else (f"procedencia trazable ({clase})" if proc_url else "source_url no trazable"))
        checks.append(Check(claim_id=c.claim_id, procedencia_ok=proc, numeros_ok=numeros_ok,
                            es_declaracion_corporativa=no_primaria, dato_vigente=True, motivo=motivo))

        if contraste is not None and contraste.contradice:          # el número CONTRADICE el XBRL
            if es_central:
                falla_central = True
                motivos.append(f"central {c.claim_id} CONTRADICE XBRL: {contraste.detalle}")
            else:
                hay_review = True
        elif contraste is not None and contraste.ok:
            continue                                                # hecho verificado por XBRL (gana a la URL)
        elif not proc_url:
            if es_central:
                falla_central = True
                motivos.append(f"central {c.claim_id} sin procedencia")
            else:
                hay_review = True
        elif no_primaria and es_central:
            hay_review = True
            motivos.append(f"central {c.claim_id}: fuente NO primaria ({clase}) — no es un hecho verificado")

    flags = flags_supervivencia(dossier.red_flags)
    if falla_central:
        veredicto = "fail"
    elif hay_review:
        veredicto = "review"
    else:
        veredicto = "pass"

    meta = AgentMeta(agent="verificador", prompt_version=PROMPT_VERSION, model=model)
    if consistencia_fn is not None:
        override, motivos_llm, meta_llm = consistencia_fn(dossier)
        motivos.extend(motivos_llm)
        if meta_llm is not None:
            meta = meta_llm
        if override in ("review", "fail"):   # el LLM solo DEGRADA
            orden = {"pass": 0, "review": 1, "fail": 2}
            if orden[override] > orden[veredicto]:
                veredicto = override

    return VerificationReport(meta=meta, ticker=dossier.ticker, checks=checks,
                              veredicto=veredicto, flags_supervivencia=flags, motivos=motivos)
