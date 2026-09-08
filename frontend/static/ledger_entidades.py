"""Identidad, máquina de estados (Art. 5) y mapa persistido — sobre el ledger.

Reusa VIDAS_REENTRADA del núcleo (no redefine constantes). El estado actual de una
empresa es la proyección del log de eventos (nx_empresa_evento); `nx_empresa.estado`
es un cache que se actualiza en la misma transacción. Transiciones no permitidas se
rechazan (fallo seguro, Art. 8).
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.ledger.models import (
    NxEmpresa,
    NxEmpresaEvento,
    NxEmpresaNodo,
    NxNodo,
)
from backend.nucleo.constantes import VIDAS_REENTRADA


class Estado(str, Enum):
    CANDIDATA = "Candidata"
    DESCARTADA = "Descartada"
    ESPERANDO_EVIDENCIA = "Esperando-evidencia"
    EN_DEEP_RESEARCH = "En-deep-research"
    ELEGIBLE = "Elegible"
    WATCHLIST = "Watchlist"
    POSICION = "Posicion"
    TESIS_INVALIDADA = "Tesis-invalidada"
    ARCHIVADA = "Archivada"


# Transiciones permitidas (Art. 5.2). Claves/valores como strings.
TRANSICIONES: dict[str, set[str]] = {
    Estado.CANDIDATA.value: {Estado.DESCARTADA.value, Estado.ESPERANDO_EVIDENCIA.value,
                             Estado.EN_DEEP_RESEARCH.value},
    Estado.ESPERANDO_EVIDENCIA.value: {Estado.EN_DEEP_RESEARCH.value, Estado.DESCARTADA.value,
                                       Estado.ARCHIVADA.value},
    Estado.EN_DEEP_RESEARCH.value: {Estado.ELEGIBLE.value, Estado.DESCARTADA.value,
                                    Estado.ESPERANDO_EVIDENCIA.value},
    Estado.ELEGIBLE.value: {Estado.POSICION.value, Estado.WATCHLIST.value},
    Estado.WATCHLIST.value: {Estado.ELEGIBLE.value, Estado.POSICION.value,
                             Estado.ESPERANDO_EVIDENCIA.value, Estado.ARCHIVADA.value},
    Estado.POSICION.value: {Estado.TESIS_INVALIDADA.value, Estado.WATCHLIST.value},
    Estado.TESIS_INVALIDADA.value: {Estado.ARCHIVADA.value},
    Estado.DESCARTADA.value: {Estado.CANDIDATA.value},   # fría, nuevo hecho
    Estado.ARCHIVADA.value: {Estado.CANDIDATA.value},    # re-entrada limitada (Candado B)
}


def _v(e) -> str:
    return e.value if isinstance(e, Estado) else str(e)


def _dt(f) -> datetime:
    return f if isinstance(f, datetime) else datetime(f.year, f.month, f.day)


def _append_evento(session: Session, ticker: str, anterior: str | None, nuevo: str,
                   disparado_por: str, motivo: str | None, fecha: datetime,
                   ficha_version_id: int | None = None) -> NxEmpresaEvento:
    ev = NxEmpresaEvento(ticker=ticker, estado_anterior=anterior, estado_nuevo=nuevo,
                         disparado_por=disparado_por, motivo=motivo, fecha=fecha,
                         ficha_version_id=ficha_version_id)
    session.add(ev)
    session.flush()
    return ev


def crear_candidata(session: Session, *, ticker: str, fecha: date, nombre: str | None = None,
                    sector: str | None = None, jurisdiccion: str | None = None,
                    exchange: str | None = None, fuente_ingreso: str = "manual",
                    nodo_id: int | None = None, motivo: str | None = None) -> NxEmpresa:
    """Ingresa (o re-ingresa) un ticker como Candidata. Si ya existe, es una
    transición a Candidata (con Candado B si venía de Archivada)."""
    ticker = ticker.upper()
    emp = session.get(NxEmpresa, ticker)
    if emp is None:
        emp = NxEmpresa(ticker=ticker, nombre=nombre, sector=sector, jurisdiccion=jurisdiccion,
                        exchange=exchange, estado=Estado.CANDIDATA.value,
                        fuente_ingreso=fuente_ingreso, fecha_ingreso=fecha, reentradas_usadas=0)
        session.add(emp)
        session.flush()
        _append_evento(session, ticker, None, Estado.CANDIDATA.value, "sistema",
                       motivo or "ingreso", _dt(fecha))
    else:
        transicionar(session, ticker=ticker, estado_nuevo=Estado.CANDIDATA,
                     disparado_por="sistema", motivo=motivo or "re-ingreso", fecha=fecha)
    if nodo_id is not None:
        vincular_nodo(session, ticker=ticker, nodo_id=nodo_id, es_primario=True)
    return emp


def transicionar(session: Session, *, ticker: str, estado_nuevo, disparado_por: str,
                 fecha: date, motivo: str | None = None,
                 ficha_version_id: int | None = None) -> NxEmpresa:
    """Cambia el estado de una empresa validando el Art. 5.2. Append al log +
    actualiza el cache. Rechaza transiciones no permitidas y el 2º re-ingreso
    (Candado B)."""
    ticker = ticker.upper()
    emp = session.get(NxEmpresa, ticker)
    if emp is None:
        raise ValueError(f"empresa inexistente: {ticker}")
    actual = emp.estado
    destino = _v(estado_nuevo)
    if destino not in TRANSICIONES.get(actual, set()):
        raise ValueError(f"transición no permitida: {actual} → {destino}")
    # Candado B: re-entrada Archivada → Candidata, máx VIDAS_REENTRADA.
    if actual == Estado.ARCHIVADA.value and destino == Estado.CANDIDATA.value:
        if emp.reentradas_usadas >= VIDAS_REENTRADA:
            raise ValueError(
                f"Candado B: {ticker} ya usó su re-entrada (máx {VIDAS_REENTRADA})")
        emp.reentradas_usadas += 1
    _append_evento(session, ticker, actual, destino, disparado_por, motivo, _dt(fecha),
                   ficha_version_id)
    emp.estado = destino
    session.flush()
    return emp


def estado_desde_log(session: Session, ticker: str) -> str | None:
    """Estado actual reconstruido desde el log (para reconciliar contra el cache)."""
    ev = session.execute(
        select(NxEmpresaEvento).where(NxEmpresaEvento.ticker == ticker.upper())
        .order_by(NxEmpresaEvento.id.desc())
    ).scalars().first()
    return ev.estado_nuevo if ev else None


# ---------------------------- Mapa ----------------------------

def crear_nodo(session: Session, *, nombre: str, cluster: str | None = None,
               factor_macro: str | None = None, estado_confirmacion: str = "promesa",
               nota: str | None = None) -> NxNodo:
    n = NxNodo(nombre=nombre, cluster=cluster, factor_macro=factor_macro,
               estado_confirmacion=estado_confirmacion, nota=nota)
    session.add(n)
    session.flush()
    return n


def vincular_nodo(session: Session, *, ticker: str, nodo_id: int,
                  es_primario: bool = False) -> NxEmpresaNodo:
    """Vincula empresa↔nodo. Idempotente; NUNCA borra (Art. 5.3)."""
    ticker = ticker.upper()
    existe = session.execute(
        select(NxEmpresaNodo).where(NxEmpresaNodo.ticker == ticker,
                                    NxEmpresaNodo.nodo_id == nodo_id)
    ).scalar_one_or_none()
    if existe:
        return existe
    v = NxEmpresaNodo(ticker=ticker, nodo_id=nodo_id, es_primario=es_primario)
    session.add(v)
    session.flush()
    return v
