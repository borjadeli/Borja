"""Agente RESEARCH — monitoreo continuo (doc 02 sec 2 + doc 03 sec 4).

4 monitores deterministas que corren por scheduler. Solo producen eventos en
tabla `eventos`. NO activan agentes — eso lo hace el Dispatcher leyendo la cola.

Monitores:
1. Precios: cada hora L-V 9:30-16:00 ET. Portfolio + WL_Prioritaria.
2. Earnings: diario. Ventana ±3 días. Portfolio + WL_Prioritaria.
3. Form 4 (insider): diario. CEO/CFO filings. Portfolio + WL_Prioritaria.
4. Noticias: cada 4h. Todas excepto Eliminada/Suspendida. Keywords del doc 02 sec 2.1.

Todos son idempotentes: no crean eventos duplicados dentro de ventanas razonables.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_

from backend.database import session_scope
from backend.models import EstadoEvento, EstadoFicha, Evento, Ficha, TipoEvento
from backend.services import edgar, market_data, news
from backend.services.calculators import calculate_movement_pct
from backend.utils import get_logger, utcnow

log = get_logger(__name__)


# ---------- Constantes ----------

MOVIMIENTO_PRECIO_UMBRAL_PCT = 30.0
COOLDOWN_PRECIO_HORAS = 24
EARNINGS_VENTANA_DIAS = 3
FORM4_LOOKBACK_DIAS = 2
NOTICIAS_VENTANA_DIAS = 1

SCOPE_PORTFOLIO_WLP = [
    EstadoFicha.PORTFOLIO_ACTIVO.value,
    EstadoFicha.WL_PRIORITARIA.value,
]
SCOPE_EXCLUIR_NOTICIAS = [
    EstadoFicha.ELIMINADA.value,
    EstadoFicha.SUSPENDIDA.value,
]


# ---------- Monitor 1: Precios ----------

def monitor_precios() -> dict:
    """Detecta movimientos ≥30% vs precio_ultima_actualizacion_ficha, con cooldown 24h."""
    creados = []
    skipped_cooldown = []
    now = utcnow()

    with session_scope() as s:
        fichas = (
            s.query(Ficha)
            .filter(Ficha.estado.in_(SCOPE_PORTFOLIO_WLP))
            .all()
        )
        fichas_info = [(f.ticker, f.precio_ultima_actualizacion_ficha) for f in fichas]

    for ticker, precio_ref in fichas_info:
        if precio_ref is None:
            continue  # sin baseline — el Analista debe correr primero

        # Cooldown activo?
        with session_scope() as s:
            evento_activo = (
                s.query(Evento)
                .filter(
                    Evento.ticker == ticker,
                    Evento.tipo == TipoEvento.PRECIO_ALERTA.value,
                    Evento.cooldown_hasta > now,
                )
                .first()
            )
            if evento_activo:
                skipped_cooldown.append(ticker)
                continue

        snap = market_data.get_price_snapshot(ticker)
        if snap is None or snap.precio_actual is None:
            log.warning("monitor_precios: sin snapshot para %s", ticker)
            continue

        mov = calculate_movement_pct(precio_ref, snap.precio_actual)
        if mov is None or abs(mov) < MOVIMIENTO_PRECIO_UMBRAL_PCT:
            continue

        with session_scope() as s:
            direccion = "subió" if mov > 0 else "cayó"
            s.add(Evento(
                ticker=ticker,
                tipo=TipoEvento.PRECIO_ALERTA.value,
                descripcion=(
                    f"Precio {direccion} {abs(mov):.1f}% desde última actualización de ficha "
                    f"(${precio_ref:.2f} → ${snap.precio_actual:.2f})"
                ),
                fuente="Yahoo chart API",
                tier=1 if abs(mov) >= 50 else 2,
                cooldown_hasta=now + timedelta(hours=COOLDOWN_PRECIO_HORAS),
                timestamp=now,
                metadata_json={
                    "precio_referencia": precio_ref,
                    "precio_actual": snap.precio_actual,
                    "movimiento_pct": mov,
                },
            ))
            creados.append(ticker)

    log.info("monitor_precios — creados=%d cooldown=%d", len(creados), len(skipped_cooldown))
    return {"creados": creados, "skipped_cooldown": skipped_cooldown, "timestamp": now.isoformat()}


# ---------- Monitor 2: Earnings ----------

def monitor_earnings() -> dict:
    """Crea EARNINGS_PROXIMOS si la fecha está en ±3 días. Idempotente: dedup 5 días."""
    creados = []
    now = utcnow()

    with session_scope() as s:
        fichas = (
            s.query(Ficha)
            .filter(Ficha.estado.in_(SCOPE_PORTFOLIO_WLP))
            .all()
        )
        tickers = [f.ticker for f in fichas]

    for ticker in tickers:
        # Fase 1: fecha de earnings viene de EDGAR si hubo 8-K reciente, sino skip
        # yfinance earnings date es inestable; en Fase 2 con FMP será más preciso
        filings = edgar.get_recent_filings(ticker, tipos=("10-Q", "10-K"), dias=120)
        if not filings:
            continue

        # Estimar próxima fecha: último 10-Q/K + ~91 días (trimestre típico)
        ult = max(filings, key=lambda f: f.fecha)
        proxima_estimada = ult.fecha + timedelta(days=91)
        dias_hasta = (proxima_estimada - now).days

        if abs(dias_hasta) > EARNINGS_VENTANA_DIAS:
            continue

        # Dedup: ya hay evento EARNINGS en últimos 5 días?
        with session_scope() as s:
            dup = (
                s.query(Evento)
                .filter(
                    Evento.ticker == ticker,
                    Evento.tipo == TipoEvento.EARNINGS_PROXIMOS.value,
                    Evento.timestamp > now - timedelta(days=5),
                )
                .first()
            )
            if dup:
                continue

            s.add(Evento(
                ticker=ticker,
                tipo=TipoEvento.EARNINGS_PROXIMOS.value,
                descripcion=(
                    f"Earnings estimado {proxima_estimada.date().isoformat()} "
                    f"(±{EARNINGS_VENTANA_DIAS}d, base: último filing {ult.tipo} el {ult.fecha.date()})"
                ),
                fuente="EDGAR filings estimate",
                tier=1,
                timestamp=now,
                metadata_json={
                    "fecha_estimada": proxima_estimada.isoformat(),
                    "dias_hasta": dias_hasta,
                    "fuente_estimacion": f"{ult.tipo} {ult.accession_number}",
                },
            ))
            creados.append(ticker)

    log.info("monitor_earnings — creados=%d", len(creados))
    return {"creados": creados, "timestamp": now.isoformat()}


# ---------- Monitor 3: Form 4 (insider) ----------

def monitor_form4() -> dict:
    """Crea INSIDER_ACTIVITY si aparecen Form 4 nuevos en las últimas 48h."""
    creados = []
    now = utcnow()

    with session_scope() as s:
        tickers = [
            f.ticker for f in s.query(Ficha).filter(Ficha.estado.in_(SCOPE_PORTFOLIO_WLP)).all()
        ]

    for ticker in tickers:
        ins = edgar.get_insider_activity(ticker, dias=FORM4_LOOKBACK_DIAS)
        if not ins.transacciones:
            continue

        # Dedup: crear evento solo si el último Form 4 no fue ya reportado
        ultimo_accn = ins.transacciones[0].get("accn") if ins.transacciones else None
        with session_scope() as s:
            dup = (
                s.query(Evento)
                .filter(
                    Evento.ticker == ticker,
                    Evento.tipo == TipoEvento.INSIDER_ACTIVITY.value,
                    Evento.timestamp > now - timedelta(days=FORM4_LOOKBACK_DIAS),
                )
                .first()
            )
            if dup:
                # Si ya hay evento reciente y es el mismo accn → skip
                if dup.metadata_json and dup.metadata_json.get("ultimo_accn") == ultimo_accn:
                    continue

            s.add(Evento(
                ticker=ticker,
                tipo=TipoEvento.INSIDER_ACTIVITY.value,
                descripcion=f"{len(ins.transacciones)} Form 4 en últimas 48h. Último: {ultimo_accn}",
                fuente="SEC EDGAR",
                tier=2,
                timestamp=now,
                metadata_json={
                    "count": len(ins.transacciones),
                    "ultimo_accn": ultimo_accn,
                    "urls_recientes": [t.get("url", "") for t in ins.transacciones[:3]],
                },
            ))
            creados.append(ticker)

    log.info("monitor_form4 — creados=%d", len(creados))
    return {"creados": creados, "timestamp": now.isoformat()}


# ---------- Monitor 4: Noticias ----------

def monitor_noticias() -> dict:
    """Crea NOTICIA_MATERIAL por cada match de keywords. Dedup por URL en última semana."""
    creados = []
    skipped_dup = 0
    now = utcnow()

    with session_scope() as s:
        fichas = (
            s.query(Ficha)
            .filter(~Ficha.estado.in_(SCOPE_EXCLUIR_NOTICIAS))
            .all()
        )
        tickers_info = [(f.ticker, f.nombre) for f in fichas]

    for ticker, nombre in tickers_info:
        materiales = news.get_material_news(ticker, nombre=nombre, dias=NOTICIAS_VENTANA_DIAS)
        if not materiales:
            continue

        for item in materiales:
            if not item.url:
                continue

            # Dedup por URL en últimos 7 días
            with session_scope() as s:
                dup = (
                    s.query(Evento)
                    .filter(
                        Evento.ticker == ticker,
                        Evento.tipo == TipoEvento.NOTICIA_MATERIAL.value,
                        Evento.timestamp > now - timedelta(days=7),
                    )
                    .all()
                )
                urls_previas = {
                    (ev.metadata_json or {}).get("url") for ev in dup
                }
                if item.url in urls_previas:
                    skipped_dup += 1
                    continue

                tier = 1 if item.categoria == "negativo" else 2
                s.add(Evento(
                    ticker=ticker,
                    tipo=TipoEvento.NOTICIA_MATERIAL.value,
                    descripcion=f"[{item.categoria}] {item.titulo[:200]}",
                    fuente=item.fuente,
                    tier=tier,
                    timestamp=now,
                    metadata_json={
                        "url": item.url,
                        "publicado": item.publicado.isoformat(),
                        "categoria": item.categoria,
                        "keywords_match": item.keywords_match,
                    },
                ))
                creados.append(f"{ticker}: {item.categoria}")

    log.info("monitor_noticias — creados=%d dup_skipped=%d", len(creados), skipped_dup)
    return {"creados": creados, "skipped_dup": skipped_dup, "timestamp": now.isoformat()}


# ---------- Runner agregador ----------

def correr_todos_monitores() -> dict:
    """Ejecuta los 4 monitores secuencialmente. Usado por el scheduler y /research/run-manual."""
    resultado = {
        "inicio": utcnow().isoformat(),
        "precios": monitor_precios(),
        "earnings": monitor_earnings(),
        "form4": monitor_form4(),
        "noticias": monitor_noticias(),
    }
    resultado["fin"] = utcnow().isoformat()
    total_creados = (
        len(resultado["precios"]["creados"])
        + len(resultado["earnings"]["creados"])
        + len(resultado["form4"]["creados"])
        + len(resultado["noticias"]["creados"])
    )
    resultado["total_eventos_creados"] = total_creados
    return resultado
