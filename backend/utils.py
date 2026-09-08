"""Utilidades compartidas — tiempo, logging estructurado."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from backend.config import get_settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"


def utcnow() -> datetime:
    """Naive UTC datetime (compatible con SQLite)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


_LOGGERS: dict[str, logging.Logger] = {}


def get_logger(name: str) -> logging.Logger:
    """Logger con handlers stream (stderr) + archivo rotatorio.

    - Stream: formato conciso para dev/console.
    - Archivo: logs/{modulo}.log rotatorio (10MB × 14 backups).

    Logger agrupado por módulo: agents, services, scheduler, ui, main, etc.
    Se infiere del `name` (ej. `backend.agents.analista` → archivo `agents.log`).
    """
    if name in _LOGGERS:
        return _LOGGERS[name]

    logger = logging.getLogger(name)
    logger.setLevel(get_settings().log_level.upper())
    logger.propagate = False

    if not logger.handlers:
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

        stream = logging.StreamHandler()
        stream.setFormatter(fmt)
        logger.addHandler(stream)

        try:
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            module_group = _infer_module_group(name)
            fh = RotatingFileHandler(
                LOGS_DIR / f"{module_group}.log",
                maxBytes=10 * 1024 * 1024,
                backupCount=14,
                encoding="utf-8",
            )
            fh.setFormatter(fmt)
            logger.addHandler(fh)
        except Exception as e:  # noqa: BLE001
            # Si no podemos escribir archivo (permisos, disk full), seguimos con stream
            logger.warning("no pude abrir file handler: %s", e)

    _LOGGERS[name] = logger
    return logger


def _infer_module_group(name: str) -> str:
    """Extrae el grupo del módulo para nombrar el archivo de log."""
    parts = name.split(".")
    if "agents" in parts:
        return "agents"
    if "services" in parts:
        return "services"
    if "seed" in parts:
        return "seed"
    # fallback: último componente
    return parts[-1] if parts else "app"
