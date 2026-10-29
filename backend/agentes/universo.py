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

from backend.agentes.embudo import es_red_flag, eventos_materiales_desde, precio_z
from backend.agentes.triage import SenalesTriage
from backend.ledger.models import NxEmpresa

# Estados de nx_empresa que NO entran al embudo (fuera de juego). El resto (Candidata, etc.) se screenea.
_ESTADOS_INACTIVOS = {"descartada", "cerrada", "salida", "vendida"}


def tickers_universo(session: Session) -> list[str]:
    rows = session.execute(select(NxEmpresa.ticker, NxEmpresa.estado)).all()
    return [t for t, e in rows if (e or "").lower() not in _ESTADOS_INACTIVOS]


def contexto_mapa(session: Session, ticker: str) -> str:
    """Contexto del CUELLO desde `nx_*` para el Analista (r3 #5): nodo primario (nombre, cluster, factor
    macro, estado de confirmación) + las empresas vinculadas al mismo nodo (dependencias/competencia).
    Texto plano; "" si el nombre no está mapeado. NO inventa — sale del mapa poblado en Fase 2."""
    from backend.ledger.models import NxEmpresaNodo, NxNodo
    tk = ticker.upper()
    fila = session.execute(
        select(NxNodo).join(NxEmpresaNodo, NxEmpresaNodo.nodo_id == NxNodo.id)
        .where(NxEmpresaNodo.ticker == tk)
        .order_by(NxEmpresaNodo.es_primario.desc(), NxNodo.id)).scalars().first()
    if fila is None:
        return ""
    vinculadas = session.execute(
        select(NxEmpresaNodo.ticker).where(NxEmpresaNodo.nodo_id == fila.id,
                                           NxEmpresaNodo.ticker != tk)).scalars().all()
    partes = [f"CUELLO: {fila.nombre}"]
    if fila.cluster:
        partes.append(f"cluster={fila.cluster}")
    if fila.factor_macro:
        partes.append(f"factor macro={fila.factor_macro}")
    partes.append(f"estado del cuello={fila.estado_confirmacion}")
    if vinculadas:
        partes.append(f"empresas en el mismo cuello (competencia/dependencia): {', '.join(vinculadas[:12])}")
    return " · ".join(partes)


# Cursor de monitoreo inicial para empresas NUNCA analizadas (doc 64 §A1 bug): known_at=null NO puede
# significar "todo el historial es nuevo" (dispararía el universo entero). Un nombre nuevo mira solo los
# eventos materiales de los últimos N días, no toda su vida de filings.
VENTANA_MONITOREO_INICIAL_DIAS = 30


def señales_ticker(ticker: str, *, hoy: date, fecha_dossier: date | None, filings: list,
                   precio_hist: list[float] | None, es_posicion: bool,
                   prioridad_cuello: int = 0, mercado_hist: list[float] | None = None) -> tuple[SenalesTriage, str]:
    """Señales DETERMINISTAS + resumen de eventos materiales nuevos. `filings` = RecentFiling (.tipo/.fecha/
    .items); `precio_hist` = serie de cierres. Usa la whitelist de materialidad del embudo (no todo filing)."""
    dias_dossier = (hoy - fecha_dossier).days if fecha_dossier else None
    # Cursor: si ya hubo dossier, eventos POSTERIORES a él; si nunca se analizó, solo la ventana reciente.
    cursor = fecha_dossier if fecha_dossier is not None else hoy - timedelta(days=VENTANA_MONITOREO_INICIAL_DIAS)
    nuevos = eventos_materiales_desde(filings, desde=cursor)
    tiene_evento = any(es_red_flag(f) for f in nuevos) or len(nuevos) > 0

    periodicos = sorted((f for f in (filings or []) if f.tipo in ("10-Q", "10-K")), key=lambda f: f.fecha)
    dias_a_evento = None
    if periodicos:
        prox = periodicos[-1].fecha.date() + timedelta(days=90)   # aprox por ciclo (solo para DIFERIR, doc 64 A4)
        dias_a_evento = max(0, (prox - hoy).days)

    # precio_vs_tesis_pct = movimiento residual normalizado |z| (doc 64 A1), no el % crudo. El % absoluto
    # va como respaldo en el resumen. El Triage/embudo usa este z (más bajo para posiciones).
    precio_vs = precio_z(precio_hist, mercado_hist=mercado_hist)
    pct_abs = (round(abs(precio_hist[-1] / precio_hist[0] - 1.0) * 100, 1)
               if precio_hist and len(precio_hist) >= 2 and precio_hist[0] else None)

    s = SenalesTriage(dias_desde_dossier=dias_dossier, hechos_nuevos=len(nuevos),
                      dias_a_evento=dias_a_evento, precio_vs_tesis_pct=precio_vs,
                      es_posicion=es_posicion, tiene_evento_fuerte=tiene_evento,
                      prioridad_cuello=prioridad_cuello)
    partes = [f"{f.tipo}{'/' + f.items if getattr(f, 'items', '') else ''} {f.fecha.date()}"
              for f in nuevos[:6]]
    if precio_vs is not None and pct_abs is not None:
        partes.append(f"precio z={precio_vs} ({pct_abs:+.0f}%)")
    return s, " · ".join(partes)


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
        # Se traen TODOS los tipos candidatos a material; la whitelist fina por ÍTEM la aplica el embudo.
        filings_fn = lambda tk: get_recent_filings(  # noqa: E731
            tk, tipos=("10-K", "10-Q", "10-K/A", "10-Q/A", "8-K", "S-1", "S-3", "424B5", "SC 13D",
                       "NT 10-K", "NT 10-Q", "6-K", "20-F"), dias=120)
    if precio_hist_fn is None:
        from backend.services.market_data import get_price_history
        precio_hist_fn = lambda tk: [d.get("close") for d in (get_price_history(tk, period="3mo") or [])  # noqa: E731
                                     if d.get("close")]
    prioridad_fn = prioridad_fn or (lambda _tk: 0)

    # Serie de mercado (IWM = small caps) UNA vez por corrida, para el residual del precio (β). Si falla → None.
    mercado = None
    try:
        mercado = precio_hist_fn("IWM") or None
    except Exception:  # noqa: BLE001
        mercado = None

    out: list[tuple[str, SenalesTriage, str]] = []
    for tk in tickers_universo(session):
        try:
            ph = precio_hist_fn(tk)
            merc = mercado if (mercado and ph and len(mercado) == len(ph)) else None
            s, resumen = señales_ticker(
                tk, hoy=hoy, fecha_dossier=fechas_dossier.get(tk.upper()),
                filings=filings_fn(tk), precio_hist=ph, mercado_hist=merc,
                es_posicion=tk.upper() in posiciones, prioridad_cuello=prioridad_fn(tk))
            out.append((tk.upper(), s, resumen))
        except Exception:  # noqa: BLE001 — un nombre que falla al traer señales no tumba el screening
            continue
    return out
