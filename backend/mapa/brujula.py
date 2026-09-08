"""Brújula sectorial — territorios-cuello de arranque (Bloque B, §9.1).

NO es el contenido del mapa (los nodos los puebla el Discovery con hechos). Es la
brújula que le dice al Discovery POR DÓNDE empezar a buscar firmas de hecho. Es
worldview del operador, cerrado tras doble triangulación.

Regla de unidad (§9.1): lista TERRITORIOS-CUELLO, no nodos ni candidatas. El
costo NO escala con la cantidad de territorios (el barrido es barato); escala con
candidatas investigadas a profundidad. La brújula NO se prioriza con score: el
estado que la tabla determinista asigna a cada nodo (§3.2) y la frecuencia por
estado (§6.1) ordenan solos. La prioridad-de-cartera del operador vive en la capa
de selección (PM, Bloque C), NO acá.

CONFIGURABLE: igual que MAX_WATCHLIST, esta lista es un parámetro que el operador
ajusta. Es lista de ARRANQUE — el Discovery la corrige al poblar nodos con hechos.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class EstadoTerritorio(str, Enum):
    ACTIVO = "activo"              # el Discovery arranca acá (§9.1.1).
    WATCHLIST = "watchlist"        # promesa lejana, no gasta barrido hasta entrar en ventana (§9.1.2).
    VIGILAR = "vigilar"            # sin firma vigente; se abre si aparece, cero costo (§9.1.3).
    ARCHIVADO = "archivado"        # reabrible; conserva histórico (§9.1.4).


@dataclass
class Territorio:
    nombre: str
    cluster: str
    factor_macro: str | None = None       # etiqueta visible NO-decisoria (§3.1).
    estado: EstadoTerritorio = EstadoTerritorio.ACTIVO
    subnodos: list[str] = field(default_factory=list)  # sub-cuellos aguas arriba conocidos.
    nota: str | None = None


# Factores macro recurrentes (etiquetas visibles, NUNCA entran a una fórmula).
FM_HYPERSCALER = "capex hyperscaler"
FM_DEFENSA = "gasto soberano defensa"
FM_EXPORT = "export-control / precio spot"

# ----------------------------- §9.1.1 Territorios ACTIVOS -----------------------------
BRUJULA: list[Territorio] = [
    # Clúster datacenter / cómputo (todos cuelgan de capex hyperscaler).
    Territorio("Empaque avanzado de chips (CoWoS/interposers/TSV-bonders)", "datacenter", FM_HYPERSCALER),
    Territorio("HBM", "datacenter", FM_HYPERSCALER),
    Territorio("Óptica de datacenter (transceivers 800G/1.6T)", "datacenter", FM_HYPERSCALER,
               subnodos=["EML/InP lasers", "sustrato InP/indio"]),
    Territorio("Refrigeración líquida (cold plates/CDUs/quick-disconnects/fluidos dieléctricos)",
               "datacenter", FM_HYPERSCALER),
    Territorio("Equipo de fabricación de semis (litografía EUV/deposición/metrología)", "datacenter", FM_HYPERSCALER),
    Territorio("Turbinas de gas large-frame", "datacenter", FM_HYPERSCALER),
    # Insumos upstream de semis (región-ciega destapada por la triangulación — fuentes asiáticas).
    Territorio("Photoresist (Shin-Etsu/TOK ~80% ArF)", "semis_upstream", FM_HYPERSCALER),
    Territorio("Solvente PGME/PGMEA", "semis_upstream", FM_HYPERSCALER, nota="anida bajo photoresist Y HBM"),
    Territorio("High-purity quartz / crucibles CZ (Spruce Pine)", "semis_upstream", FM_HYPERSCALER),
    # Clúster energía / grid (cuelga del capex datacenter — la concentración de factor más fuerte del mapa).
    Territorio("Transformadores de alta tensión", "energia_grid", FM_HYPERSCALER,
               subnodos=["GOES (acero eléctrico grano orientado, Cleveland-Cliffs)"]),
    Territorio("Switchgear MV/HV", "energia_grid", FM_HYPERSCALER),
    Territorio("Generación on-site / BYOP", "energia_grid", FM_HYPERSCALER,
               subnodos=["fuel cells (Bloom)", "reciprocating gas engines"]),
    Territorio("HALEU (uranio de alto ensayo, enrichment + fuel fabrication)", "energia_grid", FM_HYPERSCALER),
    # Cuello de oferta restringida (export-control / precio spot).
    Territorio("Galio", "minerales", FM_EXPORT),
    Territorio("Germanio", "minerales", FM_EXPORT),
    Territorio("Tierras raras pesadas (disprosio/terbio) e imanes NdFeB", "minerales", FM_EXPORT),
    Territorio("Antimonio", "minerales", FM_EXPORT),
    Territorio("Tungsteno", "minerales", FM_EXPORT, nota="también insumo de fusión"),
    Territorio("Graphite anode ex-China", "minerales", FM_EXPORT),
    Territorio("Fosfato / DAP", "minerales", FM_EXPORT, nota="perfil large-cap tipo-commodity, no pala-asimétrica"),
    # Quantum (SOLO por sub-cuello físico, nunca como producto).
    Territorio("Dilution refrigerators / criogenia", "quantum", subnodos=["cryo-CMOS/wiring criogénico (promesa)"]),
    Territorio("Helio-3 para refrigeradores de dilución", "quantum",
               estado=EstadoTerritorio.WATCHLIST, nota="contrato lunar 2028, sin shortage en tierra hoy"),
    # Defensa / espacio (por cuello concreto con contrato/backlog, NUNCA por la etiqueta).
    Territorio("Solid rocket motors / propelente", "defensa", FM_DEFENSA, nota="Anduril 3er proveedor US"),
    Territorio("Mini-turbojets para drones de largo alcance", "defensa", FM_DEFENSA),
    Territorio("Capacidad de lanzamiento para constelaciones", "espacio", FM_DEFENSA),
    Territorio("Smallsat propulsion / Hall-effect thrusters", "espacio", FM_DEFENSA),
    Territorio("Rad-hard electronics", "defensa", FM_DEFENSA, estado=EstadoTerritorio.VIGILAR),
    # Robótica (subnodos, reformulado desde "humanoide" que era narrativa).
    Territorio("Joint actuators bajo contrato (Schaeffler/Humanoid)", "robotica", nota="preferred-supply >50% 2031, take-or-pay"),
    Territorio("Harmonic / RV reducers (Nabtesco/Harmonic Drive)", "robotica", nota="plena capacidad, lead-times 14m"),
    Territorio("Planetary roller screws", "robotica", estado=EstadoTerritorio.WATCHLIST, nota="el más agudo (McKinsey)"),
    # Fotónica y fabricación de bio.
    Territorio("Fotónica / co-packaged optics (CPO)", "fotonica", FM_HYPERSCALER, nota="transceivers ya monetizan; CPO 2026-2027"),
    Territorio("Viral vectors / plasmid DNA GMP", "bio", nota="la pala de fabricación de bio, firma caliente"),
    # Agua.
    Territorio("Ultrapure water para fabs + constraint hídrico de datacenters", "agua", FM_HYPERSCALER,
               subnodos=["membranes", "reverse osmosis", "ion exchange", "reúso/reclamation"]),
]

# ----------------------------- §9.1.2 Watchlist — promesa lejana -----------------------------
BRUJULA_WATCHLIST: list[Territorio] = [
    Territorio("HTS REBCO tape (CFS/Type One)", "fusion", estado=EstadoTerritorio.WATCHLIST, nota="la mejor firma del grupo"),
    Territorio("Tungsteno plasma-facing", "fusion", estado=EstadoTerritorio.WATCHLIST),
    Territorio("Nb3Sn superconductor", "fusion", estado=EstadoTerritorio.WATCHLIST),
    Territorio("Lithium-6 / tritium breeding", "fusion", estado=EstadoTerritorio.WATCHLIST),
    Territorio("SMR-como-generación", "energia_grid", FM_HYPERSCALER, estado=EstadoTerritorio.WATCHLIST,
               nota="offtake 45GW pero monetiza ~2031; su combustible HALEU ya está activo"),
    Territorio("Grid-tie batteries", "energia_grid", estado=EstadoTerritorio.WATCHLIST),
    Territorio("PPA para cátodos LFP", "energia_grid", estado=EstadoTerritorio.WATCHLIST),
    Territorio("Fermentación industrial a escala", "bio", estado=EstadoTerritorio.WATCHLIST),
]

# ----------------------------- §9.1.4 Archivado reabrible -----------------------------
BRUJULA_ARCHIVADO: list[Territorio] = [
    Territorio("CDMO de péptidos / fill-finish GLP-1", "bio", estado=EstadoTerritorio.ARCHIVADO,
               nota="firma real (take-or-pay, lead-times 18-24m) pero FDA declaró resuelto el shortage (2024/2025)"),
]

# Nota de diseño (cerrada, §9.1.4): el barrido del Discovery DEBE incluir fuentes en
# japonés/coreano/chino/alemán. La búsqueda solo-inglés ocultó photoresist/PGMEA.


def territorios_activos() -> list[Territorio]:
    return [t for t in BRUJULA if t.estado == EstadoTerritorio.ACTIVO]


def concentracion_factor_macro() -> dict[str, int]:
    """Cuántos territorios activos cuelgan de cada factor_macro. Insumo de
    visibilidad (NO decisorio) — la concentración capex hyperscaler es la más
    fuerte del mapa (§6.3 de C: riesgo residual aceptado)."""
    conteo: dict[str, int] = {}
    for t in territorios_activos():
        if t.factor_macro:
            conteo[t.factor_macro] = conteo.get(t.factor_macro, 0) + 1
    return dict(sorted(conteo.items(), key=lambda kv: -kv[1]))
