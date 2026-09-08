"""Runner async del Analista — integra pipeline + task tracking.

Uso:
    from backend.agents.analista_runner import dispatch_analista
    task_id = dispatch_analista(ticker, background_tasks)
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import BackgroundTasks

from backend.agents.analista import ejecutar_analisis, AnalistaError
from backend.agents.analista_writer import escribir_ficha, ValidacionError
from backend.database import session_scope
from backend.models import EstadoTask, Task
from backend.services.llm import LLMError
from backend.utils import get_logger, utcnow

log = get_logger(__name__)


def dispatch_analista(ticker: str, background_tasks: BackgroundTasks, dry_run: bool = False) -> str:
    """Crea un task y lo encola. Devuelve task_id."""
    ticker = ticker.upper()
    task_id = str(uuid.uuid4())

    with session_scope() as s:
        s.add(Task(
            id=task_id,
            tipo="analista",
            ticker_o_sector=ticker,
            estado=EstadoTask.PENDIENTE.value,
            progreso="encolado",
        ))

    background_tasks.add_task(_run_analista_task, task_id, ticker, dry_run)
    return task_id


def _update_task(task_id: str, estado: str | None = None, progreso: str | None = None,
                 resultado: dict | None = None, error: str | None = None) -> None:
    with session_scope() as s:
        task = s.get(Task, task_id)
        if task is None:
            log.warning("task %s no existe — no se puede actualizar", task_id)
            return
        if estado:
            task.estado = estado
        if progreso:
            task.progreso = progreso
        if resultado is not None:
            task.resultado_json = resultado
        if error:
            task.error = error
        if estado in (EstadoTask.COMPLETADO.value, EstadoTask.FALLIDO.value):
            task.finished_at = utcnow()


def _run_analista_task(task_id: str, ticker: str, dry_run: bool) -> None:
    """Ejecuta el pipeline completo del Analista actualizando el task."""
    updater = lambda estado, progreso: _update_task(task_id, estado=estado, progreso=progreso)
    try:
        _update_task(task_id, estado=EstadoTask.EN_PROGRESO.value, progreso="arrancando")

        result = ejecutar_analisis(ticker, dry_run=dry_run, task_updater=updater)

        if dry_run:
            _update_task(
                task_id,
                estado=EstadoTask.COMPLETADO.value,
                progreso="dry_run completado — no se escribió ficha",
                resultado={
                    "dry_run": True,
                    "context_preview": {k: v for k, v in result["context"].items() if k in (
                        "ticker", "revenue_ttm_millones", "precio_actual", "margen_bruto_ultimo_pct",
                        "liquidez_suficiente", "gaps_detectados",
                    )},
                    "user_message_chars": result["llm_metadata"]["user_message_chars"],
                },
            )
            return

        # Escribir ficha
        _update_task(task_id, progreso="validando output y escribiendo ficha")
        precio_actual = result["context"].get("precio_actual")
        write_result = escribir_ficha(
            ticker=ticker,
            output=result["output"],
            context_dict=result["context"],
            precio_actual=precio_actual,
        )

        # Auto-disparar Portfolio + Juez (doc 02 sec 5.1)
        _update_task(task_id, progreso="generando recomendación (Portfolio + Juez)")
        from backend.agents.recomendacion_runner import ejecutar_recomendacion
        try:
            rec_resumen = ejecutar_recomendacion(ticker, task_id=task_id)
        except Exception as e:  # noqa: BLE001
            log.warning("ejecutar_recomendacion fallo (no bloquea): %s", e)
            rec_resumen = {"error": str(e)}

        resumen = {
            "ticker": write_result.ticker,
            "score_anterior": write_result.score_anterior,
            "score_nuevo": write_result.score_nuevo,
            "estado_anterior": write_result.estado_anterior,
            "estado_sugerido": write_result.estado_sugerido,
            "drift_detectado": write_result.drift_detectado,
            "gaps": write_result.gaps,
            "llm_metadata": result["llm_metadata"],
            "recomendacion": rec_resumen,
        }
        _update_task(
            task_id,
            estado=EstadoTask.COMPLETADO.value,
            progreso=f"analizado — score {write_result.score_nuevo} → estado {write_result.estado_sugerido} → rec {rec_resumen.get('accion', 'N/A')}",
            resultado=resumen,
        )

    except ValidacionError as e:
        log.error("validación fallo task=%s ticker=%s: %s", task_id, ticker, e)
        _update_task(task_id, estado=EstadoTask.FALLIDO.value,
                    progreso="validación JSON fallida", error=str(e))
    except LLMError as e:
        log.error("LLM fallo task=%s ticker=%s: %s", task_id, ticker, e)
        _update_task(task_id, estado=EstadoTask.FALLIDO.value,
                    progreso="LLM error", error=str(e))
    except AnalistaError as e:
        log.error("Analista fallo task=%s ticker=%s: %s", task_id, ticker, e)
        _update_task(task_id, estado=EstadoTask.FALLIDO.value,
                    progreso="Analista error", error=str(e))
    except Exception as e:  # noqa: BLE001
        log.exception("error inesperado task=%s ticker=%s", task_id, ticker)
        _update_task(task_id, estado=EstadoTask.FALLIDO.value,
                    progreso="error inesperado", error=f"{type(e).__name__}: {e}")


def get_task(task_id: str) -> dict | None:
    """Lee el estado actual de un task — para polling desde la UI."""
    with session_scope() as s:
        task = s.get(Task, task_id)
        if task is None:
            return None
        return {
            "task_id": task.id,
            "tipo": task.tipo,
            "ticker": task.ticker_o_sector,
            "estado": task.estado,
            "progreso": task.progreso,
            "resultado": task.resultado_json,
            "error": task.error,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        }
