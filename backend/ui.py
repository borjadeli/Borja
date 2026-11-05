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
    """Inicio — overview del sistema ACTUAL (comité PM-IA v2): cartera + discovery + presupuesto + universo,
    en una pantalla, con enlaces a cada sección. Cada bloque es best-effort (nunca tumba el home)."""
    ctx = _common_context(request, active="home")
    equity = caja = 0.0
    n_pos = 0
    pos_top: list[dict] = []
    try:
        from backend.agentes.datos_reales import abrir_paper
        from backend.ledger import core
        from backend.services.market_data import get_price_snapshot
        s = abrir_paper()
        try:
            base = core.proyectar(s)
            precios: dict[str, float] = {}
            for tk in base["posiciones"]:
                try:
                    snap = get_price_snapshot(tk)
                    if snap and snap.precio_actual:
                        precios[tk] = snap.precio_actual
                except Exception:  # noqa: BLE001
                    pass
            est = core.proyectar(s, precios)
            equity, caja = est["equity"], est["caja"]
            pos = [{"ticker": tk, "mv": p.shares * precios.get(tk, 0.0)}
                   for tk, p in est["posiciones"].items() if p.shares > 0]
            pos.sort(key=lambda r: -r["mv"])
            n_pos, pos_top = len(pos), pos[:5]
        finally:
            s.close()
    except Exception:  # noqa: BLE001
        pass

    disc = {"propuestas": 0, "al_universo": 0, "analizadas": 0, "conviccion_alta": 0}
    try:
        from backend.agentes.descubrimiento import ColaPropuestas
        from backend.agentes.discovery_hitrate import embudo_discovery
        from backend.agentes.orquestador import CacheDossiers, _CACHE_PATH
        from backend.ledger.models import NxEmpresa
        with session_scope() as s2:
            uni = {e.ticker.upper(): e.estado
                   for e in s2.query(NxEmpresa).filter(NxEmpresa.fuente_ingreso == "discovery").all()}
        cache = CacheDossiers(path=_CACHE_PATH)
        disc = embudo_discovery(propuestas=ColaPropuestas()._estado_actual(), universo_estado=uni,
                                dossier_fn=lambda tk: (cache.ultimo(tk).dossier if cache.ultimo(tk) else None))["funnel"]
    except Exception:  # noqa: BLE001
        pass

    mes_actual, tope, n_universo = 0.0, 40.0, 0
    try:
        from sqlalchemy import func
        from backend.agentes.ips import IPS
        from backend.agentes.universo import tickers_universo
        from backend.models import LLMCall
        now = utcnow()
        inicio_mes = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        with session_scope() as s3:
            mes_actual = s3.query(func.coalesce(func.sum(LLMCall.cost_usd), 0.0)).filter(
                LLMCall.timestamp >= inicio_mes).scalar() or 0.0
            n_universo = len(tickers_universo(s3))
        tope = float(IPS.cargar().cfg.get("presupuesto_usd_mes", 40.0))
    except Exception:  # noqa: BLE001
        pass

    ctx.update({
        "equity": equity, "caja": caja, "n_pos": n_pos, "pos_top": pos_top,
        "disc": disc, "mes_actual": round(mes_actual, 2), "tope": tope,
        "pct_presupuesto": round(100 * mes_actual / tope, 0) if tope else 0, "n_universo": n_universo,
    })
    return templates.TemplateResponse("home.html", ctx)


@router.get("/cartera", response_class=HTMLResponse)
def cartera_view(request: Request):
    """Cartera del paper v2 — el ledger FIEL (SQLite nx_*), valuado a mercado. Es la cartera REAL del comité
    PM-IA (donde el PM abre/cierra posiciones), NO el libro.json viejo que muestra el home."""
    from backend.agentes.datos_reales import abrir_paper
    from backend.ledger import core
    from backend.ledger.models import NxFill
    from backend.services.market_data import get_price_snapshot
    ctx = _common_context(request, active="cartera")
    s = abrir_paper()                                             # el ledger fiel del paper v2 (data/paper_v2.db)
    try:
        base = core.proyectar(s)                                  # shares (sin valuar) para saber qué pedir
        precios: dict[str, float] = {}
        for tk in base["posiciones"]:
            try:
                snap = get_price_snapshot(tk)
                if snap and snap.precio_actual:
                    precios[tk] = snap.precio_actual
            except Exception:  # noqa: BLE001 — un ticker sin precio no debe tumbar la vista
                pass
        est = core.proyectar(s, precios)
        equity = est["equity"]
        posiciones = []
        for tk, p in est["posiciones"].items():
            if p.shares <= 0:
                continue
            precio = precios.get(tk)
            avg = p.costo_promedio
            mv = p.shares * precio if precio else 0.0
            posiciones.append({
                "ticker": tk, "shares": p.shares, "avg": avg, "precio": precio, "mv": mv,
                "peso": (mv / equity) if equity else 0.0,
                "upnl": (precio - avg) * p.shares if precio else None,
                "upnl_pct": (precio / avg - 1) if (precio and avg) else None,
            })
        posiciones.sort(key=lambda r: -r["mv"])
        fills = [{"fecha": f.fecha_fill, "ticker": f.ticker, "lado": f.lado, "shares": f.shares,
                  "precio": f.precio, "nota": f.nota}
                 for f in s.query(NxFill).order_by(NxFill.id.desc()).limit(15).all()]
    finally:
        s.close()
    ctx.update({
        "equity": equity, "caja": est["caja"], "valor_pos": est["valor_posiciones"],
        "realized": est["realized_pnl"], "posiciones": posiciones, "fills": fills,
        "n_pos": len(posiciones), "sin_precio": [r["ticker"] for r in posiciones if r["precio"] is None],
    })
    return templates.TemplateResponse("cartera.html", ctx)


@router.get("/descubrimiento", response_class=HTMLResponse)
def descubrimiento_view(request: Request):
    """Discovery (doc 76) — el motor de alpha: el embudo propuesta→universo→analizada, las empresas que el
    agente surfaceó (con convicción/clasificación del comité) y los cuellos nuevos que el curador validó al
    mapa. Todo determinista (join de las colas + nx_empresa + cache de dossiers); no gasta API."""
    from backend.agentes.descubrimiento import ColaNodos, ColaPropuestas
    from backend.agentes.discovery_hitrate import embudo_discovery, embudo_nodos
    from backend.agentes.orquestador import CacheDossiers, _CACHE_PATH
    from backend.ledger.models import NxEmpresa
    from backend.mapa.brujula import BRUJULA_WATCHLIST, territorios_activos
    ctx = _common_context(request, active="descubrimiento")
    with session_scope() as s:
        uni = {e.ticker.upper(): e.estado
               for e in s.query(NxEmpresa).filter(NxEmpresa.fuente_ingreso == "discovery").all()}
    cache = CacheDossiers(path=_CACHE_PATH)

    def _dossier(tk):
        e = cache.ultimo(tk)
        return e.dossier if e else None

    emp = embudo_discovery(propuestas=ColaPropuestas()._estado_actual(), universo_estado=uni, dossier_fn=_dossier)
    nod = embudo_nodos(ColaNodos()._estado_actual())
    ctx.update({"funnel": emp["funnel"], "filas": emp["filas"], "nodos": nod,
                "n_cuellos": len(list(territorios_activos())) + len(BRUJULA_WATCHLIST)})
    return templates.TemplateResponse("descubrimiento.html", ctx)


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


@router.get("/pm", response_class=HTMLResponse)
def pm_view(request: Request):
    """Decisiones del comité (v2) — los dossiers verificados que produjo el comité (Analista→Bear→Verificador),
    con convicción, clasificación, veredicto del Verificador, tesis bull/bear y falsador. Lee el cache de
    dossiers v2 (data/cache_dossiers_v2.json). Reemplaza el canal de juicio v3 (libro_pm.json)."""
    from backend.agentes.orquestador import CacheDossiers, _CACHE_PATH
    from backend.agentes.ledger_decisiones import LedgerDecisiones
    ctx = _common_context(request, active="pm")
    # última decisión REAL del PM por ticker (acción + peso), del ledger de decisiones — para que la vista
    # muestre qué DECIDIÓ el comité, no sólo el dossier que analizó.
    ultima_dec: dict[str, object] = {}
    for reg in LedgerDecisiones().decisiones():          # orden de append (viejo→nuevo): el último pisa
        ultima_dec[reg.ticker.upper()] = reg
    decisiones = []
    for tk, e in CacheDossiers(path=_CACHE_PATH).todos().items():
        d, v = e.dossier, e.verif
        inv = d.invertibilidad
        dec = ultima_dec.get(tk.upper())
        decisiones.append({
            "ticker": tk, "fecha": e.fecha, "conviccion": d.conviccion_0_1,
            "clasificacion": inv.analyst_classification if inv else None,
            "veredicto": getattr(v, "veredicto", None),
            "negocio": d.negocio_y_posicion_cuello,
            "valuacion": d.valuacion_que_exige_el_precio,
            "bull": d.bull.tesis if d.bull else None,
            "bear": d.bear.tesis if d.bear else None,
            "falsador": d.falsador.afirmacion if d.falsador else None,
            "falsador_fecha": d.falsador.fecha_limite if d.falsador else None,
            "n_red_flags": len(d.red_flags or []),
            "motivos": list(getattr(v, "motivos", []) or []),
            # decisión real del PM (si ya hubo un ciclo que la emitió)
            "pm_accion": getattr(dec, "accion", None),
            "pm_peso": getattr(dec, "peso_resultante", None),
            "pm_ciclo": (dec.ciclo if dec else None),
            "pm_tesis": getattr(dec, "tesis", None),
        })
    decisiones.sort(key=lambda r: (r["conviccion"] is None, -(r["conviccion"] or 0.0)))
    ctx.update({"decisiones": decisiones, "n": len(decisiones)})
    return templates.TemplateResponse("pm.html", ctx)


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

    try:
        from backend.agentes.ips import IPS
        presupuesto_mes = float(IPS.cargar().cfg.get("presupuesto_usd_mes", 40.0))
    except Exception:  # noqa: BLE001
        presupuesto_mes = 40.0

    ctx = _common_context(request, active="costos")
    ctx.update({
        "total_30": round(total_30, 2),
        "mes_actual": round(mes_actual, 2),
        "presupuesto_mes": presupuesto_mes,
        "pct_presupuesto": round(100 * mes_actual / presupuesto_mes, 0) if presupuesto_mes else 0,
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

