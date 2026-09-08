"""Runner del backtest — doc 03 prerrequisito go-live.

Corre el Analista sobre el dataset de 10 empresas (5 winners + 5 losers) y
compara el resultado contra outcomes esperados. Gate: ≥8/10 correctamente
clasificados.

Modos:
- mock=True  → lee scores de mock_scores.yaml, **no llama a LLM** (gasto $0).
  Útil para iterar sobre thresholds y lógica de clasificación.
- mock=False → ejecuta el Analista real con Claude Opus 4.7. Cuesta ~$3.50.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from backend.agents.analista_writer import estado_sugerido_por_score
from backend.database import session_scope
from backend.models import EstadoFicha, Ficha
from backend.services.calculators import calculate_score_ponderado
from backend.utils import get_logger, utcnow

log = get_logger(__name__)

BACKTEST_DIR = Path(__file__).resolve().parent
DATASET_FILE = BACKTEST_DIR / "dataset.yaml"
MOCK_SCORES_FILE = BACKTEST_DIR / "mock_scores.yaml"
RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "backtests"

# Criterio go-live
PASS_RATE_MIN = 0.8
MIN_WINNERS_CORRECT = 4
MIN_LOSERS_CORRECT = 4


@dataclass
class TickerResult:
    ticker: str
    outcome_esperado: str  # winner | loser
    score_resultante: float | None = None
    nivel_r_resultante: str | None = None
    estado_sugerido: str | None = None
    correcto: bool = False
    motivo_fail: str | None = None
    rationale_esperado: str = ""
    expected_min_score: float | None = None
    expected_max_score: float | None = None
    expected_estados_ok: list[str] = field(default_factory=list)
    mock: bool = False
    error: str | None = None


@dataclass
class BacktestReport:
    timestamp: str
    mock: bool
    total: int
    correctos: int
    pass_rate: float
    winners_correct: int
    winners_total: int
    losers_correct: int
    losers_total: int
    gate_passed: bool
    gate_razones: list[str] = field(default_factory=list)
    resultados: list[TickerResult] = field(default_factory=list)
    cost_usd_total: float = 0.0


# ---------- Dataset loading ----------

def load_dataset() -> list[dict]:
    data = yaml.safe_load(DATASET_FILE.read_text(encoding="utf-8"))
    return data or []


def load_mock_scores() -> dict:
    if not MOCK_SCORES_FILE.exists():
        return {}
    return yaml.safe_load(MOCK_SCORES_FILE.read_text(encoding="utf-8")) or {}


# ---------- Helpers ----------

def _ensure_ficha(ticker: str, entry: dict) -> None:
    """Crea la ficha si no existe — el Analista requiere ficha previa."""
    with session_scope() as s:
        existe = s.query(Ficha).filter_by(ticker=ticker).first()
        if existe is None:
            s.add(Ficha(
                ticker=ticker,
                nombre=f"{ticker} (backtest)",
                sector=entry.get("sector") or "AI infra",
                driver_macro=entry.get("driver_macro"),
                origen="Backtest",
                estado=EstadoFicha.CANDIDATA.value,
                version_tesis_macro="v1.0",
                cambios_score=[],
                cambios_estado=[{
                    "timestamp": utcnow().isoformat(),
                    "estado_anterior": None,
                    "estado_nuevo": EstadoFicha.CANDIDATA.value,
                    "motivo": "backtest dataset intake",
                }],
            ))


def _evaluar_resultado(outcome: str, score: float | None, estado: str | None,
                      expected_min_score: float | None = None,
                      expected_max_score: float | None = None,
                      expected_estados_ok: list[str] | None = None) -> tuple[bool, str | None]:
    """Determina si el resultado clasificó correctamente la empresa."""
    if score is None or estado is None:
        return False, "sin score/estado (Analista fallo)"

    if outcome == "winner":
        if expected_min_score is not None and score < expected_min_score:
            return False, f"score {score} < mínimo esperado {expected_min_score}"
        if expected_estados_ok and estado not in expected_estados_ok:
            return False, f"estado {estado!r} no en {expected_estados_ok}"
        return True, None

    if outcome == "loser":
        if expected_max_score is not None and score > expected_max_score:
            return False, f"score {score} > máximo esperado {expected_max_score}"
        if expected_estados_ok and estado not in expected_estados_ok:
            return False, f"estado {estado!r} no en {expected_estados_ok}"
        return True, None

    return False, f"outcome {outcome!r} no reconocido"


# ---------- Run backtest ----------

def run_backtest(mock: bool = True, tickers_filter: list[str] | None = None,
                 persistir: bool = True, reuse_persisted: bool = False) -> BacktestReport:
    """Ejecuta backtest sobre dataset.

    Args:
        mock: usar scores sintéticos sin LLM.
        reuse_persisted: no llama LLM; lee el score ya persistido en la ficha
            (útil para recalibrar thresholds sin re-analizar).
    """
    dataset = load_dataset()
    if tickers_filter:
        tickers_up = {t.upper() for t in tickers_filter}
        dataset = [e for e in dataset if e["ticker"].upper() in tickers_up]

    log.info("backtest — iniciando mock=%s reuse=%s tickers=%d", mock, reuse_persisted, len(dataset))

    mock_scores = load_mock_scores() if mock else {}

    resultados: list[TickerResult] = []
    cost_total = 0.0

    for entry in dataset:
        ticker = entry["ticker"].upper()
        log.info("backtest — procesando %s (%s)", ticker, entry["outcome"])

        r = TickerResult(
            ticker=ticker,
            outcome_esperado=entry["outcome"],
            rationale_esperado=entry.get("rationale", "").strip(),
            expected_min_score=entry.get("expected_min_score"),
            expected_max_score=entry.get("expected_max_score"),
            expected_estados_ok=entry.get("expected_estados_ok", []),
            mock=mock,
        )

        try:
            _ensure_ficha(ticker, entry)

            if reuse_persisted:
                # Leer el score y estado ya persistido en la ficha (no llama LLM)
                with session_scope() as s:
                    f = s.query(Ficha).filter_by(ticker=ticker).first()
                    if f is None or f.score_vigente is None:
                        r.error = "ficha sin score previo — necesita análisis primero"
                        resultados.append(r)
                        continue
                    r.score_resultante = f.score_vigente
                    r.nivel_r_resultante = f.nivel_r
                    r.estado_sugerido = f.estado

            elif mock:
                # Usar scores sintéticos
                ms = mock_scores.get(ticker)
                if ms is None:
                    r.error = "mock_scores.yaml no tiene entrada para este ticker"
                    resultados.append(r)
                    continue
                criterios_raw = ms.get("criterios", {})
                scores_dict = {int(k): float(v) for k, v in criterios_raw.items()}
                score = calculate_score_ponderado(scores_dict)
                r.score_resultante = score
                r.nivel_r_resultante = ms.get("nivel_r")
                r.estado_sugerido = estado_sugerido_por_score(score, EstadoFicha.CANDIDATA.value)

            else:
                # Real: correr Analista
                from backend.agents.analista import ejecutar_analisis
                from backend.agents.analista_writer import escribir_ficha

                result = ejecutar_analisis(ticker, dry_run=False)
                output = result["output"]
                context = result["context"]
                llm_md = result["llm_metadata"]
                cost_total += llm_md.get("cost_usd", 0) or 0

                precio = context.get("precio_actual")
                write_result = escribir_ficha(
                    ticker=ticker,
                    output=output,
                    context_dict=context,
                    precio_actual=precio,
                )
                r.score_resultante = write_result.score_nuevo
                r.nivel_r_resultante = output.get("nivel_r")
                r.estado_sugerido = write_result.estado_sugerido

            correcto, motivo = _evaluar_resultado(
                r.outcome_esperado, r.score_resultante, r.estado_sugerido,
                r.expected_min_score, r.expected_max_score, r.expected_estados_ok,
            )
            r.correcto = correcto
            r.motivo_fail = motivo

        except Exception as e:  # noqa: BLE001
            r.error = f"{type(e).__name__}: {e}"
            log.exception("backtest — fallo en %s", ticker)

        resultados.append(r)

    # Agregación
    winners = [r for r in resultados if r.outcome_esperado == "winner"]
    losers = [r for r in resultados if r.outcome_esperado == "loser"]
    winners_ok = [r for r in winners if r.correcto]
    losers_ok = [r for r in losers if r.correcto]
    correctos = len(winners_ok) + len(losers_ok)
    total = len(resultados)
    pass_rate = correctos / total if total > 0 else 0

    gate_razones: list[str] = []
    if pass_rate < PASS_RATE_MIN:
        gate_razones.append(f"pass rate {pass_rate*100:.1f}% < {PASS_RATE_MIN*100:.0f}%")
    if len(winners_ok) < MIN_WINNERS_CORRECT:
        gate_razones.append(f"solo {len(winners_ok)}/{MIN_WINNERS_CORRECT} winners identificados")
    if len(losers_ok) < MIN_LOSERS_CORRECT:
        gate_razones.append(f"solo {len(losers_ok)}/{MIN_LOSERS_CORRECT} losers rechazados")

    gate_passed = len(gate_razones) == 0

    report = BacktestReport(
        timestamp=utcnow().isoformat(),
        mock=mock,
        total=total,
        correctos=correctos,
        pass_rate=round(pass_rate, 3),
        winners_correct=len(winners_ok),
        winners_total=len(winners),
        losers_correct=len(losers_ok),
        losers_total=len(losers),
        gate_passed=gate_passed,
        gate_razones=gate_razones,
        resultados=resultados,
        cost_usd_total=round(cost_total, 4),
    )

    log.info(
        "backtest — terminado correctos=%d/%d pass_rate=%.2f%% gate=%s cost=$%.2f",
        correctos, total, pass_rate * 100, "PASS" if gate_passed else "FAIL", cost_total,
    )

    if persistir:
        _persistir_report(report)

    return report


# ---------- Persistencia ----------

def _persistir_report(report: BacktestReport) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = report.timestamp.replace(":", "").replace("-", "")[:15]
    fn = RESULTS_DIR / f"backtest_{ts}_{'mock' if report.mock else 'real'}.json"
    data = asdict(report)
    data["resultados"] = [asdict(r) for r in report.resultados]
    fn.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # Simbolico: último reporte
    latest = RESULTS_DIR / f"latest_{'mock' if report.mock else 'real'}.json"
    latest.write_text(json.dumps(data, indent=2), encoding="utf-8")

    log.info("backtest — reporte guardado en %s", fn)
    return fn


def load_latest_report(mock: bool | None = None) -> dict | None:
    """Carga el último reporte persistido. Si mock=None, prefiere real sobre mock."""
    if mock is None:
        for candidate in ("latest_real.json", "latest_mock.json"):
            fn = RESULTS_DIR / candidate
            if fn.exists():
                return json.loads(fn.read_text(encoding="utf-8"))
        return None

    fn = RESULTS_DIR / f"latest_{'mock' if mock else 'real'}.json"
    if not fn.exists():
        return None
    return json.loads(fn.read_text(encoding="utf-8"))
