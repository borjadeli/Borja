"""Ledger de rechazos (doc 40 Bloque 0.1) — snapshot del universo de hoy + medición de separación.

    .venv/bin/python -m ops.ledger_decisiones snapshot   # registra las decisiones de HOY (semilla t0)
    .venv/bin/python -m ops.ledger_decisiones medir      # retorno forward por clase + separación compra/rechazo

El instrumento anti-ceguera: registrando HOY lo que compraríamos y lo que rechazaríamos, dentro de meses
podemos ver si los rechazados (los que descartamos) terminaron superando a los comprados — la señal de que
el frame no discrimina. Sin LLM. `snapshot` es idempotente por (ticker, fecha, versión de política).
"""
from __future__ import annotations

import sys
from datetime import date

from backend.database import session_scope
from backend.nucleo import registro_decisiones as RD
from backend.services import market_data
from ops.cutover_diff import cargar_libro_vivo
from ops.shadow_ranking import MUESTRA, construir


def _precios(tickers: list[str]) -> dict[str, float]:
    out = {}
    for t in tickers:
        sn = market_data.get_price_snapshot(t)
        if sn and sn.precio_actual:
            out[t] = sn.precio_actual
    return out


def snapshot(hoy: str) -> int:
    universo = sorted(set(cargar_libro_vivo()) | set(MUESTRA))
    cands = []
    with session_scope() as s:
        for t in universo:
            c = construir(s, t)
            if c is not None:
                cands.append(c)
    precios = _precios([c.ticker for c in cands])
    decs = RD.desde_candidatos(cands, precios, hoy)
    nuevas = RD.registrar(decs)
    print(f"snapshot {hoy}: {len(cands)} evaluados · {len(decs)} con precio · {nuevas} NUEVAS al ledger "
          f"(dedup por ticker+fecha+versión).")
    return nuevas


def medir(hoy: str) -> None:
    data = RD._cargar(RD.LEDGER_PATH)
    if not data:
        print("ledger vacío — corré `snapshot` primero (hoy) y volvé en unos meses.")
        return
    tickers = sorted({d["ticker"] for d in data})
    met = RD.metricas_por_clase(_precios(tickers), hoy)
    print("=" * 78)
    print(f"LEDGER DE RECHAZOS — {len(data)} decisiones registradas · {met['total_marcadas']} con retorno forward")
    print("=" * 78)
    print(f"{'ESTADO':22} {'n':>3} {'media':>8} {'mediana':>8} {'min':>8} {'max':>8}")
    for est, r in met["por_estado"].items():
        print(f"{est:22} {r['n']:>3} {str(r['media']):>8} {str(r['mediana']):>8} {str(r['min']):>8} {str(r['max']):>8}")
    print("-" * 78)
    print(f"{'→ COMPRAríamos':22} {met['compra']['n']:>3} {str(met['compra']['media']):>8}")
    print(f"{'→ RECHAZAríamos':22} {met['rechazo']['n']:>3} {str(met['rechazo']['media']):>8}")
    sep = met["separacion_media"]
    print("-" * 78)
    if sep is None:
        print("SEPARACIÓN: aún no computable (faltan clases con retorno).")
    elif abs(sep) < 0.01:
        print(f"SEPARACIÓN media (compra − rechazo) = {sep:+.1%}  → sin señal aún (dentro del ruido).")
    elif sep > 0:
        print(f"SEPARACIÓN media (compra − rechazo) = +{sep:.1%}  → el frame DISCRIMINA (compra > rechazo). ✓")
    else:
        print(f"SEPARACIÓN media (compra − rechazo) = {sep:.1%}  → ⚠️ ALARMA: rechazamos lo que subió (ceguera).")
    print("OJO: con pocos días transcurridos esto es RUIDO. El instrumento gana valor con el tiempo (meses).")


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "medir"
    hoy = argv[1] if len(argv) > 1 else date.today().isoformat()
    if cmd == "snapshot":
        snapshot(hoy)
    elif cmd == "medir":
        medir(hoy)
    else:
        print("uso: ops.ledger_decisiones [snapshot|medir] [YYYY-MM-DD]")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
