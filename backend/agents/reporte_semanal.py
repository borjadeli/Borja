"""Reporte semanal del Juez (doc 03 sec 8.4).

Template determinista con datos estructurados + LLM solo para narrativa macro
si se detectan señales de cambio de fase.

Corre lunes 8:00 ET via scheduler. Envía email al admin.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func

from backend.agents import juez as juez_agent
from backend.database import session_scope
from backend.models import (
    EstadoAprobacion,
    EstadoFicha,
    Ficha,
    LLMCall,
    Macro,
    Recomendacion,
    Sector,
)
from backend.services import mailer
from backend.utils import get_logger, utcnow

log = get_logger(__name__)


def _semana_iso() -> str:
    year, week, _ = utcnow().isocalendar()
    return f"{year}-W{week:02d}"


def recopilar_datos() -> dict:
    """Agrega datos estructurados del estado actual del sistema."""
    now = utcnow()
    inicio_mes = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    with session_scope() as s:
        n_portfolio = s.query(Ficha).filter_by(estado=EstadoFicha.PORTFOLIO_ACTIVO.value).count()
        n_bucket = s.query(Ficha).filter_by(estado=EstadoFicha.BUCKET_EXPLORATORIO.value).count()
        exposicion = sum(
            (f.sizing_actual or 0)
            for f in s.query(Ficha).filter(Ficha.estado.in_([
                EstadoFicha.PORTFOLIO_ACTIVO.value, EstadoFicha.BUCKET_EXPLORATORIO.value,
            ])).all()
        )

        sectores = s.query(Sector).order_by(Sector.nombre).all()
        sectores_data = [
            {"nombre": sc.nombre, "momentum": sc.momentum, "prioridad": sc.prioridad}
            for sc in sectores
        ]

        macro = s.query(Macro).filter_by(activa=True).first()
        macro_fase = macro.fase_actual if macro else None
        macro_postura = macro.postura_capital if macro else None
        macro_version = macro.version if macro else None
        macro_notas = (macro.notas or "") if macro else ""

        recs = (
            s.query(Recomendacion)
            .filter(Recomendacion.estado_aprobacion == EstadoAprobacion.PENDIENTE.value)
            .order_by(Recomendacion.timestamp_juez.desc())
            .limit(15)
            .all()
        )
        recs_data = [
            {
                "ticker": r.ticker, "accion": r.accion,
                "sizing_sugerido": r.sizing_sugerido,
                "asimetria": r.asimetria_vigente,
                "estado_rec": r.estado_rec,
            }
            for r in recs
        ]

        costo_mes = s.query(func.coalesce(func.sum(LLMCall.cost_usd), 0.0)).filter(
            LLMCall.timestamp >= inicio_mes
        ).scalar() or 0.0

    risk_alertas = juez_agent.risk_monitor(notificar_email=False)
    process_items = juez_agent.process_auditor()

    # Estado general — heurística simple
    estado_general = "estable"
    if any(a.severidad == "alta" for a in risk_alertas):
        estado_general = "crítico"
    elif risk_alertas or len(process_items) > 5:
        estado_general = "atención requerida"

    return {
        "semana": _semana_iso(),
        "estado_general": estado_general,
        "kpis": {
            "n_portfolio": n_portfolio,
            "n_bucket": n_bucket,
            "exposicion": round(exposicion, 1),
            "n_risk_alertas": len(risk_alertas),
            "n_process_items": len(process_items),
            "n_recs_pendientes": len(recs_data),
            "costo_mes": round(costo_mes, 2),
        },
        "sectores": sectores_data,
        "risk_alertas": [
            {"tipo": a.tipo, "ticker": a.ticker, "severidad": a.severidad, "descripcion": a.descripcion}
            for a in risk_alertas
        ],
        "process_items": [
            {"tipo": i.tipo, "ticker": i.ticker, "descripcion": i.descripcion, "dias_vencido": i.dias_vencido}
            for i in process_items
        ],
        "recs_validadas": recs_data,
        "macro": {
            "fase": macro_fase, "postura": macro_postura, "version": macro_version, "notas": macro_notas,
        },
    }


def _detectar_senales_macro(datos: dict) -> bool:
    """True si hay señales que ameritan narrativa LLM. Por ahora simple: kill_switch + concentración alta."""
    kill = any(a["tipo"] == "KILL_SWITCH" for a in datos["risk_alertas"])
    conc = sum(1 for a in datos["risk_alertas"] if "CONCENTRACION" in a["tipo"])
    return kill or conc > 0


def generar_narrativa_llm(datos: dict, dry_run: bool = False) -> str | None:
    """Narrativa compleja con LLM solo si hay señales. En Sprint 6 lo dejamos como stub opcional
    — el template estructurado es suficiente para la primera versión."""
    if not _detectar_senales_macro(datos):
        return None
    # TODO: implementar narrativa con Claude cuando sea necesario.
    return None


def generar_reporte(dry_run_llm: bool = True, enviar_email: bool = True) -> dict:
    """Pipeline completo. Retorna dict con html + metadata."""
    datos = recopilar_datos()
    narrativa = generar_narrativa_llm(datos, dry_run=dry_run_llm)

    html = mailer.render_template(
        "reporte_semanal.html",
        semana=datos["semana"],
        estado_general=datos["estado_general"],
        kpis=datos["kpis"],
        sectores=datos["sectores"],
        risk_alertas=datos["risk_alertas"],
        process_items=datos["process_items"],
        recs_validadas=datos["recs_validadas"],
        narrativa_macro=narrativa,
    )

    mail_result = None
    if enviar_email:
        try:
            mail_result = mailer.reporte_semanal_email(html, datos["estado_general"])
        except Exception as e:  # noqa: BLE001
            log.error("reporte_semanal email fallo: %s", e)

    log.info("reporte_semanal generado — semana=%s estado=%s", datos["semana"], datos["estado_general"])
    return {
        "semana": datos["semana"],
        "estado_general": datos["estado_general"],
        "html": html,
        "html_chars": len(html),
        "email_enviado": mail_result.enviado if mail_result else False,
        "email_dry_run": mail_result.dry_run if mail_result else False,
        "narrativa_llm_usada": narrativa is not None,
    }
