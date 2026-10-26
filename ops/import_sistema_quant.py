"""Importa el universo + mapa de cuellos del Sistema-Quant a las tablas nx_* (v2 Fase 2).

Determinista. Lee las fuentes versionadas en `backend/seed/sistema_quant/` (procedencia ahí):
- `industry_map.yaml`  → `nx_nodo`         (idempotente por nombre; guarda sq_id/atributos en la nota).
- `companies.yaml`     → `nx_empresa`      (filtradas por el rango de market cap del IPS) + `nx_empresa_nodo`
                                            (vínculo ticker↔nodo; el 1º nodo de la empresa = primario).

El market cap NO viene en el YAML (por diseño): se trae por API (yfinance, $0) y se aplica el rango IPS
[cap_min, cap_max]. No borra nada (Art. 5.3). El fetch de market cap es inyectable (`market_cap_fn`) para
testear sin red.

Correr:  .venv/bin/python -m ops.import_sistema_quant              # con filtro de cap (llama API)
         .venv/bin/python -m ops.import_sistema_quant --no-cap     # sin filtro (no llama API)
         .venv/bin/python -m ops.import_sistema_quant --solo OKLO,NNE
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.ledger import entidades
from backend.ledger.models import NxEmpresa, NxNodo

_SEED = Path(__file__).resolve().parent.parent / "backend" / "seed" / "sistema_quant"
MAP_PATH = _SEED / "map" / "industry_map.yaml"
UNIV_PATH = _SEED / "universe" / "companies.yaml"

# Rango de market cap del IPS (decisión del operador 2026-10-26). En Fase 4 pasa a config/ips.yaml.
CAP_MIN = 150_000_000.0          # $150M
CAP_MAX = 60_000_000_000.0       # $60B


def _nota_nodo(node: dict) -> str:
    parts = [f"sq_id={node['id']}", f"type={node.get('type', '?')}"]
    for k in ("concentration", "substitutability"):
        if node.get(k):
            parts.append(f"{k}={node[k]}")
    if node.get("depends_on"):
        parts.append("depends_on=" + ",".join(node["depends_on"]))
    return "; ".join(parts)


def importar_nodos(session: Session) -> dict[str, int]:
    """`industry_map.yaml` → `nx_nodo` (idempotente por nombre). Devuelve {sq_id: nodo_id}."""
    mapa = yaml.safe_load(MAP_PATH.read_text())
    sqid_to_id: dict[str, int] = {}
    for layer in mapa.get("layers", []):
        for seg in layer.get("segments", []):
            for node in seg.get("nodes", []):
                nombre = node["name"]
                ex = session.execute(
                    select(NxNodo).where(NxNodo.nombre == nombre)
                ).scalar_one_or_none()
                if ex is None:
                    ex = entidades.crear_nodo(
                        session, nombre=nombre, cluster=seg.get("id"),
                        factor_macro=layer.get("id"), nota=_nota_nodo(node),
                    )
                sqid_to_id[node["id"]] = ex.id
    return sqid_to_id


def _market_cap_default(ticker: str) -> float | None:
    from backend.services import market_data
    snap = market_data.get_price_snapshot(ticker)
    return snap.market_cap if snap else None


def importar_empresas(session: Session, sqid_to_id: dict[str, int], *, aplicar_cap: bool = True,
                      cap_min: float = CAP_MIN, cap_max: float = CAP_MAX,
                      market_cap_fn=_market_cap_default, solo: set[str] | None = None,
                      hoy: date | None = None) -> dict:
    """`companies.yaml` → `nx_empresa` (filtradas por cap) + `nx_empresa_nodo`."""
    hoy = hoy or date.today()
    universo = yaml.safe_load(UNIV_PATH.read_text()).get("companies", [])
    res: dict = {"importadas": [], "descartadas_cap": [], "sin_cap": [], "links": 0}
    for c in universo:
        ticker = str(c["ticker"]).upper()
        if solo is not None and ticker not in solo:
            continue
        if aplicar_cap:
            mc = market_cap_fn(ticker)
            if mc is None:
                res["sin_cap"].append(ticker)
                continue
            if not (cap_min <= mc <= cap_max):
                res["descartadas_cap"].append((ticker, mc))
                continue
        if session.get(NxEmpresa, ticker) is None:
            entidades.crear_candidata(
                session, ticker=ticker, fecha=hoy, nombre=c.get("name"),
                exchange=c.get("exchange"), jurisdiccion=c.get("country"),
                fuente_ingreso="import_sq", motivo="import Sistema-Quant",
            )
        for i, sqid in enumerate(c.get("nodes", [])):
            nid = sqid_to_id.get(sqid)
            if nid is not None:
                entidades.vincular_nodo(session, ticker=ticker, nodo_id=nid, es_primario=(i == 0))
                res["links"] += 1
        res["importadas"].append(ticker)
    return res


def importar(session: Session, *, merge_tickers: list[str] | None = None, **kw) -> dict:
    """ETL completo: nodos + empresas (+ merge opcional de tickers vivos de BORJA, sin filtro de cap)."""
    sqid_to_id = importar_nodos(session)
    res = importar_empresas(session, sqid_to_id, **kw)
    res["nodos"] = len(sqid_to_id)
    if merge_tickers:
        hoy = kw.get("hoy") or date.today()
        res["merge"] = []
        for tk in merge_tickers:
            tk = str(tk).upper()
            if session.get(NxEmpresa, tk) is None:
                entidades.crear_candidata(session, ticker=tk, fecha=hoy,
                                          fuente_ingreso="borja_vivo", motivo="merge universo BORJA")
                res["merge"].append(tk)
    return res


def _main() -> None:
    ap = argparse.ArgumentParser(description="Importa el Sistema-Quant a nx_*")
    ap.add_argument("--no-cap", action="store_true", help="no filtra por market cap (no llama a la API)")
    ap.add_argument("--solo", help="tickers separados por coma (subset)")
    ap.add_argument("--no-merge", action="store_true", help="no fusiona los tickers vivos de BORJA")
    args = ap.parse_args()

    from backend.database import session_scope
    solo = {x.strip().upper() for x in args.solo.split(",")} if args.solo else None
    merge = None
    if not args.no_merge:
        from backend.seleccion.universo import tickers_vivos
        merge = tickers_vivos()

    with session_scope() as s:
        res = importar(s, aplicar_cap=not args.no_cap, solo=solo, merge_tickers=merge)

    print(f"nodos={res['nodos']}  importadas={len(res['importadas'])}  "
          f"descartadas_por_cap={len(res['descartadas_cap'])}  sin_cap={len(res['sin_cap'])}  "
          f"links={res['links']}  merge_borja={len(res.get('merge', []))}")
    if res["descartadas_cap"]:
        ej = ", ".join(f"{t} (${mc/1e9:.0f}B)" for t, mc in res["descartadas_cap"][:6])
        print(f"  descartadas por tamaño (ej.): {ej}")
    if res["sin_cap"]:
        print(f"  sin market cap (ej.): {', '.join(res['sin_cap'][:8])}")


if __name__ == "__main__":
    _main()
