"""Filtro de universo (Art. 2) — ¿esta empresa es ADMISIBLE para analizarse?

Determinista y puro: hechos inyectados → admisible/no + motivos. NO decide si es
buena inversión (eso es el gate) ni si vale el deep research (eso es el Filtro 0);
solo si PUEDE entrar al pipeline. Piso de market cap SIN techo (decisión del
operador). Reusa LIQUIDEZ_SCREENER del núcleo.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.nucleo.constantes import LIQUIDEZ_SCREENER

# Piso de market cap (sin techo — el filtrado por tamaño lo hace el pipeline, Art. 2.3).
MIN_MARKET_CAP = 50_000_000

# Jurisdicciones permitidas (Art. 2.1): EE.UU., Canadá, Europa, Asia tech. China afuera.
# [DEFERIDO — registro 14] normalizar upstream: definir si es país de listing vs.
# incorporación, y usar códigos ISO consistentes. Hoy el adapter solo produce "US"
# (EDGAR), así que la imperfección de esta lista no muerde todavía.
JURISDICCIONES_PERMITIDAS = frozenset({
    "US", "CA",                       # Norteamérica
    "UK", "GB", "DE", "FR", "NL", "SE", "CH",  # Europa (GB = alias de UK)
    "JP", "KR", "TW",                 # Asia tech relevante
})


@dataclass
class HechosUniverso:
    jurisdiccion: str | None = None
    es_adr: bool = False
    market_cap: float | None = None
    adv_usd: float | None = None          # volumen promedio diario en USD (ver registro 14: def. exacta)
    tiene_nodo: bool = False              # vínculo con un nodo del mapa (Art. 2.1)
    instrumento_permitido: bool = True    # common equity (no SPAC/warrant/pref/ETF) — lo resuelve upstream
    mercado_operable: bool = True         # operable por IBKR, no halted/delisting — lo resuelve upstream


@dataclass
class ResultadoUniverso:
    admisible: bool
    motivos: list[str] = field(default_factory=list)


def evaluar_universo(h: HechosUniverso) -> ResultadoUniverso:
    """¿Admisible para el pipeline? Todos los criterios deben cumplirse."""
    motivos: list[str] = []
    if h.jurisdiccion not in JURISDICCIONES_PERMITIDAS:
        motivos.append(f"jurisdicción no permitida: {h.jurisdiccion or 'N/D'}")
    if h.es_adr:
        motivos.append("ADR (no se opera vía ADR)")
    if h.market_cap is None or h.market_cap < MIN_MARKET_CAP:
        cap = f"${h.market_cap/1e6:.0f}M" if h.market_cap is not None else "N/D"
        motivos.append(f"market cap {cap} < ${MIN_MARKET_CAP/1e6:.0f}M")
    if h.adv_usd is None or h.adv_usd < LIQUIDEZ_SCREENER:
        liq = f"${h.adv_usd/1e6:.1f}M" if h.adv_usd is not None else "N/D"
        motivos.append(f"liquidez {liq}/día < ${LIQUIDEZ_SCREENER/1e6:.1f}M/día")
    if not h.tiene_nodo:
        motivos.append("sin vínculo con nodo del mapa")
    if not h.instrumento_permitido:
        motivos.append("instrumento no permitido (SPAC/warrant/pref/ETF/no common equity)")
    if not h.mercado_operable:
        motivos.append("mercado no operable (halted / delisting / no operable por IBKR)")
    return ResultadoUniverso(admisible=not motivos, motivos=motivos)
