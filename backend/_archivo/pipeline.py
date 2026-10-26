"""Cableado end-to-end del sistema nuevo (Etapas 3→6 sobre el ledger fiel).

Ata las piezas ya construidas: entrada + Filtro 0 → deep research (ficha) → PM →
deploy. Determinista y testeable con hechos INYECTADOS (el adapter de datos reales /
el LLM son edges aparte). El PM por defecto es un baseline determinista por mérito
(sin API); se puede inyectar el PM-LLM.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.ingreso import flujo
from backend.ingreso.filtro0 import HechosFiltro0
from backend.ingreso.universo import HechosUniverso
from backend.ledger import ficha
from backend.ledger.entidades import Estado, estado_desde_log, transicionar
from backend.ledger.models import NxFichaVersion
from backend.nucleo.constantes import MAX_POR_SUBSECTOR, MAX_POSICIONES, PISO_POSICION
from backend.seleccion.deploy import desplegar
from backend.seleccion.pm_loop import correr_pm
from backend.seleccion.validador import FACTOR_CAP, Candidata, LineaPropuesta


@dataclass
class Solicitud:
    ticker: str
    universo: HechosUniverso
    filtro0: HechosFiltro0
    nodo_id: int
    entrada_deep: object = None            # EntradaEmpresa; requerida si Filtro 0 = "investigar"
    sector: str | None = None
    factores: list = field(default_factory=list)
    fuente_ingreso: str = "manual"


def _norm(s):
    return s.strip().casefold() if isinstance(s, str) and s.strip() else "SIN_SECTOR"


def crear_proponente_merito(merito_por_ticker: dict, *, cash_objetivo: float,
                            piso: float = PISO_POSICION, factor_cap: float = FACTOR_CAP,
                            max_por_sector: int = MAX_POR_SUBSECTOR,
                            max_posiciones: int = MAX_POSICIONES):
    """PM baseline determinista: rankea por mérito y asigna peso dentro de todos los
    caps (hard cap, sector, factor, presupuesto por cash objetivo). Produce un mix
    válido por construcción — el validador lo confirma."""
    def _prop(candidatas: list[Candidata], errores_previos: list[str]) -> list[LineaPropuesta]:
        cs = sorted(candidatas, key=lambda c: -merito_por_ticker.get(c.ticker.upper(), 0.0))
        budget = 1.0 - cash_objetivo
        por_sector: dict[str, int] = {}
        por_factor: dict[str, float] = {}
        lineas: list[LineaPropuesta] = []
        for c in cs:
            if len(lineas) >= max_posiciones or budget < piso:
                break
            sec = _norm(c.sector)
            if por_sector.get(sec, 0) >= max_por_sector:
                continue
            facs = {f.strip().casefold() for f in c.factores if f and f.strip()}
            w = min(c.hard_cap, budget)
            for f in facs:
                w = min(w, factor_cap - por_factor.get(f, 0.0))
            w = math.floor(w * 1e6) / 1e6       # floor: nunca excede un cap por redondeo
            if w < piso - 1e-9:
                continue
            lineas.append(LineaPropuesta(c.ticker.upper(), w))
            budget -= w
            por_sector[sec] = por_sector.get(sec, 0) + 1
            for f in facs:
                por_factor[f] = por_factor.get(f, 0.0) + w
        return lineas
    return _prop


def _ultima_ficha(session: Session, ticker: str) -> NxFichaVersion | None:
    return session.execute(
        select(NxFichaVersion).where(NxFichaVersion.ticker == ticker.upper())
        .order_by(NxFichaVersion.version.desc())
    ).scalars().first()


def correr_ciclo(session: Session, solicitudes: list[Solicitud], *, precios: dict,
                 cash_objetivo: float, fecha, adv_usd: dict | None = None,
                 proponer=None, max_posiciones: int = 10) -> dict:
    """Corre un ciclo completo: por cada solicitud entrada→Filtro 0→(deep research);
    junta las Elegibles → PM → deploy. Devuelve el resumen."""
    por_ticker: dict[str, dict] = {}

    # --- Fase 1: entrada + Filtro 0 + deep research ---
    for s in solicitudes:
        r_ing = flujo.ingresar(session, ticker=s.ticker, universo=s.universo,
                               filtro0=s.filtro0, fecha=fecha, nodo_id=s.nodo_id,
                               fuente_ingreso=s.fuente_ingreso, sector=s.sector)
        por_ticker[s.ticker.upper()] = {"filtro0": r_ing}
        if r_ing["resultado"] == "investigar" and s.entrada_deep is not None:
            r_dr = ficha.correr_deep_research(session, ticker=s.ticker,
                                              entrada=s.entrada_deep, fecha=fecha)
            por_ticker[s.ticker.upper()]["deep"] = r_dr

    # --- Fase 2: juntar Elegibles → Candidatas + mérito ---
    candidatas: list[Candidata] = []
    merito: dict[str, float] = {}
    for s in solicitudes:
        t = s.ticker.upper()
        if estado_desde_log(session, t) == Estado.ELEGIBLE.value:
            fv = _ultima_ficha(session, t)
            if fv is None or fv.hard_cap is None:
                continue
            candidatas.append(Candidata(t, elegible=True, hard_cap=fv.hard_cap,
                                        sector=s.sector, factores=list(s.factores)))
            merito[t] = fv.merito or 0.0

    # --- Fase 3: PM ---
    prop = proponer or crear_proponente_merito(merito, cash_objetivo=cash_objetivo,
                                               max_posiciones=max_posiciones)
    r_pm = correr_pm(candidatas, cash_objetivo=cash_objetivo, proponer=prop,
                     max_posiciones=max_posiciones)

    # --- Fase 4: deploy + transición de estado (Elegible → Posición / Watchlist) ---
    r_dep = None
    if r_pm["ok"] and r_pm["mix"] is not None:
        r_dep = desplegar(session, mix=r_pm["mix"], precios=precios, fecha=fecha,
                          adv_usd=adv_usd, candidatas=candidatas, cash_objetivo=cash_objetivo)
        for c in candidatas:
            destino = Estado.POSICION if c.ticker in r_pm["mix"] else Estado.WATCHLIST
            transicionar(session, ticker=c.ticker, estado_nuevo=destino,
                         disparado_por="pm", motivo="selección PM", fecha=fecha)

    return {"por_ticker": por_ticker, "elegibles": [c.ticker for c in candidatas],
            "pm": r_pm, "deploy": r_dep}
