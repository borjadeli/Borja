"""Funciones deterministas — el núcleo cuantitativo del sistema.

Principio invariante (doc 02 sec 1): el LLM NUNCA calcula números desde texto.
Todas las métricas que el Analista le pasa al LLM se computan acá.

Cada función:
- Tiene tipo explícito.
- Es pura (no side effects).
- Loguea y retorna None ante datos insuficientes — nunca raisea.
- Es testeable sin red ni DB.
"""
from __future__ import annotations

from typing import Iterable

from backend.utils import get_logger

log = get_logger(__name__)


# ---------- Score ponderado (doc 01 sec 2) ----------

CRITERIOS_CORE = (1, 2, 3)       # peso x1.5
CRITERIOS_RESTO = (4, 5, 6, 7, 8, 9, 10)  # peso x1.0
PESO_CORE = 1.5
PESO_RESTO = 1.0
DIVISOR = 12.5  # 3*1.5 + 7*1.0 = 11.5 → el doc dice 12.5 (normaliza a 1-10 con algún buffer)


def calculate_score_ponderado(scores: dict[int, float | None]) -> float | None:
    """Score ponderado 1-10. CORE (1,2,3) x1.5, resto x1.0, divisor 12.5.

    Requiere scores de los 10 criterios. Si falta alguno → None.
    """
    try:
        vals = {int(k): float(v) if v is not None else None for k, v in scores.items()}
    except (TypeError, ValueError):
        return None
    for k in range(1, 11):
        if vals.get(k) is None:
            log.warning("score_ponderado: falta criterio %d", k)
            return None
    total = 0.0
    for k in CRITERIOS_CORE:
        total += vals[k] * PESO_CORE
    for k in CRITERIOS_RESTO:
        total += vals[k] * PESO_RESTO
    # Divisor 12.5 (doc 01 sec 2). Con todos 10s: 115/12.5 = 9.2 — la escala 9-10
    # deliberadamente difícil de alcanzar.
    return round(total / DIVISOR, 2)


# ---------- Asimetría R/R (doc 01 sec 3 Regla 1) ----------

def calculate_asymmetry(precio_actual: float | None, bull_case: float | None,
                       bear_case: float | None) -> float | None:
    """Ratio upside/downside al precio actual.

    upside = (bull - precio) / precio
    downside = (precio - bear) / precio  (positivo)
    asimetría = upside / downside

    Retorna None si algún dato falta o downside ≤ 0 (lo que implicaría que
    el precio ya está en/por debajo del bear case).
    """
    if precio_actual is None or bull_case is None or bear_case is None:
        return None
    if precio_actual <= 0:
        return None
    upside = (bull_case - precio_actual) / precio_actual
    downside = (precio_actual - bear_case) / precio_actual
    if downside <= 0:
        return None
    return round(upside / downside, 2)


# ---------- Movimiento acumulado (Radar — doc 02 sec 2.1) ----------

def calculate_movement_pct(precio_anterior: float | None, precio_actual: float | None) -> float | None:
    """% de movimiento acumulado desde precio_anterior hasta precio_actual."""
    if precio_anterior is None or precio_actual is None or precio_anterior <= 0:
        return None
    return round((precio_actual / precio_anterior - 1) * 100, 2)


# ---------- Crecimiento implícito en precio (doc 01 sec 2, Criterio 1 y 10) ----------

def calculate_implicit_growth(precio_actual: float | None, revenue_ttm: float | None,
                             shares_outstanding: float | None,
                             sector_multiple_revenue: float | None = 5.0,
                             horizonte_anios: int = 3) -> float | None:
    """% de crecimiento anual implícito en el precio actual, asumiendo que el mercado
    lo pricea a un múltiplo revenue_{t+horizonte} × sector_multiple.

    market_cap_actual = precio_actual × shares
    revenue_futuro_implicito = market_cap_actual / sector_multiple
    growth_anual_implicito = (revenue_futuro / revenue_ttm)^(1/h) - 1
    """
    if None in (precio_actual, revenue_ttm, shares_outstanding, sector_multiple_revenue):
        return None
    if revenue_ttm <= 0 or sector_multiple_revenue <= 0 or shares_outstanding <= 0:
        return None
    market_cap = precio_actual * shares_outstanding
    revenue_futuro = market_cap / sector_multiple_revenue
    ratio = revenue_futuro / revenue_ttm
    if ratio <= 0:
        return None
    growth = ratio ** (1 / horizonte_anios) - 1
    return round(growth * 100, 2)


# ---------- Runway (doc 02 sec 4.2, Criterio 7) ----------

def calculate_runway(cash: float | None, burn_rate_monthly: float | None) -> float | None:
    """Cash runway en meses. Si no hay burn (FCF>=0) → None (no aplica)."""
    if cash is None or burn_rate_monthly is None or burn_rate_monthly <= 0:
        return None
    return round(cash / burn_rate_monthly, 1)


# ---------- Deuda / revenue ----------

def calculate_deuda_revenue(total_debt: float | None, revenue_ttm: float | None) -> float | None:
    if total_debt is None or revenue_ttm is None or revenue_ttm <= 0:
        return None
    return round(total_debt / revenue_ttm, 2)


# ---------- Percentil sectorial ----------

def sector_percentile(valor: float | None, valores_sector: Iterable[float]) -> int | None:
    """Percentil 0-100 del valor dentro de la distribución sectorial.

    percentile = (# valores ≤ valor) / total × 100
    """
    if valor is None:
        return None
    lista = [v for v in valores_sector if v is not None]
    if not lista:
        return None
    por_debajo = sum(1 for v in lista if v <= valor)
    return int(round(por_debajo / len(lista) * 100))


# ---------- Sizing (doc 01 sec 2 Criterio 11 + sec 4) ----------

# Tabla de sizing base por nivel R × score (doc 01 tabla Criterio 11 + extensión
# empírica post-backtest 2026-04-21: bucket 6 agregado porque Opus 4.7 produce
# winners consistentes en 6.0-6.5, raramente >=7. Sizing de bucket 6 es ~70%
# del de bucket 7 — refleja menor convicción relativa.
SIZING_BASE = {
    "R1": {10: 15.0, 9: 15.0, 8: 12.0, 7: 10.0, 6: 7.0},
    "R2": {10: 12.0, 9: 12.0, 8: 10.0, 7: 8.0,  6: 5.0},
    "R3": {10: 10.0, 9: 10.0, 8: 7.0,  7: 5.0,  6: 3.0},
    "R4": {10: 7.0,  9: 7.0,  8: 5.0,  7: None, 6: None},  # R4 ≤7 = NO entrar
}

# Matriz convicción × momentum (v4.2 sec 4 — doc 04 tabla 9).
# Filas = convicción macro del sector (prioridad). Columnas = momentum v4.2.
# Valores = multiplicador sobre el techo R. None = no entrar.
MATRIZ_CONVICCION_MOMENTUM: dict[str, dict[str, float | None]] = {
    "alta": {
        "Favorable": 1.00,
        "Neutral": 0.85,
        "Desfavorable": 0.50,   # alerta + sin aumentar (no entrar nuevos)
    },
    "media-alta": {
        "Favorable": 0.85,
        "Neutral": 0.70,
        "Desfavorable": None,   # no entrar nuevo, existentes máx 50%
    },
    "media": {
        "Favorable": 0.70,
        "Neutral": 0.50,
        "Desfavorable": None,   # no entrar, rotar existentes
    },
}

# Umbral de rotación según momentum (v4.2). Mantiene la idea: en momentum bajo,
# si la tesis sectorial está cumplida, se rota más fácil.
UMBRAL_ROTACION = {
    "Favorable": 0.5,
    "Neutral": 1.0,
    "Desfavorable": 0.5,
    # legacy
    "pre_rally": 0.5,
    "rally_temprano": 0.5,
    "rally_maduro": 1.0,
    "agotamiento": 0.5,
}


def _normalizar_momentum(m: str | None) -> str | None:
    """Mapea momentum legacy al vocabulario v4.2."""
    if m in ("Favorable", "Neutral", "Desfavorable"):
        return m
    return {
        "pre_rally": "Favorable",
        "rally_temprano": "Favorable",
        "rally_maduro": "Neutral",
        "agotamiento": "Desfavorable",
    }.get(m)


def _normalizar_conviccion(p: str | None) -> str:
    """Normaliza la prioridad/convicción del sector. Default: 'media' (conservador)."""
    if not p:
        return "media"
    p_l = p.strip().lower()
    if p_l in ("alta", "media-alta", "media"):
        return p_l
    return "media"


def calculate_sizing(
    score: float | None,
    nivel_r: str | None,
    momentum_sectorial: str | None,
    conviccion_macro: str | None = None,
    duda: bool = False,
) -> dict[str, float | None]:
    """Sizing efectivo (v4.2 sec 4):

      Sizing final = Techo R × matriz(convicción × momentum) × multiplicador "ante la duda"

    El multiplicador CRR se aplica fuera de esta función (en portfolio._sizing_for_ficha).

    Returns: {
      "capacidad_maxima_teorica": float | None,    # techo del nivel R puro
      "sizing_sugerido": float | None,             # con matriz × duda aplicados
      "umbral_rotacion": float,                    # 0.5 o 1.0
      "motivo_no_entrar": str | None,
      "matriz_multiplier": float | None,           # multiplicador convicción×momentum
      "duda_multiplier": float,                    # 0.7 si duda, 1.0 si no
    }
    """
    out: dict[str, float | None] = {
        "capacidad_maxima_teorica": None,
        "sizing_sugerido": None,
        "umbral_rotacion": 0.5,
        "motivo_no_entrar": None,
        "matriz_multiplier": None,
        "duda_multiplier": 0.7 if duda else 1.0,
    }
    if score is None or nivel_r is None:
        out["motivo_no_entrar"] = "score o nivel R faltante"
        return out

    if nivel_r not in SIZING_BASE:
        out["motivo_no_entrar"] = f"nivel R desconocido: {nivel_r}"
        return out

    score_bucket = _score_bucket(score)
    if score_bucket is None:
        out["motivo_no_entrar"] = "score <7: no entrar"
        return out

    techo = SIZING_BASE[nivel_r].get(score_bucket)
    if techo is None:
        out["motivo_no_entrar"] = f"{nivel_r} + score {score_bucket}: NO entrar (doc 01 tabla R11)"
        return out

    out["capacidad_maxima_teorica"] = techo

    mom = _normalizar_momentum(momentum_sectorial) or "Favorable"
    conv = _normalizar_conviccion(conviccion_macro)
    matriz = MATRIZ_CONVICCION_MOMENTUM.get(conv, MATRIZ_CONVICCION_MOMENTUM["media"])
    mult = matriz.get(mom)
    out["matriz_multiplier"] = mult

    if mult is None:
        out["motivo_no_entrar"] = (
            f"matriz convicción×momentum (conv={conv}, mom={mom}): NO entrar (v4.2)"
        )
        return out

    sizing = techo * mult * out["duda_multiplier"]
    out["sizing_sugerido"] = round(sizing, 2)
    if mom == "Desfavorable":
        # Convicción Alta + Desfavorable: 50% del techo, alerta. No bloquear pero
        # marcar que no se debería aumentar.
        out["motivo_no_entrar"] = (
            f"momentum Desfavorable — sizing reducido a {sizing:.1f}% del techo R, sin aumentos"
        )
    out["umbral_rotacion"] = UMBRAL_ROTACION.get(mom, 0.5)
    return out


def _score_bucket(score: float) -> int | None:
    """Mapea score continuo a bucket de tabla (10, 9, 8, 7, 6). Score <6 → None."""
    if score >= 9.0:
        return 10 if score >= 9.5 else 9
    if score >= 8.0:
        return 8
    if score >= 7.0:
        return 7
    if score >= 6.0:
        return 6
    return None


# ---------- Liquidez ----------

UMBRAL_LIQUIDEZ_USD = 1_000_000


def liquidez_suficiente(volumen_diario_usd: float | None,
                       umbral: float = UMBRAL_LIQUIDEZ_USD) -> bool:
    """Regla doc 01 sec 6: volumen diario promedio >$1M."""
    if volumen_diario_usd is None:
        return False
    return volumen_diario_usd >= umbral


# ---------- Detección de drift de score (doc 02 sec 4.6, v1.4) ----------

UMBRAL_DRIFT_SCORE = 1.5


def detecta_drift(score_anterior: float | None, score_nuevo: float | None) -> bool:
    """True si la diferencia absoluta supera el umbral."""
    if score_anterior is None or score_nuevo is None:
        return False
    return abs(score_nuevo - score_anterior) >= UMBRAL_DRIFT_SCORE


# ---------- Market cap (combinado) ----------

def calculate_market_cap(precio_actual: float | None, shares_outstanding: float | None) -> float | None:
    if precio_actual is None or shares_outstanding is None:
        return None
    return precio_actual * shares_outstanding


# ---------- Capital Raise Risk (v4.2 sec 4 + 7) ----------

CRR_MULTIPLIER = {
    "Bajo": 1.00,
    "Medio": 0.85,
    "Alto": 0.70,
    "Crítico": 0.50,
}


def calculate_capital_raise_risk(
    dilution_pct_3y: float | None,
    runway_meses: float | None,
    shelf_count_24m: int | None,
    revenue_growth_yoy: float | None,
    revenue_ttm: float | None = None,
    going_concern: bool = False,
) -> dict:
    """CRR determinista basado en 5 señales:

    - Dilución 3y (% nuevas shares vs 3 años atrás)
    - Runway (cash / burn mensual)
    - Shelf registrations (S-1/S-3) en 24 meses
    - Revenue growth YoY (para distinguir dilución "buena" de "mala")
    - Revenue TTM (sanity check — si la empresa es grande/profitable, runway no aplica)
    - Going concern en 10-K (Fase 0 migración — fuga activa → Crítico directo)

    Reglas v4.2:
    - Crítico: going concern en 10-K O dilución >60% sin growth O runway <6m (small cap). → fail condition.
    - Alto: dilución >40% sin growth O runway <12m (small cap) O ≥4 shelf en 24m.
    - Medio: ≥3 shelf en 24m O runway <18m (small cap).
    - Bajo: default.

    Sanity check: si revenue_ttm > $500M, ignoramos señales de runway (FCF negativo
    en grandes suele ser capex o working capital, no burn real). El going concern NO
    tiene sanity check de tamaño: es lenguaje afirmativo del propio filing.
    """
    nivel = "Bajo"
    motivos: list[str] = []
    sin_growth = revenue_growth_yoy is None or revenue_growth_yoy < 10.0
    runway_aplica = revenue_ttm is None or revenue_ttm < 500_000_000

    # Crítico — going concern es FUGA ACTIVA (traspaso §2.2, Fase 0): el propio
    # filing declara duda sustancial sobre la continuidad. Va primero para que
    # encabece la evidencia; los demás chequeos Crítico igual se acumulan.
    if going_concern:
        nivel = "Crítico"
        motivos.append("going concern en 10-K (fuga activa)")

    # Crítico
    if dilution_pct_3y is not None and dilution_pct_3y > 60.0 and sin_growth:
        nivel = "Crítico"
        motivos.append(f"dilución 3y {dilution_pct_3y:.1f}% sin crecimiento revenue")
    if runway_aplica and runway_meses is not None and runway_meses < 6.0:
        nivel = "Crítico"
        motivos.append(f"runway {runway_meses:.1f} meses (<6m)")

    # Alto (si no es ya Crítico)
    if nivel != "Crítico":
        if dilution_pct_3y is not None and dilution_pct_3y > 40.0 and sin_growth:
            nivel = "Alto"
            motivos.append(f"dilución 3y {dilution_pct_3y:.1f}% sin crecimiento")
        if runway_aplica and runway_meses is not None and runway_meses < 12.0 and nivel != "Alto":
            nivel = "Alto"
            motivos.append(f"runway {runway_meses:.1f} meses (<12m)")
        if shelf_count_24m is not None and shelf_count_24m >= 4 and nivel != "Alto":
            nivel = "Alto"
            motivos.append(f"{shelf_count_24m} shelf registrations en 24m (≥4)")

    # Medio (si no es Alto/Crítico)
    if nivel == "Bajo":
        if shelf_count_24m is not None and shelf_count_24m >= 3:
            nivel = "Medio"
            motivos.append(f"{shelf_count_24m} shelf registrations en 24m (≥3)")
        if runway_aplica and runway_meses is not None and runway_meses < 18.0 and nivel != "Medio":
            nivel = "Medio"
            motivos.append(f"runway {runway_meses:.1f} meses (<18m)")

    return {
        "nivel": nivel,
        "multiplier": CRR_MULTIPLIER[nivel],
        "evidencia": motivos,
        "datos": {
            "dilucion_3y_pct": dilution_pct_3y,
            "runway_meses": runway_meses,
            "shelf_24m": shelf_count_24m,
            "revenue_growth_yoy": revenue_growth_yoy,
            "going_concern": going_concern,
        },
    }
