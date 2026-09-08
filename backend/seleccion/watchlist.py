"""Watchlist VIVA + MAX_WATCHLIST — Bloque C §5, traspaso §3.1.

Las candidatas que pasan el núcleo y el PM no elige quedan en watchlist VIVA (no
foto): el PM elige SIEMPRE sobre data viva al precio de hoy; la que rompió tesis
se cae sola al re-correr el gate.

Reglas cerradas:
  - Tope fijo MAX_WATCHLIST. No se cubre todo el universo (aceptado). Entra una
    mejor y está llena → sale la PEOR por mérito re-derivado a precio de hoy.
  - Timing (traspaso §3.1): una candidata con catalizador fechado dentro de la
    ventana 45-60 días NO es elegible para salir aunque su mérito-hoy sea bajo
    (igual que el núcleo §14 protege a la incumbente con catalizador cercano).
  - Salir NO borra el vínculo candidata↔nodo ni su timestamp_revision: si aparece
    un hecho nuevo en su nodo, vuelve al flujo como candidata fría (no se pierde
    la 2ª/3ª ola). Salir solo la saca del monitor de precio.

La re-derivación del mérito a precio de hoy la hace el núcleo (evaluar_empresa);
acá vive la lógica determinista de tope/expulsión/protección. El monitor de
precio (BLOQUEA IBKR) mantiene viva la data; la watchlist no lo necesita para su
lógica de ranking.
"""
from __future__ import annotations

from dataclasses import dataclass

# Tope de la watchlist (calibrable, traspaso §3.1). Necesario, no cosmético: sin
# tope el monitor de precio correría sobre un conjunto que crece sin límite y
# choca con el single-thread.
MAX_WATCHLIST = 20

# Ventana de catalizador que protege de expulsión (días). Importa el criterio de
# timing ya cerrado del núcleo §14; no es constante nueva.
VENTANA_CATALIZADOR_PROTEGIDA = (45, 60)


@dataclass
class EntradaWatchlist:
    ticker: str
    merito: float                       # re-derivado a precio de hoy por el núcleo.
    catalizador_dias: int | None = None # días al catalizador fechado (None = sin catalizador cercano).
    nodo_id: str | None = None          # vínculo candidata↔nodo (NO se borra al salir).
    timestamp_revision: str | None = None

    def protegida_por_timing(self) -> bool:
        """§3.1: catalizador dentro de la ventana 45-60d → no elegible para salir."""
        if self.catalizador_dias is None:
            return False
        lo, hi = VENTANA_CATALIZADOR_PROTEGIDA
        return lo <= self.catalizador_dias <= hi


def intentar_ingresar(watchlist: list[EntradaWatchlist], nueva: EntradaWatchlist,
                      max_watchlist: int = MAX_WATCHLIST) -> dict:
    """Intenta meter `nueva` en la watchlist. Si hay lugar, entra. Si está llena,
    desplaza a la PEOR no-protegida por mérito SOLO si `nueva` la supera.

    Devuelve {ingresa, expulsada (EntradaWatchlist|None), motivo}. La expulsada
    sale del monitor pero conserva su vínculo (responsabilidad del caller).
    """
    if len(watchlist) < max_watchlist:
        watchlist.append(nueva)
        return {"ingresa": True, "expulsada": None, "motivo": "había lugar"}

    # Candidatas elegibles para salir: las NO protegidas por timing.
    elegibles = [e for e in watchlist if not e.protegida_por_timing()]
    if not elegibles:
        return {"ingresa": False, "expulsada": None,
                "motivo": "watchlist llena y todas protegidas por catalizador cercano"}

    peor = min(elegibles, key=lambda e: e.merito)
    if nueva.merito > peor.merito:
        watchlist.remove(peor)
        watchlist.append(nueva)
        return {"ingresa": True, "expulsada": peor,
                "motivo": f"desplaza a {peor.ticker} (mérito {peor.merito:.2f} < {nueva.merito:.2f})"}
    return {"ingresa": False, "expulsada": None,
            "motivo": f"mérito {nueva.merito:.2f} no supera a la peor ({peor.merito:.2f})"}


def caer_por_tesis_rota(watchlist: list[EntradaWatchlist], ticker: str) -> EntradaWatchlist | None:
    """La que rompió tesis al re-correr el gate se cae sola (§5). Sale del monitor,
    pero el vínculo candidata↔nodo NO se borra (lo preserva el caller en el mapa).
    Devuelve la entrada removida (con su nodo_id/timestamp para preservar)."""
    for e in list(watchlist):
        if e.ticker.upper() == ticker.upper():
            watchlist.remove(e)
            return e
    return None


def re_rankear(watchlist: list[EntradaWatchlist]) -> list[EntradaWatchlist]:
    """Devuelve la watchlist ordenada por mérito re-derivado (mejor primero). El
    PM elige siempre sobre esta data viva."""
    return sorted(watchlist, key=lambda e: -e.merito)
