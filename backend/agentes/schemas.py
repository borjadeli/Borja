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
    # Para claims NUMÉRICOS: a qué métrica del data pack se contrasta (por id, no por NLP; doc 59 paso 3/4).
    ref_metrica: str | None = None          # p.ej. "cash", "operating_income_loss", "revenue"
    valor_num: float | None = None          # el número afirmado, en la escala `escala`
    escala: str = ""                        # "", "M", "B", "K" (millones/miles-de-millones/miles)
    periodo: str | None = None              # "FY" | "Q" | "instant" (para no comparar Q vs FY)


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


class EscenarioValuacion(BaseModel):
    """Escenario NUMÉRICO para el puente económico al precio (doc 74 D1). El Analista pone métrica terminal +
    múltiplo + horizonte + probabilidad (juicio); el determinismo hace la aritmética (retorno, reverse burden,
    probabilidad implícita). El `bear` debe ser 'la tesis FALLA' (≈ caja remanente), no 'se demora' — ahí entra
    la pata del presente. Comparten horizonte para que los MOIC sean comparables."""
    nombre: Literal["bull", "base", "bear"]
    metrica_terminal: float                  # EBITDA o revenue terminal (USD), al nivel del múltiplo
    tipo_metrica: Literal["revenue", "ebitda"]
    multiplo_salida: float                   # ancla a comparables con el crecimiento/margen del AÑO TERMINAL
    margen_terminal_pct: float | None = None  # si el múltiplo es sobre revenue: margen que lo justifica
    anios: int = Field(ge=1)
    prob: float = Field(ge=0, le=1)
    ancla_tasa_base: str | None = None        # D3: id de fila de tasas_base que ancla esta prob (o "sin_muestra")
    # Cash bridge por escenario (doc 83 F1): HIPÓTESIS de fuentes y usos hasta el año terminal. En USD. El código
    # hace la contabilidad (deuda/acciones terminales); el analista solo estima los flujos. 0 si no aplica.
    fcf_cumulative: float = 0.0              # FCF operativo acumulado a T (incluye CAPEX de mantenimiento; negativo = quema)
    new_equity_proceeds: float = 0.0         # caja NETA levantada por emisión primaria en el camino
    new_equity_shares: float = 0.0           # acciones nuevas emitidas por esa emisión
    new_debt: float = 0.0                    # deuda nueva tomada
    debt_repaid: float = 0.0                 # deuda repagada
    distributions: float = 0.0               # dividendos + recompras (salida de caja al accionista)
    dilucion_sbc: float | None = None        # dilución por SBC específica del escenario (None → usa dilucion_esperada_pct)


class Catalizador(BaseModel):
    descripcion: str
    fecha_esperada: str | None = None        # YYYY-MM-DD / YYYY-MM / null
    tipo: Literal["earnings", "contrato", "capacidad", "producto", "regulatorio", "financiamiento", "otro"]


class RedFlag(BaseModel):
    tipo: str
    severidad: Literal["alta", "media", "baja"]
    cita: Evidence


TipoVara = Literal["hito_tercero", "economico", "competitivo"]


class VaraExterna(BaseModel):
    """D2 (doc 74): el falsador se apoya en una referencia EXTERNA o ECONÓMICA, no en el propio roadmap
    (RGTI 99,5% = su propia meta no falsa nada). `comparador` = contra qué se mide (benchmark externo /
    economía unitaria / criterio comercial); `metrica`+`umbral`+`fuente_medicion` la hacen falsable (sin fuente
    de medición es tan infalsable como una narrativa). Si de verdad NO hay benchmark comparable → `no_aplica`
    con `razon_no_aplica` (el Verificador la revisa; sin esa salida el LLM fabrica un comparable = teatral)."""
    tipo: TipoVara
    metrica: str
    umbral: str
    comparador: str
    fuente_medicion: str
    accion_si_dispara: str = ""               # consecuencia pre-comprometida (ej: baja un escalón de clasificación)
    no_aplica: bool = False
    razon_no_aplica: str = ""


class Falsador(BaseModel):
    """Lo que, de cumplirse, invalida la tesis. CON FECHA — alimenta el ledger de hit-rate. La `vara_externa`
    (D2) lo saca de lo autorreferencial; None = legacy → el Verificador lo baja a REVIEW."""
    afirmacion: str
    fecha_limite: str                        # YYYY-MM-DD
    que_lo_mataria: str
    vara_externa: VaraExterna | None = None


RiesgoRemanente = Literal["cientifico", "ingenieria", "comercial", "escala"]
ClasifInvertibilidad = Literal["core", "satelite", "especulativa", "watchlist"]


class Invertibilidad(BaseModel):
    """Ficha de invertibilidad temporal (doc 70 D2) — el corazón del análisis de futuro. NO es un score:
    son campos que el Analista completa y el PM usa para clasificar. Separa 'futuro prometedor' de
    'inversión atractiva hoy'. La herramienta clave: la primera INFLEXIÓN DE VALOR (no un catalizador de
    precio) dentro del horizonte de inversión, con camino financiado y evidencia externa."""
    # Qué tipo de pregunta sigue abierta (lo que separa la cuántica por la razón correcta):
    riesgo_remanente: RiesgoRemanente
    # Primera inflexión de VALOR verificable (hecho con relación causal al valor económico; NO "sube la acción"):
    next_value_inflection: str
    months_to_inflection: int | None = None
    fundamental_impact_if_successful: str    # por qué ese hito mueve ingresos/márgenes/financiación/flujos
    independent_evidence: str                # evidencia externa de que el hito es alcanzable y relevante
    traccion_0_4: int = Field(ge=0, le=4, description="0 PR/MOU · 1 piloto pago · 2 vinc.c/cond · 3 vinc. · 4 revenue recurrente")
    # Camino financiado (determinista cuando hay datos; el Analista lo resume citando el pack):
    milestone_funding_coverage: str          # ¿la caja+financiación comprometida llega al próximo hito?
    stress_funding_gap: str                  # gap bajo estrés razonable
    subsequent_capital_need: str             # qué capital hace falta DESPUÉS para monetizar
    dilution_exposure: str                   # overhang: ATM/warrants/convertibles/lockups
    price_implied_requirements: str          # qué exige el precio (reverse underwriting) + base rate
    dependencia_politica_publica: str = ""   # subsidio/crédito/préstamo de agencia que una elección revierte
    critical_unverified_assumption: str      # el supuesto que, si es falso, tumba la tesis
    test_de_atraso: str                      # ★ "¿qué pasa si todo sale bien pero 2 años más tarde?"
    analyst_classification: ClasifInvertibilidad


class InstrumentoCapital(BaseModel):
    """Inventario de un instrumento de capital material (doc 83 F2). El Analista lo provee CON cita al filing; el
    código (resolver) decide por términos qué convierte en cada escenario. Sin esto, un share count 'fully diluted'
    sumado a mano es engañoso (caso MP: 178M básicas + converts/preferida/warrant, no un número único)."""
    id: str
    tipo: Literal["convertible", "convertible_preferred", "warrant", "term_debt"]
    principal: float = 0.0                    # nominal en USD (absoluto)
    conversion_price: float | None = None     # convierte si V_i ≥ este precio
    potential_shares: float = 0.0             # acciones si convierte/ejerce
    en_deuda_xbrl: bool = False               # ¿ya está en la deuda del balance? (no doble-contar)
    liq_preference: float = 0.0               # preferida: piso de liquidación USD (senior al común si no convierte)
    strike: float | None = None              # warrant: precio de ejercicio (entra caja)
    hedge_cap: float | None = None           # capped call: tope hasta el que se neutraliza la dilución
    mandatory: bool = False                  # mandatory convertible: convierte SÍ o SÍ a T (nunca queda senior)
    cita: str | None = None                  # accession/URL del filing


class CargaFactor(BaseModel):
    """Carga de un driver/factor común (doc 83 §3, F4). El Analista asigna la intensidad (1 primario / 0.5
    secundario) eligiendo de la taxonomía CERRADA del IPS; el código capea la exposición ponderada de cartera."""
    factor: str                               # debe estar en taxonomia_factores del ips.yaml
    intensidad: float = Field(ge=0, le=1)     # 1.0 = dependencia central · 0.5 = material no dominante


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
    invertibilidad: Invertibilidad | None = None   # ficha de futuro (doc 70 D2); None = dossier legacy
    # Puente económico al precio (doc 74 D1): escenarios numéricos + insumos del equity bridge/dilución. Vacío
    # = dossier legacy / sin puente (→ el inverso da UNKNOWN y D4 lo trata como máx. especulativa).
    escenarios: list[EscenarioValuacion] = Field(default_factory=list)
    instrumentos: list[InstrumentoCapital] = Field(default_factory=list)   # inventario de capital (doc 83 F2)
    factores_carga: list[CargaFactor] = Field(default_factory=list)        # drivers comunes (doc 83 F4)
    caja_neta_terminal: float | None = None        # caja − deuda estimada del año terminal (equity = EV + esto)
    dilucion_esperada_pct: float | None = None     # dilución acumulada al terminal (PISO determinista de Tier A)
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
    motivos: list[str] = Field(default_factory=list)               # por qué el veredicto (gates duros)
    notas: list[str] = Field(default_factory=list)                 # gaps no-materiales (PASS con notas, doc 64 B1)


# --------------------------------------------------------------------------- 7. PM

AccionTipo = Literal["comprar", "vender", "recortar", "aumentar", "mantener", "caja"]


class PMAccion(BaseModel):
    ticker: str
    accion: AccionTipo
    peso_objetivo: float = Field(ge=0, le=1, description="fracción de cartera (0-1); el IPS valida el techo")
    conviccion_0_1: float = Field(
        ge=0, le=1, description="convicción del PM en la tesis (P tesis se sostiene) — insumo del Brier del ledger")
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
    # los 4 últimos (doc 74 D5) son hallazgos de la búsqueda web adversarial del Auditor (lo que el comité no vio)
    tipo: Literal["concentracion", "coherencia_memo_peso", "coherencia", "rotacion", "verificacion_fallida",
                  "violacion_ips", "omision_material", "evento_proximo", "clausula_filing", "competidor"]
    detalle: str                                 # D5: hallazgo + evidencia (url) + consecuencia (qué número cambia)
    severidad: Literal["alta", "media", "baja"]


class AuditReport(BaseModel):
    meta: AgentMeta
    objeciones: list[AuditObjecion] = Field(default_factory=list)
    devuelve_al_pm: bool                      # máx 1 vuelta
    replica_pm: str | None = None
    decision_final_registrada: bool = False
