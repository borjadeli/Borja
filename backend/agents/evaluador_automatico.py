"""Evaluador diario determinista de Portfolio + WL_Prioritaria.

Objetivo: cerrar el hueco entre "esperar evento de 30%+" y "re-evaluar con
precios frescos cada día". Corre SIN LLM — usa precio actual (yahoo chart) +
bull/bear de la ficha vigente + reglas del doc 01/02/03.

Frecuencia: diario post-cierre mercado (16:15 ET). Para cada ficha:
- Portfolio_Activo → evaluar_rotacion (puede ROTAR si asim <0.5x o red flags)
- WL_Prioritaria  → evaluar_entrada (puede ENTRAR si pasa r1+r2+r3 + hay slot)

Las recs VALIDADAS se auto-aprueban vía modo paper (recomendacion_runner).
Las CUESTIONADAS quedan pendientes — nunca se auto-aprueban.

No dispara nada si el sistema está pausado (panic).
"""
from __future__ import annotations

from dataclasses import dataclass

from backend import panic
from backend.agents.recomendacion_runner import ejecutar_recomendacion
from backend.database import session_scope
from backend.models import EstadoFicha, Ficha
from backend.utils import get_logger

log = get_logger(__name__)


ESTADOS_A_EVALUAR = [
    EstadoFicha.PORTFOLIO_ACTIVO.value,
    EstadoFicha.WL_PRIORITARIA.value,
]


@dataclass
class EvaluacionResult:
    ticker: str
    estado_pre: str
    accion: str
    estado_rec: str  # VALIDADA / CUESTIONADA
    auto_aprobada: bool
    asimetria_vigente: float | None
    error: str | None = None


def correr_evaluacion_diaria() -> dict:
    """Corre Portfolio+Juez sobre cada Portfolio_Activo y WL_Prioritaria.

    Retorna resumen agregado: cuántos se evaluaron, cuántas decisiones hubo,
    qué cambios se aplicaron. No consume Anthropic API.
    """
    if panic.esta_pausado():
        log.warning("evaluador_automatico — sistema pausado, skip")
        return {"sistema_pausado": True, "evaluados": 0}

    with session_scope() as s:
        tickers = [
            f.ticker
            for f in s.query(Ficha).filter(Ficha.estado.in_(ESTADOS_A_EVALUAR)).all()
        ]

    log.info("evaluador_automatico — arrancando — %d tickers a evaluar", len(tickers))

    resultados: list[EvaluacionResult] = []
    for ticker in tickers:
        # Tomamos el estado_pre fresco por si ya se movió durante la corrida
        # (ej: un rotar libera slot y otro entra).
        with session_scope() as s:
            f = s.query(Ficha).filter_by(ticker=ticker).first()
            if f is None:
                continue
            estado_pre = f.estado
            if estado_pre not in ESTADOS_A_EVALUAR:
                continue  # cambió de estado durante la corrida, skip

        try:
            res = ejecutar_recomendacion(ticker)
            resultados.append(EvaluacionResult(
                ticker=ticker,
                estado_pre=estado_pre,
                accion=res.get("accion", "?"),
                estado_rec=res.get("estado_rec", "?"),
                auto_aprobada=bool(res.get("auto_aprobada")),
                asimetria_vigente=res.get("asimetria_vigente"),
            ))
        except Exception as e:  # noqa: BLE001
            log.exception("evaluador_automatico — %s fallo: %s", ticker, e)
            resultados.append(EvaluacionResult(
                ticker=ticker, estado_pre=estado_pre, accion="ERROR",
                estado_rec="ERROR", auto_aprobada=False,
                asimetria_vigente=None, error=str(e),
            ))

    # Resumen por acción
    por_accion: dict[str, int] = {}
    aprobadas = 0
    for r in resultados:
        por_accion[r.accion] = por_accion.get(r.accion, 0) + 1
        if r.auto_aprobada:
            aprobadas += 1

    resumen = {
        "evaluados": len(resultados),
        "auto_aprobadas": aprobadas,
        "por_accion": por_accion,
        "detalle": [
            {
                "ticker": r.ticker,
                "estado_pre": r.estado_pre,
                "accion": r.accion,
                "estado_rec": r.estado_rec,
                "auto_aprobada": r.auto_aprobada,
                "asimetria_vigente": r.asimetria_vigente,
                "error": r.error,
            }
            for r in resultados
        ],
    }
    log.info(
        "evaluador_automatico — completado — evaluados=%d auto_aprobadas=%d por_accion=%s",
        resumen["evaluados"], resumen["auto_aprobadas"], por_accion,
    )
    return resumen
