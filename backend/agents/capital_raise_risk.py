"""Capital Raise Risk — cálculo determinista (v4.2 sec 4 + 7 + traspaso Fase 0).

Para cada ficha activa, junta señales desde EDGAR (dilución 3y, runway, shelf
filings 24m, revenue growth, going concern en 10-K) y aplica
calculate_capital_raise_risk para obtener nivel (Bajo / Medio / Alto / Crítico)
+ multiplicador.

Fase 0 migración: going concern en el último 10-K → CRR-crítico EN ENTRADA
(fuga activa). Hoy era flag manual del filtro anti-fraude; ahora se detecta en
código vía edgar.detect_going_concern y fuerza Crítico → Eliminada.

Crítico → fail condition (estado pasa a Eliminada).
Alto → bloqueo de Portfolio formal (queda en Bucket o se elimina).
Medio/Bajo → multiplicador aplicado al sizing.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from backend.database import session_scope
from backend.models import EstadoFicha, Ficha
from backend.services import edgar
from backend.services.calculators import calculate_capital_raise_risk, calculate_runway
from backend.utils import get_logger, utcnow

log = get_logger(__name__)


ESTADOS_A_EVALUAR_CRR = [
    EstadoFicha.PORTFOLIO_ACTIVO.value,
    EstadoFicha.WL_PRIORITARIA.value,
    EstadoFicha.WL_ACTIVA.value,
    EstadoFicha.WL_SEGUIMIENTO.value,
    EstadoFicha.BUCKET_EXPLORATORIO.value,
]


def calcular_crr_ticker(ticker: str) -> dict | None:
    """Computa CRR para un ticker. Devuelve dict con nivel + multiplier + evidencia + datos.

    None si EDGAR no responde para ese ticker.
    """
    fin = edgar.get_financials_quarterly(ticker, periodos=8)
    runway = calculate_runway(fin.cash, fin.burn_rate_monthly)
    dilution = edgar.get_dilution_pct_3y(ticker)
    shelf_info = edgar.count_capital_raise_filings(ticker, dias=730)
    shelf_24m = shelf_info.get("shelf_total")
    growth_yoy = fin.organic_growth_yoy

    # Going concern en el último 10-K → fuga activa (traspaso Fase 0).
    gc = edgar.detect_going_concern(ticker)

    res = calculate_capital_raise_risk(
        dilution_pct_3y=dilution,
        runway_meses=runway,
        shelf_count_24m=shelf_24m,
        revenue_growth_yoy=growth_yoy,
        revenue_ttm=fin.revenue_ttm,
        going_concern=gc.get("detected", False),
    )

    # Reemplaza el motivo genérico de going concern por la evidencia con cita y
    # fecha del filing, para que el humano pueda verificar la auto-eliminación.
    if gc.get("detected") and gc.get("evidencia"):
        res["evidencia"] = [gc["evidencia"]] + [
            m for m in res["evidencia"] if "going concern" not in m
        ]
        res["datos"]["going_concern_filing"] = gc.get("filing_url")
    return res


def actualizar_crr_universo() -> dict:
    """Recalcula CRR de todas las fichas activas. Persiste en Ficha.

    Crítico → estado pasa a Eliminada (fail condition v4.2 sec 7).
    Alto → si está en Portfolio_Activo, deja flag pero NO mueve estado (humano decide).
    """
    with session_scope() as s:
        tickers = [
            f.ticker for f in s.query(Ficha)
            .filter(Ficha.estado.in_(ESTADOS_A_EVALUAR_CRR)).all()
        ]

    log.info("crr — arrancando — %d tickers", len(tickers))

    resumen = {"actualizados": 0, "errores": 0, "criticos": [], "altos": [], "detalle": []}
    now = utcnow()

    for t in tickers:
        try:
            res = calcular_crr_ticker(t)
        except Exception as e:  # noqa: BLE001
            log.warning("crr — %s falló: %s", t, e)
            resumen["errores"] += 1
            continue
        if res is None:
            resumen["errores"] += 1
            continue

        with session_scope() as s:
            f = s.query(Ficha).filter_by(ticker=t).first()
            if f is None:
                continue
            f.capital_raise_risk = res["nivel"]
            f.capital_raise_risk_evidencia = " | ".join(res["evidencia"]) or "sin señales adversas"
            f.capital_raise_risk_at = now

            # Crítico → fail condition (estado=Eliminada)
            if res["nivel"] == "Crítico" and f.estado != EstadoFicha.ELIMINADA.value:
                cambios = list(f.cambios_estado or [])
                cambios.append({
                    "timestamp": now.isoformat(),
                    "estado_anterior": f.estado,
                    "estado_nuevo": EstadoFicha.ELIMINADA.value,
                    "motivo": f"CRR Crítico: {f.capital_raise_risk_evidencia}",
                })
                f.cambios_estado = cambios
                f.estado = EstadoFicha.ELIMINADA.value
                resumen["criticos"].append(t)

            if res["nivel"] == "Alto":
                resumen["altos"].append(t)

        resumen["actualizados"] += 1
        resumen["detalle"].append({
            "ticker": t,
            "nivel": res["nivel"],
            "multiplier": res["multiplier"],
            "datos": res["datos"],
        })

    log.info(
        "crr — completado — actualizados=%d errores=%d criticos=%d altos=%d",
        resumen["actualizados"], resumen["errores"], len(resumen["criticos"]), len(resumen["altos"]),
    )
    return resumen
