"""Tests del orquestador del PM (Etapa 6). Propuesta inyectada → sin API."""
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.ledger import core
from backend.ledger.models import crear_tablas
from backend.seleccion.deploy import desplegar
from backend.seleccion.pm_loop import correr_pm
from backend.seleccion.validador import Candidata, LineaPropuesta


def _cands():
    return [
        Candidata("ACME", elegible=True, hard_cap=0.25, sector="ciber", factores=["fx"]),
        Candidata("BETA", elegible=True, hard_cap=0.20, sector="energia", factores=["fy"]),
    ]


def test_propuesta_valida_primer_intento():
    proponer = lambda cands, errs: [LineaPropuesta("ACME", 0.20), LineaPropuesta("BETA", 0.15)]
    r = correr_pm(_cands(), cash_objetivo=0.55, proponer=proponer)
    assert r["ok"]
    assert r["intentos"] == 1
    assert r["mix"] == {"ACME": 0.20, "BETA": 0.15}


def test_re_propone_tras_rechazo():
    intentos = {"n": 0}

    def proponer(cands, errores_previos):
        intentos["n"] += 1
        if intentos["n"] == 1:
            return [LineaPropuesta("ACME", 0.40)]        # > hard cap 0.25 → rechazo
        assert errores_previos                            # el PM recibe los errores
        return [LineaPropuesta("ACME", 0.25)]             # corregido

    r = correr_pm(_cands(), cash_objetivo=0.75, proponer=proponer)
    assert r["ok"]
    assert r["intentos"] == 2


def test_falla_tras_max_intentos():
    proponer = lambda cands, errs: [LineaPropuesta("ZZZZ", 0.10)]   # ticker inventado, siempre
    r = correr_pm(_cands(), cash_objetivo=0.9, proponer=proponer, max_intentos=3)
    assert not r["ok"]
    assert r["mix"] is None
    assert len(r["historial"]) == 3


def test_solo_incluye_las_lineas_propuestas():
    proponer = lambda cands, errs: [LineaPropuesta("BETA", 0.10)]   # solo BETA
    r = correr_pm(_cands(), cash_objetivo=0.9, proponer=proponer)
    assert r["ok"]
    assert r["mix"] == {"BETA": 0.10}


def test_mix_del_pm_se_puede_desplegar():
    # El mix aprobado por el PM alimenta el deploy sin fricción.
    engine = create_engine("sqlite:///:memory:", future=True)
    crear_tablas(engine)
    with Session(engine, future=True) as s:
        core.depositar(s, 100_000.0, date(2026, 1, 1))
        proponer = lambda cands, errs: [LineaPropuesta("ACME", 0.20), LineaPropuesta("BETA", 0.15)]
        r = correr_pm(_cands(), cash_objetivo=0.55, proponer=proponer)
        assert r["ok"]
        d = desplegar(s, mix=r["mix"], precios={"ACME": 50, "BETA": 20}, fecha=date(2026, 1, 2),
                      candidatas=_cands(), cash_objetivo=0.55)
        assert d["compras"]
        assert not d["violaciones_post"]   # el deploy respeta lo que el validador aprobó
