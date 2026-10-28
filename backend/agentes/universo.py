"""Candidatos desde el universo (v2 embudo, doc 61 §A) — la parte DETERMINISTA y barata del embudo.

Computa las `SenalesTriage` de cada empresa de `nx_empresa` desde EDGAR (filings nuevos) + precio + el cache
de dossiers + la cartera — SIN LLM. Con esas señales, el Triage (Haiku, ~gratis) filtra TODO el universo y
solo los nombres con algo nuevo (filing/evento/posición/movimiento) pasan al Analista caro. Es el embudo que
"cuida la plata": screenear cientos por casi nada, pagar profundidad solo donde se movió algo.

Los UMBRALES finos (qué % de precio, cuántos días a earnings) viven en la lógica del Triage y se afinan en la
triangulación del doc 61; acá solo se computan las señales crudas, fielmente.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.agentes.triage import SenalesTriage
from backend.ledger.models import NxEmpresa

# Estados de nx_empresa que NO entran al embudo (fuera de juego). El resto (Candidata, etc.) se screenea.
_ESTADOS_INACTIVOS = {"descartada", "cerrada", "salida", "vendida"}


def tickers_universo(session: Session) -> list[str]:
    rows = session.execute(select(NxEmpresa.ticker, NxEmpresa.estado)).all()
    return [t for t, e in rows if (e or "").lower() not in _ESTADOS_INACTIVOS]


def señales_ticker(ticker: str, *, hoy: date, fecha_dossier: date | None, filings: list,
                   precio_hist: list[float] | None, es_posicion: bool,
                   prioridad_cuello: int = 0) -> tuple[SenalesTriage, str]:
    """Señales DETERMINISTAS + un resumen de los filings nuevos (insumo del juez de materialidad del Triage).
    `filings` = objetos con `.tipo` y `.fecha` (datetime); `precio_hist` = serie de cierres."""
    dias_dossier = (hoy - fecha_dossier).days if fecha_dossier else None
    nuevos = [f for f in (filings or []) if fecha_dossier is None or f.fecha.date() > fecha_dossier]
    tiene_evento = any(f.tipo == "8-K" for f in nuevos)

    periodicos = sorted((f for f in (filings or []) if f.tipo in ("10-Q", "10-K")), key=lambda f: f.fecha)
    dias_a_evento = None
    if periodicos:
        prox = periodicos[-1].fecha.date() + timedelta(days=90)   # aprox por ciclo trimestral (doc 61 A4)
        dias_a_evento = max(0, (prox - hoy).days)

    precio_vs = None
    if precio_hist and len(precio_hist) >= 2 and precio_hist[0]:
        precio_vs = round(abs(precio_hist[-1] / precio_hist[0] - 1.0) * 100, 1)

    s = SenalesTriage(dias_desde_dossier=dias_dossier, hechos_nuevos=len(nuevos),
                      dias_a_evento=dias_a_evento, precio_vs_tesis_pct=precio_vs,
                      es_posicion=es_posicion, tiene_evento_fuerte=tiene_evento,
                      prioridad_cuello=prioridad_cuello)
    resumen = (" · ".join(f"{f.tipo} {f.fecha.date()}" for f in nuevos[:6])
               if nuevos else "")
    return s, resumen


def candidatos_del_universo(session: Session, *, hoy: date | None = None,
                            fechas_dossier: dict[str, date] | None = None,
                            posiciones: set[str] | None = None,
                            filings_fn=None, precio_hist_fn=None,
                            prioridad_fn=None) -> list[tuple[str, SenalesTriage, str]]:
    """Arma los `candidatos` (ticker, SenalesTriage, resumen) para `orquestador.correr_semana` desde todo el
    universo. Fuentes reales por default (EDGAR + market_data), inyectables para tests."""
    hoy = hoy or date.today()
    fechas_dossier = fechas_dossier or {}
    posiciones = {t.upper() for t in (posiciones or set())}
    if filings_fn is None:
        from backend.services.edgar import get_recent_filings
        # Solo filings MATERIALES (no Form 4 / insiders, que son ruido y dispararían análisis caro de gusto).
        filings_fn = lambda tk: get_recent_filings(  # noqa: E731
            tk, tipos=("10-K", "10-Q", "8-K", "S-1", "424B5", "6-K", "20-F"), dias=120)
    if precio_hist_fn is None:
        from backend.services.market_data import get_price_history
        precio_hist_fn = lambda tk: [d.get("close") for d in (get_price_history(tk, period="3mo") or [])  # noqa: E731
                                     if d.get("close")]
    prioridad_fn = prioridad_fn or (lambda _tk: 0)

    out: list[tuple[str, SenalesTriage, str]] = []
    for tk in tickers_universo(session):
        try:
            s, resumen = señales_ticker(
                tk, hoy=hoy, fecha_dossier=fechas_dossier.get(tk.upper()),
                filings=filings_fn(tk), precio_hist=precio_hist_fn(tk),
                es_posicion=tk.upper() in posiciones, prioridad_cuello=prioridad_fn(tk))
            out.append((tk.upper(), s, resumen))
        except Exception:  # noqa: BLE001 — un nombre que falla al traer señales no tumba el screening
            continue
    return out
