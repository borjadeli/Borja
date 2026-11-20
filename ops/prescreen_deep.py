"""Shortlist de candidatos a DEEP (doc 90 §8) — corre el mapa + el pre-screen en vivo y rankea qué nombres
merecen gastar el presupuesto de deep (Opus). $0 LLM (determinista; companyfacts cacheado). Import-safe.

Correr:  .venv/bin/python -m ops.prescreen_deep [--top 20]
"""
from __future__ import annotations

import argparse
from datetime import date


def _fichas_vigentes() -> set:
    try:
        from backend.agentes.ficha_store import StoreFichas
        return {tk.upper() for tk, f in StoreFichas().todos().items() if getattr(f, "estado", None) == "VIGENTE"}
    except Exception:  # noqa: BLE001
        return set()


def correr(top: int = 20, hoy: date | None = None) -> list:
    from backend.agentes import data_pack as dp
    from backend.agentes.mapa_atribucion import MapaAtribucion
    from backend.agentes.mapa_store import StoreMapa
    from backend.agentes.mapa_vivo import correr_mapa
    from backend.agentes.prescreen import prescreen
    from ops.mapa_job import cuellos_empresas, metricas_de_pack
    hoy = hoy or date.today()
    atrib = MapaAtribucion()
    anotados = set(atrib._m.keys())
    ce = {k: v for k, v in cuellos_empresas().items() if k in anotados}
    tickers = sorted({t for v in ce.values() for t in v})

    metr: dict[str, dict] = {}
    for tk in tickers:
        try:
            metr[tk] = metricas_de_pack(dp.ensamblar(tk, as_of=hoy))
        except Exception as e:  # noqa: BLE001 — un ticker que falla no tumba el barrido
            print(f"  ⚠ {tk}: {str(e)[:50]}")

    store = StoreMapa()
    estados, _ = correr_mapa(ce, metr, store=store, atrib=atrib, hoy=hoy)
    store.guardar()

    vigentes = _fichas_vigentes()
    cands = []
    for cuello, tks in ce.items():
        for tk in tks:
            m = metr.get(tk)
            if m:
                cands.append({"ticker": tk, "cuello": cuello, **m, "tiene_ficha_reciente": tk in vigentes})
    ranked = prescreen(cands, estados_cuello=estados, atrib=atrib)

    visto, uniq = set(), []          # dedup por ticker (se queda el mejor par cuello, ya viene ordenado)
    for c in ranked:
        if c.ticker not in visto:
            visto.add(c.ticker)
            uniq.append(c)

    aptos = [c for c in uniq if c.apto]
    print(f"\n=== SHORTLIST DE DEEP ({len(aptos)} aptos de {len(uniq)} evaluados) ===")
    for c in (aptos or uniq)[:top]:
        est = estados.get(c.cuello)
        print(f"  {'✅' if c.apto else '  '} {c.ticker:7} [{getattr(est, 'estado', '?'):11}] "
              f"{(c.cuello or '')[:38]:38} brecha {c.brecha if c.brecha is not None else '—'} · {c.motivo}")
    return aptos


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=20)
    correr(ap.parse_args().top)
