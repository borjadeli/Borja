"""Runner que integra Portfolio + Juez + persistencia.

Flujo end-to-end post-Analista:
1. Portfolio.generar_recomendacion(ticker) — decisión de capital determinista.
2. Juez.validar_recomendacion(rec)         — valida contra reglas del sistema.
3. Persiste en tabla `recomendaciones` con estado=pendiente_aprobacion.
4. El humano aprueba/rechaza vía endpoints (main.py).

El runner se llama automáticamente desde el Analista tras escribir una ficha (doc 02 sec 5.1).
También se puede disparar manualmente con `POST /portfolio/evaluar/{ticker}`.
"""
from __future__ import annotations

from backend.agents import juez as juez_agent
from backend.agents.portfolio import Recomendacion as RecomendacionPortfolio
from backend.agents.portfolio import generar_recomendacion as portfolio_generar
from backend.database import session_scope
from backend.models import EstadoAprobacion, EstadoRecomendacion, Ficha, Recomendacion, Trade
from backend.utils import get_logger, utcnow


# ---------- Trade lifecycle helpers (v4.2) ----------

def _abrir_trade(s, ficha, rec, precio_entrada: float, capital_total: float, now) -> int | None:
    """Crea un Trade(open) cuando se aprueba entrar/bucket. Retorna trade_id."""
    if not precio_entrada or not (rec.sizing_sugerido or 0):
        return None
    sizing_pct = float(rec.sizing_sugerido)
    cap_deployado = round((sizing_pct / 100.0) * (capital_total or 0.0), 2)
    t = Trade(
        ticker=ficha.ticker,
        status="open",
        fecha_apertura=now,
        precio_entrada=precio_entrada,
        sizing_pct_apertura=sizing_pct,
        capital_deployado_usd=cap_deployado,
        rec_id_apertura=rec.id,
        sector_apertura=ficha.sector,
    )
    s.add(t)
    s.flush()
    return t.id


def _cerrar_trade(s, ticker: str, rec, precio_cierre: float | None, motivo: str, now) -> int | None:
    """Cierra el Trade(open) más reciente del ticker. Computa pnl realizado."""
    abierto = (
        s.query(Trade)
        .filter_by(ticker=ticker, status="open")
        .order_by(Trade.id.desc())
        .first()
    )
    if abierto is None:
        return None  # nunca hubo trade abierto (ej. ficha post-restauración manual)
    if precio_cierre is None:
        # último mtm como fallback
        ficha = s.query(Ficha).filter_by(ticker=ticker).first()
        precio_cierre = (
            ficha.precio_mtm if ficha and ficha.precio_mtm
            else ficha.precio_ultima_actualizacion_ficha if ficha
            else abierto.precio_entrada
        )
    if not abierto.precio_entrada or not precio_cierre:
        return None
    valor_cierre = abierto.capital_deployado_usd * (precio_cierre / abierto.precio_entrada)
    pnl_usd = valor_cierre - abierto.capital_deployado_usd
    pnl_pct = (precio_cierre - abierto.precio_entrada) / abierto.precio_entrada * 100.0

    abierto.status = "closed"
    abierto.fecha_cierre = now
    abierto.precio_cierre = float(precio_cierre)
    abierto.valor_cierre_usd = round(valor_cierre, 2)
    abierto.pnl_realizado_usd = round(pnl_usd, 2)
    abierto.pnl_realizado_pct = round(pnl_pct, 2)
    abierto.motivo_cierre = motivo
    abierto.rec_id_cierre = rec.id
    return abierto.id

log = get_logger(__name__)


def ejecutar_recomendacion(ticker: str, task_id: str | None = None) -> dict:
    """Corre Portfolio → Juez → persiste. Devuelve dict resumen.

    Args:
        ticker: símbolo a evaluar.
        task_id: si el llamador es el Analista async, vincularlo con la recomendación generada.
    """
    ticker = ticker.upper()

    # 1. Portfolio
    rec_obj: RecomendacionPortfolio = portfolio_generar(ticker)

    # 2. Juez
    estado_rec, motivo = juez_agent.validar_recomendacion(rec_obj)
    if estado_rec == "CUESTIONADA":
        rec_obj.motivo_cuestionada = motivo

    # 3. Persistir
    with session_scope() as s:
        row = Recomendacion(
            ticker=rec_obj.ticker,
            accion=rec_obj.accion,
            estado_rec=estado_rec,
            motivo_cuestionada=motivo,
            sizing_sugerido=rec_obj.sizing_sugerido,
            capacidad_maxima_teorica=rec_obj.capacidad_maxima_teorica,
            momentum_sectorial_leido=rec_obj.momentum_sectorial_leido,
            asimetria_vigente=rec_obj.asimetria_vigente,
            umbral_rotacion_activo=rec_obj.umbral_rotacion_activo,
            reglas_verificadas=rec_obj.reglas_verificadas,
            checklist_completo=rec_obj.checklist_completo,
            checklist_json=rec_obj.checklist_detalle,
            contexto_macro=rec_obj.contexto_macro,
            nota_bucket=rec_obj.nota_bucket,
            justificacion=rec_obj.justificacion,
            prioridad_capital=rec_obj.prioridad_capital,
            exposicion_pct_al_evaluar=rec_obj.exposicion_pct_al_evaluar,
            estado_aprobacion=EstadoAprobacion.PENDIENTE.value,
            timestamp_juez=utcnow(),
            task_id=task_id,
        )
        s.add(row)
        s.flush()
        rec_id = row.id

    log.info(
        "RECOMENDACION creada — ticker=%s accion=%s estado=%s rec_id=%s",
        ticker, rec_obj.accion, estado_rec, rec_id,
    )

    resultado = {
        "rec_id": rec_id,
        "ticker": ticker,
        "accion": rec_obj.accion,
        "estado_rec": estado_rec,
        "motivo_cuestionada": motivo,
        "sizing_sugerido": rec_obj.sizing_sugerido,
        "asimetria_vigente": rec_obj.asimetria_vigente,
        "checklist_completo": rec_obj.checklist_completo,
        "justificacion": rec_obj.justificacion,
    }

    # Auto-aprobación en modo paper trading (Tier 2 — pre go-live).
    # Solo se aprueban VALIDADAS; CUESTIONADAS siguen requiriendo humano.
    try:
        from backend import panic
        if estado_rec == "VALIDADA" and panic.auto_aprobar_habilitado():
            log.warning("AUTO-APROBANDO rec_id=%s ticker=%s accion=%s (modo paper)",
                       rec_id, ticker, rec_obj.accion)
            aprobacion = aprobar_recomendacion(rec_id)
            resultado["auto_aprobada"] = True
            resultado["aprobacion_result"] = aprobacion
    except Exception as e:  # noqa: BLE001
        log.error("auto_aprobacion fallo: %s", e)

    return resultado


# ---------- Aprobación / rechazo ----------

def aprobar_recomendacion(rec_id: int, precio_entrada: float | None = None) -> dict:
    """Aplica una recomendación aprobada por el humano.

    Para 'entrar' / 'aumentar' / 'piramidacion' / 'bucket':
        - sizing_actual ← sizing_sugerido
        - precio_entrada ← precio_actual al momento de aprobar
        - estado ← Portfolio_Activo (o Bucket_Exploratorio)
        - umbral_rotacion ← umbral_rotacion_activo
        - piramidacion_disponible ← False (se consumió)

    Para 'reducir' / 'salir' / 'rotar':
        - sizing_actual ← 0 (si salir) o reducido
        - estado ← WL_Activa (si salir) o Portfolio_Activo (si reducir)

    Para 'wl_prioritaria':
        - solo cambia estado si aún no está en WL_Prioritaria.

    Para 'mantener':
        - no-op (solo marca la rec como aprobada).
    """
    from backend.agents.portfolio import Accion
    from backend.models import EstadoFicha, Ficha

    with session_scope() as s:
        rec = s.get(Recomendacion, rec_id)
        if rec is None:
            raise ValueError(f"rec_id {rec_id} no existe")
        if rec.estado_aprobacion != EstadoAprobacion.PENDIENTE.value:
            raise ValueError(f"rec_id {rec_id} ya fue {rec.estado_aprobacion}")

        ficha = s.query(Ficha).filter_by(ticker=rec.ticker).first()
        if ficha is None:
            raise ValueError(f"ficha {rec.ticker} no existe")

        estado_anterior = ficha.estado
        now = utcnow()

        # Si no vino precio_entrada explícito, tomar el último snapshot
        if precio_entrada is None:
            from backend.services import market_data
            snap = market_data.get_price_snapshot(rec.ticker)
            precio_entrada = snap.precio_actual if snap else ficha.precio_ultima_actualizacion_ficha

        # Capital total para computar capital_deployado_usd del Trade
        from backend import panic
        capital_total = panic.estado().get("capital_total_usd") or 0.0

        if rec.accion in (Accion.ENTRAR, Accion.AUMENTAR, Accion.PIRAMIDACION):
            ficha.sizing_actual = (ficha.sizing_actual or 0) + (rec.sizing_sugerido or 0) if rec.accion != Accion.ENTRAR else (rec.sizing_sugerido or 0)
            ficha.precio_entrada = precio_entrada
            ficha.umbral_rotacion = rec.umbral_rotacion_activo or 0.5
            ficha.estado = EstadoFicha.PORTFOLIO_ACTIVO.value
            ficha.piramidacion_disponible = False  # se consume hasta próximo deep research
            if rec.accion == Accion.ENTRAR:
                ficha.fecha_entrada_portfolio = now
                # Crear Trade abierto
                _abrir_trade(s, ficha=ficha, rec=rec, precio_entrada=precio_entrada,
                             capital_total=capital_total, now=now)

        elif rec.accion == Accion.BUCKET:
            ficha.sizing_actual = rec.sizing_sugerido
            ficha.precio_entrada = precio_entrada
            ficha.estado = EstadoFicha.BUCKET_EXPLORATORIO.value
            ficha.fecha_entrada_portfolio = now
            _abrir_trade(s, ficha=ficha, rec=rec, precio_entrada=precio_entrada,
                         capital_total=capital_total, now=now)

        elif rec.accion == Accion.REDUCIR:
            ficha.sizing_actual = max(0, (ficha.sizing_actual or 0) - (rec.sizing_sugerido or 0))
            # estado permanece activo

        elif rec.accion in (Accion.SALIR, Accion.ROTAR):
            # Cerrar Trade abierto antes de limpiar la ficha
            _cerrar_trade(s, ticker=rec.ticker, rec=rec, precio_cierre=precio_entrada,
                          motivo=rec.accion, now=now)
            ficha.sizing_actual = 0
            ficha.precio_entrada = None
            ficha.fecha_entrada_portfolio = None
            ficha.estado = EstadoFicha.WL_ACTIVA.value

        elif rec.accion == Accion.WL_PRIORITARIA:
            ficha.estado = EstadoFicha.WL_PRIORITARIA.value

        # MANTENER / CASH_PREVENTIVO: no cambios a la ficha

        # Persistir cambio de estado si aplica
        if ficha.estado != estado_anterior:
            cambios = list(ficha.cambios_estado or [])
            cambios.append({
                "timestamp": now.isoformat(),
                "estado_anterior": estado_anterior,
                "estado_nuevo": ficha.estado,
                "motivo": f"aprobación humana de rec {rec_id} — acción {rec.accion}",
            })
            ficha.cambios_estado = cambios

        rec.estado_aprobacion = EstadoAprobacion.APROBADA.value
        rec.timestamp_human = now

        log.info(
            "REC %s aprobada — ticker=%s accion=%s estado %s→%s",
            rec_id, rec.ticker, rec.accion, estado_anterior, ficha.estado,
        )

        result = {
            "rec_id": rec_id,
            "ticker": rec.ticker,
            "accion": rec.accion,
            "estado_ficha_anterior": estado_anterior,
            "estado_ficha_nuevo": ficha.estado,
            "sizing_actual": ficha.sizing_actual,
            "precio_entrada": ficha.precio_entrada,
        }
        rec_ticker = rec.ticker
        rec_accion = rec.accion
        rec_justificacion = rec.justificacion
        auto_aprobada_flag = "(auto-aprobada modo paper)" if not rec.timestamp_human else ""

    # v4.2 — log al decision journal (fuera de la session anterior).
    from backend.agents.decision_journal import registrar_decision
    registrar_decision(
        accion=rec_accion,
        ticker=rec_ticker,
        decisor="humano",
        motivo=rec_justificacion,
        rec_id=rec_id,
    )
    return result


def rechazar_recomendacion(rec_id: int, motivo: str | None = None) -> dict:
    with session_scope() as s:
        rec = s.get(Recomendacion, rec_id)
        if rec is None:
            raise ValueError(f"rec_id {rec_id} no existe")
        if rec.estado_aprobacion != EstadoAprobacion.PENDIENTE.value:
            raise ValueError(f"rec_id {rec_id} ya fue {rec.estado_aprobacion}")
        rec.estado_aprobacion = EstadoAprobacion.RECHAZADA.value
        rec.timestamp_human = utcnow()
        if motivo:
            rec.motivo_cuestionada = (rec.motivo_cuestionada or "") + f" | rechazo: {motivo}"
        log.info("REC %s rechazada — ticker=%s motivo=%s", rec_id, rec.ticker, motivo)
        rec_ticker = rec.ticker

    # v4.2 — log al decision journal.
    from backend.agents.decision_journal import registrar_decision
    registrar_decision(
        accion="rechazar",
        ticker=rec_ticker,
        decisor="humano",
        motivo=motivo,
        rec_id=rec_id,
    )
    return {"rec_id": rec_id, "estado": EstadoAprobacion.RECHAZADA.value, "motivo": motivo}
