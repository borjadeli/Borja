"""Backup automatizado de SQLite.

Usa `sqlite3 .backup` (atómico, funciona con WAL activo). Retención 30 días.
Cron integrado en scheduler (diario 4:00 AM UTC).

Uso manual:
    from backend.ops.backup import correr_backup
    correr_backup()
"""
from __future__ import annotations

import shutil
import sqlite3
from datetime import timedelta
from pathlib import Path

from backend.config import get_settings
from backend.utils import get_logger, utcnow

log = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKUPS_DIR = PROJECT_ROOT / "data" / "backups"
RETENCION_DIAS = 30


def correr_backup() -> dict:
    """Crea un backup atómico del SQLite. Retorna dict con metadatos."""
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    src_path = Path(settings.db_url.replace("sqlite:///", ""))

    if not src_path.exists():
        log.error("backup — DB source no existe: %s", src_path)
        return {"ok": False, "error": "db source no existe"}

    now = utcnow()
    ts = now.strftime("%Y%m%dT%H%M%S")
    dst = BACKUPS_DIR / f"borja_{ts}.db"

    try:
        # sqlite3 .backup es atómico incluso con WAL y conexiones abiertas
        src = sqlite3.connect(str(src_path))
        dst_conn = sqlite3.connect(str(dst))
        with dst_conn:
            src.backup(dst_conn)
        dst_conn.close()
        src.close()
        size_mb = dst.stat().st_size / (1024 * 1024)
        log.info("backup — creado %s (%.2f MB)", dst.name, size_mb)
    except Exception as e:  # noqa: BLE001
        log.exception("backup — fallo creando %s", dst)
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    # Limpiar antiguos
    limpiados = _limpiar_antiguos()

    return {
        "ok": True,
        "backup_file": dst.name,
        "size_mb": round(size_mb, 2),
        "timestamp": now.isoformat(),
        "limpiados": limpiados,
        "total_backups": len(list(BACKUPS_DIR.glob("borja_*.db"))),
    }


def _limpiar_antiguos() -> int:
    cutoff = utcnow() - timedelta(days=RETENCION_DIAS)
    n = 0
    for bk in BACKUPS_DIR.glob("borja_*.db"):
        mtime = bk.stat().st_mtime
        from datetime import datetime
        if datetime.utcfromtimestamp(mtime) < cutoff:
            bk.unlink()
            n += 1
    if n > 0:
        log.info("backup — eliminados %d backups antiguos (>%d días)", n, RETENCION_DIAS)
    return n


def listar_backups() -> list[dict]:
    if not BACKUPS_DIR.exists():
        return []
    items = []
    for bk in sorted(BACKUPS_DIR.glob("borja_*.db"), reverse=True):
        stat = bk.stat()
        from datetime import datetime
        items.append({
            "archivo": bk.name,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "timestamp": datetime.utcfromtimestamp(stat.st_mtime).isoformat(),
            "path": str(bk),
        })
    return items
