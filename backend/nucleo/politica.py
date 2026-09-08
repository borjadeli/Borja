"""Archivo de política versionado (doc 28 §0, §6) — TODAS las constantes de juicio en un solo lugar.

El juicio del sistema vive acá, aislado en constantes GLOBALES y versionadas. Cambiar cualquiera
BUMPEA la versión (y obliga a recorrer toda la cartera — regla anti "revisar la constante para salvar
una tesis", doc 28 §0). Cada output del compiler estampa `version`+`hash`; sin versión no es auditable.

Los números son PRIORS de política, NO verdades empíricas (doc 28 §0). Se calibran contra historial
propio a los ~8 trimestres de operación; al calibrar, se recorre toda la cartera.
"""
from __future__ import annotations

import hashlib
import json

VERSION = "v2.3"    # v2.1: +sizing continuo bucket growth. v2.2: quita triple-conteo SBC + gate carril por burden.
                    # v2.3: sizing_burden produce un CAP en [4%,8%] (no el size) — el PM elige adentro (doc 39/47)

# --- Retención por tipo de contrato (doc 28 §1). retención = 1 − haircut. ---
# destino: "operable" (entra al bull con la retención) | "ledger_O3" (condicional/ceiling → no valúa).
# cap=True: usar min(fracción contractual leída, retención) — la retención es el techo, no el default.
RETENCION_CONTRATO: dict[str, dict] = {
    "take_or_pay_min":      {"retencion": 0.90, "destino": "operable", "cap": True},
    "gov_funded_task_order": {"retencion": 0.90, "destino": "operable"},
    "firm_po":               {"retencion": 0.85, "destino": "operable"},
    "lta_committed_min":     {"retencion": 0.85, "destino": "operable"},   # solo el mínimo comprometido
    "cancelable_backlog":    {"retencion": 0.60, "destino": "operable"},
    "idiq_ceiling":          {"retencion": 0.0,  "destino": "ledger_O3"},  # "hasta $X" NO es backlog
    "conditional_award":     {"retencion": 0.0,  "destino": "ledger_O3"},  # condición precedente
}

# --- Piso universal + cap agregado (doc 28 §1 fallback) ---
PISO_UNIVERSAL = 0.50            # hecho contratado sin cláusula/historia entra al 50%
CAP_AGREGADO_PISO = 0.40         # si > 40% del (bull−bear) viene del piso → evidencia_insuficiente

# --- Tasa de descuento / retorno exigido por arquetipo (doc 28 §2) — fija en política, nunca por nombre ---
# ÚNICA tabla canónica de `r` del sistema: la usan la valuación operable (templates/bridge) Y el reverse
# underwriting (pre_revenue). Antes convivía con un duplicado divergente `ranking._TASA` (borrado en v1.1
# tras triangulación 2026-08): `r` = costo de equity del arquetipo, leído en dos direcciones (descontar
# hacia atrás en valuación, capitalizar hacia adelante en reverse underwriting) — es la MISMA magnitud.
# Anclada en costo de equity real de small/mid cap ilíquida (rf + β×ERP + size/iliquidez + stage; techo
# ~25% deliberado: los hurdles VC 40-70% bundlean failure+dilución, que BORJA modela aparte → no van en r).
# La binaria NO se castiga con r (riesgo idiosincrático, beta≈0): se maneja por PoS + cap de sizing.
R_ARQUETIPO = {"Madura": 0.12, "Growth": 0.15, "Tracción": 0.20, "Pre-revenue": 0.25, "Binary": 0.25}

# --- Cap yield TERMINAL del reverse underwriting (doc 31 §2, fix triangulación 2026-08) ---
# En FCFE_req = OP × r_exit × (1+r_hurdle)^t, el PRIMER factor es el múltiplo de salida (cap yield del
# estado YA de-riesgado al que la empresa migra a t años), NO el r de la etapa de HOY. Usar r_hurdle en
# ambos lugares castiga dos veces el ser pre-revenue hoy, cuando el propio escenario dice que a t=5 ya
# migró a Growth. r_exit = min(r_hurdle, R_TERMINAL): las de-riesgadas conservan su tasa baja; las
# riesgosas bajan al estado maduro. Constante única (no tabla) — el spread de migración es <0.01 (IA1+IA2).
R_TERMINAL = 0.15   # ≈ costo de equity del estado comercializado/rentable (Growth)

# --- Cap por TIER de riesgo de capital (doc 28 §8 / doc 34 §1) — A/B/C → 8/5/2.5% ---
# El tier de riesgo de capital (¿financiada hasta su hito? runway+dilución) → techo de sizing. Es UNO de los
# caps que entran al min() (junto a arquetipo×fragilidad, liquidez, sector). Priors versionados (doc 28 §0).
CAP_TIER_CAPITAL = {"A": 0.08, "B": 0.05, "C": 0.025}

# --- Cap de VALUACIÓN por estado (doc 34 §3ter) — retícula DISCRETA, no función continua (anti-score) ---
# El estado sale de la cobertura de GP_req por evidencia contratada (o del burden como proxy). Es UNO de los
# caps del min(); COVERED no restringe (1.0), OPTION_PRICED empuja al piso, NON_UNDERWRITABLE saca (0).
CAP_VALUACION = {"COVERED": 1.0, "STRETCH": 0.04, "OPTION_PRICED": 0.02, "NON_UNDERWRITABLE": 0.0}
# Bandas de burden → estado (proxy hasta la cobertura de GP_req fina; en burden-múltiplo del GP actual).
# ⚠️ UNCALIBRADO: el target es anclar los bordes en base rates (¿cuántas compusieron GP a ese CAGR una década?).
UMBRAL_BURDEN_COVERED = 3.0      # ≤3× → el precio lo cubre casi la economía actual → COVERED
UMBRAL_BURDEN_STRETCH = 12.0     # ≤12× → gap cerrable escalando lo demostrado → STRETCH; >12× → OPTION_PRICED
MIN_VIABLE = 0.015               # posición mínima viable (< esto no entra); distinto del PISO_POSICION viejo (merito)

# --- Umbral de ABSTENCIÓN por cobertura de evidencia (doc 34 §3bis) ---
# Abajo de este umbral de cobertura el sistema NO decide: ABSTENCIÓN determinista (EVIDENCIA_INSUFICIENTE →
# fuera del ciclo → cola de investigación), NO un veto. "No sé" ≠ "no". La tasa de abstención es métrica de
# salud de 1ª línea (si no baja en el tiempo, el cuello es la EXTRACCIÓN, no los gates).
# ⚠️ UNCALIBRADO (placeholder): el target es umbral POR TIPO DE HECHO desde la medición de retrieval
# (precisión por fact_key vs muestra auditada, [[motor-evidencia-medido-solido]]), no una cobertura agregada a ojo.
UMBRAL_COBERTURA_ABSTENCION = 0.10

# --- Carril especulativo (doc 29 §4/§5) — opcionalidad con libro/presupuesto PROPIOS y contenidos ---
# La especulación cambia la SELECCIÓN sin contaminar el número duro ni desplazar un nombre contratado (§1).
# Todos priors versionados (§5): calibrables por hit-rate, cambiarlos bumpea versión y recorre la cartera.
CAP_CARRIL_POS = 0.08          # §4: tamaño de una opcional = min(arquetipo×fragilidad, 8%)
MAX_PLAZAS_CARRIL = 2          # §4: máx 2 plazas opcionales (máx 1 por catalizador/cuello — refinamiento pendiente)
PISO_CARRIL = 0.10             # §5: piso AGREGADO del carril desde el día 1 (real y accionable ya)
TECHO_CARRIL = 0.25            # §5: techo AGREGADO, ganado por hit-rate sobre hitos resueltos (trailing 8Q)
RUNWAY_MIN_CARRIL = 1.5        # §2 supervivencia: runway mínimo (años) hasta el hito si no está capturado en fragilidad
HITO_MAX_MESES_CARRIL = 18     # §2: el hito tiene que resolver en ~12-18 meses
# §3: rúbrica citada → grado ordinal de opcionalidad (más alto = rankea mejor en el carril). El LLM produce
# las RESPUESTAS citadas; esta tabla versionada produce el ORDEN (NUNCA un escalar de "probabilidad" del LLM).
# ⚠️ PESOS UNCALIBRADOS (prior, doc 28 §0): candidato a triangular. Desempate intra-grado por densidad de
# falsabilidad (# hitos fechados que resuelven en 2-4Q) — pendiente (hoy placeholder por cobertura).
PESO_RUBRICA_OPCION = {"contraparte_financiada": 2, "dinero_autorizado": 1, "transaccion_precedente": 1}

# --- Ruteo de dos ejes (doc 42 §2, Bloque 2 D2) — qué gramática de valuación por empresa ---
# El test es de DERIVADA (apalancamiento operativo demostrado), no de nivel. Priors versionados.
SBC_REV_MAX_COMERCIAL = 0.25   # SBC/revenue > esto sostenido → motor comercial ficticio → BURDEN (doc 42 §2)
GM_MIN_ESCALANDO = 0.55        # gross margin mínimo para el bucket COMERCIAL_ESCALANDO (good-loser)
RUNWAY_MIN_ESCALANDO_M = 24    # meses de runway mínimos para ESCALANDO (si no, no aguanta el ramp)
APAL_LAG_Q = 3                 # doc 47 (triangulación IA#3): el S&M de HOY produce gross profit en 2-4Q; medir
                               # GP vs OpEx contemporáneos sesga el apal ABAJO en quien ACELERA inversión. Se lag-ea
                               # el GP 3Q. Medido: rescató NET (0.70→1.20, falso negativo), desenmascaró S (1.13→0.85,
                               # falso positivo por disciplina de costos post-layoff), confirmó PL no-escala.
BASE_RATE_N_MIN = 20           # denominador mínimo de una celda de base-rate para admitir la vía binaria (doc 42 §1)
# --- Gramática binaria — piso de liquidación + quinto estado (doc 42 §1/§Q4, skeleton) ---
# V_fracaso SOLO de XBRL (texto solo resta, nunca suma). Default 0 legítimo (converts). Priors versionados.
WIND_DOWN_QTRS = 2             # reserva de wind-down = 2 trimestres de opex (fijo por política, doc 42 §Q4)
BURN_HORIZONTE_P90 = 1.5       # multiplicador P90 sobre el horizonte de burn (retrasos de la reference class)
K_FLOOR_BINARIA = 1.4          # quinto estado: sin base-rate, solo underwritable si Precio_ops ≤ V_fracaso × k

# --- Canal de JUICIO (doc 39 §2.6, Bloque 3) — el juicio acotado, presupuestado y puntuado ---
# El PM-LLM emite SOLO etiquetas; este allocator determinista las traduce a una banda. El LLM NUNCA emite un
# número. El juicio se mueve DENTRO de [piso, techo], NUNCA supera el techo (cap de supervivencia).
PRESUPUESTO_PROMOCIONES = 3    # máx PROMOCIONES de juicio por ciclo (vetos ilimitados) — §2.6. Se achica solo si
                              # el juicio no le gana al baseline (ledger de hit-rate).
# Cuánto mueve una PRIORITY dentro de la banda [base, techo] (fracción del gap base→techo). NUNCA pasa el techo.
FACTOR_PRIORITY = {"PRIORITY_HIGH": 1.0, "PRIORITY_MEDIUM": 0.5, "PRIORITY_LOW": 0.25}
SIZE_PROBE_JUICIO = 0.01      # tamaño de un ADMIT_PROBE (rescate de falso-negativo determinista) — chico, dentro
                              # del presupuesto de probes (carril). Entre MIN_VIABLE-ish y el cap del carril.

# --- Escalera de add-on (doc 46, CERRADA por triangulación) — `stage` escala el techo del min() ---
# NO es un módulo: w_target = STAGE_FRACTION[stage] × LIVE_CAP. `stage` sube SOLO por hechos citados (triggers).
# Discreto y fijo (nunca proporcional al Δriesgo = juicio numérico encubierto). Priors versionados.
STAGE_FRACTION_COMERCIAL = [0.25, 0.50, 0.75, 1.00]   # probe + 3 add-ons; cada stage resuelve un riesgo distinto
STAGE_FRACTION_BINARIA = [0.20, 0.50]                 # probe + 1; post-evento → RE-CLASIFICA arquetipo (no auto-100)
HISTERESIS_ADD = 0.15                                 # solo add si target > peso + 0.15×techo (evita micro-adds)
TOL_MARGEN_FALSACION_A = 0.5                          # A3 comercial: add si M_t ≥ M_{t-1} − 0.5 años (anti sapo hervido)
TOL_MARGEN_FALSACION_B = 0.90                         # A3 binaria: add si M_t ≥ 0.90 × M_{t-1}
# TRIM (doc 46 §5) — la valuación CONGELA, no vende. Trim SOLO por peso o falsación, NUNCA por ganancia.
ABSOLUTE_SINGLE_NAME_CAP = 0.10                       # tope duro de un nombre (% NAV)
DRIFT_MULT = 2.0                                      # DRIFT_LIMIT = min(2×CAP_ANCHOR, ABSOLUTE); deja correr al ganador
TRIM_TARGET_FRAC = 0.75                               # trim a 0.75 × DRIFT_LIMIT
COOLDOWN_TRIM_DIAS = 90
FREEZE_TRIGGER_QTRS = 2                               # fail-closed: trigger vencido/no-evaluado → stage−1 + freeze 2Q

# --- Cuota EX-ANTE por arquetipo (doc 34 §3bis) — CAP agregado por arquetipo en la cartera ---
# El trade-off cross-arquetipo se decide UNA vez acá, a nivel política, no por nombre y no en caliente (evita el
# "lo mejor de cada arquetipo" = "lo que me gustó"). Son CAPS, no cuotas obligatorias: si no hay buena empresa en
# un arquetipo, el capital queda en cash. Priors versionados; se calibran por presupuesto de riesgo, no a ojo.
CUOTA_ARQUETIPO = {"Madura": 0.50, "Growth": 0.50, "Tracción": 0.40, "Pre-revenue": 0.35, "Binary": 0.15}

# --- Crecimiento DEMOSTRADO para el reverse-DCF (doc 36 §3/§4) — priors versionados, unidireccionales (recortan) ---
G_TERMINAL = 0.03                # g_∞ nominal al que fadea todo crecimiento (madurez)
CAP_CRECIMIENTO_ARQ = {          # cap DURO de g_D por arquetipo: nadie recibe crédito por > esto (base rate ~0 a >3-4a)
    "Madura": 0.15, "Growth": 0.40, "Tracción": 0.40, "Pre-revenue": 0.40, "Binary": 0.30}
UMBRAL_BASE_CHICA = 50e6         # revenue TTM < esto → cap g_D a 0.30 (crecer desde base chica no es sostenible)
CAP_BASE_CHICA = 0.30
FACTOR_MARGEN_COMPRADO = 0.75    # ΔGM_3y < −300bps → crecimiento "comprado" con margen → ×0.75
UMBRAL_GM_COMPRADO = -0.03       # caída de margen bruto 3y que dispara el castigo (−300bps)
FACTOR_INORGANICO = 0.50         # M&A_cash ≥ 20%·ΔRevenue → inorgánico → ×0.50
UMBRAL_INORGANICO = 0.20
FACTOR_DECEL_MAX = 0.50          # castigo máximo por deceleración de los 8 YoY (g_D *= 1 − FACTOR·decel, decel∈[0,1])
# Concentración de clientes → crecimiento FRÁGIL (no durable). Validación externa 2026-08-26: la IA objetiva
# cazó "63% en 3 clientes" de CLS como riesgo de 1er orden que nuestro g_D plano ignoraba. Un cliente que se va
# = el crecimiento colapsa → se descuenta g_D. Umbral y factor priors versionados.
UMBRAL_CONCENTRACION_FRAGIL = 0.30   # concentración top-cliente > 30% → crecimiento frágil
FACTOR_CONCENTRACION = 0.70          # g_D *= 0.70 si concentración > umbral (crecimiento no durable)

# --- Tasa de LECTURA del reverse-DCF (doc 37) — r_mkt, SEPARADA del hurdle R_ARQUETIPO ---
# DOS namespaces de tasa (doc 37): `r_mkt` para LEER qué pricea el mercado (reverse-DCF, piso operable),
# `R_ARQUETIPO` (hurdle) para EXIGIR tu retorno. Un mismo número para las dos = colisión. r_mkt = Rf +
# β_sectorial × ERP, SIN prima de size/iliquidez/stage (esas explican como riesgo lo que querés detectar como
# mispricing). ⚠️ prior (snapshot 2026-08: Rf~4.65 + ERP~4.18); recalibrar con inputs fechados. β sectorial.
R_MKT_MODELO = {"software": 0.10, "semis": 0.11, "hardware": 0.095, "servicios": 0.09,
                "salud": 0.10, "energia": 0.095, "default": 0.10}


def r_mkt(modelo: str = "default") -> float:
    """Costo de equity de MERCADO por modelo de negocio (lente de LECTURA, doc 37). NO es el hurdle."""
    return R_MKT_MODELO.get(modelo, R_MKT_MODELO["default"])


# --- Reverse-DCF: superficie de margen + umbrales de T* (doc 36 §1/§6) — priors versionados ---
# Margen owner-FCF (FCF−SBC / revenue) de comparables MADUROS por MODELO DE NEGOCIO, fijado ANTES de ver el
# ticker (guarda anti margin-laundering, doc 36 §7). ⚠️ UNCALIBRADO (prior): el target (P1) es computarlo del
# bulk XBRL de la SEC por modelo. El estado se barre P25/P50/P75 y toma el PEOR.
MARGEN_TERMINAL_MODELO = {
    "software":  {"P25": 0.18, "P50": 0.25, "P75": 0.32},
    "semis":     {"P25": 0.12, "P50": 0.18, "P75": 0.25},
    "hardware":  {"P25": 0.06, "P50": 0.10, "P75": 0.15},
    "servicios": {"P25": 0.06, "P50": 0.10, "P75": 0.14},
    "salud":     {"P25": 0.10, "P50": 0.16, "P75": 0.24},
    "energia":   {"P25": 0.08, "P50": 0.14, "P75": 0.22},
    "default":   {"P25": 0.08, "P50": 0.14, "P75": 0.20},
}
H_MARGEN = 7                    # años para que el margen converja m_0 → m_j (doc 36 §1)
T_MAX_REVERSE = 30             # tope de búsqueda de T*; sin raíz antes → NON_UNDERWRITABLE
# Umbrales v1 de T* → estado (doc 36 §6). COVERED se juzga a margen P25 (conservador), STRETCH a P50, OPTION a
# P75 — la superficie de margen se pliega EN la escalera. ⚠️ prior; v2 = umbrales en p_BR (base rate).
UMBRAL_T_COVERED = 3.0
UMBRAL_T_STRETCH = 7.0
UMBRAL_T_OPTION = 12.0
TV_SHARE_MAX_COVERED = 0.80    # PV(terminal)/P_ops > esto → no puede ser COVERED (doc 36 §7)

# --- Sizing CONTINUO del bucket growth/BURDEN (doc 47, triangulación 3-voces + medición 2026-09-03) ---
# Reemplaza el "todo BURDEN → OPTION_PRICED (masa puntual ~2%)" por techo-con-distribución: SIZE = CAP × f_val(T)
# × q_GM × q_apal × q_ps, con cap de CLUSTER y muerte del piso. CALIBRABLES (la IA#3 marcó que CAP y tolerancia
# a DD son decisión del operador). T_min/T_max reusan UMBRAL_T_COVERED/OPTION (3/12).
# `sizing_burden` produce un CAP (techo), NO el tamaño — la SELECCIÓN y el size final los hace el PM DENTRO del cap
# (doc 39, sándwich: determinismo=límites, juicio=elige adentro). Por eso el cap tiene PISO (un nombre elegible
# nunca recibe cap 0 — eso le prohibiría al PM tener una tesis de aceleración de crecimiento). Rango [FLOOR, MAX].
CAP_FLOOR_BURN = 0.04          # cap MÍNIMO de un nombre elegible del bucket (decisión del operador 2026-09-03)
CAP_BURN_BUCKET = 0.08         # cap MÁXIMO single-name del bucket owner-FCF<0 / growth. (calibrable)
CLUSTER_CAP_MULT = 2.0         # Σ peso del bucket ≤ CLUSTER_CAP_MULT × CAP (N_eff: ρ≈0.7 ⇒ 5 nombres≈1.3 apuestas)
ACRETIVIDAD_MIN = 0.12         # ΔGP/acción(8Q anual) ≥ esto → acretivo (dilución financia algo) = mejor anti-diluidor
# NO hay factor de impuesto SBC en el producto: la dilución YA se cobra 2× (burden via owner-FCF post-SBC + q_ps
# acretividad). Un 3er factor SBC = triple conteo (la IA#3 lo marcó explícito) → aplastaba todo a "empresa perfecta".
BURDEN_CARRIL_MIN = 15.0       # fcf_pre_sbc<0 → carril SOLO si burden > esto (pura opción, tipo RKLB 41×). Un comercial
                               # que-invierte con burden moderado (KTOS 7.5×) va al libro duro CHICO, no al sleeve. (calibrable)
# Anclas de persistencia de crecimiento (doc 36 §5) — DISPLAY/auditoría (bootstrap; P1 = tabla propia del
# bulk XBRL). fracción histórica que sostuvo ≥ g durante T años (revenue inicial > $50M).
BASE_RATE_PERSISTENCIA = {  # g → {años: fracción}
    0.20: {5: 0.17, 10: 0.04}, 0.30: {5: 0.085, 10: 0.015},
    0.40: {5: 0.04, 10: 0.008}, 0.50: {5: 0.02, 10: 0.002}}

# --- Horizonte por arquetipo (años) — fijo en política, anti horizon-creep (doc 28 §1) ---
HORIZONTE_T = {"Madura": 5, "Growth": 5, "Tracción": 5, "Pre-revenue": 5, "Binary": 5}

# --- Utilización física (doc 28 §3 template D) ---
UTILIZACION = {"FOAK": 0.60, "NOAK": 0.85}

# --- Invariantes (doc 28 §2) ---
DESCUENTO_DILUCION = 0.20        # RESERVADO/SIN USO: era I3 (dilución EN el bridge); DESCARTADO por doc 33 §4
                                # (dilución = eje separado, ya en dilucion.py). Ver doc 14 §E3-bis. No se borra
                                # para no bumpear versión por un muerto; queda anotado.
PPE_REALIZABLE = 0.30           # bear tracción/pre-revenue: PP&E a 30% (mercado secundario ilíquido)
SHARE_FLAG = 0.20               # template D: share implícito > 20% sin planta operando → flag

# --- Template de valuación operable (doc 28 §2/§3) ---
IMPUESTO = 0.21                  # tasa impositiva para UFCF = EBIT × (1 − tax)
PROFIT_GATE_QTRS = 4            # terminal (perpetuidad) solo si ≥4 trimestres seguidos de EBIT > 0

# --- Guardas de plausibilidad del falsador ("un dato mal no debería pasar bajo ningún concepto") ---
# El bridge en perpetuidad capitaliza el margen ACTUAL; con margen bajo, el revenue implícito explota.
# Estas guardas hacen que un número absurdo NO salga como número → no_evaluable (requiere el template).
MARGEN_MIN_PERPETUIDAD = 0.05    # margen UFCF < 5% → perpetuidad sobre margen actual no es fiable
MULT_REVENUE_IMPLICITO_MAX = 15.0  # revenue implícito > 15× el operable → implausible (margen no normalizado)


def _hash() -> str:
    """Hash determinista del contenido de política — para estampar outputs (doc 28 §6)."""
    blob = json.dumps({
        "version": VERSION, "retencion": RETENCION_CONTRATO, "piso": PISO_UNIVERSAL,
        "cap_piso": CAP_AGREGADO_PISO, "r": R_ARQUETIPO, "r_terminal": R_TERMINAL, "T": HORIZONTE_T,
        "cap_tier": CAP_TIER_CAPITAL, "cuota_arq": CUOTA_ARQUETIPO,
        "umbral_abst": UMBRAL_COBERTURA_ABSTENCION,
        "cap_valuacion": CAP_VALUACION, "burden_covered": UMBRAL_BURDEN_COVERED,
        "burden_stretch": UMBRAL_BURDEN_STRETCH, "min_viable": MIN_VIABLE,
        "presup_promo": PRESUPUESTO_PROMOCIONES, "factor_priority": FACTOR_PRIORITY,
        "size_probe_juicio": SIZE_PROBE_JUICIO,
        "stage_comercial": STAGE_FRACTION_COMERCIAL, "stage_binaria": STAGE_FRACTION_BINARIA,
        "histeresis_add": HISTERESIS_ADD, "abs_name_cap": ABSOLUTE_SINGLE_NAME_CAP,
        "drift_mult": DRIFT_MULT, "trim_target_frac": TRIM_TARGET_FRAC,
        "sbc_rev_max": SBC_REV_MAX_COMERCIAL, "gm_min_escalando": GM_MIN_ESCALANDO,
        "runway_min_escalando": RUNWAY_MIN_ESCALANDO_M, "apal_lag_q": APAL_LAG_Q,
        "cap_floor_burn": CAP_FLOOR_BURN, "cap_burn": CAP_BURN_BUCKET, "cluster_mult": CLUSTER_CAP_MULT,
        "acretividad_min": ACRETIVIDAD_MIN, "burden_carril_min": BURDEN_CARRIL_MIN,
        "base_rate_n_min": BASE_RATE_N_MIN,
        "wind_down_qtrs": WIND_DOWN_QTRS, "burn_p90": BURN_HORIZONTE_P90, "k_floor": K_FLOOR_BINARIA,
        "cap_carril_pos": CAP_CARRIL_POS, "max_plazas_carril": MAX_PLAZAS_CARRIL,
        "piso_carril": PISO_CARRIL, "techo_carril": TECHO_CARRIL,
        "runway_min_carril": RUNWAY_MIN_CARRIL, "hito_max_carril": HITO_MAX_MESES_CARRIL,
        "peso_rubrica_opcion": PESO_RUBRICA_OPCION,
        "g_terminal": G_TERMINAL, "cap_crec_arq": CAP_CRECIMIENTO_ARQ,
        "base_chica": UMBRAL_BASE_CHICA, "cap_base_chica": CAP_BASE_CHICA,
        "f_margen_comprado": FACTOR_MARGEN_COMPRADO, "umbral_gm_comprado": UMBRAL_GM_COMPRADO,
        "f_inorganico": FACTOR_INORGANICO, "umbral_inorganico": UMBRAL_INORGANICO,
        "f_decel_max": FACTOR_DECEL_MAX,
        "umbral_conc_fragil": UMBRAL_CONCENTRACION_FRAGIL, "f_concentracion": FACTOR_CONCENTRACION,
        "margen_modelo": MARGEN_TERMINAL_MODELO, "h_margen": H_MARGEN, "t_max_rev": T_MAX_REVERSE,
        "t_covered": UMBRAL_T_COVERED, "t_stretch": UMBRAL_T_STRETCH, "t_option": UMBRAL_T_OPTION,
        "tv_share_max": TV_SHARE_MAX_COVERED, "r_mkt": R_MKT_MODELO,
        "util": UTILIZACION, "dil": DESCUENTO_DILUCION, "ppe": PPE_REALIZABLE,
        "share_flag": SHARE_FLAG, "margen_min": MARGEN_MIN_PERPETUIDAD,
        "mult_rev_max": MULT_REVENUE_IMPLICITO_MAX, "impuesto": IMPUESTO,
        "profit_gate": PROFIT_GATE_QTRS,
    }, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


HASH = _hash()


def sello() -> dict:
    """El sello de política que cada output del compiler debe estampar (doc 28 §6)."""
    return {"politica_version": VERSION, "politica_hash": HASH}


def retencion_contrato(tipo: str) -> dict:
    """Retención + destino por tipo de contrato. Tipo desconocido → conservador: piso, operable."""
    r = RETENCION_CONTRATO.get(tipo)
    if r is None:
        return {"retencion": PISO_UNIVERSAL, "destino": "operable", "fallback": True}
    return dict(r)


def r_efectiva(arquetipo: str) -> float:
    """Tasa de descuento / retorno exigido del arquetipo (default Growth si desconocido)."""
    return R_ARQUETIPO.get(arquetipo, R_ARQUETIPO["Growth"])


def cap_tier_capital(tier: str) -> float:
    """Cap de sizing por tier de riesgo de capital A/B/C → 8/5/2.5% (doc 28 §8). Desconocido → C (conservador)."""
    return CAP_TIER_CAPITAL.get(tier, CAP_TIER_CAPITAL["C"])


def grado_opcionalidad(contraparte_financiada: bool, dinero_autorizado: bool,
                       transaccion_precedente: bool) -> int:
    """Grado ordinal de opcionalidad (doc 29 §3) desde las 3 respuestas citadas de la rúbrica. Suma de pesos
    versionados (PESO_RUBRICA_OPCION). 0-4; más alto = opcionalidad más fundada = rankea mejor en el carril."""
    g = 0
    if contraparte_financiada:
        g += PESO_RUBRICA_OPCION["contraparte_financiada"]
    if dinero_autorizado:
        g += PESO_RUBRICA_OPCION["dinero_autorizado"]
    if transaccion_precedente:
        g += PESO_RUBRICA_OPCION["transaccion_precedente"]
    return g


def cap_valuacion(estado: str) -> float:
    """Cap de sizing por estado de valuación (doc 34 §3ter). Estado desconocido → OPTION_PRICED (conservador:
    si no sé cuánto exige el precio, asumo que exige mucho → piso)."""
    return CAP_VALUACION.get(estado, CAP_VALUACION["OPTION_PRICED"])


def estado_valuacion_por_burden(burden: float | None) -> str:
    """Mapea el burden (múltiplo de GP que el precio exige) → estado por bandas (doc 34 §3ter). burden None
    (no computable) → NON_UNDERWRITABLE. Cuando haya rango de burden, pasar el EXTREMO PEOR (más alto)."""
    if burden is None:
        return "NON_UNDERWRITABLE"
    if burden <= UMBRAL_BURDEN_COVERED:
        return "COVERED"
    if burden <= UMBRAL_BURDEN_STRETCH:
        return "STRETCH"
    return "OPTION_PRICED"


def cuota_arquetipo(arquetipo: str) -> float:
    """Cap AGREGADO de cartera por arquetipo (doc 34 §3bis). Desconocido → 1.0 (sin restricción propia; los otros
    caps ya limitan)."""
    return CUOTA_ARQUETIPO.get(arquetipo, 1.0)


def r_exit(r_hurdle: float) -> float:
    """Cap yield terminal del reverse underwriting = min(r_hurdle, R_TERMINAL) (doc 31 §2, fix 2026-08).
    Las de-riesgadas (Madura 0.12) conservan su tasa; las riesgosas (Pre-rev 0.25) bajan al estado
    maduro (0.15). Nunca SUBE la tasa de una empresa ya de-riesgada."""
    return min(r_hurdle, R_TERMINAL)
