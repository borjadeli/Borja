"""r6 #2: las tenencias siempre con precio (feed → USD; si el feed no responde, último precio del ledger).
Sin red — monkeypatch de recolectar_snapshots. Paper in-memory."""
from datetime import date
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import ops.correr_semana_v2 as op
from backend.ledger import core
from backend.ledger.models import crear_tablas


def _paper_con(ticker, shares, precio):
    engine = create_engine("sqlite:///:memory:", future=True)
    crear_tablas(engine)
    s = Session(engine, future=True)
    core.depositar(s, 100_000, date(2026, 1, 1))
    core.registrar_fill(s, ticker=ticker, lado="buy", shares=shares, precio=precio, fecha_fill=date(2026, 1, 2))
    return s


def test_tenencia_toma_precio_del_feed(monkeypatch):
    s = _paper_con("OKLO", 100, 25.0)
    monkeypatch.setattr(op, "recolectar_snapshots",
                        lambda tks: {"OKLO": SimpleNamespace(precio_actual=30.0, currency="USD")})
    precios: dict = {}
    op._asegurar_precios_tenencias(s, precios)
    assert precios["OKLO"] == 30.0                  # tomó el precio del feed


def test_tenencia_fallback_ultimo_del_ledger(monkeypatch):
    s = _paper_con("OKLO", 100, 25.0)
    monkeypatch.setattr(op, "recolectar_snapshots", lambda tks: {})   # feed no responde
    precios: dict = {}
    op._asegurar_precios_tenencias(s, precios)
    assert precios["OKLO"] == 25.0                  # cayó al último precio del ledger (nunca queda sin precio)


def test_no_pisa_precio_existente(monkeypatch):
    s = _paper_con("OKLO", 100, 25.0)
    monkeypatch.setattr(op, "recolectar_snapshots", lambda tks: (_ for _ in ()).throw(AssertionError("no debió llamar")))
    precios = {"OKLO": 28.0}                         # ya tiene precio (es candidato en esta corrida)
    op._asegurar_precios_tenencias(s, precios)
    assert precios["OKLO"] == 28.0                  # no lo re-busca ni lo pisa
