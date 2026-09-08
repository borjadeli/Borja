"""Revalidación forzada cada 30 días (v4.2 sec 5).

Para cada posición Portfolio_Activo, cada 30 días el sistema pregunta:
'¿Seguís creyendo esta tesis? Sí/No'. Si NO → 5 preguntas obligatorias
(Discretionary Thesis Review).

El job NO bloquea la posición. Genera un evento + entrada en `revalidaciones`.
Si el humano responde NO sin las 5 preguntas, el endpoint las exige (400).
"""
from __future__ import annotations

from datetime import timedelta

from backend.database import session_scope
from backend.models import (
    EstadoEvento,
    EstadoFicha,
    Evento,
    Ficha,
    Revalidacion,
    TipoEvento,
)
from backend.utils import get_logger, utcnow

log = get_logger(__name__)


CICLO_REVALIDACION_DIAS = 30


PREGUNTAS_OBLIGATORIAS = (
    "p1_que_aprendi",
    "p2_supuesto_cambio",
    "p3_deterioro_o_precio",
    "p4_red_team_anticipo",
    "p5_trigger_faltante",
)


def detectar_revalidaciones_pendientes() -> dict:
    """Job diario: detecta Portfolio_Activo cuyo último ciclo de 30d se cumple.

    Crea Revalidacion(pendiente) + Evento de tipo NOTICIA_MATERIAL marca'revalidacion'.
    Idempotente: si ya hay una revalidación pendiente para el ticker, no crea otra.
    """
    now = utcnow()
    creadas: list[str] = []
    saltadas: list[str] = []

    with session_scope() as s:
        portfolio = (
            s.query(Ficha)
            .filter_by(estado=EstadoFicha.PORTFOLIO_ACTIVO.value)
            .all()
        )
        for f in portfolio:
            if f.fecha_entrada_portfolio is None:
                saltadas.append(f"{f.ticker} (sin fecha_entrada_portfolio)")
                continue

            # Ya hay revalidación pendiente?
            pendiente = (
                s.query(Revalidacion)
                .filter_by(ticker=f.ticker, estado="pendiente")
                .first()
            )
            if pendiente:
                saltadas.append(f"{f.ticker} (ya pendiente id={pendiente.id})")
                continue

            # Última revalidación contestada
            ult = (
                s.query(Revalidacion)
                .filter_by(ticker=f.ticker)
                .filter(Revalidacion.estado.in_(["si", "no"]))
                .order_by(Revalidacion.fecha_respuesta.desc())
                .first()
            )
            if ult and ult.fecha_respuesta:
                proximo = ult.fecha_respuesta + timedelta(days=CICLO_REVALIDACION_DIAS)
            else:
                proximo = f.fecha_entrada_portfolio + timedelta(days=CICLO_REVALIDACION_DIAS)

            if now < proximo:
                saltadas.append(f"{f.ticker} (próximo ciclo {proximo.date()})")
                continue

            rev = Revalidacion(ticker=f.ticker, timestamp=now, estado="pendiente")
            s.add(rev)
            s.add(Evento(
                ticker=f.ticker,
                tipo=TipoEvento.NOTICIA_MATERIAL.value,
                descripcion=f"Revalidación 30d obligatoria — ¿Seguís creyendo la tesis de {f.ticker}?",
                fuente="revalidacion_30d",
                tier=1,
                estado=EstadoEvento.PENDIENTE.value,
                timestamp=now,
                metadata_json={"tipo_evento_logico": "revalidacion_pendiente"},
            ))
            creadas.append(f.ticker)

    log.info("revalidacion — creadas=%d saltadas=%d", len(creadas), len(saltadas))
    return {"creadas": creadas, "saltadas": saltadas}


def responder_revalidacion(
    ticker: str,
    sigue_creyendo: bool,
    respuestas: dict | None = None,
    accion_decidida: str | None = None,
) -> dict:
    """Responde la revalidación pendiente más reciente del ticker.

    sigue_creyendo=True → estado='si', no requiere respuestas.
    sigue_creyendo=False → estado='no', exige las 5 respuestas.
    """
    if not sigue_creyendo:
        respuestas = respuestas or {}
        faltantes = [p for p in PREGUNTAS_OBLIGATORIAS if not (respuestas.get(p) or "").strip()]
        if faltantes:
            raise ValueError(f"5 preguntas obligatorias incompletas: {faltantes}")

    now = utcnow()
    with session_scope() as s:
        rev = (
            s.query(Revalidacion)
            .filter_by(ticker=ticker.upper(), estado="pendiente")
            .order_by(Revalidacion.id.desc())
            .first()
        )
        if rev is None:
            raise ValueError(f"sin revalidación pendiente para {ticker}")

        rev.estado = "si" if sigue_creyendo else "no"
        rev.fecha_respuesta = now
        if not sigue_creyendo:
            rev.p1_que_aprendi = respuestas.get("p1_que_aprendi")
            rev.p2_supuesto_cambio = respuestas.get("p2_supuesto_cambio")
            rev.p3_deterioro_o_precio = respuestas.get("p3_deterioro_o_precio")
            rev.p4_red_team_anticipo = respuestas.get("p4_red_team_anticipo")
            rev.p5_trigger_faltante = respuestas.get("p5_trigger_faltante")
            rev.accion_decidida = accion_decidida

        rev_id = rev.id

    # Log al decision journal
    from backend.agents.decision_journal import registrar_decision
    registrar_decision(
        accion=("revalidacion_si" if sigue_creyendo else "revalidacion_no"),
        ticker=ticker.upper(),
        decisor="humano",
        motivo=(accion_decidida if not sigue_creyendo else "tesis vigente"),
        metadata={"revalidacion_id": rev_id, "respuestas": respuestas if not sigue_creyendo else None},
    )
    return {"revalidacion_id": rev_id, "estado": "si" if sigue_creyendo else "no"}
