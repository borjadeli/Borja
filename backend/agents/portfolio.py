"""Agente PORTFOLIO — decisiones de capital (determinista, sin LLM).

Responsabilidad: dado el estado actual de una ficha, decidir qué acción de capital
recomendar (entrar / aumentar / piramidacion / mantener / reducir / salir / rotar /
cash_preventivo / wl_prioritaria). NO ejecuta. Produce una recomendación estructurada
para que el Juez la valide y el humano la apruebe.

Separación con Analista (doc 03 sec 7):
- Analista → capacidad máxima teórica (score × nivel R × momentum).
- Portfolio → posición efectiva dado slots, concentración, tesis macro, asimetría al precio actual.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from backend.database import session_scope
from backend.models import EstadoFicha, Ficha, Macro, Sector
from backend.services import market_data
from backend.services.calculators import (
    calculate_asymmetry,
    calculate_sizing,
    liquidez_suficiente,
)
from backend.utils import get_logger

log = get_logger(__name__)


# ---------- Constantes ----------

SLOT_PORTFOLIO_MAX = 10      # ajuste 2026-05-04 (era 5): ampliación de cartera a 10 posiciones formales
SLOT_BUCKET_MAX = 1          # doc 01 sec 1: máx 1 bucket exploratorio
MAX_POR_SECTOR = 3           # ajuste 2026-05-04 (era 2): coherente con cartera ampliada
MAX_POR_DRIVER = 3           # ajuste 2026-05-04 (era 2): coherente con cartera ampliada
EXPOSICION_PISO_PCT = 80.0   # ajuste 2026-05-04: cash libre permitido ≤20% — bajo el piso, 'entrar' se prioriza

# v4.2: claims centrales (criterios cuyo confidence Baja bloquea Portfolio).
# Doc 04 sec 8: "Confidence Baja en cualquier claim central → no Portfolio formal."
# Aplican criterios CORE (1-3) + Moat (4) + Calidad del Revenue (6).
CRITERIOS_CENTRALES = {1, 2, 3, 4, 6}


def claims_centrales_con_confidence_baja(ficha) -> list[int]:
    """Devuelve la lista de criterios centrales con confidence='Baja'. Vacía si no aplica.

    Si la ficha no tiene `confidence_y_fuentes_json` poblado (Analista pre-v4.2),
    retorna lista vacía (no bloquea — backward compat).
    """
    cfj = ficha.confidence_y_fuentes_json
    if not cfj:
        return []
    bajas: list[int] = []
    for c in CRITERIOS_CENTRALES:
        info = cfj.get(str(c)) or {}
        if (info.get("confidence") or "").lower() == "baja":
            bajas.append(c)
    return bajas
# Score mínimo calibrado empíricamente (2026-04-20) tras backtest real:
# Opus 4.7 puntúa en rango 4.8-6.3 para winners, <3.6 para losers. Score>=6
# aísla winners claros; 5.5-6 es zona "interesante con gap" (WL_Activa);
# 5-5.5 "borderline" WL_Seguimiento. Originalmente era 8.0 (doc 01) pero
# con el divisor 12.5 del score ponderado eso era inalcanzable en práctica.
SCORE_MIN_ENTRADA = 6.0
ROTATION_UMBRAL_SALIDA = 0.5  # asimetría <0.5x → rotar

# Asimetría mínima DINÁMICA por momentum sectorial (v4.2 — 3 estados).
# Mantiene la filosofía del v4.1 (mercado caliente → exigir más margen) en el
# vocabulario nuevo. Aliases legacy mapeados para retro-compat hasta que el
# scheduler/UI no emitan más los nombres viejos.
ASIMETRIA_MIN_POR_MOMENTUM = {
    "Favorable": 2.0,
    "Neutral": 2.5,
    "Desfavorable": None,   # no entrar
    # legacy (deprecated)
    "pre_rally": 2.0,
    "rally_temprano": 2.5,
    "rally_maduro": 3.0,
    "agotamiento": None,
    None: 2.0,
}


def asimetria_min_para_momentum(momentum: str | None) -> float | None:
    """Retorna la asimetría mínima requerida según momentum. None = no entrar."""
    return ASIMETRIA_MIN_POR_MOMENTUM.get(momentum, 2.0)

# Estados con posición de capital activa
ESTADOS_ACTIVOS = {
    EstadoFicha.PORTFOLIO_ACTIVO.value,
    EstadoFicha.BUCKET_EXPLORATORIO.value,
}

# Acciones posibles
class Accion:
    ENTRAR = "entrar"
    AUMENTAR = "aumentar"
    PIRAMIDACION = "piramidacion"
    BUCKET = "bucket"
    MANTENER = "mantener"
    REDUCIR = "reducir"
    SALIR = "salir"
    WL_PRIORITARIA = "wl_prioritaria"
    CASH_PREVENTIVO = "cash_preventivo"
    ROTAR = "rotar"


# ---------- Contenedor de recomendación ----------

@dataclass
class Recomendacion:
    ticker: str
    accion: str
    sizing_sugerido: float | None = None
    capacidad_maxima_teorica: float | None = None
    momentum_sectorial_leido: str | None = None
    asimetria_vigente: float | None = None
    umbral_rotacion_activo: float = 0.5
    reglas_verificadas: dict = field(default_factory=lambda: {
        "r1_asimetria": False, "r2_governance": False, "r3_concentracion": False,
    })
    checklist_completo: bool = False
    checklist_detalle: dict = field(default_factory=dict)
    contexto_macro: str | None = None
    nota_bucket: str | None = None
    justificacion: str = ""
    # Prioridad por piso de exposición (regla 2026-05-04): "alta" si exposición<80% y accion==entrar.
    prioridad_capital: str | None = None
    exposicion_pct_al_evaluar: float | None = None
    # Estado pre-Juez (el Juez puede marcarla CUESTIONADA)
    motivo_cuestionada: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


# ---------- Helpers de estado de cartera ----------

def contar_slots_portfolio(session) -> int:
    return (
        session.query(Ficha)
        .filter(Ficha.estado == EstadoFicha.PORTFOLIO_ACTIVO.value)
        .count()
    )


def contar_bucket(session) -> int:
    return (
        session.query(Ficha)
        .filter(Ficha.estado == EstadoFicha.BUCKET_EXPLORATORIO.value)
        .count()
    )


def concentracion_sectorial(session, sector: str, excluir_ticker: str | None = None) -> int:
    q = session.query(Ficha).filter(
        Ficha.sector == sector,
        Ficha.estado.in_(list(ESTADOS_ACTIVOS)),
    )
    if excluir_ticker:
        q = q.filter(Ficha.ticker != excluir_ticker)
    return q.count()


def concentracion_driver(session, cluster_driver: str | None, excluir_ticker: str | None = None) -> int:
    """Cuenta posiciones activas que comparten cluster_driver del sector (v4.2 Regla 3 ampliada).

    El cluster_driver vive en la tabla Sector. Ejemplo: AI infra (4 sub-temas)
    + Power Generation comparten 'capex_AI' → la regla aplica en cualquier
    combinación, no solo dentro de un sector individual.
    """
    if not cluster_driver:
        return 0
    sectores_en_cluster = [
        row.nombre for row in
        session.query(Sector).filter(Sector.cluster_driver == cluster_driver).all()
    ]
    if not sectores_en_cluster:
        return 0
    q = session.query(Ficha).filter(
        Ficha.sector.in_(sectores_en_cluster),
        Ficha.estado.in_(list(ESTADOS_ACTIVOS)),
    )
    if excluir_ticker:
        q = q.filter(Ficha.ticker != excluir_ticker)
    return q.count()


def cluster_driver_de_ficha(session, ficha: Ficha) -> str | None:
    """Lee el cluster_driver del sector de la ficha. None si el sector no está en un cluster."""
    sec = session.query(Sector).filter_by(nombre=ficha.sector).first()
    return sec.cluster_driver if sec else None


# ---------- Tesis intacta (doc 03 sec 7.1) ----------

def tesis_intacta(session, ficha: Ficha, sector_row: Sector | None) -> tuple[bool, list[str]]:
    """True + lista vacía si la tesis está intacta. False + motivos si no."""
    motivos: list[str] = []

    # 1. red_flags no aumentó
    if ficha.red_flags_count > ficha.red_flags_count_anterior:
        motivos.append(f"red_flags subió de {ficha.red_flags_count_anterior} a {ficha.red_flags_count}")

    # 2. revenue no recortado >20% (proxy: score cayó >=1.5 puntos en última eval).
    # Threshold 1.5 calibrado: el divisor del score es 12.5, entonces 1.5/12.5 ≈ 12%.
    # El doc 04 sec 5 menciona "revenue o guidance no ha sido recortado >20%" — proxy razonable.
    cambios = list(ficha.cambios_score or [])
    if cambios:
        ult = cambios[-1]
        ant = ult.get("score_anterior")
        nue = ult.get("score_nuevo")
        if ant is not None and nue is not None and (ant - nue) >= 1.5:
            motivos.append(f"score cayó de {ant} a {nue} (Δ-{ant-nue:.1f}) — proxy de deterioro de tesis")

    # 3. catalizador_necesario no fallido (si tipo=necesario, fecha no expiró sin ocurrencia)
    if ficha.tipo_catalizador == "necesario" and ficha.catalizador_fecha:
        # Fase 1: evaluación manual por el humano — el script solo flaggea si la fecha pasó
        # y el score no subió (implica que no ocurrió o no tuvo impacto)
        pass  # se profundiza en Sprint 3 con script nocturno

    # 4. selling atípico management — Fase 1 no parsea Form 4 detallado (Sprint 3)

    # 5. momentum sectorial != Desfavorable (v4.2) / agotamiento (legacy)
    if sector_row and sector_row.momentum in ("Desfavorable", "agotamiento"):
        motivos.append(f"momentum sectorial = {sector_row.momentum}")

    return (len(motivos) == 0, motivos)


# ---------- Checklist de entrada (doc 02 sec 5.2) ----------

def verificar_checklist_entrada(ficha: Ficha) -> dict:
    """Devuelve dict con True/False por cada ítem del checklist."""
    chk = {
        "invalidation_triggers_ok": bool(
            ficha.invalidation_triggers and len(ficha.invalidation_triggers) >= 1
        ),
        "plan_salida_definido": bool(ficha.plan_salida and len(ficha.plan_salida) > 20),
        "tipo_catalizador_definido": ficha.tipo_catalizador in ("necesario", "util", "ninguno"),
        "management_track_record_completo": bool(
            ficha.management_track_record and len(ficha.management_track_record) > 20
        ),
        "liquidez_suficiente": bool(ficha.liquidez_suficiente),
        "nivel_r_asignado": ficha.nivel_r in ("R1", "R2", "R3", "R4"),
    }
    chk["_todos_ok"] = all(v for k, v in chk.items() if not k.startswith("_"))
    return chk


# ---------- Lógica de evaluación ----------

def _contexto_macro_str(macro: Macro | None) -> str:
    if not macro:
        return "sin macro activa"
    return f"Estado macro: {macro.fase_actual} — Postura: {macro.postura_capital} ({macro.version})"


def _sizing_for_ficha(ficha: Ficha, momentum: str | None, conviccion: str | None = None) -> dict:
    """Sizing efectivo (v4.2 sec 4):

      Techo R × matriz(convicción×momentum) × multiplicador 'ante la duda' × CRR

    Si CRR Crítico → no entra (motivo_no_entrar).
    Si CRR Alto → no Portfolio formal (motivo_no_entrar, salvo Bucket).
    """
    from backend.services.calculators import CRR_MULTIPLIER

    base = calculate_sizing(
        score=ficha.score_vigente,
        nivel_r=ficha.nivel_r,
        momentum_sectorial=momentum,
        conviccion_macro=conviccion,
    )
    crr = ficha.capital_raise_risk
    if crr == "Crítico":
        base["motivo_no_entrar"] = "Capital Raise Risk Crítico — eliminar de universo (v4.2)"
        base["sizing_sugerido"] = None
        base["crr_nivel"] = crr
        base["crr_multiplier"] = CRR_MULTIPLIER.get(crr, 1.0)
        return base
    if crr == "Alto":
        base["motivo_no_entrar"] = "Capital Raise Risk Alto — solo bucket o eliminar, no Portfolio formal (v4.2)"
        # sizing_sugerido se mantiene (para bucket) pero con multiplicador
    base["crr_nivel"] = crr or "N/D"
    base["crr_multiplier"] = CRR_MULTIPLIER.get(crr, 1.0) if crr else 1.0
    if base.get("sizing_sugerido") is not None:
        base["sizing_sugerido"] = round(base["sizing_sugerido"] * base["crr_multiplier"], 2)
    return base


def evaluar_entrada(session, ficha: Ficha, sector_row: Sector | None, macro: Macro | None) -> Recomendacion:
    """Doc 03 sec 7.2. Se ejecuta sobre fichas que NO están en Portfolio_Activo."""
    rec = Recomendacion(
        ticker=ficha.ticker,
        accion=Accion.WL_PRIORITARIA,
        momentum_sectorial_leido=sector_row.momentum if sector_row else None,
        contexto_macro=_contexto_macro_str(macro),
    )

    # Score mínimo
    if (ficha.score_vigente or 0) < SCORE_MIN_ENTRADA:
        rec.accion = Accion.MANTENER
        rec.justificacion = f"Score {ficha.score_vigente} < {SCORE_MIN_ENTRADA} — no entrar, mantener estado actual."
        return rec

    # Checklist
    chk = verificar_checklist_entrada(ficha)
    rec.checklist_detalle = chk
    rec.checklist_completo = chk["_todos_ok"]

    # Asimetría al precio actual
    precio_actual = _get_precio_actual(ficha.ticker)
    asim = calculate_asymmetry(precio_actual, ficha.bull_case_precio, ficha.bear_case_precio)
    rec.asimetria_vigente = asim

    # Sizing
    siz = _sizing_for_ficha(
        ficha,
        sector_row.momentum if sector_row else None,
        conviccion=sector_row.prioridad if sector_row else None,
    )
    rec.capacidad_maxima_teorica = siz["capacidad_maxima_teorica"]
    rec.sizing_sugerido = siz["sizing_sugerido"]
    rec.umbral_rotacion_activo = siz["umbral_rotacion"]

    # Slots y concentración
    slots_port = contar_slots_portfolio(session)
    conc_sec = concentracion_sectorial(session, ficha.sector, excluir_ticker=ficha.ticker)
    cluster_drv = sector_row.cluster_driver if sector_row else None
    conc_drv = concentracion_driver(session, cluster_drv, excluir_ticker=ficha.ticker)

    no_entrar_razones: list[str] = []
    if siz["motivo_no_entrar"]:
        no_entrar_razones.append(siz["motivo_no_entrar"])
    if not rec.checklist_completo:
        faltantes = [k for k, v in chk.items() if not k.startswith("_") and not v]
        no_entrar_razones.append(f"checklist incompleto: {faltantes}")
    if slots_port >= SLOT_PORTFOLIO_MAX:
        no_entrar_razones.append(f"Portfolio lleno ({slots_port}/{SLOT_PORTFOLIO_MAX})")
    if conc_sec >= MAX_POR_SECTOR:
        no_entrar_razones.append(f"concentración sectorial: {conc_sec}/{MAX_POR_SECTOR} en {ficha.sector}")

    # v4.2: claims centrales con Confidence Baja bloquean Portfolio.
    centrales_baja = claims_centrales_con_confidence_baja(ficha)
    if centrales_baja:
        no_entrar_razones.append(
            f"Confidence Baja en claims centrales {centrales_baja} (v4.2) — solo WL hasta evidencia A/B"
        )
    if conc_drv >= MAX_POR_DRIVER:
        no_entrar_razones.append(f"concentración driver: {conc_drv}/{MAX_POR_DRIVER} en cluster '{cluster_drv}'")

    # Asimetría dinámica según momentum sectorial
    momentum_sec = sector_row.momentum if sector_row else None
    asim_min = asimetria_min_para_momentum(momentum_sec)
    if asim_min is None:
        no_entrar_razones.append(f"momentum={momentum_sec} — no entrar")
    elif asim is not None and asim < asim_min:
        no_entrar_razones.append(
            f"asimetría {asim}x < {asim_min}x (momentum {momentum_sec or 'null→conservador'})"
        )

    # Reglas verificadas
    rec.reglas_verificadas = {
        "r1_asimetria": (asim is not None and asim_min is not None and asim >= asim_min),
        "r2_governance": (ficha.red_flags_count < 2),
        "r3_concentracion": (
            slots_port < SLOT_PORTFOLIO_MAX
            and conc_sec < MAX_POR_SECTOR
            and conc_drv < MAX_POR_DRIVER
        ),
    }

    if no_entrar_razones:
        rec.accion = Accion.WL_PRIORITARIA
        rec.justificacion = "No entrar por: " + " | ".join(no_entrar_razones)
    else:
        rec.accion = Accion.ENTRAR
        rec.justificacion = (
            f"Score {ficha.score_vigente} ({ficha.nivel_r}), momentum {rec.momentum_sectorial_leido or 'N/D'}, "
            f"asimetría {asim}x. Checklist completo. Sizing {siz['sizing_sugerido']}% (max {siz['capacidad_maxima_teorica']}%)."
        )

    # Regla piso de exposición (2026-05-04): si vamos a entrar y la exposición vigente está
    # bajo el 80%, prioridad alta — el sistema busca completar cartera hasta el piso.
    if rec.accion == Accion.ENTRAR:
        try:
            from backend.agents.portfolio_snapshot import calcular_estado_portfolio
            estado_pf = calcular_estado_portfolio()
            exp = estado_pf.get("exposicion_pct")
            rec.exposicion_pct_al_evaluar = exp
            if exp is not None and exp < EXPOSICION_PISO_PCT:
                rec.prioridad_capital = "alta"
                rec.justificacion += (
                    f" Prioridad alta: exposición {exp}% < piso {EXPOSICION_PISO_PCT}% — completar hasta el piso."
                )
        except Exception as exc:  # noqa: BLE001 — no romper recomendación si snapshot falla
            log.warning("no se pudo computar exposicion_pct_al_evaluar: %s", exc)

    return rec


def evaluar_rotacion(session, ficha: Ficha, sector_row: Sector | None, macro: Macro | None) -> Recomendacion:
    """Para fichas en Portfolio_Activo o Bucket_Exploratorio (doc 03 sec 7.2)."""
    rec = Recomendacion(
        ticker=ficha.ticker,
        accion=Accion.MANTENER,
        momentum_sectorial_leido=sector_row.momentum if sector_row else None,
        contexto_macro=_contexto_macro_str(macro),
    )
    precio_actual = _get_precio_actual(ficha.ticker)
    asim = calculate_asymmetry(precio_actual, ficha.bull_case_precio, ficha.bear_case_precio)
    rec.asimetria_vigente = asim
    umbral = ficha.umbral_rotacion or 0.5
    rec.umbral_rotacion_activo = umbral

    # Red flags = 3 → kill switch salida urgente (doc 01 sec 3 Regla 2)
    if ficha.red_flags_count >= 3:
        rec.accion = Accion.SALIR
        rec.justificacion = "3 red flags activos — kill switch. Salida urgente."
        rec.reglas_verificadas["r2_governance"] = False
        return rec

    # Asimetría < 0.5x → rotar
    if asim is not None and asim < ROTATION_UMBRAL_SALIDA:
        rec.accion = Accion.ROTAR
        rec.justificacion = f"Asimetría vigente {asim}x < {ROTATION_UMBRAL_SALIDA}x — recomendar rotación."
        return rec

    # Asimetría bajo umbral pero >0.5 → mantener sin aumentar
    if asim is not None and asim < 1.0 and umbral >= 1.0:
        rec.accion = Accion.MANTENER
        rec.justificacion = f"Asimetría {asim}x bajo umbral {umbral}x pero >0.5 — mantener sin aumentar."
        return rec

    # Score cayó <6 — doc 04 sec 5: rotar SOLO si además la tesis no está intacta.
    # Las 5 condiciones de tesis intacta (sin red flags nuevos / revenue no -20% /
    # catalizador no fallado / sin selling atípico / momentum no Desfavorable
    # sostenido) las verifica `tesis_intacta`. Si está intacta → mantener (caída
    # de score con tesis sana NO justifica salida según el doc).
    if (ficha.score_vigente or 10) < 6.0:
        intacta, motivos_no_intacta = tesis_intacta(session, ficha, sector_row)
        if not intacta:
            rec.accion = Accion.ROTAR
            rec.justificacion = (
                f"Score {ficha.score_vigente} < 6 + tesis NO intacta (doc 04 sec 5). "
                f"Motivos: {' | '.join(motivos_no_intacta)}"
            )
            return rec
        rec.accion = Accion.MANTENER
        rec.justificacion = (
            f"Score {ficha.score_vigente} < 6 PERO tesis intacta (doc 04 sec 5: "
            f"'no rotar por score que baja levemente con tesis intacta'). Mantener con alerta."
        )
        return rec

    # Tesis intacta + asimetría mejoró → oportunidad de aumentar (piramidación)
    intacta, motivos = tesis_intacta(session, ficha, sector_row)
    if intacta and asim is not None and asim >= 3.0:
        # v4.2: bloquear aumentos en Convicción Alta + Momentum Desfavorable.
        conviccion = (sector_row.prioridad or "").lower() if sector_row else ""
        mom_actual = sector_row.momentum if sector_row else None
        # Compat: aceptar tanto "Desfavorable" (v4.2) como "agotamiento" (legacy).
        es_desfavorable = mom_actual in ("Desfavorable", "agotamiento")
        bloqueo_v42 = (conviccion == "alta" and es_desfavorable)
        if ficha.piramidacion_disponible and ficha.red_flags_count < 2 and not bloqueo_v42:
            rec.accion = Accion.PIRAMIDACION
            rec.justificacion = f"Tesis intacta, asimetría {asim}x ≥3x y piramidación disponible. Evaluar aumento."
            return rec
        if bloqueo_v42:
            rec.accion = Accion.MANTENER
            rec.justificacion = (
                f"Tesis intacta y asimetría {asim}x, pero Convicción Alta + Momentum Desfavorable "
                f"(v4.2): aumentos bloqueados. Mantener sizing actual."
            )
            return rec

    # Default: mantener
    rec.accion = Accion.MANTENER
    intacta_txt = "intacta" if intacta else f"comprometida ({'; '.join(motivos)})"
    rec.justificacion = f"Score {ficha.score_vigente}, asimetría {asim}x, tesis {intacta_txt}. Sin catalizador de cambio — mantener."
    return rec


def evaluar_candidata(session, ficha: Ficha, sector_row: Sector | None, macro: Macro | None) -> Recomendacion:
    """Para fichas en Universo/WL_Activa/WL_Seguimiento/Candidata — foco en promoción de estado, no entrada de capital."""
    rec = Recomendacion(
        ticker=ficha.ticker,
        accion=Accion.MANTENER,
        momentum_sectorial_leido=sector_row.momentum if sector_row else None,
        contexto_macro=_contexto_macro_str(macro),
    )
    if (ficha.score_vigente or 0) >= SCORE_MIN_ENTRADA:
        # Score alto — proponer WL_Prioritaria (el estado ya lo setea el Analista auto, pero generamos rec)
        return evaluar_entrada(session, ficha, sector_row, macro)

    rec.justificacion = (
        f"Estado {ficha.estado}, score {ficha.score_vigente}. Sin acción de capital recomendada."
    )
    return rec


# ---------- Entry point ----------

def generar_recomendacion(ticker: str) -> Recomendacion:
    """Dispatch según estado actual de la ficha."""
    ticker = ticker.upper()
    with session_scope() as s:
        ficha = s.query(Ficha).filter_by(ticker=ticker).first()
        if ficha is None:
            raise ValueError(f"ficha {ticker} no existe")
        sector_row = s.query(Sector).filter_by(nombre=ficha.sector).first()
        macro = s.query(Macro).filter_by(activa=True).first()

        if ficha.estado in ESTADOS_ACTIVOS:
            return evaluar_rotacion(s, ficha, sector_row, macro)
        if ficha.estado == EstadoFicha.WL_PRIORITARIA.value:
            return evaluar_entrada(s, ficha, sector_row, macro)
        return evaluar_candidata(s, ficha, sector_row, macro)


# ---------- Helpers ----------

def _get_precio_actual(ticker: str) -> float | None:
    snap = market_data.get_price_snapshot(ticker)
    return snap.precio_actual if snap else None
