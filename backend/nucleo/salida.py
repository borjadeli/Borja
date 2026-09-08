"""Las cinco vías de salida + re-gate — Núcleo consolidado v3, §13.

Reemplaza ÍNTEGRAMENTE las 8 reglas de rotación del sistema viejo (§16). Misma
separación estricta de la entrada: el LLM trae hechos fechados; una tabla decide;
el LLM nunca asigna el resultado. El score global y el momentum NO disparan nada.
No hay stop de precio: el precio solo alimenta vía 4 (asimetría) y vía 5 (peso).

Toda vía produce una RECOMENDACIÓN con hecho/fuente/trigger citados; el humano
aprueba (journal) o frena (§15: frenar cuesta y deja huella). El sistema nunca
vende solo.

Orden de precedencia atómico (traspaso §7.1, extiende el Candado A al caso
general): governance hard → CRR-crítico → vía 1/re-gate → vía 4 → vía 5. Si una
vía superior recomienda salida total, las inferiores solo se registran como
contexto.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.nucleo.constantes import (
    ARQUETIPOS_CON_REVENUE,
    BANDA_RECORTE,
    CICLOS_SIN_PROGRESO_BASE,
    CICLOS_SIN_PROGRESO_FRAGIL,
    ROTATION_UMBRAL_SALIDA,
    VIDAS_REENTRADA,
)
from backend.nucleo.sizing import asimetria_vigente

# Clase integridad-de-datos (Candado A / vía 3 hard-event, §13.1/§13.2): un solo
# elemento basta para venta directa sin re-gate y sin esperar a juntar tres.
HARD_GOVERNANCE_EVENTS = (
    "auditor_resignation",
    "filing_delay",            # material filing non-compliance
    "investigacion_sec_doj",   # investigación formal SEC/DOJ
    "trading_halt",
    "delisting",
    "insolvency",              # incl. Chapter 7/11
)


def ciclos_sin_progreso_max(arquetipo: str) -> int:
    """Ventana del stop de progreso por arquetipo (§13.1, CICLOS_SIN_PROGRESO):
    2 earnings para Madura/Growth/Tracción; 1 para Pre-revenue/Binary."""
    return (CICLOS_SIN_PROGRESO_BASE if arquetipo in ARQUETIPOS_CON_REVENUE
            else CICLOS_SIN_PROGRESO_FRAGIL)


def via4_elegible(arquetipo: str, bull_bear_anclado_en_hechos_ocurridos: bool) -> bool:
    """Alcance de la vía 4 (§13.2, corrección anti-RGTI): arquetipos con revenue
    MÁS cualquier posición cuyo bull/bear sea re-derivable con hechos OCURRIDOS
    duros (contrato firmado, backlog en filing, revenue contratado, hito P1/P2
    cumplido). La pura narrativa (IONQ) queda excluida sola por no tener ancla."""
    if arquetipo in ARQUETIPOS_CON_REVENUE:
        return True
    return bool(bull_bear_anclado_en_hechos_ocurridos)


@dataclass
class EstadoPosicion:
    """Estado vivo de una posición para evaluar las 5 vías. El LLM re-deriva los
    hechos; estos llegan ya como datos."""
    ticker: str
    arquetipo: str
    # Vía 1 — invalidación:
    trigger_disparado: bool = False
    trigger_vencido_sin_catalizador: bool = False
    segunda_corrida_de_fecha: bool = False
    earnings_sin_hecho_a_favor: int = 0   # ventanas de earnings consecutivas sin progreso.
    # Vía 2 — CRR-crítico sobreviniente:
    crr_critico: bool = False
    # Vía 3 — governance:
    hard_governance_events: list[str] = field(default_factory=list)
    soft_red_flags: int = 0
    # Vía 4 — asimetría muerta:
    bull: float | None = None
    precio: float | None = None
    bear: float | None = None
    bull_bear_anclado_en_hechos_ocurridos: bool = False
    # Vía 5 — recorte por tamaño:
    peso_vivo: float | None = None
    hardcap_vigente: float | None = None
    # Re-entrada (Candado B):
    reentradas_usadas: int = 0


def _via1_invalidacion(e: EstadoPosicion) -> dict | None:
    disparadores = []
    if e.trigger_disparado:
        disparadores.append("trigger disparado")
    if e.trigger_vencido_sin_catalizador:
        disparadores.append("trigger vencido sin catalizador")
    if e.segunda_corrida_de_fecha:
        disparadores.append("segunda corrida de fecha (anti-LAZR)")
    if e.earnings_sin_hecho_a_favor >= ciclos_sin_progreso_max(e.arquetipo):
        disparadores.append(
            f"stop de progreso: {e.earnings_sin_hecho_a_favor} ventanas sin hecho a favor "
            f"(máx {ciclos_sin_progreso_max(e.arquetipo)})"
        )
    if not disparadores:
        return None
    return {"via": 1, "nombre": "invalidación", "disparadores": disparadores}


def _via2_crr_critico(e: EstadoPosicion) -> dict | None:
    if e.crr_critico:
        return {"via": 2, "nombre": "CRR-crítico sobreviniente", "accion": "recomendar_salir"}
    return None


def _via3_governance(e: EstadoPosicion) -> dict | None:
    hard = [ev for ev in e.hard_governance_events if ev in HARD_GOVERNANCE_EVENTS]
    if hard:
        return {"via": 3, "nombre": "governance", "tipo": "hard",
                "eventos": hard, "accion": "venta_directa", "bloquea_regate": True}
    if e.soft_red_flags >= 3:
        return {"via": 3, "nombre": "governance", "tipo": "soft",
                "red_flags": e.soft_red_flags, "accion": "salir_urgente", "bloquea_regate": True}
    return None


def _via4_asimetria_muerta(e: EstadoPosicion) -> dict | None:
    if not via4_elegible(e.arquetipo, e.bull_bear_anclado_en_hechos_ocurridos):
        return None
    if e.bull is None or e.precio is None or e.bear is None:
        return None
    asim = asimetria_vigente(e.bull, e.precio, e.bear)
    if asim is None:
        return None
    if asim < ROTATION_UMBRAL_SALIDA:
        return {"via": 4, "nombre": "asimetría muerta", "asimetria": asim,
                "accion": "recomendar_salir"}
    if asim < 1.0:
        return {"via": 4, "nombre": "asimetría débil", "asimetria": asim,
                "accion": "no_aumentar"}
    return None


def _via5_recorte(e: EstadoPosicion) -> dict | None:
    if e.peso_vivo is None or e.hardcap_vigente is None:
        return None
    if e.peso_vivo > e.hardcap_vigente * BANDA_RECORTE:
        return {"via": 5, "nombre": "recorte por tamaño", "peso_vivo": e.peso_vivo,
                "recortar_a": e.hardcap_vigente, "accion": "recortar"}
    return None


def evaluar_salida(e: EstadoPosicion) -> dict:
    """Evalúa las 5 vías y resuelve con el orden de precedencia atómico
    (traspaso §7.1). Devuelve la acción ganadora + las vías como contexto.

    Acciones posibles: venta_directa, salir_urgente, recomendar_salir,
    re_gate, recortar, no_aumentar, mantener.
    """
    v1 = _via1_invalidacion(e)
    v2 = _via2_crr_critico(e)
    v3 = _via3_governance(e)
    v4 = _via4_asimetria_muerta(e)
    v5 = _via5_recorte(e)
    todas = [v for v in (v3, v2, v1, v4, v5) if v is not None]  # ya en orden de precedencia.

    # Precedencia: governance hard → CRR-crítico → vía 1 → vía 4 → vía 5.
    if v3 is not None:
        # Governance gana y bloquea re-gate (Candado A): venta sin re-gate.
        accion = v3["accion"]
        return _resultado(e, accion, v3, todas, regate=False)

    if v2 is not None:
        return _resultado(e, "recomendar_salir", v2, todas)

    if v1 is not None:
        # Vía 1 → re-gate completo, salvo Candado B agotado (una sola vida).
        if e.reentradas_usadas >= VIDAS_REENTRADA:
            return _resultado(e, "venta_directa", v1, todas, regate=False,
                              nota="Candado B: re-entrada ya usada (una sola vida) → venta sin re-gate")
        return _resultado(e, "re_gate", v1, todas, regate=True)

    if v4 is not None:
        return _resultado(e, v4["accion"], v4, todas)

    if v5 is not None:
        return _resultado(e, "recortar", v5, todas)

    return _resultado(e, "mantener", None, todas)


def _resultado(e: EstadoPosicion, accion: str, via_ganadora: dict | None,
               todas: list[dict], regate: bool = False, nota: str = "") -> dict:
    return {
        "ticker": e.ticker,
        "accion": accion,
        "via_ganadora": via_ganadora,
        "regate": regate,
        "vias_disparadas": todas,        # contexto: todas las vías que aplicaron.
        "nota": nota,
    }
