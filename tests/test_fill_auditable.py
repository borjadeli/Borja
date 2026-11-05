"""Auditabilidad del fill (r7a #4): moneda nativa + precio nativo + FX quedan en cada NxFill; y la migración
idempotente agrega las columnas a DBs ya creadas."""
from datetime import date

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.agentes.datos_reales import precios_meta_de
from backend.ledger import core
from backend.ledger.models import crear_tablas


@pytest.fixture
def sesion():
    engine = create_engine("sqlite:///:memory:", future=True)
    crear_tablas(engine)
    with Session(engine, future=True) as s:
        core.depositar(s, 100_000.0, date(2026, 1, 1))
        yield s


def test_fill_guarda_moneda_nativo_fx(sesion):
    f = core.registrar_fill(sesion, ticker="6315.T", lado="buy", shares=10, precio=28.0,
                            fecha_fill=date(2026, 1, 2), moneda="JPY", precio_nativo=4200.0, fx_usado=0.00667)
    assert f.precio == 28.0 and f.moneda == "JPY" and f.precio_nativo == 4200.0
    assert f.fx_usado == pytest.approx(0.00667)


def test_fill_sin_meta_queda_null(sesion):
    f = core.registrar_fill(sesion, ticker="ACME", lado="buy", shares=1, precio=50.0, fecha_fill=date(2026, 1, 2))
    assert f.moneda is None and f.precio_nativo is None and f.fx_usado is None


def test_migracion_idempotente():
    # simula una DB vieja sin las columnas: crea nx_fill a mano y corre la migración dos veces
    engine = create_engine("sqlite:///:memory:", future=True)
    with engine.begin() as con:
        con.execute(text("CREATE TABLE nx_fill (id INTEGER PRIMARY KEY, ticker TEXT, lado TEXT, shares FLOAT, "
                         "precio FLOAT, comision FLOAT, slippage_bps FLOAT, cash_delta FLOAT, fecha_fill DATE)"))
    crear_tablas(engine)                                     # agrega moneda/precio_nativo/fx_usado
    crear_tablas(engine)                                     # idempotente: no falla la 2a vez
    with engine.begin() as con:
        cols = {r[1] for r in con.execute(text("PRAGMA table_info(nx_fill)"))}
    assert {"moneda", "precio_nativo", "fx_usado"} <= cols


def test_precios_meta_de():
    class _Snap:
        def __init__(self, p, cur):
            self.precio_actual, self.currency = p, cur
    snaps = {"6315.T": _Snap(4200.0, "JPY"), "ACME": _Snap(50.0, "USD")}
    meta = precios_meta_de(snaps, fx_fn=lambda c: 0.0067 if c == "JPY" else 1.0)
    assert meta["6315.T"] == {"moneda": "JPY", "precio_nativo": 4200.0, "fx_usado": 0.0067}
    assert meta["ACME"]["moneda"] == "USD" and meta["ACME"]["fx_usado"] is None   # USD no lleva FX
