"""Ficha PROFUNDA por empresa — corre el proceso completo y lo imprime LEGIBLE, para VALIDAR el análisis.

    .venv/bin/python -m ops.ficha_profunda LEU RKLB S TER OKTA

Ensambla, por ticker, el análisis end-to-end de la superficie nueva (doc 34): evidencia CITADA → 3 pilares
→ valuación (bull/bear/burden/falsador) → clasificación (arquetipo/route/tier) → DECISIÓN (gate/abstención/
celda/cartera). Es lo que un humano/PM leería. Sirve para contrastar contra el análisis independiente de otra
IA (ver ops/prompt_validacion_externa) y ver si converge. SHADOW: no toca el paper.
"""
from __future__ import annotations

import sys

from backend.database import session_scope
from backend.ingreso.filtro0 import HechosFiltro0, evaluar_filtro0
from backend.nucleo import fact_store as FS
from backend.nucleo import ranking
from backend.nucleo.compilador import _cobertura
from backend.nucleo.hoja_evidencia import hoja
from backend.nucleo.ranking_lexicografico import candidato_desde, estado_decision
from backend.services import market_data
from backend.utils import get_logger

log = get_logger(__name__)


def _m(x, sufijo="M", div=1e6):
    return f"${x/div:,.1f}{sufijo}" if isinstance(x, (int, float)) else "s/d"


def ficha(session, ticker: str) -> None:
    try:
        ev = ranking.evaluar_ticker(session, ticker)
        h = hoja(ticker, session=session)
        snap = FS.snapshot_vigente(session, ticker)
        cob = _cobertura(snap) if snap else 0.0
        sn = market_data.get_price_snapshot(ticker)
        liq = sn.volumen_diario_promedio_30d if sn else None
        c = candidato_desde(ev, h, cobertura=cob, liquidez_adv=liq)
    except Exception as e:  # noqa: BLE001
        print(f"\n### {ticker}: FALLO — {e}"); return

    det = ranking.extraer_deterministas(ticker)
    print("\n" + "═" * 84)
    print(f"  {ticker}  ·  {h.arquetipo}  ·  route={h.route}  ·  stage={h.stage}")
    print("═" * 84)

    # FILTRO 0 — pre-screen barato determinista (¿vale el deep research?). Es el gate del frente.
    crec, marg, rev, deu = (det.get(k) for k in ("crecimiento_headline_yoy", "margen_bruto", "revenue_ttm", "total_debt"))
    f0 = evaluar_filtro0(HechosFiltro0(
        es_prerevenue=bool(rev and rev < 10e6),
        tiene_contrato_vinculante_material=(h.demanda_tier or 0) >= 2,
        tiene_traccion_comercial=(h.demanda_tier or 0) >= 1,
        crecimiento_yoy=(crec / 100.0) if crec is not None else None,
        margen_bruto=(marg / 100.0) if marg is not None else None,
        deuda_sobre_revenue=(deu / rev) if (deu and rev) else None,
        runway_meses=(h.runway_anos * 12) if h.runway_anos is not None else None))
    print(f"  FILTRO 0 (pre-screen barato, sin LLM): {f0.veredicto.upper()} — {f0.motivo}")

    print("  EVIDENCIA (citada, del filing):")
    print(f"    · demanda tier: {h.demanda_tier or 's/d'}"
          + (f'  «{h.demanda_quote[:90]}»' if h.demanda_quote else ""))
    print(f"    · backlog RPO (XBRL): {_m(det.get('rpo'))}  as_of {det.get('rpo_as_of') or 's/d'}")
    print(f"    · revenue TTM: {_m(det.get('revenue_ttm'))} · FCF TTM: {_m(det.get('fcf_ttm'))} · "
          f"caja: {_m(det.get('caja'))} · deuda: {_m(det.get('total_debt'))}")
    print(f"    · cobertura de evidencia: {cob:.0%}")

    # RUTEO (doc 42 §2) — qué gramática de valuación. Se lee del flag que deja hoja.
    rt = next((f.split("ruteo: ")[1] for f in h.flags if f.startswith("ruteo:")), "—")
    print(f"  RUTEO (2 ejes, doc 42): {rt}")

    print("  PILARES (SCORING no-compensatorio — SOLO el veto de supervivencia excluye; doc 39 §2.1):")
    for p in ev.pilares:
        hh = "; ".join(x.get("claim", "") for x in (p.hechos or [])[:2]) or "—"
        veto = "  ⛔VETO-SUPERVIVENCIA" if getattr(p, "es_veto_supervivencia", False) else ""
        print(f"    · {p.nombre:14} {p.banda.name:10} (conf {p.confianza})  {hh}{veto}")

    print("  VALUACIÓN:")
    if h.estado_reverse is not None:
        tp = h.t_star_reverse or {}
        print(f"    · REVERSE-DCF (comercial, r_mkt): estado={h.estado_reverse} · g_D={h.g_D_reverse and f'{h.g_D_reverse:.0%}'} "
              f"· T*(P25/P50/P75)={tp.get('P25')}/{tp.get('P50')}/{tp.get('P75')}")
    else:
        print(f"    · (no comercial → path burden/pre-revenue) · burden(GP): {h.burden_gp if h.burden_gp is not None else '—'} "
              f"· anchor: {h.price_anchor_status}")
    print(f"    · precio ${h.precio} · base ${h.operable and round(h.operable,1)} · "
          f"asimetría: {h.asimetria_operable if h.asimetria_operable is not None else 'N/A'} · FALSADOR: {h.falsador_veredicto}")

    print("  DILUCIÓN / SUPERVIVENCIA:")
    print(f"    · burn_yield: {h.burn_yield and round(h.burn_yield,3)} ({h.banda_dilucion}) · "
          f"runway: {h.runway_anos}a · Δacciones 12m: {h.shares_growth_12m}")

    dec = estado_decision(c)
    _EMOJI = {"UNDERWRITTEN": "✅", "PROBE": "🔬", "WATCH": "⏸", "REJECT": "⛔"}
    print(f"  DECISIÓN → {_EMOJI.get(dec,'')} {dec}   (estado de valuación: {c.estado_valuacion})")
    print(f"    · elegible (sobrevivió): {c.elegible} · veto supervivencia: {getattr(ev,'veto_supervivencia',False)} · "
          f"tier score: {ev.tier} (limita: {ev.pilar_limitante or '—'})")
    print(f"    · cap de sizing: {c.cap and f'{c.cap:.1%}'} (ligó: {c.cap_reason}) · celda: {c.arquetipo}×{c.tier_capital}")
    if c.abstenido:
        print(f"    · ⏸ {c.motivo_abstencion} → cola de investigación (NO veto)")
    print(f"    · flags: {'; '.join(h.flags[:4]) or '—'}")


def main(argv: list[str]) -> int:
    tickers = [t.upper() for t in argv] or ["LEU", "RKLB", "S", "TER", "OKTA"]
    with session_scope() as s:
        for t in tickers:
            ficha(s, t)
    print("\n" + "─" * 84)
    print("SHADOW — análisis de la superficie nueva (doc 34). Contrastar contra IA externa para validar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
