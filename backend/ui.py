"""Routes de UI — renderizado server-side con Jinja2.

Separado de main.py (que expone la API JSON) para mantener responsabilidades claras.
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from backend import auth
from backend.agents import descubrimiento as desc_agent
from backend.agents.analista_runner import dispatch_analista
from backend.agents import discovery_hipotesis as discovery_agent
from backend.agents import juez as juez_agent
from backend.agents import mapa_sectorial as mapa_agent
from backend.agents.portfolio_snapshot import calcular_estado_portfolio
from backend.database import session_scope
from backend.models import (
    DispatchLog,
    EstadoAprobacion,
    EstadoEvento,
    EstadoFicha,
    Evento,
    Ficha,
    Macro,
    PortfolioSnapshot,
    Recomendacion,
    Sector,
    SectorMapa,
)
from backend.utils import utcnow

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()


VERSION = "0.5.0"


def _common_context(request: Request, active: str = "") -> dict:
    """Contexto compartido por todas las páginas (sidebar info, macro, etc)."""
    from backend import panic
    with session_scope() as s:
        macro = s.query(Macro).filter_by(activa=True).first()
        macro_version = macro.version if macro else None
        macro_fase = macro.fase_actual if macro else None
        macro_postura = macro.postura_capital if macro else None
        eventos_pend = s.query(Evento).filter_by(estado=EstadoEvento.PENDIENTE.value).count()

    panic_estado = panic.estado()

    return {
        "request": request,
        "version": VERSION,
        "active": active,
        "macro_version": macro_version,
        "macro_fase": macro_fase,
        "macro_postura": macro_postura,
        "eventos_pendientes": eventos_pend,
        "estado_sistema": "pausado" if panic_estado["sistema_pausado"] else "ok",
        "panic": panic_estado,
    }


# ---------- Dashboard ----------

@router.get("/", response_class=HTMLResponse)
def home_nucleo(request: Request):
    """Home — núcleo nuevo (cartera paper autónoma + P&L + equity). Reemplaza al
    dashboard viejo, que pasa a /legacy."""
    import json as _json
    libro_path = Path(__file__).resolve().parent.parent / "data" / "nucleo_paper" / "libro.json"
    mtm, snapshots, journal, actualizado = None, [], [], None
    if libro_path.exists():
        try:
            lp = _json.loads(libro_path.read_text(encoding="utf-8"))
            mtm = lp.get("last_mtm")
            snapshots = lp.get("snapshots") or []
            journal = list(reversed(lp.get("journal") or []))[:12]
            actualizado = lp.get("actualizado")
        except Exception:
            pass
    from backend.seleccion.paper_pnl import curva_vs_spy
    curva = curva_vs_spy(snapshots)
    alpha_actual = next((a for a in reversed(curva["alpha_pct"]) if a is not None), None)
    ctx = _common_context(request, active="home")
    ctx.update({"mtm": mtm, "snapshots": snapshots, "journal": journal,
                "actualizado": actualizado, "curva": curva, "alpha_actual": alpha_actual})
    return templates.TemplateResponse("home.html", ctx)


@router.get("/hoja", response_class=HTMLResponse)
def hoja_evidencia_view(request: Request):
    """Hoja de evidencia rankeada del universo (precomputada por ops.generar_hoja)."""
    import json
    from pathlib import Path
    ctx = _common_context(request, active="hoja")
    path = Path(__file__).resolve().parent.parent / "data" / "hoja_evidencia.json"
    if path.exists():
        ctx.update(json.loads(path.read_text()))
    else:
        ctx.update({"rankeado": [], "descriptivo": {}, "generado": None, "universo_n": 0})
    return templates.TemplateResponse("hoja.html", ctx)


@router.get("/sizing", response_class=HTMLResponse)
def sizing_view(request: Request):
    """Ledger de sizing determinista (doc 47, Fase 1) — el TECHO que el motor pone a cada nombre del bucket
    growth/BURDEN, con el desglose de factores. Precomputado por ops.generar_sizing. NO es el tamaño final:
    el PM elige dentro del cap (doc 39)."""
    import json
    from pathlib import Path
    ctx = _common_context(request, active="sizing")
    path = Path(__file__).resolve().parent.parent / "data" / "sizing_book.json"
    if path.exists():
        ctx.update(json.loads(path.read_text()))
    else:
        ctx.update({"rows": [], "generado": None, "politica": None,
                    "cap_floor": 0.04, "cap_max": 0.08, "cluster_cap": 0.16})
    return templates.TemplateResponse("sizing.html", ctx)


@router.get("/legacy", response_class=HTMLResponse)
def dashboard(request: Request):
    now = utcnow()

    # Estado vivo del portfolio (precios MtM + P&L por posición)
    from backend import panic
    capital_actual = panic.estado().get("capital_total_usd") or 0.0
    estado_pf = calcular_estado_portfolio(capital_actual)
    n_portfolio = sum(
        1 for p in estado_pf["posiciones"]
        if p["estado"] == EstadoFicha.PORTFOLIO_ACTIVO.value
    )
    n_bucket = sum(
        1 for p in estado_pf["posiciones"]
        if p["estado"] == EstadoFicha.BUCKET_EXPLORATORIO.value
    )
    posiciones_data = [
        {
            "ticker": p["ticker"],
            "nombre": p["nombre"],
            "sector": p["sector"],
            "sizing": p["sizing_pct"],
            "precio_entrada": p["precio_entrada"],
            "precio_actual": p["precio_actual"],
            "precio_mtm_at": p["precio_mtm_at"],
            "valor_actual_usd": p["valor_actual_usd"],
            "pnl_pct": p["pnl_pct"],
            "pnl_usd": p["pnl_usd"],
            "dias_en_cartera": p["dias_en_cartera"],
            "estado": p["estado"],
        }
        for p in estado_pf["posiciones"]
    ]
    exposicion = estado_pf["exposicion_pct"]
    with session_scope() as s:

        macro = s.query(Macro).filter_by(activa=True).first()
        macro_data = {
            "version": macro.version if macro else None,
            "fase": macro.fase_actual if macro else None,
            "postura": macro.postura_capital if macro else None,
            "notas": (macro.notas or "")[:500] if macro else "",
        }

        recs_pendientes = (
            s.query(Recomendacion)
            .filter(Recomendacion.estado_aprobacion == EstadoAprobacion.PENDIENTE.value)
            .order_by(Recomendacion.timestamp_juez.desc())
            .limit(10)
            .all()
        )
        recs_data = [
            {
                "id": r.id,
                "ticker": r.ticker,
                "accion": r.accion,
                "estado_rec": r.estado_rec,
                "motivo_cuestionada": r.motivo_cuestionada,
                "sizing_sugerido": r.sizing_sugerido,
                "asimetria": r.asimetria_vigente,
                "momentum": r.momentum_sectorial_leido,
                "justificacion": r.justificacion,
                "prioridad_capital": r.prioridad_capital,
                "exposicion_pct_al_evaluar": r.exposicion_pct_al_evaluar,
                "timestamp": r.timestamp_juez.strftime("%Y-%m-%d %H:%M") if r.timestamp_juez else "",
            }
            for r in recs_pendientes
        ]

        eventos_recientes = (
            s.query(Evento)
            .filter(Evento.estado == EstadoEvento.PENDIENTE.value)
            .order_by(Evento.timestamp.desc())
            .limit(5)
            .all()
        )
        eventos_data = [
            {
                "id": e.id,
                "ticker": e.ticker,
                "tipo": e.tipo,
                "descripcion": e.descripcion[:120],
                "timestamp": e.timestamp.strftime("%Y-%m-%d %H:%M"),
                "tier": e.tier,
            }
            for e in eventos_recientes
        ]

        sectores = s.query(Sector).order_by(Sector.nombre).all()
        sectores_data = [
            {
                "nombre": sc.nombre,
                "momentum": sc.momentum,
                "prioridad": sc.prioridad,
                "ultima_actualizacion": sc.ultima_actualizacion.strftime("%Y-%m-%d") if sc.ultima_actualizacion else "",
            }
            for sc in sectores
        ]

    # Alertas
    risk_alertas = juez_agent.risk_monitor()
    process_items = juez_agent.process_auditor()

    # Snapshot anterior (para mostrar P&L del día) — busca el último snapshot de fecha previa.
    pnl_dia_usd = 0.0
    fecha_hoy = now.strftime("%Y-%m-%d")
    from backend.models import Trade
    with session_scope() as s:
        snap_prev = (
            s.query(PortfolioSnapshot)
            .filter(PortfolioSnapshot.fecha < fecha_hoy)
            .order_by(PortfolioSnapshot.fecha.desc())
            .first()
        )
        if snap_prev and estado_pf["equity_total_usd"]:
            pnl_dia_usd = round(estado_pf["equity_total_usd"] - snap_prev.equity_total_usd, 2)

        # Equity curve últimos 30 días para mini-sparkline en dashboard
        snaps_30d = (
            s.query(PortfolioSnapshot)
            .order_by(PortfolioSnapshot.fecha.desc())
            .limit(30)
            .all()
        )
        equity_curve = [
            {"fecha": sn.fecha, "equity": sn.equity_total_usd, "pnl_total_pct": sn.pnl_total_pct}
            for sn in reversed(snaps_30d)
        ]

        # Trades cerrados (P&L realizado por trade) — últimos 10
        trades_closed = (
            s.query(Trade)
            .filter_by(status="closed")
            .order_by(Trade.fecha_cierre.desc())
            .limit(10)
            .all()
        )
        trades_cerrados_data = [
            {
                "ticker": t.ticker,
                "sector": t.sector_apertura,
                "fecha_apertura": t.fecha_apertura.strftime("%Y-%m-%d") if t.fecha_apertura else "",
                "fecha_cierre": t.fecha_cierre.strftime("%Y-%m-%d") if t.fecha_cierre else "",
                "precio_entrada": t.precio_entrada,
                "precio_cierre": t.precio_cierre,
                "capital_deployado_usd": t.capital_deployado_usd,
                "pnl_realizado_usd": t.pnl_realizado_usd,
                "pnl_realizado_pct": t.pnl_realizado_pct,
                "motivo_cierre": t.motivo_cierre,
                "dias": (t.fecha_cierre - t.fecha_apertura).days if t.fecha_cierre and t.fecha_apertura else None,
            }
            for t in trades_closed
        ]

    # Alertas
    risk_alertas = juez_agent.risk_monitor()
    process_items = juez_agent.process_auditor()

    ctx = _common_context(request, active="legacy")
    capital = ctx.get("panic", {}).get("capital_total_usd") or 0
    ctx.update({
        "n_portfolio": n_portfolio,
        "n_bucket": n_bucket,
        "exposicion": round(exposicion, 1),
        "exposicion_usd": round(estado_pf["capital_deployado_usd"], 2),
        "capital_usd": round(capital, 2),
        "cash_usd": round(estado_pf["cash_usd"], 2),
        "equity_total_usd": round(estado_pf["equity_total_usd"], 2),
        "pnl_total_usd": round(estado_pf["pnl_total_usd"], 2),
        "pnl_total_pct": round(estado_pf["pnl_total_pct"], 2),
        "pnl_realizado_usd": round(estado_pf.get("pnl_realizado_usd", 0.0), 2),
        "pnl_abierto_usd": round(estado_pf.get("pnl_abierto_usd", 0.0), 2),
        "n_trades_cerrados": estado_pf.get("n_trades_cerrados", 0),
        "n_trades_abiertos": estado_pf.get("n_trades_abiertos", 0),
        "trades_cerrados": trades_cerrados_data,
        "pnl_dia_usd": pnl_dia_usd,
        "equity_curve": equity_curve,
        "posiciones": posiciones_data,
        "macro": macro_data,
        "recomendaciones": recs_data,
        "eventos_recientes": eventos_data,
        "sectores": sectores_data,
        "alertas_risk": [
            {"tipo": a.tipo, "ticker": a.ticker, "severidad": a.severidad, "descripcion": a.descripcion}
            for a in risk_alertas
        ],
        "process_items": [
            {"tipo": p.tipo, "ticker": p.ticker, "descripcion": p.descripcion, "dias_vencido": p.dias_vencido}
            for p in process_items
        ],
    })
    return templates.TemplateResponse("dashboard.html", ctx)


# ---------- Evaluate ----------

@router.get("/evaluate", response_class=HTMLResponse)
def evaluate(request: Request):
    """UI para correr batch_analista on-demand con filtros."""
    with session_scope() as s:
        sectores_disponibles = sorted([sec.nombre for sec in s.query(Sector).all()])
        # Tasks recientes de tipo evaluate_batch
        from backend.models import Task
        tasks_recientes = (
            s.query(Task)
            .filter_by(tipo="evaluate_batch")
            .order_by(Task.created_at.desc())
            .limit(5)
            .all()
        )
        tasks_data = []
        for t in tasks_recientes:
            tickers_total = (t.resultado_json or {}).get("tickers_total", []) or []
            # Mostrar primeros 4 tickers + "+N más" si hay más
            if len(tickers_total) <= 4:
                tickers_str = ", ".join(tickers_total) if tickers_total else "—"
            else:
                tickers_str = f"{', '.join(tickers_total[:4])} +{len(tickers_total) - 4}"
            tasks_data.append({
                "id": t.id,
                "estado": t.estado,
                "progreso": t.progreso,
                "ticker_o_sector": t.ticker_o_sector,
                "tickers_lista": tickers_str,
                "tickers_full": ", ".join(tickers_total) if tickers_total else "",
                "created_at": t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "",
                "n_candidatos": len((t.resultado_json or {}).get("candidatos", [])),
            })
    estados_disponibles = [
        "Universo", "Candidata", "WL_Seguimiento", "WL_Activa",
        "WL_Prioritaria", "Portfolio_Activo", "Bucket_Exploratorio",
    ]
    ctx = _common_context(request, active="evaluate")
    ctx.update({
        "sectores_disponibles": sectores_disponibles,
        "estados_disponibles": estados_disponibles,
        "tasks_recientes": tasks_data,
    })
    return templates.TemplateResponse("evaluate.html", ctx)


# ---------- Universo ----------

@router.get("/universo", response_class=HTMLResponse)
def universo(
    request: Request,
    estado: str = "",
    sector: str = "",
    score_min: float = 0,
    nivel_r: str = "",
    q: str = "",
):
    with session_scope() as s:
        query = s.query(Ficha)
        if estado:
            query = query.filter(Ficha.estado == estado)
        if sector:
            query = query.filter(Ficha.sector == sector)
        if score_min > 0:
            query = query.filter(Ficha.score_vigente >= score_min)
        if nivel_r:
            query = query.filter(Ficha.nivel_r == nivel_r)
        if q:
            qu = f"%{q.upper()}%"
            from sqlalchemy import or_
            query = query.filter(or_(Ficha.ticker.ilike(qu), Ficha.nombre.ilike(qu)))

        fichas = query.order_by(Ficha.score_vigente.desc().nullslast(), Ficha.ticker.asc()).all()
        fichas_data = [
            {
                "ticker": f.ticker,
                "nombre": f.nombre,
                "sector": f.sector,
                "estado": f.estado,
                "score": f.score_vigente,
                "nivel_r": f.nivel_r,
                "sizing": f.sizing_actual,
                "driver_macro": f.driver_macro,
                "proximo_catalizador": f.catalizador_fecha,
                "tipo_catalizador": f.tipo_catalizador,
            }
            for f in fichas
        ]
        sectores_lista = [x.nombre for x in s.query(Sector).order_by(Sector.nombre).all()]

    ctx = _common_context(request, active="universo")
    ctx.update({
        "fichas": fichas_data,
        "sectores_lista": sectores_lista,
        "filtros": {"estado": estado, "sector": sector, "score_min": score_min, "nivel_r": nivel_r, "q": q},
        "estados_posibles": [e.value for e in EstadoFicha],
    })
    return templates.TemplateResponse("universo.html", ctx)


# ---------- Ficha Detalle ----------

@router.get("/fichas/{ticker}/view", response_class=HTMLResponse)
def ficha_detalle(request: Request, ticker: str):
    ticker_u = ticker.upper()
    with session_scope() as s:
        f = s.query(Ficha).filter_by(ticker=ticker_u).first()
        if f is None:
            return HTMLResponse(f"<h1>Ficha {ticker_u} no existe</h1>", status_code=404)

        criterios_data = []
        for i in range(1, 11):
            score = getattr(f, f"score_criterio_{i}")
            if score is not None:
                criterios_data.append({
                    "num": i,
                    "score": score,
                    "core": i in (1, 2, 3),
                    "evidencia_favor": (f.evidencia_favor_json or {}).get(str(i), ""),
                    "evidencia_contra": (f.evidencia_contra_json or {}).get(str(i), ""),
                    "justificacion": (f.justificacion_json or {}).get(str(i), ""),
                })

        # Recomendación pendiente (si existe)
        rec = (
            s.query(Recomendacion)
            .filter(Recomendacion.ticker == ticker_u)
            .filter(Recomendacion.estado_aprobacion == EstadoAprobacion.PENDIENTE.value)
            .order_by(Recomendacion.timestamp_juez.desc())
            .first()
        )
        rec_data = None
        if rec:
            rec_data = {
                "id": rec.id,
                "accion": rec.accion,
                "estado_rec": rec.estado_rec,
                "motivo_cuestionada": rec.motivo_cuestionada,
                "sizing_sugerido": rec.sizing_sugerido,
                "capacidad_maxima": rec.capacidad_maxima_teorica,
                "asimetria": rec.asimetria_vigente,
                "momentum": rec.momentum_sectorial_leido,
                "reglas": rec.reglas_verificadas or {},
                "checklist": rec.checklist_json or {},
                "contexto_macro": rec.contexto_macro,
                "justificacion": rec.justificacion,
                "prioridad_capital": rec.prioridad_capital,
                "exposicion_pct_al_evaluar": rec.exposicion_pct_al_evaluar,
            }

        f_data = {
            "ticker": f.ticker, "nombre": f.nombre, "sector": f.sector,
            "driver_macro": f.driver_macro, "estado": f.estado,
            "score": f.score_vigente, "nivel_r": f.nivel_r,
            "tesis": f.tesis_vigente,
            "posicion_ciclo": f.posicion_ciclo, "duracion_edge": f.duracion_edge,
            "duracion_edge_justif": f.duracion_edge_justificacion,
            "bull": f.bull_case_precio, "bear": f.bear_case_precio,
            "precio_actual": f.precio_ultima_actualizacion_ficha,
            "crec_implicito": f.crecimiento_implicito_precio,
            "crec_estimado": f.estimacion_crecimiento,
            "triggers": f.invalidation_triggers or [],
            "tipo_cat": f.tipo_catalizador, "cat_desc": f.catalizador_descripcion,
            "cat_fecha": f.catalizador_fecha, "cat_impacto": f.catalizador_impacto,
            "plan_salida": f.plan_salida,
            "mgmt_track": f.management_track_record,
            "mgmt_alignment": f.management_alignment,
            "mgmt_evidencia": f.management_alignment_evidencia,
            "liquidez": f.liquidez_suficiente,
            "tam_excepcion": f.tam_excepcion,
            "red_flags": f.red_flags_count,
            "red_flags_detalle": f.red_flags_detalle,
            "estado_gov": f.estado_governance,
            "sizing_actual": f.sizing_actual,
            "precio_entrada": f.precio_entrada,
            "umbral_rotacion": f.umbral_rotacion,
            "piramidacion_disp": f.piramidacion_disponible,
            "mapa_usado": f.mapa_sectorial_usado,
            "mapa_version": f.mapa_sectorial_version,
            "mapa_citado": f.contexto_sectorial_citado,
            "ultimo_dr": f.fecha_ultimo_deep_research.strftime("%Y-%m-%d") if f.fecha_ultimo_deep_research else None,
            "proximo_dr": f.fecha_proximo_deep_research.strftime("%Y-%m-%d") if f.fecha_proximo_deep_research else None,
            "prompt_version": f.prompt_version,
            "cambios_score": f.cambios_score or [],
            "cambios_estado": f.cambios_estado or [],
        }

    ctx = _common_context(request, active="universo")
    ctx.update({"f": f_data, "criterios": criterios_data, "rec": rec_data})
    return templates.TemplateResponse("ficha.html", ctx)


# ---------- Sectores ----------

@router.get("/sectores", response_class=HTMLResponse)
def sectores_view(request: Request):
    with session_scope() as s:
        sectores = s.query(Sector).order_by(Sector.nombre).all()
        data = []
        for sc in sectores:
            m = (
                s.query(SectorMapa)
                .filter_by(sector=sc.nombre, estado="activo")
                .order_by(SectorMapa.fecha_generacion.desc())
                .first()
            )
            mapa_info = None
            if m:
                vencimiento = m.fecha_generacion + timedelta(days=m.dias_vencimiento)
                now = utcnow()
                mapa_info = {
                    "fecha_gen": m.fecha_generacion.strftime("%Y-%m-%d"),
                    "dias_restantes": (vencimiento - now).days,
                    "vencido": vencimiento < now,
                    "aprobado": m.aprobado_por_humano,
                    "dias_venc": m.dias_vencimiento,
                }
            n_empresas = s.query(Ficha).filter_by(sector=sc.nombre).count()
            data.append({
                "nombre": sc.nombre,
                "momentum": sc.momentum,
                "prioridad": sc.prioridad,
                "horizonte": sc.horizonte,
                "ultima_actualizacion": sc.ultima_actualizacion.strftime("%Y-%m-%d") if sc.ultima_actualizacion else "",
                "mapa": mapa_info,
                "n_empresas": n_empresas,
            })

    ctx = _common_context(request, active="sectores")
    ctx.update({"sectores": data, "momentums_posibles": ["pre_rally", "rally_temprano", "rally_maduro", "agotamiento", ""]})
    return templates.TemplateResponse("sectores.html", ctx)


@router.get("/sectores/{nombre}/view", response_class=HTMLResponse)
def sector_detalle(request: Request, nombre: str):
    mapa = mapa_agent.get_mapa_activo(nombre)
    with session_scope() as s:
        sc = s.query(Sector).filter_by(nombre=nombre).first()
        if sc is None:
            return HTMLResponse(f"<h1>Sector {nombre} no existe</h1>", status_code=404)
        n_empresas = s.query(Ficha).filter_by(sector=nombre).count()
        fichas_sector = [
            {"ticker": f.ticker, "nombre": f.nombre, "estado": f.estado, "score": f.score_vigente}
            for f in s.query(Ficha).filter_by(sector=nombre).order_by(Ficha.score_vigente.desc().nullslast()).limit(30).all()
        ]
        sc_data = {
            "nombre": sc.nombre,
            "momentum": sc.momentum,
            "prioridad": sc.prioridad,
            "horizonte": sc.horizonte,
            "notas": sc.notas,
            "n_empresas": n_empresas,
        }

    ctx = _common_context(request, active="sectores")
    ctx.update({"sc": sc_data, "mapa": mapa, "fichas": fichas_sector})
    return templates.TemplateResponse("sector_detalle.html", ctx)


# ---------- Eventos ----------

@router.get("/eventos", response_class=HTMLResponse)
def eventos_view(request: Request, estado: str = "pendiente", tipo: str = "", ticker: str = ""):
    with session_scope() as s:
        q = s.query(Evento)
        if estado:
            q = q.filter(Evento.estado == estado)
        if tipo:
            q = q.filter(Evento.tipo == tipo)
        if ticker:
            q = q.filter(Evento.ticker == ticker.upper())
        eventos = q.order_by(Evento.timestamp.desc()).limit(100).all()
        eventos_data = [
            {
                "id": e.id, "ticker": e.ticker, "tipo": e.tipo,
                "descripcion": e.descripcion, "fuente": e.fuente,
                "tier": e.tier, "estado": e.estado,
                "timestamp": e.timestamp.strftime("%Y-%m-%d %H:%M"),
                "cooldown_hasta": e.cooldown_hasta.strftime("%Y-%m-%d %H:%M") if e.cooldown_hasta else None,
                "metadata": e.metadata_json or {},
            }
            for e in eventos
        ]

        logs = (
            s.query(DispatchLog)
            .order_by(DispatchLog.timestamp.desc())
            .limit(50)
            .all()
        )
        logs_data = [
            {
                "id": l.id, "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M"),
                "ticker": l.ticker_o_sector, "tipo_evento": l.tipo_evento,
                "tier": l.tier_fuente, "regla": l.regla_activada,
                "destino": l.destino, "urgencia": l.urgencia,
                "motivo": l.motivo, "cooldown": l.cooldown_activo,
            }
            for l in logs
        ]

    ctx = _common_context(request, active="eventos")
    ctx.update({
        "eventos": eventos_data,
        "dispatch_log": logs_data,
        "filtros": {"estado": estado, "tipo": tipo, "ticker": ticker},
        "tipos_evento": ["PRECIO_ALERTA", "EARNINGS_PROXIMOS", "NOTICIA_MATERIAL",
                        "INSIDER_ACTIVITY", "SCORE_DRIFT", "SHORT_REPORT", "RED_FLAG", "MOMENTUM_SECTORIAL"],
    })
    return templates.TemplateResponse("eventos.html", ctx)


# ---------- Discovery ----------

@router.get("/backtest", response_class=HTMLResponse)
def backtest_view(request: Request, mock: bool | None = None):
    from backend.backtesting.report import render_report_html
    from backend.backtesting.runner import load_latest_report

    latest_mock = load_latest_report(mock=True)
    latest_real = load_latest_report(mock=False)

    # Preferir real si existe, sino mock, según param
    if mock is True:
        activo = latest_mock
    elif mock is False:
        activo = latest_real
    else:
        activo = latest_real or latest_mock

    report_html = render_report_html(activo) if activo else None
    ctx = _common_context(request, active="backtest")
    ctx.update({
        "latest_mock": latest_mock,
        "latest_real": latest_real,
        "activo": activo,
        "report_html": report_html,
    })
    return templates.TemplateResponse("backtest.html", ctx)


@router.get("/costos", response_class=HTMLResponse)
def costos_view(request: Request):
    from datetime import timedelta
    from sqlalchemy import func
    from backend.models import LLMCall

    now = utcnow()
    cutoff_30 = now - timedelta(days=30)
    inicio_mes = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    with session_scope() as s:
        total_30 = s.query(func.coalesce(func.sum(LLMCall.cost_usd), 0.0)).filter(
            LLMCall.timestamp >= cutoff_30
        ).scalar() or 0.0
        mes_actual = s.query(func.coalesce(func.sum(LLMCall.cost_usd), 0.0)).filter(
            LLMCall.timestamp >= inicio_mes
        ).scalar() or 0.0
        total_lifetime = s.query(func.coalesce(func.sum(LLMCall.cost_usd), 0.0)).scalar() or 0.0
        n_calls = s.query(LLMCall).count()

        por_agente = s.query(
            LLMCall.agent,
            func.count(LLMCall.id),
            func.coalesce(func.sum(LLMCall.cost_usd), 0.0),
            func.coalesce(func.sum(LLMCall.tokens_input), 0),
            func.coalesce(func.sum(LLMCall.tokens_output), 0),
            func.coalesce(func.sum(LLMCall.web_searches), 0),
        ).filter(LLMCall.timestamp >= cutoff_30).group_by(LLMCall.agent).all()

        recientes = (
            s.query(LLMCall)
            .order_by(LLMCall.timestamp.desc())
            .limit(50)
            .all()
        )
        recientes_data = [
            {
                "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M"),
                "agent": l.agent,
                "ticker": l.ticker_o_sector,
                "model": l.model,
                "in": l.tokens_input, "out": l.tokens_output, "cache": l.tokens_cache_read,
                "searches": l.web_searches,
                "cost": l.cost_usd,
                "latency": l.latency_s,
            }
            for l in recientes
        ]

    ctx = _common_context(request, active="costos")
    ctx.update({
        "total_30": round(total_30, 2),
        "mes_actual": round(mes_actual, 2),
        "total_lifetime": round(total_lifetime, 2),
        "n_calls": n_calls,
        "por_agente": [
            {"agent": r[0], "calls": r[1], "cost": round(r[2], 2),
             "in": r[3], "out": r[4], "searches": r[5]}
            for r in por_agente
        ],
        "recientes": recientes_data,
    })
    return templates.TemplateResponse("costos.html", ctx)


@router.get("/rediseno", response_class=HTMLResponse)
def rediseno_view(request: Request):
    """Núcleo nuevo (rediseño) corriendo EN SOMBRA — ejemplos ilustrativos del flujo
    determinista + concentración de factor_macro de la brújula. No toca el sistema
    vivo; no gasta API."""
    from backend.nucleo import demo as nucleo_demo
    from backend.mapa.brujula import concentracion_factor_macro, territorios_activos

    entradas = nucleo_demo.ejemplos_entrada()
    salidas = nucleo_demo.ejemplos_salida()
    cartera = nucleo_demo.cartera_demo()
    fm = concentracion_factor_macro()

    fases = [
        ("Fase 0", "Going concern → CRR-crítico", True),
        ("Fase 1", "Núcleo determinista (arquetipo · gate · mérito · sizing · 5 vías) + extractor + estado", True),
        ("Fase 2", "Bloque B — mapa de cuellos (nodos · transiciones · brújula · discovery)", True),
        ("Fase 3", "Bloque C — presupuesto · watchlist viva · PM · sparring · monitor", True),
        ("Fase 4", "Integración — resolve_event · pre-flight · factor_macro · puntos humanos", True),
    ]
    pendientes = [
        "Conexión IBKR (fuente de precio del monitor; yfinance interino posible)",
        "Validación PASS_RATE 80% con hechos reales (ops/shadow_nucleo.py)",
        "Wiring al scheduler + persistencia DB de nodos",
        "El corte: apagar el score 0-10 viejo cuando valide",
    ]

    # Resultado de la última corrida real (sombra) sobre la cartera viva, si existe.
    import json as _json
    real_merged, real_meta = None, None
    _shadow_path = Path(__file__).resolve().parent.parent / "data" / "batches" / "shadow_nucleo_latest.json"
    if _shadow_path.exists():
        try:
            raw = _json.loads(_shadow_path.read_text(encoding="utf-8"))
            sal_por_ticker = {c["ticker"]: c for c in (raw.get("salida", {}).get("comparaciones") or [])}
            real_merged = []
            for c in (raw.get("entrada", {}).get("comparaciones") or []):
                s = sal_por_ticker.get(c["ticker"], {})
                real_merged.append({
                    "ticker": c["ticker"],
                    "old": c.get("old_accion"),
                    "entrada_new": c.get("new_decision"),
                    "arquetipo": c.get("new_arquetipo"),
                    "entrada_motivo": (c.get("new_motivo") or "")[:60],
                    "salida_new": s.get("new_accion"),
                    "salida_via": s.get("new_via"),
                })
            real_meta = {"generado": raw.get("generado"), "n": len(real_merged),
                         "acuerdo_entrada": raw.get("entrada", {}).get("resumen", {}).get("tasa_acuerdo"),
                         "acuerdo_salida": raw.get("salida", {}).get("resumen", {}).get("tasa_acuerdo")}
        except Exception:
            real_merged = None

    # Libro paper autónomo del núcleo nuevo (opera sin confirmación humana, simulado).
    paper = None
    _paper_path = Path(__file__).resolve().parent.parent / "data" / "nucleo_paper" / "libro.json"
    if _paper_path.exists():
        try:
            lp = _json.loads(_paper_path.read_text(encoding="utf-8"))
            pos = sorted(
                ({"ticker": t, **v} for t, v in (lp.get("posiciones") or {}).items()),
                key=lambda p: -(p.get("sizing") or 0))
            paper = {
                "posiciones": pos,
                "invertido": sum(p.get("sizing") or 0 for p in pos),
                "n": len(pos),
                "actualizado": lp.get("actualizado"),
                "journal": list(reversed(lp.get("journal") or []))[:15],
            }
        except Exception:
            paper = None

    ctx = _common_context(request, active="rediseno")
    ctx.update({
        "entradas": entradas, "salidas": salidas, "cartera": cartera,
        "factor_macro": fm, "territorios_activos": len(territorios_activos()),
        "fases": fases, "pendientes": pendientes,
        "real": real_merged, "real_meta": real_meta, "paper": paper,
    })
    return templates.TemplateResponse("rediseno.html", ctx)


@router.get("/discovery", response_class=HTMLResponse)
def discovery_view(request: Request):
    sessions = discovery_agent.list_discovery(20)
    latest = None
    if sessions:
        latest = discovery_agent.get_discovery_semana(sessions[0]["semana"])
    ctx = _common_context(request, active="discovery")
    ctx.update({"sessions": sessions, "latest": latest})
    return templates.TemplateResponse("discovery.html", ctx)


# ---------- Macro (edición inline con HTMX) ----------

@router.post("/macro/edit", response_class=HTMLResponse)
def macro_edit(
    request: Request,
    fase_actual: str = Form(...),
    postura_capital: str = Form(...),
    version: str = Form(...),
    notas: str = Form(""),
):
    with session_scope() as s:
        macro = s.query(Macro).filter_by(activa=True).first()
        if macro is None:
            macro = Macro(fase_actual=fase_actual, postura_capital=postura_capital, version=version, notas=notas, activa=True)
            s.add(macro)
        else:
            macro.fase_actual = fase_actual
            macro.postura_capital = postura_capital
            macro.version = version
            macro.notas = notas
            macro.fecha_actualizacion = utcnow()
    return RedirectResponse("/", status_code=303)


# ---------- Ajuste momentum sectorial inline ----------

@router.post("/sectores/{nombre}/momentum", response_class=HTMLResponse)
def set_momentum(nombre: str, momentum: str = Form("")):
    with session_scope() as s:
        sc = s.query(Sector).filter_by(nombre=nombre).first()
        if sc:
            sc.momentum = momentum or None
            sc.ultima_actualizacion = utcnow()
    return RedirectResponse(f"/sectores", status_code=303)


# ---------- Login / Logout ----------

@router.get("/login", response_class=HTMLResponse)
def login_get(next: str = "/"):
    return auth.login_page(next_path=next)


@router.post("/login")
def login_post(password: str = Form(...), next: str = Form("/")):
    ok, resp = auth.do_login(password, next_path=next)
    return resp


@router.get("/logout")
def logout():
    return auth.do_logout()


# ---------- Intake form (modal Universo) ----------

@router.post("/descubrimiento/crear-candidatas-form")
def intake_form(
    background_tasks: BackgroundTasks,
    ticker: str = Form(...),
    nombre: str = Form(...),
    sector: str = Form(...),
    driver_macro: str = Form(""),
    tesis_inicial: str = Form(""),
    urgencia: str = Form("baja"),
):
    """Intake de ficha desde el modal. Si urgencia=alta, dispara Analista auto (doc 02 sec 8.6)."""
    ticker_u = ticker.upper().strip()
    with session_scope() as s:
        existe = s.query(Ficha).filter_by(ticker=ticker_u).first()
        if existe is None:
            now = utcnow()
            s.add(Ficha(
                ticker=ticker_u,
                nombre=nombre,
                sector=sector,
                driver_macro=driver_macro or None,
                tesis_vigente=tesis_inicial or None,
                origen="Manual",
                estado=EstadoFicha.CANDIDATA.value,
                version_tesis_macro="v1.0",
                cambios_score=[],
                cambios_estado=[{
                    "timestamp": now.isoformat(),
                    "estado_anterior": None,
                    "estado_nuevo": EstadoFicha.CANDIDATA.value,
                    "motivo": f"intake manual (urgencia {urgencia})",
                }],
            ))

    # Urgencia alta → dispara Analista automático
    if urgencia == "alta":
        dispatch_analista(ticker_u, background_tasks)

    return RedirectResponse(f"/fichas/{ticker_u}/view", status_code=303)
