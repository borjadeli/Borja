"""Agente DESCUBRIMIENTO — screener cuantitativo + RSS (doc 03 sec 3).

Sin LLM. Solo reglas deterministas.

Responsabilidad:
1. Correr screener (5 filtros) sobre una lista de tickers editable.
2. Para tickers que pasan TODOS los filtros Y no están ya en `fichas` → crear Candidata.

Filtros (doc 03 sec 3.1):
- Market cap $50M - $2B
- Revenue YoY > 20%
- Margen bruto > 30%
- Deuda/revenue < 2x
- Volumen diario promedio > $1M

Fuentes de datos:
- market_data (precio, volumen, cálculo de market cap con shares de EDGAR)
- edgar (revenue TTM, YoY, margen bruto, deuda total)

RSS de 8-K con keywords (doc 03 sec 3.1) — opcional, agregado si hay tiempo.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

import yaml

from backend.database import session_scope
from backend.models import EstadoFicha, Ficha
from backend.services import edgar, market_data
from backend.services.calculators import calculate_deuda_revenue, calculate_market_cap
from backend.utils import get_logger, utcnow

log = get_logger(__name__)

WATCHLIST_FILE = Path(__file__).resolve().parent.parent / "seed" / "screener_watchlist.yaml"

# Umbrales del screener (doc 03 sec 3.1)
MIN_MARKET_CAP = 50_000_000
MAX_MARKET_CAP = 2_000_000_000
MIN_REV_YOY_PCT = 20.0
MIN_MARGEN_BRUTO_PCT = 30.0
MAX_DEUDA_REVENUE = 2.0
MIN_VOLUMEN_USD = 1_000_000


@dataclass
class ScreenerResult:
    ticker: str
    pasa_todos: bool = False
    market_cap: float | None = None
    revenue_ttm: float | None = None
    revenue_yoy_pct: float | None = None
    margen_bruto_pct: float | None = None
    deuda_revenue: float | None = None
    volumen_diario_usd: float | None = None
    precio_actual: float | None = None
    ya_en_fichas: bool = False
    filtros_fallados: list[str] = None
    error: str | None = None

    def __post_init__(self):
        if self.filtros_fallados is None:
            self.filtros_fallados = []


# ---------- Screener ----------

def _load_watchlist() -> list[str]:
    if not WATCHLIST_FILE.exists():
        log.warning("watchlist no existe: %s", WATCHLIST_FILE)
        return []
    data = yaml.safe_load(WATCHLIST_FILE.read_text(encoding="utf-8"))
    return [str(t).upper().strip() for t in (data or []) if str(t).strip()]


def _evaluar_ticker(ticker: str) -> ScreenerResult:
    r = ScreenerResult(ticker=ticker.upper())
    try:
        with session_scope() as s:
            r.ya_en_fichas = s.query(Ficha).filter_by(ticker=r.ticker).first() is not None

        snap = market_data.get_price_snapshot(r.ticker)
        if snap is None or snap.precio_actual is None:
            r.error = "sin precio (Yahoo chart falló o ticker inválido)"
            r.filtros_fallados.append("precio")
            return r
        r.precio_actual = snap.precio_actual
        r.volumen_diario_usd = snap.volumen_diario_promedio_30d

        fin = edgar.get_financials_quarterly(r.ticker, periodos=8)
        if not fin.cik:
            r.error = "ticker sin CIK en EDGAR"
            r.filtros_fallados.append("edgar")
            return r
        r.revenue_ttm = fin.revenue_ttm
        r.revenue_yoy_pct = fin.organic_growth_yoy
        r.margen_bruto_pct = fin.margen_bruto_ultimo
        r.deuda_revenue = calculate_deuda_revenue(fin.total_debt, fin.revenue_ttm)
        if fin.shares_outstanding and snap.precio_actual:
            r.market_cap = calculate_market_cap(snap.precio_actual, fin.shares_outstanding)

        # Aplicar filtros
        fallos = []
        if r.market_cap is None:
            fallos.append("market_cap: no calculable (faltan shares)")
        elif not (MIN_MARKET_CAP <= r.market_cap <= MAX_MARKET_CAP):
            fallos.append(f"market_cap ${r.market_cap/1e6:.0f}M fuera de rango $50M-$2B")
        if r.revenue_yoy_pct is None:
            fallos.append("revenue_yoy: desconocido")
        elif r.revenue_yoy_pct < MIN_REV_YOY_PCT:
            fallos.append(f"revenue_yoy {r.revenue_yoy_pct}% < {MIN_REV_YOY_PCT}%")
        if r.margen_bruto_pct is None:
            fallos.append("margen_bruto: desconocido")
        elif r.margen_bruto_pct < MIN_MARGEN_BRUTO_PCT:
            fallos.append(f"margen_bruto {r.margen_bruto_pct}% < {MIN_MARGEN_BRUTO_PCT}%")
        if r.deuda_revenue is None:
            # Si no hay deuda, acepta (algunas empresas sin deuda)
            if fin.total_debt is None:
                pass  # ok
            else:
                fallos.append("deuda_revenue: desconocido")
        elif r.deuda_revenue > MAX_DEUDA_REVENUE:
            fallos.append(f"deuda/revenue {r.deuda_revenue}x > {MAX_DEUDA_REVENUE}x")
        if r.volumen_diario_usd is None:
            fallos.append("volumen: desconocido")
        elif r.volumen_diario_usd < MIN_VOLUMEN_USD:
            fallos.append(f"volumen ${r.volumen_diario_usd/1e6:.2f}M < $1M/día")

        r.filtros_fallados = fallos
        r.pasa_todos = len(fallos) == 0

    except Exception as e:  # noqa: BLE001
        r.error = f"{type(e).__name__}: {e}"
        r.filtros_fallados.append("excepcion")
        log.warning("_evaluar_ticker(%s) fallo: %s", ticker, e)

    return r


def correr_screener(tickers: Iterable[str] | None = None) -> dict:
    """Corre el screener sobre una lista de tickers. Default: watchlist YAML."""
    if tickers is None:
        tickers = _load_watchlist()
    tickers = [t.upper().strip() for t in tickers if t and t.strip()]

    resultados: list[ScreenerResult] = []
    for t in tickers:
        resultados.append(_evaluar_ticker(t))

    pasa = [r for r in resultados if r.pasa_todos]
    nuevos = [r for r in pasa if not r.ya_en_fichas]

    return {
        "total_evaluados": len(resultados),
        "pasan_screener": len(pasa),
        "nuevos_candidatos": len(nuevos),
        "tickers_pasa": [r.ticker for r in pasa],
        "nuevos_tickers": [r.ticker for r in nuevos],
        "resultados": [asdict(r) for r in resultados],
        "timestamp": utcnow().isoformat(),
    }


def crear_candidatas(tickers: list[str], sector_default: str = "AI infra",
                    driver_macro_default: str | None = None,
                    origen: str = "Screener") -> dict:
    """Crea fichas nuevas en estado Candidata para los tickers dados.

    NOTA: sector y driver_macro son placeholders — el humano los revisa tras crear.
    En Fase 2 con FMP/Polygon podríamos inferir sector automáticamente.
    """
    creados: list[str] = []
    ya_existentes: list[str] = []
    errores: list[dict] = []

    with session_scope() as s:
        for tk in tickers:
            tk_up = tk.upper().strip()
            if s.query(Ficha).filter_by(ticker=tk_up).first() is not None:
                ya_existentes.append(tk_up)
                continue
            try:
                # Fetch nombre desde EDGAR si se puede
                cik = edgar.get_cik(tk_up)
                nombre = tk_up
                if cik:
                    sub_data = edgar._get_submissions(cik) or {}
                    nombre = sub_data.get("name", tk_up)

                s.add(Ficha(
                    ticker=tk_up,
                    nombre=nombre,
                    sector=sector_default,
                    driver_macro=driver_macro_default or f"candidato via {origen}",
                    origen=origen,
                    estado=EstadoFicha.CANDIDATA.value,
                    version_tesis_macro="v1.0",
                    cambios_score=[],
                    cambios_estado=[{
                        "timestamp": utcnow().isoformat(),
                        "estado_anterior": None,
                        "estado_nuevo": EstadoFicha.CANDIDATA.value,
                        "motivo": f"creado por {origen}",
                    }],
                ))
                creados.append(tk_up)
            except Exception as e:  # noqa: BLE001
                errores.append({"ticker": tk_up, "error": f"{type(e).__name__}: {e}"})

    log.info("crear_candidatas — creados=%d ya_existentes=%d errores=%d", len(creados), len(ya_existentes), len(errores))
    return {
        "creados": creados,
        "ya_existentes": ya_existentes,
        "errores": errores,
        "origen": origen,
    }
