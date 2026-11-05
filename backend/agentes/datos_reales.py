"""Adaptadores de datos reales para el runner semanal (v2 Fase 4).

El runner es puro sobre datos inyectados; acá viven los adaptadores que los traen de las fuentes reales:
- **precios + market cap + ADV**: `market_data.get_price_snapshot` (un fetch por ticker, reusado).
- **sector + cuello**: del ledger `nx_*` (`nx_empresa.sector` + nodo primario vía `nx_empresa_nodo`→`nx_nodo`).
- **paper nuevo**: un ledger fiel SQLite SEPARADO y limpio (`data/paper_v2.db`), para no mezclarse con los
  datos `nx_*` de `borja.db` ni con el paper v3 congelado.

Todo inyectable (snapshots, session) → testeable sin red ni DB real.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.agentes.ips import ContextoTicker
from backend.ledger.models import NxEmpresa, NxEmpresaNodo, NxNodo, crear_tablas
from backend.ledger import core

_PAPER_DB = Path(__file__).resolve().parent.parent.parent / "data" / "paper_v2.db"


def recolectar_snapshots(tickers, *, snapshot_fn=None) -> dict:
    """ticker → PriceSnapshot (o nada si el feed no responde). Un fetch por ticker, para reusar."""
    if snapshot_fn is None:
        from backend.services.market_data import get_price_snapshot
        snapshot_fn = get_price_snapshot
    out = {}
    for t in tickers:
        snap = snapshot_fn(t)
        if snap is not None:
            out[t.upper()] = snap
    return out


def precios_de(snapshots: dict, *, fx_fn=None) -> dict[str, float]:
    """ticker → precio actual EN USD (solo los que se pueden valuar). Soporte extranjero (r6 #1): el feed da el
    precio en moneda de cotización; acá —el borde del paper y de las carteras sombra— se pasa a USD, porque el
    libro razona en USD (equity, sizing). Un extranjero sin FX disponible queda fuera (igual que sin precio)."""
    from backend.services.market_data import precio_a_usd
    out: dict[str, float] = {}
    for tk, s in snapshots.items():
        usd = precio_a_usd(getattr(s, "precio_actual", None), getattr(s, "currency", "USD"), fx_fn=fx_fn)
        if usd is not None:
            out[tk] = usd
    return out


def precios_meta_de(snapshots: dict, *, fx_fn=None) -> dict[str, dict]:
    """Metadata de conversión por ticker para el rastro del fill (r7a #4): {moneda, precio_nativo, fx_usado}.
    fx_usado = USD por 1 unidad de la moneda (None si es USD o no se pudo). Solo los que se pueden valuar."""
    from backend.services.market_data import fx_a_usd, precio_a_usd
    out: dict[str, dict] = {}
    for tk, s in snapshots.items():
        nativo = getattr(s, "precio_actual", None)
        cur = (getattr(s, "currency", "USD") or "USD").upper()
        usd = precio_a_usd(nativo, cur, fx_fn=fx_fn)
        if usd is None:
            continue
        fx = None if cur == "USD" else ((fx_fn or fx_a_usd)(cur))
        out[tk] = {"moneda": cur, "precio_nativo": nativo, "fx_usado": fx}
    return out


def _sector(session: Session, tk: str) -> str | None:
    row = session.execute(select(NxEmpresa.sector).where(NxEmpresa.ticker == tk)).first()
    return row[0] if row else None


def _cuello_primario(session: Session, tk: str) -> str | None:
    """Nombre del nodo-cuello primario de la empresa (o cualquiera si no hay primario marcado)."""
    row = session.execute(
        select(NxNodo.nombre)
        .join(NxEmpresaNodo, NxEmpresaNodo.nodo_id == NxNodo.id)
        .where(NxEmpresaNodo.ticker == tk)
        .order_by(NxEmpresaNodo.es_primario.desc(), NxNodo.id)
    ).first()
    return row[0] if row else None


def contexto_de(tickers, snapshots: dict, *, session: Session) -> dict[str, ContextoTicker]:
    """Arma el ContextoTicker MECÁNICO por nombre: sector/cuello del ledger nx_*, market cap/ADV del feed."""
    out: dict[str, ContextoTicker] = {}
    for t in tickers:
        tk = t.upper()
        snap = snapshots.get(tk)
        out[tk] = ContextoTicker(
            sector=_sector(session, tk),
            cuello=_cuello_primario(session, tk),
            market_cap=getattr(snap, "market_cap", None) if snap else None,
            adv_usd=getattr(snap, "volumen_diario_promedio_30d", None) if snap else None,
        )
    return out


def abrir_paper(path: Path | str | None = None, *, capital_inicial: float | None = None,
                fecha: date | None = None) -> Session:
    """Abre (crea si no existe) el ledger fiel del paper nuevo. Si está vacío y se pasa `capital_inicial`,
    hace el depósito inicial. Devuelve una `Session` viva (el caller la cierra)."""
    engine = create_engine(f"sqlite:///{Path(path or _PAPER_DB)}", future=True)
    crear_tablas(engine)
    session = Session(engine, future=True)
    if capital_inicial and core.proyectar(session, {})["equity"] <= 0:
        core.depositar(session, capital_inicial, fecha or date.today())
        session.commit()
    return session
