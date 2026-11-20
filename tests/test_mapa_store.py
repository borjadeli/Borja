"""Pieza 1 del mapa MVP (doc 89 §9.1): persistencia point-in-time del tablero de cuello."""
from __future__ import annotations

from backend.agentes.mapa_store import SnapshotCuello, StoreMapa
from backend.agentes.mapa_vivo import TableroCuello


def _tablero(cuello="fotonica", fecha="2026-09-30", ventas=15_000.0, margen=0.07, crec=0.4):
    return TableroCuello(cuello=cuello, fecha=fecha, n_empresas=4, ventas_total=ventas,
                         margen_bruto_pond=margen, capex_sobre_ventas=0.10, inventario_sobre_ventas=0.15,
                         rpo_total=None, crecimiento_pond=crec)


def test_set_ultimo_y_roundtrip(tmp_path):
    p = tmp_path / "mapa.json"
    st = StoreMapa(p)
    st.set(_tablero(), empresas_revenue={"LITE": 8000.0, "COHR": 7000.0})
    st.guardar()

    st2 = StoreMapa(p)                      # recarga desde disco
    u = st2.ultimo("fotonica")
    assert u is not None
    assert u.tablero.ventas_total == 15_000.0
    assert u.empresas_revenue == {"LITE": 8000.0, "COHR": 7000.0}
    assert u.fecha == "2026-09-30"


def test_idempotente_misma_fecha_reemplaza(tmp_path):
    st = StoreMapa(tmp_path / "m.json")
    st.set(_tablero(ventas=15_000.0))
    st.set(_tablero(ventas=16_000.0))        # misma fecha → reemplaza, no duplica
    serie = st.serie("fotonica")
    assert len(serie) == 1
    assert serie[0].tablero.ventas_total == 16_000.0


def test_serie_ordenada_y_previo(tmp_path):
    st = StoreMapa(tmp_path / "m.json")
    st.set(_tablero(fecha="2026-09-30", ventas=15_000.0))
    st.set(_tablero(fecha="2026-03-31", ventas=12_000.0))   # se inserta desordenado a propósito
    st.set(_tablero(fecha="2026-06-30", ventas=13_500.0))

    fechas = [s.fecha for s in st.serie("fotonica")]
    assert fechas == ["2026-03-31", "2026-06-30", "2026-09-30"]       # ordenado ascendente

    # previo sin antes_de = la penúltima
    assert st.previo("fotonica").fecha == "2026-06-30"
    # previo ESTRICTAMENTE anterior a una fecha
    assert st.previo("fotonica", antes_de="2026-06-30").fecha == "2026-03-31"
    # no hay nada antes de la primera
    assert st.previo("fotonica", antes_de="2026-03-31") is None


def test_cuello_sin_datos(tmp_path):
    st = StoreMapa(tmp_path / "m.json")
    assert st.ultimo("quantum") is None
    assert st.previo("quantum") is None
    assert st.serie("quantum") == []
    assert st.cuellos() == []


def test_snapshot_from_dict_tolera_sin_empresas():
    d = {"tablero": _tablero().to_dict()}        # sin empresas_revenue (foto vieja)
    s = SnapshotCuello.from_dict(d)
    assert s.empresas_revenue == {}
    assert s.tablero.cuello == "fotonica"
