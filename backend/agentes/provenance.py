"""Trazabilidad de datos — el contrato del data pack (Capa A, v2 doc 51 §3A).

Adaptado de `src/qa/provenance.py` del Sistema-Quant. Todo número relevante es un `DataPoint` con
fuente, fecha, unidad y una *clase epistemológica* explícita (`DataKind`):

- ORIGINAL: dato tal como lo publica la fuente (10-K, press release, precio de mercado).
- DERIVED: cálculo determinista sobre originales (owner-FCF, dilución, g_D...). Guarda sus insumos.
- ESTIMATE: supuesto o proyección. Guarda quién lo estimó.
- INTERPRETATION: juicio de un agente LLM o del analista. NUNCA se mezcla con los anteriores.

`known_at` = fecha en que el dato estuvo disponible públicamente (p.ej. fecha de filing). Es la clave
anti look-ahead: una decisión en t solo puede usar datapoints con known_at <= t.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class DataKind(str, Enum):
    ORIGINAL = "original"
    DERIVED = "derived"
    ESTIMATE = "estimate"
    INTERPRETATION = "interpretation"


class Verification(str, Enum):
    """Grado de verificación de un hecho cualitativo."""
    CONFIRMED_FILING = "confirmed_by_filing"   # documento regulatorio (hecho verificado)
    COMPANY_STATEMENT = "company_statement"     # press release / earnings call (NO es hecho verificado)
    MEDIA_REPORT = "media_report"               # prensa / research de terceros
    SEARCH_SUMMARY = "search_summary"           # resumen de buscador, no el documento primario
    ANALYST_PRIOR = "analyst_prior"             # conocimiento previo NO verificado acá
    HYPOTHESIS = "hypothesis"                   # inferencia, requiere confirmación
    SYNTHETIC = "synthetic_test_data"           # dataset de prueba, jamás para decisiones


class Source(BaseModel):
    name: str
    url: str | None = None
    document_type: str | None = None            # 10-K, 10-Q, 8-K, press_release, api, transcript...
    published_at: date | None = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DataPoint(BaseModel):
    """Un número con procedencia completa. La unidad del data pack que reciben los agentes."""
    entity: str                                 # ticker / company_id / bottleneck_id
    metric: str                                 # revenue, owner_fcf, dilucion_24m, runway, g_D...
    value: float | None
    unit: str = "USD"                           # USD, USD_millones, shares, pct, ratio, dias...
    currency: str | None = "USD"
    period_end: date | None = None
    period_type: str | None = None              # FY, Q, TTM, instant, spot
    fiscal_label: str | None = None             # "FY2025", "Q2 2026"
    kind: DataKind = DataKind.ORIGINAL
    verification: Verification = Verification.CONFIRMED_FILING
    source: Source
    known_at: date | None = None                # disponibilidad pública (point-in-time)
    inputs: list[str] = Field(default_factory=list)   # métricas/ids insumo (para DERIVED)
    author: str | None = None                   # agente / persona (ESTIMATE / INTERPRETATION)
    note: str | None = None

    @field_validator("value")
    @classmethod
    def _finito(cls, v: float | None) -> float | None:
        if v is not None and (math.isnan(v) or math.isinf(v)):
            raise ValueError("value debe ser finito (no NaN/inf)")
        return v


class DataPack(BaseModel):
    """El paquete de datos de una empresa que recibe el Analista — solo inputs, nunca veredicto."""
    ticker: str
    as_of: date
    puntos: list[DataPoint] = Field(default_factory=list)

    def visible_en(self, t: date) -> list[DataPoint]:
        """Anti look-ahead: solo los datapoints conocidos públicamente al tiempo t."""
        return [p for p in self.puntos if p.known_at is None or p.known_at <= t]
