"""Agente DISCOVERY — hipótesis semanales (doc 02 sec 4B).

Genera hipótesis de inversión estructuradas, no análisis. Corre semanal (domingos 20:00 ET).
Input: tesis macro + momentum sectores + tickers ya en sistema.
Output: 3-5 hipótesis, 1-5 candidatos cada una. Sin scoring. Sin recomendaciones de compra.

Las hipótesis nunca entran al sistema directamente — el humano elige cuáles investigar.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from backend.database import session_scope
from backend.models import DiscoveryHipotesis, Ficha, Macro, Sector
from backend.services.llm import call_llm_json_with_web_search
from backend.utils import get_logger, utcnow

log = get_logger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"
PROMPT_VERSION = "v1"
PROMPT_FILE = PROMPTS_DIR / f"discovery_{PROMPT_VERSION}.txt"

VALID_SECTORES = {"AI infra", "Ciberseguridad", "Defensa", "Robótica",
                  "Minerales críticos", "Nuclear", "Espacio"}


class DiscoveryError(Exception):
    pass


# ---------- Validador ----------

def validar_hipotesis_json(payload: dict) -> list[str]:
    errores: list[str] = []
    if not isinstance(payload, dict):
        return ["output no es dict"]
    if "semana" not in payload:
        errores.append("falta semana")
    hips = payload.get("hipotesis")
    if not isinstance(hips, list):
        errores.append("hipotesis debe ser lista")
        return errores
    if len(hips) == 0:
        errores.append("hipotesis vacía")
    if len(hips) > 5:
        errores.append(f"demasiadas hipótesis: {len(hips)} (máx 5)")
    for i, h in enumerate(hips):
        if not isinstance(h, dict):
            errores.append(f"hipotesis[{i}] no es dict")
            continue
        for k in ("sector", "hipotesis", "evidencia_minima", "por_que_ahora", "candidatos"):
            if k not in h:
                errores.append(f"hipotesis[{i}] sin {k}")
        if h.get("sector") not in VALID_SECTORES:
            errores.append(f"hipotesis[{i}].sector={h.get('sector')!r} no está en sectores válidos")
        cands = h.get("candidatos")
        if not isinstance(cands, list):
            errores.append(f"hipotesis[{i}].candidatos no es lista")
        elif len(cands) == 0:
            errores.append(f"hipotesis[{i}].candidatos vacía")
        elif len(cands) > 5:
            errores.append(f"hipotesis[{i}].candidatos con {len(cands)} items (máx 5)")
    return errores


# ---------- Generación ----------

def _semana_iso(d: datetime | None = None) -> str:
    d = d or utcnow()
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"


def _cargar_prompt() -> str:
    if not PROMPT_FILE.exists():
        raise DiscoveryError(f"prompt no encontrado: {PROMPT_FILE}")
    return PROMPT_FILE.read_text(encoding="utf-8")


def _construir_contexto() -> dict:
    """Extrae macro, sectores con momentum y tickers ya en sistema."""
    with session_scope() as s:
        macro = s.query(Macro).filter_by(activa=True).first()
        sectores = s.query(Sector).order_by(Sector.nombre).all()
        tickers = [f.ticker for f in s.query(Ficha).all()]

        return {
            "macro_fase": macro.fase_actual if macro else "N/D",
            "macro_postura": macro.postura_capital if macro else "N/D",
            "macro_version": macro.version if macro else "N/D",
            "macro_notas": (macro.notas or "").replace("\n", " ")[:600] if macro else "",
            "sectores_momentum": "\n".join(
                f"  - {s.nombre}: {s.momentum or 'sin momentum'} (prioridad {s.prioridad})"
                for s in sectores
            ),
            "tickers_existentes": ", ".join(tickers),
        }


def generar_hipotesis_semanales(*, dry_run: bool = False, max_searches: int = 5) -> dict:
    """Corre Discovery. Persiste una fila por semana en tabla discovery. Idempotente por semana."""
    semana = _semana_iso()

    # Idempotencia por semana
    with session_scope() as s:
        existe = s.query(DiscoveryHipotesis).filter_by(semana=semana).first()
        if existe is not None and not dry_run:
            log.info("discovery — semana %s ya existe, skip", semana)
            return {"skipped": True, "semana": semana, "id": existe.id}

    ctx = _construir_contexto()
    system_prompt = _cargar_prompt()
    for key, val in ctx.items():
        system_prompt = system_prompt.replace("{" + key + "}", str(val))
    system_prompt = system_prompt.replace("{semana}", semana)

    user_message = (
        f"Ejecutá la sesión de discovery de la semana {semana}.\n\n"
        f"PROCESO: usá la tool web_search para investigar señales emergentes de las últimas 2-8 "
        f"semanas en los sectores prioritarios. No escribas comentarios ni narración entre búsquedas.\n\n"
        f"OUTPUT FINAL OBLIGATORIO: tu última respuesta debe ser EXCLUSIVAMENTE un único objeto JSON "
        f"que empiece con `{{` y termine con `}}`, siguiendo exactamente la estructura definida en el "
        f"system prompt (claves prompt_version, semana, hipotesis[]). Sin prosa previa, sin ```json, "
        f"sin explicación, sin texto posterior. Si no emitís el JSON, el sistema falla. "
        f"Producí AHORA el JSON con 3-5 hipótesis."
    )

    result = call_llm_json_with_web_search(
        system_prompt=system_prompt,
        user_message=user_message,
        max_searches=max_searches,
        cache_system=False,
        dry_run=dry_run,
        extra_metadata={"agent": "discovery", "semana": semana, "prompt_version": PROMPT_VERSION},
    )

    if dry_run:
        return {"dry_run": True, "semana": semana, "system_chars": len(system_prompt),
                "user_chars": len(user_message)}

    payload = result.parsed_json or {}
    errores = validar_hipotesis_json(payload)
    if errores:
        _persistir_discovery_fallido(semana, payload, errores)
        raise DiscoveryError(f"JSON inválido: {errores}")

    # Asegurar campo semana consistente
    payload["semana"] = semana

    with session_scope() as s:
        row = DiscoveryHipotesis(
            semana=semana,
            hipotesis_json=payload.get("hipotesis", []),
            prompt_version=PROMPT_VERSION,
            estado="pendiente_revision",
            timestamp=utcnow(),
        )
        s.add(row)
        s.flush()
        did = row.id

    log.info(
        "DISCOVERY — semana=%s id=%d hipotesis=%d cost=$%.4f searches=%d",
        semana, did, len(payload.get("hipotesis", [])),
        result.cost_usd, result.metadata.get("web_searches_usadas", 0),
    )

    return {
        "id": did,
        "semana": semana,
        "hipotesis_count": len(payload.get("hipotesis", [])),
        "cost_usd": result.cost_usd,
        "web_searches": result.metadata.get("web_searches_usadas", 0),
        "urls_citadas": result.metadata.get("urls_citadas", []),
    }


def _persistir_discovery_fallido(semana: str, payload: dict, errores: list[str]) -> None:
    with session_scope() as s:
        s.add(DiscoveryHipotesis(
            semana=semana + "_fallido",
            hipotesis_json={"errores_validacion": errores, "payload_parcial": payload},
            prompt_version=PROMPT_VERSION,
            estado="descartada",
            timestamp=utcnow(),
        ))


# ---------- Lectura y feedback ----------

def get_discovery_semana(semana: str | None = None) -> dict | None:
    with session_scope() as s:
        if semana is None:
            row = s.query(DiscoveryHipotesis).order_by(DiscoveryHipotesis.timestamp.desc()).first()
        else:
            row = s.query(DiscoveryHipotesis).filter_by(semana=semana).first()
        if row is None:
            return None
        return {
            "id": row.id,
            "semana": row.semana,
            "hipotesis": row.hipotesis_json,
            "prompt_version": row.prompt_version,
            "estado": row.estado,
            "timestamp": row.timestamp.isoformat(),
            "util": row.util,
            "feedback": row.feedback,
        }


def list_discovery(limit: int = 20) -> list[dict]:
    with session_scope() as s:
        rows = (
            s.query(DiscoveryHipotesis)
            .order_by(DiscoveryHipotesis.timestamp.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "semana": r.semana,
                "estado": r.estado,
                "hipotesis_count": len(r.hipotesis_json) if isinstance(r.hipotesis_json, list) else 0,
                "util": r.util,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in rows
        ]


def set_feedback(semana: str, util: bool | None = None, feedback: str | None = None) -> dict:
    with session_scope() as s:
        row = s.query(DiscoveryHipotesis).filter_by(semana=semana).first()
        if row is None:
            raise DiscoveryError(f"semana {semana} no existe")
        if util is not None:
            row.util = util
        if feedback is not None:
            row.feedback = feedback
        row.estado = "revisada"
        return {"semana": semana, "util": row.util, "feedback": row.feedback, "estado": row.estado}
