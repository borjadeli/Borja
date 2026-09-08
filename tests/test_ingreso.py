"""Tests de la Etapa 3: filtro de universo, Filtro 0 y el flujo sobre el ledger.

SQLite in-memory — no toca data/borja.db.
"""
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.ingreso import flujo
from backend.ingreso.filtro0 import HechosFiltro0, evaluar_filtro0
from backend.ingreso.universo import HechosUniverso, evaluar_universo
from backend.ledger import entidades as e
from backend.ledger.entidades import Estado
from backend.ledger.models import NxEmpresa, crear_tablas


# ------------------------------- Universo -------------------------------

def _universo_ok(**kw):
    base = dict(jurisdiccion="US", es_adr=False, market_cap=500e6, adv_usd=5e6,
                tiene_nodo=True)
    base.update(kw)
    return HechosUniverso(**base)


def test_universo_admisible():
    assert evaluar_universo(_universo_ok()).admisible


@pytest.mark.parametrize("kw,motivo", [
    (dict(jurisdiccion="CN"), "jurisdicción"),
    (dict(es_adr=True), "ADR"),
    (dict(market_cap=10e6), "market cap"),
    (dict(adv_usd=100e3), "liquidez"),
    (dict(tiene_nodo=False), "nodo"),
    (dict(instrumento_permitido=False), "instrumento"),
    (dict(mercado_operable=False), "mercado"),
])
def test_universo_rechaza(kw, motivo):
    r = evaluar_universo(_universo_ok(**kw))
    assert not r.admisible
    assert any(motivo in m for m in r.motivos)


def test_universo_sin_techo_de_market_cap():
    # Una mega-cap NO se rechaza por tamaño (Art. 2.3).
    assert evaluar_universo(_universo_ok(market_cap=3_000_000e6)).admisible


# ------------------------------- Filtro 0 -------------------------------

def test_filtro0_riesgo_financiero_descarta():
    h = HechosFiltro0(runway_meses=3, deuda_sobre_revenue=3.0, crecimiento_yoy=0.5,
                      margen_bruto=0.6)
    assert evaluar_filtro0(h).veredicto == "descartar"


def test_filtro0_prerevenue():
    assert evaluar_filtro0(HechosFiltro0(es_prerevenue=True,
                                         tiene_contrato_vinculante_material=True)).veredicto == "investigar"
    assert evaluar_filtro0(HechosFiltro0(es_prerevenue=True,
                                         tiene_traccion_comercial=True)).veredicto == "esperar-evidencia"
    assert evaluar_filtro0(HechosFiltro0(es_prerevenue=True)).veredicto == "descartar"


def test_filtro0_revenue_investigar():
    assert evaluar_filtro0(HechosFiltro0(crecimiento_yoy=0.30,
                                         margen_bruto=0.45)).veredicto == "investigar"


def test_filtro0_revenue_near_miss_espera():
    assert evaluar_filtro0(HechosFiltro0(crecimiento_yoy=0.15,
                                         margen_bruto=0.35)).veredicto == "esperar-evidencia"
    assert evaluar_filtro0(HechosFiltro0(crecimiento_yoy=0.25,
                                         margen_bruto=0.25)).veredicto == "esperar-evidencia"


def test_filtro0_solo_ambas_feas_descarta():
    # ambas feas → descarta
    assert evaluar_filtro0(HechosFiltro0(crecimiento_yoy=0.05,
                                         margen_bruto=0.10)).veredicto == "descartar"
    # una fea y otra excelente → NO descarta (recall): esperar
    assert evaluar_filtro0(HechosFiltro0(crecimiento_yoy=0.40,
                                         margen_bruto=0.05)).veredicto == "esperar-evidencia"


# --- Fixes de la revisión externa ---

def test_filtro0_dato_faltante_no_descarta():
    # 35% de crecimiento, margen faltante → esperar (recall), NO descartar
    assert evaluar_filtro0(HechosFiltro0(crecimiento_yoy=0.35,
                                         margen_bruto=None)).veredicto == "esperar-evidencia"


def test_filtro0_runway_critico_sin_deuda_descarta():
    # 2 meses de runway, SIN deuda, buenas métricas → descartar (riesgo de dilución)
    assert evaluar_filtro0(HechosFiltro0(runway_meses=2, deuda_sobre_revenue=0,
                                         crecimiento_yoy=0.50, margen_bruto=0.60)).veredicto == "descartar"


def test_filtro0_prerevenue_runway_critico_descarta():
    # pre-revenue con contrato PERO 2 meses de runway → descartar (no llega a deep research)
    assert evaluar_filtro0(HechosFiltro0(es_prerevenue=True, tiene_contrato_vinculante_material=True,
                                         runway_meses=2)).veredicto == "descartar"


def test_filtro0_financiacion_comprometida_neutraliza_runway():
    assert evaluar_filtro0(HechosFiltro0(runway_meses=3, financiacion_comprometida=True,
                                         crecimiento_yoy=0.5, margen_bruto=0.6)).veredicto == "investigar"


def test_filtro0_valida_unidades():
    # porcentaje sin convertir (30 / 35 en vez de 0.30 / 0.35) → esperar (unidades sospechosas)
    assert evaluar_filtro0(HechosFiltro0(crecimiento_yoy=30,
                                         margen_bruto=35)).veredicto == "esperar-evidencia"


def test_filtro0_dimension_excepcional_arrastra_near_miss():
    # crecimiento 132% (excepcional) + margen 29% (near) → investigar (el caso AAOI)
    assert evaluar_filtro0(HechosFiltro0(crecimiento_yoy=1.32,
                                         margen_bruto=0.29)).veredicto == "investigar"
    # margen 65% (excepcional) + crecimiento 15% (near) → investigar
    assert evaluar_filtro0(HechosFiltro0(crecimiento_yoy=0.15,
                                         margen_bruto=0.65)).veredicto == "investigar"


def test_filtro0_excepcional_no_arrastra_feo():
    # crecimiento excepcional pero margen feo (<20%) → NO arrastra: sigue esperar
    assert evaluar_filtro0(HechosFiltro0(crecimiento_yoy=1.32,
                                         margen_bruto=0.10)).veredicto == "esperar-evidencia"


# ------------------------------- Flujo (sobre el ledger) -------------------------------

@pytest.fixture
def sesion():
    engine = create_engine("sqlite:///:memory:", future=True)
    crear_tablas(engine)
    with Session(engine, future=True) as s:
        yield s


def test_flujo_fuera_universo_no_crea_candidata(sesion):
    r = flujo.ingresar(sesion, ticker="ACME", fecha=date(2026, 1, 1),
                       universo=_universo_ok(jurisdiccion="CN"),
                       filtro0=HechosFiltro0(crecimiento_yoy=0.5, margen_bruto=0.6))
    assert r["resultado"] == "fuera_universo"
    assert sesion.get(NxEmpresa, "ACME") is None


def test_flujo_investigar_deja_en_deep_research(sesion):
    nodo = e.crear_nodo(sesion, nombre="HBM", cluster="datacenter")
    r = flujo.ingresar(sesion, ticker="ACME", fecha=date(2026, 1, 1), nodo_id=nodo.id,
                       universo=_universo_ok(), filtro0=HechosFiltro0(crecimiento_yoy=0.3,
                                                                      margen_bruto=0.45))
    assert r["resultado"] == "investigar"
    assert e.estado_desde_log(sesion, "ACME") == Estado.EN_DEEP_RESEARCH.value


def test_flujo_descartar_deja_descartada(sesion):
    nodo = e.crear_nodo(sesion, nombre="HBM", cluster="datacenter")
    r = flujo.ingresar(sesion, ticker="ACME", fecha=date(2026, 1, 1), nodo_id=nodo.id,
                       universo=_universo_ok(), filtro0=HechosFiltro0(crecimiento_yoy=0.02,
                                                                      margen_bruto=0.05))
    assert r["resultado"] == "descartar"
    assert e.estado_desde_log(sesion, "ACME") == Estado.DESCARTADA.value


def test_reemision_por_nodo_revive_descartada(sesion):
    nodo = e.crear_nodo(sesion, nombre="HBM", cluster="datacenter")
    # Entra y queda descartada por calidad pobre.
    flujo.ingresar(sesion, ticker="ACME", fecha=date(2026, 1, 1), nodo_id=nodo.id,
                   universo=_universo_ok(), filtro0=HechosFiltro0(crecimiento_yoy=0.02,
                                                                  margen_bruto=0.05))
    assert e.estado_desde_log(sesion, "ACME") == Estado.DESCARTADA.value
    # El nodo cambia → re-chequeo con hechos frescos (ahora sí califica).
    res = flujo.reemitir_por_nodo(sesion, nodo_id=nodo.id, fecha=date(2026, 2, 1),
                                  filtro0_por_ticker={"ACME": HechosFiltro0(
                                      crecimiento_yoy=0.35, margen_bruto=0.50)})
    assert res["ACME"] == "investigar"
    assert e.estado_desde_log(sesion, "ACME") == Estado.EN_DEEP_RESEARCH.value
    # No gastó Candado B (Descartada→Candidata no cuenta).
    emp = sesion.get(NxEmpresa, "ACME")
    assert emp.reentradas_usadas == 0


def test_flujo_deriva_tiene_nodo_de_nodo_id(sesion):
    # universo dice tiene_nodo=True pero nodo_id=None → flujo lo corrige → fuera_universo
    r = flujo.ingresar(sesion, ticker="ACME", fecha=date(2026, 1, 1), nodo_id=None,
                       universo=_universo_ok(tiene_nodo=True),
                       filtro0=HechosFiltro0(crecimiento_yoy=0.3, margen_bruto=0.45))
    assert r["resultado"] == "fuera_universo"
    assert any("nodo" in m for m in r["motivos"])


def test_reemision_no_revive_descarte_duro(sesion):
    nodo = e.crear_nodo(sesion, nombre="HBM", cluster="datacenter")
    e.crear_candidata(sesion, ticker="ACME", fecha=date(2026, 1, 1), nodo_id=nodo.id)
    e.transicionar(sesion, ticker="ACME", estado_nuevo=Estado.EN_DEEP_RESEARCH,
                   disparado_por="regla", fecha=date(2026, 1, 2))
    # Descarte DURO (governance/fraude en deep research) → reversible=False.
    e.transicionar(sesion, ticker="ACME", estado_nuevo=Estado.DESCARTADA, disparado_por="humano",
                   motivo="fraude contable", fecha=date(2026, 1, 3), reversible=False)
    res = flujo.reemitir_por_nodo(sesion, nodo_id=nodo.id, fecha=date(2026, 2, 1),
                                  filtro0_por_ticker={"ACME": HechosFiltro0(
                                      crecimiento_yoy=0.40, margen_bruto=0.50)})
    assert "ACME" not in res  # NO se re-evalúa un descarte duro
    assert e.estado_desde_log(sesion, "ACME") == Estado.DESCARTADA.value
