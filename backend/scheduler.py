"""APScheduler — gestión de jobs automáticos (Research + Dispatcher + Script Nocturno).

Requisitos (doc 02 sec 1.2):
- **1 thread worker** para evitar lock contention en SQLite.
- Timezone: America/New_York (para respetar horario de mercado).
- Los módulos del Radar corren secuencialmente.

Schedule:
- Research precios:   cron L-V, 9-15h, minuto 30 (cada hora en horario mercado ET)
- Research earnings:  cron diario 7:00 ET
- Research Form 4:    cron diario 7:05 ET
- Research noticias:  interval cada 4h
- Dispatcher:         interval cada 15 min (procesa cola pendiente)
- Script Nocturno:    cron diario 6:00 ET
"""
from __future__ import annotations

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from backend.agents.dispatcher import procesar_cola_eventos
from backend.agents.research import (
    monitor_earnings,
    monitor_form4,
    monitor_noticias,
    monitor_precios,
)
from backend.utils import get_logger

log = get_logger(__name__)

_scheduler: BackgroundScheduler | None = None
_jobs_registered = False


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(
            executors={"default": ThreadPoolExecutor(max_workers=1)},
            job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300},
            timezone="America/New_York",
        )
    return _scheduler


def register_jobs(scheduler: BackgroundScheduler) -> None:
    """Registra los jobs. Idempotente — si ya están, reemplaza."""
    global _jobs_registered

    # Monitor de precios — L-V, 9-15h ET, :30 en punto (cada hora durante mercado)
    scheduler.add_job(
        func=_safe_run(monitor_precios, "monitor_precios"),
        trigger=CronTrigger(day_of_week="mon-fri", hour="9-15", minute=30, timezone="America/New_York"),
        id="research_precios",
        replace_existing=True,
    )

    # Monitor earnings — diario 7:00 ET
    scheduler.add_job(
        func=_safe_run(monitor_earnings, "monitor_earnings"),
        trigger=CronTrigger(hour=7, minute=0, timezone="America/New_York"),
        id="research_earnings",
        replace_existing=True,
    )

    # Monitor Form 4 — diario 7:05 ET
    scheduler.add_job(
        func=_safe_run(monitor_form4, "monitor_form4"),
        trigger=CronTrigger(hour=7, minute=5, timezone="America/New_York"),
        id="research_form4",
        replace_existing=True,
    )

    # Monitor noticias — cada 4h
    scheduler.add_job(
        func=_safe_run(monitor_noticias, "monitor_noticias"),
        trigger=IntervalTrigger(hours=4),
        id="research_noticias",
        replace_existing=True,
    )

    # Dispatcher — cada 15 min procesa cola pendiente
    scheduler.add_job(
        func=_safe_run(procesar_cola_eventos, "dispatcher"),
        trigger=IntervalTrigger(minutes=15),
        id="dispatcher_process_queue",
        replace_existing=True,
    )

    # Script nocturno — diario 6:00 ET
    from backend.agents.script_nocturno import correr_script_nocturno
    scheduler.add_job(
        func=_safe_run(correr_script_nocturno, "script_nocturno"),
        trigger=CronTrigger(hour=6, minute=0, timezone="America/New_York"),
        id="script_nocturno",
        replace_existing=True,
    )

    # Evaluador automático — L-V cada hora 10:15-16:15 ET (mercado abierto).
    # Determinista, SIN LLM. Corre Portfolio+Juez sobre cada Portfolio_Activo y
    # WL_Prioritaria con precios frescos. Recs VALIDADAS se auto-aprueban en modo paper.
    from backend.agents.evaluador_automatico import correr_evaluacion_diaria
    scheduler.add_job(
        func=_safe_run(correr_evaluacion_diaria, "evaluador_horario"),
        trigger=CronTrigger(day_of_week="mon-fri", hour="10-16", minute=15, timezone="America/New_York"),
        id="evaluador_horario",
        replace_existing=True,
    )

    # MtM intra-day — L-V cada 30 min entre 10:00 y 16:00 ET.
    # Determinista, sin LLM. Trae precio actual de Portfolio + WLP + Bucket
    # vía Yahoo. Side effect: dispara alertas PRECIO_ALERTA cuando un WLP
    # cae dentro de su entry_range.
    from backend.agents.mtm import actualizar_mtm
    scheduler.add_job(
        func=_safe_run(actualizar_mtm, "mtm_intraday"),
        trigger=CronTrigger(day_of_week="mon-fri", hour="10-16", minute="0,30", timezone="America/New_York"),
        id="mtm_intraday",
        replace_existing=True,
    )

    # Snapshot diario equity — L-V 16:30 ET (post-cierre, después del evaluador).
    # Persiste fila en portfolio_snapshots para construir equity curve histórica.
    from backend.agents.portfolio_snapshot import generar_snapshot_diario
    scheduler.add_job(
        func=_safe_run(generar_snapshot_diario, "portfolio_snapshot"),
        trigger=CronTrigger(day_of_week="mon-fri", hour=16, minute=30, timezone="America/New_York"),
        id="portfolio_snapshot",
        replace_existing=True,
    )

    # Revalidación 30d (v4.2 sec 5) — diario 7:30 ET. Detecta posiciones con
    # ciclo de 30d cumplido y crea evento + Revalidación pendiente.
    from backend.agents.revalidacion import detectar_revalidaciones_pendientes
    scheduler.add_job(
        func=_safe_run(detectar_revalidaciones_pendientes, "revalidacion_30d"),
        trigger=CronTrigger(hour=7, minute=30, timezone="America/New_York"),
        id="revalidacion_30d",
        replace_existing=True,
    )

    # Discovery — semanal domingos 20:00 ET
    from backend.agents.discovery_hipotesis import generar_hipotesis_semanales
    scheduler.add_job(
        func=_safe_run(generar_hipotesis_semanales, "discovery_hipotesis"),
        trigger=CronTrigger(day_of_week="sun", hour=20, minute=0, timezone="America/New_York"),
        id="discovery_semanal",
        replace_existing=True,
    )

    # Reporte semanal del Juez — lunes 8:00 ET
    from backend.agents.reporte_semanal import generar_reporte
    scheduler.add_job(
        func=_safe_run(generar_reporte, "reporte_semanal"),
        trigger=CronTrigger(day_of_week="mon", hour=8, minute=0, timezone="America/New_York"),
        id="reporte_semanal",
        replace_existing=True,
    )

    # Backup SQLite diario — 4:00 AM UTC (antes del horario mercado)
    from backend.ops.backup import correr_backup
    scheduler.add_job(
        func=_safe_run(correr_backup, "backup_sqlite"),
        trigger=CronTrigger(hour=4, minute=0, timezone="UTC"),
        id="backup_sqlite",
        replace_existing=True,
    )

    # ---- Núcleo nuevo en PAPER (autónomo, sin confirmación humana, simulado) ----
    from backend.seleccion.jobs import (
        job_paper_ciclo, job_paper_pm, job_paper_reextraccion, job_paper_snapshot,
    )

    # Opera (compra/vende) — diario L-V tras el cierre. Sin LLM (hechos cacheados + precios).
    scheduler.add_job(
        func=_safe_run(job_paper_ciclo, "paper_ciclo"),
        trigger=CronTrigger(day_of_week="mon-fri", hour=16, minute=40, timezone="America/New_York"),
        id="paper_ciclo",
        replace_existing=True,
    )
    # Marca a mercado + snapshot de equity — diario L-V tras operar.
    scheduler.add_job(
        func=_safe_run(job_paper_snapshot, "paper_snapshot"),
        trigger=CronTrigger(day_of_week="mon-fri", hour=16, minute=45, timezone="America/New_York"),
        id="paper_snapshot",
        replace_existing=True,
    )
    # Mark-to-market INTRADÍA — cada 30 min en horario de mercado, para P&L en vivo.
    scheduler.add_job(
        func=_safe_run(job_paper_snapshot, "paper_mtm_intraday"),
        trigger=CronTrigger(day_of_week="mon-fri", hour="9-16", minute="0,30", timezone="America/New_York"),
        id="paper_mtm_intraday",
        replace_existing=True,
    )
    # Re-extracción de hechos con LLM — semanal (domingo 19:00 ET, antes del Discovery). ~$3.5/corrida.
    scheduler.add_job(
        func=_safe_run(job_paper_reextraccion, "paper_reextraccion"),
        trigger=CronTrigger(day_of_week="sun", hour=19, minute=0, timezone="America/New_York"),
        id="paper_reextraccion",
        replace_existing=True,
    )
    # Canal de juicio PM-LLM → libro_pm.json (targets de tamaño) — semanal (domingo 19:30 ET, TRAS la
    # re-extracción, con hechos frescos). Costoso (LLM + web search por nombre). El evento lo dispara el ciclo.
    scheduler.add_job(
        func=_safe_run(job_paper_pm, "paper_pm"),
        trigger=CronTrigger(day_of_week="sun", hour=19, minute=30, timezone="America/New_York"),
        id="paper_pm",
        replace_existing=True,
    )

    _jobs_registered = True
    log.info("scheduler — %d jobs registrados", len(scheduler.get_jobs()))


def _safe_run(fn, name: str):
    """Wrapper que loguea excepciones sin matar el scheduler."""
    def wrapper(*args, **kwargs):
        try:
            log.info("scheduler — ejecutando %s", name)
            result = fn(*args, **kwargs)
            log.info("scheduler — %s completado", name)
            return result
        except Exception as e:  # noqa: BLE001
            log.exception("scheduler — %s falló: %s", name, e)
    wrapper.__name__ = f"wrapped_{name}"
    return wrapper


def start() -> dict:
    s = get_scheduler()
    if not _jobs_registered:
        register_jobs(s)
    if not s.running:
        s.start()
        log.info("scheduler — started")
    return status()


def stop() -> dict:
    global _scheduler, _jobs_registered
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("scheduler — stopped")
    _scheduler = None
    _jobs_registered = False
    return {"running": False, "jobs": []}


def status() -> dict:
    s = _scheduler
    if s is None:
        return {"running": False, "jobs": []}
    return {
        "running": s.running,
        "jobs": [
            {
                "id": j.id,
                "next_run_time": j.next_run_time.isoformat() if j.next_run_time else None,
                "trigger": str(j.trigger),
            }
            for j in s.get_jobs()
        ],
    }
