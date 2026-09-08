"""Agente ANALISTA — núcleo del sistema BORJA.

Pipeline (doc 02 sec 4.2):
1. Revenue y crecimiento           → EDGAR
2. Guidance y backlog              → (Fase 2 con FMP transcripts)
3. Insider activity                → EDGAR Form 4
4. Analyst ratings                 → (Fase 2 con FMP)
5. Riesgos específicos             → News RSS con keywords
6. Balance y cash                  → EDGAR
7. Márgenes                        → EDGAR + percentile sectorial
8. Asimetría R/R                   → calculators (con bull/bear del LLM)
9. Liquidez                        → market_data
10. Contexto sectorial             → tabla sectores_mapas (Sprint 4)

El script Python prepara TODOS los números antes de llamar al LLM.
El LLM recibe datos ya procesados y produce evaluación cualitativa estructurada.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from backend.config import get_settings
from backend.database import session_scope
from backend.models import Ficha, Macro, Sector, SectorMapa
from backend.services import edgar, market_data, news
from backend.services.calculators import (
    calculate_deuda_revenue,
    calculate_implicit_growth,
    calculate_market_cap,
    calculate_runway,
    liquidez_suficiente,
)
from backend.services.llm import LLMCallResult, call_llm_json
from backend.utils import get_logger, utcnow

log = get_logger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"
PROMPT_VERSION = "v1"
PROMPT_FILE = PROMPTS_DIR / f"analista_{PROMPT_VERSION}.txt"

# Multiplicador sectorial default para implicit growth (conservador).
# Sprint 4: leer del mapa sectorial cuando exista.
SECTOR_MULTIPLE_REVENUE_DEFAULT = 5.0


class AnalistaError(Exception):
    pass


# ---------- Estructura del contexto ----------

@dataclass
class AnalisisContext:
    ticker: str
    nombre: str
    sector: str
    driver_macro: str | None
    tesis_previa: str | None
    estado_actual: str
    score_anterior: float | None

    # Paso 1 — Revenue
    revenue_qtrs_millones: list[float] = field(default_factory=list)
    revenue_ttm_millones: float | None = None
    organic_growth_yoy_pct: float | None = None

    # Paso 3 — Insider (Form 4 counts; detalle monto en Sprint 2)
    form4_count_90d: int = 0
    form4_urls_recientes: list[str] = field(default_factory=list)

    # Paso 5 — Riesgos (noticias)
    noticias_negativas: list[dict] = field(default_factory=list)
    noticias_contratos: list[dict] = field(default_factory=list)

    # Paso 6 — Balance
    cash_millones: float | None = None
    total_debt_millones: float | None = None
    fcf_ttm_millones: float | None = None
    runway_meses: float | None = None
    deuda_revenue_ratio: float | None = None
    burn_rate_mensual_millones: float | None = None

    # Paso 7 — Márgenes
    margen_bruto_ultimo_pct: float | None = None
    margen_bruto_tendencia_4q: list[float] = field(default_factory=list)
    margen_percentil_sectorial: int | None = None  # Sprint 2

    # Paso 8 — Precio y market cap
    precio_actual: float | None = None
    market_cap_millones: float | None = None
    shares_outstanding_millones: float | None = None
    implicit_growth_default_pct: float | None = None

    # Paso 9 — Liquidez
    volumen_diario_usd: float | None = None
    liquidez_suficiente: bool = False

    # Paso 10 — Contexto sectorial (Sprint 4)
    mapa_sectorial_activo: bool = False
    mapa_sectorial_version: str | None = None
    mapa_sectorial_texto: str | None = None

    # Meta
    momentum_sectorial: str | None = None
    macro_version: str | None = None
    macro_fase: str | None = None
    macro_postura: str | None = None

    # Diagnósticos — gaps de datos detectados
    gaps_detectados: list[str] = field(default_factory=list)


# ---------- Paso 1-10: recopilación de datos ----------

def preparar_contexto(ticker: str) -> AnalisisContext:
    """Ejecuta los 10 pasos. Retorna el contexto — no llama al LLM."""
    ticker = ticker.upper()

    with session_scope() as s:
        ficha = s.query(Ficha).filter_by(ticker=ticker).first()
        if ficha is None:
            raise AnalistaError(f"ticker {ticker} no está en fichas — usar intake rápido primero")
        sector_nombre = ficha.sector
        sector_row = s.query(Sector).filter_by(nombre=sector_nombre).first()
        momentum = sector_row.momentum if sector_row else None
        macro = s.query(Macro).filter_by(activa=True).first()
        macro_data = (macro.version, macro.fase_actual, macro.postura_capital) if macro else (None, None, None)
        mapa = s.query(SectorMapa).filter_by(sector=sector_nombre, estado="activo").first()
        mapa_version = mapa.fecha_generacion.isoformat() if mapa else None
        mapa_json = mapa.mapa_json if mapa else None

        ctx = AnalisisContext(
            ticker=ticker,
            nombre=ficha.nombre,
            sector=sector_nombre,
            driver_macro=ficha.driver_macro,
            tesis_previa=ficha.tesis_vigente,
            estado_actual=ficha.estado,
            score_anterior=ficha.score_vigente,
            momentum_sectorial=momentum,
            macro_version=macro_data[0],
            macro_fase=macro_data[1],
            macro_postura=macro_data[2],
        )

    # Paso 1+6+7 — financials (incluye balance, revenue, márgenes)
    fin = edgar.get_financials_quarterly(ticker, periodos=8)
    if fin.revenue_ttm is None:
        ctx.gaps_detectados.append("paso_1: sin revenue_ttm en EDGAR (posible pre-revenue o no reporta XBRL)")
    else:
        ctx.revenue_ttm_millones = round(fin.revenue_ttm / 1e6, 1)
    ctx.revenue_qtrs_millones = [round(v / 1e6, 1) for v in (fin.revenue_qtrs or [])]
    ctx.organic_growth_yoy_pct = fin.organic_growth_yoy
    ctx.cash_millones = round(fin.cash / 1e6, 1) if fin.cash is not None else None
    ctx.total_debt_millones = round(fin.total_debt / 1e6, 1) if fin.total_debt is not None else None
    ctx.fcf_ttm_millones = round(fin.fcf_ttm / 1e6, 1) if fin.fcf_ttm is not None else None
    ctx.burn_rate_mensual_millones = round(fin.burn_rate_monthly / 1e6, 2) if fin.burn_rate_monthly is not None else None
    ctx.runway_meses = calculate_runway(fin.cash, fin.burn_rate_monthly)
    ctx.deuda_revenue_ratio = calculate_deuda_revenue(fin.total_debt, fin.revenue_ttm)
    ctx.margen_bruto_ultimo_pct = fin.margen_bruto_ultimo
    ctx.margen_bruto_tendencia_4q = fin.margen_bruto_tendencia

    if fin.margen_bruto_ultimo is None:
        ctx.gaps_detectados.append("paso_7: sin margen bruto (empresa no tagea GrossProfit en XBRL)")

    ctx.shares_outstanding_millones = round(fin.shares_outstanding / 1e6, 2) if fin.shares_outstanding else None

    # Paso 8 + 9 — precio, market cap, liquidez
    snap = market_data.get_price_snapshot(ticker)
    if snap is None:
        ctx.gaps_detectados.append("paso_8-9: precio no disponible (Yahoo chart fallo)")
    else:
        ctx.precio_actual = snap.precio_actual
        ctx.volumen_diario_usd = snap.volumen_diario_promedio_30d
        ctx.liquidez_suficiente = liquidez_suficiente(snap.volumen_diario_promedio_30d)
        mc = calculate_market_cap(snap.precio_actual, fin.shares_outstanding)
        ctx.market_cap_millones = round(mc / 1e6, 1) if mc else None
        ctx.implicit_growth_default_pct = calculate_implicit_growth(
            precio_actual=snap.precio_actual,
            revenue_ttm=fin.revenue_ttm,
            shares_outstanding=fin.shares_outstanding,
            sector_multiple_revenue=SECTOR_MULTIPLE_REVENUE_DEFAULT,
            horizonte_anios=3,
        )

    # Paso 3 — Insider
    ins = edgar.get_insider_activity(ticker, dias=90)
    ctx.form4_count_90d = len(ins.transacciones)
    ctx.form4_urls_recientes = [t.get("url", "") for t in ins.transacciones[:5]]

    # Paso 5 — Riesgos (noticias materiales)
    material = news.get_material_news(ticker, nombre=ctx.nombre, dias=30)
    for n in material:
        item = {
            "titulo": n.titulo[:200],
            "fecha": n.publicado.date().isoformat(),
            "url": n.url,
            "keywords_match": n.keywords_match,
        }
        if n.categoria == "negativo":
            ctx.noticias_negativas.append(item)
        elif n.categoria == "contrato":
            ctx.noticias_contratos.append(item)

    # Paso 10 — Contexto sectorial
    if mapa_json:
        ctx.mapa_sectorial_activo = True
        ctx.mapa_sectorial_version = mapa_version
        ctx.mapa_sectorial_texto = _format_mapa_para_prompt(mapa_json)
    else:
        ctx.gaps_detectados.append(f"paso_10: sin mapa sectorial activo para {sector_nombre} (Sprint 4)")

    log.info("ANALISTA contexto preparado — ticker=%s gaps=%d", ticker, len(ctx.gaps_detectados))
    return ctx


def _format_mapa_para_prompt(mapa_json: dict) -> str:
    """Formatea el mapa sectorial como bloque de contexto según doc 02 sec 3.6."""
    lines = []
    lines.append(f"Sector: {mapa_json.get('sector', 'N/A')}")
    ind = mapa_json.get("industria_servida") or {}
    if ind:
        lines.append(f"Industria servida: {ind.get('tamano_estimado', 'N/A')} creciendo {ind.get('crecimiento_anual', 'N/A')}")
    cuellos = mapa_json.get("cuellos_de_botella") or []
    if cuellos:
        lines.append("Cuellos de botella activos:")
        for i, c in enumerate(cuellos, 1):
            lines.append(f"  {i}. {c.get('componente', '?')} — Criticidad: {c.get('nivel_critico', '?')}")
            lines.append(f"     Proveedores: {c.get('cantidad_proveedores', '?')}. Sustituibilidad: {c.get('sustituibilidad', '?')}. Lead time: {c.get('lead_time_estimado', '?')}")
            lines.append(f"     Justificación: {c.get('justificacion_criticidad', '')[:200]}")
    return "\n".join(lines)


# ---------- Formateo del user message ----------

def formatear_user_message(ctx: AnalisisContext) -> str:
    """Convierte el contexto en el prompt estructurado para el LLM."""
    d = asdict(ctx)
    # Truncar listas grandes
    noticias_neg = ctx.noticias_negativas[:10]
    noticias_con = ctx.noticias_contratos[:10]

    msg = f"""=== DATOS ESTRUCTURADOS PARA {ctx.ticker} ({ctx.nombre}) ===

Sector: {ctx.sector}
Driver macro: {ctx.driver_macro or 'no especificado'}
Estado actual en sistema: {ctx.estado_actual}
Score anterior: {ctx.score_anterior if ctx.score_anterior is not None else 'sin análisis previo'}
Tesis previa: {ctx.tesis_previa or '(sin tesis registrada)'}

=== CONTEXTO MACRO (informativo, no modifica criterios) ===
Versión: {ctx.macro_version}
Fase: {ctx.macro_fase}
Postura capital: {ctx.macro_postura}

=== MOMENTUM SECTORIAL ===
{ctx.sector}: {ctx.momentum_sectorial or 'sin momentum asignado — tratar como pre_rally conservador'}

=== CONTEXTO SECTORIAL ({'mapa activo' if ctx.mapa_sectorial_activo else 'SIN MAPA — Sprint 4'}) ===
{ctx.mapa_sectorial_texto or '(sin mapa sectorial activo — evaluar sin contexto estructural. Asignar criticidad usando conocimiento general del sector.)'}

Instrucciones mapa: considerar la criticidad en Criterio 4 (Moat) y 2 (Captura de valor). Si los datos financieros contradicen el mapa, prevalecen los datos. Citar qué parte del mapa usaste en contexto_sectorial_citado.

=== PASO 1 — REVENUE (EDGAR XBRL) ===
Revenue TTM: {_fmt_money(ctx.revenue_ttm_millones)}
Crecimiento YoY orgánico: {_fmt_pct(ctx.organic_growth_yoy_pct)}
Revenue últimos trimestres (millones USD, viejo → reciente): {ctx.revenue_qtrs_millones}

=== PASO 2 — GUIDANCE Y BACKLOG ===
(Fase 1 sin transcripts — evaluar desde noticias de contratos más abajo. Cuando haya FMP, incluirá guidance explícito y backlog cuantificado.)

=== PASO 3 — INSIDER ACTIVITY (SEC Form 4, últimos 90 días) ===
Cantidad de Form 4 presentados: {ctx.form4_count_90d}
URLs recientes (hasta 5): {ctx.form4_urls_recientes}
(Fase 1 no parsea montos — en Sprint 2 se agregarán compras netas USD y ventas CEO/CFO desagregadas. Interpretar el volumen como señal direccional.)

=== PASO 4 — ANALYST RATINGS ===
(Fase 1 sin datos — en Fase 2 con FMP: PT consenso, upgrades/downgrades recientes.)

=== PASO 5 — RIESGOS Y NOTICIAS MATERIALES (últimos 30 días) ===
Noticias negativas ({len(ctx.noticias_negativas)}):
{_fmt_noticias(noticias_neg)}

Noticias de contratos/customers ({len(ctx.noticias_contratos)}):
{_fmt_noticias(noticias_con)}

=== PASO 6 — BALANCE Y CASH (EDGAR) ===
Cash: {_fmt_money(ctx.cash_millones)}
Deuda total: {_fmt_money(ctx.total_debt_millones)}
FCF TTM: {_fmt_money(ctx.fcf_ttm_millones)}
Burn rate mensual (si FCF<0): {_fmt_money(ctx.burn_rate_mensual_millones)}
Runway (meses): {ctx.runway_meses if ctx.runway_meses is not None else '(FCF positivo o burn desconocido)'}
Ratio deuda/revenue: {ctx.deuda_revenue_ratio if ctx.deuda_revenue_ratio is not None else 'N/D'}x

=== PASO 7 — MÁRGENES (EDGAR) ===
Margen bruto último trimestre: {_fmt_pct(ctx.margen_bruto_ultimo_pct)}
Tendencia últimos 4Q: {ctx.margen_bruto_tendencia_4q}
Percentil sectorial: {ctx.margen_percentil_sectorial if ctx.margen_percentil_sectorial is not None else '(Sprint 2: cálculo con universo propio)'}

=== PASO 8 — PRECIO Y ASIMETRÍA ===
Precio actual: ${ctx.precio_actual}
Market cap: {_fmt_money(ctx.market_cap_millones)}
Shares outstanding: {_fmt_money(ctx.shares_outstanding_millones)} (millones de acciones)

Crecimiento implícito en precio (asumiendo múltiplo {SECTOR_MULTIPLE_REVENUE_DEFAULT}x revenue a 3 años): {_fmt_pct(ctx.implicit_growth_default_pct)}

Tu tarea en este paso: proponer bull_case_precio y bear_case_precio con lógica explícita. El sistema validará la asimetría (upside/downside).

=== PASO 9 — LIQUIDEZ ===
Volumen diario promedio 30d: {_fmt_money_exact(ctx.volumen_diario_usd)}
Liquidez suficiente (>$1M): {ctx.liquidez_suficiente}

=== DIAGNÓSTICOS DE GAPS ===
{_fmt_gaps(ctx.gaps_detectados)}

=== INSTRUCCIONES FINALES ===
Evaluá los 10 criterios con score 1-10 cada uno.
Producí un OBJETO JSON siguiendo EXACTAMENTE la estructura del system prompt.
No agregues texto antes ni después del JSON.
Si un criterio tiene gaps de datos, score ≤5 y documentá "DATOS INSUFICIENTES:" en evidencia_en_contra.
"""
    return msg


def _fmt_money(val: float | None) -> str:
    if val is None:
        return "N/D"
    if val >= 1000:
        return f"${val/1000:.2f}B"
    return f"${val:.1f}M"


def _fmt_money_exact(val: float | None) -> str:
    if val is None:
        return "N/D"
    if val >= 1e9:
        return f"${val/1e9:.2f}B"
    if val >= 1e6:
        return f"${val/1e6:.1f}M"
    return f"${val:,.0f}"


def _fmt_pct(val: float | None) -> str:
    return f"{val}%" if val is not None else "N/D"


def _fmt_noticias(items: list[dict]) -> str:
    if not items:
        return "  (ninguna en la ventana)"
    lines = []
    for n in items:
        kws = ",".join(n.get("keywords_match", [])[:3])
        lines.append(f"  [{n['fecha']}] kw={kws}: {n['titulo'][:120]}")
    return "\n".join(lines)


def _fmt_gaps(gaps: list[str]) -> str:
    if not gaps:
        return "(sin gaps detectados)"
    return "\n".join(f"  - {g}" for g in gaps)


# ---------- Carga del prompt ----------

def load_system_prompt() -> str:
    if not PROMPT_FILE.exists():
        raise AnalistaError(f"Prompt file no encontrado: {PROMPT_FILE}")
    return PROMPT_FILE.read_text(encoding="utf-8")


# ---------- Pipeline completo ----------

def ejecutar_analisis(
    ticker: str,
    *,
    dry_run: bool = False,
    task_updater=None,
) -> dict:
    """Pipeline end-to-end del Analista.

    Args:
        ticker: ticker a analizar. Debe existir en fichas.
        dry_run: si True, no llama a Anthropic — útil para tests.
        task_updater: callable(estado: str, progreso: str) para actualizar tabla tasks.

    Returns:
        dict con 'output' (JSON parseado del LLM), 'context' (dict), 'llm_metadata'.
    """
    if task_updater:
        task_updater("en_progreso", "paso 1/10 — armando contexto")

    ctx = preparar_contexto(ticker)

    if task_updater:
        task_updater("en_progreso", f"contexto listo — {len(ctx.gaps_detectados)} gaps")

    system_prompt = load_system_prompt()
    user_message = formatear_user_message(ctx)

    if task_updater:
        task_updater("en_progreso", "llamando LLM")

    llm_result = call_llm_json(
        system_prompt=system_prompt,
        user_message=user_message,
        dry_run=dry_run,
        extra_metadata={"ticker": ticker, "prompt_version": PROMPT_VERSION, "agent": "analista"},
    )

    if dry_run:
        # En dry_run devolvemos contexto + prompt para inspección
        return {
            "output": None,
            "context": _ctx_to_dict(ctx),
            "user_message": user_message,
            "llm_metadata": {
                "dry_run": True,
                "system_prompt_chars": len(system_prompt),
                "user_message_chars": len(user_message),
            },
        }

    return {
        "output": llm_result.parsed_json,
        "context": _ctx_to_dict(ctx),
        "user_message": user_message,
        "llm_metadata": {
            "model": llm_result.model,
            "tokens_input": llm_result.tokens_input,
            "tokens_output": llm_result.tokens_output,
            "tokens_cache_read": llm_result.tokens_cache_read,
            "tokens_cache_write": llm_result.tokens_cache_write,
            "cost_usd": llm_result.cost_usd,
            "latency_s": llm_result.latency_s,
        },
    }


def _ctx_to_dict(ctx: AnalisisContext) -> dict:
    d = asdict(ctx)
    # Truncar campos que no hacen falta persistir enteros
    d.pop("mapa_sectorial_texto", None)
    return d
