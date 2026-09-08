"""Agente JUEZ — supervisor del sistema (determinista, sin LLM en Sprint 2).

Tres subfunciones independientes (doc 03 sec 8):

A) Risk Monitor: supervisa posiciones activas — sizing excedido, red flags, asimetría bajo
   umbral, concentración sectorial/driver, bucket stop-loss, coexistencia bucket+excepción.

B) Process Auditor: supervisa completeness de fichas Portfolio/WL Prioritaria — deep
   research vencido, triggers faltantes, plan salida faltante, management incompleto,
   liquidez insuficiente, catalizador vencido sin downgrade.

C) Validar Recomendación: valida cada recomendación del Portfolio antes de que vaya al
   humano — checklist completo, concentración, sizing ≤ máximo teórico, condición de
   rotación cumplida, piramidación disponible.

El LLM se usa solo para la narrativa del reporte semanal (Sprint 3).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any

from backend.agents.portfolio import (
    Accion,
    ESTADOS_ACTIVOS,
    MAX_POR_DRIVER,
    MAX_POR_SECTOR,
    SLOT_BUCKET_MAX,
    SLOT_PORTFOLIO_MAX,
    Recomendacion,
    concentracion_driver,
    concentracion_sectorial,
    contar_bucket,
    contar_slots_portfolio,
    verificar_checklist_entrada,
)
from backend.database import session_scope
from backend.models import EstadoFicha, Ficha, Macro, Sector
from backend.services import market_data
from backend.services.calculators import (
    calculate_asymmetry,
    calculate_sizing,
)
from backend.utils import get_logger, utcnow

log = get_logger(__name__)

# Tracking de qué tickers ya tuvieron alerta email enviada — evita spam.
# Se resetea al reiniciar el proceso. Las alertas se re-envían si el estado cambia y vuelve.
_alertas_enviadas_ticker: dict[str, set[str]] = {}


def _ya_alertado(ticker: str, tipo: str) -> bool:
    return tipo in _alertas_enviadas_ticker.get(ticker, set())


def _marcar_alertado(ticker: str, tipo: str) -> None:
    _alertas_enviadas_ticker.setdefault(ticker, set()).add(tipo)


def _desmarcar_alertado(ticker: str, tipo: str) -> None:
    _alertas_enviadas_ticker.get(ticker, set()).discard(tipo)


# ---------- Enums y tipos ----------

class AlertaTipo:
    SIZING_EXCEDIDO = "SIZING_EXCEDIDO"
    RED_FLAGS = "RED_FLAGS"
    ROTACION_PENDIENTE = "ROTACION_PENDIENTE"
    CONCENTRACION_SECTOR = "CONCENTRACION_SECTOR"
    CONCENTRACION_DRIVER = "CONCENTRACION_DRIVER"
    BUCKET_STOP_LOSS = "BUCKET_STOP_LOSS"
    BUCKET_COEXISTENCIA = "BUCKET_COEXISTENCIA"
    KILL_SWITCH = "KILL_SWITCH"
    # v4.2: Convicción Alta + Momentum Desfavorable → alerta humana, sin trim automático.
    CONVICCION_ALTA_MOMENTUM_DESFAVORABLE = "CONVICCION_ALTA_MOMENTUM_DESFAVORABLE"


# ---------- Mapeo momentum 4 → 3 estados (v4.2) ----------

def momentum_v42(momentum: str | None) -> str | None:
    """Normaliza momentum al vocabulario v4.2 (Favorable/Neutral/Desfavorable).

    Si ya viene en formato v4.2, devuelve tal cual. Si viene en formato legacy
    (pre_rally/rally_temprano/rally_maduro/agotamiento), lo mapea.
    """
    if momentum in ("Favorable", "Neutral", "Desfavorable"):
        return momentum
    return {
        "pre_rally": "Favorable",
        "rally_temprano": "Favorable",
        "rally_maduro": "Neutral",
        "agotamiento": "Desfavorable",
    }.get(momentum)


class ProcessItemTipo:
    FICHA_DESACTUALIZADA = "FICHA_DESACTUALIZADA"
    TRIGGER_FALTANTE = "TRIGGER_FALTANTE"
    PLAN_SALIDA_FALTANTE = "PLAN_SALIDA_FALTANTE"
    MANAGEMENT_INCOMPLETO = "MANAGEMENT_INCOMPLETO"
    LIQUIDEZ_INSUFICIENTE = "LIQUIDEZ_INSUFICIENTE"
    CATALIZADOR_VENCIDO = "CATALIZADOR_VENCIDO"
    TRIGGERS_SIN_EVALUAR = "TRIGGERS_SIN_EVALUAR"


@dataclass
class Alerta:
    tipo: str
    ticker: str
    severidad: str  # alta | media | baja
    descripcion: str
    contexto: dict = field(default_factory=dict)


@dataclass
class ProcessItem:
    tipo: str
    ticker: str
    descripcion: str
    dias_vencido: int | None = None


# ---------- Subfunción A — Risk Monitor ----------

def risk_monitor(notificar_email: bool = True) -> list[Alerta]:
    """Supervisa posiciones activas (Portfolio_Activo + Bucket_Exploratorio).

    Si `notificar_email=True`, dispara emails críticos para kill_switch y bucket_stop_loss
    (una vez por ticker hasta que cambie el estado, evita spam).
    """
    alertas: list[Alerta] = []
    with session_scope() as s:
        activas = (
            s.query(Ficha)
            .filter(Ficha.estado.in_(list(ESTADOS_ACTIVOS)))
            .all()
        )

        # Por posición activa
        for f in activas:
            sector_row = s.query(Sector).filter_by(nombre=f.sector).first()
            momentum = sector_row.momentum if sector_row else None

            # Sizing excedido (sizing_actual > capacidad_maxima_teorica_ajustada)
            siz = calculate_sizing(f.score_vigente, f.nivel_r, momentum)
            capacidad = siz.get("capacidad_maxima_teorica")
            if (
                f.sizing_actual is not None
                and capacidad is not None
                and f.sizing_actual > capacidad + 0.5  # margen 0.5pp
            ):
                alertas.append(Alerta(
                    tipo=AlertaTipo.SIZING_EXCEDIDO,
                    ticker=f.ticker,
                    severidad="media",
                    descripcion=f"Sizing actual {f.sizing_actual}% > máximo teórico {capacidad}%",
                    contexto={"sizing_actual": f.sizing_actual, "capacidad": capacidad, "momentum": momentum},
                ))

            # Red flags
            if f.red_flags_count >= 3:
                alertas.append(Alerta(
                    tipo=AlertaTipo.KILL_SWITCH,
                    ticker=f.ticker,
                    severidad="alta",
                    descripcion=f"Kill switch: {f.red_flags_count} red flags activos. Salida urgente.",
                    contexto={"red_flags": f.red_flags_count, "detalle": f.red_flags_detalle},
                ))
                if notificar_email and not _ya_alertado(f.ticker, "kill_switch"):
                    from backend.services import mailer
                    try:
                        mailer.alert_kill_switch(f.ticker, f.red_flags_count, f.red_flags_detalle)
                        _marcar_alertado(f.ticker, "kill_switch")
                    except Exception as e:  # noqa: BLE001
                        log.error("alert_kill_switch email fallo: %s", e)
            elif f.red_flags_count >= 2:
                alertas.append(Alerta(
                    tipo=AlertaTipo.RED_FLAGS,
                    ticker=f.ticker,
                    severidad="media",
                    descripcion=f"{f.red_flags_count} red flags activos — no aumentar posición.",
                    contexto={"red_flags": f.red_flags_count, "detalle": f.red_flags_detalle},
                ))
                if notificar_email and not _ya_alertado(f.ticker, "red_flags_2"):
                    from backend.services import mailer
                    try:
                        mailer.alert_red_flags_nivel_2(f.ticker, f.red_flags_count, f.red_flags_detalle)
                        _marcar_alertado(f.ticker, "red_flags_2")
                    except Exception as e:  # noqa: BLE001
                        log.error("alert_red_flags email fallo: %s", e)
            else:
                # Si red_flags cayó a <2, permite volver a notificar si sube
                _desmarcar_alertado(f.ticker, "kill_switch")
                _desmarcar_alertado(f.ticker, "red_flags_2")

            # Asimetría vigente < umbral rotación
            precio = _get_precio_actual(f.ticker)
            asim = calculate_asymmetry(precio, f.bull_case_precio, f.bear_case_precio)
            umbral = f.umbral_rotacion or 0.5
            if asim is not None and asim < umbral:
                alertas.append(Alerta(
                    tipo=AlertaTipo.ROTACION_PENDIENTE,
                    ticker=f.ticker,
                    severidad="alta" if asim < 0.5 else "media",
                    descripcion=f"Asimetría vigente {asim}x < umbral {umbral}x — evaluar rotación.",
                    contexto={"asimetria": asim, "umbral": umbral, "precio_actual": precio},
                ))

            # Bucket stop-loss
            if (
                f.estado == EstadoFicha.BUCKET_EXPLORATORIO.value
                and f.stop_loss_pct is not None
                and f.precio_entrada
                and precio
            ):
                caida_pct = (precio / f.precio_entrada - 1) * 100
                if caida_pct <= -abs(f.stop_loss_pct):
                    alertas.append(Alerta(
                        tipo=AlertaTipo.BUCKET_STOP_LOSS,
                        ticker=f.ticker,
                        severidad="alta",
                        descripcion=f"Bucket stop-loss: caída {caida_pct:.1f}% ≥ stop {f.stop_loss_pct}%. Requiere acción humana.",
                        contexto={"caida_pct": round(caida_pct, 2), "stop_loss_pct": f.stop_loss_pct},
                    ))
                    if notificar_email and not _ya_alertado(f.ticker, "bucket_stop_loss"):
                        from backend.services import mailer
                        try:
                            mailer.alert_bucket_stop_loss(
                                f.ticker, caida_pct, f.stop_loss_pct, f.precio_entrada,
                            )
                            _marcar_alertado(f.ticker, "bucket_stop_loss")
                        except Exception as e:  # noqa: BLE001
                            log.error("alert_bucket_stop_loss email fallo: %s", e)
                else:
                    _desmarcar_alertado(f.ticker, "bucket_stop_loss")

        # Concentración sectorial
        sectores_vistos: set[str] = set()
        for f in activas:
            if f.sector in sectores_vistos:
                continue
            sectores_vistos.add(f.sector)
            cnt = concentracion_sectorial(s, f.sector)
            if cnt > MAX_POR_SECTOR:
                alertas.append(Alerta(
                    tipo=AlertaTipo.CONCENTRACION_SECTOR,
                    ticker="(portfolio)",
                    severidad="media",
                    descripcion=f"Sector {f.sector} con {cnt} posiciones — excede máximo {MAX_POR_SECTOR}.",
                    contexto={"sector": f.sector, "count": cnt, "max": MAX_POR_SECTOR},
                ))

        # Concentración por cluster_driver del sector (v4.2 Regla 3 ampliada).
        clusters_vistos: set[str] = set()
        sectores_por_nombre = {sec.nombre: sec for sec in s.query(Sector).all()}
        for f in activas:
            sec = sectores_por_nombre.get(f.sector)
            cluster = sec.cluster_driver if sec else None
            if not cluster or cluster in clusters_vistos:
                continue
            clusters_vistos.add(cluster)
            cnt = concentracion_driver(s, cluster)
            if cnt > MAX_POR_DRIVER:
                alertas.append(Alerta(
                    tipo=AlertaTipo.CONCENTRACION_DRIVER,
                    ticker="(portfolio)",
                    severidad="media",
                    descripcion=f"Cluster '{cluster}' con {cnt} posiciones — excede máximo {MAX_POR_DRIVER}.",
                    contexto={"cluster_driver": cluster, "count": cnt, "max": MAX_POR_DRIVER},
                ))

        # Coexistencia bucket + excepción controlada
        bucket_activo = contar_bucket(s) > 0
        fichas_con_excepcion = (
            s.query(Ficha)
            .filter(Ficha.estado == EstadoFicha.PORTFOLIO_ACTIVO.value)
            .filter(Ficha.tam_excepcion.is_(True))
            .count()
        )
        if bucket_activo and fichas_con_excepcion > 0:
            alertas.append(Alerta(
                tipo=AlertaTipo.BUCKET_COEXISTENCIA,
                ticker="(portfolio)",
                severidad="alta",
                descripcion="Bucket exploratorio y excepción controlada coexisten — violación de regla (doc 01 sec 7).",
                contexto={"bucket_activo": True, "excepciones": fichas_con_excepcion},
            ))

        # v4.2 — Convicción Alta + Momentum Desfavorable: alerta obligatoria, sin trim automático.
        # Sizing máximo permitido: 50% del techo R. Si supera y no hay catalizador <90d → trim manual.
        for f in activas:
            sec = sectores_por_nombre.get(f.sector)
            if sec is None:
                continue
            conviccion = (sec.prioridad or "").lower()  # 'alta' / 'media-alta' / 'media'
            mom_v42 = momentum_v42(sec.momentum)
            if conviccion == "alta" and mom_v42 == "Desfavorable":
                alertas.append(Alerta(
                    tipo=AlertaTipo.CONVICCION_ALTA_MOMENTUM_DESFAVORABLE,
                    ticker=f.ticker,
                    severidad="media",
                    descripcion=(
                        f"{f.ticker} ({f.sector}) — Convicción Alta + Momentum Desfavorable. "
                        f"Bloquear aumentos. Sizing máx 50% del techo R. "
                        f"Si excede 50% sin catalizador <90 días, trim manual."
                    ),
                    contexto={
                        "sector": f.sector,
                        "conviccion": conviccion,
                        "momentum_v42": mom_v42,
                        "sizing_actual_pct": f.sizing_actual,
                        "catalizador_fecha": f.catalizador_fecha,
                    },
                ))

    return alertas


# ---------- Subfunción B — Process Auditor ----------

def process_auditor() -> list[ProcessItem]:
    """Supervisa completeness de fichas Portfolio + WL_Prioritaria."""
    items: list[ProcessItem] = []
    now = utcnow()
    with session_scope() as s:
        relevantes = (
            s.query(Ficha)
            .filter(Ficha.estado.in_([
                EstadoFicha.PORTFOLIO_ACTIVO.value,
                EstadoFicha.WL_PRIORITARIA.value,
                EstadoFicha.BUCKET_EXPLORATORIO.value,
            ]))
            .all()
        )
        for f in relevantes:
            # Ficha desactualizada
            if f.fecha_proximo_deep_research and f.fecha_proximo_deep_research < now:
                dias = (now - f.fecha_proximo_deep_research).days
                items.append(ProcessItem(
                    tipo=ProcessItemTipo.FICHA_DESACTUALIZADA,
                    ticker=f.ticker,
                    descripcion=f"Deep research vencido hace {dias} días",
                    dias_vencido=dias,
                ))
            # Triggers faltantes
            if not f.invalidation_triggers:
                items.append(ProcessItem(
                    tipo=ProcessItemTipo.TRIGGER_FALTANTE,
                    ticker=f.ticker,
                    descripcion="Sin invalidation_triggers definidos",
                ))
            # Plan salida
            if not f.plan_salida or len(f.plan_salida) < 20:
                items.append(ProcessItem(
                    tipo=ProcessItemTipo.PLAN_SALIDA_FALTANTE,
                    ticker=f.ticker,
                    descripcion="plan_salida ausente o muy corto",
                ))
            # Management
            if not f.management_track_record or len(f.management_track_record) < 20:
                items.append(ProcessItem(
                    tipo=ProcessItemTipo.MANAGEMENT_INCOMPLETO,
                    ticker=f.ticker,
                    descripcion="management_track_record ausente o muy corto",
                ))
            # Liquidez
            if not f.liquidez_suficiente:
                items.append(ProcessItem(
                    tipo=ProcessItemTipo.LIQUIDEZ_INSUFICIENTE,
                    ticker=f.ticker,
                    descripcion="liquidez_suficiente = False",
                ))
            # Triggers sin evaluar >7 días
            if f.ultima_evaluacion_triggers and (now - f.ultima_evaluacion_triggers).days > 7:
                items.append(ProcessItem(
                    tipo=ProcessItemTipo.TRIGGERS_SIN_EVALUAR,
                    ticker=f.ticker,
                    descripcion=f"Triggers no revisados hace {(now - f.ultima_evaluacion_triggers).days} días",
                    dias_vencido=(now - f.ultima_evaluacion_triggers).days,
                ))
            # Catalizador vencido sin downgrade (Fase 1: check de fecha string)
            if f.tipo_catalizador in ("necesario", "util") and f.catalizador_fecha:
                expired = _fecha_catalizador_vencida(f.catalizador_fecha, now)
                if expired:
                    items.append(ProcessItem(
                        tipo=ProcessItemTipo.CATALIZADOR_VENCIDO,
                        ticker=f.ticker,
                        descripcion=f"Catalizador {f.tipo_catalizador} con fecha {f.catalizador_fecha} ya pasó — evaluar downgrade",
                    ))
    return items


# ---------- Subfunción C — Validar Recomendación ----------

def validar_recomendacion(rec: Recomendacion) -> tuple[str, str | None]:
    """Valida una recomendación del Portfolio. Retorna (estado, motivo).

    estado: "VALIDADA" o "CUESTIONADA"
    motivo: None si VALIDADA, string descriptivo si CUESTIONADA
    """
    with session_scope() as s:
        ficha = s.query(Ficha).filter_by(ticker=rec.ticker).first()
        if ficha is None:
            return "CUESTIONADA", f"ficha {rec.ticker} no existe"

        # Regla 1: recomendación de entrar requiere checklist + concentración + sizing
        if rec.accion == Accion.ENTRAR:
            if not rec.checklist_completo:
                faltantes = [
                    k for k, v in (rec.checklist_detalle or {}).items()
                    if not k.startswith("_") and not v
                ]
                return "CUESTIONADA", f"checklist incompleto: {faltantes}"

            # Asimetría dinámica según momentum (coherente con portfolio.py)
            from backend.agents.portfolio import asimetria_min_para_momentum
            asim_min = asimetria_min_para_momentum(rec.momentum_sectorial_leido)
            if asim_min is None:
                return "CUESTIONADA", f"momentum={rec.momentum_sectorial_leido} — no entrar"
            if rec.asimetria_vigente is not None and rec.asimetria_vigente < asim_min:
                return "CUESTIONADA", (
                    f"asimetría {rec.asimetria_vigente}x < {asim_min}x "
                    f"(momentum {rec.momentum_sectorial_leido or 'null→conservador'})"
                )

            if not rec.reglas_verificadas.get("r3_concentracion"):
                return "CUESTIONADA", "regla 3 de concentración no verificada"

            if (
                rec.sizing_sugerido is not None
                and rec.capacidad_maxima_teorica is not None
                and rec.sizing_sugerido > rec.capacidad_maxima_teorica + 0.01
            ):
                return "CUESTIONADA", f"sizing {rec.sizing_sugerido}% excede máximo teórico {rec.capacidad_maxima_teorica}%"

        # Regla 2: rotar/salir requiere alguna condición de rotación cumplida
        if rec.accion in (Accion.ROTAR, Accion.SALIR):
            asim_baja = rec.asimetria_vigente is not None and rec.asimetria_vigente < rec.umbral_rotacion_activo
            red_flags = ficha.red_flags_count >= 3
            score_bajo = (ficha.score_vigente or 10) < 6.0
            if not (asim_baja or red_flags or score_bajo):
                return "CUESTIONADA", "no hay condición de rotación cumplida (asimetría, red flags, o score bajo)"

        # Regla 3: piramidacion requiere piramidacion_disponible
        if rec.accion == Accion.PIRAMIDACION:
            if not ficha.piramidacion_disponible:
                return "CUESTIONADA", "piramidacion_disponible=False (ya se usó entre deep researches)"
            if ficha.red_flags_count >= 2:
                return "CUESTIONADA", f"{ficha.red_flags_count} red flags activos — no aumentar"

        # Bucket con slot ocupado → alternativa WL_Prioritaria
        if rec.accion == Accion.BUCKET and contar_bucket(s) >= SLOT_BUCKET_MAX:
            return "CUESTIONADA", "slot de bucket ocupado — evaluar WL_Prioritaria como alternativa"

    return "VALIDADA", None


# ---------- Helpers ----------

def _get_precio_actual(ticker: str) -> float | None:
    snap = market_data.get_price_snapshot(ticker)
    return snap.precio_actual if snap else None


def _fecha_catalizador_vencida(fecha_str: str, now: datetime) -> bool:
    """Parser simple para formatos tipo '2026-Q3' / '2026-12-31' / '2026-12'."""
    if not fecha_str:
        return False
    fs = fecha_str.strip()
    try:
        # 'YYYY-QN' → fin del trimestre
        if "Q" in fs.upper():
            year, q = fs.upper().split("-Q")
            fin = datetime(int(year), int(q) * 3, 28)  # approx fin de Q
            return fin < now
        if len(fs) == 7:  # 'YYYY-MM'
            dt = datetime.strptime(fs + "-28", "%Y-%m-%d")
            return dt < now
        if len(fs) == 10:  # 'YYYY-MM-DD'
            dt = datetime.strptime(fs, "%Y-%m-%d")
            return dt < now
    except (ValueError, IndexError):
        pass
    return False


# ---------- Serializers ----------

def alertas_to_dict(alertas: list[Alerta]) -> list[dict]:
    return [asdict(a) for a in alertas]


def items_to_dict(items: list[ProcessItem]) -> list[dict]:
    return [asdict(i) for i in items]
