"""Adapter de datos: ticker real → HechosUniverso + HechosFiltro0.

Reusa los servicios existentes (market_data + EDGAR + calculators). NO hace juicios:
solo trae los hechos mecánicos. Los campos cualitativos (contrato firme, tracción,
vínculo con nodo) los provee quien llama — el adapter no los inventa.

Unidades: EDGAR devuelve crecimiento/margen en PORCENTAJE (20, 30); el Filtro 0 usa
FRACCIÓN (0.20, 0.30) → se convierte. Jurisdicción: hoy el extractor solo es EDGAR
(US), así que un CIK ⇒ US-listed; sin CIK no hay financials.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from backend.ingreso.filtro0 import HechosFiltro0
from backend.ingreso.universo import HechosUniverso
from backend.nucleo.constantes import UMBRAL_PREREV
from backend.services import edgar, market_data
from backend.services.calculators import (
    calculate_deuda_revenue,
    calculate_market_cap,
    calculate_runway,
)
from backend.utils import get_logger

log = get_logger(__name__)


@dataclass
class HechosEmpresa:
    universo: HechosUniverso
    filtro0: HechosFiltro0
    precio_actual: float | None = None
    revenue_ttm: float | None = None
    market_cap: float | None = None


def _pct_a_frac(v: float | None) -> float | None:
    return v / 100.0 if v is not None else None


def construir_hechos(ticker: str, *, tiene_nodo: bool, es_adr: bool = False,
                     tiene_contrato_vinculante_material: bool = False,
                     tiene_traccion_comercial: bool = False,
                     financiacion_comprometida: bool = False) -> HechosEmpresa | None:
    """Arma hechos de universo + Filtro 0 desde datos reales. None si no hay precio
    (ticker inválido / Yahoo caído). Los campos cualitativos los pasa el caller."""
    snap = market_data.get_price_snapshot(ticker)
    if snap is None or snap.precio_actual is None:
        log.warning("adapter — sin precio para %s", ticker)
        return None
    fin = edgar.get_financials_quarterly(ticker, periodos=8)

    market_cap = (calculate_market_cap(snap.precio_actual, fin.shares_outstanding)
                  if fin.shares_outstanding else None)

    universo = HechosUniverso(
        jurisdiccion="US" if fin.cik else None,   # CIK EDGAR ⇒ US-listed
        es_adr=es_adr,
        market_cap=market_cap,
        adv_usd=snap.volumen_diario_promedio_30d,
        tiene_nodo=tiene_nodo,
    )

    es_prerev = fin.revenue_ttm is not None and fin.revenue_ttm < UMBRAL_PREREV
    quema_caja = fin.burn_rate_monthly is not None and fin.burn_rate_monthly > 0
    filtro0 = HechosFiltro0(
        es_prerevenue=es_prerev,
        tiene_contrato_vinculante_material=tiene_contrato_vinculante_material,
        tiene_traccion_comercial=tiene_traccion_comercial,
        crecimiento_yoy=_pct_a_frac(fin.organic_growth_yoy),
        margen_bruto=_pct_a_frac(fin.margen_bruto_ultimo),
        deuda_sobre_revenue=calculate_deuda_revenue(fin.total_debt, fin.revenue_ttm),
        quema_caja=quema_caja,
        runway_meses=calculate_runway(fin.cash, fin.burn_rate_monthly),  # None si no hay burn
        financiacion_comprometida=financiacion_comprometida,
    )
    return HechosEmpresa(universo=universo, filtro0=filtro0, precio_actual=snap.precio_actual,
                         revenue_ttm=fin.revenue_ttm, market_cap=market_cap)


def ingresar_ticker(session: Session, *, ticker: str, nodo_id: int | None, fecha: date,
                    es_adr: bool = False, tiene_contrato_vinculante_material: bool = False,
                    tiene_traccion_comercial: bool = False, fuente_ingreso: str = "manual",
                    nombre: str | None = None, sector: str | None = None) -> dict:
    """Entry-point de datos REALES: trae hechos y corre la Etapa 3 sobre el ledger.
    Devuelve {resultado, ...}. 'sin_datos' si no hay precio."""
    from backend.ingreso.flujo import ingresar

    h = construir_hechos(ticker, tiene_nodo=nodo_id is not None, es_adr=es_adr,
                         tiene_contrato_vinculante_material=tiene_contrato_vinculante_material,
                         tiene_traccion_comercial=tiene_traccion_comercial)
    if h is None:
        return {"resultado": "sin_datos", "ticker": ticker.upper()}
    return ingresar(session, ticker=ticker, universo=h.universo, filtro0=h.filtro0,
                    fecha=fecha, nodo_id=nodo_id, fuente_ingreso=fuente_ingreso,
                    nombre=nombre, sector=sector)
