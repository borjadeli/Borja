"""P1 (doc 91 §8, IA2 §3.5/3.6) — registro de la decisión en SOMBRA. Por cada decisión del comité guarda qué habría
decidido P1 (el VeredictoSombra), si eso CAMBIARÍA la propuesta del PM, y qué campos portantes faltaron. Append-only
a `data/shadow_p1.jsonl`. NO aplica nada. Es lo que se observa durante la sombra antes de darle autoridad.

Mide (IA2 §3.6): % bloqueado por P1, % por datos desconocidos, % por mérito, y —clave— registra también las
propuestas BLOQUEADAS (para medir el costo de oportunidad, no solo las permitidas). Determinista, $0.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "shadow_p1.jsonl"

# ¿la acción del PM BUSCA desplegar/mover capital? (si P1 la bloquea/difiere, cambia la decisión)
_ACCIONES_QUE_MUEVEN = {"abrir", "aumentar", "reducir", "salir"}


def _cambiaria(accion_pm: str, permiso: str) -> bool:
    """La decisión del PM cambiaría si propuso mover capital y P1 no la deja EJECUTAR."""
    return (accion_pm or "").strip().lower() in _ACCIONES_QUE_MUEVEN and permiso != "EJECUTAR"


def construir_shadow_decision(*, ciclo: str, ticker: str, accion_pm: str, veredicto, dossier_ref: str | None = None,
                              ips_version: str = "p1-v1") -> dict:
    """`veredicto` = VeredictoSombra (de evaluar_sombra/harness)."""
    return {
        "tipo": "shadow_p1",
        "ts": datetime.now(timezone.utc).isoformat(),
        "ciclo": ciclo,
        "ips_version": ips_version,
        "ticker": ticker.upper(),
        "evidence_ref": dossier_ref,
        "propuesta_pm": accion_pm,
        "shadow": {
            "arquetipo": veredicto.arquetipo,
            "banda": veredicto.banda,
            "tier": veredicto.tier,
            "cap": veredicto.cap,
            "permiso": veredicto.permiso,
            "motivos": list(veredicto.motivos),
        },
        "cambiaria_la_decision": _cambiaria(accion_pm, veredicto.permiso),
        "data_quality": {"missing_fields": list(veredicto.missing_fields)},
    }


def registrar_shadow(record: dict, *, path: Path | str | None = None) -> None:
    """Append best-effort (la sombra NUNCA debe tumbar el run)."""
    p = Path(path or _PATH)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 — logging de sombra, no crítico
        pass


def resumen_sombra(records: list[dict]) -> dict:
    """Agregados de IA2 §3.6 sobre los registros de un período (para el monitor)."""
    n = len(records) or 1
    cambios = sum(1 for r in records if r.get("cambiaria_la_decision"))
    bloqueadas = sum(1 for r in records if r.get("shadow", {}).get("permiso") == "BLOQUEAR")
    por_datos = sum(1 for r in records if r.get("data_quality", {}).get("missing_fields"))
    return {"n": len(records), "cambiaria_%": round(100 * cambios / n, 1),
            "bloqueadas_%": round(100 * bloqueadas / n, 1),
            "con_datos_faltantes_%": round(100 * por_datos / n, 1),
            "fecha": date.today().isoformat()}
