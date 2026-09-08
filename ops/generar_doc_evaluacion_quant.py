"""Genera un .docx corporativo (Banking & Finance) con la EVALUACIÓN CUANTITATIVA
de las reglas de entrada y salida del núcleo determinista de BORJA (v3).

Auto-contenido para enviar al equipo de Quants: describe el sistema bajo revisión
(criterios exactos, leídos del código) + la evaluación de diseño (fortalezas,
debilidades priorizadas, recomendaciones por leverage).

Output: data/reportes/borja_evaluacion_quant_<timestamp>.docx
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

# ---- Paleta corporativa (consistente con generar_doc_resumen_sistema.py) ----
NAVY = RGBColor(0x1E, 0x3A, 0x8A)
ACCENT = RGBColor(0xD9, 0x77, 0x06)
SLATE_900 = RGBColor(0x0F, 0x17, 0x2A)
SLATE_700 = RGBColor(0x33, 0x41, 0x55)
SLATE_500 = RGBColor(0x64, 0x74, 0x8B)
EMERALD = RGBColor(0x05, 0x96, 0x69)
CRIMSON = RGBColor(0xB9, 0x1C, 0x1C)


def _shade_cell(cell, fill_hex: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill_hex)
    tc_pr.append(shd)


def _set_cell_borders(cell, color="CBD5E1", sz="4") -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        b = OxmlElement(f"w:{edge}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), sz)
        b.set(qn("w:color"), color)
        borders.append(b)
    tc_pr.append(borders)


def _cell_margins(cell, top=60, bottom=60, left=100, right=100) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    m = OxmlElement("w:tcMar")
    for edge, val in (("top", top), ("bottom", bottom), ("start", left), ("end", right)):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:w"), str(val))
        e.set(qn("w:type"), "dxa")
        m.append(e)
    tcPr.append(m)


def add_table(doc, headers, rows, col_widths_cm=None, header_fill="1E3A8A") -> None:
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.alignment = WD_ALIGN_PARAGRAPH.LEFT
    hdr = table.rows[0]
    for i, h in enumerate(headers):
        c = hdr.cells[i]
        c.text = ""
        run = c.paragraphs[0].add_run(h)
        run.bold = True
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _shade_cell(c, header_fill)
        _set_cell_borders(c)
        _cell_margins(c)
        c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    for r_idx, row in enumerate(rows):
        tr = table.rows[r_idx + 1]
        fill = "F1F5F9" if r_idx % 2 == 0 else "FFFFFF"
        for i, val in enumerate(row):
            c = tr.cells[i]
            c.text = ""
            run = c.paragraphs[0].add_run(str(val))
            run.font.size = Pt(9)
            run.font.color.rgb = SLATE_700
            _shade_cell(c, fill)
            _set_cell_borders(c)
            _cell_margins(c)
            c.vertical_alignment = WD_ALIGN_VERTICAL.TOP
    if col_widths_cm:
        for row in table.rows:
            for i, w in enumerate(col_widths_cm):
                if i < len(row.cells):
                    row.cells[i].width = Cm(w)


def add_rule(doc, color="D97706", space_before=2, space_after=8) -> None:
    """Regla horizontal fina (acento)."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    pPr = p._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "12")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), color)
    pbdr.append(bottom)
    pPr.append(pbdr)


def add_h1(doc, text, kicker=None) -> None:
    if kicker:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(16)
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(kicker.upper())
        r.bold = True
        r.font.size = Pt(9)
        r.font.color.rgb = ACCENT
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2 if kicker else 16)
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(19)
    run.font.color.rgb = NAVY
    add_rule(doc)


def add_h2(doc, text) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(13.5)
    run.font.color.rgb = NAVY


def add_h3(doc, text, color=None) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(9)
    p.paragraph_format.space_after = Pt(3)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(11.5)
    run.font.color.rgb = color or SLATE_900


def add_p(doc, text, italic=False, color=None, size=10, space_after=6) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.12
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.font.color.rgb = color or SLATE_700
    run.italic = italic


def add_bullet(doc, text, bold_lead=None) -> None:
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(3)
    if bold_lead:
        r0 = p.add_run(bold_lead)
        r0.bold = True
        r0.font.size = Pt(10)
        r0.font.color.rgb = NAVY
    run = p.add_run(text)
    run.font.size = Pt(10)
    run.font.color.rgb = SLATE_700


def add_callout(doc, title, body_paras, fill="F1F5F9", accent_hex="1E3A8A") -> None:
    table = doc.add_table(rows=1, cols=1)
    cell = table.rows[0].cells[0]
    _shade_cell(cell, fill)
    _cell_margins(cell, top=120, bottom=120, left=200, right=200)
    tcPr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for edge, sz, col in (("left", "24", accent_hex), ("top", "4", "E2E8F0"),
                          ("bottom", "4", "E2E8F0"), ("right", "4", "E2E8F0")):
        b = OxmlElement(f"w:{edge}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), sz)
        b.set(qn("w:color"), col)
        borders.append(b)
    tcPr.append(borders)
    p0 = cell.paragraphs[0]
    if title:
        r = p0.add_run(title)
        r.bold = True
        r.font.size = Pt(11)
        r.font.color.rgb = NAVY
    for i, txt in enumerate(body_paras):
        pp = cell.add_paragraph()
        pp.paragraph_format.line_spacing = 1.12
        pp.paragraph_format.space_before = Pt(4 if (title or i) else 0)
        r = pp.add_run(txt)
        r.font.size = Pt(10)
        r.font.color.rgb = SLATE_700
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def add_footer(doc) -> None:
    p = doc.sections[0].footer.paragraphs[0]
    p.text = ""
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("BORJA  ·  Confidencial — Uso Interno  ·  pág. ")
    r.font.size = Pt(8)
    r.font.color.rgb = SLATE_500
    run = p.add_run()
    for kind in ("begin", None, "end"):
        if kind:
            fld = OxmlElement("w:fldChar")
            fld.set(qn("w:fldCharType"), kind)
            run._r.append(fld)
        else:
            it = OxmlElement("w:instrText")
            it.set(qn("xml:space"), "preserve")
            it.text = "PAGE"
            run._r.append(it)
    run.font.size = Pt(8)
    run.font.color.rgb = SLATE_500


# =============================================================================
def build() -> Document:
    doc = Document()
    for s in doc.sections:
        s.top_margin = Cm(2.0)
        s.bottom_margin = Cm(2.0)
        s.left_margin = Cm(2.2)
        s.right_margin = Cm(2.2)
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10)
    add_footer(doc)

    # ---------------- CARÁTULA ----------------
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(90)
    r = p.add_run("BORJA")
    r.bold = True
    r.font.size = Pt(46)
    r.font.color.rgb = NAVY

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Núcleo Determinista · v3")
    r.italic = True
    r.font.size = Pt(13)
    r.font.color.rgb = SLATE_500

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(110)
    r = p.add_run("Revisión Cuantitativa de las\nReglas de Entrada y Salida")
    r.bold = True
    r.font.size = Pt(22)
    r.font.color.rgb = SLATE_900

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Evaluación de Diseño — Fortalezas, Riesgos y Plan de Ajustes")
    r.font.size = Pt(11)
    r.font.color.rgb = SLATE_500

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(150)
    for label, val in (("Destinatario", "Equipo de Quants"),
                       ("Fecha", datetime.now().strftime("%d de %B de %Y")),
                       ("Clasificación", "Confidencial — Uso Interno")):
        pp = doc.add_paragraph()
        pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r1 = pp.add_run(f"{label}:  ")
        r1.bold = True
        r1.font.size = Pt(10)
        r1.font.color.rgb = NAVY
        r2 = pp.add_run(val)
        r2.font.size = Pt(10)
        r2.font.color.rgb = SLATE_700

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(60)
    r = p.add_run("Documento elaborado a partir del estado actual del código (no de la especificación).")
    r.italic = True
    r.font.size = Pt(9)
    r.font.color.rgb = SLATE_500
    doc.add_page_break()

    # ---------------- 1. RESUMEN EJECUTIVO ----------------
    add_h1(doc, "Resumen Ejecutivo", kicker="Sección 1")
    add_callout(doc, "Veredicto", [
        "El esqueleto del sistema es sólido: su arquitectura es superior a la de la mayoría de "
        "los sistemas semi-profesionales. Pero todavía no constituye un sistema sólido en "
        "sentido cuantitativo.",
        "Cuatro razones lo explican: (1) no incorpora probabilidad en ninguna etapa — optimiza "
        "geometría de payoff, no valor esperado; (2) ningún umbral está calibrado contra "
        "resultados; (3) carece de un modelo de riesgo a nivel de cartera (correlación, factores, "
        "volatilidad); y (4) tal como está implementado hoy es materialmente más débil que como "
        "está diseñado, porque la lógica de salida sofisticada (vías 1 a 3) aún no está cableada.",
        "En una frase: huesos sólidos; sistema, todavía no. Lo que más lo frena no es ninguna "
        "regla individual — están razonablemente pensadas — sino la ausencia de probabilidad, la "
        "ausencia de validación empírica y las salidas inteligentes apagadas.",
    ])

    # ---------------- 2. SISTEMA BAJO REVISIÓN ----------------
    add_h1(doc, "Sistema Bajo Revisión", kicker="Sección 2")
    add_p(doc,
        "La decisión de capital es 100% determinista. El LLM aporta hechos fechados con fuente; "
        "una serie de tablas deterministas deciden — el LLM nunca asigna el resultado. El flujo de "
        "entrada compone: Arquetipo → Gate de evidencia → Mérito (Quality × Asimetría) → Hard Cap "
        "→ Selector (normalización relativa) → Sizing. La salida se resuelve por cinco vías con "
        "precedencia atómica.", italic=True, color=SLATE_500)

    add_h2(doc, "2.1 · Clasificación de Arquetipo")
    add_p(doc, "Sobre el revenue elegible (descomposición ASC 606; si un cliente concentra > 50%, "
               "o el top-2 > 66%, se resta el dominante salvo contrato en firme). Primer match gana:")
    add_table(doc,
        ["Condición", "Arquetipo"],
        [["Un evento no-comercial deja el equity con recuperación residual ~nula", "Binary"],
         ["Revenue elegible < $10M", "Pre-revenue"],
         ["$10M – $50M", "Tracción"],
         ["≥ $50M, crecimiento elegible ≥ 25%", "Growth"],
         ["≥ $50M, < 25%, FCF > 0", "Madura"],
         ["≥ $50M, < 25%, FCF < 0 (residuo)", "Tracción"]],
        col_widths_cm=[11.5, 5.0])

    add_h2(doc, "2.2 · Gate de Evidencia (pasa / no-pasa, sin compensación)")
    add_p(doc, "Checklist donde TODOS los ítems deben pasar. Cada ítem es un hecho con fuente "
               "mínima. Fallar P2 / T2 solo por distancia temporal → «todavía no» (watchlist), no rechazo.")
    add_table(doc,
        ["Bloque", "Exigencia"],
        [["U1 — Triggers (todos)", "2 a 4 triggers con forma completa (hecho + umbral + fecha + fuente); ≥1 de estructura de capital; ≥1 atado al hecho de entrada."],
         ["Madura", "M1: ≥1 hecho ocurrido vigente (no one-off)."],
         ["Growth", "G1: crecimiento orgánico ≥ 50% (con desglose orgánico vs M&A); G2: hecho de continuidad (backlog/RPO)."],
         ["Tracción", "T1: hecho comercial nuevo en ≤4 trimestres; T2: catalizador ≤18m con métrica."],
         ["Pre-revenue", "P1: contrato firmado / design-in económico / LOI económica (MOU no cuenta); P2: catalizador ≤12m con métrica y fecha congelada; P3: financiación-hasta-el-hito."],
         ["Binary", "B1: evidencia objetiva (no press release propio); B2: evento fechado + métrica binaria; B3: financiación firmada hasta después del evento."]],
        col_widths_cm=[3.8, 12.7])

    add_h2(doc, "2.3 · Mérito y Hard Cap")
    add_p(doc, "Quien pasa el gate recibe un mérito que lo ordena; el Hard Cap acota su tamaño.")
    add_bullet(doc, "Mérito = Quality (tier ordinal 1-4) × Asimetría.", bold_lead="Mérito.  ")
    add_bullet(doc, "(bull − precio) / (precio − bear). Si precio ≤ bear → no calculable → no entra.", bold_lead="Asimetría.  ")
    add_bullet(doc, "Por puntos (margen bruto, expansión, crecimiento orgánico, recurrencia, hechos comerciales, ventaja estructural): ≥6 → tier 4, ≥4 → 3, ≥2 → 2, resto → 1.", bold_lead="Quality.  ")
    add_bullet(doc, "min(cap por arquetipo × fragility, cap_CRR, 40% absoluto).", bold_lead="Hard Cap.  ")
    add_p(doc, "Tabla de caps por arquetipo × Fragility Score (techo de sizing, % de cartera):", space_after=4)
    add_table(doc,
        ["Arquetipo", "Frag 0", "Frag 1", "Frag 2", "Frag 3"],
        [["Madura", "40%", "33%", "25%", "13%"],
         ["Growth", "33%", "27%", "19%", "11%"],
         ["Tracción", "27%", "21%", "14%", "8%"],
         ["Pre-revenue", "22%", "17%", "12%", "7%"],
         ["Binary", "8%", "7%", "6%", "5%"]],
        col_widths_cm=[5.0, 2.875, 2.875, 2.875, 2.875])

    add_h2(doc, "2.4 · Despliegue (deploy)")
    add_p(doc, "Candidata con mérito → top-N por mérito (Selector, normalización relativa) → bruto "
               "normalizado ≥ 5% (piso) → entra a min(bruto, Hard Cap). Máximo 12 posiciones. "
               "Despliegue hacia 100% del capital, siendo el 70% un PISO (no un techo); el cash "
               "residual emerge de los caps. El tramo 70→100% se cubre comprando NOMBRES NUEVOS: la "
               "piramidación de posiciones existentes está desactivada por configuración del operador "
               "(2026-06-30), aunque la lógica queda disponible si se reactiva.")
    add_p(doc, "Nota: el ciclo diario opera sin LLM (lee hechos cacheados de la re-extracción "
               "semanal); el sizing de cada posición usa precio de entrada mezclado (promedio "
               "ponderado) al piramidar, para no inflar el P&L del incremento.",
               italic=True, color=SLATE_500, size=9)

    add_h2(doc, "2.5 · Criterios de Salida — cinco vías, precedencia atómica")
    add_p(doc, "Sin stop de precio. El score global y el momentum no disparan nada. "
               "Precedencia: Governance → CRR-crítico → Vía 1 → Vía 4 → Vía 5.")
    add_table(doc,
        ["Vía", "Disparador", "Umbral", "Acción"],
        [["3 · Governance", "Evento hard de integridad / red flags blandos", "1 hard  /  ≥3 soft", "Venta directa / salir urgente"],
         ["2 · CRR-crítico", "Deterioro financiero sobreviniente", "—", "Recomendar salir"],
         ["1 · Invalidación", "Trigger disparado o vencido, 2ª corrida de fecha, stop de progreso", "2 earnings sin hecho a favor (1 en frágiles)", "Re-gate (o venta si Candado B usado)"],
         ["4 · Asimetría", "Asimetría vigente al precio", "< 0.5 → salir;  < 1.0 → no aumentar", "Recomendar salir / no aumentar"],
         ["5 · Tamaño", "Peso vivo vs Hard Cap", "> Hard Cap × 1.25", "Recortar al Hard Cap"]],
        col_widths_cm=[2.8, 5.5, 4.7, 3.5])

    add_h2(doc, "2.6 · Estado de Implementación (lo vivo vs lo diseñado)")
    add_callout(doc, "Advertencia material para la lectura", [
        "En el executor en paper hoy solo están vivas las vías 4 (asimetría) y 5 (tamaño) — las de "
        "precio. Las vías 1, 2 y 3 (invalidación / stop de progreso, CRR sobreviniente, governance) "
        "tienen la lógica escrita, pero no reciben eventos: el pipeline Research/RedFlags aún no está "
        "cableado. La salida viva es, en la práctica, «vender si la asimetría baja de 0.5».",
        "Adicionalmente: la concentración por subsector (máx 2) y el cubo de fragilidad agregado (8%) "
        "existen como constantes / en el armador de cartera, pero el executor en paper no los verifica "
        "al entrar; y la piramidación no respeta aún la señal «no_aumentar» de la vía 4.",
    ], fill="FEF3F2", accent_hex="B91C1C")

    # ---------------- 3. FORTALEZAS ----------------
    add_h1(doc, "Fortalezas del Diseño", kicker="Sección 3")
    add_h3(doc, "1 · Separación estricta de motores (Quality / Asimetría / Fragility / CRR)", color=EMERALD)
    add_p(doc, "Lo mejor del diseño. El pecado más común de estos sistemas es el doble conteo — dejar "
               "que una valuación barata tape una insolvencia. Forzar Quality = solo negocio, CRR = "
               "balance como cap (no multiplicador), y Fragility = severidad del downside → cap, elimina "
               "el efecto halo.")
    add_h3(doc, "2 · El gate como pasa / no-pasa duro, sin compensación", color=EMERALD)
    add_p(doc, "El mejor antídoto contra la entrada por narrativa. Rechazar MOU/partnership como "
               "demanda, exigir contrato o design-in económico, y la prueba de financiación-hasta-el-hito "
               "que excluye shelf, ATM y «en negociación», es exactamente la disciplina que separa una "
               "tesis real de un pump en small-caps. Es la pieza más fuerte.")
    add_h3(doc, "3 · Asimetría recalculada al precio y anclada en hechos ocurridos", color=EMERALD)
    add_p(doc, "Primitiva limpia de R/R. Tiene una propiedad valiosa: una posición cuyo precio cae con "
               "tesis intacta ve subir su asimetría, lo que auto-corrige el sesgo de comprar caro / "
               "vender barato.")
    add_h3(doc, "4 · El LLM como traedor de hechos, con decisión determinista", color=EMERALD)
    add_p(doc, "Arquitectura auditable y reproducible: los fallos viven en hechos verificables, no en "
               "un juicio de caja negra.")

    # ---------------- 4. DEBILIDADES ----------------
    add_h1(doc, "Debilidades y Riesgos (priorizados)", kicker="Sección 4")

    add_h3(doc, "Riesgo 1 — No hay probabilidad en ninguna etapa: optimiza geometría de payoff, no valor esperado", color=CRIMSON)
    add_p(doc, "Quality «ordena, no es probabilidad»; Asimetría es R/R puro «sin probabilidad de que la "
               "tesis se cumpla»; Fragility es severidad. Lo único probabilístico es el gate, y es binario "
               "{0,1}. Consecuencia: entre todos los que pasan el gate, el de mayor asimetría rankea "
               "primero, aunque su bull sea el menos probable — una lotería 10x al 5% le gana a un 2x al "
               "80%. Es selección adversa hacia value traps: la asimetría altísima suele existir porque el "
               "mercado asigna baja probabilidad, y a veces tiene razón.")
    add_p(doc, "Y sin probabilidad que amortigüe, todo el ranking cuelga de dos números por nombre — bull "
               "y bear — estimados por el LLM, el input más blando del sistema. Bull/bear mal calibrados → "
               "mérito malo → cartera mala, sin ensemble que lo dampee. Es el riesgo oculto número uno.")

    add_h3(doc, "Riesgo 2 — Todo calibrado por afirmación, no por datos", color=CRIMSON)
    add_p(doc, "Los cortes de Quality, los caps de fragility, el umbral 0.5 de la vía 4, la banda de "
               "recorte 1.25 y los cortes de revenue de arquetipo están fijados a mano y declarados «primera "
               "aproximación, no validada». Ninguno fue backtesteado contra resultados. El sistema lleva ~6 "
               "días en paper con 8 posiciones y prácticamente cero salidas realizadas; cualquier "
               "outperformance observada es ruido estadístico sobre nombres de alta beta. Estado honesto: "
               "hipótesis bien razonadas, sin validar.")

    add_h3(doc, "Riesgo 3 — No hay modelo de riesgo a nivel de cartera", color=CRIMSON)
    add_p(doc, "Los Hard Caps acotan por nombre, pero falta la dimensión de cartera:")
    add_bullet(doc, "8 small-caps de «industrias del futuro» no son apuestas independientes: comparten beta small-cap, sensibilidad a tasas (duración larga), risk-on/off y el ciclo de capex de IA. Pueden ser una sola apuesta macro dimensionada como si estuviera diversificada — en risk-off caen juntas. El «máx 2/subsector» es un proxy crudo, no un modelo de factores.", bold_lead="Sin conciencia de correlación.  ")
    add_bullet(doc, "16% en un nombre de 30% de vol no es el mismo riesgo que 16% en uno de 90%; el sizing no normaliza por volatilidad.", bold_lead="Sin escalado por volatilidad.  ")
    add_bullet(doc, "No hay circuit-breaker de drawdown a nivel de cartera en el camino vivo.", bold_lead="Sin breaker agregado.  ")

    add_h3(doc, "Riesgo 4 — Tal como corre hoy es más débil que como está diseñado", color=CRIMSON)
    add_p(doc, "Con las vías 1 a 3 dormidas, una tesis puede romperse (guidance cortado, catalizador "
               "fallido, fraude, insider dumping, going-concern sobreviniente) y el sistema vivo no reacciona "
               "hasta que el precio ya cayó lo suficiente para hundir la asimetría — un stop lagging, basado "
               "en precio. La parte sofisticada de la salida es justo la apagada.")

    add_h3(doc, "Riesgo 5 — Observaciones puntuales de consistencia", color=CRIMSON)
    add_bullet(doc, "No hay piso de asimetría para entrar, pero la vía 4 vende en < 0.5 y marca «no aumentar» en < 1.0: se puede entrar a 0.6 y quedar a un tick de la venta. Entrada y salida no están alineadas en la misma banda.")
    add_bullet(doc, "Mérito = tier ordinal (1-4) × asimetría continua: multiplicar ordinal por cardinal es dimensionalmente dudoso y vuelve el ranking sensible a cortes arbitrarios; la resolución es gruesa (dos tier-4 de 6 y 10 puntos son idénticos).")
    add_bullet(doc, "El gate se «gana» por etiqueta del LLM (orgánico vs M&A, design-in económico vs técnico); sin segunda opinión viva, un borderline pasa o falla por una sola etiqueta.")
    add_bullet(doc, "No hay costo de transacción ni impacto de liquidez en el sizing: para small-caps, una posición grande en un nombre de bajo volumen tarda días en salir y mueve el precio. El paper lo esconde.")

    # ---------------- 5. RECOMENDACIONES ----------------
    add_h1(doc, "Recomendaciones (por leverage)", kicker="Sección 5")
    add_table(doc,
        ["#", "Recomendación", "Qué ataca"],
        [["1", "Introducir una dimensión de confianza / probabilidad graduada que pondere el mérito (mérito′ = confianza × Quality × Asimetría), derivada de fuerza del gate, nº de hechos independientes y calidad de fuente.", "Riesgo 1 — ausencia de probabilidad (el fix más profundo)."],
         ["2", "Harness de calibración de bull/bear: trackear realizado vs predicho. Si están sesgados, el edge es ilusorio.", "Fragilidad del input más blando; barato y de alto impacto."],
         ["3", "Capa de riesgo de cartera: cap de correlación / factor real, sizing consciente de volatilidad y circuit-breaker de drawdown.", "Riesgo 3 — concentración macro oculta."],
         ["4", "Cablear las vías 1, 2 y 3 al pipeline de eventos (Research/RedFlags).", "Riesgo 4 — la salida viva es solo precio (lagging)."],
         ["5", "Validar los umbrales con backtest / tracking antes de fijarlos como definitivos.", "Riesgo 2 — calibración por afirmación."]],
        col_widths_cm=[1.0, 9.8, 5.7])

    # ---------------- 6. CONCLUSIÓN ----------------
    add_h1(doc, "Conclusión", kicker="Sección 6")
    add_p(doc, "La arquitectura del núcleo es deliberada y, en lo conceptual, está por encima del promedio: "
               "la separación de motores y el gate de evidencia son piezas de calidad institucional. El "
               "trabajo pendiente para que sea un sistema robusto — no solo un diseño robusto — es de tres "
               "frentes: incorporar probabilidad al ranking, construir la capa de riesgo de cartera, y "
               "cerrar la brecha entre lo diseñado y lo que efectivamente corre (cablear las salidas y "
               "calibrar los umbrales con datos).")
    add_p(doc, "Prioridad sugerida para arrancar: cablear las salidas inteligentes (vías 1-3), por ser "
               "concreto y por tapar el mayor riesgo del sistema vivo, en paralelo con el harness de "
               "calibración de bull/bear, que es barato y ataca el riesgo número uno.", color=SLATE_900)

    # ---------------- APÉNDICE — AJUSTES CONCRETOS REGLA POR REGLA ----------------
    add_h1(doc, "Ajustes Concretos, Regla por Regla", kicker="Apéndice A")
    add_p(doc,
        "Las recomendaciones de la §5 son las palancas estratégicas. Este apéndice las baja a "
        "ajustes tácticos por regla — hipótesis a validar con tracking, no cambios validados. Cada "
        "uno es accionable sobre el código actual.", italic=True, color=SLATE_500)

    add_h3(doc, "A.1 · Reglas de entrada")
    add_table(doc,
        ["Regla (hoy)", "Ajuste sugerido", "Por qué"],
        [["Asimetría de entrada: sin piso", "Exigir asimetría ≥ 1.5–2.0x para entrar (margen sobre el umbral de salida de 1.0)",
          "Hoy se puede entrar a 0.6x y quedar a un tick de la venta; alinea la banda de entrada con la de salida."],
         ["Mérito = tier (1-4) × asimetría", "Sumar un factor de confianza del gate (nº de triggers, calidad de fuente): mérito′ = confianza × tier × asimetría",
          "Incorpora la probabilidad que hoy falta y reduce la selección adversa hacia value traps."],
         ["Cortes de Quality (≥6→4, ≥4→3…)", "Calibrar los cortes con el retorno realizado por tier",
          "Hoy están fijados a mano, sin evidencia de que separen bien."],
         ["El gate se gana por etiqueta del LLM", "Segunda opinión (sparring) en borderline, o exigir 2 fuentes para la etiqueta pivote (orgánico %, design-in)",
          "Un nombre pasa o falla por una sola etiqueta, sin control cruzado vivo."],
         ["Liquidez: filtro $1M/día de universo", "Cap de tamaño vs ADV (que la salida total tome ≤ N días de volumen)",
          "Una posición grande en bajo volumen no se puede salir sin mover el precio."]],
        col_widths_cm=[4.2, 7.3, 5.0])

    add_h3(doc, "A.2 · Reglas de salida")
    add_table(doc,
        ["Regla (hoy)", "Ajuste sugerido", "Por qué"],
        [["Vías 1-3 dormidas (solo 4 y 5 vivas)", "Cablear el pipeline de eventos (Research/RedFlags) → gobernanza, CRR sobreviniente y stop de progreso disparan",
          "Mayor agujero del sistema vivo: una tesis rota no se actúa hasta que el precio ya cayó. PRIORIDAD ALTA."],
         ["Vía 4: asimetría < 0.5 (umbral único)", "Calibrar y hacerla por arquetipo (Binary debería salir antes que Madura)",
          "Un único umbral trata igual riesgos muy distintos."],
         ["Vía 1: stop de progreso (2 earnings)", "Definir «hecho a favor» con criterio duro y fechado (no cualitativo)",
          "Es la salida por «no rinde lo esperado»; hoy el disparador es ambiguo."],
         ["No hay breaker de cartera", "Circuit-breaker de drawdown agregado (reduce sizing / frena entradas bajo cierto DD)",
          "Cartera concentrada de alta beta sin freno agregado ante un drawdown sistémico."]],
        col_widths_cm=[4.2, 7.3, 5.0])

    add_h3(doc, "A.3 · Construcción de cartera y despliegue")
    add_table(doc,
        ["Regla (hoy)", "Ajuste sugerido", "Por qué"],
        [["Universo incluye mega-caps off-theme (AAPL, IBM)", "Higiene de universo: techo de market-cap + filtro temático",
          "Con el deploy comprando nombres nuevos entró AAPL — fuera del mandato small/mid-cap de industrias del futuro."],
         ["Máx 2/subsector NO se enforcea en el deploy", "Aplicar el cap de subsector + cluster capex_AI en el executor de paper",
          "El parámetro existe pero el executor no lo chequea; permite cargar un solo factor macro."],
         ["Sizing sin ajuste por volatilidad", "Escalar el sizing por volatilidad (riesgo, no notional)",
          "16% en un nombre de 30% de vol no es el mismo riesgo que 16% en uno de 90%."]],
        col_widths_cm=[4.2, 7.3, 5.0])

    return doc


def main() -> Path:
    out_dir = Path(__file__).resolve().parent.parent / "data" / "reportes"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"borja_evaluacion_quant_{datetime.now().strftime('%Y%m%dT%H%M%S')}.docx"
    build().save(out)
    return out


if __name__ == "__main__":
    path = main()
    print(f"OK -> {path}")
