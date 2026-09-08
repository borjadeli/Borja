"""Agente DISPATCHER — motor de reglas de routing (doc 03 sec 5).

Lee eventos pendientes de la tabla `eventos` y decide destino (qué agente corresponde)
según reglas fijas. Loguea cada decisión en `dispatch_log`. Marca el evento como
`procesado` o `descartado`.

**NO ejecuta los agentes** — solo decide y loguea. El Analista y el Portfolio se
disparan manualmente desde la UI ("Analizar" en la pantalla de eventos) o por el
humano vía endpoint. Esto mantiene human-in-the-loop y control de costo LLM.

Sprint siguiente (o producción) puede agregar un flag `auto_fire_earnings=True` para
que EARNINGS en Portfolio/WLP dispare el Analista automáticamente. Por ahora, conservador.

Cooldown: si el mismo ticker ya tuvo un dispatch material en los últimos 5 días hábiles,
los eventos subsiguientes NO-críticos se descartan con motivo COOLDOWN. Excepciones:
SHORT_REPORT, RED_FLAG, o NOTICIA_MATERIAL clasificada como BINARIO (categoría=negativo).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_

from backend.database import session_scope
from backend.models import (
    DispatchLog,
    EstadoEvento,
    EstadoFicha,
    Evento,
    Ficha,
    Sector,
    TipoEvento,
)
from backend.utils import get_logger, utcnow

log = get_logger(__name__)


# ---------- Constantes ----------

COOLDOWN_DIAS_HABILES = 5
SCOPE_PORTFOLIO_WLP = [
    EstadoFicha.PORTFOLIO_ACTIVO.value,
    EstadoFicha.WL_PRIORITARIA.value,
]


class Destino:
    ANALISTA_EARNINGS = "ANALISTA:modo_earnings"
    ANALISTA_ALERTA = "ANALISTA:modo_alerta"
    ANALISTA_ALERTA_URGENTE = "ANALISTA:modo_alerta_urgente"
    ANALISTA_JUEZ = "ANALISTA+JUEZ"
    PORTFOLIO = "PORTFOLIO"
    PORTFOLIO_JUEZ = "PORTFOLIO+JUEZ"
    ACTUALIZAR_SECTOR = "ACTUALIZAR_SECTOR"
    DESCARTADO = "DESCARTADO"


class Urgencia:
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"


TIPOS_INMUNES_COOLDOWN = {
    TipoEvento.SHORT_REPORT.value,
    TipoEvento.RED_FLAG.value,
    TipoEvento.EARNINGS_PROXIMOS.value,  # earnings es crítico — siempre pasa
}


@dataclass
class DispatchDecision:
    evento_id: int
    ticker: str
    tipo_evento: str
    tier: int
    destino: str
    urgencia: str
    regla_activada: str
    motivo: Optional[str] = None
    cooldown_activo: bool = False


# ---------- Reglas de routing ----------

def _es_binaria(evento: Evento) -> bool:
    """Aproximación de impacto BINARIO: categoría 'negativo' o tier==1."""
    if evento.tier == 1:
        return True
    meta = evento.metadata_json or {}
    return meta.get("categoria") == "negativo"


def aplicar_reglas(evento: Evento, ficha: Ficha | None) -> DispatchDecision:
    """Aplica las reglas en orden. Puro — sin side effects.

    Orden importa: las primeras que matchean ganan.
    """
    d = DispatchDecision(
        evento_id=evento.id,
        ticker=evento.ticker,
        tipo_evento=evento.tipo,
        tier=evento.tier,
        destino=Destino.DESCARTADO,
        urgencia=Urgencia.BAJA,
        regla_activada="R_default",
    )

    # Sin ficha → descartar (no debería pasar si Research solo usa fichas existentes)
    if ficha is None:
        d.regla_activada = "R_default: ficha no existe"
        return d

    # R2: SHORT_REPORT tier ≤ 2 → ANALISTA + JUEZ (alta urgencia, inmune a cooldown)
    if evento.tipo == TipoEvento.SHORT_REPORT.value and evento.tier <= 2:
        d.destino = Destino.ANALISTA_JUEZ
        d.urgencia = Urgencia.ALTA
        d.regla_activada = "R2: SHORT_REPORT tier<=2"
        return d

    # R4: RED_FLAG + Portfolio → PORTFOLIO + JUEZ (alta)
    if evento.tipo == TipoEvento.RED_FLAG.value and ficha.estado == EstadoFicha.PORTFOLIO_ACTIVO.value:
        d.destino = Destino.PORTFOLIO_JUEZ
        d.urgencia = Urgencia.ALTA
        d.regla_activada = "R4: RED_FLAG + Portfolio"
        return d

    # R1: EARNINGS + Portfolio/WLP → ANALISTA modo_earnings (alta)
    if evento.tipo == TipoEvento.EARNINGS_PROXIMOS.value and ficha.estado in SCOPE_PORTFOLIO_WLP:
        d.destino = Destino.ANALISTA_EARNINGS
        d.urgencia = Urgencia.ALTA
        d.regla_activada = "R1: EARNINGS + Portfolio/WLP"
        return d

    # R3: NOTICIA_MATERIAL binaria + Portfolio/WLP → ANALISTA urgente + PORTFOLIO (alta)
    if evento.tipo == TipoEvento.NOTICIA_MATERIAL.value and ficha.estado in SCOPE_PORTFOLIO_WLP and _es_binaria(evento):
        d.destino = Destino.ANALISTA_ALERTA_URGENTE
        d.urgencia = Urgencia.ALTA
        d.regla_activada = "R3: NOTICIA binaria + Portfolio/WLP"
        return d

    # R5: NOTICIA_MATERIAL no-binaria + Portfolio → PORTFOLIO (media)
    if evento.tipo == TipoEvento.NOTICIA_MATERIAL.value and ficha.estado == EstadoFicha.PORTFOLIO_ACTIVO.value:
        d.destino = Destino.PORTFOLIO
        d.urgencia = Urgencia.MEDIA
        d.regla_activada = "R5: NOTICIA no-binaria + Portfolio"
        return d

    # R6: PRECIO_ALERTA + Portfolio → PORTFOLIO con verificación de asimetría
    if evento.tipo == TipoEvento.PRECIO_ALERTA.value and ficha.estado == EstadoFicha.PORTFOLIO_ACTIVO.value:
        d.destino = Destino.PORTFOLIO
        d.urgencia = Urgencia.MEDIA
        d.regla_activada = "R6: PRECIO + Portfolio (verificacion_asimetria)"
        return d

    # R6b: PRECIO_ALERTA + WLP → humano decide (por defecto, DESCARTADO con flag)
    if evento.tipo == TipoEvento.PRECIO_ALERTA.value and ficha.estado == EstadoFicha.WL_PRIORITARIA.value:
        d.destino = Destino.DESCARTADO
        d.urgencia = Urgencia.MEDIA
        d.regla_activada = "R6b: PRECIO + WLP — humano decide (evento visible)"
        return d

    # INSIDER_ACTIVITY → si Portfolio/WLP, ruta a PORTFOLIO para reevaluar
    if evento.tipo == TipoEvento.INSIDER_ACTIVITY.value and ficha.estado in SCOPE_PORTFOLIO_WLP:
        d.destino = Destino.PORTFOLIO
        d.urgencia = Urgencia.BAJA
        d.regla_activada = "R5b: INSIDER + Portfolio/WLP"
        return d

    # R7: MOMENTUM_SECTORIAL → actualizar tabla sectores (no tiene ticker único)
    if evento.tipo == TipoEvento.MOMENTUM_SECTORIAL.value:
        d.destino = Destino.ACTUALIZAR_SECTOR
        d.urgencia = Urgencia.BAJA
        d.regla_activada = "R7: MOMENTUM_SECTORIAL"
        return d

    # SCORE_DRIFT → no route (ya está visible; humano lo ve en dashboard)
    if evento.tipo == TipoEvento.SCORE_DRIFT.value:
        d.destino = Destino.DESCARTADO
        d.urgencia = Urgencia.MEDIA
        d.regla_activada = "R_drift: SCORE_DRIFT — solo alerta visible"
        return d

    # Default: sin regla aplicable
    d.destino = Destino.DESCARTADO
    d.urgencia = Urgencia.BAJA
    d.regla_activada = "R_default: sin regla para este tipo+estado"
    return d


# ---------- Cooldown ----------

def _cooldown_activo(session, ticker: str, tipo_evento: str, now: datetime) -> bool:
    """True si hubo dispatch no-descartado en los últimos 5 días hábiles Y el tipo no es inmune."""
    if tipo_evento in TIPOS_INMUNES_COOLDOWN:
        return False

    # 5 días hábiles ≈ 7 días naturales (ajustable)
    cutoff = now - timedelta(days=7)
    existe = (
        session.query(DispatchLog)
        .filter(
            DispatchLog.ticker_o_sector == ticker,
            DispatchLog.timestamp > cutoff,
            DispatchLog.destino != Destino.DESCARTADO,
            # Si el dispatch previo era sobre evento inmune, no cuenta para cooldown
            ~DispatchLog.tipo_evento.in_(list(TIPOS_INMUNES_COOLDOWN)),
        )
        .first()
    )
    return existe is not None


# ---------- Pipeline principal ----------

def dispatch_evento(evento_id: int) -> DispatchDecision:
    """Dispatcha un evento específico. Actualiza estado + loguea en dispatch_log."""
    now = utcnow()
    with session_scope() as s:
        ev = s.get(Evento, evento_id)
        if ev is None:
            raise ValueError(f"evento {evento_id} no existe")
        if ev.estado != EstadoEvento.PENDIENTE.value:
            raise ValueError(f"evento {evento_id} ya está {ev.estado}")

        ficha = s.query(Ficha).filter_by(ticker=ev.ticker).first()

        decision = aplicar_reglas(ev, ficha)

        # Chequeo de cooldown (solo si la decisión iba a rutear algo)
        if decision.destino != Destino.DESCARTADO:
            if _cooldown_activo(s, ev.ticker, ev.tipo, now):
                decision.cooldown_activo = True
                decision.motivo = f"COOLDOWN: dispatch previo material <{COOLDOWN_DIAS_HABILES}d"
                decision.destino = Destino.DESCARTADO
                decision.regla_activada = f"COOLDOWN (descarta {decision.regla_activada})"

        # Persistir decisión
        s.add(DispatchLog(
            timestamp=now,
            ticker_o_sector=ev.ticker,
            tipo_evento=ev.tipo,
            tier_fuente=ev.tier,
            regla_activada=decision.regla_activada,
            destino=decision.destino,
            urgencia=decision.urgencia,
            motivo=decision.motivo,
            cooldown_activo=decision.cooldown_activo,
            evento_id=ev.id,
        ))

        # Actualizar estado del evento
        if decision.destino == Destino.DESCARTADO:
            ev.estado = EstadoEvento.DESCARTADO.value
        else:
            ev.estado = EstadoEvento.PROCESADO.value

    log.info(
        "DISPATCHER — evento=%d ticker=%s tipo=%s destino=%s urgencia=%s regla=%s",
        evento_id, decision.ticker, decision.tipo_evento,
        decision.destino, decision.urgencia, decision.regla_activada,
    )
    return decision


def procesar_cola_eventos(limit: int = 200) -> dict:
    """Procesa todos los eventos pendientes aplicando reglas de routing."""
    now = utcnow()
    with session_scope() as s:
        pendientes_ids = [
            ev.id for ev in
            s.query(Evento)
            .filter(Evento.estado == EstadoEvento.PENDIENTE.value)
            .order_by(Evento.timestamp.asc())
            .limit(limit)
            .all()
        ]

    decisiones = []
    for eid in pendientes_ids:
        try:
            d = dispatch_evento(eid)
            decisiones.append(d)
        except Exception as e:
            log.exception("error dispatch evento %d: %s", eid, e)

    resumen = {
        "total_procesados": len(decisiones),
        "por_destino": {},
        "timestamp": now.isoformat(),
    }
    for d in decisiones:
        resumen["por_destino"][d.destino] = resumen["por_destino"].get(d.destino, 0) + 1
    log.info("dispatcher — procesados=%d por_destino=%s", len(decisiones), resumen["por_destino"])
    return resumen
