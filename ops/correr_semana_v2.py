"""Corre un ciclo semanal del PM-IA v2 end-to-end con DATOS REALES (el harness del SMOKE REAL).

Cablea research (Macro→Triage→Analista→Bear→Verificador, bajo presupuesto) → PM (sizea bajo IPS) →
orquestador de decisión (gate IPS + Auditor + ledger) → paper nuevo (fills contra el ledger fiel
`data/paper_v2.db`). Usa precios/market-cap/ADV de market_data y sector/cuello del ledger `nx_*`.

⚠️ GASTA DINERO REAL (llamadas a Opus/Sonnet + web search). Pensado para el smoke sobre pocos nombres.

Uso:
  .venv/bin/python -m ops.correr_semana_v2 OKLO MP RKLB            # 3 nombres, sin macro
  .venv/bin/python -m ops.correr_semana_v2 --con-macro OKLO        # incluye el memo macro (otro Opus+web)
  .venv/bin/python -m ops.correr_semana_v2 --capital 100000 OKLO   # capital inicial del paper (1a vez)
"""
from __future__ import annotations

import argparse
import sys
from datetime import date

from backend.agentes import analista as m_analista
from backend.agentes import auditor as m_auditor
from backend.agentes import bear as m_bear
from backend.agentes import macro as m_macro
from backend.agentes import pm as m_pm
from backend.agentes import triage as m_triage
from backend.agentes.auditor import Auditor
from backend.agentes.analista import Analista
from backend.agentes.base import Agente
from backend.agentes.bear import Bear
from backend.agentes.data_pack import ensamblar
from backend.agentes.datos_reales import abrir_paper, contexto_de, precios_de, recolectar_snapshots
from backend.agentes.ips import IPS
from backend.agentes.ledger_decisiones import LedgerDecisiones
from backend.agentes.macro import Macro
from backend.agentes.orquestador import Orquestador
from backend.agentes.orquestador_decision import OrquestadorDecision
from backend.agentes.pm import PM
from backend.agentes.presupuesto import LedgerPresupuesto
from backend.agentes.runner_semanal import RunnerSemanal
from backend.agentes.triage import SenalesTriage, Triage

# Modelos por rol (doc 53): Opus 5.5 Analista/PM/Auditor/Macro · Sonnet 5.5 Bear · Haiku 5.5 Triage.
M_OPUS, M_SONNET, M_HAIKU = "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"


def _candidatos(tickers: list[str]) -> list[tuple[str, SenalesTriage, str]]:
    """Fuerza research profundo en los nombres del smoke (tiene_evento_fuerte) con 0 hechos nuevos → el
    Triage no gasta LLM; el gasto es el comité por nombre (Analista+Bear+Verificador)."""
    señales = SenalesTriage(dias_desde_dossier=None, hechos_nuevos=0, dias_a_evento=None,
                            precio_vs_tesis_pct=None, tiene_evento_fuerte=True)
    return [(t.upper(), señales, "") for t in tickers]


def main() -> int:
    ap = argparse.ArgumentParser(description="Smoke real del ciclo semanal v2")
    ap.add_argument("tickers", nargs="*", default=["OKLO"], help="nombres a correr (default OKLO)")
    ap.add_argument("--con-macro", action="store_true", help="incluir el memo macro (otro Opus+web)")
    ap.add_argument("--capital", type=float, default=100_000.0, help="capital inicial del paper (1a vez)")
    ap.add_argument("--presupuesto", type=float, default=9.0, help="sobre semanal USD (de los $40/mes)")
    args = ap.parse_args()
    tickers = [t.upper() for t in (args.tickers or ["OKLO"])]

    # --- agentes reales (cliente Anthropic real vía services.llm) ---
    triage = Triage(Agente("triage", m_triage.PROMPT_VERSION, M_HAIKU))
    analista = Analista(Agente("analista", m_analista.PROMPT_VERSION, M_OPUS))
    bear = Bear(Agente("bear", m_bear.PROMPT_VERSION, M_SONNET))
    macro = Macro(Agente("macro", m_macro.PROMPT_VERSION, M_OPUS)) if args.con_macro else None
    pm = PM(Agente("pm", m_pm.PROMPT_VERSION, M_OPUS), IPS.cargar())
    auditor = Auditor(Agente("auditor", m_auditor.PROMPT_VERSION, M_OPUS))

    research = Orquestador(
        triage=triage, analista=analista, bear=bear, macro=macro,
        ledger=LedgerPresupuesto(sobre_semanal=args.presupuesto),
        data_pack_fn=lambda tk: ensamblar(tk),
        contexto_fn=lambda _tk: "",                      # contexto del cuello para el Analista: mejora futura
    )
    decision = OrquestadorDecision(IPS.cargar(), LedgerDecisiones(), auditor=auditor)
    runner = RunnerSemanal(research=research, pm=pm, decision=decision)

    # --- datos reales ---
    snaps = recolectar_snapshots(tickers)
    precios = precios_de(snaps)
    sin_precio = [t for t in tickers if t not in precios]
    if sin_precio:
        print(f"⚠️  sin precio (se saltean en el paper): {sin_precio}")
    from backend.database import session_scope
    with session_scope() as s_nx:
        contexto = contexto_de(tickers, snaps, session=s_nx)

    paper = abrir_paper(capital_inicial=args.capital, fecha=date.today())
    try:
        res = runner.correr(_candidatos(tickers), session=paper, precios=precios, contexto=contexto,
                            hoy=date.today())
        paper.commit()
    finally:
        paper.close()

    # --- resumen ---
    print("\n=== SMOKE v2 ===")
    print(f"dossiers considerados (PASS/REVIEW): {res.dossiers_considerados}")
    print(f"gasto research: ${res.research.gastado_usd:.4f}")
    print(f"decisión del PM: operar={res.decision.operar_ahora} · acciones={len(res.decision.acciones)} "
          f"· clip={res.resultado_decision.clip} · no_action={res.resultado_decision.no_action}")
    if res.resultado_decision.demoradas:
        print(f"demoradas por el auditor: {res.resultado_decision.demoradas}")
    print(f"fills del paper: {res.paper.fills}")
    if res.paper.nota:
        print(f"nota paper: {res.paper.nota}")
    print(f"hit-rate inyectado al PM: {res.hit_rate_resumen}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
