"""Script Nocturno — cron 6:00 AM ET diario (doc 02 sec 6).

Verificaciones deterministas + limpieza. Sin LLM. Todas las alertas quedan visibles
en Dashboard vía los endpoints GET /juez/process y GET /eventos.

Checks:
1. Entry ranges vencidos → WL_Prioritaria pasa a WL_Activa + alerta.
2. Triggers sin evaluar hace >7 días en Portfolio/WLP → alerta visible.
3. Deep research vencido (fecha_proximo_deep_research < hoy) → alerta.
4. Sectores sin actualizar hace >10 días → alerta.
5. Mapas sectoriales vencidos (Sprint 4) → dispara regeneración.
6. Limpieza de eventos procesados/descartados >90 días.
7. Eliminar tasks completados/fallidos antiguos >30 días.
"""
from __future__ import annotations

from datetime import timedelta

from backend.database import session_scope
from backend.models import (
    EstadoEvento,
    EstadoFicha,
    EstadoTask,
    Evento,
    Ficha,
    Sector,
    SectorMapa,
    Task,
)
from backend.utils import get_logger, utcnow

log = get_logger(__name__)


LIMPIEZA_EVENTOS_DIAS = 90
LIMPIEZA_TASKS_DIAS = 30
SECTOR_SIN_ACTUALIZAR_DIAS = 10
TRIGGERS_SIN_EVALUAR_DIAS = 7


def verificar_entry_ranges() -> list[dict]:
    """WL_Prioritaria con entry_range_vencimiento < hoy → pasa a WL_Activa."""
    cambios = []
    now = utcnow()
    with session_scope() as s:
        fichas = (
            s.query(Ficha)
            .filter(
                Ficha.estado == EstadoFicha.WL_PRIORITARIA.value,
                Ficha.entry_range_vencimiento.isnot(None),
                Ficha.entry_range_vencimiento < now,
            )
            .all()
        )
        for f in fichas:
            cambios.append({
                "ticker": f.ticker,
                "entry_range_vencimiento": f.entry_range_vencimiento.isoformat(),
                "estado_anterior": f.estado,
                "estado_nuevo": EstadoFicha.WL_ACTIVA.value,
            })
            hist = list(f.cambios_estado or [])
            hist.append({
                "timestamp": now.isoformat(),
                "estado_anterior": f.estado,
                "estado_nuevo": EstadoFicha.WL_ACTIVA.value,
                "motivo": "entry_range vencido — script nocturno",
            })
            f.cambios_estado = hist
            f.estado = EstadoFicha.WL_ACTIVA.value
    return cambios


def triggers_sin_evaluar() -> list[dict]:
    """Fichas Portfolio/WLP con ultima_evaluacion_triggers hace >7 días."""
    items = []
    now = utcnow()
    cutoff = now - timedelta(days=TRIGGERS_SIN_EVALUAR_DIAS)
    with session_scope() as s:
        fichas = (
            s.query(Ficha)
            .filter(
                Ficha.estado.in_([
                    EstadoFicha.PORTFOLIO_ACTIVO.value,
                    EstadoFicha.WL_PRIORITARIA.value,
                ]),
                Ficha.ultima_evaluacion_triggers.isnot(None),
                Ficha.ultima_evaluacion_triggers < cutoff,
            )
            .all()
        )
        for f in fichas:
            dias = (now - f.ultima_evaluacion_triggers).days
            items.append({
                "ticker": f.ticker,
                "ultima_evaluacion": f.ultima_evaluacion_triggers.isoformat(),
                "dias_sin_revisar": dias,
            })
    return items


def deep_research_vencido() -> list[dict]:
    """Fichas con fecha_proximo_deep_research < hoy."""
    items = []
    now = utcnow()
    with session_scope() as s:
        fichas = (
            s.query(Ficha)
            .filter(
                Ficha.estado.in_([
                    EstadoFicha.PORTFOLIO_ACTIVO.value,
                    EstadoFicha.WL_PRIORITARIA.value,
                    EstadoFicha.WL_ACTIVA.value,
                ]),
                Ficha.fecha_proximo_deep_research.isnot(None),
                Ficha.fecha_proximo_deep_research < now,
            )
            .all()
        )
        for f in fichas:
            dias_venc = (now - f.fecha_proximo_deep_research).days
            items.append({
                "ticker": f.ticker,
                "estado": f.estado,
                "dias_vencido": dias_venc,
                "proximo_dr": f.fecha_proximo_deep_research.isoformat(),
            })
    return items


def sectores_sin_actualizar() -> list[dict]:
    """Sectores cuyo momentum no se actualizó hace >10 días."""
    items = []
    now = utcnow()
    cutoff = now - timedelta(days=SECTOR_SIN_ACTUALIZAR_DIAS)
    with session_scope() as s:
        sectores = s.query(Sector).filter(Sector.ultima_actualizacion < cutoff).all()
        for sec in sectores:
            dias = (now - sec.ultima_actualizacion).days
            items.append({
                "sector": sec.nombre,
                "dias_sin_actualizar": dias,
                "momentum_actual": sec.momentum,
            })
    return items


def mapas_sectoriales_vencidos(regenerar: bool = True) -> list[dict]:
    """Detecta mapas activos vencidos. Si regenerar=True, dispara regeneración vía Claude+web search.

    Reporta los vencidos y (si regenerar=True) ejecuta `mapa_sectorial.regenerar_si_vencido`,
    que solo regenera mapas de sectores con fichas activas (Portfolio/WLP/WL_Activa).
    """
    items = []
    now = utcnow()
    with session_scope() as s:
        mapas = s.query(SectorMapa).filter(SectorMapa.estado == "activo").all()
        for m in mapas:
            vencimiento = m.fecha_generacion + timedelta(days=m.dias_vencimiento)
            if vencimiento < now:
                items.append({
                    "sector": m.sector,
                    "fecha_generacion": m.fecha_generacion.isoformat(),
                    "dias_vencimiento": m.dias_vencimiento,
                    "dias_atraso": (now - vencimiento).days,
                })

    # Disparar regeneración (Sprint 4 en adelante)
    if regenerar and items:
        try:
            from backend.agents.mapa_sectorial import regenerar_si_vencido
            resultado_regen = regenerar_si_vencido()
            log.info(
                "script_nocturno — regenerados=%d omitidos_aprobados=%d errores=%d",
                len(resultado_regen.get("regenerados", [])),
                len(resultado_regen.get("omitidos_aprobados", [])),
                len(resultado_regen.get("errores", [])),
            )
            # Marcar items con info de regeneración
            regenerados_sectores = {r["sector"] for r in resultado_regen.get("regenerados", [])}
            for item in items:
                item["regenerado"] = item["sector"] in regenerados_sectores
        except Exception as e:  # noqa: BLE001
            log.exception("script_nocturno — regeneración mapas fallo: %s", e)

    return items


def limpiar_eventos_antiguos() -> int:
    """Elimina eventos procesados/descartados con timestamp >90 días."""
    cutoff = utcnow() - timedelta(days=LIMPIEZA_EVENTOS_DIAS)
    with session_scope() as s:
        n = (
            s.query(Evento)
            .filter(
                Evento.estado.in_([EstadoEvento.PROCESADO.value, EstadoEvento.DESCARTADO.value]),
                Evento.timestamp < cutoff,
            )
            .delete()
        )
    return n


def limpiar_tasks_antiguos() -> int:
    """Elimina tasks completados/fallidos con finished_at >30 días."""
    cutoff = utcnow() - timedelta(days=LIMPIEZA_TASKS_DIAS)
    with session_scope() as s:
        n = (
            s.query(Task)
            .filter(
                Task.estado.in_([EstadoTask.COMPLETADO.value, EstadoTask.FALLIDO.value]),
                Task.finished_at.isnot(None),
                Task.finished_at < cutoff,
            )
            .delete()
        )
    return n


def correr_script_nocturno(enviar_digest: bool = True) -> dict:
    """Ejecuta todos los checks. Retorna resumen para logs y dashboard.

    Si `enviar_digest=True` y hay items materiales, envía el digest email.
    """
    now = utcnow()

    # Red flags detection ANTES del resto — porque afecta state que luego auditamos
    red_flags_resumen = {}
    try:
        from backend.agents.red_flags_detector import escanear_eventos_recientes
        red_flags_resumen = escanear_eventos_recientes(dias=1)
    except Exception as e:  # noqa: BLE001
        log.error("script_nocturno — red_flags_detector fallo: %s", e)
        red_flags_resumen = {"error": str(e)}

    result = {
        "inicio": now.isoformat(),
        "red_flags_detectados": red_flags_resumen,
        "entry_ranges_vencidos": verificar_entry_ranges(),
        "triggers_sin_evaluar": triggers_sin_evaluar(),
        "deep_research_vencido": deep_research_vencido(),
        "sectores_sin_actualizar": sectores_sin_actualizar(),
        "mapas_sectoriales_vencidos": mapas_sectoriales_vencidos(),
        "eventos_limpiados": limpiar_eventos_antiguos(),
        "tasks_limpiados": limpiar_tasks_antiguos(),
    }
    result["fin"] = utcnow().isoformat()
    log.info(
        "script_nocturno — entry_venc=%d triggers_sin_ev=%d dr_venc=%d sec_sin_act=%d "
        "mapas_venc=%d eventos_limpiados=%d tasks_limpiados=%d",
        len(result["entry_ranges_vencidos"]),
        len(result["triggers_sin_evaluar"]),
        len(result["deep_research_vencido"]),
        len(result["sectores_sin_actualizar"]),
        len(result["mapas_sectoriales_vencidos"]),
        result["eventos_limpiados"],
        result["tasks_limpiados"],
    )

    # Digest email
    if enviar_digest:
        try:
            from backend.services import mailer
            mail_result = mailer.digest_nocturno(result)
            if mail_result:
                result["digest_enviado"] = True
                result["digest_dry_run"] = mail_result.dry_run
        except Exception as e:  # noqa: BLE001
            log.error("digest_nocturno email fallo: %s", e)

    return result
