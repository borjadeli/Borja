"""Embudo / hit-rate de discovery — join determinista, sin API ni DB (inyección de dependencias)."""
from types import SimpleNamespace

from backend.agentes.discovery_hitrate import embudo_discovery, embudo_nodos


def _dossier(conv, clas):
    return SimpleNamespace(conviccion_0_1=conv, invertibilidad=SimpleNamespace(analyst_classification=clas))


def test_embudo_discovery_funnel_y_orden():
    propuestas = {
        "AAA": {"estado": "aprobada", "propuesta": {"cuello": "HBM"}},        # universo + dossier conv alta
        "BBB": {"estado": "aprobada", "propuesta": {"cuello": "Galio"}},      # universo, sin dossier
        "CCC": {"estado": "rechazada", "propuesta": {"cuello": "x"}},         # no entró
    }
    universo = {"AAA": "Candidata", "BBB": "Candidata"}
    dossiers = {"AAA": _dossier(0.8, "satelite")}
    r = embudo_discovery(propuestas=propuestas, universo_estado=universo,
                         dossier_fn=lambda tk: dossiers.get(tk))
    assert r["funnel"] == {"propuestas": 3, "al_universo": 2, "analizadas": 1,
                           "conviccion_alta": 1, "rechazadas": 1}
    # ordenado por convicción desc (AAA con dossier primero; los sin convicción al final)
    assert r["filas"][0].ticker == "AAA" and r["filas"][0].clasificacion == "satelite"
    bbb = next(f for f in r["filas"] if f.ticker == "BBB")
    assert bbb.en_universo and not bbb.analizada and bbb.conviccion is None
    ccc = next(f for f in r["filas"] if f.ticker == "CCC")
    assert not ccc.en_universo and ccc.estado_cola == "rechazada"


def test_embudo_nodos():
    nodos = {
        "Cuello bueno": {"estado": "aprobada", "propuesta": {"nombre": "Cuello bueno"}},
        "Cuello flojo": {"estado": "rechazada", "propuesta": {"nombre": "Cuello flojo"}},
        "Cuello pend": {"estado": "observacion", "propuesta": {"nombre": "Cuello pend"}},
    }
    r = embudo_nodos(nodos)
    assert r["propuestos"] == 3 and r["al_mapa"] == 1 and r["rechazados"] == 1
    assert {d["nombre"]: d["estado"] for d in r["detalle"]}["Cuello bueno"] == "aprobada"
