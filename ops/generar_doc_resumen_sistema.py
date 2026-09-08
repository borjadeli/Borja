"""Genera un .docx con el resumen ejecutivo del sistema BORJA.

Parte 1: Reglas y criterios de conformación del Portfolio (estado actual).
Parte 2: Resumen completo de la plataforma (agentes, jobs, endpoints, UI).

Output: data/reportes/borja_resumen_sistema_<timestamp>.docx
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Cm, Pt, RGBColor


NAVY = RGBColor(0x1E, 0x3A, 0x8A)
ACCENT = RGBColor(0xD9, 0x77, 0x06)
SLATE_700 = RGBColor(0x33, 0x41, 0x55)
SLATE_500 = RGBColor(0x64, 0x74, 0x8B)
EMERALD = RGBColor(0x05, 0x96, 0x69)


def _shade_cell(cell, fill_hex: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill_hex)
    tc_pr.append(shd)


def _set_cell_borders(cell) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        b = OxmlElement(f"w:{edge}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), "4")
        b.set(qn("w:color"), "CBD5E1")
        borders.append(b)
    tc_pr.append(borders)


def add_table(doc, headers: list[str], rows: list[list[str]], col_widths_cm: list[float] | None = None) -> None:
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.alignment = WD_ALIGN_PARAGRAPH.LEFT

    # Header row
    hdr = table.rows[0]
    for i, h in enumerate(headers):
        c = hdr.cells[i]
        c.text = ""
        p = c.paragraphs[0]
        run = p.add_run(h)
        run.bold = True
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _shade_cell(c, "1E3A8A")
        _set_cell_borders(c)
        c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    # Body rows
    for r_idx, row in enumerate(rows):
        tr = table.rows[r_idx + 1]
        fill = "F8FAFC" if r_idx % 2 == 0 else "FFFFFF"
        for i, val in enumerate(row):
            c = tr.cells[i]
            c.text = ""
            p = c.paragraphs[0]
            run = p.add_run(str(val))
            run.font.size = Pt(9)
            _shade_cell(c, fill)
            _set_cell_borders(c)
            c.vertical_alignment = WD_ALIGN_VERTICAL.TOP

    if col_widths_cm:
        for row in table.rows:
            for i, w in enumerate(col_widths_cm):
                if i < len(row.cells):
                    row.cells[i].width = Cm(w)


def add_h1(doc, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(8)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(20)
    run.font.color.rgb = NAVY
    run.font.name = "Calibri"


def add_h2(doc, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(15)
    run.font.color.rgb = NAVY


def add_h3(doc, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(12)
    run.font.color.rgb = SLATE_700


def add_p(doc, text: str, italic: bool = False, color: RGBColor | None = None, size: int = 10) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.font.color.rgb = color or SLATE_700
    if italic:
        run.italic = True


def add_bullet(doc, text: str, level: int = 0) -> None:
    p = doc.add_paragraph(style="List Bullet" if level == 0 else "List Bullet 2")
    run = p.add_run(text)
    run.font.size = Pt(10)
    run.font.color.rgb = SLATE_700


def add_label_value(doc, label: str, value: str) -> None:
    p = doc.add_paragraph()
    r1 = p.add_run(label + ": ")
    r1.bold = True
    r1.font.size = Pt(10)
    r1.font.color.rgb = NAVY
    r2 = p.add_run(value)
    r2.font.size = Pt(10)
    r2.font.color.rgb = SLATE_700


def build_doc() -> Document:
    doc = Document()

    # Page setup
    for section in doc.sections:
        section.top_margin = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.left_margin = Cm(2.2)
        section.right_margin = Cm(2.2)

    # Default font
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10)

    # ============================================================
    # CARÁTULA
    # ============================================================
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(80)
    r = p.add_run("BORJA")
    r.bold = True
    r.font.size = Pt(48)
    r.font.color.rgb = NAVY

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Sistema Quant — Small/Mid Caps en Industrias del Futuro")
    r.italic = True
    r.font.size = Pt(13)
    r.font.color.rgb = SLATE_500

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(120)
    r = p.add_run("Resumen Ejecutivo del Sistema")
    r.bold = True
    r.font.size = Pt(18)
    r.font.color.rgb = SLATE_700

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Reglas, Criterios de Portfolio y Arquitectura de la Plataforma")
    r.font.size = Pt(11)
    r.font.color.rgb = SLATE_500

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(160)
    r = p.add_run(f"Versión vigente · {datetime.now().strftime('%Y-%m-%d')}")
    r.font.size = Pt(10)
    r.font.color.rgb = SLATE_500

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Documento generado a partir del estado actual del código (no de la spec)")
    r.italic = True
    r.font.size = Pt(9)
    r.font.color.rgb = SLATE_500

    doc.add_page_break()

    # ============================================================
    # PARTE 1 — REGLAS DE PORTFOLIO
    # ============================================================
    add_h1(doc, "Parte 1 · Reglas y Criterios de Conformación del Portfolio")

    add_p(doc,
        "Este capítulo describe el conjunto completo de reglas deterministas que el sistema "
        "aplica para decidir qué títulos integran el portfolio, en qué tamaño, y cuándo "
        "aumentar, mantener, reducir o salir. Toda la lógica es auditable: el LLM contribuye "
        "al análisis cualitativo, pero las decisiones de capital se toman con código.",
        italic=True, color=SLATE_500)

    # ---- 1.1 Capacidad de cartera y concentración ----
    add_h2(doc, "1.1 · Capacidad de Cartera y Concentración")

    add_p(doc,
        "Estos parámetros definen cuántas posiciones admite el sistema y cómo limita "
        "concentración en un mismo sector o driver macro. Fueron actualizados el 2026-05-04 "
        "para ampliar la cartera.")

    add_table(doc,
        headers=["Parámetro", "Valor", "Descripción"],
        rows=[
            ["SLOT_PORTFOLIO_MAX", "10", "Máximo de posiciones formales en Portfolio_Activo (antes 5)."],
            ["SLOT_BUCKET_MAX", "1", "Bucket exploratorio coexistente."],
            ["MAX_POR_SECTOR", "3", "Máximo de posiciones por sector individual (antes 2)."],
            ["MAX_POR_DRIVER", "3", "Máximo por cluster_driver macro compartido (v4.2 Regla 3 ampliada — ej. 'capex_AI' agrupa AI infra + Power Gen)."],
            ["EXPOSICION_PISO_PCT", "80%", "Piso de exposición vigente (cash libre permitido ≤20%). Bajo el piso, las recomendaciones de 'entrar' se etiquetan prioridad ALTA."],
        ],
        col_widths_cm=[5.0, 2.0, 9.5])

    # ---- 1.2 Score y umbrales de entrada ----
    add_h2(doc, "1.2 · Score y Umbrales de Entrada")

    add_p(doc,
        "El score ponderado de cada ficha (0-10) sintetiza diez criterios de análisis. "
        "Para entrar al Portfolio formal el score debe superar un piso calibrado empíricamente.")

    add_table(doc,
        headers=["Parámetro", "Valor", "Descripción"],
        rows=[
            ["SCORE_MIN_ENTRADA", "6.0",
             "Umbral mínimo para acción 'entrar'. Calibrado tras backtest 2026-04-20 con Opus 4.7: "
             "winners reales puntúan 4.8-6.3, losers <3.6. Score ≥6.0 aísla winners claros."],
            ["Banda 5.5-5.99", "—", "Zona 'interesante con gap' → estado WL_Activa."],
            ["Banda 5.0-5.49", "—", "Borderline → estado WL_Seguimiento."],
            ["Score < 5.0", "—", "Universo (no candidato a Portfolio)."],
        ],
        col_widths_cm=[4.5, 2.0, 10.0])

    # ---- 1.3 Asimetría dinámica ----
    add_h2(doc, "1.3 · Asimetría R/R Dinámica por Momentum Sectorial")

    add_p(doc,
        "La asimetría se computa al precio actual: (bull_case − precio) / (precio − bear_case). "
        "El umbral mínimo de asimetría requerido para entrar varía con el momentum sectorial — "
        "mercados en momentum favorable exigen menos margen, mercados sobrecalentados exigen más.")

    add_table(doc,
        headers=["Momentum Sectorial (v4.2)", "Asimetría mínima", "Comportamiento"],
        rows=[
            ["Favorable", "≥ 2.0x", "Entrada permitida con asimetría amplia."],
            ["Neutral", "≥ 2.5x", "Exige más margen — mercado en transición."],
            ["Desfavorable", "—", "No entrar bajo ningún umbral. Mantener posiciones existentes con tesis intacta."],
            ["null (sin clasificar)", "≥ 2.0x", "Default conservador."],
        ],
        col_widths_cm=[5.0, 3.5, 8.0])

    add_p(doc,
        "Vocabulario legacy (pre_rally / rally_temprano / rally_maduro / agotamiento) se mantiene "
        "mapeado para retro-compatibilidad mientras se migran scheduler y UI. La asimetría "
        "<0.5x sobre una posición vigente dispara rotación (ROTATION_UMBRAL_SALIDA = 0.5).",
        italic=True, color=SLATE_500, size=9)

    # ---- 1.4 Las 10 acciones ----
    add_h2(doc, "1.4 · Acciones Posibles del Agente Portfolio")

    add_table(doc,
        headers=["Acción", "Cuándo se emite"],
        rows=[
            ["entrar", "Score ≥6, asimetría ≥ umbral, slots y concentración OK, checklist completo, sin claims centrales con confidence Baja, CRR ≤ Medio."],
            ["aumentar", "Posición abierta + tesis intacta + asimetría ≥ 3.0x + piramidación disponible + red flags <2."],
            ["piramidacion", "Variante explícita de aumento: solo si piramidacion_disponible=True y momentum no es Desfavorable con convicción Alta."],
            ["bucket", "Tesis exploratoria que aún no pasa Portfolio formal. Slot único. Tamaño reducido."],
            ["mantener", "Default cuando no hay catalizador de cambio."],
            ["reducir", "Trim parcial — usado bajo Convicción Alta + Momentum Desfavorable (no aumentar más)."],
            ["salir", "Kill switch (red_flags ≥ 3) o tesis fundamentalmente rota."],
            ["wl_prioritaria", "Score alto pero algún chequeo bloquea entrada (asimetría, concentración, c#3 Baja, etc.)."],
            ["cash_preventivo", "Defensa macro — no fuerza ventas pero frena nuevos deploys."],
            ["rotar", "Asimetría < 0.5x o tesis no intacta + score <6. Cierra posición, libera slot."],
        ],
        col_widths_cm=[3.0, 13.5])

    # ---- 1.5 Algoritmo de entrada ----
    add_h2(doc, "1.5 · Algoritmo de Evaluación de Entrada")

    add_p(doc,
        "Se aplica a fichas con estado WL_Prioritaria. Los chequeos se ejecutan en este orden; "
        "el primer fallo bloquea con justificación trazable. Si todos pasan, la acción es 'entrar'.")

    add_table(doc,
        headers=["#", "Chequeo", "Bloqueo si"],
        rows=[
            ["1", "Score mínimo", "score_vigente < 6.0 → mantener (no entra)"],
            ["2", "Checklist de entrada", "Falta cualquier ítem (invalidation_triggers, plan_salida, tipo_catalizador, management_track_record, liquidez_suficiente, nivel_r) → wl_prioritaria"],
            ["3", "Asimetría dinámica", "asimetría < umbral según momentum (1.3) → wl_prioritaria"],
            ["4", "Capital Raise Risk", "CRR=Crítico → eliminar; CRR=Alto → solo Bucket; CRR=Medio → multiplicador 0.85; CRR=Bajo → 1.00"],
            ["5", "Slots Portfolio", "slots ≥ SLOT_PORTFOLIO_MAX (10)"],
            ["6", "Concentración sectorial", "≥ MAX_POR_SECTOR (3) en el mismo sector"],
            ["7", "Concentración driver", "≥ MAX_POR_DRIVER (3) en el mismo cluster_driver"],
            ["8", "Confidence claims centrales", "Cualquier criterio en {1, 2, 3, 4, 6} con confidence='Baja' (v4.2 sec 8) → wl_prioritaria"],
            ["9", "Piso de exposición (post-decisión)", "Si acción=entrar y exposición<80% → marcar prioridad_capital='alta'"],
        ],
        col_widths_cm=[1.0, 4.5, 11.0])

    # ---- 1.6 Algoritmo de rotación ----
    add_h2(doc, "1.6 · Algoritmo de Rotación / Mantenimiento")

    add_p(doc,
        "Se aplica a fichas en Portfolio_Activo y Bucket_Exploratorio. Decide si la posición "
        "se mantiene, aumenta, reduce, rota o sale. El orden importa — primer match gana.")

    add_table(doc,
        headers=["#", "Condición", "Acción"],
        rows=[
            ["1", "red_flags_count ≥ 3", "salir (kill switch — alerta urgente)"],
            ["2", "asimetría_vigente < 0.5x", "rotar"],
            ["3", "asimetría 0.5-1.0x con umbral ≥ 1.0x", "mantener (sin aumentar)"],
            ["4", "score < 6 y tesis NO intacta", "rotar"],
            ["5", "score < 6 pero tesis intacta", "mantener (doc 04 sec 5 — no rotar por score leve con tesis sana)"],
            ["6", "tesis intacta + asimetría ≥ 3.0x + piramidación disponible + red_flags <2", "piramidacion (excepto bloqueo v4.2 abajo)"],
            ["7", "(bloqueo v4.2) Convicción Alta + Momentum Desfavorable", "mantener (aumentos prohibidos — sizing capado al 50% del techo R)"],
            ["8", "Default", "mantener"],
        ],
        col_widths_cm=[1.0, 9.0, 6.5])

    add_h3(doc, "Condiciones de 'tesis intacta' (5 verificaciones)")
    add_bullet(doc, "red_flags_count NO aumentó respecto al snapshot anterior.")
    add_bullet(doc, "Score NO cayó ≥1.5 puntos en la última evaluación (proxy de revenue/guidance no recortado >20%).")
    add_bullet(doc, "Catalizador 'necesario' NO falló (fecha vigente o ya ocurrió con impacto).")
    add_bullet(doc, "Sin selling atípico de management (Form 4 — Sprint 3 lo automatiza).")
    add_bullet(doc, "Momentum sectorial ≠ Desfavorable / agotamiento (legacy).")

    # ---- 1.7 Sizing ----
    add_h2(doc, "1.7 · Sizing Efectivo")

    add_p(doc,
        "Fórmula: Sizing = TechoR(score, nivel_r) × Matriz(convicción × momentum) × Multiplicador 'ante la duda' × CRR_Multiplier.")

    add_h3(doc, "Techo R por Score y Nivel R (% del capital)")
    add_table(doc,
        headers=["Nivel R", "Score 10", "Score 9", "Score 8", "Score 7", "Score 6"],
        rows=[
            ["R1", "15", "15", "12", "10", "7"],
            ["R2", "12", "12", "10", "8", "5"],
            ["R3", "10", "10", "7", "5", "3"],
            ["R4", "7", "7", "5", "—", "—"],
        ],
        col_widths_cm=[2.5, 2.5, 2.5, 2.5, 2.5, 2.5])
    add_p(doc,
        "Score < 6 → no entra. Score ≥ 9.5 → bucket 10. Score 6.0-6.99 → bucket 6, etc. "
        "R4 con score < 8 → no entra (no hay celda).",
        italic=True, color=SLATE_500, size=9)

    add_h3(doc, "Matriz Convicción × Momentum (v4.2 doc 04 tabla 9)")
    add_table(doc,
        headers=["Convicción / Momentum", "Favorable", "Neutral", "Desfavorable"],
        rows=[
            ["Alta", "1.00", "0.85", "0.50 (alerta — sin aumentar)"],
            ["Media-Alta", "0.85", "0.70", "— (no entrar)"],
            ["Media", "0.70", "0.50", "— (rotar existentes)"],
        ],
        col_widths_cm=[4.0, 3.5, 3.5, 4.5])

    add_h3(doc, "Multiplicador 'Ante la Duda'")
    add_p(doc,
        "0.7 si hay duda documentada (ej. ítem del checklist resuelto a medias, gap de datos relevante). "
        "1.0 si no hay duda explícita.")

    add_h3(doc, "Multiplicador por Capital Raise Risk")
    add_table(doc,
        headers=["CRR", "Multiplicador", "Implicancia"],
        rows=[
            ["Bajo", "1.00", "Default."],
            ["Medio", "0.85", "Aplica descuento. Entrada permitida."],
            ["Alto", "0.70", "Bloquea Portfolio formal — solo Bucket o eliminar."],
            ["Crítico", "0.50", "Eliminada del universo automáticamente (fail condition)."],
        ],
        col_widths_cm=[2.5, 3.0, 10.5])

    # ---- 1.8 Capital Raise Risk ----
    add_h2(doc, "1.8 · Capital Raise Risk (CRR)")

    add_p(doc,
        "Función determinista que clasifica la solidez de capital de la empresa para sostener "
        "el plan de negocios sin diluir agresivamente. Se actualiza diariamente sobre todo "
        "el universo (small caps con revenue_ttm < $500M).")

    add_table(doc,
        headers=["Nivel", "Disparadores"],
        rows=[
            ["Crítico (eliminada)",
             "(a) Dilución 3y > 60% sin crecimiento (revenue YoY < 10%); o (b) runway < 6 meses (small cap)."],
            ["Alto (solo Bucket)",
             "(a) Dilución 3y > 40% sin crecimiento; (b) runway < 12 meses (small cap); o (c) ≥ 4 shelf registrations en 24 meses."],
            ["Medio",
             "(a) ≥ 3 shelf registrations en 24 meses; o (b) runway < 18 meses (small cap)."],
            ["Bajo (default)",
             "Ninguna de las anteriores."],
        ],
        col_widths_cm=[3.5, 13.0])

    add_p(doc,
        "Sanity check: si revenue_ttm > $500M, el sistema ignora señales de runway (FCF negativo "
        "en empresas grandes suele ser capex o working capital, no burn de subsistencia).",
        italic=True, color=SLATE_500, size=9)

    # ---- 1.9 Red flags ----
    add_h2(doc, "1.9 · Red Flags Detector (Governance)")

    add_p(doc,
        "Escanea continuamente eventos NOTICIA_MATERIAL e INSIDER_ACTIVITY contra patrones "
        "de gobierno corporativo deteriorado. Cap a 3 red flags activos por ficha.")

    add_table(doc,
        headers=["Categoría", "Patrón keyword (insensible a mayúsculas)"],
        rows=[
            ["ATM_DILUTION", "'at-the-market offering', 'ATM program', 'shelf offering', 'secondary offering', 'registered direct'."],
            ["GUIDANCE_CUT", "'lowered guidance', 'cut guidance', 'below consensus', 'misses estimates'."],
            ["AUDITOR_RESTATEMENT", "'auditor resigned', 'restatement', 'material weakness', 'CFO resigned', 'delay filing'."],
            ["SHORT_REPORT", "'short report', 'Hindenburg', 'Grizzly', 'Culper', 'Citron', 'Muddy Waters', 'Kerrisdale', 'Wolfpack'."],
            ["SEC_INVESTIGATION", "'SEC investigation', 'Wells notice', 'subpoena', 'securities fraud', 'class action'."],
            ["INSIDER_SELLING (v4.2 Enmienda C)", "'insider selling', 'CEO sells', 'insiders dump'. Overrideable con 10b5-1 / founder_50 / diversificacion_programada."],
        ],
        col_widths_cm=[5.0, 11.5])

    add_p(doc,
        "Escala: 1 flag = atención; 2 flags = no aumentar (alerta amarilla); 3 flags = kill switch "
        "(salir urgente, alerta email). Dedup por URL en ventana de 30 días.",
        size=9, color=SLATE_500)

    # ---- 1.10 Filtro antifraude ----
    add_h2(doc, "1.10 · Filtro Anti-Fraude (v4.2 sec 7)")

    add_p(doc,
        "Filtro determinista que marca violaciones (bloquean) y advertencias (flag manual). "
        "NO mueve estado automáticamente — el humano decide.")

    add_bullet(doc, "Empresa con < 2 años desde IPO (primer filing < 730 días) → VIOLACIÓN.")
    add_bullet(doc, "Más de 3 shelf registrations (S-1/S-3) en 24 meses → VIOLACIÓN.")
    add_bullet(doc, "Dilución > 40% en 3 años SIN crecimiento (YoY < 10%) → VIOLACIÓN.")
    add_bullet(doc, "ATM > 15% del float (proxy: 424B + shelf en 6m activo) → ADVERTENCIA.")
    add_bullet(doc, "Cambio de auditor > 1 vez en 5 años → flag manual (Fase 1).")
    add_bullet(doc, "Class actions abiertas (Stanford SCAC) → flag manual (Fase 1).")
    add_bullet(doc, "Going concern en 10-K → flag manual (Fase 1, leer notes).")

    # ---- 1.11 Los 10 criterios ----
    add_h2(doc, "1.11 · Los 10 Criterios de Análisis")

    add_p(doc,
        "El Analista (LLM Opus 4.7) puntúa cada criterio de 0 a 10 con confidence (Alta/Media/Baja) "
        "y nivel de fuente (jerarquía A-F). El score ponderado es:")

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Score = (C1×1.5 + C2×1.5 + C3×1.5 + C4 + C5 + C6 + C7 + C8 + C9 + C10) / 12.5")
    r.font.size = Pt(11)
    r.font.color.rgb = NAVY
    r.bold = True

    add_table(doc,
        headers=["#", "Criterio", "Peso", "Central", "Fuente principal"],
        rows=[
            ["1", "Oportunidad de crecimiento (TAM × trayectoria revenue)", "1.5", "Sí", "EDGAR + mapa sectorial"],
            ["2", "Captura de valor (margen, diferenciación, poder de mercado)", "1.5", "Sí", "EDGAR márgenes + noticias contratos"],
            ["3", "Catalizadores (eventos próximos con timing y magnitud)", "1.5", "Sí", "Noticias + earnings + Form 4"],
            ["4", "Moat competitivo (switching costs, network, brand)", "1.0", "Sí", "Mapa sectorial + noticias"],
            ["5", "Timing de mercado (momentum sectorial + catalysts)", "1.0", "No", "Sector + earnings"],
            ["6", "Calidad del revenue (recurrente, diversificación clientes)", "1.0", "Sí", "Guidance + contratos"],
            ["7", "Runway / salud de balance", "1.0", "No", "EDGAR balance"],
            ["8", "Riesgo de dilución (shelf + dilución histórica)", "1.0", "No", "EDGAR filings"],
            ["9", "Señales de mercado (insider activity, price action)", "1.0", "No", "Form 4 + Yahoo"],
            ["10", "Visibilidad earnings (track record sorpresas, guidance)", "1.0", "No", "Earnings histórico"],
        ],
        col_widths_cm=[1.0, 7.5, 1.5, 1.5, 5.0])

    add_h3(doc, "Confidence por Criterio (v4.2 Sprint B)")
    add_bullet(doc, "Alta — datos EDGAR + noticias directas + mapa sectorial alineados.")
    add_bullet(doc, "Media — datos parciales o inferences razonables.")
    add_bullet(doc, "Baja — datos insuficientes, proxies débiles, gaps detectados.")
    add_p(doc,
        "Si cualquier criterio en CRITERIOS_CENTRALES = {1, 2, 3, 4, 6} tiene confidence='Baja', "
        "el sistema bloquea Portfolio formal hasta que llegue evidencia A/B (v4.2 sec 8).",
        italic=True, color=SLATE_500, size=9)

    add_h3(doc, "Jerarquía de Fuentes (A-F)")
    add_table(doc,
        headers=["Nivel", "Tipo de fuente"],
        rows=[
            ["A", "EDGAR filings oficiales (10-K, 10-Q) — máxima fiabilidad."],
            ["B", "Company guidance oficial + transcripts de earnings calls."],
            ["C", "Reuters / WSJ / press release oficial."],
            ["D", "Reportes de analistas con consenso."],
            ["E", "RSS noticias secundarias."],
            ["F", "Proxies, estimaciones (Gartner, IDC, etc.)."],
        ],
        col_widths_cm=[2.0, 14.5])

    # ---- 1.12 Revalidación 30d ----
    add_h2(doc, "1.12 · Revalidación 30 Días")

    add_p(doc,
        "Cada 30 días desde la entrada (o última revalidación), el sistema obliga al humano a "
        "responder: ¿Seguís creyendo la tesis de {ticker}? Mitiga rubber-stamping.")

    add_p(doc,
        "Si la respuesta es NO, el endpoint exige cinco preguntas obligatorias antes de "
        "cerrar la posición:")
    add_bullet(doc, "p1 — ¿Qué aprendiste desde la entrada?")
    add_bullet(doc, "p2 — ¿Qué supuesto cambió?")
    add_bullet(doc, "p3 — ¿Es deterioro de tesis o solo precio?")
    add_bullet(doc, "p4 — ¿Qué anticipó el red team?")
    add_bullet(doc, "p5 — ¿Qué trigger esperabas que no se activó?")

    # ---- 1.13 Transición fase macro ----
    add_h2(doc, "1.13 · Transición Fase Macro (Defensiva)")

    add_p(doc,
        "Cuando el humano declara 'Fase 2 activada' (revisión trimestral de tesis macro), el "
        "sistema ejecuta un protocolo defensivo automático:")
    add_bullet(doc, "Revalidación forzada de todas las posiciones contra checklist Fase 2 (capex discrecional, sensibilidad a tasas, balance 18m).")
    add_bullet(doc, "Posiciones que no pasan: sizing al 50% inmediato, plan de salida acelerado.")
    add_bullet(doc, "Suspensión Bucket: la posición exploratoria pasa a WL_Activa.")
    add_bullet(doc, "Sube cash objetivo (no fuerza ventas, frena nuevos deploys).")
    add_bullet(doc, "Resumen completo en decision_journal.")

    # ---- 1.14 Decision Journal ----
    add_h2(doc, "1.14 · Decision Journal (Auditoría)")

    add_p(doc,
        "Log append-only de toda decisión de capital. Hace visible el patrón 'ratifica-todo' "
        "del humano, mitigando uno de los failure modes principales del sistema.")
    add_bullet(doc, "Cada acción de capital aprobada (entrar, aumentar, rotar, salir, etc.).")
    add_bullet(doc, "Cada rechazo de recomendación con motivo.")
    add_bullet(doc, "Revalidaciones 30d (sí/no + las 5 preguntas si aplica).")
    add_bullet(doc, "Transiciones fase macro.")
    add_p(doc,
        "Campos: timestamp, ticker, acción, decisor (humano/sistema), motivo, rec_id, "
        "evento_id, metadata, resultado_post (fill posterior).",
        size=9, color=SLATE_500)

    # ---- 1.15 Cuadro consolidado ----
    add_h2(doc, "1.15 · Cuadro Consolidado de Constantes")

    add_table(doc,
        headers=["Variable", "Valor", "Contexto"],
        rows=[
            ["SLOT_PORTFOLIO_MAX", "10", "Capacidad de cartera (2026-05-04)"],
            ["SLOT_BUCKET_MAX", "1", "Coexistencia"],
            ["MAX_POR_SECTOR", "3", "Concentración por sector (2026-05-04)"],
            ["MAX_POR_DRIVER", "3", "Concentración por cluster macro (v4.2)"],
            ["EXPOSICION_PISO_PCT", "80%", "Cash libre permitido ≤20%"],
            ["SCORE_MIN_ENTRADA", "6.0", "Calibración Opus 4.7"],
            ["ROTATION_UMBRAL_SALIDA", "0.5x", "Asimetría crítica vigente"],
            ["ASIMETRIA_MIN (Favorable)", "2.0x", "Momentum v4.2"],
            ["ASIMETRIA_MIN (Neutral)", "2.5x", "Momentum v4.2"],
            ["ASIMETRIA_MIN (Desfavorable)", "—", "No entrar"],
            ["CRR_MULTIPLIER (Bajo / Medio / Alto / Crítico)", "1.00 / 0.85 / 0.70 / 0.50", "v4.2 sec 4"],
            ["DILUTION_CRITICO / ALTO", "60% / 40% (sin growth)", "Capital Raise Risk"],
            ["RUNWAY_CRITICO / ALTO", "6m / 12m (small cap)", "Capital Raise Risk"],
            ["SHELF_FILTRACION_ALTO / MEDIO", "≥4 / ≥3 en 24m", "Capital Raise Risk"],
            ["UMBRAL_LIQUIDEZ_USD", "$1M / día", "Screener"],
            ["UMBRAL_DRIFT_SCORE", "1.5 puntos", "Detección deterioro tesis"],
            ["DIVISOR_SCORE", "12.5", "Normalización score ponderado"],
            ["RED_FLAGS_CAP", "3", "Kill switch a 3 flags"],
            ["CICLO_REVALIDACION_DIAS", "30", "Portfolio activo"],
            ["MOVIMIENTO_PRECIO_ALERTA", "30%", "Research precios"],
            ["EARNINGS_VENTANA", "±3 días", "Research earnings"],
            ["FORM4_LOOKBACK", "2 días", "Research insider"],
            ["COOLDOWN_DISPATCH", "5 días hábiles", "Anti-spam Dispatcher"],
            ["PASS_RATE_BACKTEST", "80%", "Gate go-live"],
        ],
        col_widths_cm=[6.5, 4.5, 5.5])

    doc.add_page_break()

    # ============================================================
    # PARTE 2 — PLATAFORMA
    # ============================================================
    add_h1(doc, "Parte 2 · Resumen de la Plataforma")

    add_p(doc,
        "BORJA es un sistema autónomo bajo systemd (puerto 8111) compuesto por agentes "
        "deterministas y agentes LLM, orquestados por un scheduler tipo cron. Toda la "
        "interacción humana ocurre vía dashboard web (Flask/FastAPI + Jinja2 + Tailwind + HTMX). "
        "La fuente de verdad es SQLite con 9+ tablas, backup automático diario.",
        italic=True, color=SLATE_500)

    # ---- 2.1 Stack ----
    add_h2(doc, "2.1 · Stack Tecnológico")
    add_table(doc,
        headers=["Capa", "Tecnología"],
        rows=[
            ["Backend", "Python 3.13 + FastAPI + SQLAlchemy 2.x"],
            ["Base de datos", "SQLite (WAL mode)"],
            ["LLM", "Anthropic Claude Opus 4.7 (1M context) — prompt caching activo"],
            ["Datos de mercado", "yfinance (curl_cffi impersonate=chrome) + EDGAR XBRL + RSS materiales"],
            ["Scheduler", "APScheduler (BackgroundScheduler, single-thread, timezone America/New_York)"],
            ["Frontend", "Jinja2 + Tailwind CSS + HTMX (sin SPA)"],
            ["Charts", "Apache ECharts (equity curve)"],
            ["Auth", "single-user admin con password hash"],
            ["Email", "SMTP (alertas + reporte semanal)"],
            ["Service", "systemd unit (borja.service) — port 8111, logs en /var/log/borja/"],
        ],
        col_widths_cm=[3.5, 13.0])

    # ---- 2.2 Agentes ----
    add_h2(doc, "2.2 · Agentes del Sistema")

    add_h3(doc, "Agentes deterministas (sin LLM)")
    add_table(doc,
        headers=["Agente", "Responsabilidad"],
        rows=[
            ["Portfolio", "Decisiones de capital: entrar / aumentar / rotar / salir / mantener / bucket / wl_prioritaria / cash_preventivo. Aplica todas las reglas de la Parte 1."],
            ["Juez", "Tres funciones: (a) Risk Monitor — supervisa posiciones activas; (b) Process Auditor — supervisa completeness de fichas; (c) Validar Recomendación — pre-aprueba antes del humano."],
            ["Capital Raise Risk", "Clasifica empresas en Bajo/Medio/Alto/Crítico según dilución, runway y shelf filings."],
            ["Red Flags Detector", "Escanea noticias e insider activity contra 6 categorías de gobierno deteriorado."],
            ["Filtro Anti-Fraude", "7 condiciones de filtrado del universo (IPO reciente, shelf abusivo, dilución sin growth, etc.)."],
            ["Dispatcher", "Routing de eventos a destinos (Analista, Portfolio, descartado) con 7 reglas y cooldown 5 días."],
            ["Research", "Cuatro monitores: precios (cada hora), earnings (diario), Form 4 insider (diario), noticias materiales (cada 4h)."],
            ["Evaluador Automático", "Corre Portfolio + Juez horario L-V 10:15-16:15 ET sin LLM. Auto-aprueba VALIDADAS en modo paper."],
            ["Mark-to-Market", "Trae precio actual cada 30 min L-V 10:00-16:00 ET para Portfolio + WLP + Bucket."],
            ["Portfolio Snapshot", "Persiste estado diario (P&L abierto + realizado) para equity curve histórica."],
            ["Equity Curve", "Computa curva diaria desde inception y comparación vs SPY normalizado."],
            ["Decision Journal", "Log append-only de toda decisión de capital (auditoría)."],
            ["Revalidación 30d", "Detecta posiciones con ciclo cumplido y crea evento + revalidación pendiente."],
            ["Transición Fase Macro", "Protocolo defensivo cuando humano declara Fase 2."],
            ["Reporte Semanal", "Compila KPIs + alertas + recomendaciones + costo LLM y envía email lunes 8:00 ET."],
        ],
        col_widths_cm=[4.0, 12.5])

    add_h3(doc, "Agentes con LLM (Claude Opus 4.7)")
    add_table(doc,
        headers=["Agente", "Cuándo se invoca", "Costo aprox."],
        rows=[
            ["Analista", "Análisis profundo de una ficha (10 criterios + scoring + bull/bear). Disparado por Dispatcher (eventos) o batch manual.", "~$0.40 / call"],
            ["Mapa Sectorial", "Genera/regenera el mapa estructural de un sector (cadena de valor, cuellos de botella). Vencimientos 14-45 días.", "~$0.50 / sector"],
            ["Discovery Hipótesis", "Cron domingos 20:00 ET. Genera 3-5 hipótesis con 1-5 candidatos cada una (sin scoring, sin entrada al sistema directo).", "~$1.50 / corrida"],
        ],
        col_widths_cm=[4.5, 9.5, 2.5])

    # ---- 2.3 Jobs ----
    add_h2(doc, "2.3 · Jobs Programados (Scheduler)")
    add_p(doc,
        "Timezone: America/New_York. Workers: 1 thread (evita lock contention SQLite). "
        "Coalesce: True (si se atrasa, ejecuta una sola vez).", size=9, color=SLATE_500)

    add_table(doc,
        headers=["Job", "Trigger", "Qué hace"],
        rows=[
            ["research_precios", "Cron L-V 9:30-15:30 ET, cada hora", "Detecta movimientos ≥30%; cooldown 24h."],
            ["research_earnings", "Diario 7:00 ET", "Earnings ±3d sobre Portfolio + WLP."],
            ["research_form4", "Diario 7:05 ET", "Form 4 CEO/CFO últimos 2 días."],
            ["research_noticias", "Cada 4h", "RSS materiales (excepto Eliminada/Suspendida)."],
            ["dispatcher_process_queue", "Cada 15 min", "Procesa eventos pendientes; aplica 7 reglas."],
            ["mtm_intraday", "L-V 10:00-16:00 ET, :00 y :30", "Mark-to-market + alerta entry_range."],
            ["evaluador_horario", "L-V 10:15-16:15 ET, :15", "Portfolio + Juez determinista; auto-aprueba VALIDADAS."],
            ["portfolio_snapshot", "L-V 16:30 ET", "Persiste fila histórica equity curve."],
            ["script_nocturno", "Diario 6:00 ET", "Entry ranges, triggers, deep research, sectores, mapas, limpieza."],
            ["revalidacion_30d", "Diario 7:30 ET", "Detecta ciclos 30d cumplidos."],
            ["discovery_semanal", "Domingos 20:00 ET", "Genera hipótesis y candidatos."],
            ["reporte_semanal", "Lunes 8:00 ET", "Email HTML con KPIs y alertas."],
            ["backup_sqlite", "Diario 4:00 AM UTC", "Backup automático de la base."],
        ],
        col_widths_cm=[3.5, 4.0, 9.0])

    # ---- 2.4 Ciclo nocturno ----
    add_h2(doc, "2.4 · Ciclo Nocturno (script_nocturno)")
    add_p(doc,
        "Diario 6:00 ET, sin LLM. Pasos en orden:")
    add_bullet(doc, "Entry ranges vencidos: WL_Prioritaria con vencimiento < hoy → WL_Activa + alerta.")
    add_bullet(doc, "Triggers sin evaluar: Portfolio/WLP con ultima_evaluacion_triggers > 7d.")
    add_bullet(doc, "Deep research vencido: fecha_proximo_deep_research < hoy.")
    add_bullet(doc, "Sectores sin actualizar: momentum no actualizado > 10 días.")
    add_bullet(doc, "Mapas sectoriales vencidos: dispara regeneración Claude + web search.")
    add_bullet(doc, "Limpieza: eventos procesados/descartados > 90 días.")
    add_bullet(doc, "Limpieza: tasks completados/fallidos > 30 días.")

    # ---- 2.5 Dispatcher ----
    add_h2(doc, "2.5 · Dispatcher — Routing de Eventos")
    add_p(doc,
        "Cada 15 minutos procesa la cola de eventos (NOTICIA_MATERIAL, EARNINGS_PROXIMOS, "
        "INSIDER_ACTIVITY, RED_FLAG, SHORT_REPORT, PRECIO_ALERTA) y los rutea al destino "
        "correcto según 7 reglas. Primer match gana.")

    add_table(doc,
        headers=["#", "Evento + Estado", "Destino", "Urgencia", "Inmune al cooldown"],
        rows=[
            ["R2", "SHORT_REPORT tier ≤ 2", "Analista + Juez", "Alta", "Sí"],
            ["R4", "RED_FLAG + Portfolio_Activo", "Portfolio + Juez", "Alta", "Sí"],
            ["R1", "EARNINGS + Portfolio/WLP", "Analista (earnings)", "Alta", "Sí"],
            ["R3", "NOTICIA_MATERIAL binaria + Portfolio/WLP", "Analista (urgente)", "Alta", "Sí"],
            ["R5", "NOTICIA_MATERIAL no-binaria + Portfolio", "Portfolio", "Media", "No"],
            ["R6", "NOTICIA_MATERIAL + WL_Prioritaria", "Analista (alerta)", "Media", "No"],
            ["R7", "Default", "Descartado", "—", "—"],
        ],
        col_widths_cm=[1.0, 5.5, 3.5, 2.0, 4.5])

    add_p(doc,
        "Cooldown anti-spam: si el mismo ticker tuvo dispatch material en los últimos 5 días "
        "hábiles, eventos no-críticos se descartan. Excepciones: SHORT_REPORT, RED_FLAG, "
        "EARNINGS, NOTICIA binaria.",
        size=9, color=SLATE_500)

    # ---- 2.6 Pantallas ----
    add_h2(doc, "2.6 · Pantallas del Dashboard")

    add_table(doc,
        headers=["Plantilla", "Para qué sirve"],
        rows=[
            ["dashboard.html", "Panel principal: KPIs (capital, P&L, exposición, slots), recomendaciones pendientes, posiciones activas, alertas risk, equity curve vs SPY."],
            ["universo.html", "Listado completo de fichas con filtros por sector, estado y score."],
            ["ficha.html", "Detalle individual: scores por criterio, bull/bear, triggers, plan de salida, cambios de score, eventos relacionados."],
            ["sectores.html", "Momentum sectorial, prioridad, horizonte, performance tracker."],
            ["sector_detalle.html", "Mapa estructural, cluster_driver, composición portfolio por sector."],
            ["evaluate.html", "Interfaz para correr Portfolio + Juez manualmente y revisar recomendaciones."],
            ["eventos.html", "Cola de eventos del Research, filtrable por tipo, urgencia y ticker."],
            ["discovery.html", "Hipótesis semanales y candidatos, investigación manual."],
            ["backtest.html", "Ejecución y resultados de backtests (mock vs real)."],
            ["costos.html", "Tracking de gasto LLM mensual, por ticker, trending."],
            ["reporte_semanal.html (email)", "Compilación ejecutiva semanal — solo template para email lunes."],
            ["alert_*.html (emails)", "Templates de alertas: kill_switch, red_flags, bucket_stop_loss."],
        ],
        col_widths_cm=[4.5, 12.0])

    # ---- 2.7 Endpoints API ----
    add_h2(doc, "2.7 · Endpoints API Principales")

    add_h3(doc, "Portfolio y Recomendaciones")
    add_bullet(doc, "GET  /api/recomendaciones — lista con filtros estado/ticker.")
    add_bullet(doc, "POST /portfolio/evaluar/{ticker} — corre Portfolio + Juez manual.")
    add_bullet(doc, "POST /aprobar/{rec_id} — aprueba (persiste sizing + precio entrada).")
    add_bullet(doc, "POST /rechazar/{rec_id} — rechaza con motivo.")

    add_h3(doc, "Analista")
    add_bullet(doc, "POST /analizar/{ticker} — dispara Analista en background (retorna task_id).")
    add_bullet(doc, "GET  /task/{task_id} — polling de progreso.")

    add_h3(doc, "Universo y Sectores")
    add_bullet(doc, "GET /api/universo — lista todas las fichas.")
    add_bullet(doc, "GET /api/sectores — lista sectores con momentum y prioridad.")
    add_bullet(doc, "GET /macro — tesis macro activa.")

    add_h3(doc, "Insider Override (v4.2 Enmienda C)")
    add_bullet(doc, "POST /api/fichas/{ticker}/insider-override — marca overrides (10b5-1, founder_50, diversificacion_programada).")
    add_bullet(doc, "DELETE /api/fichas/{ticker}/insider-override — limpia overrides.")

    add_h3(doc, "Peer Groups y Bucket Mecánico")
    add_bullet(doc, "GET / POST /api/peer-groups/{ticker}.")
    add_bullet(doc, "GET /api/precio-base/{ticker}.")

    add_h3(doc, "Equity Curve y Snapshots")
    add_bullet(doc, "GET /api/equity-curve-vs-spy — datos diarios para chart ECharts.")
    add_bullet(doc, "POST /api/equity-curve/backfill — regenera la curva desde inception.")

    add_h3(doc, "Panic / Sistema")
    add_bullet(doc, "POST /panic/pausar — frena scheduler y marca recs pendientes como cuestionadas.")
    add_bullet(doc, "POST /panic/reanudar — reactiva scheduler.")
    add_bullet(doc, "GET  /health — verifica DB + APIs externas.")

    # ---- 2.8 Backtest ----
    add_h2(doc, "2.8 · Backtest (Gate Pre Go-Live)")

    add_p(doc,
        "Validación obligatoria antes de poner capital real. Dataset: 10 empresas (5 winners + 5 losers).")

    add_table(doc,
        headers=["Modo", "Costo", "Para qué"],
        rows=[
            ["mock=True", "$0", "CI / regresión rápida con scores precargados."],
            ["mock=False", "~$3.50", "Ejecuta Analista real con Claude Opus 4.7."],
            ["reuse_persisted=True", "$0", "Lee scores ya persistidos en fichas."],
        ],
        col_widths_cm=[5.0, 2.5, 9.0])

    add_p(doc, "Criterio go-live:")
    add_bullet(doc, "Pass rate ≥ 80% (8/10).")
    add_bullet(doc, "≥ 4/5 winners correctamente identificados.")
    add_bullet(doc, "≥ 4/5 losers correctamente rechazados.")

    # ---- 2.9 Estados de ficha ----
    add_h2(doc, "2.9 · Estados de Ficha (Lifecycle)")
    add_table(doc,
        headers=["Estado", "Significado"],
        rows=[
            ["Universo", "Detectada por screener; aún no analizada en profundidad."],
            ["Candidata", "Analizada — score < 5.0; no avanza salvo cambio material."],
            ["WL_Seguimiento", "Score 5.0-5.49; borderline."],
            ["WL_Activa", "Score 5.5-5.99; interesante con gap."],
            ["WL_Prioritaria", "Score ≥ 6.0; candidata directa a entrada."],
            ["Portfolio_Activo", "Posición vigente con sizing comprometido."],
            ["Bucket_Exploratorio", "Tesis exploratoria con sizing reducido (slot único)."],
            ["Eliminada", "Removida del universo (CRR Crítico, fail antifraude, etc.)."],
            ["Suspendida", "Pausada por humano; sin actividad de Research."],
        ],
        col_widths_cm=[5.0, 11.5])

    # ---- 2.10 Failure modes ----
    add_h2(doc, "2.10 · Failure Modes Mitigados")
    add_p(doc, "El sistema fue diseñado teniendo presente tres failure modes principales:")
    add_bullet(doc, "Sobre-confianza del LLM en datos parciales — mitigado por jerarquía de fuentes A-F y bloqueo de Portfolio si claims centrales tienen confidence Baja.")
    add_bullet(doc, "Rubber-stamping del humano (ratifica todo automáticamente) — mitigado por Decision Journal append-only y revalidación 30d con 5 preguntas obligatorias para salir.")
    add_bullet(doc, "Drift gradual de la cartera respecto a la tesis macro — mitigado por Transición Fase Macro defensiva con checklist Fase 2 obligatorio.")

    # ---- 2.11 Notas y deprecaciones ----
    add_h2(doc, "2.11 · Notas, Limitaciones y Pendientes")
    add_bullet(doc, "(legacy) El vocabulario de momentum 4 estados (pre_rally / rally_temprano / rally_maduro / agotamiento) sigue mapeado al v4.2 (Favorable / Neutral / Desfavorable) por compatibilidad — pendiente migración total de scheduler y UI.")
    add_bullet(doc, "(Fase 1) Form 4 detallado (montos insider buy/sell), auditor changes y class actions están en flag manual — Sprint 3 los automatiza.")
    add_bullet(doc, "(Fase 2) FMP transcripts para guidance / backlog cuantificado y analyst ratings consenso quedan pendientes — Anthropic-only por ahora.")
    add_bullet(doc, "Drift consciente: los documentos canónicos en init_docs/04_sistema_inversion_v4_2_mvp.docx NO se actualizaron con el cambio del 2026-05-04 (slots/sector/driver). El cambio existe solo en código.")

    # ============================================================
    # Pie
    # ============================================================
    doc.add_page_break()
    add_h2(doc, "Anexo · Glosario")
    add_table(doc,
        headers=["Término", "Significado"],
        rows=[
            ["Asimetría R/R", "(bull − precio) / (precio − bear). Mide cuánto upside teórico vs downside."],
            ["Bucket exploratorio", "Posición de tesis no-confirmada con sizing reducido. Slot único."],
            ["Capacidad máxima teórica", "Sizing% que el sistema admitiría dado score, nivel R, momentum, convicción y CRR."],
            ["Cluster driver", "Macro driver compartido entre sectores (ej. capex_AI agrupa AI infra + Power Generation)."],
            ["Confidence (Alta/Media/Baja)", "Nivel de robustez del análisis del LLM en cada criterio (v4.2 Sprint B)."],
            ["CRR", "Capital Raise Risk: clasificación determinista de la solidez de capital de la empresa."],
            ["Drift de score", "Caída ≥ 1.5 puntos en una evaluación reciente — proxy de revenue/guidance recortado."],
            ["Failure modes", "Tres riesgos sistémicos: sobre-confianza LLM, rubber-stamping humano, drift de cartera."],
            ["Jerarquía A-F", "Orden de fiabilidad de fuentes (A=EDGAR oficial, F=proxy/estimación)."],
            ["Kill switch", "Salida urgente automática cuando red_flags = 3."],
            ["Momentum sectorial", "Estado del sector: Favorable / Neutral / Desfavorable (v4.2)."],
            ["Nivel R", "Riesgo intrínseco de la posición (R1-R4). Determina techo de sizing."],
            ["Piramidación", "Aumentar sizing tras un primer impulso favorable de la tesis."],
            ["Tesis intacta", "Cinco verificaciones (red_flags, score, catalizadores, insider, momentum) que justifican mantener una posición pese a deterioro de score."],
            ["Umbral rotación", "Asimetría < 0.5x dispara rotar (cerrar y liberar slot)."],
            ["WL", "Watchlist (Activa / Seguimiento / Prioritaria)."],
        ],
        col_widths_cm=[4.0, 12.5])

    return doc


def main() -> int:
    doc = build_doc()
    out_dir = Path("data/reportes")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    out_path = out_dir / f"borja_resumen_sistema_{ts}.docx"
    doc.save(str(out_path))
    print(f"Documento generado: {out_path}")
    print(f"Tamaño: {out_path.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
