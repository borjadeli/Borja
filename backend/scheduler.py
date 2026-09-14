"""APScheduler — jobs automáticos del núcleo nuevo en paper (+ backup de infra).

Requisitos:
- **1 thread worker** para evitar lock contention en SQLite.
- Timezone: America/New_York (para respetar horario de mercado).

Schedule (tras el destete del sistema viejo, 2026-09-14):
- Backup SQLite:       cron 4:00 UTC
- paper_ciclo:         cron L-V 16:40 ET (opera; $0 salvo evento)
- paper_snapshot:      cron L-V 16:45 ET (MtM + equity)
- paper_mtm_intraday:  cron L-V 9-16h :00/:30 (MtM en vivo)
- paper_reextraccion:  cron dom 19:00 ET (re-extrae hechos, LLM)
- paper_pm:            cron dom 19:30 ET (canal de juicio PM-LLM → libro_pm.json)
"""
from __future__ import annotations

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

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

    # NOTA (destete 2026-09-14): los jobs del SISTEMA VIEJO (research precios/earnings/form4/noticias,
    # dispatcher, script nocturno, evaluador horario, mtm intradía, portfolio_snapshot, revalidación 30d,
    # discovery, reporte semanal — todos backend.agents) se retiraron. El sistema autónomo es ahora el
    # núcleo nuevo en paper (sección de abajo). Queda solo el backup de infra + los jobs del paper.

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
