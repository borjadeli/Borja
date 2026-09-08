"""Tests de la ficha versionada (Etapa 4a): persistencia + enchufe del núcleo.

Incluye un test de INTEGRACIÓN que corre el núcleo REAL (evaluar_empresa) sobre una
EntradaEmpresa que pasa el gate. SQLite in-memory — no toca borja.db.
"""
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.ledger import entidades as e
from backend.ledger import ficha
from backend.ledger.entidades import Estado
from backend.ledger.models import NxFichaVersion, NxHecho, crear_tablas


@pytest.fixture
def sesion():
    engine = create_engine("sqlite:///:memory:", future=True)
    crear_tablas(engine)
    with Session(engine, future=True) as s:
        yield s


def _en_deep(sesion, ticker="ACME"):
    nodo = e.crear_nodo(sesion, nombre="HBM", cluster="datacenter")
    e.crear_candidata(sesion, ticker=ticker, fecha=date(2026, 1, 1), nodo_id=nodo.id)
    e.transicionar(sesion, ticker=ticker, estado_nuevo=Estado.EN_DEEP_RESEARCH,
                   disparado_por="regla", fecha=date(2026, 1, 2))


RES_CANDIDATA = {"decision": "candidata", "arquetipo": {"arquetipo": "Madura"},
                 "quality": {"tier": 3}, "fragility": {"score": 0}, "asimetria": 2.0,
                 "merito": 6.0, "cap_celda": 0.40, "hard_cap": 0.40}
RES_WATCHLIST = {"decision": "watchlist", "motivo": "gate todavia_no",
                 "arquetipo": {"arquetipo": "Tracción"}}
RES_RECHAZO = {"decision": "rechazo", "motivo": "gate no_pasa",
               "arquetipo": {"arquetipo": "Growth"}}


def test_persistir_ficha_campos_y_hechos(sesion):
    _en_deep(sesion)
    fv = ficha.persistir_ficha(sesion, ticker="ACME", resultado=RES_CANDIDATA, precio=10,
                               bull=20, bear=5, fecha=date(2026, 1, 3),
                               hechos={"margen_bruto": 0.55, "arquetipo": "Madura"})
    assert fv.version == 1
    assert fv.arquetipo == "Madura"
    assert fv.quality_tier == 3
    assert fv.asimetria == 2.0
    assert fv.hard_cap == 0.40
    n = sesion.execute(select(func.count()).select_from(NxHecho)
                       .where(NxHecho.ficha_version_id == fv.id)).scalar_one()
    assert n == 2


def test_version_incrementa(sesion):
    _en_deep(sesion)
    ficha.persistir_ficha(sesion, ticker="ACME", resultado=RES_CANDIDATA, precio=10,
                          bull=20, bear=5, fecha=date(2026, 1, 3))
    fv2 = ficha.persistir_ficha(sesion, ticker="ACME", resultado=RES_CANDIDATA, precio=11,
                                bull=22, bear=6, fecha=date(2026, 2, 3))
    assert fv2.version == 2


def test_rechazo_temprano_sin_campos_de_analisis(sesion):
    _en_deep(sesion)
    fv = ficha.persistir_ficha(sesion, ticker="ACME",
                               resultado={"decision": "rechazo", "motivo": "CRR-crítico"},
                               precio=10, bull=20, bear=5, fecha=date(2026, 1, 3))
    assert fv.decision == "rechazo"
    assert fv.arquetipo is None and fv.quality_tier is None   # nullable, no rompe


@pytest.mark.parametrize("res,estado", [
    (RES_CANDIDATA, Estado.ELEGIBLE),
    (RES_WATCHLIST, Estado.ESPERANDO_EVIDENCIA),
    (RES_RECHAZO, Estado.DESCARTADA),
])
def test_deep_research_transiciona(sesion, monkeypatch, res, estado):
    _en_deep(sesion)
    monkeypatch.setattr(ficha, "evaluar_empresa", lambda entrada: res)
    entrada = SimpleNamespace(precio=10.0, bull=20.0, bear=5.0)
    r = ficha.correr_deep_research(sesion, ticker="ACME", entrada=entrada, fecha=date(2026, 1, 3))
    assert r["estado"] == estado.value
    assert e.estado_desde_log(sesion, "ACME") == estado.value
    assert sesion.get(NxFichaVersion, r["ficha_version_id"]) is not None


def test_integracion_nucleo_real(sesion):
    """Corre el núcleo REAL: una Madura que pasa el gate → Elegible + ficha persistida."""
    from backend.nucleo.arquetipo import HechosArquetipo
    from backend.nucleo.flujo import EntradaEmpresa
    from backend.nucleo.fragility import HechosFragility
    from backend.nucleo.gate import HechosGate, Trigger
    from backend.nucleo.quality import HechosQuality

    _en_deep(sesion)
    entrada = EntradaEmpresa(
        ticker="ACME",
        hechos_arquetipo=HechosArquetipo(revenue_elegible=100e6,
                                         crecimiento_elegible_yoy=0.10, fcf_ttm=5e6),
        hechos_gate=HechosGate(arquetipo="", madura_hecho_vigente=True, triggers=[
            Trigger(hecho="deuda sube 2x", umbral=">2x", fecha="2026-01-01", fuente="A",
                    es_estructura_capital=True),
            Trigger(hecho="cliente ancla se va", umbral="<10%", fecha="2026-01-01",
                    fuente="A", atado_a_hecho_de_entrada=True),
        ]),
        hechos_quality=HechosQuality(margen_bruto=0.55, revenue_recurrente=True),
        hechos_fragility=HechosFragility(financiacion_completa_cerrada=True,
                                         redundancia_comercial_real=True),
        precio=10.0, bull=20.0, bear=5.0,
    )
    r = ficha.correr_deep_research(sesion, ticker="ACME", entrada=entrada, fecha=date(2026, 1, 3))
    assert r["decision"] == "candidata"
    assert e.estado_desde_log(sesion, "ACME") == Estado.ELEGIBLE.value
    fv = sesion.get(NxFichaVersion, r["ficha_version_id"])
    assert fv.arquetipo == "Madura"
    assert fv.hard_cap == pytest.approx(0.40)
    assert fv.asimetria == pytest.approx(2.0)      # (20-10)/(10-5)
