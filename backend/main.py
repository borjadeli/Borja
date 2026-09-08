"""FastAPI app — entrypoint del sistema BORJA.

Sprint 0: skeleton con /health y metadata. Las rutas de agentes se cargan en
sprints siguientes (Analista: Sprint 1, Juez: Sprint 2, etc.).

Uso:
    uvicorn backend.main:app --reload
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from backend.auth import AuthMiddleware
from backend.agents import descubrimiento as descubrimiento_agent
from backend.agents import discovery_hipotesis as discovery_agent
from backend.agents import juez as juez_agent
from backend.agents import mapa_sectorial as mapa_agent
from backend.agents import research as research_agent
from backend.agents.analista_runner import dispatch_analista, get_task
from backend.agents.dispatcher import dispatch_evento, procesar_cola_eventos
from backend.agents.recomendacion_runner import (
    aprobar_recomendacion,
    ejecutar_recomendacion,
    rechazar_recomendacion,
)
from backend.agents.script_nocturno import correr_script_nocturno
from backend.ui import router as ui_router
from backend.config import get_settings
from backend.database import init_db, session_scope
from backend.models import (
    DispatchLog,
    EstadoAprobacion,
    EstadoEvento,
    Evento,
    Ficha,
    LLMCall,
    Macro,
    Recomendacion,
    Sector,
)
from backend import scheduler as scheduler_mod
from backend.services import edgar, llm, market_data, news
from backend.utils import get_logger, utcnow

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    settings = get_settings()
    log.info("BORJA starting — env=%s db=%s model=%s",
             settings.app_env, settings.db_path, settings.anthropic_model)
    init_db()
    if settings.scheduler_autostart:
        try:
            from backend import scheduler as sch
            sch.start()
            log.info("BORJA — scheduler autostart activado")
        except Exception as e:  # noqa: BLE001
            log.error("scheduler autostart fallo: %s", e)
    yield
    log.info("BORJA shutting down")
    try:
        from backend import scheduler as sch
        sch.stop()
    except Exception:
        pass


app = FastAPI(
    title="BORJA Investment System",
    description="Sistema de recomendaciones de inversión — small/mid caps industrias del futuro",
    version="0.5.0",
    lifespan=lifespan,
)

# Auth middleware — solo activa si ADMIN_PASSWORD_HASH está seteado en .env
app.add_middleware(AuthMiddleware)

# Mount static files + UI routes
from pathlib import Path
_static_dir = Path(__file__).resolve().parent.parent / "frontend" / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")
app.include_router(ui_router)

# Consola Claude Code embebida (sidebar → /consola). Ver ops/consola/DEMO.md.
from backend.consola import router as consola_router
app.include_router(consola_router)


@app.get("/api")
def root() -> dict:
    """API JSON root — UI root (/) sirve el Dashboard HTML."""
    return {
        "name": "BORJA Investment System",
        "version": "0.5.0",
        "ui": "/",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health() -> dict:
    """Verifica DB + APIs externas + config."""
    settings = get_settings()
    checks: dict = {
        "timestamp": utcnow().isoformat(),
        "env": settings.app_env,
        "model": settings.anthropic_model,
    }

    # DB
    try:
        with session_scope() as s:
            n_fichas = s.query(Ficha).count()
            macro = s.query(Macro).filter_by(activa=True).first()
            macro_version = macro.version if macro else None
            macro_fase = macro.fase_actual if macro else None
        checks["db"] = {
            "ok": True,
            "fichas": n_fichas,
            "macro_version": macro_version,
            "macro_fase": macro_fase,
        }
    except Exception as e:
        checks["db"] = {"ok": False, "error": str(e)}

    # APIs externas (quick checks, no bloquean)
    checks["apis"] = {
        "yahoo_chart": _safe_ping(market_data.ping),
        "edgar": _safe_ping(edgar.ping),
        "news_rss": _safe_ping(news.ping),
        "anthropic_configured": _safe_ping(llm.ping),
    }

    # Secrets
    checks["smtp_configured"] = bool(settings.smtp_host and settings.smtp_password)
    checks["fase_2_ready"] = settings.fase_2_enabled

    all_ok = (
        checks["db"].get("ok")
        and checks["apis"]["yahoo_chart"]
        and checks["apis"]["edgar"]
        and checks["apis"]["news_rss"]
    )
    checks["status"] = "ok" if all_ok else "degraded"
    return checks


@app.get("/api/universo")
def list_universo() -> dict:
    """Lista de todas las fichas cargadas — endpoint JSON (UI está en /universo)."""
    with session_scope() as s:
        fichas = s.query(Ficha).order_by(Ficha.sector, Ficha.ticker).all()
        rows = [
            {
                "ticker": f.ticker,
                "nombre": f.nombre,
                "sector": f.sector,
                "estado": f.estado,
                "score": f.score_vigente,
                "origen": f.origen,
            }
            for f in fichas
        ]
    return {"total": len(rows), "fichas": rows}


@app.get("/api/sectores")
def list_sectores() -> dict:
    with session_scope() as s:
        secs = s.query(Sector).order_by(Sector.nombre).all()
        rows = [
            {
                "nombre": x.nombre,
                "momentum": x.momentum,
                "prioridad": x.prioridad,
                "horizonte": x.horizonte,
                "ultima_actualizacion": x.ultima_actualizacion.isoformat() if x.ultima_actualizacion else None,
            }
            for x in secs
        ]
    return {"sectores": rows}


@app.get("/macro")
def get_macro_activa() -> dict:
    with session_scope() as s:
        m = s.query(Macro).filter_by(activa=True).first()
        if not m:
            return {"error": "sin tesis macro activa"}
        return {
            "version": m.version,
            "fase_actual": m.fase_actual,
            "postura_capital": m.postura_capital,
            "fecha_actualizacion": m.fecha_actualizacion.isoformat(),
            "notas": m.notas,
        }  # SQLAlchemy permite acceso mientras la sesión esté abierta (context aún vigente)


def _safe_ping(fn) -> bool:
    try:
        return bool(fn())
    except Exception as e:
        log.warning("ping fallo: %s", e)
        return False


# ===================================================================
#  AGENTE ANALISTA — endpoints async
# ===================================================================

@app.post("/analizar/{ticker}")
def analizar_ticker(ticker: str, background_tasks: BackgroundTasks, dry_run: bool = False) -> dict:
    """Dispara el Analista en background. Devuelve task_id para polling.

    Query param opcional dry_run=true: no llama a Anthropic — útil para validar
    que el contexto se arma bien sin gastar tokens.
    """
    ticker_upper = ticker.upper().strip()
    with session_scope() as s:
        ficha = s.query(Ficha).filter_by(ticker=ticker_upper).first()
        if ficha is None:
            raise HTTPException(status_code=404, detail=f"ticker {ticker_upper} no está en fichas — cargar vía intake primero")

    task_id = dispatch_analista(ticker_upper, background_tasks, dry_run=dry_run)
    return {
        "task_id": task_id,
        "ticker": ticker_upper,
        "dry_run": dry_run,
        "poll_url": f"/task/{task_id}",
        "mensaje": "análisis encolado — consultar /task/{task_id} para estado",
    }


@app.get("/task/{task_id}")
def get_task_status(task_id: str) -> dict:
    """Estado de un task async (polling desde la UI)."""
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"task {task_id} no encontrado")
    return task


# ===================================================================
#  AGENTES PORTFOLIO + JUEZ — endpoints de aprobación y monitoreo
# ===================================================================

@app.post("/portfolio/evaluar/{ticker}")
def portfolio_evaluar(ticker: str) -> dict:
    """Corre Portfolio+Juez manualmente sobre una ficha (fuera del pipeline del Analista).

    Útil para reevaluar una posición ante cambio de precio o macro sin correr el Analista.
    """
    ticker_upper = ticker.upper().strip()
    with session_scope() as s:
        ficha = s.query(Ficha).filter_by(ticker=ticker_upper).first()
        if ficha is None:
            raise HTTPException(status_code=404, detail=f"ticker {ticker_upper} no existe")
    return ejecutar_recomendacion(ticker_upper)


@app.get("/recomendaciones")
def list_recomendaciones(estado: str | None = "pendiente_aprobacion", ticker: str | None = None) -> dict:
    """Lista recomendaciones. Por default solo las pendientes."""
    with session_scope() as s:
        q = s.query(Recomendacion)
        if estado:
            q = q.filter(Recomendacion.estado_aprobacion == estado)
        if ticker:
            q = q.filter(Recomendacion.ticker == ticker.upper())
        rows = q.order_by(Recomendacion.timestamp_juez.desc()).limit(100).all()
        result = [
            {
                "rec_id": r.id,
                "ticker": r.ticker,
                "accion": r.accion,
                "estado_rec": r.estado_rec,
                "motivo_cuestionada": r.motivo_cuestionada,
                "sizing_sugerido": r.sizing_sugerido,
                "capacidad_maxima_teorica": r.capacidad_maxima_teorica,
                "asimetria_vigente": r.asimetria_vigente,
                "momentum_sectorial_leido": r.momentum_sectorial_leido,
                "umbral_rotacion_activo": r.umbral_rotacion_activo,
                "reglas_verificadas": r.reglas_verificadas,
                "checklist_completo": r.checklist_completo,
                "checklist_detalle": r.checklist_json,
                "contexto_macro": r.contexto_macro,
                "nota_bucket": r.nota_bucket,
                "justificacion": r.justificacion,
                "estado_aprobacion": r.estado_aprobacion,
                "timestamp_juez": r.timestamp_juez.isoformat() if r.timestamp_juez else None,
                "timestamp_human": r.timestamp_human.isoformat() if r.timestamp_human else None,
            }
            for r in rows
        ]
    return {"total": len(result), "recomendaciones": result}


@app.post("/aprobar/{rec_id}")
def aprobar(rec_id: int, precio_entrada: float | None = None) -> dict:
    """Aprueba una recomendación pendiente. Si es 'entrar'/'aumentar', aplica sizing y precio."""
    try:
        return aprobar_recomendacion(rec_id, precio_entrada=precio_entrada)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/rechazar/{rec_id}")
def rechazar(rec_id: int, motivo: str | None = None) -> dict:
    try:
        return rechazar_recomendacion(rec_id, motivo=motivo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# v4.2 Enmienda C — Override manual de insider selling como red flag.

VALID_INSIDER_OVERRIDES = {"10b5-1", "founder_50", "diversificacion_programada"}


@app.post("/api/fichas/{ticker}/insider-override")
def set_insider_override(ticker: str, motivos: list[str], evidencia: str = "") -> dict:
    """Marca overrides documentados que evitan que insider selling active red flag.

    motivos válidos: '10b5-1', 'founder_50', 'diversificacion_programada'.
    evidencia: descripción de la documentación que justifica el override.
    """
    motivos_invalidos = [m for m in motivos if m not in VALID_INSIDER_OVERRIDES]
    if motivos_invalidos:
        raise HTTPException(
            status_code=400,
            detail=f"motivos inválidos: {motivos_invalidos}. Válidos: {sorted(VALID_INSIDER_OVERRIDES)}",
        )
    from backend.database import session_scope
    from backend.models import Ficha
    with session_scope() as s:
        f = s.query(Ficha).filter_by(ticker=ticker.upper()).first()
        if f is None:
            raise HTTPException(status_code=404, detail=f"ficha {ticker} no existe")
        f.insider_selling_overrides_json = list(motivos)
        f.insider_selling_overrides_evidencia = evidencia
    return {
        "ticker": ticker.upper(),
        "overrides": list(motivos),
        "evidencia": evidencia,
    }


@app.delete("/api/fichas/{ticker}/insider-override")
def clear_insider_override(ticker: str) -> dict:
    from backend.database import session_scope
    from backend.models import Ficha
    with session_scope() as s:
        f = s.query(Ficha).filter_by(ticker=ticker.upper()).first()
        if f is None:
            raise HTTPException(status_code=404, detail=f"ficha {ticker} no existe")
        f.insider_selling_overrides_json = None
        f.insider_selling_overrides_evidencia = None
    return {"ticker": ticker.upper(), "overrides": []}


# ===================================================================
#  v4.2 Sprint D — Bucket mecánico (peer groups + precio base + ficha contractual)
# ===================================================================

VALID_PEER_TIPOS = {"emerging", "anchor"}


@app.get("/api/peer-groups/{ticker}")
def get_peer_groups(ticker: str) -> dict:
    """Devuelve los peer groups (emerging y anchor) registrados para un ticker."""
    from backend.database import session_scope
    from backend.models import PeerGroup
    with session_scope() as s:
        groups = s.query(PeerGroup).filter_by(ticker_target=ticker.upper()).all()
        return {
            "ticker": ticker.upper(),
            "groups": [
                {
                    "tipo": g.tipo,
                    "peers": g.peers_json,
                    "notas": g.notas,
                    "fecha_actualizacion": g.fecha_actualizacion.isoformat() if g.fecha_actualizacion else None,
                }
                for g in groups
            ],
        }


@app.post("/api/peer-groups/{ticker}")
def set_peer_group(ticker: str, tipo: str, peers: list[str], notas: str = "") -> dict:
    """Crea o actualiza un peer group (emerging o anchor) para un ticker."""
    if tipo not in VALID_PEER_TIPOS:
        raise HTTPException(
            status_code=400,
            detail=f"tipo inválido: {tipo}. Válidos: {sorted(VALID_PEER_TIPOS)}",
        )
    if not peers:
        raise HTTPException(status_code=400, detail="lista de peers vacía")
    if tipo == "emerging" and len(peers) > 10:
        raise HTTPException(status_code=400, detail="emerging admite hasta 10 peers")
    if tipo == "anchor" and len(peers) > 2:
        raise HTTPException(status_code=400, detail="anchor admite hasta 2 peers")

    from backend.database import session_scope
    from backend.models import PeerGroup
    peers_clean = [p.strip().upper() for p in peers if p.strip()]
    target = ticker.upper()
    with session_scope() as s:
        existente = s.query(PeerGroup).filter_by(ticker_target=target, tipo=tipo).first()
        if existente:
            existente.peers_json = peers_clean
            existente.notas = notas or None
        else:
            s.add(PeerGroup(
                ticker_target=target,
                tipo=tipo,
                peers_json=peers_clean,
                notas=notas or None,
            ))
    return {"ticker": target, "tipo": tipo, "peers": peers_clean}


@app.get("/api/precio-base/{ticker}")
def precio_base_endpoint(
    ticker: str,
    revenue_recurrente: float | None = None,
    bull_case_precio: float | None = None,
) -> dict:
    """Calcula precio base sin contratos para un ticker usando sus peer groups.

    Si no se pasa revenue_recurrente/bull_case_precio, los toma de la ficha:
    revenue_ttm de EDGAR y bull_case_precio de la ficha del Analista.
    """
    from backend.database import session_scope
    from backend.models import Ficha, PeerGroup
    from backend.services.precio_base import calculate_precio_base

    target = ticker.upper()
    with session_scope() as s:
        f = s.query(Ficha).filter_by(ticker=target).first()
        if f is None:
            raise HTTPException(status_code=404, detail=f"ficha {ticker} no existe")
        if bull_case_precio is None:
            bull_case_precio = f.bull_case_precio
        groups = s.query(PeerGroup).filter_by(ticker_target=target).all()
        emerging = next((g for g in groups if g.tipo == "emerging"), None)
        anchor = next((g for g in groups if g.tipo == "anchor"), None)

    if emerging is None or not emerging.peers_json:
        raise HTTPException(
            status_code=400,
            detail=f"sin emerging peers para {target}. Cargar via POST /api/peer-groups/{{ticker}}.",
        )

    res = calculate_precio_base(
        ticker=target,
        revenue_recurrente_target=revenue_recurrente,
        bull_case_precio=bull_case_precio,
        emerging_peers=emerging.peers_json,
        anchor_peers=anchor.peers_json if anchor else None,
    )
    return {
        "ticker": res.ticker,
        "current_fd_equity_value_usd": res.current_fd_equity_value_usd,
        "base_equity_value_usd": res.base_equity_value_usd,
        "base_precio": res.base_precio,
        "banda_p25_precio": res.banda_p25_precio,
        "banda_p75_precio": res.banda_p75_precio,
        "reference_anchor_precio": res.reference_anchor_precio,
        "implied_future_value_usd": res.implied_future_value_usd,
        "pct_bull_case_priceado": res.pct_bull_case_priceado,
        "confidence": res.confidence,
        "cv_emerging": res.cv_emerging,
        "n_emerging_peers": res.n_emerging_peers,
        "n_anchor_peers": res.n_anchor_peers,
        "notas": res.notas,
    }


@app.get("/api/fichas-contractuales/{ticker}")
def get_ficha_contractual(ticker: str) -> dict:
    from backend.database import session_scope
    from backend.models import FichaContractual
    with session_scope() as s:
        rows = (
            s.query(FichaContractual)
            .filter_by(ticker=ticker.upper())
            .order_by(FichaContractual.id.desc())
            .all()
        )
        return {
            "ticker": ticker.upper(),
            "items": [_ficha_contractual_to_dict(fc) for fc in rows],
        }


def _ficha_contractual_to_dict(fc) -> dict:
    return {
        "id": fc.id,
        "cliente": fc.cliente,
        "tipo_instrumento": fc.tipo_instrumento,
        "monto_divulgado_usd": fc.monto_divulgado_usd,
        "fecha_inicio_entregas": fc.fecha_inicio_entregas,
        "fuente_url": fc.fuente_url,
        "lenguaje_literal_management": fc.lenguaje_literal_management,
        "condiciones_pendientes": fc.condiciones_pendientes,
        "derechos_cancelacion": fc.derechos_cancelacion,
        "dependencias_tecnicas": fc.dependencias_tecnicas,
        "capex_pre_revenue": fc.capex_pre_revenue,
        "lenguaje_riesgo_10k": fc.lenguaje_riesgo_10k,
        "binding_o_condicionado": fc.binding_o_condicionado,
        "aprobada_por_humano": fc.aprobada_por_humano,
        "fecha_aprobacion": fc.fecha_aprobacion.isoformat() if fc.fecha_aprobacion else None,
        "notas_revisor": fc.notas_revisor,
        "created_at": fc.created_at.isoformat() if fc.created_at else None,
        "updated_at": fc.updated_at.isoformat() if fc.updated_at else None,
    }


@app.post("/api/fichas-contractuales/{ticker}")
def create_ficha_contractual(ticker: str, payload: dict) -> dict:
    """Crea una ficha contractual estructurada para un ticker.

    payload acepta los campos positivos y negativos. Los campos negativos son
    obligatorios (al menos string vacío explícito) — si faltan se rechaza con 400.
    """
    REQUERIDOS_NEGATIVOS = (
        "condiciones_pendientes",
        "derechos_cancelacion",
        "dependencias_tecnicas",
        "capex_pre_revenue",
        "lenguaje_riesgo_10k",
        "binding_o_condicionado",
    )
    faltantes = [k for k in REQUERIDOS_NEGATIVOS if k not in payload]
    if faltantes:
        raise HTTPException(
            status_code=400,
            detail=f"campos negativos obligatorios faltantes: {faltantes}",
        )
    if payload.get("binding_o_condicionado") not in ("binding", "condicionado", None):
        raise HTTPException(
            status_code=400,
            detail="binding_o_condicionado debe ser 'binding' o 'condicionado'",
        )

    from backend.database import session_scope
    from backend.models import Ficha, FichaContractual
    target = ticker.upper()
    with session_scope() as s:
        f = s.query(Ficha).filter_by(ticker=target).first()
        if f is None:
            raise HTTPException(status_code=404, detail=f"ficha {ticker} no existe")
        fc = FichaContractual(
            ticker=target,
            cliente=payload.get("cliente"),
            tipo_instrumento=payload.get("tipo_instrumento"),
            monto_divulgado_usd=payload.get("monto_divulgado_usd"),
            fecha_inicio_entregas=payload.get("fecha_inicio_entregas"),
            fuente_url=payload.get("fuente_url"),
            lenguaje_literal_management=payload.get("lenguaje_literal_management"),
            condiciones_pendientes=payload.get("condiciones_pendientes"),
            derechos_cancelacion=payload.get("derechos_cancelacion"),
            dependencias_tecnicas=payload.get("dependencias_tecnicas"),
            capex_pre_revenue=payload.get("capex_pre_revenue"),
            lenguaje_riesgo_10k=payload.get("lenguaje_riesgo_10k"),
            binding_o_condicionado=payload.get("binding_o_condicionado"),
            notas_revisor=payload.get("notas_revisor"),
        )
        s.add(fc)
        s.flush()
        fc_id = fc.id
        result = _ficha_contractual_to_dict(fc)
    return result


# --- Revalidación 30d (v4.2 sec 5) ---

@app.get("/api/revalidaciones")
def list_revalidaciones(estado: str | None = None, ticker: str | None = None) -> dict:
    from backend.database import session_scope
    from backend.models import Revalidacion
    with session_scope() as s:
        q = s.query(Revalidacion)
        if estado:
            q = q.filter_by(estado=estado)
        if ticker:
            q = q.filter_by(ticker=ticker.upper())
        rows = q.order_by(Revalidacion.id.desc()).limit(100).all()
        return {
            "items": [
                {
                    "id": r.id,
                    "ticker": r.ticker,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                    "estado": r.estado,
                    "fecha_respuesta": r.fecha_respuesta.isoformat() if r.fecha_respuesta else None,
                    "p1_que_aprendi": r.p1_que_aprendi,
                    "p2_supuesto_cambio": r.p2_supuesto_cambio,
                    "p3_deterioro_o_precio": r.p3_deterioro_o_precio,
                    "p4_red_team_anticipo": r.p4_red_team_anticipo,
                    "p5_trigger_faltante": r.p5_trigger_faltante,
                    "accion_decidida": r.accion_decidida,
                }
                for r in rows
            ],
        }


@app.post("/api/revalidaciones/{ticker}/responder")
def responder_revalidacion_endpoint(
    ticker: str,
    sigue_creyendo: bool,
    payload: dict | None = None,
) -> dict:
    """payload (si sigue_creyendo=False): {p1_que_aprendi, p2_supuesto_cambio,
    p3_deterioro_o_precio, p4_red_team_anticipo, p5_trigger_faltante, accion_decidida}
    """
    from backend.agents.revalidacion import responder_revalidacion
    payload = payload or {}
    accion_decidida = payload.pop("accion_decidida", None) if isinstance(payload, dict) else None
    try:
        return responder_revalidacion(
            ticker=ticker,
            sigue_creyendo=sigue_creyendo,
            respuestas=payload if not sigue_creyendo else None,
            accion_decidida=accion_decidida,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/revalidaciones/run")
def revalidaciones_run() -> dict:
    """Trigger manual del job (normalmente corre 7:30 ET diario)."""
    from backend.agents.revalidacion import detectar_revalidaciones_pendientes
    return detectar_revalidaciones_pendientes()


# --- Protocolo Transición Fase Macro (v4.2 sec 5) ---

@app.post("/api/macro/fase-2-activar")
def macro_fase_2_activar(motivo: str = "humano declara Fase 2 activada") -> dict:
    """Trigger humano de Transición Fase Macro. Reduce sizing 50% en posiciones
    que no pasen checklist + suspende bucket. NO ejecuta ventas automáticas.
    """
    from backend.agents.transicion_fase_macro import activar_fase_2
    return activar_fase_2(motivo=motivo)


# --- Admin: restart del servicio ---

@app.post("/admin/restart")
def admin_restart() -> dict:
    """Reinicia el proceso. Funciona porque systemd tiene Restart=always.

    Side effect: registra la decisión en decision_journal y luego os._exit(0)
    con delay de 0.5s para que el response llegue al cliente antes.
    """
    import os
    import threading

    from backend.agents.decision_journal import registrar_decision

    registrar_decision(
        accion="admin_restart",
        decisor="humano",
        motivo="reinicio manual desde dashboard",
        metadata={"pid": os.getpid()},
    )
    log.warning("ADMIN — reinicio solicitado desde UI (PID %s) — saliendo en 0.5s", os.getpid())

    def _exit_delayed():
        import time
        time.sleep(0.5)
        # Exit code 1 (no 0) para que systemd con Restart=on-failure SÍ reinicie.
        # Con Restart=always (configurado en ops/borja.service nuevo) cualquier
        # exit code reinicia, pero acá usamos 1 para compatibilidad con la
        # config actual de producción que aún tiene Restart=on-failure.
        os._exit(1)

    threading.Thread(target=_exit_delayed, daemon=True).start()
    return {
        "ok": True,
        "mensaje": "Reinicio iniciado. systemd lo levantará en ~5s (Restart=on-failure).",
        "pid_anterior": os.getpid(),
    }


# Borrar la línea log = get_logger duplicada de arriba — ya existe a nivel módulo


# --- Evaluate UI: batch_analista on-demand ---

@app.post("/api/evaluate/dry-run")
def evaluate_dry_run(payload: dict) -> dict:
    """Estima cuántos tickers + costo sin gastar API."""
    import argparse
    from ops.batch_analista import COSTO_PROMEDIO_USD, construir_lista_tickers

    args = argparse.Namespace(
        tickers=payload.get("tickers", "") or "",
        estado=payload.get("estados") or [],
        sector=payload.get("sectores") or [],
        score_min=payload.get("score_min"),
        score_max=payload.get("score_max"),
        excluir_evaluados_hace=int(payload.get("excluir_evaluados_hace") or 0),
        sector_default_nuevo="(sin asignar)",
        solo_estimar_costo=True,
        max_tickers=payload.get("max_tickers"),
        output_dir="data/batches",
    )
    tickers = construir_lista_tickers(args, crear_fichas=False)
    return {
        "tickers_count": len(tickers),
        "tickers": tickers,
        "costo_estimado_usd": round(len(tickers) * COSTO_PROMEDIO_USD, 2),
        "tiempo_estimado_min": round(len(tickers) * 70 / 60, 1),
    }


@app.post("/api/evaluate/start")
def evaluate_start(payload: dict, background_tasks: BackgroundTasks) -> dict:
    """Lanza el batch en background y crea una Task con estado=en_progreso."""
    import argparse
    import secrets
    import threading
    from ops.batch_analista import construir_lista_tickers, correr_uno
    from backend.database import session_scope
    from backend.models import EstadoTask, Task

    args = argparse.Namespace(
        tickers=payload.get("tickers", "") or "",
        estado=payload.get("estados") or [],
        sector=payload.get("sectores") or [],
        score_min=payload.get("score_min"),
        score_max=payload.get("score_max"),
        excluir_evaluados_hace=int(payload.get("excluir_evaluados_hace") or 0),
        sector_default_nuevo="(sin asignar)",
        solo_estimar_costo=False,
        max_tickers=payload.get("max_tickers"),
        output_dir="data/batches",
    )
    tickers = construir_lista_tickers(args, crear_fichas=True)
    if not tickers:
        raise HTTPException(status_code=400, detail="ningún ticker seleccionado con esos filtros")

    task_id = f"eval-{secrets.token_hex(6)}"
    with session_scope() as s:
        s.add(Task(
            id=task_id,
            tipo="evaluate_batch",
            ticker_o_sector=f"{len(tickers)} tickers",
            estado=EstadoTask.EN_PROGRESO.value,
            progreso=f"0/{len(tickers)}",
            resultado_json={"tickers_total": tickers, "completados": [], "candidatos": []},
        ))

    def _run():
        from backend.utils import utcnow
        completados: list[dict] = []
        candidatos: list[dict] = []
        for i, t in enumerate(tickers, 1):
            r = correr_uno(t)
            completados.append(r)
            # Marcar candidato si pasa el filtro Portfolio
            if r.get("ok") and (r.get("score_nuevo") or 0) >= 6.0 and not r.get("centrales_baja"):
                candidatos.append({
                    "ticker": r["ticker"],
                    "score": r["score_nuevo"],
                    "asimetria": r.get("asimetria"),
                    "rec": r.get("accion_rec"),
                })
            with session_scope() as s:
                tk = s.query(Task).filter_by(id=task_id).first()
                if tk:
                    tk.progreso = f"{i}/{len(tickers)}"
                    tk.resultado_json = {
                        "tickers_total": tickers,
                        "completados": completados,
                        "candidatos": candidatos,
                    }
        with session_scope() as s:
            tk = s.query(Task).filter_by(id=task_id).first()
            if tk:
                tk.estado = EstadoTask.COMPLETADO.value
                tk.finished_at = utcnow()

    threading.Thread(target=_run, daemon=True).start()
    return {
        "task_id": task_id,
        "tickers_count": len(tickers),
        "estado": "en_progreso",
    }


@app.get("/api/evaluate/{task_id}/status")
def evaluate_status(task_id: str) -> dict:
    from backend.database import session_scope
    from backend.models import Task
    with session_scope() as s:
        tk = s.query(Task).filter_by(id=task_id).first()
        if tk is None:
            raise HTTPException(status_code=404, detail=f"task {task_id} no existe")
        return {
            "task_id": tk.id,
            "estado": tk.estado,
            "progreso": tk.progreso,
            "tipo": tk.tipo,
            "resultado": tk.resultado_json,
            "created_at": tk.created_at.isoformat() if tk.created_at else None,
            "finished_at": tk.finished_at.isoformat() if tk.finished_at else None,
        }


# --- Equity curve vs SPY (benchmark) ---

@app.get("/api/equity-curve-vs-spy")
def get_equity_curve_vs_spy(desde: str | None = None) -> dict:
    """Curva diaria BORJA vs SPY normalizado al capital base.

    Args:
        desde: opcional 'YYYY-MM-DD'. Si None, toma todo el histórico disponible.
    """
    from backend.agents.equity_curve import equity_curve_vs_spy
    return equity_curve_vs_spy(fecha_desde=desde)


@app.post("/api/equity-curve/backfill")
def post_equity_curve_backfill() -> dict:
    """Trigger manual del backfill (recomputa snapshots desde primer trade)."""
    from backend.agents.equity_curve import backfill_equity_historico
    return backfill_equity_historico()


# --- Trades (P&L realizado vs abierto) ---

@app.get("/api/trades")
def list_trades(status: str | None = None, ticker: str | None = None, limit: int = 100) -> dict:
    """Lista trades con su P&L realizado (closed) o abierto (open)."""
    from backend.database import session_scope
    from backend.models import Trade
    with session_scope() as s:
        q = s.query(Trade)
        if status:
            q = q.filter_by(status=status)
        if ticker:
            q = q.filter_by(ticker=ticker.upper())
        rows = q.order_by(Trade.id.desc()).limit(limit).all()

        # Resumen
        total_realizado = sum((t.pnl_realizado_usd or 0) for t in rows if t.status == "closed")

        return {
            "total": len(rows),
            "pnl_realizado_total_usd": round(total_realizado, 2),
            "items": [
                {
                    "id": t.id,
                    "ticker": t.ticker,
                    "status": t.status,
                    "sector_apertura": t.sector_apertura,
                    "fecha_apertura": t.fecha_apertura.isoformat() if t.fecha_apertura else None,
                    "precio_entrada": t.precio_entrada,
                    "sizing_pct_apertura": t.sizing_pct_apertura,
                    "capital_deployado_usd": t.capital_deployado_usd,
                    "fecha_cierre": t.fecha_cierre.isoformat() if t.fecha_cierre else None,
                    "precio_cierre": t.precio_cierre,
                    "valor_cierre_usd": t.valor_cierre_usd,
                    "pnl_realizado_usd": t.pnl_realizado_usd,
                    "pnl_realizado_pct": t.pnl_realizado_pct,
                    "motivo_cierre": t.motivo_cierre,
                    "rec_id_apertura": t.rec_id_apertura,
                    "rec_id_cierre": t.rec_id_cierre,
                }
                for t in rows
            ],
        }


# --- Decision Journal (v4.2 sec 8 + 10) ---

@app.get("/api/decision-journal")
def list_decision_journal(
    ticker: str | None = None,
    accion: str | None = None,
    desde: str | None = None,
    limit: int = 100,
) -> dict:
    from backend.agents.decision_journal import listar_decisiones
    items = listar_decisiones(ticker=ticker, accion=accion, desde=desde, limit=limit)
    return {"total": len(items), "items": items}


@app.post("/api/decision-journal/{decision_id}/resultado")
def anotar_resultado_decision(decision_id: int, resultado: str) -> dict:
    from backend.agents.decision_journal import anotar_resultado
    try:
        return anotar_resultado(decision_id, resultado)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/fichas-contractuales/{fc_id}/aprobar")
def aprobar_ficha_contractual(fc_id: int, notas_revisor: str = "") -> dict:
    from backend.database import session_scope
    from backend.models import FichaContractual
    from backend.utils import utcnow
    with session_scope() as s:
        fc = s.query(FichaContractual).filter_by(id=fc_id).first()
        if fc is None:
            raise HTTPException(status_code=404, detail=f"ficha contractual {fc_id} no existe")
        fc.aprobada_por_humano = True
        fc.fecha_aprobacion = utcnow()
        if notas_revisor:
            fc.notas_revisor = notas_revisor
        return _ficha_contractual_to_dict(fc)


# ===================================================================
#  RESEARCH + DISPATCHER + SCHEDULER + NOCTURNO  (Sprint 3)
# ===================================================================

@app.get("/api/eventos")
def list_eventos(
    estado: str | None = None,
    tipo: str | None = None,
    ticker: str | None = None,
    limit: int = 100,
) -> dict:
    with session_scope() as s:
        q = s.query(Evento)
        if estado:
            q = q.filter(Evento.estado == estado)
        if tipo:
            q = q.filter(Evento.tipo == tipo)
        if ticker:
            q = q.filter(Evento.ticker == ticker.upper())
        rows = q.order_by(Evento.timestamp.desc()).limit(limit).all()
        result = [
            {
                "id": e.id,
                "ticker": e.ticker,
                "tipo": e.tipo,
                "descripcion": e.descripcion,
                "fuente": e.fuente,
                "tier": e.tier,
                "estado": e.estado,
                "cooldown_hasta": e.cooldown_hasta.isoformat() if e.cooldown_hasta else None,
                "timestamp": e.timestamp.isoformat(),
                "metadata": e.metadata_json,
            }
            for e in rows
        ]
    return {"total": len(result), "eventos": result}


@app.post("/eventos/{evento_id}/descartar")
def descartar_evento(evento_id: int, motivo: str | None = None) -> dict:
    with session_scope() as s:
        ev = s.get(Evento, evento_id)
        if ev is None:
            raise HTTPException(status_code=404, detail=f"evento {evento_id} no existe")
        if ev.estado != EstadoEvento.PENDIENTE.value:
            raise HTTPException(status_code=400, detail=f"evento ya está {ev.estado}")
        ev.estado = EstadoEvento.DESCARTADO.value
        if motivo:
            meta = dict(ev.metadata_json or {})
            meta["descarte_motivo"] = motivo
            meta["descarte_timestamp"] = utcnow().isoformat()
            ev.metadata_json = meta
        return {"evento_id": evento_id, "estado": ev.estado, "motivo": motivo}


@app.get("/dispatch_log")
def list_dispatch_log(
    ticker: str | None = None,
    destino: str | None = None,
    limit: int = 100,
) -> dict:
    with session_scope() as s:
        q = s.query(DispatchLog)
        if ticker:
            q = q.filter(DispatchLog.ticker_o_sector == ticker.upper())
        if destino:
            q = q.filter(DispatchLog.destino == destino)
        rows = q.order_by(DispatchLog.timestamp.desc()).limit(limit).all()
        result = [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat(),
                "ticker": r.ticker_o_sector,
                "tipo_evento": r.tipo_evento,
                "tier": r.tier_fuente,
                "regla_activada": r.regla_activada,
                "destino": r.destino,
                "urgencia": r.urgencia,
                "motivo": r.motivo,
                "cooldown_activo": r.cooldown_activo,
                "evento_id": r.evento_id,
            }
            for r in rows
        ]
    return {"total": len(result), "dispatch_log": result}


@app.post("/dispatcher/process-queue")
def dispatcher_process_queue() -> dict:
    """Procesa todos los eventos pendientes aplicando reglas de routing."""
    return procesar_cola_eventos()


@app.post("/dispatcher/evento/{evento_id}")
def dispatcher_evento(evento_id: int) -> dict:
    """Dispatcha un evento específico manualmente."""
    try:
        d = dispatch_evento(evento_id)
        from dataclasses import asdict
        return asdict(d)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/research/run-manual")
def research_run_manual() -> dict:
    """Ejecuta los 4 monitores del Research sin esperar al cron."""
    return research_agent.correr_todos_monitores()


@app.post("/research/{monitor}")
def research_monitor_individual(monitor: str) -> dict:
    """Ejecuta un monitor individual: precios / earnings / form4 / noticias."""
    mapping = {
        "precios": research_agent.monitor_precios,
        "earnings": research_agent.monitor_earnings,
        "form4": research_agent.monitor_form4,
        "noticias": research_agent.monitor_noticias,
    }
    fn = mapping.get(monitor)
    if fn is None:
        raise HTTPException(status_code=400, detail=f"monitor '{monitor}' inválido. Válidos: {list(mapping)}")
    return fn()


@app.post("/nocturno/run")
def nocturno_run() -> dict:
    """Ejecuta el script nocturno manualmente (sin esperar 6:00 AM ET)."""
    return correr_script_nocturno()


@app.get("/scheduler/status")
def scheduler_status_endpoint() -> dict:
    return scheduler_mod.status()


@app.post("/scheduler/start")
def scheduler_start_endpoint() -> dict:
    return scheduler_mod.start()


@app.post("/scheduler/stop")
def scheduler_stop_endpoint() -> dict:
    return scheduler_mod.stop()


@app.post("/evaluador/correr")
def evaluador_correr() -> dict:
    """Dispara manualmente el evaluador diario (Portfolio + WL_Prioritaria).

    Determinista, sin LLM. Útil para forzar re-evaluación con precios frescos
    fuera del horario automático (16:15 ET L-V).
    """
    from backend.agents.evaluador_automatico import correr_evaluacion_diaria
    return correr_evaluacion_diaria()


@app.post("/reporte/generar")
def reporte_generar(enviar_email: bool = True) -> dict:
    """Genera el reporte semanal del Juez manualmente."""
    from backend.agents.reporte_semanal import generar_reporte
    r = generar_reporte(enviar_email=enviar_email)
    # No devolvemos el HTML completo en el JSON para mantenerlo liviano
    return {k: v for k, v in r.items() if k != "html"}


# ===================================================================
#  BACKTESTING  (Sprint 7 — gate go-live)
# ===================================================================

@app.post("/backtest/run")
def backtest_run(mock: bool = True, tickers: str | None = None) -> dict:
    """Corre el backtest. Por default mock (gratis); mock=false cuesta ~$3.50."""
    from dataclasses import asdict
    from backend.backtesting.runner import run_backtest

    tickers_list = [t.strip() for t in tickers.split(",")] if tickers else None
    report = run_backtest(mock=mock, tickers_filter=tickers_list, persistir=True)
    data = asdict(report)
    data["resultados"] = [asdict(r) for r in report.resultados]
    return data


@app.get("/api/backtest/latest")
def backtest_latest(mock: bool | None = None) -> dict:
    """Último reporte persistido. mock=None prefiere real."""
    from backend.backtesting.runner import load_latest_report
    r = load_latest_report(mock=mock)
    if r is None:
        raise HTTPException(status_code=404, detail="sin backtests previos")
    return r


# ===================================================================
#  KILL SWITCH GLOBAL  (Tier 1 hardening)
# ===================================================================

@app.get("/api/panic/estado")
def panic_estado() -> dict:
    from backend import panic
    return panic.estado()


@app.post("/api/config/capital")
def set_capital_endpoint(capital_usd: float, modo_paper: bool = True) -> dict:
    """Setea capital de referencia para paper trading. Default modo_paper=True."""
    from backend import panic
    return panic.set_capital(capital_usd, modo_paper=modo_paper)


@app.post("/api/config/auto-aprobar")
def set_auto_aprobar_endpoint(activo: bool) -> dict:
    """Toggle auto-aprobación (solo válido en modo_paper_trading)."""
    from backend import panic
    return panic.set_auto_aprobar(activo)


@app.get("/api/config")
def get_config_endpoint() -> dict:
    """Estado completo de la config del sistema (panic + capital + paper mode)."""
    from backend import panic
    return panic.estado()


@app.post("/panic/pausar")
def panic_pausar(motivo: str = "manual") -> dict:
    """Pausa el sistema: detiene scheduler + marca recomendaciones pendientes."""
    from backend import panic
    return panic.pausar(motivo=motivo, by="admin")


@app.post("/panic/reanudar")
def panic_reanudar() -> dict:
    """Reanuda el sistema: arranca scheduler."""
    from backend import panic
    return panic.reanudar(by="admin")


@app.post("/backup/run")
def backup_run() -> dict:
    """Corre backup de SQLite manualmente (fuera del cron diario)."""
    from backend.ops.backup import correr_backup
    return correr_backup()


@app.get("/api/backups")
def backups_list() -> dict:
    from backend.ops.backup import listar_backups
    return {"backups": listar_backups()}


# ===================================================================
#  MAPA SECTORIAL + DISCOVERY + DESCUBRIMIENTO  (Sprint 4)
# ===================================================================

@app.get("/sectores/{nombre}/mapa")
def get_mapa_sector(nombre: str) -> dict:
    m = mapa_agent.get_mapa_activo(nombre)
    if m is None:
        raise HTTPException(status_code=404, detail=f"sin mapa activo para '{nombre}'")
    return m


@app.post("/sectores/{nombre}/regenerar-mapa")
def regenerar_mapa(nombre: str, dry_run: bool = False, max_searches: int = 5) -> dict:
    try:
        return mapa_agent.generar_mapa_sectorial(nombre, dry_run=dry_run, max_searches=max_searches)
    except mapa_agent.MapaSectorialError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/sectores/{nombre}/aprobar-mapa")
def aprobar_mapa_endpoint(nombre: str) -> dict:
    try:
        return mapa_agent.aprobar_mapa(nombre)
    except mapa_agent.MapaSectorialError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.patch("/sectores/{nombre}/criticidad")
def ajustar_criticidad_endpoint(nombre: str, componente: str, nivel: str | None = None) -> dict:
    try:
        return mapa_agent.ajustar_criticidad(nombre, componente, nivel)
    except mapa_agent.MapaSectorialError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/discovery")
def list_discovery_endpoint(limit: int = 20) -> dict:
    return {"total": len(discovery_agent.list_discovery(limit)), "sessions": discovery_agent.list_discovery(limit)}


@app.get("/discovery/{semana}")
def get_discovery_endpoint(semana: str) -> dict:
    d = discovery_agent.get_discovery_semana(semana)
    if d is None:
        raise HTTPException(status_code=404, detail=f"semana '{semana}' no encontrada")
    return d


@app.post("/discovery/run")
def run_discovery(dry_run: bool = False, max_searches: int = 5) -> dict:
    try:
        return discovery_agent.generar_hipotesis_semanales(dry_run=dry_run, max_searches=max_searches)
    except discovery_agent.DiscoveryError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.patch("/discovery/{semana}/feedback")
def feedback_discovery(semana: str, util: bool | None = None, feedback: str | None = None) -> dict:
    try:
        return discovery_agent.set_feedback(semana, util=util, feedback=feedback)
    except discovery_agent.DiscoveryError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/descubrimiento/screener")
def run_screener(tickers: list[str] | None = None) -> dict:
    """Corre el screener cuantitativo. Si tickers=None, usa watchlist YAML."""
    return descubrimiento_agent.correr_screener(tickers)


@app.post("/descubrimiento/crear-candidatas")
def crear_candidatas(tickers: list[str], sector: str = "AI infra", driver_macro: str | None = None) -> dict:
    """Crea fichas Candidata a partir de una lista de tickers (tras pasar screener)."""
    return descubrimiento_agent.crear_candidatas(tickers, sector_default=sector,
                                                  driver_macro_default=driver_macro)


# ===================================================================
#  COST TRACKING LLM  (Sprint 6)
# ===================================================================

@app.get("/api/costos")
def api_costos(dias: int = 30) -> dict:
    """Resumen de costo LLM de los últimos N días."""
    from datetime import timedelta
    from sqlalchemy import func

    now = utcnow()
    cutoff = now - timedelta(days=dias)
    inicio_mes = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    with session_scope() as s:
        total = s.query(func.coalesce(func.sum(LLMCall.cost_usd), 0.0)).filter(
            LLMCall.timestamp >= cutoff
        ).scalar() or 0.0

        mes_actual = s.query(func.coalesce(func.sum(LLMCall.cost_usd), 0.0)).filter(
            LLMCall.timestamp >= inicio_mes
        ).scalar() or 0.0

        por_agente = s.query(
            LLMCall.agent,
            func.count(LLMCall.id),
            func.coalesce(func.sum(LLMCall.cost_usd), 0.0),
            func.coalesce(func.sum(LLMCall.tokens_input), 0),
            func.coalesce(func.sum(LLMCall.tokens_output), 0),
            func.coalesce(func.sum(LLMCall.tokens_cache_read), 0),
            func.coalesce(func.sum(LLMCall.web_searches), 0),
        ).filter(LLMCall.timestamp >= cutoff).group_by(LLMCall.agent).all()

        recientes = (
            s.query(LLMCall)
            .filter(LLMCall.timestamp >= cutoff)
            .order_by(LLMCall.timestamp.desc())
            .limit(30)
            .all()
        )
        recientes_data = [
            {
                "id": l.id,
                "timestamp": l.timestamp.isoformat(),
                "agent": l.agent,
                "ticker_o_sector": l.ticker_o_sector,
                "model": l.model,
                "tokens_in": l.tokens_input,
                "tokens_out": l.tokens_output,
                "cache_read": l.tokens_cache_read,
                "web_searches": l.web_searches,
                "cost_usd": round(l.cost_usd, 4),
                "latency_s": l.latency_s,
            }
            for l in recientes
        ]

    return {
        "ventana_dias": dias,
        "total_usd": round(total, 2),
        "mes_actual_usd": round(mes_actual, 2),
        "por_agente": [
            {
                "agent": r[0], "calls": r[1], "cost_usd": round(r[2], 2),
                "tokens_in": r[3], "tokens_out": r[4],
                "cache_read": r[5], "web_searches": r[6],
            }
            for r in por_agente
        ],
        "recientes": recientes_data,
    }


@app.get("/juez/risk")
def juez_risk_monitor() -> dict:
    alertas = juez_agent.risk_monitor()
    return {"total": len(alertas), "alertas": juez_agent.alertas_to_dict(alertas)}


@app.get("/juez/process")
def juez_process_auditor() -> dict:
    items = juez_agent.process_auditor()
    return {"total": len(items), "items": juez_agent.items_to_dict(items)}


@app.get("/fichas/{ticker}")
def get_ficha(ticker: str) -> dict:
    """Ficha completa de una empresa — post-análisis."""
    ticker_upper = ticker.upper().strip()
    with session_scope() as s:
        f = s.query(Ficha).filter_by(ticker=ticker_upper).first()
        if f is None:
            raise HTTPException(status_code=404, detail=f"ficha {ticker_upper} no existe")

        criterios = {}
        for i in range(1, 11):
            score = getattr(f, f"score_criterio_{i}")
            if score is not None:
                criterios[str(i)] = {
                    "score": score,
                    "evidencia_a_favor": (f.evidencia_favor_json or {}).get(str(i)),
                    "evidencia_en_contra": (f.evidencia_contra_json or {}).get(str(i)),
                    "justificacion": (f.justificacion_json or {}).get(str(i)),
                }

        return {
            "ticker": f.ticker,
            "nombre": f.nombre,
            "sector": f.sector,
            "driver_macro": f.driver_macro,
            "estado": f.estado,
            "score_vigente": f.score_vigente,
            "nivel_r": f.nivel_r,
            "tesis_vigente": f.tesis_vigente,
            "posicion_ciclo": f.posicion_ciclo,
            "duracion_edge": f.duracion_edge,
            "catalizador": {
                "tipo": f.tipo_catalizador,
                "descripcion": f.catalizador_descripcion,
                "fecha": f.catalizador_fecha,
                "impacto": f.catalizador_impacto,
            },
            "invalidation_triggers": f.invalidation_triggers,
            "plan_salida": f.plan_salida,
            "precio": {
                "actual": f.precio_ultima_actualizacion_ficha,
                "bull_case": f.bull_case_precio,
                "bear_case": f.bear_case_precio,
            },
            "crecimiento": {
                "implicito_en_precio": f.crecimiento_implicito_precio,
                "estimado_analista": f.estimacion_crecimiento,
            },
            "management": {
                "track_record": f.management_track_record,
                "alignment": f.management_alignment,
                "alignment_evidencia": f.management_alignment_evidencia,
            },
            "liquidez_suficiente": f.liquidez_suficiente,
            "tam_excepcion": f.tam_excepcion,
            "governance": {
                "red_flags": f.red_flags_count,
                "estado": f.estado_governance,
                "detalle": f.red_flags_detalle,
            },
            "contexto_sectorial": {
                "mapa_usado": f.mapa_sectorial_usado,
                "version": f.mapa_sectorial_version,
                "citado": f.contexto_sectorial_citado,
            },
            "freshness": {
                "ultimo_deep_research": f.fecha_ultimo_deep_research.isoformat() if f.fecha_ultimo_deep_research else None,
                "proximo_deep_research": f.fecha_proximo_deep_research.isoformat() if f.fecha_proximo_deep_research else None,
                "prompt_version": f.prompt_version,
            },
            "criterios": criterios,
            "cambios_score": f.cambios_score or [],
            "cambios_estado": f.cambios_estado or [],
        }
