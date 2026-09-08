"""Validador y escritor de ficha para el Analista.

Responsabilidades:
- Validar JSON del LLM contra schema estricto (doc 02 sec 4.5).
- Calcular score_ponderado determinísticamente desde los 10 scores.
- Escribir los 69 campos de la ficha con transacción atómica.
- Append-only de cambios_score y cambios_estado.
- Detectar drift (>1.5 puntos sin evento material reciente) → crea SCORE_DRIFT.
- Determinar nuevo estado según score (doc 02 sec 4.7).
- Actualizar fecha_proximo_deep_research (90d Portfolio/WLP, 180d resto).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from backend.database import session_scope
from backend.models import EstadoEvento, EstadoFicha, Evento, Ficha, TipoEvento
from backend.services.calculators import calculate_score_ponderado, detecta_drift
from backend.utils import get_logger, utcnow

log = get_logger(__name__)

# Enums válidos (copiar del prompt — si cambian, actualizar en ambos lados)
VALID_NIVEL_R = {"R1", "R2", "R3", "R4"}
VALID_POSICION_CICLO = {"early", "acceleration", "saturation"}
VALID_DURACION_EDGE = {"corto (0-12 meses)", "medio (12-36 meses)", "largo (36+ meses)"}
VALID_CATALIZADOR_TIPO = {"necesario", "util", "ninguno"}
VALID_CATALIZADOR_IMPACTO = {"alto", "medio", "bajo"}
VALID_MANAGEMENT_ALIGNMENT = {"alto", "medio", "bajo"}

ESTADOS_FRESHNESS_90D = {EstadoFicha.PORTFOLIO_ACTIVO.value, EstadoFicha.WL_PRIORITARIA.value}


class ValidacionError(Exception):
    """JSON del LLM no cumple el schema — aborta escritura."""


# ---------- Validador ----------

def _desempacar_output(output) -> dict | None:
    """Desempaca outputs intermitentes del LLM que vienen envueltos.

    Casos vistos en producción (2026-04-27):
    - lista con 1 dict: [{"prompt_version": ...}]
    - dict con una key wrapper: {"output": {...}} o {"result": {...}}
    Devuelve el dict desempacado o None si no es recuperable.
    """
    if isinstance(output, dict):
        # Si el dict tiene una única key wrapper conocida, desempacar.
        if len(output) == 1:
            wrapper_keys = {"output", "result", "json", "data", "response"}
            single_key = next(iter(output.keys()))
            if single_key in wrapper_keys and isinstance(output[single_key], dict):
                return output[single_key]
        return output
    if isinstance(output, list) and len(output) == 1 and isinstance(output[0], dict):
        return output[0]
    return None


REQUIRED_NUMERIC_FIELDS = (
    "bull_case_precio", "bear_case_precio",
    "estimacion_crecimiento", "crecimiento_implicito_precio",
)


def validar_output(output) -> list[str]:
    """Valida estructura y enums. Retorna lista de errores; vacía si OK.

    Antes de validar intenta desempacar wrappers comunes del LLM (lista de 1 dict,
    {"output": {...}}, etc.) — el caller debe usar el dict devuelto por _desempacar_output.
    """
    errores: list[str] = []
    if not isinstance(output, dict):
        return [f"output no es un dict (type={type(output).__name__})"]

    # Campos numéricos requeridos no pueden ser None (evita float(None) downstream).
    for k in REQUIRED_NUMERIC_FIELDS:
        if k in output and output[k] is None:
            errores.append(f"{k} es None — el LLM debe proveer un valor numérico")
        elif k in output and not isinstance(output[k], (int, float)):
            errores.append(f"{k} no es numérico (type={type(output[k]).__name__})")

    # Campos top-level requeridos
    required_top = {
        "prompt_version", "criterios", "nivel_r", "tesis_vigente",
        "posicion_ciclo", "duracion_edge", "invalidation_triggers",
        "catalizador_tipo", "plan_salida", "bull_case_precio",
        "bear_case_precio", "estimacion_crecimiento", "crecimiento_implicito_precio",
        "management_track_record", "management_alignment", "liquidez_suficiente",
    }
    missing = required_top - set(output.keys())
    if missing:
        errores.append(f"campos top-level faltantes: {sorted(missing)}")

    # Criterios
    crit = output.get("criterios")
    if not isinstance(crit, dict):
        errores.append("criterios no es dict")
    else:
        for i in range(1, 11):
            key = str(i)
            if key not in crit:
                errores.append(f"criterio {i} faltante")
                continue
            entry = crit[key]
            if not isinstance(entry, dict):
                errores.append(f"criterio {i} no es dict")
                continue
            if "score" not in entry or not isinstance(entry["score"], (int, float)):
                errores.append(f"criterio {i} sin score numérico")
            elif not (1 <= entry["score"] <= 10):
                errores.append(f"criterio {i} score fuera de rango [1,10]: {entry['score']}")
            for sub in ("evidencia_a_favor", "evidencia_en_contra", "justificacion"):
                if sub not in entry or not isinstance(entry[sub], str):
                    errores.append(f"criterio {i} sin {sub}")

    # Enums
    _check_enum(output, "nivel_r", VALID_NIVEL_R, errores)
    _check_enum(output, "posicion_ciclo", VALID_POSICION_CICLO, errores)
    _check_enum(output, "duracion_edge", VALID_DURACION_EDGE, errores)
    _check_enum(output, "catalizador_tipo", VALID_CATALIZADOR_TIPO, errores)
    _check_enum(output, "management_alignment", VALID_MANAGEMENT_ALIGNMENT, errores)
    if output.get("catalizador_tipo") != "ninguno":
        _check_enum(output, "catalizador_impacto", VALID_CATALIZADOR_IMPACTO, errores)

    # Triggers
    trigs = output.get("invalidation_triggers")
    if not isinstance(trigs, list) or len(trigs) < 1:
        errores.append("invalidation_triggers debe ser lista con al menos 1 elemento")
    elif not all(isinstance(t, str) and len(t.strip()) > 10 for t in trigs):
        errores.append("invalidation_triggers contiene elementos demasiado cortos o no-string")

    # Números
    for k in ("bull_case_precio", "bear_case_precio", "estimacion_crecimiento", "crecimiento_implicito_precio"):
        v = output.get(k)
        if v is not None and not isinstance(v, (int, float)):
            errores.append(f"{k} debe ser numérico, vino {type(v).__name__}")

    # liquidez
    if not isinstance(output.get("liquidez_suficiente"), bool):
        errores.append("liquidez_suficiente debe ser bool")

    # Coherencia bull > bear
    bull = output.get("bull_case_precio")
    bear = output.get("bear_case_precio")
    if isinstance(bull, (int, float)) and isinstance(bear, (int, float)) and bull <= bear:
        errores.append(f"bull_case ({bull}) debe ser mayor que bear_case ({bear})")

    return errores


def _check_enum(output: dict, key: str, valid: set, errores: list[str]):
    v = output.get(key)
    if v is None:
        errores.append(f"{key} faltante")
    elif v not in valid:
        errores.append(f"{key}={v!r} no es válido. Esperados: {sorted(valid)}")


# ---------- Estado post-análisis (doc 02 sec 4.7) ----------

def estado_sugerido_por_score(score: float | None, estado_actual: str) -> str:
    """Mapea score → estado sugerido.

    Thresholds recalibrados (2026-04-20) tras backtest real con Opus 4.7.
    Observación empírica: winners top out ~6.3, losers <3.6. Los cortes originales
    del doc (≥8 WL_Prioritaria) son inalcanzables en práctica. Ajuste:
      ≥7.0 → WL_Prioritaria (excepcional)
      ≥6.0 → WL_Activa (tesis sólida con gap menor)
      ≥5.0 → WL_Seguimiento (interesante pero requiere catalizador)
       <5  → Universo (especulativo o fuera de tesis)
    """
    if score is None:
        return estado_actual
    if score >= 7.0:
        return EstadoFicha.WL_PRIORITARIA.value
    if score >= 6.0:
        return EstadoFicha.WL_ACTIVA.value
    if score >= 5.0:
        return EstadoFicha.WL_SEGUIMIENTO.value
    return EstadoFicha.UNIVERSO.value


# ---------- Escritura de ficha ----------

@dataclass
class WriteResult:
    ticker: str
    score_anterior: float | None
    score_nuevo: float
    estado_anterior: str
    estado_sugerido: str
    drift_detectado: bool
    gaps: list[str]


def escribir_ficha(
    ticker: str,
    output,
    context_dict: dict,
    precio_actual: float | None,
) -> WriteResult:
    """Escribe los campos del Analista en la ficha, atómicamente.

    Tolera outputs envueltos del LLM (lista de 1 dict, {"output": {...}}).
    """
    # Desempacar wrappers comunes antes de validar
    desempacado = _desempacar_output(output)
    if desempacado is None:
        raise ValidacionError(
            f"output del LLM inválido — no es dict ni recuperable. "
            f"type={type(output).__name__}"
        )
    output = desempacado

    errores = validar_output(output)
    if errores:
        raise ValidacionError(f"output del LLM inválido: {errores}")

    ticker = ticker.upper()
    now = utcnow()

    # Score ponderado determinista
    crit = output["criterios"]
    scores = {i: crit[str(i)]["score"] for i in range(1, 11)}
    score_ponderado = calculate_score_ponderado(scores)
    if score_ponderado is None:
        raise ValidacionError("no se pudo calcular score_ponderado")

    drift_detectado = False

    with session_scope() as s:
        ficha = s.query(Ficha).filter_by(ticker=ticker).first()
        if ficha is None:
            raise ValidacionError(f"ticker {ticker} no existe en fichas")

        score_anterior = ficha.score_vigente
        estado_anterior = ficha.estado

        # Detectar drift ANTES de sobrescribir
        if detecta_drift(score_anterior, score_ponderado):
            evento_reciente = (
                s.query(Evento)
                .filter(
                    Evento.ticker == ticker,
                    Evento.estado.in_([EstadoEvento.PENDIENTE.value, EstadoEvento.PROCESADO.value]),
                    Evento.timestamp >= now - timedelta(days=7),
                )
                .first()
            )
            if evento_reciente is None:
                drift_detectado = True
                s.add(Evento(
                    ticker=ticker,
                    tipo=TipoEvento.SCORE_DRIFT.value,
                    descripcion=f"Score cambió de {score_anterior} a {score_ponderado} sin evento material reciente",
                    fuente="Analista",
                    tier=2,
                    timestamp=now,
                ))

        # Escritura atómica de los 10 criterios
        evidencia_favor = {}
        evidencia_contra = {}
        justif = {}
        confidences = {}  # v4.2: confidence + fuente_nivel por criterio
        for i in range(1, 11):
            setattr(ficha, f"score_criterio_{i}", float(crit[str(i)]["score"]))
            evidencia_favor[str(i)] = crit[str(i)]["evidencia_a_favor"]
            evidencia_contra[str(i)] = crit[str(i)]["evidencia_en_contra"]
            justif[str(i)] = crit[str(i)]["justificacion"]
            # v4.2 — Confidence + Jerarquía A-F (opcional para retrocompatibilidad).
            confidence = crit[str(i)].get("confidence")
            fuente_nivel = crit[str(i)].get("fuente_nivel")
            if confidence or fuente_nivel:
                confidences[str(i)] = {
                    "confidence": confidence,
                    "fuente_nivel": fuente_nivel,
                }

        ficha.evidencia_favor_json = evidencia_favor
        ficha.evidencia_contra_json = evidencia_contra
        ficha.justificacion_json = justif
        ficha.confidence_y_fuentes_json = confidences if confidences else None

        # Campos cualitativos
        ficha.score_vigente = score_ponderado
        ficha.nivel_r = output["nivel_r"]
        ficha.tesis_vigente = output["tesis_vigente"]
        ficha.posicion_ciclo = output["posicion_ciclo"]
        ficha.duracion_edge = output["duracion_edge"]
        ficha.duracion_edge_justificacion = output.get("duracion_edge_justificacion")
        ficha.invalidation_triggers = output["invalidation_triggers"]
        ficha.tipo_catalizador = output["catalizador_tipo"]
        ficha.catalizador_descripcion = output.get("catalizador_descripcion")
        ficha.catalizador_fecha = output.get("catalizador_fecha")
        ficha.catalizador_impacto = output.get("catalizador_impacto")
        ficha.plan_salida = output["plan_salida"]
        ficha.bull_case_precio = float(output["bull_case_precio"])
        ficha.bear_case_precio = float(output["bear_case_precio"])
        ficha.estimacion_crecimiento = float(output["estimacion_crecimiento"])
        ficha.crecimiento_implicito_precio = float(output["crecimiento_implicito_precio"])
        ficha.management_track_record = output["management_track_record"]
        ficha.management_alignment = output["management_alignment"]
        ficha.management_alignment_evidencia = output.get("management_alignment_evidencia")
        ficha.liquidez_suficiente = bool(output["liquidez_suficiente"])
        ficha.tam_excepcion = bool(output.get("tam_excepcion", False))

        # Contexto sectorial
        ficha.mapa_sectorial_usado = bool(context_dict.get("mapa_sectorial_activo"))
        ficha.mapa_sectorial_version = context_dict.get("mapa_sectorial_version")
        ficha.contexto_sectorial_citado = output.get("contexto_sectorial_citado")

        # Precio de referencia para alertas del Radar (doc 02 sec 2.1)
        if precio_actual is not None:
            ficha.precio_ultima_actualizacion_ficha = precio_actual

        # Meta
        ficha.prompt_version = output.get("prompt_version", "v1")
        ficha.fecha_ultimo_deep_research = now
        freshness_dias = 90 if estado_anterior in ESTADOS_FRESHNESS_90D else 180
        ficha.fecha_proximo_deep_research = now + timedelta(days=freshness_dias)
        ficha.ultima_evaluacion_triggers = now

        # Estado sugerido (no se cambia si ya es Portfolio_Activo o Bucket_Exploratorio — requieren aprobación humana)
        estado_sugerido = estado_sugerido_por_score(score_ponderado, estado_anterior)
        estados_humanos = {
            EstadoFicha.PORTFOLIO_ACTIVO.value,
            EstadoFicha.BUCKET_EXPLORATORIO.value,
            EstadoFicha.SUSPENDIDA.value,
            EstadoFicha.ELIMINADA.value,
        }
        if estado_anterior not in estados_humanos and estado_sugerido != estado_anterior:
            ficha.estado = estado_sugerido
            cambios = list(ficha.cambios_estado or [])
            cambios.append({
                "timestamp": now.isoformat(),
                "estado_anterior": estado_anterior,
                "estado_nuevo": estado_sugerido,
                "motivo": f"analista auto-promote por score {score_ponderado}",
            })
            ficha.cambios_estado = cambios

        # Append cambios_score
        cambios = list(ficha.cambios_score or [])
        cambios.append({
            "timestamp": now.isoformat(),
            "score_anterior": score_anterior,
            "score_nuevo": score_ponderado,
            "prompt_version": output.get("prompt_version", "v1"),
            "drift_alert": drift_detectado,
        })
        ficha.cambios_score = cambios

        # Re-armar piramidación tras deep research nuevo sobre una posición abierta.
        # Doc 01 sec 3: piramidación exige re-validación de tesis; un deep research
        # que no deteriora el score cuenta como re-validación.
        if (
            estado_anterior == EstadoFicha.PORTFOLIO_ACTIVO.value
            and score_anterior is not None
            and score_ponderado >= score_anterior
            and not ficha.piramidacion_disponible
        ):
            ficha.piramidacion_disponible = True
            log.info(
                "ANALISTA re-arm piramidación — ticker=%s score %s→%s",
                ticker, score_anterior, score_ponderado,
            )

        log.info(
            "ANALISTA wrote ficha — ticker=%s score=%s→%s estado=%s→%s drift=%s",
            ticker, score_anterior, score_ponderado,
            estado_anterior, ficha.estado, drift_detectado,
        )

        return WriteResult(
            ticker=ticker,
            score_anterior=score_anterior,
            score_nuevo=score_ponderado,
            estado_anterior=estado_anterior,
            estado_sugerido=ficha.estado,
            drift_detectado=drift_detectado,
            gaps=context_dict.get("gaps_detectados", []),
        )
