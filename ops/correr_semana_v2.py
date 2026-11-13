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


def _fechas_dossier(cache) -> dict:
    """ticker → fecha del dossier cacheado (para el cursor de eventos del embudo)."""
    return {tk: e.fecha for tk, e in getattr(cache, "_d", {}).items()}


def _posiciones_paper(paper) -> set[str]:
    from backend.ledger import core
    return set(core.proyectar(paper, {})["posiciones"].keys())


def _ultimo_precio_ledger(paper, tk: str) -> float | None:
    """Último precio de fill del ticker en el ledger (ya en USD). Fallback si el feed no responde."""
    from backend.ledger.models import NxFill
    f = paper.query(NxFill).filter(NxFill.ticker == tk).order_by(NxFill.id.desc()).first()
    return float(f.precio) if f else None


def _asegurar_precios_tenencias(paper, precios: dict) -> None:
    """r6 #2: una TENENCIA sin precio vale 0 → subestima el equity y descoloca los tamaños. Asegura que toda
    tenencia tenga precio (en USD): feed primero; si no responde, último precio del ledger (marcado viejo).
    Nunca la deja sin precio (así no se cae de pesos_actual ni se vende a 0)."""
    from backend.ledger import core
    pos = core.proyectar(paper, {})["posiciones"]
    faltan = [tk for tk, p in pos.items() if p.shares > 0 and tk not in precios]
    if not faltan:
        return
    extra = precios_de(recolectar_snapshots(faltan))          # feed → USD
    for tk in faltan:
        if tk in extra:
            precios[tk] = extra[tk]
        else:
            ult = _ultimo_precio_ledger(paper, tk)
            if ult is not None:
                precios[tk] = ult
                print(f"⚠️  {tk}: tenencia sin precio de feed → último del ledger ${ult:.2f} (viejo)")


def _prioridad_cuello_fn(session):
    """prioridad del cuello (0-2) desde nx_*: confirmado=2 · vigilancia=1 · promesa/otro=0. Determinista."""
    from sqlalchemy import select
    from backend.ledger.models import NxEmpresaNodo, NxNodo
    _MAP = {"confirmado": 2, "vigilancia": 1}
    def _fn(ticker: str) -> int:
        fila = session.execute(
            select(NxNodo.estado_confirmacion).join(NxEmpresaNodo, NxEmpresaNodo.nodo_id == NxNodo.id)
            .where(NxEmpresaNodo.ticker == ticker.upper())
            .order_by(NxEmpresaNodo.es_primario.desc(), NxNodo.id)).first()
        return _MAP.get((fila[0] if fila else "").lower(), 0)
    return _fn


def _filtros_embudo(candidatos, ips):
    """Construye los filtros del embudo (doc 76) que usan TANTO el dry-run COMO la corrida real → garantiza
    'dry-run = real'. Devuelve (invertible_fn, gigante_barato_fn, cupo_forzados, cupo_gigantes). Sin LLM:
    market cap/ADV de los snapshots + el z de precio de cada SenalesTriage."""
    from backend.agentes.embudo import gate_invertibilidad
    from backend.agentes.ips import ContextoTicker
    snaps = recolectar_snapshots([t for t, _s, _r in candidatos])
    cap_max = float(ips.cfg.get("market_cap_max_usd", 60e9))
    z_por_tk = {tk.upper(): s.precio_vs_tesis_pct for tk, s, _r in candidatos}

    def _invertible(tk: str) -> bool:
        s = snaps.get(tk.upper())
        ctx = ContextoTicker(market_cap=getattr(s, "market_cap", None) if s else None,
                             adv_usd=getattr(s, "volumen_diario_promedio_30d", None) if s else None)
        return gate_invertibilidad(ctx, ips.cfg)

    def _gigante_barato(tk: str) -> bool:
        s = snaps.get(tk.upper())
        mc = getattr(s, "market_cap", None) if s else None
        z = z_por_tk.get(tk.upper())
        return mc is not None and mc > cap_max and z is not None and z <= -1.5   # gigante que cayó fuerte

    return _invertible, _gigante_barato, int(ips.cfg.get("cupo_forzados", 8)), int(ips.cfg.get("cupo_gigantes", 2))


def _seleccion_oportunidad(*, met: dict, cuellos: dict, posiciones: set, ips):
    """r9 P1 (doc 80 §D): rankea las ficha-less por score de oportunidad + asigna carriles (banca/oportunidad),
    leyendo el store de fichas + el estado del cuello (nx). Determinista, $0. La USAN el dry-run Y el run real
    ('dry-run = real'). Devuelve (sel, scores, n_fichas)."""
    from backend.agentes.ficha_store import StoreFichas
    from backend.agentes.oportunidad import asignar_carriles, candidato_desde_metricas, rankear_oportunidades
    fichas = StoreFichas().todos()
    fichas_zona = {tk: f.latido.zona for tk, f in fichas.items() if f.latido}
    fichas_estado = {tk: f.estado for tk, f in fichas.items()}
    con_ficha = {tk.upper() for tk in fichas}
    hurdle = float(ips.cfg.get("ficha_hurdles", {}).get("satelite", 0.20))
    estados = {}
    try:
        from sqlalchemy import select
        from backend.database import session_scope
        from backend.ledger.models import NxEmpresaNodo, NxNodo
        with session_scope() as s:
            for tk in met:
                fila = s.execute(select(NxNodo.estado_confirmacion)
                                 .join(NxEmpresaNodo, NxEmpresaNodo.nodo_id == NxNodo.id)
                                 .where(NxEmpresaNodo.ticker == tk.upper())
                                 .order_by(NxEmpresaNodo.es_primario.desc(), NxNodo.id)).first()
                if fila:
                    estados[tk.upper()] = fila[0]
    except Exception:  # noqa: BLE001 — sin mapa igual rankea (estado default)
        pass
    cand = [candidato_desde_metricas(tk, cluster=cuellos.get(tk), metricas=m, cuello_estado=estados.get(tk.upper()),
                                     runway_meses=m.get("cash_runway_months"),
                                     dilucion_overhang=bool(m.get("dilucion_overhang")), hurdle=hurdle)
            for tk, m in met.items() if tk.upper() not in con_ficha and tk.upper() not in posiciones]
    scores = rankear_oportunidades(cand)
    sel = asignar_carriles(posiciones=posiciones, fichas_zona=fichas_zona, fichas_estado=fichas_estado,
                           scores=scores, cupo_oportunidad=int(ips.cfg.get("cupo_oportunidad", 4)))
    return sel, scores, len(fichas)


def _dry_run_oportunidad(*, met: dict, cuellos: dict, posiciones: set, ips) -> None:
    sel, scores, n_fichas = _seleccion_oportunidad(met=met, cuellos=cuellos, posiciones=posiciones, ips=ips)
    print("\n=== PRIORIZACIÓN POR OPORTUNIDAD (r9 P1, doc 80 §D) ===")
    print(f"fichas vivas: {n_fichas} · BANCA en zona de compra: {sel.banca}")
    print(f"CARRIL OPORTUNIDAD (cupo {int(ips.cfg.get('cupo_oportunidad', 4))}): {sel.oportunidad}")
    print("top score (ficha-less, V=brecha de expectativas · M=momentum · C=cuello · A=supervivencia):")
    for f in [x for x in scores if x.score is not None][:10]:
        print(f"  {f.ticker:8} score={f.score:.3f}  V={f.v if f.v is not None else '—'} "
              f"M={f.m if f.m is not None else '—'} C={f.c:.2f} A={f.a}  [{f.cluster}]")


def _dry_run_universo(candidatos, *, ips, cupo: int, valor=None, posiciones: set | None = None) -> None:
    """Imprime qué se analizaría usando la MISMA función de selección + MISMOS filtros que la corrida real
    (seleccionar_para_deep), SIN llamar a Analista/Bear/PM (r4 #1c). `valor` = (ratios, metricas, cuellos) de
    la señal de valor (r7 §3/§8) → imprime el top-15 más barato por cuello."""
    from backend.agentes.embudo import seleccionar_para_deep
    invertible_fn, gigante_barato_fn, cupo_forzados, cupo_gigantes = _filtros_embudo(candidatos, ips)
    cupo_op = int(ips.cfg.get("cupo_oportunidad", 4))
    sel = seleccionar_para_deep(candidatos, cupo=cupo,
                                dias_earnings=int(ips.cfg.get("dias_earnings_proximo", 10)),
                                invertible_fn=invertible_fn, cupo_forzados=cupo_forzados,
                                gigante_barato_fn=gigante_barato_fn, cupo_gigantes=cupo_gigantes,
                                eventos_solo_posiciones=True, cupo_oportunidad=cupo_op)   # r9 §D
    n_deep = len(sel["deep"])
    _pos = [t for t, _m in sel['forzados']]
    _op = [t for t, _m in sel.get('oportunidad', [])]
    print("\n=== DRY-RUN --universo (doc 80 §D: eventos solo tenencias + oportunidad; sin gasto LLM) ===")
    print(f"candidatos: {len(candidatos)}")
    print(f"TENENCIAS → deep/refresh ({len(_pos)}): {_pos}")
    print(f"OPORTUNIDAD → deep completo (cupo {cupo_op}, {len(_op)}): {_op}")
    print(f"GIGANTES caídos → ALERTA ({len(sel['gigantes_watch'])}): {[t for t, _ in sel['gigantes_watch']]}")
    print(f"NO INVERTIBLES (fuera del IPS por market cap) ({len(sel['no_invertible'])})")
    print(f"en espera (no-tenencia sin oportunidad — el evento solo movió su score): {len(sel['espera'])}")
    costo = len(_pos) * 0.25 + (len(_op) + len(sel['gigantes_watch'])) * 0.68   # tenencias=refresh, oportunidad=completo
    print(f"→ deeps: {len(_op)} completos + {len(_pos)} refresh de tenencias  ·  costo estimado: ~${costo:.2f}")
    if valor:
        from backend.agentes.embudo import top_por_valor
        ratios, met, cuellos = valor
        top = top_por_valor(ratios, cuellos, met, n=15)
        print("\n=== SEÑAL DE VALOR — top 15 más baratos por cuello (r7 §3; EV/(contratado+revenue)) ===")
        for f in top:
            ev = f["ev"]; rev = f["revenue"]; vc = f["valor_contratado"]
            print(f"  {f['ticker']:8} pct={f['percentil_valor']:.2f}  ratio={f['ratio_valor']}  "
                  f"EV={ev/1e6:,.0f}M  rev={rev/1e6 if rev else 0:,.0f}M  "
                  f"contratado={vc/1e6 if vc else 0:,.0f}M  [{f['cuello']}]")
        _dry_run_oportunidad(met=met, cuellos=cuellos, posiciones=posiciones or set(), ips=ips)


def _contexto_mapa_fn(ticker: str) -> str:
    """Contexto del cuello desde nx_* para el Analista (abre su propia sesión; fail-silent)."""
    try:
        from backend.agentes.universo import contexto_mapa
        from backend.database import session_scope
        with session_scope() as s:
            return contexto_mapa(s, ticker)
    except Exception:  # noqa: BLE001
        return ""


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
    ap.add_argument("--universo", action="store_true",
                    help="armar candidatos desde TODO nx_empresa con señales reales (el embudo decide qué va "
                         "a deep), en vez de forzar los tickers pasados")
    ap.add_argument("--dry-run", action="store_true",
                    help="con --universo: imprime qué se analizaría (forzados/promovidos/saltados + costo) "
                         "SIN gastar en Analista/Bear/PM")
    ap.add_argument("--sin-opus-solo", action="store_true",
                    help="no correr el baseline 'Opus+web solo' de Fase 5 (ahorra ~$0.5-1)")
    ap.add_argument("--sin-valor", action="store_true",
                    help="con --universo: saltear la señal de valor (r7 §3) para una corrida rápida sin "
                         "assemblar la lente de valuación de todo el universo")
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
    # Auditor en modelo DISTINTO del Analista (Opus) → errores descorrelacionados (D5, IA2: así funcionó la
    # triangulación de 3 IAs). Sonnet alcanza para la búsqueda adversarial dirigida por checklist.
    auditor = Auditor(Agente("auditor", m_auditor.PROMPT_VERSION, M_SONNET))

    research = Orquestador(
        triage=triage, analista=analista, bear=bear, macro=macro,
        ledger=ledger_pres,                              # tope mensual persistente / bootstrap (P0.4)
        cache=CacheDossiers(_CACHE_PATH),                # reutilización PERSISTENTE a disco (P0.2b)
        data_pack_fn=lambda tk: ensamblar(tk),
        contexto_fn=_contexto_mapa_fn,                   # contexto del cuello desde nx_* (r3 #5)
    )
    decision = OrquestadorDecision(ips, LedgerDecisiones(), auditor=auditor)
    runner = RunnerSemanal(research=research, pm=pm, decision=decision)

    # --- datos reales ---
    snaps = recolectar_snapshots(tickers)
    precios = precios_de(snaps)
    sin_precio = [t for t in tickers if t not in precios]
    if sin_precio:
        print(f"⚠️  sin precio (se saltean en el paper): {sin_precio}")
    # --universo (r3 #7 / r4 #1b): candidatos desde TODO nx con señales reales + fechas del cache +
    # posiciones del paper + prioridad del cuello del mapa. El Triage/embudo filtra qué va a deep.
    from backend.database import session_scope
    if args.universo:
        from backend.agentes import data_pack as dp
        from backend.agentes.universo import (candidatos_del_universo, cuello_primario,
                                              tickers_universo, valor_del_universo)
        cache = CacheDossiers(_CACHE_PATH)
        _paper_tmp = abrir_paper(capital_inicial=args.capital, fecha=date.today())
        try:
            posiciones = _posiciones_paper(_paper_tmp)
        finally:
            _paper_tmp.close()
        with session_scope() as s_nx:
            # Señal de valor (r7 §3): assembla la lente de valuación por nombre (hits de red) → percentil por
            # cuello, que entra a la prioridad del embudo. Se puede saltear con --sin-valor (corrida rápida).
            valor_pct, valor_met, valor_ratios, valor_cuellos = {}, {}, {}, {}
            if not args.sin_valor:
                tks = tickers_universo(s_nx)
                print(f"calculando señal de valor sobre {len(tks)} nombres (lente de valuación; hits de red)…")
                valor_pct, valor_met, valor_ratios, valor_cuellos = valor_del_universo(
                    tks, pack_fn=lambda tk: dp.ensamblar(tk, as_of=date.today()),
                    cuello_fn=lambda tk: cuello_primario(s_nx, tk))
            candidatos = candidatos_del_universo(
                s_nx, hoy=date.today(), fechas_dossier=_fechas_dossier(cache),
                posiciones=posiciones, prioridad_fn=_prioridad_cuello_fn(s_nx),
                valor_percentiles=valor_pct)
        tickers = [c[0] for c in candidatos]
        print(f"universo: {len(candidatos)} candidatos triageados (posiciones={sorted(posiciones)})")
        # r9 P1 (doc 80 §D): el carril de OPORTUNIDAD manda deep, no solo los eventos. Fuerza los top-N por score
        # ficha-less + la banca en zona de compra a deep (antes del check de dry-run → dry-run = real). El cupo +
        # el ledger de presupuesto (fail-closed) acotan el gasto. Se saltea con --sin-valor (no hay métricas).
        if valor_met:
            sel_op, _sc, _nf = _seleccion_oportunidad(met=valor_met, cuellos=valor_cuellos,
                                                      posiciones=posiciones, ips=ips)
            forzar = {t.upper() for t in (sel_op.oportunidad + sel_op.banca)}
            por_tk = {c[0].upper(): c[1] for c in candidatos}
            for tk in forzar:
                s = por_tk.get(tk)
                if s is not None:
                    s.forzado_oportunidad = True           # r9 §D: carril de OPORTUNIDAD (no evento)
            print(f"OPORTUNIDAD → deep ({len(forzar & set(por_tk))}): {sorted(forzar & set(por_tk))}")
        if args.dry_run:
            _dry_run_universo(candidatos, ips=ips, cupo=args.cupo or 6, posiciones=posiciones,
                              valor=(valor_ratios, valor_met, valor_cuellos) if valor_ratios else None)
            return 0
        snaps = recolectar_snapshots(tickers)
        precios = precios_de(snaps)
    else:
        candidatos = _candidatos(tickers)
    with session_scope() as s_nx:
        contexto = contexto_de(tickers, snaps, session=s_nx)

    # Filtros del embudo (doc 76): los MISMOS que el dry-run → la corrida real no analiza gigantes ni se
    # pasa del tope del carril forzado (si no, el real divergiría del dry-run y gastaría de más).
    inv_fn, gig_fn, cupo_forz, cupo_gig = _filtros_embudo(candidatos, ips)

    # Estacionamiento (r7a #1): sumar precios de los ETFs de parking al feed + meta de conversión (moneda/FX)
    # para el rastro del fill (r7a #4). Sin esto el paper no podría ejecutar los ETFs del residual.
    from backend.agentes.datos_reales import precios_meta_de
    from backend.agentes.estacionamiento import tickers_parking
    _snaps_etf = recolectar_snapshots(sorted(tickers_parking(ips.cfg)))
    precios.update(precios_de(_snaps_etf))
    precios_meta = precios_meta_de({**snaps, **_snaps_etf})

    paper = abrir_paper(capital_inicial=args.capital, fecha=date.today())
    try:
        _asegurar_precios_tenencias(paper, precios)   # r6 #2: tenencias siempre con precio (equity/sizing OK)
        res = runner.correr(candidatos, session=paper, precios=precios, contexto=contexto,
                            hoy=date.today(), cupo_cobertura=args.cupo, bootstrap=args.bootstrap,
                            invertible_fn=inv_fn, cupo_forzados=cupo_forz,
                            gigante_barato_fn=gig_fn, cupo_gigantes=cupo_gig, precios_meta=precios_meta,
                            eventos_solo_posiciones=args.universo, cupo_oportunidad=int(ips.cfg.get("cupo_oportunidad", 4)))
        paper.commit()
        _registrar_sombras(paper, precios, res)      # Fase 5: snapshot pm/ew_pass/ETFs del ciclo
    finally:
        paper.close()

    # Fase 5: baseline "Opus+web solo" (la vara que dice si el COMITÉ agrega). Gasta ~$0.5-1.
    if not args.sin_opus_solo:
        try:
            from backend.agentes.carteras_sombra import LedgerSombras, SnapshotSombra
            from backend.agentes.opus_solo import OpusSolo
            # PARIDAD de gasto (r3 #3): darle al baseline búsquedas proporcionales a lo que corrió el comité
            # (~9 búsquedas por nombre ANALIZADO: 6 Analista + 3 Bear).
            n_analizados = sum(1 for d in res.research.decisiones if d.accion == "analizado")
            max_web = max(6, n_analizados * 9)
            r_os = OpusSolo(Agente("opus_solo", "opus_solo_v1", M_OPUS)).elegir(
                tickers, peso_max=float(ips.cfg.get("peso_max_nombre", 0.20)), max_web=max_web)
            LedgerSombras().registrar(SnapshotSombra(
                fecha=date.today().isoformat(), cartera="opus_solo", pesos=r_os.pesos,
                precios={t: precios[t] for t in r_os.pesos if t in precios}))
            costo = r_os.meta.cost_usd if r_os.meta else 0.0
            print(f"opus_solo (baseline Fase 5, max_web={max_web}): {r_os.pesos}  "
                  f"(${costo:.4f} vs comité ${res.research.gastado_usd:.4f})")
        except Exception as e:  # noqa: BLE001
            print(f"aviso: baseline opus_solo falló: {e}")

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
