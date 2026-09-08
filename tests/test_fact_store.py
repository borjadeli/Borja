"""Tests del fact store (doc 22 §4). SQLite in-memory — no toca data/borja.db."""
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.ledger.models import crear_tablas
from backend.nucleo import fact_store as fs


@pytest.fixture
def sesion():
    engine = create_engine("sqlite:///:memory:", future=True)
    crear_tablas(engine)
    with Session(engine, future=True) as s:
        yield s


def _g(s, fact_key, value, acc, accepted, support="DIRECT", **kw):
    return fs.guardar(s, cik="0000820318", ticker="COHR", fact_key=fact_key, value=value,
                      support_type=support, source_accession=acc, accepted_at=accepted,
                      document_hash=f"{acc}:{fact_key}", **kw)


def test_guardar_y_snapshot(sesion):
    _g(sesion, "gross_margin", 0.376, "acc-A", date(2026, 5, 6))
    _g(sesion, "organic_growth_available", True, "acc-A", date(2026, 5, 6), support="DERIVED")
    snap = fs.snapshot_vigente(sesion, "COHR")
    assert set(snap) == {"gross_margin", "organic_growth_available"}
    assert fs._dec(snap["gross_margin"].value) == 0.376
    assert snap["organic_growth_available"].support_type == "DERIVED"


def test_dedup_idempotente(sesion):
    a = _g(sesion, "gross_margin", 0.376, "acc-A", date(2026, 5, 6))
    b = _g(sesion, "gross_margin", 0.376, "acc-A", date(2026, 5, 6))  # idéntico → no duplica
    assert a.id == b.id


def test_supersesion(sesion):
    v1 = _g(sesion, "gross_margin", 0.376, "acc-A", date(2026, 5, 6))
    v2 = _g(sesion, "gross_margin", 0.34, "acc-B", date(2026, 8, 6))  # período nuevo
    assert v1.superseded_by == v2.id
    assert fs._dec(fs.snapshot_vigente(sesion, "COHR")["gross_margin"].value) == 0.34


def test_point_in_time(sesion):
    _g(sesion, "gross_margin", 0.376, "acc-A", date(2026, 5, 6))
    _g(sesion, "gross_margin", 0.34, "acc-B", date(2026, 8, 6))
    # as_of anterior a acc-B → ve el viejo (sin look-ahead)
    snap = fs.snapshot_vigente(sesion, "COHR", as_of=date(2026, 6, 1))
    assert fs._dec(snap["gross_margin"].value) == 0.376


def test_diff_delta_evidencia(sesion):
    _g(sesion, "gross_margin", 0.376, "acc-A", date(2026, 5, 6))
    _g(sesion, "organic_growth_available", True, "acc-A", date(2026, 5, 6), support="DERIVED")
    _g(sesion, "gross_margin", 0.34, "acc-B", date(2026, 8, 6))
    _g(sesion, "take_or_pay_present", True, "acc-B", date(2026, 8, 6))
    d = {c["fact_key"]: c["tipo"] for c in fs.diff(sesion, "COHR", "acc-A", "acc-B")}
    assert d["gross_margin"] == "VALUE_CHANGED"
    assert d["organic_growth_available"] == "REMOVED"   # no reaparece en el filing nuevo
    assert d["take_or_pay_present"] == "ADDED"          # primera aparición = first_seen
