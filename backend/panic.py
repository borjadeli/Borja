"""Kill switch global — pausa todo el sistema en una sola operación.

Casos de uso (Tier 1 hardening):
- Mercado en crash / evento sistémico inesperado
- Descubrís un bug en el sistema que puede estar generando recomendaciones malas
- Querés cortar la operación sin apagar manualmente cada agente

Al pausar:
- Se detiene el scheduler (los 8 jobs)
- Todas las recomendaciones pendientes se marcan con motivo "PAUSA GLOBAL"
- Nuevas corridas del Analista/Portfolio/Juez chequean el flag y rechazan
- El humano ve en Dashboard una banda roja fija hasta que reanuda

Al reanudar:
- El scheduler vuelve a arrancar
- Las recomendaciones previas NO se deshacen (siguen cuestionadas)
- El humano decide qué hacer con cada una

El estado se persiste en tabla `system_config` (nueva) para sobrevivir reinicios.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import session_scope
from backend.models import Base
from backend.utils import get_logger, utcnow

log = get_logger(__name__)


class SystemConfig(Base):
    """Configuración global del sistema — singleton row (id=1)."""
    __tablename__ = "system_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    sistema_pausado: Mapped[bool] = mapped_column(default=False)
    pausa_motivo: Mapped[str | None] = mapped_column(String(512), nullable=True)
    pausa_timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pausa_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reanudacion_timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    historial: Mapped[list] = mapped_column(JSON, default=list)
    # Paper trading / capital virtual (Tier 2 — pre go-live)
    capital_total_usd: Mapped[float] = mapped_column(default=0.0)
    modo_paper_trading: Mapped[bool] = mapped_column(default=True)
    auto_aprobar_paper: Mapped[bool] = mapped_column(default=False)


def _get_or_create_config():
    with session_scope() as s:
        c = s.get(SystemConfig, 1)
        if c is None:
            c = SystemConfig(id=1, sistema_pausado=False, historial=[],
                            capital_total_usd=0.0, modo_paper_trading=True)
            s.add(c)
            s.flush()
        return {
            "sistema_pausado": c.sistema_pausado,
            "pausa_motivo": c.pausa_motivo,
            "pausa_timestamp": c.pausa_timestamp.isoformat() if c.pausa_timestamp else None,
            "pausa_by": c.pausa_by,
            "reanudacion_timestamp": c.reanudacion_timestamp.isoformat() if c.reanudacion_timestamp else None,
            "historial": list(c.historial or []),
            "capital_total_usd": c.capital_total_usd or 0.0,
            "modo_paper_trading": bool(c.modo_paper_trading),
            "auto_aprobar_paper": bool(c.auto_aprobar_paper),
        }


def auto_aprobar_habilitado() -> bool:
    """True solo si modo_paper_trading Y auto_aprobar_paper están activos. Safe-by-default."""
    try:
        e = _get_or_create_config()
        return bool(e.get("modo_paper_trading")) and bool(e.get("auto_aprobar_paper"))
    except Exception:
        return False


def set_auto_aprobar(activo: bool) -> dict:
    """Toggle auto-aprobación. Solo tiene efecto en modo_paper_trading=True."""
    with session_scope() as s:
        c = s.get(SystemConfig, 1)
        if c is None:
            c = SystemConfig(id=1, historial=[])
            s.add(c)
            s.flush()
        if activo and not c.modo_paper_trading:
            return {"ok": False, "motivo": "auto_aprobar solo disponible en modo_paper_trading"}
        c.auto_aprobar_paper = bool(activo)
        hist = list(c.historial or [])
        hist.append({
            "evento": "auto_aprobar_toggle",
            "timestamp": utcnow().isoformat(),
            "activo": bool(activo),
        })
        c.historial = hist
    log.warning("AUTO-APROBACIÓN %s — se aprobarán automáticamente recomendaciones VALIDADAS en modo paper",
                "ACTIVADA" if activo else "DESACTIVADA")
    return {"ok": True, "auto_aprobar_paper": bool(activo)}


def set_capital(capital_usd: float, modo_paper: bool = True) -> dict:
    """Setea el capital de referencia (virtual para paper trading)."""
    with session_scope() as s:
        c = s.get(SystemConfig, 1)
        if c is None:
            c = SystemConfig(id=1, historial=[])
            s.add(c)
            s.flush()
        c.capital_total_usd = float(capital_usd)
        c.modo_paper_trading = bool(modo_paper)
        hist = list(c.historial or [])
        hist.append({
            "evento": "capital_set",
            "timestamp": utcnow().isoformat(),
            "capital_usd": capital_usd,
            "modo_paper": modo_paper,
        })
        c.historial = hist
    log.info("capital configurado — $%.2f USD · modo_paper=%s", capital_usd, modo_paper)
    return {"ok": True, "capital_total_usd": capital_usd, "modo_paper_trading": modo_paper}


def estado() -> dict:
    return _get_or_create_config()


def esta_pausado() -> bool:
    """Helper rápido para chequear si el sistema está en modo pausa. Usado por agentes."""
    try:
        return _get_or_create_config()["sistema_pausado"]
    except Exception:  # noqa: BLE001
        return False


def pausar(motivo: str = "manual", by: str = "admin") -> dict:
    """Pausa el sistema completo. Detiene scheduler + marca recomendaciones pendientes."""
    now = utcnow()
    with session_scope() as s:
        c = s.get(SystemConfig, 1)
        if c is None:
            c = SystemConfig(id=1, historial=[])
            s.add(c)
            s.flush()
        if c.sistema_pausado:
            return {"ok": False, "motivo": "sistema ya estaba pausado"}
        c.sistema_pausado = True
        c.pausa_motivo = motivo
        c.pausa_timestamp = now
        c.pausa_by = by
        hist = list(c.historial or [])
        hist.append({
            "evento": "pausa",
            "timestamp": now.isoformat(),
            "motivo": motivo,
            "by": by,
        })
        c.historial = hist

    # Detener scheduler
    try:
        from backend import scheduler as sch
        sch.stop()
        log.warning("PANIC — sistema pausado, scheduler detenido. motivo=%s", motivo)
    except Exception as e:  # noqa: BLE001
        log.error("PANIC — no pude detener scheduler: %s", e)

    # Marcar recomendaciones pendientes con flag (sin cambiar estado — humano decide)
    try:
        from backend.models import EstadoAprobacion, Recomendacion
        with session_scope() as s:
            pendientes = s.query(Recomendacion).filter_by(
                estado_aprobacion=EstadoAprobacion.PENDIENTE.value
            ).all()
            for r in pendientes:
                prev = r.motivo_cuestionada or ""
                r.motivo_cuestionada = f"[PAUSA GLOBAL {now.strftime('%Y-%m-%d %H:%M')}] {prev}".strip()
            n = len(pendientes)
        log.warning("PANIC — %d recomendaciones pendientes marcadas con flag de pausa", n)
    except Exception as e:  # noqa: BLE001
        log.error("PANIC — fallo marcando recomendaciones: %s", e)

    return {
        "ok": True,
        "sistema_pausado": True,
        "motivo": motivo,
        "timestamp": now.isoformat(),
    }


def reanudar(by: str = "admin") -> dict:
    """Reanuda el sistema. Scheduler vuelve a arrancar. Recomendaciones siguen cuestionadas."""
    now = utcnow()
    with session_scope() as s:
        c = s.get(SystemConfig, 1)
        if c is None or not c.sistema_pausado:
            return {"ok": False, "motivo": "sistema no estaba pausado"}
        c.sistema_pausado = False
        c.reanudacion_timestamp = now
        hist = list(c.historial or [])
        hist.append({
            "evento": "reanudacion",
            "timestamp": now.isoformat(),
            "by": by,
        })
        c.historial = hist

    # Arrancar scheduler automáticamente
    try:
        from backend import scheduler as sch
        sch.start()
        log.info("PANIC — sistema reanudado, scheduler activo")
    except Exception as e:  # noqa: BLE001
        log.error("PANIC — fallo al arrancar scheduler: %s", e)

    return {"ok": True, "sistema_pausado": False, "timestamp": now.isoformat()}
