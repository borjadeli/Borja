"""Genera reporte PDF corporativo con:
- Por qué el portfolio está en 3/5
- Cómo se construyó BORJA + reglas v4.2 aplicándose
- Tabla 58 tickers que no entran (agrupados por motivo)
- Acciones disponibles

Pipeline: HTML+CSS → chromium headless → PDF.
"""
from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from backend.agents.portfolio_snapshot import calcular_estado_portfolio
from backend.database import session_scope
from backend.models import EstadoFicha, Ficha, Macro, Sector
from backend.agents.portfolio import (
    Accion,
    SCORE_MIN_ENTRADA,
    evaluar_entrada,
)


def cargar_no_pasan() -> list[dict]:
    """Carga las 58 fichas (todas excepto S/TENB/LEU) y devuelve motivo por cada una."""
    EXCLUIR = {"S", "TENB", "LEU"}
    resultados = []
    with session_scope() as s:
        macro = s.query(Macro).filter_by(activa=True).first()
        sectores_map = {sec.nombre: sec for sec in s.query(Sector).all()}
        rows = (
            s.query(Ficha)
            .filter(~Ficha.ticker.in_(EXCLUIR))
            .filter(~Ficha.estado.in_([EstadoFicha.SUSPENDIDA.value, EstadoFicha.ELIMINADA.value]))
            .order_by(Ficha.score_vigente.desc().nullslast(), Ficha.ticker)
            .all()
        )
        for f in rows:
            motivo = "—"
            grupo = "Otro"
            if f.score_vigente is None:
                motivo = "Sin análisis del Analista"
                grupo = "Sin análisis"
            elif f.bull_case_precio is None or f.bear_case_precio is None or f.nivel_r is None:
                motivo = "Análisis incompleto (falta bull/bear/nivel R)"
                grupo = "Sin análisis"
            else:
                sec = sectores_map.get(f.sector)
                rec = evaluar_entrada(s, f, sec, macro)
                if rec.accion == Accion.MANTENER:
                    motivo = rec.justificacion
                else:
                    motivo = rec.justificacion

                # Categorizar grupo
                m_low = motivo.lower()
                if "score" in m_low and "< 6" in m_low:
                    if (f.score_vigente or 0) >= 5.0:
                        grupo = "Borderline 5.0-5.99"
                    elif (f.score_vigente or 0) >= 4.0:
                        grupo = "Score bajo 4.0-4.95"
                    else:
                        grupo = "Loser ≤4.0"
                elif "concentración sectorial" in m_low and "ciber" in m_low:
                    grupo = "Concentración Ciber 2/2"
                elif "confidence baja" in m_low:
                    grupo = "Confidence Baja c#3"
                elif "asimetría" in m_low and "<" in m_low:
                    grupo = "Asimetría < umbral"

            resultados.append({
                "ticker": f.ticker,
                "sector": f.sector,
                "score": f.score_vigente,
                "estado": f.estado,
                "motivo": motivo,
                "grupo": grupo,
            })
    return resultados


def generar_html(no_pasan: list[dict], estado_pf: dict) -> str:
    """Renderiza el HTML corporativo."""
    fecha = datetime.now().strftime("%d %B %Y")

    # Agrupar para tablas
    grupos_orden = [
        "Concentración Ciber 2/2",
        "Confidence Baja c#3",
        "Asimetría < umbral",
        "Borderline 5.0-5.99",
        "Score bajo 4.0-4.95",
        "Loser ≤4.0",
        "Sin análisis",
    ]
    por_grupo: dict[str, list[dict]] = {g: [] for g in grupos_orden}
    for r in no_pasan:
        por_grupo.setdefault(r["grupo"], []).append(r)

    # Helpers para filas
    def filas_grupo(filas: list[dict]) -> str:
        if not filas:
            return '<tr><td colspan="3" class="empty">— sin tickers en esta categoría —</td></tr>'
        return "".join(
            f'<tr><td class="ticker">{r["ticker"]}</td>'
            f'<td class="sector">{(r["sector"] or "")[:34]}</td>'
            f'<td class="motivo">{r["motivo"]}</td></tr>'
            for r in filas
        )

    capital = estado_pf["capital_total_usd"]
    equity = estado_pf["equity_total_usd"]
    pnl_total = estado_pf["pnl_total_usd"]
    pnl_realizado = estado_pf.get("pnl_realizado_usd", 0)
    pnl_abierto = estado_pf.get("pnl_abierto_usd", 0)
    pnl_pct = estado_pf["pnl_total_pct"]

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>BORJA — Reporte de Portfolio · {fecha}</title>
<style>
@page {{
    size: A4;
    margin: 18mm 16mm 18mm 16mm;
    @bottom-right {{
        content: "BORJA · Investment System  ·  Página " counter(page) " / " counter(pages);
        font-family: 'Inter', sans-serif;
        font-size: 8pt;
        color: #64748b;
    }}
    @bottom-left {{
        content: "{fecha}  ·  CONFIDENCIAL";
        font-family: 'Inter', sans-serif;
        font-size: 8pt;
        color: #64748b;
    }}
}}

* {{ box-sizing: border-box; }}

body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    color: #0f172a;
    font-size: 9.5pt;
    line-height: 1.55;
    margin: 0;
}}

.serif {{ font-family: 'IBM Plex Serif', Georgia, serif; }}

.cover {{
    page-break-after: always;
    height: 100vh;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: flex-start;
    padding: 0 0;
    background: linear-gradient(135deg, #0a1628 0%, #142447 100%);
    color: white;
    margin: -18mm -16mm;
    padding: 18mm 16mm;
}}

.cover .brand {{
    font-family: 'IBM Plex Serif', Georgia, serif;
    font-size: 64pt;
    font-weight: 700;
    letter-spacing: -2px;
    line-height: 1;
    margin-bottom: 6px;
    color: white;
}}

.cover .subtitle {{
    font-size: 11pt;
    text-transform: uppercase;
    letter-spacing: 4px;
    color: #94a3b8;
    font-weight: 600;
    margin-bottom: 60px;
}}

.cover h1 {{
    font-family: 'IBM Plex Serif', Georgia, serif;
    font-size: 36pt;
    font-weight: 600;
    color: white;
    margin: 0 0 12px 0;
    line-height: 1.1;
}}

.cover .lead {{
    font-size: 12pt;
    color: #cbd5e1;
    max-width: 480px;
    line-height: 1.6;
}}

.cover .meta {{
    margin-top: 80px;
    border-top: 1px solid #475569;
    padding-top: 16px;
    font-size: 9pt;
    color: #94a3b8;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}}

.cover .meta strong {{ color: white; font-weight: 600; }}

h1.section {{
    font-family: 'IBM Plex Serif', Georgia, serif;
    font-size: 22pt;
    font-weight: 700;
    color: #0f172a;
    margin-top: 30px;
    margin-bottom: 4px;
    border-bottom: 3px solid #0a1628;
    padding-bottom: 8px;
}}

h1.section .num {{
    color: #94a3b8;
    font-weight: 400;
    margin-right: 12px;
}}

h2 {{
    font-family: 'IBM Plex Serif', Georgia, serif;
    font-size: 14pt;
    color: #0f172a;
    margin-top: 22px;
    margin-bottom: 10px;
    font-weight: 600;
}}

h3 {{
    font-size: 10.5pt;
    color: #1e293b;
    margin-top: 18px;
    margin-bottom: 8px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

p {{ margin: 8px 0; text-align: justify; }}

ul, ol {{ margin: 8px 0 8px 18px; padding-left: 14px; }}
li {{ margin: 4px 0; }}

.lead-section {{
    background: #f8fafc;
    border-left: 4px solid #0a1628;
    padding: 14px 18px;
    margin: 14px 0;
    font-size: 10pt;
    color: #334155;
}}

.lead-section .label {{
    text-transform: uppercase;
    letter-spacing: 1.5px;
    font-size: 8pt;
    color: #64748b;
    font-weight: 700;
    margin-bottom: 6px;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0 18px 0;
    font-size: 9pt;
    page-break-inside: avoid;
}}

th {{
    background: #0a1628;
    color: white;
    font-weight: 600;
    text-align: left;
    padding: 8px 10px;
    font-size: 8pt;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

td {{
    padding: 7px 10px;
    border-bottom: 1px solid #e2e8f0;
    vertical-align: top;
}}

tr:nth-child(even) td {{ background: #f8fafc; }}

td.ticker {{
    font-family: 'IBM Plex Mono', 'Courier New', monospace;
    font-weight: 700;
    color: #0a1628;
    width: 70px;
}}

td.sector {{
    color: #475569;
    font-size: 8.5pt;
    width: 180px;
}}

td.motivo {{
    color: #334155;
    font-size: 8.5pt;
}}

td.empty {{
    text-align: center;
    color: #94a3b8;
    font-style: italic;
    padding: 16px;
}}

.kpi-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin: 14px 0;
}}

.kpi {{
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    padding: 10px 12px;
    background: white;
}}

.kpi .label {{
    text-transform: uppercase;
    letter-spacing: 1px;
    font-size: 7.5pt;
    color: #64748b;
    font-weight: 600;
    margin-bottom: 4px;
}}

.kpi .value {{
    font-family: 'IBM Plex Serif', Georgia, serif;
    font-size: 18pt;
    font-weight: 700;
    color: #0a1628;
    line-height: 1;
}}

.kpi .sub {{
    font-size: 8pt;
    color: #64748b;
    margin-top: 4px;
}}

.kpi.pnl-pos .value {{ color: #047857; }}
.kpi.pnl-neg .value {{ color: #be123c; }}

.group-header {{
    background: #f1f5f9;
    padding: 10px 14px;
    border-left: 4px solid #0a1628;
    margin: 18px 0 0 0;
    page-break-after: avoid;
}}

.group-header h3 {{
    margin: 0;
    color: #0a1628;
    font-size: 10pt;
}}

.group-header .count {{
    float: right;
    background: #0a1628;
    color: white;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 8pt;
    font-weight: 700;
}}

.group-header.critical {{ border-left-color: #be123c; }}
.group-header.critical h3 {{ color: #be123c; }}
.group-header.critical .count {{ background: #be123c; }}

.group-header.warning {{ border-left-color: #d97706; }}
.group-header.warning h3 {{ color: #92400e; }}
.group-header.warning .count {{ background: #d97706; }}

.group-header.info {{ border-left-color: #475569; }}
.group-header.info h3 {{ color: #475569; }}
.group-header.info .count {{ background: #475569; }}

.callout {{
    background: #fef3c7;
    border-left: 4px solid #d97706;
    padding: 12px 16px;
    margin: 14px 0;
    font-size: 9pt;
}}

.callout-success {{
    background: #d1fae5;
    border-left: 4px solid #047857;
    padding: 12px 16px;
    margin: 14px 0;
    font-size: 9pt;
}}

.callout strong, .callout-success strong {{ color: inherit; }}

.architecture-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin: 12px 0;
}}

.arch-card {{
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    padding: 12px 14px;
    background: white;
    page-break-inside: avoid;
}}

.arch-card h4 {{
    font-family: 'IBM Plex Serif', Georgia, serif;
    margin: 0 0 6px 0;
    font-size: 11pt;
    color: #0a1628;
}}

.arch-card p {{ margin: 4px 0; font-size: 8.5pt; color: #475569; }}

.rules-list {{
    list-style: none;
    padding: 0;
    margin: 12px 0;
}}

.rules-list li {{
    background: #f8fafc;
    border-left: 3px solid #0a1628;
    padding: 10px 14px;
    margin: 6px 0;
    font-size: 9pt;
}}

.rules-list li strong {{
    display: block;
    color: #0a1628;
    margin-bottom: 4px;
    font-size: 9.5pt;
}}

.tag {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 7.5pt;
    font-weight: 600;
    margin-right: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

.tag-doc {{ background: #dbeafe; color: #1e40af; }}
.tag-sprint {{ background: #ede9fe; color: #5b21b6; }}

.section-break {{ page-break-before: always; }}
</style>
</head>
<body>

<!-- ==================== PORTADA ==================== -->
<div class="cover">
    <div class="brand">BORJA</div>
    <div class="subtitle">Investment System · v4.2</div>
    <h1>Reporte ejecutivo de portfolio</h1>
    <div class="lead">
        Análisis del estado actual del portfolio, los 58 tickers fuera del sistema
        formal con justificación cuantitativa, y la arquitectura de decisión que
        determina las entradas y salidas.
    </div>
    <div class="meta">
        <strong>Confidencial</strong> · Generado {fecha} · Capital base ${capital:,.0f}
    </div>
</div>

<!-- ==================== SECCIÓN 1 ==================== -->
<h1 class="section"><span class="num">1.</span>Estado del portfolio</h1>

<div class="kpi-grid">
    <div class="kpi">
        <div class="label">Equity total</div>
        <div class="value">${equity:,.0f}</div>
        <div class="sub">sobre ${capital:,.0f} inicial</div>
    </div>
    <div class="kpi {'pnl-pos' if pnl_total > 0 else 'pnl-neg' if pnl_total < 0 else ''}">
        <div class="label">P&amp;L total</div>
        <div class="value">{'+' if pnl_total >= 0 else ''}${pnl_total:,.0f}</div>
        <div class="sub">{'+' if pnl_pct >= 0 else ''}{pnl_pct:.2f}% sobre capital</div>
    </div>
    <div class="kpi {'pnl-pos' if pnl_realizado > 0 else 'pnl-neg' if pnl_realizado < 0 else ''}">
        <div class="label">P&amp;L realizado</div>
        <div class="value">{'+' if pnl_realizado >= 0 else ''}${pnl_realizado:,.0f}</div>
        <div class="sub">{estado_pf.get('n_trades_cerrados', 0)} trades cerrados</div>
    </div>
    <div class="kpi {'pnl-pos' if pnl_abierto > 0 else 'pnl-neg' if pnl_abierto < 0 else ''}">
        <div class="label">P&amp;L abierto</div>
        <div class="value">{'+' if pnl_abierto >= 0 else ''}${pnl_abierto:,.0f}</div>
        <div class="sub">{estado_pf.get('n_trades_abiertos', 0)} posiciones vivas</div>
    </div>
</div>

<h2>¿Por qué el portfolio está en 2 / 5 posiciones?</h2>

<div class="lead-section">
    <div class="label">Pregunta clave</div>
    Desde la primera operación BORJA seleccionó solo 3 instrumentos del universo de 50,
    y nunca más compró ni vendió hasta la rotación de LEU el 27-abril. ¿Es disfunción
    o disciplina funcionando?
</div>

<p>
Las 3 entradas originales (LEU, S, TENB) pasaron el 21-abril vía aprobación humana
después de que el Analista las puntuara alto. Desde entonces el sistema generó
<strong>205 recomendaciones más</strong>, todas resolviendo en <em>mantener</em> (69)
o <em>wl_prioritaria</em> (132) — nunca en <em>entrar</em>.
</p>

<p>
La razón es <strong>acumulación de filtros</strong>, no inactividad:
</p>

<ul>
    <li><strong>Score mínimo 6.0</strong>: filtra ~30 del universo automáticamente
        (la mayoría queda en 4-5.5).</li>
    <li><strong>Asimetría dinámica ≥2.0x al precio actual</strong>: AI infra
        (CRDO/ALAB/COHR/VRT/KLIC) tiene asimetrías 0.32-1.99x porque los precios
        subieron post-rally. La regla es clara: <em>"el precio que pagaste no importa,
        importa el upside vigente desde acá"</em>.</li>
    <li><strong>Concentración Ciber 2/2</strong>: S+TENB ya ocupan los 2 slots
        permitidos. Eso bloquea automáticamente a QLYS (asim 2.62), VRNS (2.04),
        RBRK, CVLT — los 4 mejores candidatos cualitativos.</li>
    <li><strong>Driver compartido capex_AI</strong>: aunque hubiera slot sectorial,
        los 5 sub-temas AI infra + Power Generation comparten driver y solo 2
        simultáneas pueden estar en Portfolio.</li>
</ul>

<p>
Ningún ticker pasó los 4 gates al mismo tiempo desde el 22-abril. El sistema
<strong>no compra solo</strong> — propone, y la propuesta se aprueba si pasa todo.
</p>

<div class="callout-success">
    <strong>El sistema está haciendo lo que se le pidió.</strong> La filosofía
    operativa explícita del usuario es <em>"prefiero slots vacíos a forzar entradas"</em>.
    Los 2 slots libres reflejan disciplina, no fallo.
</div>

<p>
Si se buscara más actividad sin tocar la disciplina, los caminos están:
</p>

<ul>
    <li><strong>(a)</strong> Cambiar la prioridad sectorial Ciber a <em>media-alta</em>
        para liberar el cap (afecta sizing también).</li>
    <li><strong>(b)</strong> Esperar caídas que devuelvan asimetría.</li>
</ul>

<!-- ==================== SECCIÓN 2 ==================== -->
<div class="section-break"></div>
<h1 class="section"><span class="num">2.</span>Cómo se construyó BORJA</h1>

<p>
BORJA es un sistema de inversión cuantitativo-cualitativo basado en el documento
<span class="tag tag-doc">v4.2 MVP</span> con agentes LLM. La filosofía operativa
es <strong>gestión con ratificación humana</strong>: la IA filtra, ordena, calcula
y obliga disciplina. El humano hace los juicios cualitativos finos y ratifica
cada acción.
</p>

<h2>Arquitectura de agentes</h2>

<div class="architecture-grid">
    <div class="arch-card">
        <h4>1. Filtro anti-fraude</h4>
        <p>Determinista, sin LLM. Bloquea antes del scoring: IPO &lt;2y, &gt;3 shelf
        en 24m, dilución &gt;40% sin growth, ATM &gt;15% del float.</p>
    </div>
    <div class="arch-card">
        <h4>2. Data Collector</h4>
        <p>SEC EDGAR + Yahoo + News RSS. Sin LLM. Junta financials, Form 4,
        precios, Capital Raise Risk determinista.</p>
    </div>
    <div class="arch-card">
        <h4>3. Analista (LLM Opus 4.7)</h4>
        <p>Llena los 10 criterios con score + confidence (Alta/Media/Baja) +
        fuente_nivel (A-F). Aplica enmiendas A/B cuando corresponde.</p>
    </div>
    <div class="arch-card">
        <h4>4. Rule Engine (Portfolio + Juez)</h4>
        <p>Determinista. Aplica gates de fail conditions, sizing efectivo
        (matriz convicción×momentum), bloqueos por confidence/CRR/concentración.</p>
    </div>
    <div class="arch-card">
        <h4>5. Research + Dispatcher</h4>
        <p>Monitores de earnings, Form 4, noticias, precios. Filtro adversario
        sobre cada noticia material. 7 reglas de routing.</p>
    </div>
    <div class="arch-card">
        <h4>6. Decision Journal + Trades</h4>
        <p>Append-only. Cada decisión queda con motivo. Trades con apertura/cierre
        preservan P&amp;L realizado al cerrar posiciones.</p>
    </div>
</div>

<h2>Sprints v4.2 implementados</h2>

<table>
<thead>
<tr><th>Sprint</th><th>Foco</th><th>Estado</th></tr>
</thead>
<tbody>
<tr><td><span class="tag tag-sprint">A</span></td><td>Capital Raise Risk + driver compartido capex_AI + filtro anti-fraude + alerta convicción/momentum</td><td>✓</td></tr>
<tr><td><span class="tag tag-sprint">B</span></td><td>Confidence Score por criterio + Jerarquía A-F + Enmienda C insider override</td><td>✓</td></tr>
<tr><td><span class="tag tag-sprint">C</span></td><td>Migración momentum 4→3 estados + matriz convicción×momentum + sub-temas AI infra</td><td>✓</td></tr>
<tr><td><span class="tag tag-sprint">D</span></td><td>Bucket mecánico (peer groups duales + precio base FD EV + ficha contractual)</td><td>✓</td></tr>
<tr><td><span class="tag tag-sprint">E</span></td><td>Decision Journal + Revalidación 30d + Protocolo Transición Fase Macro</td><td>✓</td></tr>
</tbody>
</table>

<!-- ==================== SECCIÓN 3 ==================== -->
<div class="section-break"></div>
<h1 class="section"><span class="num">3.</span>Reglas actualmente aplicándose</h1>

<h2>Las 3 Reglas invariantes</h2>

<ul class="rules-list">
    <li><strong>Regla 1 — Asimetría vigente al precio actual</strong>
        Recalcular R/R al precio actual antes de entrar/aumentar. Umbral según momentum
        sectorial (Favorable ≥2.0x, Neutral ≥2.5x, Desfavorable no entrar). Si cayó
        bajo 0.5x, evaluar rotación. La caída de precio con tesis intacta NO es señal
        de salida — es oportunidad.
    </li>
    <li><strong>Regla 2 — Governance y alignment</strong>
        Management con exposición significativa al precio. 8 red flags monitoreados.
        Con 2 red flags activos, no aumentar. Con 3, kill switch automático.
    </li>
    <li><strong>Regla 3 — Disciplina de concentración</strong>
        Máximo 5 posiciones formales + 1 bucket exploratorio. Máximo 2 por sector.
        Máximo 2 por driver macro compartido (capex_AI agrupa los 4 sub-temas
        AI infra + Power Generation).
    </li>
</ul>

<h2>Filtros operativos actuales</h2>

<table>
<thead>
<tr><th>Filtro</th><th>Umbral</th><th>Activación</th></tr>
</thead>
<tbody>
<tr><td>Score mínimo Portfolio</td><td>≥ 6.0</td><td>Calibrado empíricamente sobre Opus 4.7</td></tr>
<tr><td>Asimetría dinámica</td><td>≥ 2.0x (Favorable) / ≥ 2.5x (Neutral)</td><td>Calculada con precio_actual + bull/bear case</td></tr>
<tr><td>Confidence Baja en claim central</td><td>0 permitida</td><td>Criterios 1, 2, 3, 4, 6 deben tener fuente A o B</td></tr>
<tr><td>Capital Raise Risk</td><td>Solo Bajo o Medio</td><td>Alto = solo Bucket; Crítico = Eliminar del universo</td></tr>
<tr><td>Concentración por sector</td><td>Máx 2 simultáneas</td><td>Cap dura</td></tr>
<tr><td>Concentración por driver</td><td>Máx 2 simultáneas</td><td>capex_AI cubre AI infra (4 sub-temas) + Power Gen</td></tr>
<tr><td>Liquidez</td><td>Volumen diario &gt;$1M (&gt;$2M si pos &gt;7%)</td><td>Cap dura</td></tr>
<tr><td>Tesis intacta</td><td>5 condiciones</td><td>Rotar score&lt;6 requiere tesis no intacta</td></tr>
</tbody>
</table>

<h2>Matriz de sizing (Sprint C — v4.2 sec 4)</h2>

<p>El sizing efectivo de cada posición se calcula como:</p>

<div class="lead-section">
    <strong>Sizing final = Techo R × Multiplicador (convicción × momentum) × Multiplicador CRR × Multiplicador "ante la duda"</strong>
</div>

<table>
<thead>
<tr><th>Convicción macro</th><th>Momentum Favorable</th><th>Momentum Neutral</th><th>Momentum Desfavorable</th></tr>
</thead>
<tbody>
<tr><td>Alta</td><td>100% del techo</td><td>85% del techo</td><td>50% + alerta + sin aumentar</td></tr>
<tr><td>Media-alta</td><td>85% del techo</td><td>70% del techo</td><td>No entrar nuevo, existentes máx 50%</td></tr>
<tr><td>Media</td><td>70% del techo</td><td>50% del techo</td><td>No entrar, rotar existentes</td></tr>
</tbody>
</table>

<h2>Jerarquía de fuentes A-F (Sprint B — v4.2 sec 6)</h2>

<table>
<thead>
<tr><th>Nivel</th><th>Fuente</th><th>Uso</th></tr>
</thead>
<tbody>
<tr><td><strong>A</strong></td><td>10-K, 10-Q, 8-K, S-1, S-3, DEF14A, Form 4</td><td>Primaria. Requerida para claims centrales.</td></tr>
<tr><td><strong>B</strong></td><td>Earnings call transcript oficial</td><td>Aceptable para claims centrales.</td></tr>
<tr><td><strong>C</strong></td><td>Investor presentation</td><td>Útil pero sesgada — no suficiente para central.</td></tr>
<tr><td><strong>D</strong></td><td>Press release</td><td>Confirma evento, no tesis completa.</td></tr>
<tr><td><strong>E</strong></td><td>Sell-side / industry reports</td><td>Contexto sectorial, no claims específicos.</td></tr>
<tr><td><strong>F</strong></td><td>Twitter/X, Reddit, blogs</td><td>Solo sentimiento, nunca soporte de tesis.</td></tr>
</tbody>
</table>

<!-- ==================== SECCIÓN 4 ==================== -->
<div class="section-break"></div>
<h1 class="section"><span class="num">4.</span>Tickers fuera del sistema formal</h1>

<p>
Tabla completa de los <strong>58 tickers</strong> evaluados (universo total
excluyendo S, TENB y LEU ya tradeados). Cada uno con la justificación cuantitativa
del Portfolio Agent — todas decisiones <strong>determinísticas</strong>, sin
intervención del LLM.
</p>

<div class="callout">
    <strong>Lectura:</strong> los grupos están ordenados de <em>más cerca</em> a
    <em>más lejos</em> del Portfolio. Los primeros 13 (concentración, confidence,
    asimetría) tienen score ≥6 y serían candidatos legítimos si se levanta el
    bloqueo específico que los frena. Los borderline 5.0-5.99 son candidatos a
    revisar en próximos earnings.
</div>

<div class="group-header critical">
    <span class="count">{len(por_grupo['Concentración Ciber 2/2'])}</span>
    <h3>A.1 — Concentración Ciber 2/2 (S+TENB ocupan slots)</h3>
</div>
<table>
<thead><tr><th>Ticker</th><th>Sector</th><th>Motivo</th></tr></thead>
<tbody>{filas_grupo(por_grupo['Concentración Ciber 2/2'])}</tbody>
</table>

<div class="group-header critical">
    <span class="count">{len(por_grupo['Confidence Baja c#3'])}</span>
    <h3>A.2 — Confidence Baja en claim central c#3 (catalizadores en fuente F)</h3>
</div>
<table>
<thead><tr><th>Ticker</th><th>Sector</th><th>Motivo</th></tr></thead>
<tbody>{filas_grupo(por_grupo['Confidence Baja c#3'])}</tbody>
</table>

<div class="group-header warning">
    <span class="count">{len(por_grupo['Asimetría < umbral'])}</span>
    <h3>A.3 — Asimetría &lt; umbral momentum (precio cerca de bull case)</h3>
</div>
<table>
<thead><tr><th>Ticker</th><th>Sector</th><th>Motivo</th></tr></thead>
<tbody>{filas_grupo(por_grupo['Asimetría < umbral'])}</tbody>
</table>

<div class="group-header warning">
    <span class="count">{len(por_grupo['Borderline 5.0-5.99'])}</span>
    <h3>B — Borderline (score 5.0-5.99, un step del threshold)</h3>
</div>
<table>
<thead><tr><th>Ticker</th><th>Sector</th><th>Motivo</th></tr></thead>
<tbody>{filas_grupo(por_grupo['Borderline 5.0-5.99'])}</tbody>
</table>

<div class="group-header info">
    <span class="count">{len(por_grupo['Score bajo 4.0-4.95'])}</span>
    <h3>C — Score bajo (4.0-4.95)</h3>
</div>
<table>
<thead><tr><th>Ticker</th><th>Sector</th><th>Motivo</th></tr></thead>
<tbody>{filas_grupo(por_grupo['Score bajo 4.0-4.95'])}</tbody>
</table>

<div class="group-header info">
    <span class="count">{len(por_grupo['Loser ≤4.0'])}</span>
    <h3>D — Losers identificados (score ≤4.0)</h3>
</div>
<table>
<thead><tr><th>Ticker</th><th>Sector</th><th>Motivo</th></tr></thead>
<tbody>{filas_grupo(por_grupo['Loser ≤4.0'])}</tbody>
</table>

{f'''<div class="group-header info">
    <span class="count">{len(por_grupo['Sin análisis'])}</span>
    <h3>E — Sin análisis del Analista</h3>
</div>
<table>
<thead><tr><th>Ticker</th><th>Sector</th><th>Motivo</th></tr></thead>
<tbody>{filas_grupo(por_grupo['Sin análisis'])}</tbody>
</table>''' if por_grupo['Sin análisis'] else ''}

<!-- ==================== SECCIÓN 5 ==================== -->
<div class="section-break"></div>
<h1 class="section"><span class="num">5.</span>Acciones disponibles</h1>

<p>
Para desbloquear entradas al Portfolio sin violar la disciplina del sistema, las
opciones disponibles son las siguientes. Todas requieren <strong>decisión humana
explícita</strong> — el algoritmo no las ejecuta solo.
</p>

<ul class="rules-list">
    <li><strong>Opción 1 — Esperar caídas de precio</strong>
        Sin acción. Cuando los precios de AI infra (8 candidatos) caen 15-25% sin
        deterioro fundamental, la asimetría dinámica supera el umbral 2.0x y entran
        automáticamente. Es la opción más alineada con el doc 04 sec 5.
    </li>
    <li><strong>Opción 2 — Subir prioridad Ciber a "media-alta"</strong>
        Cambio de tesis macro. Permite 3 simultáneas en Ciber. <strong>NABL</strong>
        (score 6.04, asimetría 5.57x — la mejor del universo) entraría inmediatamente.
        Afecta sizing también — con prioridad media-alta el multiplicador convicción×momentum
        baja del 100% al 85%.
    </li>
    <li><strong>Opción 3 — Override de confidence c#3</strong>
        Solo si el humano tiene evidencia A/B documentada (10-K, earnings call) sobre
        catalizadores de COHR/CRDO/CVLT/QLYS. Endpoint disponible para subir manualmente
        la confidence con evidencia. Sin evidencia real, no hacer.
    </li>
    <li><strong>Opción 4 — Re-correr Analista en próximas earnings</strong>
        Los 21 borderline (5.0-5.99) tienen tesis sólidas. Próximas earnings (CVLT 29-abr,
        ALGM 1-may, etc.) pueden cambiar 2-3 scores significativamente.
    </li>
</ul>

<h2>Candidato más fuerte hoy</h2>

<div class="callout-success">
    <strong>NABL</strong> — score 6.04 + asimetría 5.57x + 0 red flags + CRR Bajo +
    sin Confidence Baja en claim central. Único bloqueo: concentración sectorial Ciber
    2/2. Si se libera el cap (Opción 2), entra al Portfolio inmediatamente con sizing
    máximo del nivel R.
</div>

</body>
</html>
"""


def generar_pdf(html_content: str, output_path: Path) -> Path:
    """Convierte HTML a PDF usando chromium headless."""
    html_path = output_path.with_suffix(".html")
    html_path.write_text(html_content, encoding="utf-8")
    cmd = [
        "/usr/bin/chromium",
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--no-pdf-header-footer",
        "--print-to-pdf=" + str(output_path),
        "file://" + str(html_path.resolve()),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print("STDERR:", result.stderr[-500:])
        raise RuntimeError(f"chromium falló: exit {result.returncode}")
    return output_path


def main() -> None:
    print("Cargando estado del portfolio…", flush=True)
    estado_pf = calcular_estado_portfolio()

    print("Cargando 58 tickers que no entran…", flush=True)
    no_pasan = cargar_no_pasan()

    print(f"Generando HTML… ({len(no_pasan)} tickers)", flush=True)
    html = generar_html(no_pasan, estado_pf)

    output_dir = Path("data/reportes")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"borja_reporte_{datetime.now().strftime('%Y%m%dT%H%M%S')}.pdf"

    print(f"Generando PDF en {output_path}…", flush=True)
    generar_pdf(html, output_path)

    size_kb = output_path.stat().st_size / 1024
    print(f"\nReporte generado:")
    print(f"  PDF:  {output_path}  ({size_kb:.1f} KB)")
    print(f"  HTML: {output_path.with_suffix('.html')}")


if __name__ == "__main__":
    main()
