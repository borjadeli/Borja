"""Agente MAPA SECTORIAL — genera mapa estructural por sector con LLM + web search.

Responsabilidad (doc 02 sec 3):
- Por cada sector prioritario, generar un JSON con cadena de valor, cuellos de botella
  (con criticidad alto/medio/bajo/null), empresas dominantes e industria servida.
- Se usa como **contexto orientativo** del Analista — no verdad absoluta.
- Vencimiento configurable por sector. Regeneración automática al vencer.
- Aprobación humana OPCIONAL. Overrides de criticidad SOBREVIVEN regeneraciones.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from backend.database import session_scope
from backend.models import EstadoMapa, Ficha, Macro, Sector, SectorMapa
from backend.services.llm import call_llm_json, call_llm_json_with_web_search
from backend.utils import get_logger, utcnow

log = get_logger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"
PROMPT_VERSION = "v1"
PROMPT_FILE = PROMPTS_DIR / f"mapa_sectorial_{PROMPT_VERSION}.txt"

# Vencimientos default por sector (doc 02 sec 3.4)
DIAS_VENCIMIENTO_DEFAULT = {
    "AI infra": 14,
    "Ciberseguridad": 21,
    "Defensa": 30,
    "Robótica": 21,
    "Minerales críticos": 30,
    "Nuclear": 45,
    "Espacio": 30,
}

VALID_CRITICIDAD = {"alto", "medio", "bajo", None}
VALID_SUSTITUIBILIDAD = {"baja", "media", "alta"}


class MapaSectorialError(Exception):
    pass


# ---------- Validador ----------

def validar_mapa_json(payload: dict) -> list[str]:
    """Retorna lista de errores. Vacía = OK."""
    errores: list[str] = []
    if not isinstance(payload, dict):
        return ["output no es dict"]

    required = {"prompt_version", "sector", "cadena_de_valor",
               "cuellos_de_botella", "empresas_dominantes", "fecha_investigacion"}
    missing = required - set(payload.keys())
    if missing:
        errores.append(f"campos faltantes: {sorted(missing)}")

    if not isinstance(payload.get("cadena_de_valor"), list):
        errores.append("cadena_de_valor debe ser lista")

    cuellos = payload.get("cuellos_de_botella")
    if not isinstance(cuellos, list):
        errores.append("cuellos_de_botella debe ser lista")
    else:
        for i, c in enumerate(cuellos):
            if not isinstance(c, dict):
                errores.append(f"cuello[{i}] no es dict")
                continue
            for key in ("componente", "por_que_es_cuello", "nivel_critico", "justificacion_criticidad"):
                if key not in c:
                    errores.append(f"cuello[{i}] sin {key}")
            if c.get("nivel_critico") not in VALID_CRITICIDAD:
                errores.append(f"cuello[{i}].nivel_critico={c.get('nivel_critico')!r} inválido")
            if c.get("sustituibilidad") not in VALID_SUSTITUIBILIDAD and c.get("sustituibilidad") is not None:
                errores.append(f"cuello[{i}].sustituibilidad={c.get('sustituibilidad')!r} inválido")

    emp = payload.get("empresas_dominantes")
    if not isinstance(emp, list):
        errores.append("empresas_dominantes debe ser lista")

    return errores


# ---------- Generación ----------

def _cargar_prompt() -> str:
    if not PROMPT_FILE.exists():
        raise MapaSectorialError(f"prompt no encontrado: {PROMPT_FILE}")
    return PROMPT_FILE.read_text(encoding="utf-8")


def _construir_mensaje_usuario(sector: str) -> str:
    with session_scope() as s:
        macro = s.query(Macro).filter_by(activa=True).first()
        sector_row = s.query(Sector).filter_by(nombre=sector).first()
        macro_fase = macro.fase_actual if macro else "N/D"
        macro_postura = macro.postura_capital if macro else "N/D"
        macro_version = macro.version if macro else "N/D"
        macro_notas = (macro.notas or "").replace("\n", " ")[:500] if macro else ""
        prioridad = sector_row.prioridad if sector_row else "N/D"
        horizonte = sector_row.horizonte if sector_row else "N/D"
        notas_sec = (sector_row.notas or "")[:300] if sector_row else ""

    return (
        f"Investigá y producí el mapa sectorial estructurado para el sector **{sector}**.\n\n"
        f"Prioridad del sistema: {prioridad}. Horizonte típico: {horizonte}.\n"
        f"Notas internas sobre el sector: {notas_sec}\n\n"
        f"Contexto macro: fase {macro_fase}, postura {macro_postura} (v{macro_version}).\n"
        f"Resumen macro: {macro_notas}\n\n"
        f"Ejecutá búsquedas web (máximo 5) para validar industria servida, cuellos de botella actuales, "
        f"proveedores conocidos y empresas dominantes. Aplicá los criterios de criticidad literalmente.\n\n"
        f"Producí el JSON ahora."
    )


def generar_mapa_sectorial(sector: str, *, dry_run: bool = False, max_searches: int = 3,
                           usar_web_search: bool = False) -> dict:
    """Genera un nuevo mapa para el sector. Persiste y desactiva mapa anterior.

    Args:
        usar_web_search: si True, usa web_search tool (costoso ~$2, puede saturar contexto).
            Default False — usa knowledge del LLM (cutoff Jan 2026), ~$0.10-0.20 por mapa.
            Web search es preferible solo cuando se necesite info muy reciente (<3 meses).

    Returns: dict con mapa_id, costo LLM, urls citadas, validación.
    """
    with session_scope() as s:
        existe_sector = s.query(Sector).filter_by(nombre=sector).first()
        if existe_sector is None:
            raise MapaSectorialError(f"sector {sector} no existe en tabla sectores")

    system_prompt = _cargar_prompt()
    # Reemplazar placeholders del prompt
    with session_scope() as s:
        macro = s.query(Macro).filter_by(activa=True).first()
        macro_fase = macro.fase_actual if macro else "N/D"
        macro_postura = macro.postura_capital if macro else "N/D"
        macro_version = macro.version if macro else "N/D"
        macro_notas = (macro.notas or "").replace("\n", " ")[:500] if macro else ""
        # end with — todas las lecturas dentro de la sesión

    system_prompt = (
        system_prompt
        .replace("{sector}", sector)
        .replace("{macro_fase}", macro_fase)
        .replace("{macro_postura}", macro_postura)
        .replace("{macro_version}", macro_version)
        .replace("{macro_notas}", macro_notas)
    )

    user_message = _construir_mensaje_usuario(sector)

    if usar_web_search:
        result = call_llm_json_with_web_search(
            system_prompt=system_prompt,
            user_message=user_message,
            max_searches=max_searches,
            cache_system=False,
            dry_run=dry_run,
            extra_metadata={"agent": "mapa_sectorial", "sector": sector, "prompt_version": PROMPT_VERSION},
        )
    else:
        # Sin web search — más barato y más confiable de parsear
        result = call_llm_json(
            system_prompt=system_prompt,
            user_message=user_message + "\n\nIMPORTANTE: NO uses búsqueda web. Usá solo tu conocimiento. "
                                         "Tu respuesta debe empezar con `{` y ser exclusivamente un objeto JSON.",
            max_tokens=8192,
            cache_system=True,
            dry_run=dry_run,
            extra_metadata={"agent": "mapa_sectorial", "sector": sector, "prompt_version": PROMPT_VERSION},
        )

    if dry_run:
        return {
            "dry_run": True,
            "sector": sector,
            "system_chars": len(system_prompt),
            "user_chars": len(user_message),
        }

    payload = result.parsed_json or {}
    errores = validar_mapa_json(payload)
    if errores:
        _persistir_mapa_fallido(sector, payload, result, errores)
        raise MapaSectorialError(f"JSON inválido del mapa {sector}: {errores}")

    # Aplicar overrides humanos previos (si el humano había ajustado criticidades)
    overrides = _cargar_overrides(sector)
    if overrides:
        for c in payload.get("cuellos_de_botella", []):
            comp = c.get("componente")
            if comp in overrides:
                c["nivel_critico"] = overrides[comp]
                c["justificacion_criticidad"] = (c.get("justificacion_criticidad") or "") + " [override humano aplicado]"

    mapa_id = _persistir_mapa_activo(
        sector=sector,
        payload=payload,
        urls=result.metadata.get("urls_citadas", []),
        cost_usd=result.cost_usd,
        overrides=overrides,
    )

    return {
        "mapa_id": mapa_id,
        "sector": sector,
        "cost_usd": result.cost_usd,
        "web_searches": result.metadata.get("web_searches_usadas", 0),
        "urls_citadas": result.metadata.get("urls_citadas", []),
        "cuellos_count": len(payload.get("cuellos_de_botella", [])),
        "empresas_dominantes_count": len(payload.get("empresas_dominantes", [])),
        "overrides_aplicados": list(overrides.keys()) if overrides else [],
    }


def _persistir_mapa_activo(sector: str, payload: dict, urls: list[str],
                           cost_usd: float, overrides: dict | None) -> int:
    now = utcnow()
    dias_venc = DIAS_VENCIMIENTO_DEFAULT.get(sector, 30)
    with session_scope() as s:
        # Desactivar mapas previos activos
        s.query(SectorMapa).filter_by(sector=sector, estado=EstadoMapa.ACTIVO.value).update(
            {"estado": EstadoMapa.VENCIDO.value}
        )
        fuentes_resumen = "\n".join(urls[:20])
        nuevo = SectorMapa(
            sector=sector,
            mapa_json=payload,
            estado=EstadoMapa.ACTIVO.value,
            fuentes_resumen=fuentes_resumen,
            fecha_generacion=now,
            dias_vencimiento=dias_venc,
            criticidades_override=overrides or None,
            prompt_version=PROMPT_VERSION,
            aprobado_por_humano=False,
        )
        s.add(nuevo)
        s.flush()
        mid = nuevo.id
    log.info("MAPA SECTORIAL persistido — sector=%s mapa_id=%s cost=$%.4f", sector, mid, cost_usd)
    return mid


def _persistir_mapa_fallido(sector: str, payload: dict, result, errores: list[str]) -> None:
    with session_scope() as s:
        s.add(SectorMapa(
            sector=sector,
            mapa_json={"errores_validacion": errores, "payload_parcial": payload},
            estado=EstadoMapa.FALLIDO.value,
            fuentes_resumen="\n".join(result.metadata.get("urls_citadas", [])[:20]) if not isinstance(result, dict) else "",
            fecha_generacion=utcnow(),
            dias_vencimiento=DIAS_VENCIMIENTO_DEFAULT.get(sector, 30),
            prompt_version=PROMPT_VERSION,
        ))
    log.warning("MAPA SECTORIAL fallido — sector=%s errores=%s", sector, errores)


def _cargar_overrides(sector: str) -> dict[str, str]:
    """Lee overrides del humano del mapa ACTIVO o último aprobado."""
    with session_scope() as s:
        m = (
            s.query(SectorMapa)
            .filter_by(sector=sector)
            .order_by(SectorMapa.fecha_generacion.desc())
            .first()
        )
        if m and m.criticidades_override:
            return dict(m.criticidades_override)
    return {}


# ---------- Lectura y admin ----------

def get_mapa_activo(sector: str) -> dict | None:
    with session_scope() as s:
        m = (
            s.query(SectorMapa)
            .filter_by(sector=sector, estado=EstadoMapa.ACTIVO.value)
            .order_by(SectorMapa.fecha_generacion.desc())
            .first()
        )
        if not m:
            return None
        now = utcnow()
        vencimiento = m.fecha_generacion + timedelta(days=m.dias_vencimiento)
        return {
            "mapa_id": m.id,
            "sector": m.sector,
            "fecha_generacion": m.fecha_generacion.isoformat(),
            "fecha_vencimiento": vencimiento.isoformat(),
            "dias_vencimiento": m.dias_vencimiento,
            "dias_restantes": (vencimiento - now).days,
            "vencido": vencimiento < now,
            "estado": m.estado,
            "aprobado_por_humano": m.aprobado_por_humano,
            "fecha_aprobacion": m.fecha_aprobacion.isoformat() if m.fecha_aprobacion else None,
            "prompt_version": m.prompt_version,
            "mapa": m.mapa_json,
            "fuentes_resumen": m.fuentes_resumen,
            "criticidades_override": m.criticidades_override or {},
        }


def aprobar_mapa(sector: str) -> dict:
    """Marca el mapa activo como aprobado → no regenerar hasta 2x vencimiento."""
    now = utcnow()
    with session_scope() as s:
        m = (
            s.query(SectorMapa)
            .filter_by(sector=sector, estado=EstadoMapa.ACTIVO.value)
            .order_by(SectorMapa.fecha_generacion.desc())
            .first()
        )
        if not m:
            raise MapaSectorialError(f"sin mapa activo para {sector}")
        m.aprobado_por_humano = True
        m.fecha_aprobacion = now
        return {"sector": sector, "mapa_id": m.id, "aprobado": True}


def ajustar_criticidad(sector: str, componente: str, nivel: str | None) -> dict:
    """Override humano de criticidad de un cuello específico. Sobrevive regeneraciones."""
    if nivel not in VALID_CRITICIDAD:
        raise MapaSectorialError(f"nivel {nivel!r} inválido. Válidos: {sorted([v for v in VALID_CRITICIDAD if v])}+null")

    with session_scope() as s:
        m = (
            s.query(SectorMapa)
            .filter_by(sector=sector, estado=EstadoMapa.ACTIVO.value)
            .order_by(SectorMapa.fecha_generacion.desc())
            .first()
        )
        if not m:
            raise MapaSectorialError(f"sin mapa activo para {sector}")

        overrides = dict(m.criticidades_override or {})
        overrides[componente] = nivel
        m.criticidades_override = overrides

        # También aplicar en el JSON vivo
        mapa = dict(m.mapa_json or {})
        cuellos = mapa.get("cuellos_de_botella", [])
        found = False
        for c in cuellos:
            if c.get("componente") == componente:
                c["nivel_critico"] = nivel
                c["justificacion_criticidad"] = (c.get("justificacion_criticidad") or "") + " [override humano]"
                found = True
                break
        m.mapa_json = mapa

        return {
            "sector": sector,
            "mapa_id": m.id,
            "componente": componente,
            "nivel_critico_nuevo": nivel,
            "encontrado_en_mapa": found,
        }


def regenerar_si_vencido(sectores: list[str] | None = None) -> dict:
    """Llamada desde el script nocturno. Regenera mapas vencidos de sectores con fichas activas."""
    now = utcnow()
    regenerados: list[dict] = []
    errores: list[dict] = []
    omitidos_aprobados: list[str] = []

    with session_scope() as s:
        if sectores is None:
            # Solo regenerar sectores que tengan al menos una ficha en estado activo
            sectores_activos = {
                f.sector for f in s.query(Ficha).filter(Ficha.estado.in_([
                    "Portfolio_Activo", "WL_Prioritaria", "WL_Activa",
                ])).all()
            }
            sectores = sorted(sectores_activos)

        mapas_por_sector = {}
        for sec in sectores:
            m = (
                s.query(SectorMapa)
                .filter_by(sector=sec, estado=EstadoMapa.ACTIVO.value)
                .order_by(SectorMapa.fecha_generacion.desc())
                .first()
            )
            mapas_por_sector[sec] = {
                "existe": m is not None,
                "fecha_generacion": m.fecha_generacion if m else None,
                "dias_vencimiento": m.dias_vencimiento if m else DIAS_VENCIMIENTO_DEFAULT.get(sec, 30),
                "aprobado": bool(m.aprobado_por_humano) if m else False,
            }

    for sec, info in mapas_por_sector.items():
        try:
            if info["existe"]:
                vencimiento = info["fecha_generacion"] + timedelta(days=info["dias_vencimiento"])
                # Si está aprobado, duplicar el plazo (safety net)
                if info["aprobado"]:
                    vencimiento = info["fecha_generacion"] + timedelta(days=info["dias_vencimiento"] * 2)
                    if vencimiento > now:
                        omitidos_aprobados.append(sec)
                        continue
                if vencimiento > now:
                    continue  # no vencido
            r = generar_mapa_sectorial(sec)
            regenerados.append({"sector": sec, "mapa_id": r["mapa_id"], "cost_usd": r["cost_usd"]})
        except Exception as e:  # noqa: BLE001
            log.exception("regenerar_si_vencido — fallo en %s", sec)
            errores.append({"sector": sec, "error": str(e)})

    return {
        "regenerados": regenerados,
        "omitidos_aprobados": omitidos_aprobados,
        "errores": errores,
    }
