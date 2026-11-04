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


def _snapc(precio, currency):
    return SimpleNamespace(precio_actual=precio, currency=currency, market_cap=None,
                           volumen_diario_promedio_30d=None)


def test_precios_de_convierte_a_usd_r6_1():
    # r6 #1: el feed da precio nativo; el paper razona en USD → precios_de debe convertir en el borde.
    fx = {"KRW": 1 / 1390, "JPY": 1 / 150, "EUR": 1.12, "GBP": 1.27}
    snaps = {
        "USA": _snapc(50.0, "USD"),          # USD: identidad
        "042700.KS": _snapc(186100.0, "KRW"),
        "6315.T": _snapc(2097.0, "JPY"),
        "BESI.AS": _snapc(152.0, "EUR"),
        "SHEL.L": _snapc(2800.0, "GBp"),     # peniques de Londres → GBP/100 → USD
    }
    p = precios_de(snaps, fx_fn=lambda c: fx.get(c))
    assert p["USA"] == 50.0
    assert abs(p["042700.KS"] - 186100.0 / 1390) < 0.5           # ≈ $134
    assert abs(p["6315.T"] - 2097.0 / 150) < 0.1                 # ≈ $14
    assert abs(p["BESI.AS"] - 152.0 * 1.12) < 0.1                # ≈ $170
    assert abs(p["SHEL.L"] - (2800.0 / 100) * 1.27) < 0.1        # GBp: $35.6, NO $3556


def test_precios_de_sin_fx_queda_fuera():
    # un extranjero sin FX disponible no se puede valuar en USD → no entra (como sin precio)
    p = precios_de({"X.KS": _snapc(1000.0, "KRW")}, fx_fn=lambda c: None)
    assert p == {}


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
