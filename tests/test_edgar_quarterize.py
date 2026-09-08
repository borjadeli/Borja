"""De-acumulación de períodos YTD → trimestres (fix del Q4 faltante en el TTM)."""
from backend.services.edgar import _quarterize_flow


def test_reconstruye_los_cuatro_trimestres_incluido_q4():
    entries = [
        {"start": "2025-01-01", "end": "2025-03-31", "val": 100.0, "form": "10-Q"},  # 3M YTD = Q1
        {"start": "2025-01-01", "end": "2025-06-30", "val": 250.0, "form": "10-Q"},  # 6M YTD
        {"start": "2025-01-01", "end": "2025-09-30", "val": 420.0, "form": "10-Q"},  # 9M YTD
        {"start": "2025-01-01", "end": "2025-12-31", "val": 600.0, "form": "10-K"},  # FY
    ]
    qs = {e["end"]: e["val"] for e in _quarterize_flow(entries)}
    assert qs["2025-03-31"] == 100.0
    assert qs["2025-06-30"] == 150.0   # 250 − 100
    assert qs["2025-09-30"] == 170.0   # 420 − 250
    assert qs["2025-12-31"] == 180.0   # 600 − 420  (Q4: antes FALTABA)


def test_reconstruye_fy_no_calendario():
    # FY que arranca en julio (COHR): los acumulados cruzan el año calendario → agrupar por start.
    entries = [
        {"start": "2025-07-01", "end": "2025-09-30", "val": 100.0, "form": "10-Q"},  # 3M
        {"start": "2025-07-01", "end": "2025-12-31", "val": 210.0, "form": "10-Q"},  # 6M
        {"start": "2025-07-01", "end": "2026-03-31", "val": 330.0, "form": "10-Q"},  # 9M
        {"start": "2025-07-01", "end": "2026-06-30", "val": 460.0, "form": "10-K"},  # 12M
    ]
    qs = {e["end"]: e["val"] for e in _quarterize_flow(entries)}
    assert qs["2025-09-30"] == 100.0
    assert qs["2025-12-31"] == 110.0   # 210 − 100
    assert qs["2026-03-31"] == 120.0   # 330 − 210
    assert qs["2026-06-30"] == 130.0   # 460 − 330  (cruza año calendario, antes fallaba)


def test_no_inventa_trimestre_si_el_delta_no_es_trimestral():
    # Falta el 6M → el delta Mar→Sep es ~183 días, NO es un trimestre: no se emite.
    entries = [
        {"start": "2025-01-01", "end": "2025-03-31", "val": 100.0, "form": "10-Q"},
        {"start": "2025-01-01", "end": "2025-09-30", "val": 420.0, "form": "10-Q"},
    ]
    qs = {e["end"]: e["val"] for e in _quarterize_flow(entries)}
    assert qs["2025-03-31"] == 100.0
    assert "2025-09-30" not in qs
