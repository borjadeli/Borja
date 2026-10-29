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
from datetime import date
from urllib.parse import urlparse

from backend.agentes.contraste import contrastar_numero
from backend.agentes.schemas import AgentMeta, Check, Dossier, VerificationReport

# Clase epistémica DERIVADA DEL CÓDIGO (de la URL), no de lo que declare el Analista (auditoría P1, corr. 4).
_DOM_REGULADOR = ("sec.gov", "nrc.gov", "fda.gov", "ferc.gov", "federalregister.gov", "uspto.gov",
                  "energy.gov", "treasury.gov", "cftc.gov", "europa.eu")
_MARCA_PR = ("globenewswire", "prnewswire", "businesswire", "newswire", "accesswire", "/press-release",
             "ir.", "investors.", "/investors")


# Marcas de PRESS RELEASE dentro de un filing SEC (anexos EX-99.x): son comunicados de la empresa, NO el
# cuerpo del 10-K/10-Q/8-K → company_statement, no primaria regulatoria (auditoría r3 #2).
_MARCA_EX99 = ("ex99", "ex-99", "ex_99", "/press", "pressr", "-pr.", "_pr.")


def _fecha_iso(s) -> date | None:
    try:
        return date.fromisoformat(s) if s else None
    except (TypeError, ValueError):
        return None


def clase_por_url(url: str | None) -> str:
    """Clase epistémica de una fuente SEGÚN SU URL (no según la etiqueta del LLM):
    `primaria_regulatoria` (cuerpo de filing SEC / regulador) · `company_statement` (press release / IR /
    EX-99 adjunto) · `media_o_busqueda` · `sin_fuente`. Un central que NO es primaria no cuenta como hecho
    verificado → REVIEW."""
    if not url:
        return "sin_fuente"
    dom = urlparse(url).netloc.lower()
    u = url.lower()
    if any(d in dom for d in _DOM_REGULADOR):
        # dentro de sec.gov un EX-99.x (comunicado adjunto) NO es el cuerpo del filing → company_statement.
        return "company_statement" if any(m in u for m in _MARCA_EX99) else "primaria_regulatoria"
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
              pack: dict | None = None, ultimo_filing_periodico: date | None = None,
              hoy: date | None = None,
              consistencia_fn: Callable[[Dossier], tuple[str | None, list[str], AgentMeta | None]] | None = None,
              model: str = "claude-sonnet-5-5") -> VerificationReport:
    hoy = hoy or date.today()
    trazables = set(fuentes) | set(hechos_store or [])
    central = set(dossier.tesis_claims_soporte)
    checks: list[Check] = []
    motivos: list[str] = []
    notas: list[str] = []
    falla_central = False
    hay_review = False
    n_no_central = 0
    gaps_no_central = 0           # no-centrales sin procedencia (doc 64 B1: tasa, no cada uno)

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

    # 1e — falsador VENCIDO: si la fecha límite ya pasó, el dossier es viejo y no es decidible (FAIL). El
    # monitoreo de eventos (o una re-corrida) tiene que resolver el falsador antes de que el PM lo use.
    fl = _fecha_iso(getattr(dossier.falsador, "fecha_limite", None))
    if fl is not None and fl < hoy:
        falla_central = True
        motivos.append(f"falsador vencido ({dossier.falsador.fecha_limite} < hoy {hoy}): dossier desactualizado")

    for c in dossier.claims:
        es_central = c.claim_id in central
        if not es_central:
            n_no_central += 1
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
            else:                                                   # contradicción no-central es material → REVIEW
                hay_review = True
                motivos.append(f"no-central {c.claim_id} contradice XBRL: {contraste.detalle}")
        elif contraste is not None and contraste.ok:
            continue                                                # hecho verificado por XBRL (gana a la URL)
        elif not proc_url:
            if es_central:
                falla_central = True
                motivos.append(f"central {c.claim_id} sin procedencia")
            else:                                                   # gap no-central: NOTA (no baja a REVIEW por sí solo)
                gaps_no_central += 1
                notas.append(f"no-central {c.claim_id} sin procedencia")
        elif no_primaria and es_central:
            hay_review = True
            motivos.append(f"central {c.claim_id}: fuente NO primaria ({clase}) — no es un hecho verificado")

        # 1d — vigencia: un DATO FINANCIERO central (lleva `ref_metrica`) cuya fuente es ANTERIOR al último
        # filing periódico y NO se pudo contrastar contra XBRL está desactualizado → REVIEW. Solo aplica a
        # datos que se actualizan cada filing (caja/revenue/…), NO a hechos cualitativos (una licencia/OTA de
        # mayo no se "vence" porque después salga un 10-Q; falso positivo detectado en el smoke #3).
        if (es_central and c.ref_metrica and ultimo_filing_periodico is not None
                and not (contraste is not None and contraste.ok)):
            sd = _fecha_iso(c.source_date)
            if sd is not None and sd < ultimo_filing_periodico:
                hay_review = True
                checks[-1].dato_vigente = False
                motivos.append(f"central {c.claim_id}: fuente del {c.source_date} anterior al último filing "
                               f"({ultimo_filing_periodico}) — dato viejo")

    # Tasa de gaps no-centrales (doc 64 B1): PASS con notas mientras sean pocos — ≤3 absoluto O ≤1/3 del total
    # (OR permisivo: gaps aislados no bajan a REVIEW). Solo si una fracción ALTA no tiene procedencia el
    # Analista citó de memoria → contamina la confianza → REVIEW.
    if gaps_no_central > 3 and gaps_no_central > n_no_central / 3:
        hay_review = True
        motivos.append(f"tasa alta de gaps no-centrales ({gaps_no_central}/{n_no_central}) — "
                       f"el dossier cita de memoria")

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
                              veredicto=veredicto, flags_supervivencia=flags, motivos=motivos, notas=notas)
