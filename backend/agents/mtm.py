"""Mark-to-market intra-day — actualiza precio_mtm de Portfolio + WL_Prioritaria.

Determinista, sin LLM. Usa Yahoo chart vía services.market_data.

Frecuencia objetivo: cada 30 min en horario US market (10:00-16:00 ET, L-V).
También expone alertas cuando un ticker WLP entra a su entry_range por primera vez.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from backend import panic
from backend.database import session_scope
from backend.models import EstadoEvento, EstadoFicha, Evento, Ficha, TipoEvento
from backend.services import mailer
from backend.services.market_data import get_price_snapshot
from backend.utils import get_logger, utcnow

log = get_logger(__name__)


ESTADOS_A_TRACKEAR = [
    EstadoFicha.PORTFOLIO_ACTIVO.value,
    EstadoFicha.WL_PRIORITARIA.value,
    EstadoFicha.BUCKET_EXPLORATORIO.value,
]

# Cooldown entre alertas de entry_range para el mismo ticker (evita spam).
ENTRY_ALERT_COOLDOWN = timedelta(hours=24)


def _enviar_alerta_entry_range(
    ticker: str,
    precio: float,
    entry_min: float,
    entry_max: float,
    score: float | None,
    sector: str,
) -> None:
    """Envía email de alerta cuando un WLP entra en entry_range. Silencioso si SMTP no configurado."""
    body_html = f"""
    <h2 style='font-family: Georgia, serif;'>{ticker} en entry_range</h2>
    <p><strong>Precio actual:</strong> ${precio:.2f}</p>
    <p><strong>Entry range:</strong> ${entry_min:.2f} – ${entry_max:.2f}</p>
    <p><strong>Sector:</strong> {sector}</p>
    <p><strong>Score:</strong> {score if score is not None else 'N/D'}</p>
    <p>Revisar ficha para decidir entrada.</p>
    """
    try:
        mailer.send_email(
            subject=f"Entry range · {ticker} @ ${precio:.2f}",
            body_html=body_html,
            tag="ALERTA",
        )
    except Exception as e:  # noqa: BLE001
        log.warning("mtm — email entry_range %s falló: %s", ticker, e)


def actualizar_mtm() -> dict:
    """Trae precio actual de Portfolio + WLP + Bucket via Yahoo y persiste.

    Side effect: crea eventos PRECIO_ALERTA cuando un ticker WLP/Bucket cae dentro
    de su entry_range por primera vez (o tras cooldown de 24h).
    """
    if panic.esta_pausado():
        log.warning("mtm — sistema pausado, skip")
        return {"sistema_pausado": True, "actualizados": 0, "errores": 0}

    with session_scope() as s:
        tickers = [
            f.ticker
            for f in s.query(Ficha).filter(Ficha.estado.in_(ESTADOS_A_TRACKEAR)).all()
        ]

    log.info("mtm — arrancando — %d tickers", len(tickers))

    ok = 0
    errores: list[str] = []
    alertas_entry: list[str] = []
    detalle: list[dict] = []
    now = utcnow()

    for ticker in tickers:
        snap = get_price_snapshot(ticker)
        if snap is None or snap.precio_actual is None:
            errores.append(ticker)
            detalle.append({"ticker": ticker, "ok": False, "precio": None})
            continue

        with session_scope() as s:
            f = s.query(Ficha).filter_by(ticker=ticker).first()
            if f is None:
                continue
            f.precio_mtm = float(snap.precio_actual)
            f.precio_mtm_at = now

            # Alerta entry_range si aplica (solo WL_Prioritaria + Bucket).
            if (
                f.estado in (EstadoFicha.WL_PRIORITARIA.value, EstadoFicha.BUCKET_EXPLORATORIO.value)
                and f.entry_range_min is not None
                and f.entry_range_max is not None
                and f.entry_range_min <= snap.precio_actual <= f.entry_range_max
            ):
                last = f.entry_range_alerta_at
                if last is None or (now - last) >= ENTRY_ALERT_COOLDOWN:
                    f.entry_range_alerta_at = now
                    descripcion = (
                        f"Precio {snap.precio_actual:.2f} dentro de entry_range "
                        f"[{f.entry_range_min:.2f}, {f.entry_range_max:.2f}]. "
                        f"Score {f.score_vigente or '?'} · {f.sector}."
                    )
                    s.add(Evento(
                        ticker=ticker,
                        tipo=TipoEvento.PRECIO_ALERTA.value,
                        descripcion=descripcion,
                        fuente="mtm",
                        tier=1,
                        estado=EstadoEvento.PENDIENTE.value,
                        timestamp=now,
                    ))
                    alertas_entry.append(ticker)
                    _enviar_alerta_entry_range(
                        ticker=ticker,
                        precio=float(snap.precio_actual),
                        entry_min=f.entry_range_min,
                        entry_max=f.entry_range_max,
                        score=f.score_vigente,
                        sector=f.sector,
                    )

        ok += 1
        detalle.append({"ticker": ticker, "ok": True, "precio": float(snap.precio_actual)})

    resumen = {
        "actualizados": ok,
        "errores": len(errores),
        "tickers_error": errores,
        "alertas_entry": alertas_entry,
        "detalle": detalle,
    }
    log.info(
        "mtm — completado — actualizados=%d errores=%d alertas_entry=%d",
        ok, len(errores), len(alertas_entry),
    )
    return resumen
