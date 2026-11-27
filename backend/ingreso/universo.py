"""Filtro de universo (Art. 2) — ¿esta empresa es ADMISIBLE para analizarse?

Determinista y puro: hechos inyectados → admisible/no + motivos. NO decide si es
buena inversión (eso es el gate) ni si vale el deep research (eso es el Filtro 0);
solo si PUEDE entrar al pipeline. Piso de market cap SIN techo (decisión del
operador). Reusa LIQUIDEZ_SCREENER del núcleo.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.nucleo.constantes import LIQUIDEZ_SCREENER

# Rango de market cap (operador 2026-11-27): $150M–$60B (piso del import + techo del IPS; antes el gate tenía piso
# $50M sin techo, incoherente con los otros caminos de entrada — ahora UNA sola regla).
MIN_MARKET_CAP = 150_000_000
MAX_MARKET_CAP = 60_000_000_000

# Jurisdicciones permitidas — WHITELIST POSITIVA del operador (2026-11-27): los países donde quiere trabajar.
# EE.UU., Canadá, Brasil, Europa (amplia), Taiwán, Japón, Corea + Australia (tierras raras: LYC.AX ya está).
# [DEFERIDO — registro 14] normalizar upstream (país de listing vs. incorporación, ISO consistente).
JURISDICCIONES_PERMITIDAS = frozenset({
    "US", "CA",                                                                    # Norteamérica
    "BR",                                                                          # Brasil
    "GB", "UK", "DE", "FR", "NL", "SE", "CH", "IT", "ES", "FI", "NO", "DK",        # Europa
    "BE", "AT", "IE", "PT", "PL",
    "JP", "KR", "TW",                                                              # Asia tech
    "AU",                                                                          # Australia (tierras raras)
})


@dataclass
class HechosUniverso:
    jurisdiccion: str | None = None
    es_adr: bool = False
    market_cap: float | None = None
    adv_usd: float | None = None          # volumen promedio diario en USD (ver registro 14: def. exacta)
    tiene_nodo: bool = False              # vínculo con un nodo del mapa — INFORMATIVO (ya no gatea la entrada, 2026-11-26)
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
    elif h.market_cap > MAX_MARKET_CAP:
        motivos.append(f"market cap ${h.market_cap/1e9:.0f}B > ${MAX_MARKET_CAP/1e9:.0f}B (no es small/mid cap)")
    if h.adv_usd is None or h.adv_usd < LIQUIDEZ_SCREENER:
        liq = f"${h.adv_usd/1e6:.1f}M" if h.adv_usd is not None else "N/D"
        motivos.append(f"liquidez {liq}/día < ${LIQUIDEZ_SCREENER/1e6:.1f}M/día")
    # NOTA (2026-11-26, operador): el vínculo con un nodo del mapa YA NO es requisito de entrada. El diseño cerrado
    # (docs 88/89) dejó el cuello como INSUMO del PM + estructura de búsqueda del discovery, NO como pata de entrada
    # (el clasificador de cuellos se retiró: pro-cíclico). `tiene_nodo` se conserva como dato informativo, no gatea.
    if not h.instrumento_permitido:
        motivos.append("instrumento no permitido (SPAC/warrant/pref/ETF/no common equity)")
    if not h.mercado_operable:
        motivos.append("mercado no operable (halted / delisting / no operable por IBKR)")
    return ResultadoUniverso(admisible=not motivos, motivos=motivos)
