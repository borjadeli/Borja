"""Tests del validador determinista del PM (Etapa 6, Art. 4.4)."""
import pytest

from backend.seleccion.validador import (
    Candidata,
    LineaPropuesta,
    validar_propuesta,
)


def _cands():
    return [
        Candidata("ACME", elegible=True, hard_cap=0.25, sector="ciber", factores=["capex hyperscaler"]),
        Candidata("BETA", elegible=True, hard_cap=0.20, sector="ciber", factores=["capex hyperscaler"]),
        Candidata("GAMA", elegible=True, hard_cap=0.30, sector="energia", factores=["defensa"]),
        Candidata("DELT", elegible=False, hard_cap=0.20, sector="fotonica"),
    ]


def _val(lineas, cash=0.0, **kw):
    return validar_propuesta([LineaPropuesta(t, p) for t, p in lineas], _cands(),
                             cash_objetivo=cash, **kw)


def test_propuesta_valida():
    r = _val([("ACME", 0.20), ("GAMA", 0.25)], cash=0.55)
    assert r["ok"], r["errores"]
    assert r["invertido"] == pytest.approx(0.45)


def test_ticker_inventado():
    r = _val([("ZZZZ", 0.10)])
    assert not r["ok"]
    assert any("inventado" in e for e in r["errores"])


def test_no_elegible():
    r = _val([("DELT", 0.10)], cash=0.9)
    assert not r["ok"]
    assert any("no elegible" in e for e in r["errores"])


def test_supera_hard_cap():
    r = _val([("BETA", 0.25)], cash=0.75)   # BETA cap 0.20
    assert not r["ok"]
    assert any("hard cap" in e for e in r["errores"])


def test_debajo_del_piso():
    r = _val([("ACME", 0.02)], cash=0.9)    # piso 5%
    assert not r["ok"]
    assert any("piso" in e for e in r["errores"])


def test_cap_por_sector():
    # 3 en "ciber" con max 2 → error
    r = _val([("ACME", 0.10), ("BETA", 0.10)], cash=0.8, max_por_sector=1)
    assert not r["ok"]
    assert any("sector ciber" in e for e in r["errores"])


def test_cap_por_factor():
    # ACME 0.25 + BETA 0.20 = 0.45 en "capex hyperscaler" > 0.40
    r = _val([("ACME", 0.25), ("BETA", 0.20)], cash=0.55)
    assert not r["ok"]
    assert any("factor capex hyperscaler" in e for e in r["errores"])


def test_sobre_despliegue_vs_cash():
    # invertido 0.60 pero cash objetivo 0.50 → máximo invertible 0.50
    r = _val([("ACME", 0.25), ("GAMA", 0.30), ("BETA", 0.05)], cash=0.50)
    assert not r["ok"]
    assert any("invertido" in e for e in r["errores"])


def test_duplicado():
    r = _val([("ACME", 0.10), ("ACME", 0.10)], cash=0.8)
    assert not r["ok"]
    assert any("duplicado" in e for e in r["errores"])
