"""Job diario de las fichas vivas (r9, doc 80 §C/§F · P0) — el LATIDO barato.

Recalcula el reloj rápido (puente/zonas) de TODAS las fichas con el precio vivo + evalúa vigencia por evento, y
emite las alertas de CAMBIO de zona (COMPRA/RECORTE/SALIDA) que el PM mira. 100% determinista, $0 de LLM. Lo
corre el operador a diario (o lo agenda el scheduler). Hits de red solo para los precios.

    .venv/bin/python -m ops.job_fichas

Persiste las fichas actualizadas + imprime las alertas accionables (lo comprable = zona COMPRA + tesis VIGENTE +
datos confiables, doc 80)."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from backend.agentes.datos_reales import precios_de, recolectar_snapshots
from backend.agentes.ficha_store import StoreFichas, recalcular_todas

_ALERTAS = Path(__file__).resolve().parent.parent / "data" / "alertas_fichas_v2.json"


def main() -> int:
    store = StoreFichas()
    fichas = store.todos()
    if not fichas:
        print("no hay fichas (corré ops.backfill_fichas primero)")
        return 1
    tickers = sorted(fichas)
    print(f"job diario sobre {len(tickers)} fichas (precios vivos; $0 LLM)…")
    precios = precios_de(recolectar_snapshots(tickers))                 # feed → USD
    alertas = recalcular_todas(store, precios_fn=lambda tk: precios.get(tk.upper()))

    _ALERTAS.parent.mkdir(parents=True, exist_ok=True)
    _ALERTAS.write_text(json.dumps({"fecha": date.today().isoformat(), "alertas": alertas},
                                   ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"precios resueltos: {len(precios)}/{len(tickers)} · cambios de zona: {len(alertas)}\n")
    if not alertas:
        print("sin cambios de zona hoy (nada entró/salió de compra/recorte/salida).")
    for a in alertas:
        marca = "✅ COMPRABLE" if a.get("comprable") else ("⚠ datos conflicted" if a.get("datos_conflicted")
                                                           else f"({a.get('estado')})")
        print(f"  {a['ticker']:8} {a['zona_antes'] or '—'} → {a['zona']}  precio {a['precio']}  {marca}")
    # foto del estado actual de todas (para el dashboard / el PM)
    print("\nestado de las fichas (zona · precio · gatillo de compra):")
    for tk in tickers:
        f = store.get(tk)
        lat, g, p = f.latido, f.gatillos, f.puente
        if lat and p:
            print(f"  {tk:8} {lat.zona:9} precio {p.precio:>9.2f}  compra ≤ "
                  f"{(g.compra if g and g.compra else 0):>9.2f}  ret_esp {p.retorno_esperado}"
                  + ("  [datos conflicted]" if f.datos_conflicted else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
