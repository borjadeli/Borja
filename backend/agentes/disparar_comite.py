"""Disparar el comité PM (doc 85) — la última milla: que la DECISIÓN del PM corra sola.

El comité (`ops.correr_semana_v2`) es un script CLI monolítico; en vez de refactorizarlo, se dispara como
SUBPROCESO (proceso fresco, sin bleed de estado, aislado de un crash). Lo usan el scheduler (semanal) y el ciclo
diario (cuando hay motivo de despertar). El ledger de presupuesto (fail-closed) es la guarda de costo.
"""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

_log = logging.getLogger(__name__)
_REPO = Path(__file__).resolve().parent.parent.parent


def disparar_comite(*, universo: bool = True, contratos: bool = True, timeout: int = 2400) -> dict:
    """Corre `ops.correr_semana_v2` como subproceso. Devuelve {ok, returncode, resumen}. Fail-safe: nunca lanza."""
    cmd = [sys.executable, "-m", "ops.correr_semana_v2"]
    if universo:
        cmd.append("--universo")
    if contratos:
        cmd.append("--contratos")
    _log.info("disparando comité: %s", " ".join(cmd[2:]))
    try:
        p = subprocess.run(cmd, cwd=str(_REPO), capture_output=True, text=True, timeout=timeout)
        cola = "\n".join((p.stdout or "").strip().splitlines()[-8:])
        if p.returncode != 0:
            _log.warning("comité returncode=%s · stderr: %s", p.returncode, (p.stderr or "")[-500:])
        return {"ok": p.returncode == 0, "returncode": p.returncode, "resumen": cola}
    except subprocess.TimeoutExpired:
        _log.warning("comité excedió el timeout (%ss)", timeout)
        return {"ok": False, "returncode": -1, "resumen": "timeout"}
    except Exception as e:  # noqa: BLE001 — disparar el comité no debe tumbar el scheduler/ciclo
        _log.exception("comité falló al dispararse: %s", e)
        return {"ok": False, "returncode": -1, "resumen": str(e)[:200]}
