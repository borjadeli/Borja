"""Runner semanal (v2 Fase 4, doc 55) — cablea el ciclo completo end-to-end.

research (Macro→Triage→Analista→Bear→Verificador, bajo presupuesto) → **PM** (sizea bajo IPS) →
**orquestador de decisión** (gate IPS + Auditor + ledger) → **paper nuevo** (fills contra el ledger fiel).

Todo inyectable (igual que `orquestador.py`): recibe los agentes ya construidos y los DATOS REALES como
parámetros —`precios`, `contexto` (sector/cuello/market cap/ADV por ticker, de `nx_nodo` + market data),
`session` del ledger fiel del paper—. Así es testeable con stubs y el cableado a datos reales son
adaptadores finos que provee el caller (los armamos junto con el smoke real).

La cartera actual (pesos + caja) se PROYECTA del ledger fiel point-in-time; el hit-rate del PM sale del
ledger de decisiones (se inyecta solo si hay N suficiente, doc 55 §4.8).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from backend.agentes.ips import ContextoTicker
from backend.agentes.orquestador import Orquestador, ResultadoSemana
from backend.agentes.orquestador_decision import OrquestadorDecision, ResultadoDecision
from backend.agentes.paper_pm import ResultadoPaper
from backend.agentes.paper_pm import ejecutar as ejecutar_paper
from backend.agentes.pm import PM
from backend.agentes.schemas import Dossier, PMDecision, VerificationReport
from backend.ledger import core

MIN_N_HIT_RATE = 20              # doc 55 §4.8: no inyectar track record con menos de ~20-30 resueltos


def cartera_desde_ledger(session, precios: dict[str, float]) -> tuple[dict[str, float], float, float]:
    """Proyecta el ledger fiel → (pesos por ticker, fracción en caja, equity). Point-in-time con `precios`."""
    est = core.proyectar(session, precios)
    equity = est["equity"]
    if equity <= 0:
        return {}, 1.0, equity
    pesos = {t: (p.shares * precios.get(t.upper(), 0.0)) / equity for t, p in est["posiciones"].items()}
    return {t: w for t, w in pesos.items() if w > 0}, est["caja"] / equity, equity


@dataclass
class ResultadoRunner:
    research: ResultadoSemana
    decision: PMDecision
    resultado_decision: ResultadoDecision
    paper: ResultadoPaper
    hit_rate_resumen: str
    dossiers_considerados: list[str] = field(default_factory=list)   # PASS/REVIEW que vio el PM


class RunnerSemanal:
    def __init__(self, *, research: Orquestador, pm: PM, decision: OrquestadorDecision):
        self.research = research
        self.pm = pm
        self.decision = decision          # su `.ledger` es el ledger de decisiones (fuente del hit-rate)

    def _hit_rate_resumen(self) -> str:
        m = self.decision.ledger.metricas()
        if m.n_resueltos < MIN_N_HIT_RATE:
            return f"(histórico insuficiente: {m.n_resueltos} falsadores resueltos, se necesitan ≥{MIN_N_HIT_RATE})"
        buckets = " · ".join(f"{b.bucket}: {b.falsados}/{b.n} falsados" for b in m.por_bucket if b.n)
        return (f"Falsadores resueltos: {m.n_resueltos} · Brier={m.brier} · "
                f"hit-rate falsadores={m.hit_rate_falsadores} · por convicción: {buckets}")

    def correr(self, candidatos, *, session, precios: dict[str, float],
               contexto: dict[str, ContextoTicker], memo_macro=None, hoy: date | None = None,
               ciclo: str | None = None, comision: float = 0.0,
               cupo_cobertura: int = 0, bootstrap: bool = False) -> ResultadoRunner:
        hoy = hoy or date.today()
        ciclo = ciclo or hoy.isoformat()

        # 1. Research bajo presupuesto → dossiers verificados por nombre (con cupo de cobertura/bootstrap).
        research = self.research.correr_semana(candidatos, memo_macro=memo_macro, hoy=hoy,
                                               cupo_cobertura=cupo_cobertura, bootstrap=bootstrap)
        memo_txt = research.memo.resumen if research.memo else ""

        dossiers: list[tuple[Dossier, VerificationReport]] = []
        hashes: dict[str, str] = {}
        verifs: dict[str, str] = {}
        for d in research.decisiones:
            if d.dossier is None or d.verif is None:
                continue
            tk = d.ticker.upper()
            verifs[tk] = d.verif.veredicto
            if d.hash:
                hashes[tk] = d.hash
            if d.verif.veredicto in ("pass", "review"):          # FAIL no justifica compra/aumento
                dossiers.append((d.dossier, d.verif))

        # 2. Cartera actual (proyección del ledger fiel) + hit-rate del PM.
        pesos_actual, caja_pct, _equity = cartera_desde_ledger(session, precios)
        hr = self._hit_rate_resumen()

        # 3. PM decide.
        decision = self.pm.decidir(dossiers=dossiers, cartera_actual=pesos_actual, caja_actual=caja_pct,
                                   contexto=contexto, memo_macro=memo_txt, hit_rate_resumen=hr)

        # 4. Gate duro del IPS + Auditor + ledger de decisiones.
        res_dec = self.decision.procesar(decision, cartera_actual=pesos_actual, caja_actual=caja_pct,
                                         contexto=contexto, ciclo=ciclo, precios=precios,
                                         dossier_hash_por_ticker=hashes, verif_por_ticker=verifs,
                                         memo_macro=memo_txt)

        # 5. Paper: ejecuta los fills contra el ledger fiel.
        paper = ejecutar_paper(session, res_dec, precios=precios, fecha_fill=hoy, comision=comision)

        return ResultadoRunner(research=research, decision=decision, resultado_decision=res_dec,
                               paper=paper, hit_rate_resumen=hr,
                               dossiers_considerados=[d.ticker for d, _ in dossiers])
