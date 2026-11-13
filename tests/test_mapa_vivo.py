"""Mapa vivo (r9, doc 80 §B · P3): tablero XBRL del cuello + detección de disolución (capex↑+inventario↑+margen↓)."""
from datetime import date

from backend.agentes.mapa_vivo import TableroCuello, senal_disolucion, tablero_cuello


def test_tablero_agrega_ponderado():
    met = {
        "A": {"revenue": 1e9, "gross_profit": 4e8, "capex": 1e8, "inventarios": 2e8, "rpo": 5e8,
              "revenue_growth_yoy": 30.0},
        "B": {"revenue": 3e9, "gross_profit": 6e8, "capex": 6e8, "inventarios": 9e8, "rpo": None,
              "revenue_growth_yoy": 10.0},
    }
    t = tablero_cuello("óptica 800g", met, fecha=date(2026, 11, 13))
    assert t.n_empresas == 2 and t.ventas_total == 4e9
    assert abs(t.margen_bruto_pond - (1e9 / 4e9)) < 1e-6          # (4e8+6e8)/(4e9) = 0.25
    assert abs(t.capex_sobre_ventas - (7e8 / 4e9)) < 1e-6
    assert t.rpo_total == 5e8                                     # suma (B no tiene)
    # crecimiento ponderado por ventas: (30×1 + 10×3)/4 = 15
    assert t.crecimiento_pond == 15.0


def _tab(**kw):
    base = dict(cuello="x", fecha="2026-01-01", n_empresas=3, ventas_total=1e10, margen_bruto_pond=0.30,
                capex_sobre_ventas=0.08, inventario_sobre_ventas=0.15, rpo_total=2e9, crecimiento_pond=25.0)
    base.update(kw)
    return TableroCuello(**base)


def test_disolucion_detectada():
    previo = _tab()
    # el cuello se disuelve: capex sube, inventario sube, margen cede, crecimiento desacelera
    actual = _tab(capex_sobre_ventas=0.12, inventario_sobre_ventas=0.22, margen_bruto_pond=0.24,
                  crecimiento_pond=8.0)
    estado, razon = senal_disolucion(actual, previo)
    assert estado == "resolviendose" and "disolución" in razon


def test_inventario_y_margen_alcanza():
    previo = _tab()
    # 2 señales pero las clave (inventario↑ + margen↓) → alcanza para marcar resolviéndose
    actual = _tab(inventario_sobre_ventas=0.22, margen_bruto_pond=0.24)
    assert senal_disolucion(actual, previo)[0] == "resolviendose"


def test_sin_disolucion_estable():
    previo = _tab()
    actual = _tab(crecimiento_pond=26.0)                          # todo estable / mejorando
    assert senal_disolucion(actual, previo)[0] is None


def test_sin_previo_no_señal():
    assert senal_disolucion(_tab(), None)[0] is None
