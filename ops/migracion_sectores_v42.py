"""Migración sectores v4.2 — subdivisión AI infra + nuevos sectores.

Crea:
- AI infra — Fotónica + conectividad (cluster_driver=capex_AI)
- AI infra — Cooling + thermal management (cluster_driver=capex_AI)
- AI infra — Electrical infrastructure (cluster_driver=capex_AI)
- AI infra — Semicap + advanced packaging (cluster_driver=capex_AI)
- Power Generation con expo data center (cluster_driver=capex_AI)
- Healthcare Technology con AI (sin cluster por ahora)

Reasigna fichas activas en "AI infra" a los sub-temas según su driver_macro descriptivo:
- CRDO, ALAB, COHR → Fotónica + conectividad
- VRT → Cooling + thermal management
- KLIC → Semicap + advanced packaging

Mantiene "AI infra" como sector legacy (sin tocar) para que cualquier ficha
no migrada manualmente siga funcionando.
"""
from __future__ import annotations

from backend.database import session_scope
from backend.models import Ficha, Sector
from backend.utils import get_logger, utcnow

log = get_logger(__name__)


SECTORES_NUEVOS = [
    {
        "nombre": "AI infra — Fotónica + conectividad",
        "momentum": "Favorable",
        "prioridad": "alta",
        "horizonte": "6-12 meses",
        "cluster_driver": "capex_AI",
        "notas": "Co-packaged optics, optical transceivers, silicon photonics. Cuello de interconexión a alta velocidad.",
    },
    {
        "nombre": "AI infra — Cooling + thermal management",
        "momentum": "Favorable",
        "prioridad": "alta",
        "horizonte": "6-12 meses",
        "cluster_driver": "capex_AI",
        "notas": "Liquid cooling, immersion cooling, two-phase. Restricción dura desde Blackwell de Nvidia.",
    },
    {
        "nombre": "AI infra — Electrical infrastructure",
        "momentum": "Favorable",
        "prioridad": "alta",
        "horizonte": "6-18 meses",
        "cluster_driver": "capex_AI",
        "notas": "Transformers, switchgear, substations, backup power, grid interconnection.",
    },
    {
        "nombre": "AI infra — Semicap + advanced packaging",
        "momentum": "Favorable",
        "prioridad": "media-alta",
        "horizonte": "6-18 meses",
        "cluster_driver": "capex_AI",
        "notas": "Metrología, inspección, advanced packaging (CoWoS, hybrid bonding), foto-máscaras.",
    },
    {
        "nombre": "Power Generation con expo data center",
        "momentum": "Favorable",
        "prioridad": "media-alta",
        "horizonte": "12-24 meses",
        "cluster_driver": "capex_AI",
        "notas": "Operadores de generación con PPAs directos con Microsoft/Amazon/Google/Meta. Gas natural midstream con demanda data center. SMR si aparecen candidatas convexas.",
    },
    {
        "nombre": "Healthcare Technology con AI",
        "momentum": "Neutral",
        "prioridad": "media",
        "horizonte": "18-36 meses",
        "cluster_driver": None,
        "notas": "Medical devices con AI integrada, healthcare IT, drug discovery tools con AI. Sizing reducido los primeros 6 meses (max 70% techo R).",
    },
]


# Reasignación de fichas activas en "AI infra" a sub-temas.
REASIGNACION_FICHAS = {
    "CRDO": "AI infra — Fotónica + conectividad",
    "ALAB": "AI infra — Fotónica + conectividad",
    "COHR": "AI infra — Fotónica + conectividad",
    "VRT": "AI infra — Cooling + thermal management",
    "KLIC": "AI infra — Semicap + advanced packaging",
}


def crear_sectores() -> dict:
    creados: list[str] = []
    actualizados: list[str] = []
    with session_scope() as s:
        for spec in SECTORES_NUEVOS:
            existente = s.query(Sector).filter_by(nombre=spec["nombre"]).first()
            if existente:
                # Actualizar campos clave si ya existe
                existente.momentum = spec["momentum"]
                existente.prioridad = spec["prioridad"]
                existente.horizonte = spec["horizonte"]
                existente.cluster_driver = spec["cluster_driver"]
                existente.notas = spec["notas"]
                existente.ultima_actualizacion = utcnow()
                actualizados.append(spec["nombre"])
            else:
                s.add(Sector(
                    nombre=spec["nombre"],
                    momentum=spec["momentum"],
                    momentum_origen="manual",
                    prioridad=spec["prioridad"],
                    horizonte=spec["horizonte"],
                    cluster_driver=spec["cluster_driver"],
                    notas=spec["notas"],
                    ultima_actualizacion=utcnow(),
                ))
                creados.append(spec["nombre"])
    return {"creados": creados, "actualizados": actualizados}


def reasignar_fichas() -> dict:
    movidos: list[dict] = []
    skipped: list[str] = []
    with session_scope() as s:
        for ticker, sector_destino in REASIGNACION_FICHAS.items():
            f = s.query(Ficha).filter_by(ticker=ticker).first()
            if f is None:
                skipped.append(f"{ticker} (no existe)")
                continue
            if f.sector == sector_destino:
                skipped.append(f"{ticker} (ya en {sector_destino})")
                continue
            sector_destino_row = s.query(Sector).filter_by(nombre=sector_destino).first()
            if sector_destino_row is None:
                skipped.append(f"{ticker} (sector destino {sector_destino} no existe)")
                continue
            origen = f.sector
            f.sector = sector_destino
            movidos.append({"ticker": ticker, "de": origen, "a": sector_destino})
    return {"movidos": movidos, "skipped": skipped}


def correr_migracion() -> dict:
    log.info("migracion_sectores_v42 — arrancando")
    paso1 = crear_sectores()
    log.info("sectores creados=%d actualizados=%d", len(paso1["creados"]), len(paso1["actualizados"]))
    paso2 = reasignar_fichas()
    log.info("fichas movidas=%d skipped=%d", len(paso2["movidos"]), len(paso2["skipped"]))
    return {"sectores": paso1, "fichas": paso2}


if __name__ == "__main__":
    import json
    res = correr_migracion()
    print(json.dumps(res, indent=2, default=str))
