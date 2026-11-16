"""Verificador CIEGO (doc 83 F3) — canal de verificación INDEPENDIENTE de evidencia.

El Verificador interno (`verificador.py`) contrasta los claims contra el MISMO data pack que vio el comité →
sus errores están correlacionados (si al pack le falta un 8-K, nadie lo caza). El canal CIEGO rompe esa
correlación: re-extrae los hechos que cargan la valuación DIRECTO de la fuente primaria (EDGAR), **sin ver los
números del dossier** (anti-anclaje), y una reconciliación determinista los compara → PASS / REVIEW / FAIL.

Es meter adentro lo que hace un LLM+web externo: investiga fresco, con inputs no correlacionados. Tres paquetes
de evidencia (doc 83 §4): (1) liquidez y deuda, (2) capitalización (acciones + instrumentos), (3) premisa de la
tesis. Disparado por decisión de capital / conflicto de guarda, no a diario. Modelo barato + escalada.

Este módulo: la reconciliación (PURA, determinista) + la orquestación. La extracción ciega (LLM) es inyectable.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Campos numéricos del puente que se reconcilian, con su tolerancia relativa (un balance puede moverse algo entre
# el extractor y el pack sin ser un error material).
_TOL_REL = 0.05
_CAMPOS_NUM = ("caja", "deuda_total", "acciones_basicas")


@dataclass
class Discrepancia:
    campo: str
    referencia: float | int | str | None     # lo que dice el dossier/ficha
    ciego: float | int | str | None           # lo que extrajo el canal ciego de la fuente primaria
    tipo: str                                 # numerica | presencia | temporal | incompleta
    severidad: str                            # material | menor
    nota: str = ""


@dataclass
class VerificacionCiega:
    ticker: str
    veredicto: str                            # PASS | REVIEW | FAIL
    discrepancias: list[Discrepancia] = field(default_factory=list)
    extraido: dict = field(default_factory=dict)
    cutoff: str | None = None
    costo_usd: float = 0.0

    @property
    def confiable(self) -> bool:
        return self.veredicto == "PASS"


def _rel(a: float, b: float) -> float:
    m = max(abs(a), abs(b))
    return abs(a - b) / m if m > 0 else 0.0


def reconciliar(ciego: dict, referencia: dict, *, tol_rel: float = _TOL_REL) -> tuple[str, list[Discrepancia]]:
    """Compara la extracción ciega vs los valores de referencia (dossier/ficha). Determinista.
    - Numéricos (caja/deuda/acciones): discrepancia MATERIAL si el error relativo supera `tol_rel`.
    - Instrumentos: discrepancia de PRESENCIA si el ciego encontró más (o menos) instrumentos materiales.
    - Dato faltante (None en cualquiera de los dos) → REVIEW (no se pudo reconciliar), no FAIL.
    Veredicto: FAIL si hay alguna material; REVIEW si hay incompletas/menores; PASS si todo concilia."""
    discs: list[Discrepancia] = []
    for c in _CAMPOS_NUM:
        r, g = referencia.get(c), ciego.get(c)
        if r is None or g is None:
            discs.append(Discrepancia(c, r, g, "incompleta", "menor", "falta el dato en un lado"))
            continue
        if _rel(float(r), float(g)) > tol_rel:
            discs.append(Discrepancia(c, r, g, "numerica", "material",
                                      f"error relativo {_rel(float(r), float(g)):.0%} > {tol_rel:.0%}"))
    # instrumentos: comparás la CANTIDAD de instrumentos materiales (el caso MP: el dossier no inventarió converts)
    n_ref = int(referencia.get("n_instrumentos", 0) or 0)
    n_gc = ciego.get("n_instrumentos")
    if n_gc is not None and int(n_gc) != n_ref:
        discs.append(Discrepancia("n_instrumentos", n_ref, int(n_gc), "presencia", "material",
                                  "el canal ciego encontró un número distinto de instrumentos materiales"))
    # evento POSTERIOR al último 10-Q que cambia el balance (deuda nueva / adquisición) y la referencia NO refleja
    # → el balance de referencia está stale (el caso IESC/DBM: $525M de deuda nueva que el dossier decía $0).
    dnp = ciego.get("deuda_nueva_posterior")
    ref_deuda = referencia.get("deuda_total")
    if dnp and float(dnp) > 25e6 and (ref_deuda is None or float(ref_deuda) + 1e6 < float(dnp)):
        discs.append(Discrepancia("deuda_nueva_posterior", ref_deuda, dnp, "temporal", "material",
                                  "un 8-K posterior al 10-Q tomó deuda nueva que la referencia no refleja (balance stale)"))
    if ciego.get("adquisicion_posterior") is True and not referencia.get("adquisicion_conocida"):
        discs.append(Discrepancia("adquisicion_posterior", None, True, "temporal", "material",
                                  "adquisición/disposición material posterior al 10-Q no reflejada en la referencia"))
    # premisa de la tesis: si el ciego la marcó no sostenida → material
    if ciego.get("premisa_sostenida") is False:
        discs.append(Discrepancia("premisa_tesis", referencia.get("premisa"), ciego.get("premisa_nota"),
                                  "interpretacion", "material", "la fuente primaria no sostiene la premisa central"))

    if any(d.severidad == "material" for d in discs):
        veredicto = "FAIL"
    elif discs:
        veredicto = "REVIEW"
    else:
        veredicto = "PASS"
    return veredicto, discs


# --------------------------------------------------------------------------- extractor ciego (LLM barato, EDGAR)

EXTRACTOR_MODEL = "claude-sonnet-5-5"       # barato; escala a Opus solo si un término contractual es ambiguo (futuro)

_SCHEMA_CIEGO = {
    "type": "object", "additionalProperties": False,
    "required": ["caja", "deuda_total", "acciones_basicas", "n_instrumentos", "instrumentos_nota",
                 "premisa_sostenida", "premisa_nota", "eventos_posteriores",
                 "deuda_nueva_posterior", "adquisicion_posterior"],
    "properties": {
        "caja": {"type": ["number", "null"]},               # caja + inversiones de corto plazo (USD)
        "deuda_total": {"type": ["number", "null"]},         # deuda financiera total (USD)
        "acciones_basicas": {"type": ["number", "null"]},    # acciones comunes básicas outstanding
        "n_instrumentos": {"type": ["integer", "null"]},     # cuántos converts/preferidas/warrants materiales
        "instrumentos_nota": {"type": "string"},
        "premisa_sostenida": {"type": ["boolean", "null"]},  # ¿la fuente primaria sostiene la premisa preguntada?
        "premisa_nota": {"type": "string"},
        "eventos_posteriores": {"type": "string"},           # 8-K materiales posteriores al último 10-Q
        # cambios de balance en eventos POSTERIORES al último 10-Q (lo que XBRL no refleja hasta el próximo reporte):
        "deuda_nueva_posterior": {"type": ["number", "null"]},  # deuda nueva tomada en un 8-K posterior (USD)
        "adquisicion_posterior": {"type": ["boolean", "null"]}, # ¿hubo adquisición/disposición material posterior?
    },
}

_SYS_CIEGO = """Sos un Verificador INDEPENDIENTE. Te dan filings SEC primarios de una empresa y una pregunta sobre
la premisa de su tesis. Extraés los HECHOS directamente de los documentos, SIN suponer nada previo.

Devolvés SOLO los datos que PODÉS sostener con los filings (null si no lo encontrás — no inventes):
- caja: efectivo + inversiones de corto plazo (USD absolutos).
- deuda_total: deuda financiera total incluyendo convertibles contabilizadas como deuda (USD).
- acciones_basicas: acciones comunes BÁSICAS outstanding (la carátula del 10-Q/K).
- n_instrumentos: cuántos instrumentos dilutivos MATERIALES hay (notas convertibles, preferidas convertibles,
  warrants). instrumentos_nota: listalos brevemente con sus términos.
- premisa_sostenida: ¿los filings sostienen la premisa preguntada? (true/false/null). premisa_nota: por qué.
- eventos_posteriores: 8-K materiales (adquisición, deuda nueva, emisión) posteriores al último 10-Q/K.
- deuda_nueva_posterior: si un 8-K POSTERIOR al último 10-Q tomó deuda nueva, poné el MONTO en USD (p.ej. un
  Credit Agreement nuevo, un préstamo para financiar una compra). Es la deuda que el XBRL todavía NO refleja.
- adquisicion_posterior: true si hubo una adquisición/disposición material posterior al último 10-Q.
NO te anclés a ningún número previo: no te dieron ninguno. Citá el filing en las notas."""


def extraer_desde_edgar(ticker: str, cutoff: str | None, *, premisa_pregunta: str = "",
                        modelo: str = EXTRACTOR_MODEL, cliente=None, filings_fn=None, fetch_fn=None,
                        dias: int = 200) -> tuple[dict, float]:
    """Extracción CIEGA: baja los filings primarios recientes (10-Q/K + 8-K) y un modelo barato extrae los hechos,
    sin ver el dossier. `premisa_pregunta` es un claim de la tesis a verificar (texto, NO un número → no ancla).
    Devuelve (dict de hechos, costo). Inyectable (filings_fn/fetch_fn/cliente) para test."""
    from backend.agentes.base import Agente
    if filings_fn is None:
        from backend.services.edgar import get_recent_filings
        filings_fn = lambda tk: get_recent_filings(tk, tipos=("10-Q", "10-K", "8-K"), dias=dias)  # noqa: E731
    if fetch_fn is None:
        from ops.gold_contratos import _excerpt
        fetch_fn = lambda url: _excerpt(url, maxlen=6000)  # noqa: E731

    partes = []
    for f in filings_fn(ticker)[:6]:
        partes.append(f"--- {getattr(f, 'tipo', '?')} {getattr(f, 'fecha', '')} items={getattr(f, 'items', '')} ---\n"
                      f"{fetch_fn(f.url)}")
    if not partes:
        return {}, 0.0
    user = (f"Empresa: {ticker}\nCorte: {cutoff or 'hoy'}\nPremisa de la tesis a verificar: "
            f"{premisa_pregunta or '(ninguna)'}\n\n=== FILINGS PRIMARIOS ===\n" + "\n\n".join(partes))
    ag = Agente("verificador-ciego", "ciego-v1", modelo, cliente=cliente)
    j, meta = ag.estructurado(system=_SYS_CIEGO, user=user, payload_schema=_SCHEMA_CIEGO, max_tokens=1024)
    return (j or {}), float(getattr(meta, "cost_usd", 0.0) or 0.0)


def verificar_ciego(ticker: str, referencia: dict, *, extraer_fn, cutoff: str | None = None,
                    tol_rel: float = _TOL_REL) -> VerificacionCiega:
    """Orquesta: extracción ciega (inyectable `extraer_fn(ticker, cutoff) -> (dict, costo)`) → reconciliación.
    `referencia` = valores del dossier/ficha a contrastar (caja/deuda_total/acciones_basicas/n_instrumentos/premisa).
    NO se le pasan esos valores al extractor (anti-anclaje); `extraer_fn` solo ve ticker + cutoff + el protocolo."""
    extraido, costo = extraer_fn(ticker, cutoff)
    veredicto, discs = reconciliar(extraido or {}, referencia, tol_rel=tol_rel)
    return VerificacionCiega(ticker=ticker.upper(), veredicto=veredicto, discrepancias=discs,
                             extraido=extraido or {}, cutoff=cutoff, costo_usd=round(costo or 0.0, 4))


# --------------------------------------------------------------------------- integración al flujo de decisión (F3)

def referencia_de_ficha(ficha) -> dict:
    """Arma la `referencia` para el canal ciego desde una ficha (lo que el dossier cree hoy). deuda_total
    (bruta) = deuda_neta + caja; n_instrumentos = tamaño del inventario; premisa = resumen de la tesis."""
    caja = getattr(ficha, "caja", None)
    dn = getattr(ficha, "deuda_neta", None)
    return {
        "caja": caja,
        "deuda_total": (dn + caja) if (dn is not None and caja is not None) else None,
        "acciones_basicas": getattr(ficha, "acciones", None),
        "n_instrumentos": len(getattr(ficha, "instrumentos", []) or []),
        "premisa": (getattr(ficha, "tesis_resumen", "") or "")[:200],
    }


def verificar_decision(aumentos, fichas: dict, *, extractor=None, cutoff: str | None = None) -> dict:
    """Corre el canal ciego SOLO sobre los nombres que el PM quiere comprar/aumentar (trigger por decisión de
    capital, doc 83 §4). Devuelve {ticker: VerificacionCiega}. `extractor(ticker, cutoff, premisa)->(dict,costo)`
    inyectable (default = extraer_desde_edgar real). El runner pasa `{tk: vc.veredicto}` al gate como ciego_por_ticker."""
    extractor = extractor or (lambda tk, c, premisa: extraer_desde_edgar(tk, c, premisa_pregunta=premisa))
    out: dict = {}
    for tk in {t.upper() for t in aumentos}:
        f = (fichas or {}).get(tk)
        if f is None:
            continue
        ref = referencia_de_ficha(f)
        out[tk] = verificar_ciego(tk, ref, cutoff=cutoff,
                                  extraer_fn=lambda t, c, _r=ref: extractor(t, c, _r.get("premisa", "")))
    return out
