"""Tests de identidad + máquina de estados (Art. 5) + mapa persistido (Etapa 2).

SQLite in-memory — no toca data/borja.db.
"""
from datetime import date

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.ledger import entidades as e
from backend.ledger.entidades import Estado
from backend.ledger.models import NxEmpresaEvento, NxEmpresaNodo, crear_tablas


@pytest.fixture
def sesion():
    engine = create_engine("sqlite:///:memory:", future=True)
    crear_tablas(engine)
    with Session(engine, future=True) as s:
        yield s


def _n_eventos(sesion, ticker):
    return sesion.execute(
        select(func.count()).select_from(NxEmpresaEvento)
        .where(NxEmpresaEvento.ticker == ticker)
    ).scalar_one()


def test_crear_candidata(sesion):
    emp = e.crear_candidata(sesion, ticker="acme", fecha=date(2026, 1, 1), sector="AI infra")
    assert emp.estado == Estado.CANDIDATA.value
    assert emp.ticker == "ACME"                       # uppercase
    assert _n_eventos(sesion, "ACME") == 1
    assert e.estado_desde_log(sesion, "ACME") == Estado.CANDIDATA.value


def test_transicion_valida_actualiza_estado_y_log(sesion):
    e.crear_candidata(sesion, ticker="ACME", fecha=date(2026, 1, 1))
    e.transicionar(sesion, ticker="ACME", estado_nuevo=Estado.EN_DEEP_RESEARCH,
                   disparado_por="regla", fecha=date(2026, 1, 2))
    emp = e.transicionar(sesion, ticker="ACME", estado_nuevo=Estado.ELEGIBLE,
                         disparado_por="regla", fecha=date(2026, 1, 3))
    assert emp.estado == Estado.ELEGIBLE.value
    assert e.estado_desde_log(sesion, "ACME") == Estado.ELEGIBLE.value  # cache == log
    assert _n_eventos(sesion, "ACME") == 3


def test_transicion_invalida_rechaza(sesion):
    e.crear_candidata(sesion, ticker="ACME", fecha=date(2026, 1, 1))
    with pytest.raises(ValueError, match="no permitida"):
        e.transicionar(sesion, ticker="ACME", estado_nuevo=Estado.POSICION,
                       disparado_por="pm", fecha=date(2026, 1, 2))


def test_happy_path_a_posicion(sesion):
    e.crear_candidata(sesion, ticker="ACME", fecha=date(2026, 1, 1))
    for est, d in [(Estado.EN_DEEP_RESEARCH, 2), (Estado.ELEGIBLE, 3), (Estado.POSICION, 4)]:
        e.transicionar(sesion, ticker="ACME", estado_nuevo=est, disparado_por="pm",
                       fecha=date(2026, 1, d))
    assert e.estado_desde_log(sesion, "ACME") == Estado.POSICION.value


def _hasta_archivada(sesion, ticker, base_day):
    """Lleva un ticker vivo hasta Archivada por la vía de tesis rota."""
    e.transicionar(sesion, ticker=ticker, estado_nuevo=Estado.EN_DEEP_RESEARCH,
                   disparado_por="regla", fecha=date(2026, 1, base_day))
    e.transicionar(sesion, ticker=ticker, estado_nuevo=Estado.ELEGIBLE,
                   disparado_por="regla", fecha=date(2026, 1, base_day + 1))
    e.transicionar(sesion, ticker=ticker, estado_nuevo=Estado.POSICION,
                   disparado_por="pm", fecha=date(2026, 1, base_day + 2))
    e.transicionar(sesion, ticker=ticker, estado_nuevo=Estado.TESIS_INVALIDADA,
                   disparado_por="regla", fecha=date(2026, 1, base_day + 3))
    e.transicionar(sesion, ticker=ticker, estado_nuevo=Estado.ARCHIVADA,
                   disparado_por="regla", fecha=date(2026, 1, base_day + 4))


def test_candado_b_bloquea_segunda_reentrada(sesion):
    e.crear_candidata(sesion, ticker="ACME", fecha=date(2026, 1, 1))
    _hasta_archivada(sesion, "ACME", 2)
    # 1ª re-entrada: OK
    emp = e.crear_candidata(sesion, ticker="ACME", fecha=date(2026, 1, 10),
                            motivo="tesis reconstruida")
    assert emp.estado == Estado.CANDIDATA.value
    assert emp.reentradas_usadas == 1
    # Vuelve a Archivada y se intenta 2ª re-entrada → Candado B
    _hasta_archivada(sesion, "ACME", 11)
    with pytest.raises(ValueError, match="Candado B"):
        e.crear_candidata(sesion, ticker="ACME", fecha=date(2026, 1, 20))


def test_vinculo_nodo_idempotente_y_persiste(sesion):
    nodo = e.crear_nodo(sesion, nombre="HBM", cluster="datacenter",
                        factor_macro="capex hyperscaler")
    e.crear_candidata(sesion, ticker="ACME", fecha=date(2026, 1, 1), nodo_id=nodo.id)
    e.vincular_nodo(sesion, ticker="ACME", nodo_id=nodo.id)   # segundo intento
    n = sesion.execute(
        select(func.count()).select_from(NxEmpresaNodo)
        .where(NxEmpresaNodo.ticker == "ACME")
    ).scalar_one()
    assert n == 1   # no se duplica


def test_descartada_vuelve_a_candidata_sin_gastar_reentrada(sesion):
    e.crear_candidata(sesion, ticker="ACME", fecha=date(2026, 1, 1))
    e.transicionar(sesion, ticker="ACME", estado_nuevo=Estado.DESCARTADA,
                   disparado_por="regla", fecha=date(2026, 1, 2))
    emp = e.crear_candidata(sesion, ticker="ACME", fecha=date(2026, 1, 3))
    assert emp.estado == Estado.CANDIDATA.value
    assert emp.reentradas_usadas == 0   # Descartada→Candidata no gasta Candado B
