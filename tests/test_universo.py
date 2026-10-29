"""Tests del esqueleto del embudo (v2 doc 61 §A). Señales deterministas sin red."""
from datetime import date, datetime
from types import SimpleNamespace

from backend.agentes.universo import candidatos_del_universo, señales_ticker, tickers_universo


def _f(tipo, iso, items=""):
    return SimpleNamespace(tipo=tipo, fecha=datetime.fromisoformat(iso), items=items)


HOY = date(2026, 10, 28)


def test_nombre_nuevo_cuenta_solo_eventos_materiales_en_la_ventana():
    # nunca analizado: NO todo el historial es nuevo (cursor = últimos 30d). Un 8-K material reciente cuenta;
    # un 10-Q viejo (fuera de ventana) NO; un 8-K accesorio (9.01) tampoco.
    s, resumen = señales_ticker("OKLO", hoy=HOY, fecha_dossier=None,
                                filings=[_f("8-K", "2026-10-20", items="1.01"),  # material + en ventana
                                         _f("8-K", "2026-10-18", items="9.01"),   # accesorio
                                         _f("10-Q", "2026-08-07")],               # material pero viejo
                                precio_hist=[20.0, 27.0], es_posicion=False)
    assert s.dias_desde_dossier is None and s.hechos_nuevos == 1 and s.tiene_evento_fuerte is True
    assert abs(s.precio_vs_tesis_pct - 35.0) < 0.1          # +35%
    assert "8-K/1.01" in resumen


def test_sin_filings_nuevos_desde_el_dossier_no_dispara():
    # ya analizado el 2026-10-25; el único filing es anterior → 0 hechos nuevos, sin evento
    s, resumen = señales_ticker("MP", hoy=HOY, fecha_dossier=date(2026, 10, 25),
                                filings=[_f("10-Q", "2026-08-07")], precio_hist=[50.0, 51.0],
                                es_posicion=True)
    assert s.hechos_nuevos == 0 and s.tiene_evento_fuerte is False and s.es_posicion is True
    assert s.dias_desde_dossier == 3 and resumen == ""


def test_dias_a_evento_aprox_por_ciclo_trimestral():
    # último 10-Q el 2026-08-07 → próximo earnings ~ +90d = 2026-11-05 → ~8 días desde hoy(10-28)
    s, _ = señales_ticker("X", hoy=HOY, fecha_dossier=None, filings=[_f("10-Q", "2026-08-07")],
                          precio_hist=None, es_posicion=False)
    assert s.dias_a_evento is not None and 0 <= s.dias_a_evento <= 12


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows
    def execute(self, *_a, **_k):
        return SimpleNamespace(all=lambda: self._rows)


def test_tickers_universo_filtra_inactivas():
    s = _FakeSession([("OKLO", "Candidata"), ("MP", "Candidata"), ("ZZZ", "Descartada")])
    assert tickers_universo(s) == ["OKLO", "MP"]


def test_candidatos_del_universo_arma_la_lista():
    s = _FakeSession([("OKLO", "Candidata"), ("ZZZ", "Descartada")])
    cands = candidatos_del_universo(
        s, hoy=HOY, fechas_dossier={}, posiciones={"OKLO"},
        filings_fn=lambda tk: [_f("8-K", "2026-10-20", items="1.01")], precio_hist_fn=lambda tk: [20.0, 22.0])
    assert len(cands) == 1 and cands[0][0] == "OKLO"
    tk, señal, resumen = cands[0]
    assert señal.es_posicion is True and señal.tiene_evento_fuerte is True
