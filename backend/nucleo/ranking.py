"""Wiring del ranking v3 — arma los 4 pilares SOLO desde datos reales (doc 26).

`evaluar_ticker` compone: EDGAR determinista (economía, revenue) + fact store (demanda) +
[pendiente de plomería: Form 4 / histórico de shares / peers para ejecución y valuación] → los
4 pilares → tier + ficha. Donde falta el dato, el pilar queda UNKNOWN/confianza insuficiente
(honesto: no se inventa). NO llama al LLM: usa lo determinista + lo ya persistido.
"""
from __future__ import annotations

from backend.nucleo import fact_store as FS
from backend.nucleo import politica
from backend.nucleo.evaluacion import Evaluacion, evaluar
from backend.nucleo.extractor import extraer_deterministas
from backend.nucleo.fidelidad import canon
from backend.nucleo.fragility import HechosFragility, calcular_fragility_score, cap_celda
from backend.services import edgar

# Tasa de descuento por arquetipo → ÚNICA fuente de verdad en politica.R_ARQUETIPO (v1.1). Antes había
# aquí un duplicado divergente (0.10/0.14/0.16/0.22) que subvaluaba el riesgo; borrado en la unificación
# de la triangulación 2026-08 (misma magnitud que usan templates/bridge/pre_revenue).


def _clasificar_arquetipo(det: dict) -> str:
    """Arquetipo determinista aproximado desde EDGAR (revenue headline + crecimiento + FCF).
    Aproximación: usa revenue headline (el elegible ASC 606 refina con el extractor)."""
    rev = det.get("revenue_ttm")
    g = canon(det.get("crecimiento_headline_yoy"), tipo="crecimiento", es_pct=True)
    fcf = det.get("fcf_ttm")
    if rev is None or rev < 10e6:
        return "Pre-revenue"
    if rev < 50e6:
        return "Tracción"
    if g is not None and g >= 0.25:
        return "Growth"
    if fcf is not None and fcf > 0:
        return "Madura"
    return "Tracción"
from backend.nucleo.pilares import (
    HechosEjecucion, pilar_demanda, pilar_economia, pilar_ejecucion,
)
from backend.nucleo.quality import HechosQuality

_DEMANDA_TIER = {"REALIZED": 3, "COMMITTED": 2, "VALIDATED": 1, "UNKNOWN": 0}


def _snap(snap: dict, key: str):
    """Valor decodificado del snapshot SOLO si el hecho es DIRECT/DERIVED (fundado). Si no, None."""
    f = snap.get(key)
    if f is None or f.support_type not in ("DIRECT", "DERIVED"):
        return None
    return FS._dec(f.value)


# Hechos de VETO de SUPERVIVENCIA que se extraen por LLM (pueden quedar UNKNOWN). La dilución tóxica del veto
# viene de XBRL (siempre computable) y NO entra acá. Lección SYM (2026-08-31): un nombre con restatement NO
# extraído salía COVERED/underwritable porque `bool(None)=False` ⇒ sin veto. Regla: ausencia de dato ≠ ausencia
# de veto. Si alguno de estos NO está EXTRAÍDO+FUNDADO, no se compromete capital → abstención (WATCH).
FACT_KEYS_VETO_SUPERVIVENCIA = ("restatement_reciente",)


def _fact_extraido(snap: dict, key: str) -> bool:
    """¿El hecho existe en el snapshot y está FUNDADO (DIRECT/DERIVED)? Distingue 'extraído=False' de 'nunca
    extraído' — que `_snap` colapsa a None (y `bool(None)` a False, el bug de SYM)."""
    f = snap.get(key)
    return f is not None and f.support_type in ("DIRECT", "DERIVED")


UMBRAL_PARTE_REL_FLAG = 0.50   # rp_% ≥50% → FLAG visible (el PM/humano juzga; NO auto-excluye)


def _demanda_de_snapshot(snap: dict, rp_pct: float | None = None) -> tuple[int, str, list]:
    """Tier de demanda de hechos citados, ORIENTATIVO (el PM/humano juzga los bordes con la cita).
    Decisión 2026-08-11 (tras triangulación + verificación): el auto-tier fino es frágil para este
    universo heterogéneo (cliente nombrado vs categoría, related-party en texto, comparativos viejos) →
    NO se auto-excluye por gates difusos; se muestra el tier + la CITA + flags (ej. related_party_pct de
    XBRL) para que el decisor juzgue. `rp_pct` (de edgar.get_related_party_pct, determinista) se surface
    como flag si ≥50%, NO como veto. Estabilidad: extractor a temperature=0.
    REALIZED > COMMITTED > VALIDATED > UNKNOWN."""
    realizada = _snap(snap, "demanda_realizada") is True
    minimo = _snap(snap, "demanda_minimo") is True
    contraparte = _snap(snap, "cliente_nombrado") is True
    continuidad = _snap(snap, "growth_hecho_continuidad") is True
    hechos = []
    for k in ("demanda_realizada", "demanda_minimo", "cliente_nombrado", "growth_hecho_continuidad"):
        f = snap.get(k)
        if f is not None and f.support_type in ("DIRECT", "DERIVED"):
            hechos.append({"claim": f"{k}={FS._dec(f.value)}", "fuente_tier": f.fuente or "?",
                           "quote": (f.quote or "")[:80]})
    if rp_pct is not None and rp_pct >= UMBRAL_PARTE_REL_FLAG:      # flag informativo, NO veto
        hechos.append({"claim": f"related_party_pct={rp_pct:.0%}", "fuente_tier": "XBRL",
                       "quote": f"parte relacionada = {rp_pct:.0%} del revenue → revisar"})
    if realizada:
        return 3, "UNKNOWN", hechos          # REALIZED (revenue de cliente nombrado, no dominado por matriz)
    if minimo:
        return 2, "UNKNOWN", hechos          # COMMITTED (mínimo ejecutable / take-or-pay citado)
    if contraparte or continuidad:
        return 1, "UNKNOWN", hechos          # VALIDATED (relación real, sin mínimo)
    return 0, "UNKNOWN", []


def evaluar_ticker(session, ticker: str, *, en_nodo: bool = True,
                   multiplo_terminal: float | None = None, tasa_descuento: float = 0.14,
                   snapshot: dict | None = None) -> Evaluacion:
    """Evalúa un ticker punta a punta desde datos reales. Devuelve la Evaluacion (tier + pilares)."""
    det = extraer_deterministas(ticker)                    # EDGAR + market, sin LLM
    snap = snapshot if snapshot is not None else FS.snapshot_vigente(session, ticker)

    # Todo número que entra a un pilar pasa por canon() → unidad canónica + plausibilidad.
    margen = canon(det.get("margen_bruto"), tipo="margen", es_pct=True, campo="margen_bruto")
    crecimiento = canon(det.get("crecimiento_headline_yoy"), tipo="crecimiento", es_pct=True, campo="crecimiento_yoy")

    # Arquetipo (define tasa + caps) + hard_cap = cap_celda(arquetipo, fragility).
    arquetipo = _clasificar_arquetipo(det)
    tasa = politica.R_ARQUETIPO.get(arquetipo, tasa_descuento)
    # Concentración de clientes → fragility → cap (antes quedaba en el limbo: se extraía pero no
    # tocaba el sizing). >50% → Frag 2, 30-50% → Frag 1 (fragility.py). canon la mantiene 0-1.
    conc = canon(_snap(snap, "customer_concentration_pct"), tipo="fraccion", campo="concentracion_cliente")
    frag_h = HechosFragility(concentracion_cliente_pct=conc)
    frag_r = calcular_fragility_score(frag_h)
    frag = frag_r["score"]                                         # refina con más hechos estructurales
    hard_cap = cap_celda(arquetipo, frag)                          # CRR pendiente (tightener adicional)

    # Pilar 2 — Economía: números de XBRL + señales CUALITATIVAS del fact store (extractor).
    p_eco = pilar_economia(HechosQuality(
        margen_bruto=margen, crecimiento_organico_elegible=crecimiento,
        margen_en_expansion=bool(_snap(snap, "margen_en_expansion")),
        revenue_recurrente=bool(_snap(snap, "revenue_recurrente")),
        hechos_comerciales_independientes=int(_snap(snap, "hechos_comerciales") or 0),
        ventaja_estructural=bool(_snap(snap, "ventaja_estructural"))))

    # Pilar 1 — Demanda (del fact store)
    tier_dem, materialidad, hechos_dem = _demanda_de_snapshot(snap)
    p_dem = pilar_demanda(tier_dem, en_nodo=en_nodo, materialidad=materialidad, hechos=hechos_dem)

    # Pilar 3 — Ejecución (management por EVIDENCIA dura, doc 26):
    #   · dilución 3y real de XBRL + crecimiento POR ACCIÓN derivado.
    #   · insider_net_usd: Form 4 parseado real (compra − venta a MERCADO, código P/S) — plata propia.
    #   · sbc_pct_revenue: SBC_TTM / revenue_TTM de XBRL (dilución silenciosa).
    #   Guidance-vs-actuals sigue diferido (Fase 2: necesita transcripts/FMP).
    dilucion = canon(edgar.get_dilution_pct_3y(ticker), tipo="dilucion", es_pct=True, campo="dilucion_3y")
    crec_accion = None
    if crecimiento is not None and dilucion is not None:
        ann_dil = (1 + dilucion) ** (1 / 3) - 1                 # dilución anualizada
        crec_accion = canon((1 + crecimiento) / (1 + ann_dil) - 1, tipo="fraccion", campo="crec_por_accion")
    insider_net = edgar.get_insider_activity(ticker, dias=365).net_usd    # Form 4 real, ventana 12m
    sbc, rev = det.get("sbc_ttm"), det.get("revenue_ttm")
    sbc_pct = canon(sbc / rev, tipo="fraccion", campo="sbc_pct_revenue") if sbc and rev and rev > 0 else None
    p_eje = pilar_ejecucion(HechosEjecucion(
        dilucion_3y=dilucion, crecimiento_por_accion=crec_accion,
        insider_net_usd=insider_net, sbc_pct_revenue=sbc_pct,
        restatement_reciente=bool(_snap(snap, "restatement_reciente"))))

    # Valuación NO es pilar (doc 33/34 §1): es un GATE SEPARADO — el falsador CAGR cohort-free de
    # `bridge.py` sobre los números de `templates`/`pre_revenue`. Se enchufa en el paso 3 del refactor
    # (doc 34 §4), fuera de la composición de elegibilidad. Acá la elegibilidad son los 3 pilares.
    ev_res = evaluar(ticker, [p_dem, p_eco, p_eje])
    ev_res.arquetipo = arquetipo
    ev_res.hard_cap = hard_cap
    # ¿Los hechos de veto de supervivencia están EXTRAÍDOS? (guarda SYM 2026-08-31). Si falta alguno, el nombre
    # NO puede underwrite/probe — se abstiene hasta tener la evidencia (el veto solo vale si se lo buscó).
    ev_res.veto_facts_completos = all(_fact_extraido(snap, k) for k in FACT_KEYS_VETO_SUPERVIVENCIA)
    return ev_res
