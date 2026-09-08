"""Challenger de cartera — recambio por mérito con histéresis (Borja, 2026-07-02).

Cierra un hueco real del trader paper: hoy `paper_trader.correr_ciclo` sólo llena
SLOTS LIBRES. Con la cartera llena (12/12) y sin salidas, no entra nadie aunque
aparezca una candidata mucho mejor. El challenger permite que, en cada revisión,
la MEJOR candidata de watchlist DESAFÍE a la PEOR titular elegible y la desplace
si — y sólo si — supera una banda de histéresis que frena el churn.

Extiende el patrón que YA existe para la watchlist (`watchlist.intentar_ingresar`,
"desplaza a la peor por mérito"), agregándole la banda de histéresis que aquel no
tiene (allá alcanza `nuevo.merito > peor.merito` a secas; acá se exige margen).

Reglas (mecanismo aprobado por Borja):
  El retador entra si pasa Gate (lo verifica el caller: decision == 'candidata'),
  respeta los límites de cartera (sector/cubo/hard-cap — los enforcea el caller,
  que tiene esa maquinaria) y cumple UNA de dos condiciones:

  1. HISTÉRESIS VERTICAL — supera a la peor titular por ≥ MARGEN_VERTICAL neto de
     fricciones. Un único margen ancho: "es claramente mejor que la peor".
  2. HISTÉRESIS HORIZONTAL — supera a ≥ MIN_TITULARES_SUPERADOS titulares actuales
     Y supera a la que desplaza (la peor) por ≥ MARGEN_HORIZONTAL neto de
     fricciones. "No aplasta a una, pero es mejor que buena parte del libro".

Protección de timing (§14 núcleo / §5 watchlist C): una titular con catalizador
fechado dentro de la ventana 45-60d NO es elegible para ser desplazada, aunque su
mérito-hoy sea el peor (igual que el núcleo protege a la incumbente con
catalizador cercano). Reutiliza `VENTANA_CATALIZADOR_PROTEGIDA_DIAS`.

El throttle es 1 swap por revisión (un desafío mejor-candidata vs peor-titular por
ciclo): la disciplina manda sobre la actividad (feedback durable del operador).

⚠️ NETO DE FRICCIONES — proxy: el mérito NO es un retorno (es Quality×Asimetría,
adimensional), así que la fricción de capital no mapea 1:1 a la unidad del mérito.
Acá la modelamos como un colchón ADITIVO sobre el ratio de margen requerido
(umbral efectivo = MARGEN + FRICCION_ROUND_TRIP). Es una aproximación honesta para
paper; el costo de fricción riguroso necesita precios de EJECUCIÓN (IBKR, Fase 3,
mismo blocker que el monitor de precio). Documentado, no escondido.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.nucleo.constantes import VENTANA_CATALIZADOR_PROTEGIDA_DIAS

# ---- Flag maestro. APAGADO por defecto ----------------------------------------
# Encender toca el comportamiento del ciclo paper VIVO (que hoy alimenta la
# validación PASS_RATE contra el sistema viejo): sólo flipear a True cuando el
# operador/Borja confirmen prioridad y parámetros. Con False, el ciclo no cambia.
CHALLENGER_ACTIVO = False

# ---- Parámetros de histéresis (calibrables, defaults propuestos) --------------
MARGEN_VERTICAL = 0.20          # supera a la peor titular por ≥20% (Borja).
MARGEN_HORIZONTAL = 0.10        # margen contra la desplazada en la vía horizontal.
MIN_TITULARES_SUPERADOS = 3     # "supera a ≥3 titulares actuales" (Borja).
FRICCION_ROUND_TRIP = 0.002     # 0,2% ida+vuelta (proxy paper; ver nota del módulo).
MAX_SWAPS_POR_CICLO = 1         # throttle anti-churn: un solo desafío por revisión.

# [PENDIENTE — confirmar con Borja] Borja escribió "+5%/+10%" para la vía
# horizontal, sugiriendo DOS márgenes según contexto. Lo natural sería atarlos a
# momentum (Favorable +5% / Neutral +10%, consistente con la matriz de sizing),
# PERO en el núcleo nuevo el momentum dejó de ser un determinante de primera clase
# (§18: "vocabulario de momentum de 4 estados como determinante" MUERE). Sin una
# señal de momentum viva en la evaluación del núcleo, no hay de dónde leer el tier.
# Por eso arrancamos con un único MARGEN_HORIZONTAL conservador (+10%). Si Borja
# quiere el tier, definir primero la FUENTE de la señal de momentum.
MARGEN_HORIZONTAL_FAVORABLE = 0.05  # reservado; inactivo hasta cerrar la fuente.


@dataclass
class Titular:
    """Una posición viva de la cartera, con su mérito re-derivado a precio de hoy."""
    ticker: str
    merito: float
    catalizador_dias: int | None = None  # días al catalizador fechado (None = sin catalizador cercano).
    sector: str | None = None

    def protegida_por_timing(self) -> bool:
        """§14/§5: catalizador dentro de la ventana 45-60d → no desplazable."""
        if self.catalizador_dias is None:
            return False
        lo, hi = VENTANA_CATALIZADOR_PROTEGIDA_DIAS
        return lo <= self.catalizador_dias <= hi


def _umbral(margen: float) -> float:
    """Ratio de mérito requerido, con la fricción round-trip como colchón aditivo."""
    return 1.0 + margen + FRICCION_ROUND_TRIP


def evaluar_desafio(retador_merito: float, titulares: list[Titular]) -> dict:
    """Decide si `retador_merito` desplaza a la peor titular ELEGIBLE.

    NO verifica Gate ni límites de cartera (sector/cubo/hard-cap): eso es del
    caller, que tiene la maquinaria del núcleo. Acá vive SÓLO la lógica de
    histéresis + protección de timing.

    Devuelve:
      {swap: bool, sale: str|None, condicion: 'vertical'|'horizontal'|None,
       peor: str|None, motivo: str, detalle: {...}}
    """
    if retador_merito is None:
        return {"swap": False, "sale": None, "condicion": None, "peor": None,
                "motivo": "retador sin mérito calculable (asimetría None)"}

    elegibles = [t for t in titulares if not t.protegida_por_timing()]
    if not elegibles:
        return {"swap": False, "sale": None, "condicion": None, "peor": None,
                "motivo": "no hay titular elegible (todas protegidas por catalizador 45-60d)"}

    peor = min(elegibles, key=lambda t: t.merito)

    # Vía 1 — histéresis vertical: aplasta a la peor.
    umbral_v = peor.merito * _umbral(MARGEN_VERTICAL)
    if retador_merito >= umbral_v:
        return {"swap": True, "sale": peor.ticker, "condicion": "vertical", "peor": peor.ticker,
                "motivo": (f"vertical: retador {retador_merito:.3f} ≥ peor {peor.merito:.3f} "
                           f"×{_umbral(MARGEN_VERTICAL):.3f} = {umbral_v:.3f}"),
                "detalle": {"retador_merito": retador_merito, "peor_merito": peor.merito,
                            "umbral": umbral_v}}

    # Vía 2 — histéresis horizontal: mejor que ≥N titulares Y margen sobre la desplazada.
    superados = sum(1 for t in titulares if retador_merito > t.merito)
    umbral_h = peor.merito * _umbral(MARGEN_HORIZONTAL)
    if superados >= MIN_TITULARES_SUPERADOS and retador_merito >= umbral_h:
        return {"swap": True, "sale": peor.ticker, "condicion": "horizontal", "peor": peor.ticker,
                "motivo": (f"horizontal: supera a {superados}≥{MIN_TITULARES_SUPERADOS} titulares "
                           f"y {retador_merito:.3f} ≥ peor {peor.merito:.3f} "
                           f"×{_umbral(MARGEN_HORIZONTAL):.3f} = {umbral_h:.3f}"),
                "detalle": {"retador_merito": retador_merito, "peor_merito": peor.merito,
                            "superados": superados, "umbral": umbral_h}}

    return {"swap": False, "sale": None, "condicion": None, "peor": peor.ticker,
            "motivo": (f"no supera histéresis: retador {retador_merito:.3f} vs peor {peor.merito:.3f} "
                       f"(vertical ≥{umbral_v:.3f}, horizontal ≥{umbral_h:.3f} y superados "
                       f"{superados}/{MIN_TITULARES_SUPERADOS})"),
            "detalle": {"retador_merito": retador_merito, "peor_merito": peor.merito,
                        "superados": superados}}
