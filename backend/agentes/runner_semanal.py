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

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from backend.agentes.ips import ContextoTicker, Violacion
from backend.agentes.orquestador import Orquestador, ResultadoSemana
from backend.agentes.orquestador_decision import OrquestadorDecision, ResultadoDecision
from backend.agentes.paper_pm import ResultadoPaper
from backend.agentes.paper_pm import ejecutar as ejecutar_paper
from backend.agentes.pm import PM
from backend.agentes.schemas import Dossier, PMDecision, VerificationReport
from backend.ledger import core

MIN_N_HIT_RATE = 20              # doc 55 §4.8: no inyectar track record con menos de ~20-30 resueltos
_ALERTAS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "alertas_pm_v2.json"


def _fmt_holguras(holguras: list[Violacion]) -> str:
    return "\n".join(f"- {v.regla}: {v.detalle} (holgura {v.holgura:+.3f})" for v in holguras) or "(sin detalle)"


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
    def __init__(self, *, research: Orquestador, pm: PM, decision: OrquestadorDecision,
                 alertas_path: Path | str | None = _ALERTAS_PATH):
        self.research = research
        self.pm = pm
        self.decision = decision          # su `.ledger` es el ledger de decisiones (fuente del hit-rate)
        self.alertas_path = Path(alertas_path) if alertas_path else None   # None → sin persistencia (tests)

    def _cargar_alertas(self) -> list[str]:
        if self.alertas_path and self.alertas_path.exists():
            try:
                return list(json.loads(self.alertas_path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                return []
        return []

    def _guardar_alertas(self, alertas: list[str]) -> None:
        if not self.alertas_path:
            return
        self.alertas_path.parent.mkdir(parents=True, exist_ok=True)
        self.alertas_path.write_text(json.dumps(alertas, ensure_ascii=False), encoding="utf-8")

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
        flags: dict[str, list[str]] = {}
        for d in research.decisiones:
            if d.dossier is None or d.verif is None:
                continue
            tk = d.ticker.upper()
            verifs[tk] = d.verif.veredicto
            if d.verif.flags_supervivencia:
                flags[tk] = list(d.verif.flags_supervivencia)
            if d.hash:
                hashes[tk] = d.hash
            if d.verif.veredicto in ("pass", "review"):          # FAIL no justifica compra/aumento
                dossiers.append((d.dossier, d.verif))

        # D4 (doc 74): clasificación por nombre para la señal de sizing (modo sombra). De la ficha: el techo de
        # hechos usa revenue recurrente (tracción 4) y si hay puente económico (escenarios). fcf/runway → None
        # por ahora (no se plumbea el pack acá; la regla de runway no corre hasta surfacear ese dato).
        from backend.agentes.clasificacion import ClasifTicker
        clasif_por_ticker: dict[str, ClasifTicker] = {}
        for d, _v in dossiers:
            inv = d.invertibilidad
            if inv is None:
                continue
            clasif_por_ticker[d.ticker.upper()] = ClasifTicker(
                analyst_clasif=inv.analyst_classification,
                revenue_recurrente=(inv.traccion_0_4 == 4),
                tiene_puente=bool(d.escenarios))

        # Persistencia Brier (doc 74 D1): snapshot del puente por nombre para puntuar ex-post la P(bull) del
        # analista (¿se materializó al horizonte?) + la implícita como contexto. Lo que mide si Tier B mejoró
        # la OPORTUNIDAD o solo la vistió de números.
        from datetime import timedelta
        from backend.agentes.futuro import Escenario as _EscFut
        from backend.agentes.futuro import probabilidad_implicita_bull as _pimpl
        bull_por_ticker: dict[str, dict] = {}
        for d, _v in dossiers:
            bull = next((e for e in d.escenarios if e.nombre == "bull"), None)
            if bull is None:
                continue
            ctx = contexto.get(d.ticker.upper())
            prob_impl = None
            if ctx is not None and ctx.market_cap:
                escs = [_EscFut(e.nombre, e.metrica_terminal, e.multiplo_salida, e.anios, e.prob)
                        for e in d.escenarios]
                resto = [e for e in escs if e.nombre != "bull"]
                if resto:
                    prob_impl = _pimpl(ctx.market_cap, next(e for e in escs if e.nombre == "bull"), resto,
                                       anios=bull.anios, dilucion_pct=(d.dilucion_esperada_pct or 0.0),
                                       caja_neta_terminal=(d.caja_neta_terminal or 0.0)).p_bull
            bull_por_ticker[d.ticker.upper()] = {
                "prob": bull.prob, "prob_implicita": prob_impl,
                "horizonte_fecha": (hoy + timedelta(days=365 * bull.anios)).isoformat(),
                "escenarios": [{"nombre": e.nombre, "metrica_terminal": e.metrica_terminal,
                                "multiplo_salida": e.multiplo_salida, "anios": e.anios, "prob": e.prob}
                               for e in d.escenarios]}

        # 2. Cartera actual (proyección del ledger fiel) + hit-rate + ops de la semana + alertas previas.
        pesos_actual, caja_pct, _equity = cartera_desde_ledger(session, precios)
        hr = self._hit_rate_resumen()
        ops_previas = self.decision.ledger.sesiones_ops_en_semana(hoy)
        alertas_previas = self._cargar_alertas()
        # ciclo de resolución (doc 74): surfacear predicciones vencidas sin resolver (falsadores + bull) para
        # que el PM sepa que el track record está incompleto. NO se auto-resuelve acá (el Brier se puntúa con
        # resoluciones deliberadas, por evidencia o por la regla de silencio — ver ops/resolucion).
        from backend.agentes.resolucion import pendientes as _pendientes
        _pend = _pendientes(self.decision.ledger, hoy)
        if _pend:
            alertas_previas = alertas_previas + [
                f"{len(_pend)} predicciones vencidas SIN resolver (correr el ciclo de resolución): "
                + ", ".join(f"{p.ticker}[{p.tipo}]" for p in _pend[:5])]

        # 3. PM decide (con las ops ya usadas en la semana para su dry-run y las alertas previas).
        def _pm(feedback: str = ""):
            return self.pm.decidir(dossiers=dossiers, cartera_actual=pesos_actual, caja_actual=caja_pct,
                                   contexto=contexto, memo_macro=memo_txt, hit_rate_resumen=hr,
                                   ops_semana_previas=ops_previas, alertas_previas=alertas_previas,
                                   feedback=feedback)
        decision = _pm()

        # 4. Gate duro del IPS + Auditor + ledger; re-propuesta UNA vez si el gate rechaza aumentos (1d).
        res_dec = self.decision.procesar(
            decision, cartera_actual=pesos_actual, caja_actual=caja_pct, contexto=contexto, ciclo=ciclo,
            hoy=hoy, precios=precios, dossier_hash_por_ticker=hashes, verif_por_ticker=verifs,
            flags_por_ticker=flags, clasif_por_ticker=clasif_por_ticker, bull_por_ticker=bull_por_ticker,
            memo_macro=memo_txt, repropuesta_fn=lambda holg: _pm(feedback=_fmt_holguras(holg)))

        # 5. Paper + persistir alertas para la corrida siguiente (item 5).
        paper = ejecutar_paper(session, res_dec, precios=precios, fecha_fill=hoy, comision=comision)
        self._guardar_alertas(res_dec.alertas)

        return ResultadoRunner(research=research, decision=decision, resultado_decision=res_dec,
                               paper=paper, hit_rate_resumen=hr,
                               dossiers_considerados=[d.ticker for d, _ in dossiers])
