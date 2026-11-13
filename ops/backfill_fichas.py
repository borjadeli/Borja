"""Backfill de FICHAS VIVAS desde el cache de dossiers (r9, doc 80 §F · P0). $0 de LLM; hits de red (XBRL +
precio) para los insumos del puente. Lo corre el operador en el server.

    .venv/bin/python -m ops.backfill_fichas            # todas las del cache
    .venv/bin/python -m ops.backfill_fichas OKLO MP    # puntuales (para probar)

Para cada dossier cacheado arma la ficha: reloj lento = escenarios/clase/falsador del dossier; reloj rápido =
puente/zonas calculados con acciones, deuda neta y precio ACTUALES. Escribe `data/fichas_v2.json`.
"""
from __future__ import annotations

import sys
from datetime import date

from backend.agentes import data_pack as dp
from backend.agentes.ficha_store import StoreFichas, backfill_fichas


def _datos_de_pack(ticker: str, *, as_of: date, cuello_fn=None) -> dict | None:
    """Insumos del puente desde el data pack: acciones (XBRL si está), deuda neta (deuda LP − liquidez), precio
    (USD), cuello y `conocido_hasta` (known_at más nuevo del XBRL). Best-effort."""
    try:
        pack = dp.ensamblar(ticker, as_of=as_of)
    except Exception:  # noqa: BLE001
        return None
    puntos = pack.puntos

    def _val(metric):
        return next((p.value for p in puntos if p.metric == metric and p.value is not None), None)

    # ACCIONES: normalmente XBRL (verificado), PERO si el feed diverge >25% (split no reflejado / dilución), se
    # usa el FEED (actual, post-split) y se marca datos_conflicted → la ficha NO es comprable sin re-verificar.
    # (El caso IESC: XBRL 19,9M pre-split vs feed 42,4M → la ficha daba falso COMPRA al duplicar el valor/acción.)
    shares = [p for p in puntos if p.metric == "shares_outstanding" and p.value]
    feed_sh = next((p.value for p in shares if "xbrl" not in (p.source.name or "").lower()), None)
    xbrl_sh = next((p.value for p in shares if "xbrl" in (p.source.name or "").lower()), None)
    conflicted = bool(feed_sh and xbrl_sh and abs(feed_sh - xbrl_sh) / max(feed_sh, xbrl_sh) > 0.25)
    acciones = feed_sh if conflicted else (xbrl_sh or feed_sh)
    if not acciones:
        return None
    liquidez = _val("liquidez")
    deuda_lp = _val("long_term_debt") or 0.0
    deuda_neta = deuda_lp - (liquidez or 0.0)
    precio = _val("precio")
    knowns = [p.known_at for p in puntos if p.known_at and "xbrl" in (p.source.name or "").lower()]
    conocido = max(knowns).isoformat() if knowns else None
    return {"acciones": acciones, "deuda_neta": deuda_neta, "precio": precio, "datos_conflicted": conflicted,
            "cuello": (cuello_fn(ticker) if cuello_fn else None), "conocido_hasta": conocido,
            "cobertura": "PARCIAL" if "." in ticker else "FULL"}


def main() -> int:
    from backend.agentes.orquestador import CacheDossiers, _CACHE_PATH
    cache = CacheDossiers(path=_CACHE_PATH).todos()
    pedidos = [t.upper() for t in sys.argv[1:]]
    if pedidos:
        cache = {tk: e for tk, e in cache.items() if tk.upper() in pedidos}
    if not cache:
        print("nada en el cache de dossiers (o los tickers pedidos no están)")
        return 1

    cuello_fn = None
    try:
        from backend.agentes.universo import cuello_primario
        from backend.database import session_scope
        _s = session_scope().__enter__()
        cuello_fn = lambda tk: cuello_primario(_s, tk)  # noqa: E731
    except Exception:  # noqa: BLE001 — sin mapa igual se arma la ficha (cuello None)
        pass

    hoy = date.today()
    print(f"backfill de fichas desde {len(cache)} dossiers (hits de red para el puente)…")
    store = StoreFichas()
    fichas = backfill_fichas(cache, store=store,
                             datos_fn=lambda tk: _datos_de_pack(tk, as_of=hoy, cuello_fn=cuello_fn), hoy=hoy)
    print(f"escritas {len(fichas)} fichas en data/fichas_v2.json\n")
    print(f"{'ticker':10}{'clase':14}{'precio':>9}{'compra':>9}{'zona':>10}  estado")
    for f in sorted(fichas, key=lambda x: x.ticker):
        g = f.gatillos
        lat = f.latido
        print(f"{f.ticker:10}{f.clase_d4:14}{(f.puente.precio if f.puente else 0):>9.2f}"
              f"{(g.compra if g and g.compra else 0):>9.2f}{(lat.zona if lat else '—'):>10}  {f.estado}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
