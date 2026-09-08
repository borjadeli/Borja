"""Selector v3 — de tiers a CARTERA (doc 26: no ranking cardinal, sí tiers + sizing).

Toma las Evaluaciones (tier A/B/C + Δ de evidencia), elige los elegibles (A/B), los ordena por
prioridad (tier, luego Δ), y arma la cartera con sizing por convicción × hard_cap, respetando caps
por sector, máx posiciones y el techo de despliegue. Determinista. NO reparte proporcional al
mérito (eso era el defecto inestable del selector viejo): tamaño = convicción(tier) × cap.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.nucleo.constantes import MAX_POSICIONES, TECHO_POSICION, TOPE_INVERTIDO
from backend.nucleo.evaluacion import Evaluacion, clave_prioridad

# Convicción por tier: A (core) usa el cap pleno; B (satélite) entra más chico.
CONVICCION = {"A": 1.0, "B": 0.6}


@dataclass
class Posicion:
    ticker: str
    tier: str
    delta: str
    peso: float
    sector: str
    hard_cap: float


@dataclass
class Cartera:
    posiciones: list[Posicion] = field(default_factory=list)
    invertido: float = 0.0
    cash: float = 1.0
    afuera: list = field(default_factory=list)     # [(ticker, motivo)]


def construir_cartera(evaluaciones: list[Evaluacion], *, hard_cap_por_ticker: dict | None = None,
                      sector_por_ticker: dict | None = None,
                      max_posiciones: int = MAX_POSICIONES, cap_sector: float = 0.40,
                      techo_posicion: float = TECHO_POSICION,
                      tope: float = TOPE_INVERTIDO) -> Cartera:
    """Arma la cartera desde las evaluaciones. Elegibles = Tier A/B; C = watch (afuera)."""
    hard_cap_por_ticker = hard_cap_por_ticker or {}
    sector_por_ticker = sector_por_ticker or {}
    elegibles = sorted([e for e in evaluaciones if e.tier in ("A", "B")], key=clave_prioridad)
    c = Cartera()
    por_sector: dict[str, float] = {}

    for e in evaluaciones:                          # los Tier C van a watch (transparencia)
        if e.tier == "C":
            c.afuera.append((e.ticker, f"watch (Tier C — {e.motivo})"))

    for e in elegibles:
        if len(c.posiciones) >= max_posiciones:
            c.afuera.append((e.ticker, "sin slot (máx posiciones)")); continue
        hc = hard_cap_por_ticker.get(e.ticker) or e.hard_cap or techo_posicion
        peso = min(CONVICCION.get(e.tier, 0.6) * hc, hc, techo_posicion)
        sector = sector_por_ticker.get(e.ticker, "SIN_SECTOR")
        # cap por sector (SIN_SECTOR no se capea: no se penaliza lo que no se puede clasificar)
        # y techo de despliegue recortan el peso
        if sector != "SIN_SECTOR":
            peso = min(peso, max(0.0, cap_sector - por_sector.get(sector, 0.0)))
        peso = min(peso, max(0.0, tope - c.invertido))
        if peso <= 0.0:
            c.afuera.append((e.ticker, "sin espacio (cap sector/tope de despliegue)")); continue
        c.posiciones.append(Posicion(e.ticker, e.tier, e.delta_evidencia, round(peso, 4), sector, hc))
        c.invertido = round(c.invertido + peso, 4)
        if sector != "SIN_SECTOR":
            por_sector[sector] = por_sector.get(sector, 0.0) + peso

    c.cash = round(1.0 - c.invertido, 4)
    return c
