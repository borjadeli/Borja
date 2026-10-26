"""Tests del ETL de import del Sistema-Quant (v2 Fase 2).

Corren sobre SQLite in-memory — no tocan data/borja.db. El fetch de market cap se inyecta
(market_cap_fn) para no pegarle a la red.
"""
from datetime import date

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.ledger.models import NxEmpresa, NxEmpresaNodo, NxNodo, crear_tablas
from ops import import_sistema_quant as imp

HOY = date(2026, 10, 26)


@pytest.fixture
def sesion():
    engine = create_engine("sqlite:///:memory:", future=True)
    crear_tablas(engine)
    with Session(engine, future=True) as s:
        yield s


def _n_nodos(s):
    return s.execute(select(func.count()).select_from(NxNodo)).scalar_one()


def _n_links(s):
    return s.execute(select(func.count()).select_from(NxEmpresaNodo)).scalar_one()


# ---- nodos ----

def test_importa_nodos_del_mapa(sesion):
    sqid_to_id = imp.importar_nodos(sesion)
    assert sqid_to_id, "debería poblar nodos desde industry_map.yaml"
    assert "gpu" in sqid_to_id          # nodo conocido del mapa
    gpu = sesion.get(NxNodo, sqid_to_id["gpu"])
    assert gpu.nombre == "GPUs para datacenter"
    assert gpu.estado_confirmacion == "promesa"   # los nodos son priors hasta evidencia
    assert "sq_id=gpu" in (gpu.nota or "")        # procedencia + atributos en la nota


def test_importar_nodos_es_idempotente(sesion):
    a = imp.importar_nodos(sesion)
    n1 = _n_nodos(sesion)
    b = imp.importar_nodos(sesion)              # segunda corrida
    n2 = _n_nodos(sesion)
    assert n1 == n2, "no debe duplicar nodos"
    assert a == b


# ---- empresas + vínculos ----

def test_empresas_sin_filtro_de_cap(sesion):
    res = imp.importar(sesion, aplicar_cap=False, hoy=HOY, solo={"NVDA", "ALAB"})
    nvda = sesion.get(NxEmpresa, "NVDA")
    assert nvda is not None and nvda.estado == "Candidata"
    assert nvda.fuente_ingreso == "import_sq"
    # NVDA: nodes: [gpu, switch_asics, dpu_nic] — el 1º es primario
    links = sesion.execute(
        select(NxEmpresaNodo).where(NxEmpresaNodo.ticker == "NVDA")
    ).scalars().all()
    assert len(links) >= 1
    primarios = [l for l in links if l.es_primario]
    assert len(primarios) == 1, "exactamente un nodo primario (el 1º)"


def test_filtro_de_cap_descarta_grandes_y_marca_sin_dato(sesion):
    # MTSI es un ticker real del universo SQ; le forzamos market cap None para probar ese camino.
    caps = {"ALAB": 20_000_000_000, "NVDA": 4_000_000_000_000, "MTSI": None}

    def fake_cap(tk):
        return caps.get(tk)

    res = imp.importar(sesion, aplicar_cap=True, market_cap_fn=fake_cap, hoy=HOY,
                       solo={"ALAB", "NVDA", "MTSI"})
    assert "ALAB" in res["importadas"]                      # $20B → dentro de [150M, 60B]
    assert any(t == "NVDA" for t, _ in res["descartadas_cap"])  # $4T → fuera
    assert "MTSI" in res["sin_cap"]                         # sin dato → no se compromete
    assert sesion.get(NxEmpresa, "NVDA") is None            # el descartado no entra
    assert sesion.get(NxEmpresa, "ALAB") is not None


def test_import_completo_es_idempotente(sesion):
    imp.importar(sesion, aplicar_cap=False, hoy=HOY, solo={"NVDA", "ALAB"})
    n1, l1 = _n_nodos(sesion), _n_links(sesion)
    imp.importar(sesion, aplicar_cap=False, hoy=HOY, solo={"NVDA", "ALAB"})   # otra vez
    assert (_n_nodos(sesion), _n_links(sesion)) == (n1, l1), "ni nodos ni links se duplican"


def test_merge_tickers_de_borja_entra_sin_cap(sesion):
    # solo=set() vacío → no importa ninguna del SQ, pero el merge agrega el ticker de BORJA igual
    res = imp.importar(sesion, aplicar_cap=False, hoy=HOY, solo=set(),
                       merge_tickers=["ZZZZ"])
    assert "ZZZZ" in res.get("merge", [])
    z = sesion.get(NxEmpresa, "ZZZZ")
    assert z is not None and z.fuente_ingreso == "borja_vivo"
