"""Schemas de salida de cada agente del comité PM-IA (Capa C, v2 doc 52 §3).

Todo output de agente es INTERPRETATION (juicio), separado de los datos (provenance.DataPoint).
Regla común: cada afirmación factual lleva evidencia citada (`Evidence`) con `source_url` + `verification`.
Estos schemas son el contrato que validan los agentes con pydantic; se afinan al construir cada agente.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

VerificationLit = Literal[
    "confirmed_by_filing", "company_statement", "media_report",
    "search_summary", "analyst_prior", "hypothesis",
]


# --------------------------------------------------------------------------- comunes

class Evidence(BaseModel):
    claim: str
    source_url: str | None = None           # null = inferencia (no cita)
    source_date: str | None = None          # YYYY-MM-DD
    verification: VerificationLit


TipoClaim = Literal["hecho", "declaracion_empresa", "estimacion", "inferencia"]


class Claim(BaseModel):
    """Afirmación individualizada del Dossier (doc 54 §4) — unidad de verificación y reutilización.

    Permite al Verificador validar por afirmación (no por párrafo) y reutilizar por sección: un hecho
    nuevo invalida solo los claims afectados, no todo el Dossier.
    """
    claim_id: str
    contenido: str
    tipo: TipoClaim
    source_url: str | None = None           # null si es inferencia
    cited_text: str | None = None           # texto citado de la fuente (insumo del Verificador)
    source_date: str | None = None          # fecha de publicación de la fuente (YYYY-MM-DD)
    known_at: str | None = None             # fecha en que el sistema incorporó el dato (point-in-time)
    materiality: Literal["central", "soporte", "secundaria"]
    verification: VerificationLit


class AgentMeta(BaseModel):
    """Metadata de ejecución común a todo output de agente (costo, modelo, versión)."""
    agent: str
    prompt_version: str
    model: str
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    web_searches: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# --------------------------------------------------------------------------- 1. Macro

class CuelloPrioridad(BaseModel):
    cuello: str
    prioridad_0_3: int = Field(ge=0, le=3)
    delta_vs_anterior: Literal["sube", "baja", "igual", "nuevo"]
    razon: str


class MacroMemo(BaseModel):
    meta: AgentMeta
    ciclo_capex_ia: str
    energia: str
    commodities: str
    tasas: str
    cuellos_prioridad: list[CuelloPrioridad] = Field(default_factory=list)
    resumen: str
    evidencia: list[Evidence] = Field(default_factory=list)


# --------------------------------------------------------------------------- 2. Triage

class TriageDecision(BaseModel):
    meta: AgentMeta
    ticker: str
    prioridad_0_3: int = Field(ge=0, le=3, description="qué tan prometedora para research profundo")
    incertidumbre_0_1: float = Field(ge=0, le=1, description="valor de la información: cuánto cambiaría la visión")
    research_profundo: bool
    motivo: str


# --------------------------------------------------------------------------- 4. Analista → Dossier

class Escenario(BaseModel):
    """Bull o bear, INDEPENDIENTE. Nada de price targets libres: supuestos explícitos + contraste."""
    tesis: str
    supuestos: list[str]
    contraste_con_calculadoras: str          # cómo se compara con T*/burden/owner-FCF deterministas
    evidencia: list[Evidence] = Field(default_factory=list)


class Catalizador(BaseModel):
    descripcion: str
    fecha_esperada: str | None = None        # YYYY-MM-DD / YYYY-MM / null
    tipo: Literal["earnings", "contrato", "capacidad", "producto", "regulatorio", "financiamiento", "otro"]


class RedFlag(BaseModel):
    tipo: str
    severidad: Literal["alta", "media", "baja"]
    cita: Evidence


class Falsador(BaseModel):
    """Lo que, de cumplirse, invalida la tesis. CON FECHA — alimenta el ledger de hit-rate."""
    afirmacion: str
    fecha_limite: str                        # YYYY-MM-DD
    que_lo_mataria: str


class Dossier(BaseModel):
    meta: AgentMeta
    ticker: str
    negocio_y_posicion_cuello: str
    claims: list[Claim] = Field(default_factory=list, description="afirmaciones individualizadas y citadas")
    tesis_claims_soporte: list[str] = Field(
        default_factory=list, description="claim_ids que sostienen la tesis central (gate del Verificador)")
    valuacion_que_exige_el_precio: str       # usando T*/burden
    bull: Escenario
    bear: Escenario
    catalizadores: list[Catalizador] = Field(default_factory=list)
    red_flags: list[RedFlag] = Field(default_factory=list)
    falsador: Falsador
    conviccion_0_1: float = Field(ge=0, le=1)


# --------------------------------------------------------------------------- 5. Bear / Red team

class Objecion(BaseModel):
    afirmacion_atacada: str
    contraevidencia: str
    citas: list[Evidence] = Field(default_factory=list)
    severidad: Literal["alta", "media", "baja"]


class BearAttack(BaseModel):
    meta: AgentMeta
    ticker: str
    objeciones: list[Objecion] = Field(default_factory=list)
    replica_analista: str | None = None      # el analista responde una vez


# --------------------------------------------------------------------------- 6. Verificador

class Check(BaseModel):
    claim_id: str                            # ata el check al claim del Dossier
    procedencia_ok: bool                     # la URL está entre las que trajo web_search / el fact store
    numeros_ok: bool                         # el número coincide con el cited_text (escala/moneda/decimal)
    es_declaracion_corporativa: bool         # declaración corporativa ≠ hecho verificado
    dato_vigente: bool                       # page_age razonable (no dato viejo como actual)
    motivo: str


class VerificationReport(BaseModel):
    meta: AgentMeta
    ticker: str
    checks: list[Check] = Field(default_factory=list)
    # PASS: tesis con respaldo suficiente · REVIEW: faltantes en lo no-central · FAIL: claim central
    # (en tesis_claims_soporte) sin procedencia, o contradicción central. `fail` no justifica compra/aumento.
    veredicto: Literal["pass", "review", "fail"]
    flags_supervivencia: list[str] = Field(default_factory=list)   # going-concern / material weakness / restatement
    motivos: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- 7. PM

AccionTipo = Literal["comprar", "vender", "recortar", "aumentar", "mantener", "caja"]


class PMAccion(BaseModel):
    ticker: str
    accion: AccionTipo
    peso_objetivo: float = Field(ge=0, le=1, description="fracción de cartera (0-1); el IPS valida el techo")
    por_que_ese_tamano: str
    tesis: str
    falsador: Falsador
    que_me_haria_vender: str
    dossier_hash: str | None = None          # dossier vigente verificado que respalda la decisión


class RespuestaFlag(BaseModel):
    """Respuesta obligatoria del PM a cada flag de supervivencia del Verificador (doc 54 §4.7)."""
    flag_id: str
    accion: Literal["acepta", "reduce", "no_opera"]
    motivo: str


class PMDecision(BaseModel):
    meta: AgentMeta
    acciones: list[PMAccion] = Field(default_factory=list)
    respuestas_flags: list[RespuestaFlag] = Field(
        default_factory=list, description="debe cubrir todos los flags de supervivencia; se valida en código")
    operar_ahora: bool                        # puede quedarse en caja / no operar
    razon_timing: str


# --------------------------------------------------------------------------- 8. Auditor

class AuditObjecion(BaseModel):
    tipo: Literal["concentracion", "coherencia_memo_peso", "rotacion", "verificacion_fallida", "violacion_ips"]
    detalle: str
    severidad: Literal["alta", "media", "baja"]


class AuditReport(BaseModel):
    meta: AgentMeta
    objeciones: list[AuditObjecion] = Field(default_factory=list)
    devuelve_al_pm: bool                      # máx 1 vuelta
    replica_pm: str | None = None
    decision_final_registrada: bool = False
