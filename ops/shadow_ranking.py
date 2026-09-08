"""Ranking lexicográfico en SHADOW sobre datos reales (doc 34 §4, paso 3→cutover).

    .venv/bin/python -m ops.shadow_ranking [TICKER ...]

Corre las DOS superficies (elegibilidad de 3 pilares + números cohort-free) sobre nombres reales,
arma el `CandidatoLex` y muestra el **ranking lexicográfico** (gate→tier→cobertura→asimetría cap5×→
catalizador→liquidez). Es el paso previo al cutover: ver la superficie nueva funcionando y comparar
contra el merito viejo ANTES de tocar `selector`/`flujo` (el paper vivo, que NO se toca acá).

`catalizador` = False por ahora (sin señal citada, doc 14 §G7). Red: baja EDGAR/mercado por nombre.
"""
from __future__ import annotations

import sys

from backend.database import session_scope
from backend.nucleo import fact_store as FS
from backend.nucleo import ranking
from backend.nucleo.compilador import _cobertura
from backend.nucleo.hoja_evidencia import hoja
from backend.nucleo.cartera_celdas import construir_cartera
from backend.nucleo.ranking_lexicografico import (
    candidato_desde, cola_investigacion, cola_operativa, rankear_por_celda, tasa_abstencion,
)
from backend.services import market_data
from backend.utils import get_logger

log = get_logger(__name__)

# Muestra por defecto: nombres ya trabajados esta sesión (tienen datos). Overridable por args.
MUESTRA = ["AAOI", "LEU", "OKTA", "TENB", "BWXT", "MP", "CLS", "S", "VRNS", "NABL"]


def construir(session, ticker: str):
    """Corre las dos superficies para un ticker → CandidatoLex. None si falla (se saltea)."""
    try:
        ev = ranking.evaluar_ticker(session, ticker)               # elegibilidad (3 pilares)
        h = hoja(ticker, session=session)                          # números cohort-free
        snap = FS.snapshot_vigente(session, ticker)
        cob = _cobertura(snap) if snap else 0.0                    # cobertura de evidencia
        sn = market_data.get_price_snapshot(ticker)
        liq = sn.volumen_diario_promedio_30d if sn else None       # ADV (liquidez)
        return candidato_desde(ev, h, cobertura=cob, liquidez_adv=liq)
    except Exception as e:  # noqa: BLE001
        log.warning("shadow %s: %s", ticker, e)
        return None


def main(argv: list[str]) -> int:
    tickers = [t.upper() for t in argv] or MUESTRA
    cands = []
    with session_scope() as s:
        for t in tickers:
            c = construir(s, t)
            if c is not None:
                cands.append(c)

    abstenidos = cola_investigacion(cands)              # evidencia insuficiente → no se decide
    por_celda = rankear_por_celda(cands)                # elegibles con evidencia suficiente, por (arquetipo × tier)
    cola = cola_operativa(por_celda)                    # cola operativa (NO ranking económico cross-celda)
    fuera = [c for c in cands if not c.gate_ok and not c.abstenido]   # decididos-fuera (≠ abstenidos)
    print("=" * 96)
    print("RANKING POR CELDA (shadow, doc 34 §3bis) — llave local: asimetría FCFE / burden-tupla pre-revenue")
    print("=" * 96)
    print(f"{'#':>2} {'TICKER':7} {'CELDA (arq×tier)':20} {'ROUTE':12} {'COB':>5} {'BURD':>6} {'EST-VAL':>14} {'CAP':>5} {'LIGÓ':>10}")
    print("-" * 104)
    _EV_ABREV = {"COVERED": "COVERED", "STRETCH": "STRETCH", "OPTION_PRICED": "OPTION_PRICE", "NON_UNDERWRITABLE": "NON-UNDERW"}
    for i, c in enumerate(cola, 1):
        burd = f"{c.burden:.0f}" if c.burden is not None else "—"
        capf = f"{c.cap:.1%}" if c.cap is not None else "—"
        celda = f"{c.arquetipo}×{c.tier_capital}"
        ev = _EV_ABREV.get(c.estado_valuacion, c.estado_valuacion)
        print(f"{i:>2} {c.ticker:7} {celda:20} {c.route[:12]:12} {c.cobertura:>5.2f} {burd:>6} {ev:>14} {capf:>5} {c.cap_reason:>10}")
    print("-" * 96)
    print(f"{len(cola)} en el libro duro en {len(por_celda)} celdas · {len(fuera)} fuera-decididos "
          f"({', '.join(c.ticker for c in fuera) or '—'} → carril/descarte)")
    print(f"ABSTENIDOS (evidencia insuficiente, NO veto → cola de investigación): {len(abstenidos)} "
          f"· tasa de abstención {tasa_abstencion(cands):.0%}  ← métrica de salud (si no baja, el cuello es la extracción)")
    for c in abstenidos:
        print(f"    ⏸ {c.ticker}: {c.motivo_abstencion}")
    print("\nOJO (doc 34 §3bis): el puesto en la cola NO implica superioridad económica entre celdas distintas — "
          "eso lo decide la CUOTA ex-ante de cartera. SHADOW: no toca el paper.")

    # Construcción de cartera: llena las celdas con cuotas ex-ante (caps, no cuotas obligatorias).
    cart = construir_cartera(por_celda)
    print("\n" + "=" * 96)
    print(f"CARTERA (shadow) — cuotas ex-ante · política {cart.politica_version}/{cart.politica_hash}")
    print("=" * 96)
    for p in cart.posiciones:
        print(f"  {p.ticker:7} {p.arquetipo}×{p.tier:2} → size {p.size:.1%}  (cap {p.cap:.1%})")
    print("-" * 96)
    print(f"invertido {cart.invertido:.0%} · cash {cart.cash:.0%} · {len(cart.posiciones)} posiciones "
          f"(caps, NO cuotas obligatorias: si no hay buena empresa, queda cash).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
