"""Job del mapa vivo (pieza 6-real, doc 89 §9.1): corre el tablero sobre los cuellos de nx_*, clasifica,
persiste la foto point-in-time + los estados, y deja los cambios de estado como alerta. $0 LLM (determinista;
usa companyfacts cacheado). Import-safe: el IO vive dentro de las funciones.

Correr:  .venv/bin/python -m ops.mapa_job                 (todos los cuellos)
         .venv/bin/python -m ops.mapa_job --cuello fotonica
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

_ALERTAS = Path("data/alertas_mapa_v2.json")


def metricas_de_pack(pack) -> dict:
    """Extrae del DataPack las métricas que consume el tablero (revenue/gross/op/capex/inventarios/rpo +
    crecimiento como FRACCIÓN, derivado de revenue vs revenue_fy_prev para no mezclar % con fracción). Prefiere
    las lecturas FY/TTM sobre las trimestrales. Puro y testeable (un `pack` con `.puntos` de DataPoint)."""
    idx = {}
    for p in getattr(pack, "puntos", []):
        if p.value is None:
            continue
        prev = idx.get(p.metric)
        if prev is None or (p.period_type in ("FY", "TTM") and prev.period_type not in ("FY", "TTM")):
            idx[p.metric] = p

    def v(m):
        dp = idx.get(m)
        return dp.value if dp else None

    rev, revprev = v("revenue"), v("revenue_fy_prev")
    growth = round(rev / revprev - 1, 4) if (rev and revprev) else None
    return {"revenue": rev, "gross_profit": v("gross_profit"),
            "operating_income_loss": v("operating_income_loss"), "capex": v("capex"),
            "inventarios": v("inventarios"), "rpo": v("rpo"), "revenue_growth_yoy": growth,
            "ev_revenue": v("ev_revenue")}


def cuellos_empresas() -> dict:
    """{nombre_cuello: [tickers]} desde nx_* (NxNodo + NxEmpresaNodo)."""
    from sqlalchemy import select

    from backend.database import session_scope
    from backend.ledger.models import NxEmpresaNodo, NxNodo
    out: dict[str, list[str]] = {}
    with session_scope() as s:
        filas = s.execute(select(NxNodo.nombre, NxEmpresaNodo.ticker)
                          .join(NxEmpresaNodo, NxEmpresaNodo.nodo_id == NxNodo.id)).all()
    for nombre, ticker in filas:
        out.setdefault(nombre, []).append((ticker or "").upper())
    return out


def correr(cuello: str | None = None, hoy: date | None = None) -> dict:
    from backend.agentes import data_pack as dp
    from backend.agentes.mapa_store import StoreMapa, cargar_estados, guardar_estados
    from backend.agentes.mapa_vivo import correr_mapa
    from backend.agentes.pipeline_estado import PipelineEstado
    hoy = hoy or date.today()
    ce = cuellos_empresas()
    if cuello:
        ce = {cuello: ce.get(cuello, [])}
    tickers = sorted({t for tks in ce.values() for t in tks})

    metricas: dict[str, dict] = {}
    for tk in tickers:
        try:
            metricas[tk] = metricas_de_pack(dp.ensamblar(tk, as_of=hoy))
        except Exception as e:  # noqa: BLE001 — un ticker que falla no tumba el barrido
            print(f"  ⚠ {tk}: {e}")

    store = StoreMapa()
    estados, cambios = correr_mapa(ce, metricas, store=store, estados_previos=cargar_estados(), hoy=hoy)
    store.guardar()
    guardar_estados(estados)
    PipelineEstado().marcar("mapa")

    if cambios:
        _ALERTAS.parent.mkdir(parents=True, exist_ok=True)
        _ALERTAS.write_text(json.dumps({"fecha": hoy.isoformat(), "cambios": cambios},
                                       ensure_ascii=False, indent=2), encoding="utf-8")
    conf = sum(1 for e in estados.values() if e.estado == "confirmado")
    prom = sum(1 for e in estados.values() if e.estado == "promesa")
    disol = sum(1 for e in estados.values() if e.estado == "resolviendose")
    print(f"mapa: {len(estados)} cuellos · confirmados {conf} · promesa {prom} · disolución {disol} · "
          f"cambios {len(cambios)}")
    for c in cambios:
        print(f"  🔔 {c['cuello']}: {c['de']} → {c['a']}  ({c['razon']})")
    return {"estados": len(estados), "confirmados": conf, "cambios": cambios}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cuello", default=None, help="un solo cuello (por nombre); default = todos")
    correr(ap.parse_args().cuello)
