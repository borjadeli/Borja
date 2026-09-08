"""Deep research → ficha versionada (Etapa 4a).

Enchufa el núcleo que YA existe (`flujo.evaluar_empresa`) al ledger: corre el
análisis determinista sobre una empresa En-deep-research, persiste una **versión de
ficha** + sus hechos, y transiciona el estado según la decisión. SIN LLM en esta
capa (recibe una EntradaEmpresa ya armada; el extractor/LLM vive aguas arriba).
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.ledger.entidades import Estado, transicionar
from backend.ledger.models import NxFichaVersion, NxHecho
from backend.nucleo.flujo import EntradaEmpresa, evaluar_empresa

DECISION_A_ESTADO = {
    "candidata": Estado.ELEGIBLE,
    "watchlist": Estado.ESPERANDO_EVIDENCIA,   # gate "todavía-no" → espera el hecho
    "rechazo": Estado.DESCARTADA,
}


def _proxima_version(session: Session, ticker: str) -> int:
    m = session.execute(
        select(func.max(NxFichaVersion.version)).where(NxFichaVersion.ticker == ticker.upper())
    ).scalar_one_or_none()
    return (m or 0) + 1


def persistir_ficha(session: Session, *, ticker: str, resultado: dict, precio: float | None,
                    bull: float | None, bear: float | None, fecha: date,
                    base: float | None = None, hechos: dict | None = None,
                    version: int | None = None) -> NxFichaVersion:
    """Crea una NxFichaVersion desde el dict de evaluar_empresa + escenarios, y
    persiste los hechos que la alimentaron. Determinista y puro (DB)."""
    ticker = ticker.upper()
    version = version or _proxima_version(session, ticker)
    arq = (resultado.get("arquetipo") or {}).get("arquetipo")
    fv = NxFichaVersion(
        ticker=ticker, version=version, fecha=fecha, arquetipo=arq,
        quality_tier=(resultado.get("quality") or {}).get("tier"),
        fragility_score=(resultado.get("fragility") or {}).get("score"),
        precio=precio, bull=bull, base=base, bear=bear,
        asimetria=resultado.get("asimetria"), merito=resultado.get("merito"),
        cap_celda=resultado.get("cap_celda"), hard_cap=resultado.get("hard_cap"),
        es_binary=(arq == "Binary"),
        decision=resultado["decision"], motivo=resultado.get("motivo"),
    )
    session.add(fv)
    session.flush()
    for campo, valor in (hechos or {}).items():
        session.add(NxHecho(ficha_version_id=fv.id, campo=campo, valor=str(valor)))
    session.flush()
    return fv


def correr_deep_research(session: Session, *, ticker: str, entrada: EntradaEmpresa,
                         fecha: date, hechos: dict | None = None) -> dict:
    """Corre el núcleo sobre una empresa En-deep-research, persiste la ficha y
    transiciona según la decisión (candidata→Elegible, watchlist→Esperando-evidencia,
    rechazo→Descartada). Devuelve {decision, ficha_version_id, estado, resultado}."""
    res = evaluar_empresa(entrada)
    fv = persistir_ficha(session, ticker=ticker, resultado=res, precio=entrada.precio,
                         bull=entrada.bull, bear=entrada.bear, fecha=fecha, hechos=hechos)
    destino = DECISION_A_ESTADO[res["decision"]]
    transicionar(session, ticker=ticker, estado_nuevo=destino, disparado_por="regla",
                 motivo=res.get("motivo") or res["decision"], fecha=fecha,
                 ficha_version_id=fv.id)
    return {"decision": res["decision"], "ficha_version_id": fv.id,
            "estado": destino.value, "resultado": res}
