"""Tests de los adaptadores de datos reales (v2 Fase 4). DB in-memory + snapshots fake, sin red."""
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.agentes.datos_reales import (
    abrir_paper,
    contexto_de,
    precios_de,
    recolectar_snapshots,
)
from backend.ledger import core
from backend.ledger.models import NxEmpresa, NxEmpresaNodo, NxNodo, crear_tablas


def _snap(precio=50.0, mc=5e9, adv=10e6):
    return SimpleNamespace(precio_actual=precio, market_cap=mc, volumen_diario_promedio_30d=adv)


@pytest.fixture
def nx():
    engine = create_engine("sqlite:///:memory:", future=True)
    crear_tablas(engine)
    s = Session(engine, future=True)
    s.add(NxEmpresa(ticker="OKLO", estado="activa", fecha_ingreso=date(2026, 1, 1), sector="energia"))
    s.add(NxNodo(nombre="SMR deployment", estado_confirmacion="confirmado", estado_archivo="activo"))
    s.flush()
    nodo_id = s.execute(select(NxNodo.id)).scalar_one()
    s.add(NxEmpresaNodo(ticker="OKLO", nodo_id=nodo_id, es_primario=True))
    s.commit()
    yield s


def test_recolectar_snapshots_saltea_los_nulos():
    snaps = recolectar_snapshots(["OKLO", "ZZZ"], snapshot_fn=lambda t: _snap() if t == "OKLO" else None)
    assert set(snaps) == {"OKLO"}


def test_precios_solo_los_que_tienen_precio():
    snaps = {"OKLO": _snap(precio=50.0), "MP": _snap(precio=None)}
    assert precios_de(snaps) == {"OKLO": 50.0}


def test_contexto_mezcla_nx_y_feed(nx):
    ctx = contexto_de(["OKLO", "MP"], {"OKLO": _snap(mc=5e9, adv=10e6)}, session=nx)
    assert ctx["OKLO"].sector == "energia" and ctx["OKLO"].cuello == "SMR deployment"
    assert ctx["OKLO"].market_cap == 5e9 and ctx["OKLO"].adv_usd == 10e6
    # MP no está en nx ni tiene snapshot → todo None, sin romper
    assert ctx["MP"].sector is None and ctx["MP"].cuello is None and ctx["MP"].market_cap is None


def test_abrir_paper_deposita_una_sola_vez(tmp_path):
    ruta = tmp_path / "paper.db"
    s1 = abrir_paper(ruta, capital_inicial=100_000.0, fecha=date(2026, 1, 1))
    assert core.proyectar(s1, {})["equity"] == pytest.approx(100_000.0)
    s1.close()
    # reabrir no vuelve a depositar (ya hay equity)
    s2 = abrir_paper(ruta, capital_inicial=100_000.0, fecha=date(2026, 1, 1))
    assert core.proyectar(s2, {})["equity"] == pytest.approx(100_000.0)
    s2.close()
