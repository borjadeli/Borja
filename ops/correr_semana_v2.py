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
from backend.agentes.orquestador import CacheDossiers, Orquestador, _CACHE_PATH
from backend.agentes.orquestador_decision import OrquestadorDecision
from backend.agentes.pm import PM
from backend.agentes.presupuesto import gastado_mes_usd, ledger_bootstrap, ledger_mensual
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


def _registrar_sombras(paper, precios, res) -> None:
    """Fase 5: registra el snapshot de carteras sombra del ciclo (pm / ew_pass / ETFs). No gasta API; si
    falla no debe tumbar la corrida."""
    try:
        from backend.agentes.carteras_sombra import ETFS_DEFAULT, LedgerSombras
        from backend.ledger import core
        est = core.proyectar(paper, precios)
        eq = est["equity"]
        pm_pesos = ({t: (p.shares * precios.get(t, 0.0)) / eq for t, p in est["posiciones"].items()}
                    if eq > 0 else {})
        pass_nombres = [d.ticker for d in res.research.decisiones
                        if d.verif and d.verif.veredicto == "pass"]
        etf_precios = precios_de(recolectar_snapshots(list(ETFS_DEFAULT.values())))
        LedgerSombras().registrar_ciclo(date.today().isoformat(), pm_pesos=pm_pesos,
                                        pass_nombres=pass_nombres, precios={**precios, **etf_precios})
        print("carteras sombra: snapshot del ciclo registrado")
    except Exception as e:  # noqa: BLE001
        print(f"aviso: no se registraron carteras sombra: {e}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Smoke real del ciclo semanal v2")
    ap.add_argument("tickers", nargs="*", default=["OKLO"], help="nombres a correr (default OKLO)")
    ap.add_argument("--con-macro", action="store_true", help="incluir el memo macro (otro Opus+web)")
    ap.add_argument("--capital", type=float, default=100_000.0, help="capital inicial del paper (1a vez)")
    ap.add_argument("--cupo", type=int, default=0, help="cupo de cobertura: nombres nuevos a promover")
    ap.add_argument("--bootstrap", action="store_true", help="primera pasada: promueve todos los nuevos")
    args = ap.parse_args()
    tickers = [t.upper() for t in (args.tickers or ["OKLO"])]

    ips = IPS.cargar()
    presupuesto_mes = float(ips.cfg.get("presupuesto_usd_mes", 40.0))
    # Bootstrap: tope propio del ips.yaml (separado del mensual); si no, ritmo mensual persistente.
    ledger_pres = (ledger_bootstrap(float(ips.cfg.get("presupuesto_bootstrap_usd", 25.0)))
                   if args.bootstrap else ledger_mensual(presupuesto_mes, date.today()))

    # --- agentes reales (cliente Anthropic real vía services.llm; cada llamada se loguea a llm_calls) ---
    triage = Triage(Agente("triage", m_triage.PROMPT_VERSION, M_HAIKU))
    analista = Analista(Agente("analista", m_analista.PROMPT_VERSION, M_OPUS))
    bear = Bear(Agente("bear", m_bear.PROMPT_VERSION, M_SONNET))
    macro = Macro(Agente("macro", m_macro.PROMPT_VERSION, M_OPUS)) if args.con_macro else None
    pm = PM(Agente("pm", m_pm.PROMPT_VERSION, M_OPUS), ips)
    auditor = Auditor(Agente("auditor", m_auditor.PROMPT_VERSION, M_OPUS))

    research = Orquestador(
        triage=triage, analista=analista, bear=bear, macro=macro,
        ledger=ledger_pres,                              # tope mensual persistente / bootstrap (P0.4)
        cache=CacheDossiers(_CACHE_PATH),                # reutilización PERSISTENTE a disco (P0.2b)
        data_pack_fn=lambda tk: ensamblar(tk),
        contexto_fn=lambda _tk: "",                      # contexto del cuello para el Analista: mejora futura
    )
    decision = OrquestadorDecision(ips, LedgerDecisiones(), auditor=auditor)
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
                            hoy=date.today(), cupo_cobertura=args.cupo, bootstrap=args.bootstrap)
        paper.commit()
        _registrar_sombras(paper, precios, res)      # Fase 5: snapshot de carteras sombra del ciclo
    finally:
        paper.close()

    # --- resumen ---
    print("\n=== SMOKE v2 ===")
    print(f"dossiers considerados (PASS/REVIEW): {res.dossiers_considerados}")
    print(f"gasto research (esta corrida): ${res.research.gastado_usd:.4f}")
    _gm = gastado_mes_usd(date.today())
    print(f"gasto LLM del mes (todos los agentes, llm_calls): "
          f"${(_gm if _gm is not None else 0.0):.4f} / tope ${presupuesto_mes:.0f}"
          + ("  ⚠️ no se pudo leer (fail-closed)" if _gm is None else ""))
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
