"""Archivo inteligente / lápida (r9, doc 80 §J · P3): memoria de lo que salió + reingreso según el motivo."""
from datetime import date

from backend.agentes.archivo import StoreLapidas, archivar, evaluar_reingreso

_MET = {"revenue": 1e9, "gross_profit": 4e8, "shares_outstanding": 100e6, "rpo": 5e8}


def test_valuacion_reingresa_por_precio():
    # salió CARA con gatillo de compra $40 → vuelve si el precio cae a ≤ $40
    lap = archivar("XYZ", motivo="VALUACION", metricas=_MET, gatillo_compra=40.0)
    assert lap.reingreso_tipo == "PRECIO"
    assert evaluar_reingreso(lap, precio=38.0)[0] is True       # se abarató → vuelve
    assert evaluar_reingreso(lap, precio=52.0)[0] is False      # sigue cara → no


def test_tesis_rota_suprime_si_no_cambia_la_huella():
    lap = archivar("XYZ", motivo="TESIS_ROTA", metricas=_MET)
    assert lap.reingreso_tipo == "FUNDAMENTAL"
    # misma huella → suprimida (no re-investigar, ahorra budget)
    assert evaluar_reingreso(lap, metricas_actuales=dict(_MET))[0] is False
    # ventas +30% → la huella cambió → vuelve
    cambiada = {**_MET, "revenue": 1.3e9}
    assert evaluar_reingreso(lap, metricas_actuales=cambiada)[0] is True


def test_rotacion_universo_reingresa_por_score():
    lap = archivar("XYZ", motivo="ROTACION_UNIVERSO", metricas=_MET)
    assert lap.reingreso_tipo == "SCORE"
    assert evaluar_reingreso(lap, score_percentil=0.80)[0] is True
    assert evaluar_reingreso(lap, score_percentil=0.50)[0] is False


def test_cuello_resuelto_nunca():
    lap = archivar("XYZ", motivo="CUELLO_RESUELTO", metricas=_MET)
    assert lap.reingreso_tipo == "NUNCA"
    assert evaluar_reingreso(lap, precio=1.0, metricas_actuales={"revenue": 9e9}, score_percentil=1.0)[0] is False


def test_store_lapidas_roundtrip(tmp_path):
    s = StoreLapidas(path=tmp_path / "l.json")
    s.set(archivar("XYZ", motivo="VALUACION", metricas=_MET, gatillo_compra=40.0, hoy=date(2026, 11, 13)))
    s.guardar()
    s2 = StoreLapidas(path=tmp_path / "l.json")
    g = s2.get("XYZ")
    assert g is not None and g.motivo == "VALUACION" and g.reingreso_condicion == 40.0
