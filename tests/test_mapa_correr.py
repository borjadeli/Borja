"""Pieza 6 del mapa MVP (núcleo puro): correr el tablero sobre los cuellos, persistir y detectar cambios."""
from __future__ import annotations

import textwrap
from datetime import date

from backend.agentes.mapa_atribucion import MapaAtribucion
from backend.agentes.mapa_store import StoreMapa, cargar_estados, guardar_estados
from backend.agentes.mapa_vivo import EstadoCuello, correr_mapa

M = 1_000_000.0


def _atrib(tmp_path):
    p = tmp_path / "atrib.yaml"
    p.write_text(textwrap.dedent("""
        fotonica:
          LITE: {peso_pureza: 0.85}
          COHR: {peso_pureza: 0.45}
    """), encoding="utf-8")
    return MapaAtribucion(p)


def _metricas(rev, *, op, gross=0.35, growth=0.4):
    return {"revenue": rev, "operating_income_loss": rev * op, "gross_profit": rev * gross,
            "revenue_growth_yoy": growth}


def test_correr_clasifica_y_persiste(tmp_path):
    store = StoreMapa(tmp_path / "m.json")
    cuellos = {"fotonica": ["LITE", "COHR"], "quantum": ["IONQ", "RGTI"]}
    metricas = {"LITE": _metricas(8000 * M, op=0.07), "COHR": _metricas(4000 * M, op=0.05),
                "IONQ": _metricas(100 * M, op=-5.0), "RGTI": _metricas(62 * M, op=-6.0)}
    estados, cambios = correr_mapa(cuellos, metricas, store=store, atrib=_atrib(tmp_path),
                                   hoy=date(2026, 9, 30))
    assert estados["fotonica"].estado == "confirmado"
    assert estados["quantum"].estado == "promesa"       # sin atribución → sin economía-de-cuello
    assert store.ultimo("fotonica") is not None          # persistió la foto
    assert store.ultimo("fotonica").empresas_revenue["LITE"] == 8000 * M


def test_detecta_cambio_de_estado(tmp_path):
    store = StoreMapa(tmp_path / "m.json")
    cuellos = {"fotonica": ["LITE", "COHR"]}
    metricas = {"LITE": _metricas(8000 * M, op=0.07), "COHR": _metricas(4000 * M, op=0.05)}
    previos = {"fotonica": EstadoCuello("fotonica", "promesa", "", None, False, {}, {})}
    estados, cambios = correr_mapa(cuellos, metricas, store=store, atrib=_atrib(tmp_path), estados_previos=previos)
    assert estados["fotonica"].estado == "confirmado"
    assert cambios == [{"cuello": "fotonica", "de": "promesa", "a": "confirmado",
                        "razon": estados["fotonica"].razon}]


def test_estados_store_roundtrip(tmp_path):
    p = tmp_path / "estados.json"
    estados = {"fotonica": EstadoCuello("fotonica", "confirmado", "ok", 0.85, False, {"materialidad": True}, {})}
    guardar_estados(estados, path=p)
    vuelto = cargar_estados(path=p)
    assert vuelto["fotonica"].estado == "confirmado"
    assert vuelto["fotonica"].checks == {"materialidad": True}


def test_same_store_entre_corridas(tmp_path):
    store = StoreMapa(tmp_path / "m.json")
    atrib = _atrib(tmp_path)
    # T1
    correr_mapa({"fotonica": ["LITE", "COHR"]},
                {"LITE": _metricas(8000 * M, op=0.07), "COHR": _metricas(4000 * M, op=0.05)},
                store=store, atrib=atrib, hoy=date(2026, 6, 30))
    # T2: entra un nombre nuevo con revenue enorme; el crecimiento same-store NO debe inflarse por él
    est, _ = correr_mapa({"fotonica": ["LITE", "COHR", "NEW"]},
                         {"LITE": _metricas(8400 * M, op=0.07), "COHR": _metricas(4200 * M, op=0.05),
                          "NEW": _metricas(9000 * M, op=0.07)},
                         store=store, atrib=atrib, hoy=date(2026, 9, 30))
    # same-store = (8400+4200)/(8000+4000) − 1 = 0.05  (NEW excluido)
    assert est["fotonica"].economia["crecimiento"] == round((12600 - 12000) / 12000, 4)
