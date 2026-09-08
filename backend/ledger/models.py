"""Tablas del ledger — nx_* (Etapa 2, init_docs/16).

Base propia (LedgerBase) → aislada de backend/models.py: `crear_tablas` solo crea
las nx_*, no toca las tablas del sistema viejo. Todo el log es APPEND-ONLY;
posición y caja se derivan en backend/ledger/core.py.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class LedgerBase(DeclarativeBase):
    pass


class NxCashMovimiento(LedgerBase):
    """Movimientos de caja que NO son fills: depósito inicial, tasa libre de
    riesgo, ajustes. (Dividendos y cierres entran vía NxCorporateAction.)"""
    __tablename__ = "nx_cash_movimiento"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fecha: Mapped[date] = mapped_column(Date, index=True)
    tipo: Mapped[str] = mapped_column(String(32))       # deposito_inicial | rf | ajuste
    monto: Mapped[float] = mapped_column(Float)          # signed
    nota: Mapped[str | None] = mapped_column(Text, nullable=True)


class NxFill(LedgerBase):
    """Ejecución real (Art. 11). Append-only. cash_delta = efecto neto en caja."""
    __tablename__ = "nx_fill"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    lado: Mapped[str] = mapped_column(String(4))         # buy | sell
    shares: Mapped[float] = mapped_column(Float)         # > 0
    precio: Mapped[float] = mapped_column(Float)         # fill = apertura + 30' (Art. 11.1)
    comision: Mapped[float] = mapped_column(Float, default=0.0)
    slippage_bps: Mapped[float] = mapped_column(Float, default=0.0)
    cash_delta: Mapped[float] = mapped_column(Float)
    fecha_fill: Mapped[date] = mapped_column(Date, index=True)
    fecha_decision: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fecha_dato: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    nota: Mapped[str | None] = mapped_column(Text, nullable=True)


class NxCorporateAction(LedgerBase):
    """Split / dividendo / cierre (M&A o delisting). Append-only (Art. 11.6)."""
    __tablename__ = "nx_corporate_action"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    tipo: Mapped[str] = mapped_column(String(16))        # split | dividendo | cierre
    fecha: Mapped[date] = mapped_column(Date, index=True)
    ratio: Mapped[float | None] = mapped_column(Float, nullable=True)             # split
    monto_por_accion: Mapped[float | None] = mapped_column(Float, nullable=True)  # dividendo
    valor_recupero: Mapped[float | None] = mapped_column(Float, nullable=True)    # cierre
    nota: Mapped[str | None] = mapped_column(Text, nullable=True)


class NxSnapshot(LedgerBase):
    """Marca diaria (Art. 11.5): equity, caja, doble P&L, benchmark. Append-only."""
    __tablename__ = "nx_snapshot"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fecha: Mapped[date] = mapped_column(Date, index=True)
    equity: Mapped[float] = mapped_column(Float)
    caja: Mapped[float] = mapped_column(Float)
    valor_posiciones: Mapped[float] = mapped_column(Float)
    pnl_ideal: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_modelado: Mapped[float | None] = mapped_column(Float, nullable=True)
    benchmark: Mapped[float | None] = mapped_column(Float, nullable=True)
    n_posiciones: Mapped[int] = mapped_column(Integer, default=0)


# ---------------------------- Identidad y mapa (Art. 5) ----------------------------

class NxEmpresa(LedgerBase):
    """Identidad + estado actual (proyección del log). Los 9 estados del Art. 5.
    `estado` es cache; la verdad es nx_empresa_evento."""
    __tablename__ = "nx_empresa"
    ticker: Mapped[str] = mapped_column(String(16), primary_key=True)
    nombre: Mapped[str | None] = mapped_column(String(128), nullable=True)
    jurisdiccion: Mapped[str | None] = mapped_column(String(32), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(64), nullable=True)
    estado: Mapped[str] = mapped_column(String(24), index=True)
    fuente_ingreso: Mapped[str | None] = mapped_column(String(16), nullable=True)  # manual | discovery
    fecha_ingreso: Mapped[date] = mapped_column(Date)
    reentradas_usadas: Mapped[int] = mapped_column(Integer, default=0)             # Candado B
    # ¿El último descarte es reversible por re-emisión de nodo? (descartes duros —
    # governance/fraude en deep research — NO deben revivir).
    descarte_reversible: Mapped[bool] = mapped_column(Boolean, default=True)


class NxEmpresaEvento(LedgerBase):
    """Transición de estado (append-only). Proyecta nx_empresa.estado."""
    __tablename__ = "nx_empresa_evento"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    estado_anterior: Mapped[str | None] = mapped_column(String(24), nullable=True)
    estado_nuevo: Mapped[str] = mapped_column(String(24))
    disparado_por: Mapped[str] = mapped_column(String(16))   # regla | pm | humano | sistema
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    ficha_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, index=True)


class NxNodo(LedgerBase):
    """Nodo-cuello persistido (hoy mapa/nodo.py es solo dataclass → ruido #2)."""
    __tablename__ = "nx_nodo"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(128))
    cluster: Mapped[str | None] = mapped_column(String(64), nullable=True)
    factor_macro: Mapped[str | None] = mapped_column(String(48), nullable=True)
    estado_confirmacion: Mapped[str] = mapped_column(String(24), default="promesa")
    estado_archivo: Mapped[str] = mapped_column(String(16), default="activo")
    fecha_ultima_vigilancia: Mapped[date | None] = mapped_column(Date, nullable=True)
    nota: Mapped[str | None] = mapped_column(Text, nullable=True)


class NxNodoEvento(LedgerBase):
    """Transición de estado del nodo (append-only)."""
    __tablename__ = "nx_nodo_evento"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nodo_id: Mapped[int] = mapped_column(Integer, index=True)
    estado_anterior: Mapped[str | None] = mapped_column(String(24), nullable=True)
    estado_nuevo: Mapped[str] = mapped_column(String(24))
    hecho: Mapped[str | None] = mapped_column(Text, nullable=True)
    fuente: Mapped[str | None] = mapped_column(String(4), nullable=True)
    fecha: Mapped[datetime] = mapped_column(DateTime)


class NxEmpresaNodo(LedgerBase):
    """Vínculo N↔N empresa–nodo. NUNCA se borra (Art. 5.3)."""
    __tablename__ = "nx_empresa_nodo"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    nodo_id: Mapped[int] = mapped_column(Integer, index=True)
    es_primario: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("ticker", "nodo_id", name="uq_nx_empresa_nodo"),)


# ---------------------------- Ficha rica (Etapa 4) ----------------------------

class NxFichaVersion(LedgerBase):
    """Ficha versionada (append-only): las salidas deterministas del núcleo por
    empresa en un momento. Campos de análisis nullable (un rechazo temprano no los
    computa). Ver init_docs/16 §B y 17."""
    __tablename__ = "nx_ficha_version"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    version: Mapped[int] = mapped_column(Integer)
    fecha: Mapped[date] = mapped_column(Date)
    arquetipo: Mapped[str | None] = mapped_column(String(16), nullable=True)
    quality_tier: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fragility_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    precio: Mapped[float | None] = mapped_column(Float, nullable=True)
    bull: Mapped[float | None] = mapped_column(Float, nullable=True)
    base: Mapped[float | None] = mapped_column(Float, nullable=True)   # escenario base (Art. 12.1, se llena en 4b)
    bear: Mapped[float | None] = mapped_column(Float, nullable=True)
    asimetria: Mapped[float | None] = mapped_column(Float, nullable=True)
    merito: Mapped[float | None] = mapped_column(Float, nullable=True)
    cap_celda: Mapped[float | None] = mapped_column(Float, nullable=True)
    hard_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    es_binary: Mapped[bool] = mapped_column(Boolean, default=False)
    decision: Mapped[str] = mapped_column(String(16))                 # candidata | watchlist | rechazo
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    estado_vigencia: Mapped[str] = mapped_column(String(16), default="vigente")
    __table_args__ = (UniqueConstraint("ticker", "version", name="uq_nx_ficha_version"),)


class NxHecho(LedgerBase):
    """Átomo de evidencia ligado a una versión de ficha (Art. 3). tipo/verdad/fuente
    se enriquecen con la política de evidencia (4b); en 4a llegan con defaults."""
    __tablename__ = "nx_hecho"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ficha_version_id: Mapped[int] = mapped_column(Integer, index=True)
    campo: Mapped[str] = mapped_column(String(64))
    valor: Mapped[str | None] = mapped_column(Text, nullable=True)
    tipo: Mapped[str] = mapped_column(String(12), default="HECHO")        # HECHO|INFERENCIA|HIPOTESIS
    verdad: Mapped[str | None] = mapped_column(String(8), nullable=True)  # TRUE|FALSE|UNKNOWN
    fuente: Mapped[str | None] = mapped_column(String(4), nullable=True)  # A|B|C
    documento: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_hecho: Mapped[date | None] = mapped_column(Date, nullable=True)


class NxFact(LedgerBase):
    """Fact store FUNDADO (doc 22 §4): hechos citados, versionados, con vigencia y provenance.

    Identidad lógica = (cik, fact_key); append-only e inmutable. La vigencia
    (valid_until / superseded_by) decide qué está vigente; el snapshot compiler lo lee.
    NO reemplaza NxHecho (átomos ligados a una ficha de decisión) — es la capa persistente
    de evidencia sobre la que se compila el estado. fact_type gobierna la vigencia
    (SNAPSHOT lo reemplaza el próximo período; EVENT vive hasta supersesión; STRUCTURAL persiste).
    """
    __tablename__ = "nx_fact"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cik: Mapped[str] = mapped_column(String(12), index=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    fact_key: Mapped[str] = mapped_column(String(64), index=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)             # JSON-encoded
    support_type: Mapped[str] = mapped_column(String(10), default="UNKNOWN")   # DIRECT|DERIVED|INFERRED|UNKNOWN
    estado: Mapped[str | None] = mapped_column(String(24), nullable=True)      # TRUE|FALSE|UNKNOWN_NOT_DISCLOSED|...
    fact_type: Mapped[str] = mapped_column(String(12), default="SNAPSHOT")     # SNAPSHOT|EVENT|STRUCTURAL
    fuente: Mapped[str | None] = mapped_column(String(4), nullable=True)       # A|B|C
    # Contrato de datos → scenario compiler (doc 27 §5): unidad/moneda evitan el bug de unidades
    # (#3); evidence_class = fuerza de fuente, gobierna la admisibilidad al bull operable (§6.6).
    # La ELEGIBILIDAD la decide una regla determinista (admisibilidad.py), NO el extractor/LLM.
    unit: Mapped[str | None] = mapped_column(String(16), nullable=True)        # USD|shares|pct|MT|MW|ratio…
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)     # USD|EUR…
    evidence_class: Mapped[str | None] = mapped_column(String(24), nullable=True)  # reported_audited|contract_counterparty|…
    # Cita + posición (grounding)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    quote_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quote_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Linaje + point-in-time
    source_accession: Mapped[str | None] = mapped_column(String(24), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    accepted_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Vigencia
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    superseded_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_confirmed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Provenance (sin esto la auditoría no existe — doc 22 §4)
    model_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    retriever_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    schema_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    document_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    registrado: Mapped[date | None] = mapped_column(Date, nullable=True)       # cuándo se escribió esta fila


def crear_tablas(engine) -> None:
    """Crea solo las tablas nx_* (no toca las del sistema viejo)."""
    LedgerBase.metadata.create_all(bind=engine)
