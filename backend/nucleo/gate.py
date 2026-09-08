"""Gate de evidencia — la vara por arquetipo (Núcleo consolidado v3, §5).

Checklist pasa/no-pasa donde TODOS los ítems deben pasar. Sin niveles, sin
compensación, sin score. Cada ítem es un hecho con fuente mínima; ESTA TABLA
verifica; el LLM trae el hecho, nunca asigna el resultado. Es la ÚNICA defensa
contra el sesgo de Asimetría-pura → es brutalmente literal a propósito.

Determinista y puro: recibe hechos ya extraídos (dataclass HechosGate, que es a
la vez el CONTRATO del extractor LLM que viene después) y devuelve pasa/no-pasa
+ los ítems fallados. Distingue 'no_pasa' (rechazo) de 'todavia_no' (timing →
watchlist, §5.5: fallar P2/T2 por distancia es timing, no rechazo).

Cubre: U1 (triggers con forma + dientes), U2 (fuente mínima por tipo de hecho),
ítems por arquetipo (M1 / G1-G2 / T1-T2 / P1-P2-P3 / B1-B2-B3), financiación-
hasta-el-hito P3/B3 (§5.4), y el trigger de ejecución de U1 (§5.6).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.nucleo.constantes import (
    ARQUETIPOS_CON_REVENUE,
    MARGEN_FINANCIACION_MESES,
    VENTANA_P2_MESES,
    VENTANA_T2_MESES,
)

# P1 (Pre-revenue): qué tipo de demanda cuenta como hecho (§5.3, definiciones duras).
P1_TIPOS_VALIDOS = ("contrato_firmado", "design_in_economico", "loi_economica")
# Lo que NO cuenta: mou, partnership_estrategica, non_binding, up_to, design_in_tecnico.

FUENTES_VALIDAS = ("A", "B", "C")


def _fuente_ok(fuente: str | None, minimo: tuple[str, ...]) -> bool:
    return fuente in minimo


@dataclass
class Trigger:
    """Trigger de invalidación (U1). La FORMA se verifica: hecho verificable +
    umbral + fecha + fuente. «si la tesis se deteriora» (sin umbral/fecha) no
    cuenta."""
    hecho: str
    umbral: str | None = None
    fecha: str | None = None        # ISO date.
    fuente: str | None = None       # 'A'/'B'/'C'.
    es_estructura_capital: bool = False
    atado_a_hecho_de_entrada: bool = False
    es_trigger_ejecucion: bool = False  # §5.6: entregas/hitos/conversión de backlog.

    def forma_completa(self) -> bool:
        return bool(self.hecho and self.umbral and self.fecha and self.fuente)


@dataclass
class HechosGate:
    """Hechos extraídos para correr la vara. Contrato del extractor LLM.

    El LLM trae cada hecho con su etiqueta y fuente; la tabla decide. Los flags
    semánticos (p. ej. design-in económico vs técnico) son HECHOS ETIQUETADOS por
    el LLM según la definición dura de §5.3, no juicios de resultado.
    """
    arquetipo: str
    triggers: list[Trigger] = field(default_factory=list)

    # §5.6 — si la tesis es ejecutar un contrato plurianual / revenue lumpy.
    tesis_es_ejecucion_contrato: bool = False

    # --- Madura ---
    madura_hecho_vigente: bool = False  # M1: ≥1 hecho ocurrido vigente, no one-off.

    # --- Growth ---
    growth_desglose_organico_disponible: bool = False  # default-exclude: sin desglose → G1 falla.
    growth_organico_pct: float | None = None           # ≥0.50 orgánico (fuente A).
    growth_hecho_continuidad: bool = False             # G2 (fuente A/B).

    # --- Tracción ---
    traccion_hecho_comercial_4t: bool = False          # T1 (A/B o C verificable).
    traccion_catalizador_meses: float | None = None    # T2 ≤18m.
    traccion_catalizador_tiene_metrica: bool = False
    requiere_financiacion_externa: bool = False        # → P3 aplica.

    # --- Pre-revenue ---
    prerev_p1_tipo: str | None = None                  # ver P1_TIPOS_VALIDOS.
    prerev_p1_fuente: str | None = None                # U2: A/B; C solo design-in con contraparte.
    prerev_catalizador_meses: float | None = None      # P2 ≤12m.
    prerev_catalizador_tiene_metrica: bool = False
    prerev_fecha_congelada: bool = False
    prerev_puerta_continuidad: bool = False            # <$10M recurring etiquetado + growth orgánico.

    # --- Binary ---
    binary_b1_fuente_valida: bool = False              # evidencia objetiva (no press release propio).
    binary_evento_fecha: bool = False                  # B2: evento único con fecha/ventana regulatoria.
    binary_metrica_binaria: bool = False               # B2: métrica binaria (aprobación, no «presentar»).

    # --- Financiación-hasta-el-hito (P3/B3, §5.4) ---
    caja_ultimo_filing: float | None = None
    compromisos_firmados_no_dispuestos: float = 0.0
    lineas_credito_disponibles_hoy: float = 0.0        # sin covenants incumplidos.
    burn_mensual_prom_2t: float | None = None
    meses_hasta_hito_financiado: float | None = None   # P2/B2 (para B3: hasta DESPUÉS del evento).


def cobertura_financiacion(h: HechosGate,
                           margen_meses: int = MARGEN_FINANCIACION_MESES) -> dict:
    """Financiación-hasta-el-hito (§5.4). Solo cuentan caja + compromisos firmados
    no dispuestos + líneas de crédito disponibles HOY. Funding no firmado / shelf /
    ATM / «en negociación» NO entran (caso Lilium) — y por eso NO son campos del
    dataclass.

    Cubre si (recursos / burn) ≥ meses_hasta_hito + margen.
    """
    recursos = ((h.caja_ultimo_filing or 0.0)
                + (h.compromisos_firmados_no_dispuestos or 0.0)
                + (h.lineas_credito_disponibles_hoy or 0.0))
    burn = h.burn_mensual_prom_2t
    requerido = (h.meses_hasta_hito_financiado or 0.0) + margen_meses
    if burn is None or burn <= 0:
        # Sin burn (o no quema) → la financiación no es restricción.
        return {"cubre": True, "meses_cubiertos": float("inf"), "requerido": requerido}
    meses_cubiertos = recursos / burn
    return {"cubre": meses_cubiertos >= requerido,
            "meses_cubiertos": meses_cubiertos, "requerido": requerido,
            "recursos": recursos, "burn_mensual": burn}


def _check_u1(h: HechosGate) -> list[str]:
    fallos: list[str] = []
    validos = [t for t in h.triggers if t.forma_completa()]
    if not (2 <= len(validos) <= 4):
        fallos.append(
            f"U1: {len(validos)} triggers con forma completa (se exigen 2-4)"
        )
    if not any(t.es_estructura_capital for t in validos):
        fallos.append("U1: ningún trigger de estructura de capital")
    if not any(t.atado_a_hecho_de_entrada for t in validos):
        fallos.append("U1: ningún trigger atado al hecho que dejó entrar")
    # §5.6 — ejecución de contrato exige trigger de ejecución con umbral.
    if h.tesis_es_ejecucion_contrato and not any(
        t.es_trigger_ejecucion and t.forma_completa() for t in validos
    ):
        fallos.append("U1: tesis de ejecución sin trigger de ejecución con umbral (§5.6)")
    return fallos


def _check_madura(h: HechosGate) -> list[str]:
    if not h.madura_hecho_vigente:
        return ["M1: sin hecho ocurrido vigente en el último filing/transcript"]
    return []


def _check_growth(h: HechosGate) -> list[str]:
    fallos: list[str] = []
    # G1 default-exclude: sin desglose → falla.
    if not h.growth_desglose_organico_disponible:
        fallos.append("G1: sin desglose orgánico vs M&A (fuente A) → default-exclude")
    elif (h.growth_organico_pct or 0.0) < 0.50:
        fallos.append(f"G1: crecimiento orgánico {(h.growth_organico_pct or 0):.0%} (<50%)")
    if not h.growth_hecho_continuidad:
        fallos.append("G2: sin hecho de continuidad (backlog/RPO/contratos/renovaciones)")
    return fallos


def _check_traccion(h: HechosGate) -> tuple[list[str], list[str]]:
    """Devuelve (fallos_rechazo, fallos_timing). T2 fallado por distancia es timing."""
    fallos: list[str] = []
    timing: list[str] = []
    if not h.traccion_hecho_comercial_4t:
        fallos.append("T1: sin hecho comercial nuevo en los últimos 4 trimestres")
    # T2 — catalizador ≤18m con métrica.
    meses = h.traccion_catalizador_meses
    if meses is None or not h.traccion_catalizador_tiene_metrica:
        fallos.append("T2: sin catalizador fechado con métrica de éxito")
    elif meses > VENTANA_T2_MESES:
        timing.append(f"T2: catalizador a {meses:.0f}m (>{VENTANA_T2_MESES}m) → todavía no")
    # Si requiere financiación externa, P3 completa.
    if h.requiere_financiacion_externa and not cobertura_financiacion(h)["cubre"]:
        fallos.append("T2/P3: financiación-hasta-el-hito no cubre (requiere financiación externa)")
    return fallos, timing


def _check_prerevenue(h: HechosGate) -> tuple[list[str], list[str]]:
    fallos: list[str] = []
    timing: list[str] = []
    # P1 — demanda real con documento citable.
    if h.prerev_p1_tipo not in P1_TIPOS_VALIDOS:
        fallos.append(f"P1: demanda no cuenta como hecho ({h.prerev_p1_tipo or 'ninguno'})")
    else:
        # U2 — fuente mínima. Design-in admite C con contraparte (sin monto).
        minimo = ("A", "B", "C") if h.prerev_p1_tipo == "design_in_economico" else ("A", "B")
        if not _fuente_ok(h.prerev_p1_fuente, minimo):
            fallos.append(f"P1/U2: fuente {h.prerev_p1_fuente or 'N/D'} insuficiente para {h.prerev_p1_tipo}")
    # P2 — catalizador ≤12m con métrica, fecha congelada. Puerta de continuidad exime.
    if not h.prerev_puerta_continuidad:
        meses = h.prerev_catalizador_meses
        if meses is None or not h.prerev_catalizador_tiene_metrica:
            fallos.append("P2: sin catalizador definitorio con métrica")
        elif not h.prerev_fecha_congelada:
            fallos.append("P2: fecha del catalizador no congelada al entrar")
        elif meses > VENTANA_P2_MESES:
            timing.append(f"P2: catalizador a {meses:.0f}m (>{VENTANA_P2_MESES}m) → todavía no")
    # P3 — financiación-hasta-el-hito.
    if not cobertura_financiacion(h)["cubre"]:
        fallos.append("P3: financiación-hasta-el-hito no cubre")
    return fallos, timing


def _check_binary(h: HechosGate) -> list[str]:
    fallos: list[str] = []
    if not h.binary_b1_fuente_valida:
        fallos.append("B1: sin evidencia objetiva válida (press release propio no cuenta)")
    if not (h.binary_evento_fecha and h.binary_metrica_binaria):
        fallos.append("B2: sin evento fechado con métrica binaria")
    # B3 — financiación firmada hasta DESPUÉS del evento + 6m. Binary NO tiene «todavía no».
    if not cobertura_financiacion(h)["cubre"]:
        fallos.append("B3: financiación no cubre hasta después del evento + margen")
    return fallos


def evaluar_gate(h: HechosGate) -> dict:
    """Corre la vara completa (U1 + U2 + ítems por arquetipo). Determinista.

    Devuelve:
      pasa: bool
      estado: 'pasa' | 'no_pasa' | 'todavia_no'
      fallos: list[str]   — ítems de rechazo
      timing: list[str]   — ítems fallados solo por distancia (§5.5 «todavía no»)
    """
    fallos = _check_u1(h)
    timing: list[str] = []

    arq = h.arquetipo
    if arq == "Madura":
        fallos += _check_madura(h)
    elif arq == "Growth":
        fallos += _check_growth(h)
    elif arq == "Tracción":
        f, t = _check_traccion(h)
        fallos += f
        timing += t
    elif arq == "Pre-revenue":
        f, t = _check_prerevenue(h)
        fallos += f
        timing += t
    elif arq == "Binary":
        fallos += _check_binary(h)  # Binary NO tiene «todavía no».
    else:
        fallos.append(f"arquetipo desconocido: {arq!r}")

    if fallos:
        estado = "no_pasa"
        pasa = False
    elif timing:
        estado = "todavia_no"   # solo timing → watchlist, no rechazo.
        pasa = False
    else:
        estado = "pasa"
        pasa = True

    return {"pasa": pasa, "estado": estado, "fallos": fallos, "timing": timing,
            "arquetipo": arq}
