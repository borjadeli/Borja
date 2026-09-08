"""Gold set + medición del RETRIEVAL (Bloque 0, doc 32 §5; diseño triangulado IA1+IA2).

Por qué existe: el cuello real de la capa citada es el RETRIEVAL (ubicar el pasaje), no los
gates. Caso canónico AAOI: el pasaje "revenues from Digicomm … 42.8%" ESTÁ en el 10-Q pero el
`_window` no lo trae (el anchor `revenue from` singular no matchea "revenueS from" plural).
Para mejorarlo sin tunear a ciegas hay que MEDIRLO. Este módulo define el gold set + la métrica.

Lecciones de la triangulación (por qué NO es un simple substring):
  - La contención libre tiene solución degenerada: devolver TODO el documento da recall 100%.
    → se mide recall JUNTO al presupuesto de ventana (chars) y la precisión de región.
  - El gold se modela como OFFSETS (no substring frágil): mata NBSP, marcadores de nota `42.8%⁽¹⁾`,
    guiones suaves, comas en números. Se guarda el string verbatim y se RE-ANCLA a offsets al cargar.
  - Un hecho es un conjunto de spans REQUERIDOS (AND) con ALTERNATIVAS (OR): el nombre del cliente y
    el % suelen vivir en spans distintos; y hay divulgaciones alternativas válidas (top-ten O top-three).
  - El PERÍODO importa: una ventana con el pasaje del período equivocado (42.8% 6m vs otro 3m) es HIT
    por contención y respuesta FALSA → cada caso lleva `period` y el span es el del período correcto.
  - answerability ⊥ location: si el % no está escrito y hay que calcularlo (DERIVABLE) o vive en una
    tabla (TABLE_ONLY), NO es un miss de retrieval → se reporta aparte, no se tunea regex contra eso.
  - El negativo EXPLÍCITO ("no customer accounted for more than 10%") SE QUEDA en el denominador: es el
    mejor target para medir FALSOS POSITIVOS (un retriever que siempre devuelve algo se ve espectacular
    en un set sin negativos).
  - Causa del miss > hit-rate agregado: A (ningún anchor cerca) · B (anchor cerca pero la ventana no
    cubre el span) · C (la región la tiró el cap de max_regs — ranker sin score) · D (perdido en la
    extracción HTML→texto) · E (en otro documento = cobertura). A/B/C/D tienen arreglos DISTINTOS.

Fixture = BYTES CRUDOS del filing (`data/gold/corpus/<TICKER>_<accession>.html`) + su sha. El
extractor HTML→texto también está bajo test → se congela el crudo y se EXTRAE en runtime (así una
mejora del extractor puede arreglar/romper retrieval y se ve). Determinista y offline igual.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from backend.nucleo import retrieval
from backend.nucleo.fact_keys import FACT_KEYS

CORPUS_DIR = Path(__file__).resolve().parents[2] / "data" / "gold" / "corpus"

# --- eje LOCATION: dónde vive la evidencia (mide cobertura de ingesta) ---
PRIMARY = "PRIMARY"          # 10-Q/10-K primary → el retrieval DEBE encontrarlo
EXHIBIT = "EXHIBIT"          # Ex-10/Ex-99 de la misma accession
EIGHTK = "EIGHTK"            # 8-K
OTHER_DOC = "OTHER_DOC"      # otra accession/form

# --- eje ANSWERABILITY: si la tarea es SIQUIERA un problema de retrieval ---
STATED_SINGLE = "STATED_SINGLE"   # respuesta en un span de prosa
STATED_MULTI = "STATED_MULTI"     # respuesta compuesta (nombre + % + período en spans distintos)
TABLE_ONLY = "TABLE_ONLY"         # solo en una tabla → fix = extracción tabla-aware, no anchors
DERIVABLE = "DERIVABLE"           # hay que CALCULAR (rev cliente / total) → no hay span, no es retrieval
AMBIGUOUS = "AMBIGUOUS"           # dos candidatos con respuestas distintas → label dudoso
NOT_DISCLOSED = "NOT_DISCLOSED"   # negativo EXPLÍCITO localizable ("no customer > 10%") → cuenta

# answerability que SÍ es un problema de retrieval medible (entra al denominador)
_EVALUABLE_ANS = {STATED_SINGLE, STATED_MULTI, NOT_DISCLOSED}


@dataclass
class GoldCase:
    """Un caso = (accession, fact_key, período/scope). Un mismo filing tiene cifra actual,
    comparativa y YTD → el case_id incluye el período para no confundir HIT de período equivocado."""
    ticker: str
    accession: str
    fact_key: str
    location: str
    answerability: str
    gold_answer: object
    # OR-de-AND: lista de ALTERNATIVAS; cada alternativa es una lista de spans REQUERIDOS (verbatim,
    # tal como aparecen en el texto extraído/limpiado). HIT = alguna alternativa 100% cubierta.
    evidence: list[list[str]] = field(default_factory=list)
    period: str | None = None
    distractors: list[str] = field(default_factory=list)  # plausibles-pero-falsos (período/cifra errada)
    labeler_confidence: str = "HIGH"                       # HIGH | LOW (LOW → doble etiquetado)
    split: str = "dev"                                     # dev | holdout (por EMISOR, no por item)
    note: str = ""

    @property
    def case_id(self) -> str:
        return f"{self.ticker}:{self.fact_key}:{self.period or '-'}"


def cargar_corpus(caso: GoldCase) -> str | None:
    """Lee el HTML CRUDO congelado y lo extrae en runtime (mismo `_limpiar` que el pipeline).
    Así el extractor queda bajo test. None si no hay fixture."""
    p = CORPUS_DIR / f"{caso.ticker.upper()}_{caso.accession}.html"
    if not p.exists():
        return None
    return retrieval._limpiar(p.read_text(encoding="utf-8"))


def _buscar(texto: str, span: str) -> int | None:
    """Offset del span en el texto (case-insensitive fallback). None si no está → miss tipo D."""
    i = texto.find(span)
    if i >= 0:
        return i
    j = texto.lower().find(span.lower())     # ASCII de filings → largos alineados
    return j if j >= 0 else None


def _cubre(reg: tuple[int, int], span: tuple[int, int]) -> bool:
    return reg[0] <= span[0] and span[1] <= reg[1]


def _solapa(reg: tuple[int, int], span: tuple[int, int]) -> bool:
    return reg[0] < span[1] and span[0] < reg[1]


@dataclass
class ResultadoRetrieval:
    case_id: str
    ticker: str
    fact_key: str
    location: str
    answerability: str
    evaluable: bool
    hit: bool | None
    motivo: str                 # HIT | MISS_A_NO_ANCHOR | MISS_B_SPAN_TRUNC | MISS_C_CAP | MISS_D_LOST | <no-eval>
    win_chars: int              # presupuesto: chars de la ventana devuelta (recall NO es gratis)
    region_precision: float     # fracción de las ≤max_regs regiones que contienen evidencia gold
    n_regiones: int
    distractor_en_ventana: bool # la ventana trae un pasaje plausible-pero-falso (señal de riesgo LLM)
    split: str


def _causa_miss(alt_offs: list[tuple[int, int]], capadas, sincap, pos, texto, *, w: int) -> str:
    """Diagnostica por qué NO se cubrió el mejor alternativo. Orden C→B→A (IA2)."""
    for span in alt_offs:
        if any(_cubre(r, span) for r in capadas):
            continue                                     # este span sí está → no es el culpable
        if any(_cubre(r, span) for r in sincap):
            return "MISS_C_CAP"                           # sin_cap lo cubre → lo tiró el cap de max_regs
        if any(_solapa(r, span) for r in sincap):
            return "MISS_B_SPAN_TRUNC"                    # hay región cerca pero la ventana no alcanza
        if not any(span[0] - (w * 3) <= p <= span[1] for p in pos):
            return "MISS_A_NO_ANCHOR"                     # ningún anchor matcheó cerca (vocabulario)
    return "MISS_A_NO_ANCHOR"


def medir_caso(caso: GoldCase) -> ResultadoRetrieval:
    """Mide el retrieval de UN caso contra el corpus congelado. Sin red, sin LLM.

    Solo son EVALUABLES los PRIMARY con answerability de retrieval (STATED_*/NOT_DISCLOSED). Los
    DERIVABLE/TABLE_ONLY/AMBIGUOUS/EXHIBIT/… se reportan aparte (no son fallas de retrieval)."""
    base = dict(case_id=caso.case_id, ticker=caso.ticker, fact_key=caso.fact_key,
                location=caso.location, answerability=caso.answerability, split=caso.split)

    def no_eval(motivo: str) -> ResultadoRetrieval:
        return ResultadoRetrieval(**base, evaluable=False, hit=None, motivo=motivo,
                                  win_chars=0, region_precision=0.0, n_regiones=0,
                                  distractor_en_ventana=False)

    if caso.location != PRIMARY:
        return no_eval("COVERAGE_" + caso.location)
    if caso.answerability not in _EVALUABLE_ANS:
        return no_eval(caso.answerability)               # DERIVABLE / TABLE_ONLY / AMBIGUOUS
    texto = cargar_corpus(caso)
    if texto is None:
        return no_eval("SIN_FIXTURE")
    if not caso.evidence:
        return no_eval("SIN_LABEL")

    # re-anclar cada span verbatim a offsets sobre el texto extraído en runtime
    alts: list[list[tuple[int, int] | None]] = []
    for alt in caso.evidence:
        alts.append([(off, off + len(s)) if (off := _buscar(texto, s)) is not None else None
                     for s in alt])
    # si NINGUNA alternativa quedó completa → el verbatim se perdió en la extracción (D) o drift
    if all(any(o is None for o in alt) for alt in alts):
        return ResultadoRetrieval(**base, evaluable=True, hit=False, motivo="MISS_D_LOST",
                                  win_chars=0, region_precision=0.0, n_regiones=0,
                                  distractor_en_ventana=False)

    spec = next((s for s in FACT_KEYS if s.fact_key == caso.fact_key), None)
    anchors = spec.anchors if spec else []
    capadas, sincap, pos = analisis_regiones(texto, anchors)
    win_chars = sum(min(e, len(texto)) - s for s, e in capadas)

    # HIT = alguna alternativa (completa) con TODOS sus spans cubiertos por las regiones capadas
    hit, mejor_alt = False, None
    for alt in alts:
        if any(o is None for o in alt):
            continue
        if mejor_alt is None:
            mejor_alt = alt                              # 1ª alternativa completa = candidata a diagnóstico
        if all(any(_cubre(r, span) for r in capadas) for span in alt):
            hit, mejor_alt = True, alt
            break

    # precisión de región: cuántas de las capadas contienen ALGÚN span gold
    todos = [span for alt in alts for span in alt if span is not None]
    rel = sum(1 for r in capadas if any(_cubre(r, span) for span in todos))
    region_precision = rel / len(capadas) if capadas else 0.0

    dist_offs = [_buscar(texto, d) for d in caso.distractors]
    distractor_en_ventana = any(off is not None and any(s <= off < e for s, e in capadas)
                                for off in dist_offs)

    if hit:
        motivo = "HIT"
    elif not capadas:
        motivo = "MISS_A_NO_ANCHOR"
    else:
        alt_offs = mejor_alt or todos
        motivo = _causa_miss([s for s in alt_offs if s is not None], capadas, sincap, pos, texto, w=550)

    return ResultadoRetrieval(**base, evaluable=True, hit=hit, motivo=motivo, win_chars=win_chars,
                              region_precision=region_precision, n_regiones=len(capadas),
                              distractor_en_ventana=distractor_en_ventana)


def analisis_regiones(texto: str, anchors: list[str]):
    """Wrapper perezoso a `analisis.construir_regiones` (import diferido: analisis importa pesado)."""
    from backend.nucleo.analisis import construir_regiones
    return construir_regiones(texto, anchors)


# ---------------------------------------------------------------------------
# GOLD SET — set HÍBRIDO v1 (doc 32): concentración compuesta + demanda_realizada (caso AAOI)
# + no_customer_over_10pct (negativo, mide FP) + respaldo_backlog (diversidad tabular).
# Cada caso etiquetado A MANO contra el filing real. Empieza por AAOI (vertical slice) y se amplía
# a ~8 nombres difíciles (5 dev / 3 holdout) + ~10 random (regression), doc 32 §5.
# ---------------------------------------------------------------------------
GOLD: list[GoldCase] = [
    # ---- AAOI (dev) — EL caso motivador ------------------------------------------------------
    # Digicomm = 42.8% de revenue consolidado (6m): demanda REALIZADA de cliente nombrado, STATED.
    # El anchor `revenue from` (singular) no matchea "revenueS from" → miss tipo A esperado.
    GoldCase(
        ticker="AAOI", accession="0001437749-26-026278", fact_key="demanda_realizada",
        location=PRIMARY, answerability=STATED_SINGLE, gold_answer=True, period="6mo-2026-06-30",
        evidence=[["revenues from Digicomm were approximately $147.0 million, representing "
                   "approximately 42.8% of consolidated revenues"]],
        distractors=["211.0 million was due from Digicomm"],  # cuenta a cobrar, NO revenue reconocido
        split="dev",
        note="Cliente nombrado con revenue reconocido (42.8%). Distractor = receivable.",
    ),
    GoldCase(
        ticker="AAOI", accession="0001437749-26-026278", fact_key="customer_concentration_pct",
        location=PRIMARY, answerability=STATED_SINGLE, gold_answer=0.99, period="3mo-2026-06-30",
        evidence=[["our top ten customers represented 99 % and 98 % of our revenue"]],
        split="dev",
        note="Fracción más severa (top-ten 99%), no la de Digicomm sola.",
    ),
    # ---- LEU / Centrus (dev) -----------------------------------------------------------------
    # Backlog contratado STATED y limpio (RPO $0.8B). Buen target positivo de respaldo_backlog.
    GoldCase(
        ticker="LEU", accession="0001628280-26-053863", fact_key="respaldo_backlog",
        location=PRIMARY, answerability=STATED_SINGLE, gold_answer=True, period="asof-2026-06-30",
        evidence=[["total remaining performance obligations were approximately $ 0.8 billion "
                   "and $ 0.6 billion as of June 30, 2026"]],
        split="dev", note="RPO agregado contratado, prosa. Extiende a 2030.",
    ),
    # Concentración de clientes: DERIVABLE — divulga DÓLARES ($78.9M, $39.1M) pero NO el %. Hay que
    # calcular contra el total → NO es un problema de retrieval (ejemplo canónico de la categoría).
    GoldCase(
        ticker="LEU", accession="0001628280-26-053863", fact_key="customer_concentration_pct",
        location=PRIMARY, answerability=DERIVABLE, gold_answer=None, period="3mo-2026-06-30",
        note="Dos clientes $78.9M y $39.1M; el % no está escrito → derivable, no retrieval.",
    ),
    # ---- SMR / NuScale (dev) — period-trap + related-party -----------------------------------
    # Fluor 92%/69% es del período COMPARATIVO 2025; en 2026 "no revenue was earned from Fluor".
    # Y Fluor es la MATRIZ (related party). Una ventana que trae el 92% de 2025 sería HIT de período
    # equivocado. Label LOW-confidence a propósito.
    GoldCase(
        ticker="SMR", accession="0001822966-26-000085", fact_key="customer_concentration_pct",
        location=PRIMARY, answerability=STATED_SINGLE, gold_answer=0.92, period="3mo-2025-comparativo",
        evidence=[["Fluor accounted for $ 7,431 and $ 14,700 , respectively, or 92 % and 69 %"]],
        labeler_confidence="LOW", split="dev",
        note="Related-party (matriz) + período comparativo; 2026 actual ~0. Trampa de período.",
    ),
    # ---- ASTS (dev) — cliente genérico / non-core --------------------------------------------
    # Revenue de venta de equipos a "MNOs" (categoría, NO nombrado) y "not recognized any revenues
    # from the SpaceMobile Service" (core). No hay cliente nombrado con revenue → AMBIGUOUS de tarea.
    GoldCase(
        ticker="ASTS", accession="0001193125-26-342550", fact_key="demanda_realizada",
        location=PRIMARY, answerability=AMBIGUOUS, gold_answer=False, period="6mo-2026-06-30",
        note="MNOs = categoría genérica no nombrada; core (SpaceMobile) sin revenue. No es retrieval.",
    ),
    # ---- TER / Teradyne (dev) — concentración cualitativa ------------------------------------
    # "concentrated with a limited number of significant customers" — sin número en prosa → no hay
    # span de % que recuperar. AMBIGUOUS/no-stated (vara estricta correcta: TER no escala tier).
    GoldCase(
        ticker="TER", accession="0001193125-26-327715", fact_key="customer_concentration_pct",
        location=PRIMARY, answerability=AMBIGUOUS, gold_answer=None, period="3mo-2026-06-30",
        note="Concentración cualitativa ('limited number of significant customers'), sin %.",
    ),
    # ---- OKTA (holdout) ----------------------------------------------------------------------
    # Backlog STATED (RPO no cancelable). NO divulga concentración de clientes (SaaS de mercado amplio).
    GoldCase(
        ticker="OKTA", accession="0001660134-26-000051", fact_key="respaldo_backlog",
        location=PRIMARY, answerability=STATED_SINGLE, gold_answer=True, period="asof-2026-04-30",
        evidence=[["RPO represent all future, non-cancelable, contracted revenue under our "
                   "subscription contracts with customers that has not yet been recognized"]],
        split="holdout", note="RPO no cancelable, prosa. Backlog SaaS.",
    ),
    # ---- TENB / Tenable (holdout) ------------------------------------------------------------
    # Concentración de cliente STATED: un distribuidor = 30% de revenue (3m y 6m 2026). Limpio.
    GoldCase(
        ticker="TENB", accession="0001660280-26-000035", fact_key="customer_concentration_pct",
        location=PRIMARY, answerability=STATED_SINGLE, gold_answer=0.30, period="3mo-2026-06-30",
        evidence=[["One of our distributors accounted for 30 % of revenue in the three and "
                   "six months ended June 30, 2026"]],
        split="holdout", note="Distribuidor 30% de revenue. Concentración por canal.",
    ),
    GoldCase(
        ticker="TENB", accession="0001660280-26-000035", fact_key="respaldo_backlog",
        location=PRIMARY, answerability=STATED_SINGLE, gold_answer=True, period="asof-2026-06-30",
        evidence=[["future estimated revenue related to unsatisfied performance obligations"]],
        split="holdout", note="RPO $1.026B (tabla); acá se ancla el header en prosa.",
    ),
    # ---- RKLB / Rocket Lab (holdout) — con distractor de métrica -----------------------------
    # Cliente gubernamental = 42% del revenue (6m 2026), STATED en dos spans (label + valor). El
    # distractor "MDA Corporation 11 %" es concentración de CUENTAS POR COBRAR, no de revenue.
    GoldCase(
        ticker="RKLB", accession="0001819994-26-000062", fact_key="customer_concentration_pct",
        location=PRIMARY, answerability=STATED_MULTI, gold_answer=0.42, period="6mo-2026-06-30",
        evidence=[["customer that accounted for 10% or more of the total revenue, was",
                   "Government customer 42 %"]],
        distractors=["MDA Corporation 11 %"],  # concentración de AR, métrica equivocada
        split="holdout", note="Cliente gobierno 42% de revenue. Distractor = AR (MDA 11%).",
    ),

    # =========================================================================================
    # SET RANDOM (regression seed de nombres NORMALES, split="random") — NO se tunean anchors con
    # estos. Objetivo: confirmar que recall/extracción GENERALIZAN fuera de los casos difíciles
    # (guard anti-sobreajuste, IA2). Targets STATED limpios + 2 no-evaluables de control.
    # =========================================================================================
    GoldCase(
        ticker="NABL", accession="0001834488-26-000047", fact_key="respaldo_backlog",
        location=PRIMARY, answerability=STATED_SINGLE, gold_answer=True, period="asof-2026-06-30",
        evidence=[["remaining performance obligations as of June 30, 2026"]],
        split="random", note="RPO SaaS ($279.7M). Backlog contratado.",
    ),
    GoldCase(  # negativo EXPLÍCITO (mide falsos positivos): ningún cliente > 5% del ARR
        ticker="S", accession="0001583708-26-000041", fact_key="customer_concentration_pct",
        location=PRIMARY, answerability=STATED_SINGLE, gold_answer=0.05, period="asof-2026-04-30",
        evidence=[["no single end customer accounted for more than 5% of our ARR"]],
        split="random", note="Negativo explícito: sin cliente >5% ARR. Target de falsos positivos.",
    ),
    GoldCase(
        ticker="S", accession="0001583708-26-000041", fact_key="respaldo_backlog",
        location=PRIMARY, answerability=STATED_SINGLE, gold_answer=True, period="asof-2026-04-30",
        evidence=[["remaining performance obligations were $ 1.5 billion"]],
        split="random", note="RPO $1.5B no cancelable.",
    ),
    GoldCase(
        ticker="VRNS", accession="0001628280-26-050630", fact_key="respaldo_backlog",
        location=PRIMARY, answerability=STATED_SINGLE, gold_answer=True, period="asof-2026-06-30",
        evidence=[["remaining performance obligations were $ 1,084,497 as of June 30, 2026"]],
        split="random", note="RPO $1.08B contratado.",
    ),
    GoldCase(  # concentración AGREGADA top-N (spec: sumar clientes >10%): A 40% + B 32% + C 15% = 87%
        ticker="MP", accession="0001801368-26-000048", fact_key="customer_concentration_pct",
        location=PRIMARY, answerability=STATED_MULTI, gold_answer=0.87, period="3mo-2026-06-30",
        evidence=[["Customer A in the Materials segment accounted for 40 % in both applicable periods; "
                   "Customer B in the Materials segment accounted for 32 % and 29 %, respectively; and "
                   "Customer C, primarily in the Magnetics segment, accounted for 15 %"]],
        distractors=["Customer D in the Materials segment accounted for 22 % and 43 %"],  # período 2025
        split="random",
        note="Agregado top-N = 40+32+15 = 87%. (Reveló error de mi label previo 0.40; el extractor sumó bien.)",
    ),
    GoldCase(  # concentración top-N agregada
        ticker="CLS", accession="0001030894-26-000044", fact_key="customer_concentration_pct",
        location=PRIMARY, answerability=STATED_SINGLE, gold_answer=0.83, period="3mo-2026-06-30",
        evidence=[["our top 10 customers represented 83% of total revenue for Q2 2026 and 1H 2026"]],
        split="random", note="Top-10 = 83% del revenue.",
    ),
    GoldCase(
        ticker="BWXT", accession="0001486957-26-000042", fact_key="respaldo_backlog",
        location=PRIMARY, answerability=STATED_SINGLE, gold_answer=True, period="asof-2026-06-30",
        evidence=[["remaining performance obligations were $8,398.1 million"]],
        split="random", note="RPO $8.4B (contratado, awarded+in progress). Backlog fuerte.",
    ),
    # --- no-evaluables de control (categorías answerability) ---
    GoldCase(  # el % vive SOLO en tabla → fix = extracción tabla-aware, no anchors
        ticker="VCYT", accession="0001384101-26-000044", fact_key="customer_concentration_pct",
        location=PRIMARY, answerability=TABLE_ONLY, gold_answer=None, period="3mo-2026-06-30",
        split="random", note="Payers >10% en tabla; sin % en prosa.",
    ),
    GoldCase(  # concentración a nivel SEGMENTO + categoría ("large utility customers") → ambiguo
        ticker="BWXT", accession="0001486957-26-000042", fact_key="customer_concentration_pct",
        location=PRIMARY, answerability=AMBIGUOUS, gold_answer=None, period="3mo-2026-06-30",
        split="random", note="'large utility customers' 54% del SEGMENTO Commercial, no del total.",
    ),
]
