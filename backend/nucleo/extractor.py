"""Extractor de hechos — el LLM como traedor de hechos, no decisor (§375 paso 2/5).

Es el cambio conceptual más grande de la migración: el LLM deja de puntuar y
decidir; trae HECHOS FECHADOS CON FUENTE que pueblan los dataclasses del núcleo,
y la tabla determinista decide.

Dos capas:
  1. Determinista (EDGAR + market_data): caja, burn, revenue headline, crecimiento,
     dilución, precio. Fuente A por construcción; no pasa por el LLM.
  2. LLM (call_llm_json + prompt extractor_hechos_v1): las ETIQUETAS y hechos
     cualitativos que EDGAR no da — elegibilidad ASC 606, clientes, tipo de
     demanda P1, triggers con forma, fragilidad estructural, calidad de negocio,
     bull/bear. El LLM nunca asigna arquetipo/score/decisión.

`construir_entrada_empresa()` compone ambas en un EntradaEmpresa listo para
flujo.evaluar_empresa(). Acepta `hechos_llm` inyectado (para test/operador sin
gasto de API) o llama al LLM. Nunca decide: solo arma el input.
"""
from __future__ import annotations

from pathlib import Path

from backend.nucleo.arquetipo import HechosArquetipo
from backend.nucleo.fragility import HechosFragility
from backend.nucleo.flujo import EntradaEmpresa
from backend.nucleo.gate import HechosGate, Trigger
from backend.nucleo.quality import HechosQuality
from backend.services import edgar, market_data
from backend.services.llm import call_llm_json
from backend.utils import get_logger

log = get_logger(__name__)

PROMPT_FILE = Path(__file__).resolve().parent.parent.parent / "prompts" / "extractor_hechos_v2.txt"
PROMPT_VERSION = "extractor_hechos_v2"
HECHOS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "nucleo_hechos"


def load_system_prompt() -> str:
    return PROMPT_FILE.read_text(encoding="utf-8")


# ----------------------------- Capa determinista -----------------------------

def extraer_deterministas(ticker: str) -> dict:
    """Datos duros de EDGAR + mercado (fuente A). No pasan por el LLM."""
    fin = edgar.get_financials_quarterly(ticker, periodos=8)
    snap = market_data.get_price_snapshot(ticker)
    return {
        "ticker": ticker.upper(),
        "revenue_ttm": fin.revenue_ttm,
        "crecimiento_headline_yoy": fin.organic_growth_yoy,
        "fcf_ttm": fin.fcf_ttm,
        "caja": fin.cash,
        "burn_mensual": fin.burn_rate_monthly,
        "total_debt": fin.total_debt,
        "margen_bruto": fin.margen_bruto_ultimo,
        "rpo": fin.rpo,                       # backlog contratado (XBRL) → escenario operable del compiler
        "rpo_as_of": fin.rpo_as_of,
        "sbc_ttm": fin.sbc_ttm,               # stock-based comp TTM → SBC/revenue (dilución silenciosa, Pilar 3)
        "precio": snap.precio_actual if snap else None,
    }


def _fmt(v, money=False):
    if v is None:
        return "N/D"
    if money:
        return f"${v/1e6:,.1f}M"
    return str(v)


def formatear_contexto(det: dict) -> str:
    """Arma el bloque de datos EDGAR/mercado que se le pasa al LLM como contexto."""
    return (
        f"TICKER: {det['ticker']}\n"
        f"=== DATOS EDGAR/MERCADO (fuente A, ya calculados — NO recalcular) ===\n"
        f"Revenue TTM (headline): {_fmt(det['revenue_ttm'], money=True)}\n"
        f"Crecimiento YoY (headline): {_fmt(det['crecimiento_headline_yoy'])}\n"
        f"FCF TTM: {_fmt(det['fcf_ttm'], money=True)}\n"
        f"Caja último filing: {_fmt(det['caja'], money=True)}\n"
        f"Burn mensual (prom 2T): {_fmt(det['burn_mensual'], money=True)}\n"
        f"Deuda total: {_fmt(det['total_debt'], money=True)}\n"
        f"Margen bruto último: {_fmt(det['margen_bruto'])}\n"
        f"Precio actual: {_fmt(det['precio'])}\n\n"
        f"Traé los hechos etiquetados que faltan (elegibilidad ASC 606, clientes, "
        f"P1, triggers, fragilidad, calidad, bull/bear) en el JSON pedido."
    )


# ----------------------------- Capa LLM -----------------------------

def extraer_hechos_llm(ticker: str, det: dict, *, model: str | None = None,
                       dry_run: bool = False) -> dict | None:
    """Llama al LLM extractor. Devuelve el JSON de hechos (o None si falla parse)."""
    res = call_llm_json(
        system_prompt=load_system_prompt(),
        user_message=formatear_contexto(det),
        model=model,
        max_tokens=4096,
        dry_run=dry_run,
        extra_metadata={"ticker": ticker, "prompt_version": PROMPT_VERSION, "agent": "extractor_hechos"},
    )
    return res.parsed_json if isinstance(res.parsed_json, dict) else None


# ----------------------------- Mapeo JSON → dataclasses -----------------------------

def _frac(v):
    """Normaliza porcentajes a fracción [0,1]. El LLM suele devolver % como entero
    (13, 28.86, 80) pero el núcleo espera fracción (0.13, 0.2886, 0.80). Heurística
    robusta en ambos sentidos: si |v| > 1.5 se asume % entero y se divide por 100;
    si ya es fracción (0.40) queda igual. Cubre crecimientos >100% (116.52 → 1.165)."""
    if v is None:
        return None
    try:
        return v / 100.0 if abs(v) > 1.5 else v
    except TypeError:
        return v


def _g(d: dict | None, *keys, default=None):
    """getattr anidado seguro sobre dicts."""
    cur = d or {}
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return default if cur is None else cur


def mapear_a_entrada(ticker: str, det: dict, hechos: dict) -> EntradaEmpresa:
    """Compone los hechos deterministas + LLM en un EntradaEmpresa.

    Los números financieros (caja, burn) salen de EDGAR (fuente A); el LLM solo
    aporta compromisos firmados / líneas / meses-hasta-hito y las etiquetas.
    """
    rev = hechos.get("revenue") or {}
    gate = hechos.get("gate") or {}
    fin = hechos.get("financiacion") or {}
    frag = hechos.get("fragility") or {}
    qual = hechos.get("quality") or {}
    esc = hechos.get("escenarios") or {}

    h_arq = HechosArquetipo(
        revenue_elegible=rev.get("revenue_elegible_usd"),
        clientes_pct=[_frac(c) for c in (rev.get("clientes_pct") or [])],
        crecimiento_elegible_yoy=_frac(rev.get("crecimiento_elegible_yoy")),
        fcf_ttm=rev.get("fcf_ttm_usd") if rev.get("fcf_ttm_usd") is not None else det.get("fcf_ttm"),
        es_binary=bool(_g(hechos, "binary", "es_binary", default=False)),
        contrato_en_firme_dominante=bool(_g(hechos, "contrato_dominante", "en_firme", default=False)),
        recurrencia_etiquetada_dominante=bool(_g(hechos, "contrato_dominante", "recurrencia_etiquetada", default=False)),
    )

    triggers = [
        Trigger(
            hecho=t.get("hecho", ""), umbral=t.get("umbral"), fecha=t.get("fecha"),
            fuente=t.get("fuente"), es_estructura_capital=bool(t.get("es_estructura_capital")),
            atado_a_hecho_de_entrada=bool(t.get("atado_a_hecho_de_entrada")),
            es_trigger_ejecucion=bool(t.get("es_trigger_ejecucion")),
        )
        for t in (gate.get("triggers") or [])
    ]
    h_gate = HechosGate(
        arquetipo="",  # lo fija flujo.evaluar_empresa tras clasificar.
        triggers=triggers,
        tesis_es_ejecucion_contrato=bool(gate.get("tesis_es_ejecucion_contrato")),
        madura_hecho_vigente=bool(gate.get("madura_hecho_vigente")),
        growth_desglose_organico_disponible=bool(_g(gate, "growth", "desglose_organico_disponible", default=False)),
        growth_organico_pct=_frac(_g(gate, "growth", "organico_pct")),
        growth_hecho_continuidad=bool(_g(gate, "growth", "hecho_continuidad", default=False)),
        traccion_hecho_comercial_4t=bool(_g(gate, "traccion", "hecho_comercial_4t", default=False)),
        traccion_catalizador_meses=_g(gate, "traccion", "catalizador_meses"),
        traccion_catalizador_tiene_metrica=bool(_g(gate, "traccion", "catalizador_tiene_metrica", default=False)),
        requiere_financiacion_externa=bool(_g(gate, "traccion", "requiere_financiacion_externa", default=False)),
        prerev_p1_tipo=_g(gate, "prerev", "p1_tipo"),
        prerev_p1_fuente=_g(gate, "prerev", "p1_fuente"),
        prerev_catalizador_meses=_g(gate, "prerev", "catalizador_meses"),
        prerev_catalizador_tiene_metrica=bool(_g(gate, "prerev", "catalizador_tiene_metrica", default=False)),
        prerev_fecha_congelada=bool(_g(gate, "prerev", "fecha_congelada", default=False)),
        prerev_puerta_continuidad=bool(_g(gate, "prerev", "puerta_continuidad", default=False)),
        binary_b1_fuente_valida=bool(_g(gate, "binary_items", "b1_fuente_valida", default=False)),
        binary_evento_fecha=bool(_g(gate, "binary_items", "evento_fecha", default=False)),
        binary_metrica_binaria=bool(_g(gate, "binary_items", "metrica_binaria", default=False)),
        # Financiación: números duros de EDGAR + lo firmado que aporta el LLM.
        caja_ultimo_filing=det.get("caja"),
        compromisos_firmados_no_dispuestos=fin.get("compromisos_firmados_no_dispuestos_usd") or 0.0,
        lineas_credito_disponibles_hoy=fin.get("lineas_credito_hoy_usd") or 0.0,
        burn_mensual_prom_2t=det.get("burn_mensual"),
        meses_hasta_hito_financiado=fin.get("meses_hasta_hito_financiado"),
    )

    h_frag = HechosFragility(
        financiacion_completa_cerrada=bool(frag.get("financiacion_completa_cerrada")),
        redundancia_comercial_real=bool(frag.get("redundancia_comercial_real")),
        concentracion_cliente_pct=_frac(frag.get("concentracion_cliente_pct")),
        dependencia_con_respaldo=bool(frag.get("dependencia_con_respaldo")),
        bull_depende_evento_discreto=bool(frag.get("bull_depende_evento_discreto")),
        financiacion_externa_no_firmada=bool(frag.get("financiacion_externa_no_firmada")),
        punto_unico_de_falla=bool(frag.get("punto_unico_de_falla")),
        perfora_negocio_base=bool(frag.get("perfora_negocio_base")),
    )

    h_qual = HechosQuality(
        margen_bruto=_frac(qual.get("margen_bruto") if qual.get("margen_bruto") is not None else det.get("margen_bruto")),
        margen_en_expansion=bool(qual.get("margen_en_expansion")),
        crecimiento_organico_elegible=_frac(qual.get("crecimiento_organico_elegible")),
        revenue_recurrente=bool(qual.get("revenue_recurrente")),
        hechos_comerciales_independientes=int(qual.get("hechos_comerciales_independientes") or 0),
        ventaja_estructural=bool(qual.get("ventaja_estructural")),
    )

    return EntradaEmpresa(
        ticker=ticker.upper(),
        hechos_arquetipo=h_arq,
        hechos_gate=h_gate,
        hechos_fragility=h_frag,
        hechos_quality=h_qual,
        precio=det.get("precio") or 0.0,
        bull=esc.get("bull") or 0.0,
        bear=esc.get("bear") or 0.0,
        cap_crr=None,        # cap_CRR Medio/Alto sin calibrar (decisión operador); CRR-crítico abajo.
        crr_critico=False,   # lo setea capital_raise_risk (sub-gate financiero) en el wiring.
    )


def construir_entrada_empresa(ticker: str, *, hechos_llm: dict | None = None,
                              model: str | None = None, dry_run: bool = False) -> EntradaEmpresa | None:
    """Pipeline completo: EDGAR/market → (LLM o hechos inyectados) → EntradaEmpresa.

    hechos_llm: si se pasa, NO se llama al LLM (operador/test sin gasto de API).
    Devuelve None si no se pudieron obtener los hechos.
    """
    det = extraer_deterministas(ticker)
    hechos = hechos_llm
    if hechos is None:
        hechos = extraer_hechos_llm(ticker, det, model=model, dry_run=dry_run)
    if hechos is None:
        log.warning("extractor — %s: sin hechos (LLM falló o dry_run)", ticker)
        return None
    return mapear_a_entrada(ticker, det, hechos)


def reextraer_a_cache(tickers: list[str], *, model: str | None = None) -> dict:
    """Re-extrae hechos LLM de cada ticker y los cachea en HECHOS_DIR (1 llamada/ticker).
    Usado por el CLI y por el job semanal del scheduler. Devuelve {ok, fallo}."""
    import json as _json
    HECHOS_DIR.mkdir(parents=True, exist_ok=True)
    ok, fallo = [], []
    for t in tickers:
        try:
            det = extraer_deterministas(t)
            hechos = extraer_hechos_llm(t, det, model=model)
            if hechos:
                (HECHOS_DIR / f"{t.upper()}.json").write_text(
                    _json.dumps(hechos, indent=2, ensure_ascii=False), encoding="utf-8")
                ok.append(t)
            else:
                fallo.append(t)
        except Exception as e:  # noqa: BLE001
            log.warning("reextraer — %s falló: %s", t, e)
            fallo.append(t)
    log.info("reextraer — %d ok, %d fallaron", len(ok), len(fallo))
    return {"ok": ok, "fallo": fallo}
