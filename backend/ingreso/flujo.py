"""Orquestación de la Etapa 3 sobre el ledger.

Entrada (manual o discovery) → filtro de universo → crear Candidata → Filtro 0 →
transición de estado. Más el hook de re-emisión por cambio de NODO (Art. 5.3): las
descartadas vinculadas a un nodo que cambió se re-chequean barato (Filtro 0, sin LLM).
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.ingreso.filtro0 import HechosFiltro0, evaluar_filtro0
from backend.ingreso.universo import HechosUniverso, evaluar_universo
from backend.ledger.entidades import Estado, crear_candidata, transicionar
from backend.ledger.models import NxEmpresa, NxEmpresaNodo

VEREDICTO_A_ESTADO = {
    "descartar": Estado.DESCARTADA,
    "esperar-evidencia": Estado.ESPERANDO_EVIDENCIA,
    "investigar": Estado.EN_DEEP_RESEARCH,
}


def ingresar(session: Session, *, ticker: str, universo: HechosUniverso,
             filtro0: HechosFiltro0, fecha: date, nodo_id: int | None = None,
             fuente_ingreso: str = "manual", nombre: str | None = None,
             sector: str | None = None) -> dict:
    """Corre una candidata por universo + Filtro 0 y la deja en el estado que toque.

    Devuelve {resultado, motivo?}. 'fuera_universo' → NO se crea Candidata.
    """
    # nodo_id es la única fuente de verdad del vínculo (evita tiene_nodo contradictorio).
    universo = replace(universo, tiene_nodo=nodo_id is not None)
    u = evaluar_universo(universo)
    if not u.admisible:
        return {"resultado": "fuera_universo", "motivos": u.motivos}

    crear_candidata(session, ticker=ticker, fecha=fecha, nodo_id=nodo_id,
                    fuente_ingreso=fuente_ingreso, nombre=nombre, sector=sector,
                    jurisdiccion=universo.jurisdiccion)

    f = evaluar_filtro0(filtro0)
    transicionar(session, ticker=ticker, estado_nuevo=VEREDICTO_A_ESTADO[f.veredicto],
                 disparado_por="regla", motivo=f.motivo, fecha=fecha)
    return {"resultado": f.veredicto, "motivo": f.motivo}


def reemitir_por_nodo(session: Session, *, nodo_id: int,
                      filtro0_por_ticker: dict[str, HechosFiltro0], fecha: date) -> dict:
    """Hook Art. 5.3: un nodo cambió → re-chequea (Filtro 0 barato) las DESCARTADAS
    vinculadas. Si el veredicto mejora, revive Descartada → Candidata → destino.

    filtro0_por_ticker: hechos frescos por ticker. Los que no estén se saltean.
    Devuelve {ticker: veredicto_nuevo}.
    """
    resultados: dict[str, str] = {}
    vinculos = session.execute(
        select(NxEmpresaNodo).where(NxEmpresaNodo.nodo_id == nodo_id)
    ).scalars().all()

    for v in vinculos:
        emp = session.get(NxEmpresa, v.ticker)
        if emp is None or emp.estado != Estado.DESCARTADA.value:
            continue
        if not emp.descarte_reversible:
            continue   # descarte duro (governance/fraude) NO revive por nodo
        h = filtro0_por_ticker.get(v.ticker)
        if h is None:
            continue
        f = evaluar_filtro0(h)
        if f.veredicto == "descartar":
            resultados[v.ticker] = "sigue-descartada"
            continue
        # Revive: Descartada → Candidata (no gasta Candado B) → destino del veredicto.
        transicionar(session, ticker=v.ticker, estado_nuevo=Estado.CANDIDATA,
                     disparado_por="regla",
                     motivo=f"re-emisión por cambio de nodo {nodo_id}", fecha=fecha)
        transicionar(session, ticker=v.ticker, estado_nuevo=VEREDICTO_A_ESTADO[f.veredicto],
                     disparado_por="regla", motivo=f.motivo, fecha=fecha)
        resultados[v.ticker] = f.veredicto

    return resultados
