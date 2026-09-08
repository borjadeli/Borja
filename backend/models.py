"""SQLAlchemy models — 9 tablas del sistema BORJA.

Invariantes:
- Ticker es PK de fichas, siempre uppercase.
- Todos los campos de análisis son escritura exclusiva del Analista.
- Historial (cambios_score, cambios_estado, etc.) es append-only.
- Enums como strings para portabilidad SQLite → PostgreSQL.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ---------- Enums (guardados como strings en DB) ----------

class EstadoFicha(str, Enum):
    CANDIDATA = "Candidata"
    UNIVERSO = "Universo"
    WL_SEGUIMIENTO = "WL_Seguimiento"
    WL_ACTIVA = "WL_Activa"
    WL_PRIORITARIA = "WL_Prioritaria"
    PORTFOLIO_ACTIVO = "Portfolio_Activo"
    BUCKET_EXPLORATORIO = "Bucket_Exploratorio"
    SUSPENDIDA = "Suspendida"
    ELIMINADA = "Eliminada"


class NivelR(str, Enum):
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    R4 = "R4"


class MomentumSectorial(str, Enum):
    """v4.2: 3 estados con clasificación humana trimestral."""
    FAVORABLE = "Favorable"
    NEUTRAL = "Neutral"
    DESFAVORABLE = "Desfavorable"
    # Mantenidos como aliases legacy para retro-compat hasta migrar todos los call-sites.
    # No usar en código nuevo.
    PRE_RALLY = "pre_rally"
    RALLY_TEMPRANO = "rally_temprano"
    RALLY_MADURO = "rally_maduro"
    AGOTAMIENTO = "agotamiento"


class TipoCatalizador(str, Enum):
    NECESARIO = "necesario"
    UTIL = "util"
    NINGUNO = "ninguno"


class ImpactoCatalizador(str, Enum):
    ALTO = "alto"
    MEDIO = "medio"
    BAJO = "bajo"


class PosicionCiclo(str, Enum):
    EARLY = "early"
    ACCELERATION = "acceleration"
    SATURATION = "saturation"


class EstadoGovernance(str, Enum):
    VERDE = "verde"
    AMARILLO = "amarillo"
    KILL_SWITCH = "kill_switch"


class TipoEvento(str, Enum):
    PRECIO_ALERTA = "PRECIO_ALERTA"
    EARNINGS_PROXIMOS = "EARNINGS_PROXIMOS"
    NOTICIA_MATERIAL = "NOTICIA_MATERIAL"
    INSIDER_ACTIVITY = "INSIDER_ACTIVITY"
    SCORE_DRIFT = "SCORE_DRIFT"
    SHORT_REPORT = "SHORT_REPORT"
    RED_FLAG = "RED_FLAG"
    MOMENTUM_SECTORIAL = "MOMENTUM_SECTORIAL"


class EstadoEvento(str, Enum):
    PENDIENTE = "pendiente"
    PROCESADO = "procesado"
    DESCARTADO = "descartado"


class AccionRecomendada(str, Enum):
    ENTRAR = "entrar"
    AUMENTAR = "aumentar"
    PIRAMIDACION = "piramidacion"
    BUCKET = "bucket"
    MANTENER = "mantener"
    REDUCIR = "reducir"
    SALIR = "salir"
    WL_PRIORITARIA = "wl_prioritaria"
    CASH_PREVENTIVO = "cash_preventivo"
    ROTAR = "rotar"


class EstadoRecomendacion(str, Enum):
    VALIDADA = "VALIDADA"
    CUESTIONADA = "CUESTIONADA"


class EstadoAprobacion(str, Enum):
    PENDIENTE = "pendiente_aprobacion"
    APROBADA = "aprobada"
    RECHAZADA = "rechazada"


class FaseMacro(str, Enum):
    FASE_1_OFENSIVA = "fase_1_ofensiva"
    TRANSICION = "transicion"
    FASE_2_DEFENSIVA = "fase_2_defensiva"


class PosturaCapital(str, Enum):
    AGRESIVA = "agresiva"
    SELECTIVA = "selectiva"
    DEFENSIVA = "defensiva"


class EstadoMapa(str, Enum):
    ACTIVO = "activo"
    VENCIDO = "vencido"
    FALLIDO = "fallido"


class EstadoTask(str, Enum):
    PENDIENTE = "pendiente"
    EN_PROGRESO = "en_progreso"
    COMPLETADO = "completado"
    FALLIDO = "fallido"


# ---------- Tablas ----------

class Ficha(Base):
    """Tabla maestra — una fila por empresa."""
    __tablename__ = "fichas"

    # Identificación
    ticker: Mapped[str] = mapped_column(String(10), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200))
    sector: Mapped[str] = mapped_column(String(64), ForeignKey("sectores.nombre"), index=True)
    driver_macro: Mapped[str | None] = mapped_column(String(200), nullable=True)
    origen: Mapped[str] = mapped_column(String(32), default="Manual")
    estado: Mapped[str] = mapped_column(String(32), default=EstadoFicha.CANDIDATA.value, index=True)
    version_tesis_macro: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Análisis — escritura exclusiva del Analista
    score_vigente: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_criterio_1: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_criterio_2: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_criterio_3: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_criterio_4: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_criterio_5: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_criterio_6: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_criterio_7: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_criterio_8: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_criterio_9: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_criterio_10: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidencia_favor_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"1": "...", ...}
    evidencia_contra_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    justificacion_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    nivel_r: Mapped[str | None] = mapped_column(String(4), nullable=True)
    tesis_vigente: Mapped[str | None] = mapped_column(Text, nullable=True)

    tipo_catalizador: Mapped[str | None] = mapped_column(String(16), nullable=True)
    catalizador_descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    catalizador_fecha: Mapped[str | None] = mapped_column(String(32), nullable=True)
    catalizador_impacto: Mapped[str | None] = mapped_column(String(16), nullable=True)

    entry_range_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_range_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_range_vencimiento: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    invalidation_triggers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    posicion_ciclo: Mapped[str | None] = mapped_column(String(16), nullable=True)
    duracion_edge: Mapped[str | None] = mapped_column(String(32), nullable=True)
    duracion_edge_justificacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_salida: Mapped[str | None] = mapped_column(Text, nullable=True)

    bull_case_precio: Mapped[float | None] = mapped_column(Float, nullable=True)
    bear_case_precio: Mapped[float | None] = mapped_column(Float, nullable=True)
    crecimiento_implicito_precio: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimacion_crecimiento: Mapped[float | None] = mapped_column(Float, nullable=True)

    management_track_record: Mapped[str | None] = mapped_column(Text, nullable=True)
    management_alignment: Mapped[str | None] = mapped_column(String(16), nullable=True)
    management_alignment_evidencia: Mapped[str | None] = mapped_column(Text, nullable=True)

    liquidez_suficiente: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    tam_excepcion: Mapped[bool] = mapped_column(Boolean, default=False)

    prompt_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    fecha_ultimo_deep_research: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fecha_proximo_deep_research: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ultima_evaluacion_triggers: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Contexto sectorial (v1.4)
    mapa_sectorial_usado: Mapped[bool] = mapped_column(Boolean, default=False)
    mapa_sectorial_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    contexto_sectorial_citado: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Governance
    red_flags_count: Mapped[int] = mapped_column(Integer, default=0)
    red_flags_count_anterior: Mapped[int] = mapped_column(Integer, default=0)
    red_flags_detalle: Mapped[str | None] = mapped_column(Text, nullable=True)
    estado_governance: Mapped[str] = mapped_column(String(16), default=EstadoGovernance.VERDE.value)

    # Posición activa
    sizing_actual: Mapped[float | None] = mapped_column(Float, nullable=True)
    capacidad_maxima_teorica: Mapped[float | None] = mapped_column(Float, nullable=True)
    precio_entrada: Mapped[float | None] = mapped_column(Float, nullable=True)
    precio_ultima_actualizacion_ficha: Mapped[float | None] = mapped_column(Float, nullable=True)
    umbral_rotacion: Mapped[float | None] = mapped_column(Float, nullable=True)
    piramidacion_disponible: Mapped[bool] = mapped_column(Boolean, default=True)
    fecha_entrada_portfolio: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Mark-to-market intra-day (job MtM cada 30 min en horario US)
    precio_mtm: Mapped[float | None] = mapped_column(Float, nullable=True)
    precio_mtm_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    entry_range_alerta_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Capital Raise Risk (v4.2 sec 4) — Bajo / Medio / Alto / Crítico.
    # Crítico = fail condition (no entra al universo).
    # Alto = no Portfolio formal (solo Bucket o eliminar).
    capital_raise_risk: Mapped[str | None] = mapped_column(String(16), nullable=True)
    capital_raise_risk_evidencia: Mapped[str | None] = mapped_column(Text, nullable=True)
    capital_raise_risk_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Filtro anti-fraude (v4.2 sec 7) — flagea sin mover estado. Humano decide.
    filtro_antifraude_violaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    filtro_antifraude_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Enmienda C v4.2: overrides por los que insider selling NO activa red flag.
    # Lista de strings: '10b5-1' / 'founder_50' / 'diversificacion_programada'.
    # Cada uno requiere evidencia documentada por el humano.
    insider_selling_overrides_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    insider_selling_overrides_evidencia: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Confidence Score por criterio + jerarquía A-F (v4.2 sec 6 + 8).
    # JSON con estructura: {"1": {"confidence": "Alta", "fuente_nivel": "A"}, ...}
    # Confidence Baja en algún claim central (criterios 1-4) bloquea Portfolio.
    confidence_y_fuentes_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Bucket exploratorio
    tesis_descubrimiento: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidencia_cliente: Mapped[str | None] = mapped_column(Text, nullable=True)
    stop_loss_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    checklist_bucket_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Historial (append-only)
    cambios_score: Mapped[list] = mapped_column(JSON, default=list)
    cambios_estado: Mapped[list] = mapped_column(JSON, default=list)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_fichas_estado_score", "estado", "score_vigente"),
    )


class Evento(Base):
    __tablename__ = "eventos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), ForeignKey("fichas.ticker"), index=True)
    tipo: Mapped[str] = mapped_column(String(32), index=True)
    descripcion: Mapped[str] = mapped_column(Text)
    fuente: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tier: Mapped[int] = mapped_column(Integer, default=2)
    estado: Mapped[str] = mapped_column(String(16), default=EstadoEvento.PENDIENTE.value, index=True)
    cooldown_hasta: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Recomendacion(Base):
    __tablename__ = "recomendaciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), ForeignKey("fichas.ticker"), index=True)
    accion: Mapped[str] = mapped_column(String(32))
    estado_rec: Mapped[str] = mapped_column(String(16), default=EstadoRecomendacion.VALIDADA.value)
    motivo_cuestionada: Mapped[str | None] = mapped_column(Text, nullable=True)

    sizing_sugerido: Mapped[float | None] = mapped_column(Float, nullable=True)
    capacidad_maxima_teorica: Mapped[float | None] = mapped_column(Float, nullable=True)
    momentum_sectorial_leido: Mapped[str | None] = mapped_column(String(32), nullable=True)
    asimetria_vigente: Mapped[float | None] = mapped_column(Float, nullable=True)
    umbral_rotacion_activo: Mapped[float | None] = mapped_column(Float, nullable=True)

    reglas_verificadas: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    checklist_completo: Mapped[bool] = mapped_column(Boolean, default=False)
    checklist_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    contexto_macro: Mapped[str | None] = mapped_column(String(256), nullable=True)
    nota_bucket: Mapped[str | None] = mapped_column(Text, nullable=True)
    justificacion: Mapped[str] = mapped_column(Text)

    # Regla piso de exposición (2026-05-04): "alta" cuando accion=entrar y exposicion<80%
    prioridad_capital: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    exposicion_pct_al_evaluar: Mapped[float | None] = mapped_column(Float, nullable=True)

    estado_aprobacion: Mapped[str] = mapped_column(String(32), default=EstadoAprobacion.PENDIENTE.value, index=True)
    timestamp_juez: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    timestamp_human: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Sector(Base):
    __tablename__ = "sectores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    momentum: Mapped[str | None] = mapped_column(String(32), nullable=True)
    momentum_origen: Mapped[str] = mapped_column(String(16), default="manual")
    ultima_actualizacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    prioridad: Mapped[str | None] = mapped_column(String(16), nullable=True)  # alta / media-alta / media
    horizonte: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Cluster de driver macro compartido (v4.2 Regla 3 ampliada). Sectores con
    # mismo cluster_driver topean en MAX_POR_DRIVER simultáneas. Ejemplo:
    # AI infra (4 sub-temas) + Power Generation = 'capex_AI'.
    cluster_driver: Mapped[str | None] = mapped_column(String(32), nullable=True)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)


class Macro(Base):
    __tablename__ = "macro"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fase_actual: Mapped[str] = mapped_column(String(32))
    postura_capital: Mapped[str] = mapped_column(String(32))
    version: Mapped[str] = mapped_column(String(16))
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_actualizacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    activa: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class SectorMapa(Base):
    """Mapa estructural del sector generado por LLM + web search."""
    __tablename__ = "sectores_mapas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sector: Mapped[str] = mapped_column(String(64), ForeignKey("sectores.nombre"), index=True)
    mapa_json: Mapped[dict] = mapped_column(JSON)
    estado: Mapped[str] = mapped_column(String(16), default=EstadoMapa.ACTIVO.value, index=True)
    fuentes_resumen: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_generacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    dias_vencimiento: Mapped[int] = mapped_column(Integer, default=21)
    criticidades_override: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    aprobado_por_humano: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_aprobacion: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DiscoveryHipotesis(Base):
    __tablename__ = "discovery"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    semana: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    hipotesis_json: Mapped[list] = mapped_column(JSON)
    prompt_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    estado: Mapped[str] = mapped_column(String(32), default="pendiente_revision")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    util: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)


class DispatchLog(Base):
    """Auditoría del Dispatcher — toda decisión de routing queda logueada."""
    __tablename__ = "dispatch_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    ticker_o_sector: Mapped[str] = mapped_column(String(64), index=True)
    tipo_evento: Mapped[str] = mapped_column(String(32))
    tier_fuente: Mapped[int] = mapped_column(Integer, default=2)
    regla_activada: Mapped[str] = mapped_column(String(128))
    destino: Mapped[str] = mapped_column(String(64))
    urgencia: Mapped[str] = mapped_column(String(16), default="media")
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    cooldown_activo: Mapped[bool] = mapped_column(Boolean, default=False)
    evento_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("eventos.id"), nullable=True)


class Task(Base):
    """Tracking de tareas async del Analista y otros agentes."""
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(32))  # analista, mapa_sectorial, discovery
    ticker_o_sector: Mapped[str | None] = mapped_column(String(64), nullable=True)
    estado: Mapped[str] = mapped_column(String(16), default=EstadoTask.PENDIENTE.value, index=True)
    progreso: Mapped[str | None] = mapped_column(String(256), nullable=True)
    resultado_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class LLMCall(Base):
    """Tracking de costo por llamada LLM. Append-only."""
    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    agent: Mapped[str] = mapped_column(String(32), index=True)  # analista, mapa_sectorial, discovery
    model: Mapped[str] = mapped_column(String(64))
    ticker_o_sector: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    tokens_input: Mapped[int] = mapped_column(Integer, default=0)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0)
    tokens_cache_read: Mapped[int] = mapped_column(Integer, default=0)
    tokens_cache_write: Mapped[int] = mapped_column(Integer, default=0)
    web_searches: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class PeerGroup(Base):
    """Peer Groups Duales (v4.2 sec 7.1) — Emerging + Anchor.

    Para empresas pre-materialización (revenue chico + contrato grande pendiente),
    el sistema mantiene dos referencias separadas:
      - Emerging (5-10 small caps comparables): para precio base sin contratos.
      - Anchor (1-2 mid caps establecidas): referencia bull case y madurez.
    NO se mezclan en un solo p50. Carga manual.
    """
    __tablename__ = "peer_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker_target: Mapped[str] = mapped_column(String(10), index=True)
    tipo: Mapped[str] = mapped_column(String(16))  # 'emerging' | 'anchor'
    peers_json: Mapped[list] = mapped_column(JSON, default=list)  # ['TKR1','TKR2',...]
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_actualizacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("ticker_target", "tipo", name="uq_peer_groups_target_tipo"),
    )


class FichaContractual(Base):
    """Ficha Contractual Estructurada (v4.2 sec 7.5) — campos positivos + negativos.

    Por cada empresa con tesis forward-looking (especialmente bucket exploratorio)
    se obliga a llenar campos positivos y campos negativos. La diferencia con
    el v4.1: el sistema obliga a tener esos datos juntos. El humano valida.
    """
    __tablename__ = "fichas_contractuales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), ForeignKey("fichas.ticker"), index=True)

    # Campos positivos
    cliente: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tipo_instrumento: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # contrato_firme | purchase_order | design_in | LOI | partnership
    monto_divulgado_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    fecha_inicio_entregas: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fuente_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    lenguaje_literal_management: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Campos negativos obligatorios
    condiciones_pendientes: Mapped[str | None] = mapped_column(Text, nullable=True)
    derechos_cancelacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    dependencias_tecnicas: Mapped[str | None] = mapped_column(Text, nullable=True)
    capex_pre_revenue: Mapped[str | None] = mapped_column(Text, nullable=True)
    lenguaje_riesgo_10k: Mapped[str | None] = mapped_column(Text, nullable=True)
    binding_o_condicionado: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # 'binding' | 'condicionado'

    # Validación humana
    aprobada_por_humano: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_aprobacion: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notas_revisor: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DecisionJournal(Base):
    """Decision Journal estructurado (v4.2 sec 8 + 10).

    Append-only. Cada decisión de capital o rechazo queda con motivo y links
    a la recomendación / evento que la disparó. Permite auditar el sistema y
    detectar patrones de "rubber-stamping humano".
    """
    __tablename__ = "decision_journal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    ticker: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    accion: Mapped[str] = mapped_column(String(32))  # entrar | aumentar | reducir | salir | rechazar | revalidacion_si | revalidacion_no | fase_2_activada | etc.
    decisor: Mapped[str] = mapped_column(String(16), default="humano")  # 'humano' | 'sistema'
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    rec_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("recomendaciones.id", ondelete="SET NULL"), nullable=True)
    evento_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("eventos.id", ondelete="SET NULL"), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Outcome posterior (a llenar manualmente cuando se sepa)
    resultado_post: Mapped[str | None] = mapped_column(Text, nullable=True)
    resultado_post_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Revalidacion(Base):
    """Revalidación forzada cada 30 días (v4.2 sec 5).

    Para cada posición activa el sistema pregunta '¿Seguís creyendo esta tesis?'.
    Si NO → 5 preguntas obligatorias (Discretionary Thesis Review).
    """
    __tablename__ = "revalidaciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), ForeignKey("fichas.ticker"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    estado: Mapped[str] = mapped_column(String(16), default="pendiente")  # 'pendiente' | 'si' | 'no'
    fecha_respuesta: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 5 preguntas obligatorias si la respuesta es No
    p1_que_aprendi: Mapped[str | None] = mapped_column(Text, nullable=True)
    p2_supuesto_cambio: Mapped[str | None] = mapped_column(Text, nullable=True)
    p3_deterioro_o_precio: Mapped[str | None] = mapped_column(Text, nullable=True)
    p4_red_team_anticipo: Mapped[str | None] = mapped_column(Text, nullable=True)
    p5_trigger_faltante: Mapped[str | None] = mapped_column(Text, nullable=True)

    accion_decidida: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # 'mantener_baja_confidence' | 'reducir_sizing' | 'a_watchlist' | 'vender' | 'nuevo_trigger'


class Trade(Base):
    """Trade — entrada y salida de una posición. P&L realizado al cerrar.

    Lifecycle:
    - apertura: aprobar rec con accion ∈ {entrar, bucket} → crea Trade(status=open)
    - aumento/piramidación: actualiza capital_deployado_usd y precio_entrada (promedio ponderado)
    - cierre: aprobar rec con accion ∈ {rotar, salir} → status=closed + pnl realizado
    - reducir: cierre parcial → split en dos rows (uno cerrado parcial + uno abierto residual)

    El P&L total del portfolio = suma(pnl_realizado de closed trades) + suma(pnl_abierto de posiciones vivas).
    """
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), ForeignKey("fichas.ticker"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)  # 'open' | 'closed'

    # Apertura
    fecha_apertura: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    precio_entrada: Mapped[float] = mapped_column(Float)
    sizing_pct_apertura: Mapped[float] = mapped_column(Float)  # % del capital
    capital_deployado_usd: Mapped[float] = mapped_column(Float)
    rec_id_apertura: Mapped[int | None] = mapped_column(Integer, ForeignKey("recomendaciones.id", ondelete="SET NULL"), nullable=True)

    # Cierre (nullable si status=open)
    fecha_cierre: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    precio_cierre: Mapped[float | None] = mapped_column(Float, nullable=True)
    valor_cierre_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_realizado_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_realizado_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    motivo_cierre: Mapped[str | None] = mapped_column(String(32), nullable=True)  # 'rotar' | 'salir' | 'reducir'
    rec_id_cierre: Mapped[int | None] = mapped_column(Integer, ForeignKey("recomendaciones.id", ondelete="SET NULL"), nullable=True)

    # Meta
    sector_apertura: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PortfolioSnapshot(Base):
    """Snapshot diario equity + posiciones — habilita equity curve histórica."""
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    fecha: Mapped[str] = mapped_column(String(10), unique=True, index=True)  # YYYY-MM-DD ET
    capital_total_usd: Mapped[float] = mapped_column(Float, default=0.0)
    equity_total_usd: Mapped[float] = mapped_column(Float, default=0.0)
    cash_usd: Mapped[float] = mapped_column(Float, default=0.0)
    exposicion_pct: Mapped[float] = mapped_column(Float, default=0.0)
    n_posiciones: Mapped[int] = mapped_column(Integer, default=0)
    pnl_total_usd: Mapped[float] = mapped_column(Float, default=0.0)
    pnl_total_pct: Mapped[float] = mapped_column(Float, default=0.0)
    pnl_dia_usd: Mapped[float] = mapped_column(Float, default=0.0)
    posiciones_json: Mapped[list] = mapped_column(JSON, default=list)


__all__ = [
    "Base",
    "Ficha",
    "Evento",
    "Recomendacion",
    "Sector",
    "Macro",
    "SectorMapa",
    "DiscoveryHipotesis",
    "DispatchLog",
    "Task",
    "LLMCall",
    "PortfolioSnapshot",
    "PeerGroup",
    "FichaContractual",
    "DecisionJournal",
    "Revalidacion",
    "Trade",
    "EstadoFicha",
    "NivelR",
    "MomentumSectorial",
    "TipoCatalizador",
    "ImpactoCatalizador",
    "PosicionCiclo",
    "EstadoGovernance",
    "TipoEvento",
    "EstadoEvento",
    "AccionRecomendada",
    "EstadoRecomendacion",
    "EstadoAprobacion",
    "FaseMacro",
    "PosturaCapital",
    "EstadoMapa",
    "EstadoTask",
]
