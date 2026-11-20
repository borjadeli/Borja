"""P0-1 (review r11): la salida tier A debe PERSISTIR en el paper (commit antes de close, si no SQLAlchemy
hace rollback y la venta se pierde — y queda marcada como ejecutada → nunca se reintenta)."""
from __future__ import annotations

from datetime import date

import ops.ciclo_diario as cd
from backend.agentes import datos_reales
from backend.agentes.reglas_salida import AccionSalida
from backend.ledger import core


def _pos_shares(session, tk, precios):
    p = core.proyectar(session, precios)["posiciones"].get(tk)
    return 0 if p is None else int(round(p.shares))


def test_ejecutar_salidas_deja_la_posicion_en_cero(tmp_path, monkeypatch):
    db = tmp_path / "paper.db"
    # posición inicial OKLO 500 @ $10 (commiteada)
    s = datos_reales.abrir_paper(db, capital_inicial=100_000.0, fecha=date(2026, 1, 1))
    core.registrar_fill(s, ticker="OKLO", lado="buy", shares=500, precio=10.0, fecha_fill=date(2026, 1, 2))
    s.commit()
    s.close()

    orig = datos_reales.abrir_paper
    monkeypatch.setattr(datos_reales, "abrir_paper", lambda **k: orig(db, **k))
    monkeypatch.setattr(datos_reales, "recolectar_snapshots", lambda tks: {t: {} for t in tks})
    monkeypatch.setattr(datos_reales, "precios_de", lambda snaps: {"OKLO": 12.0})
    monkeypatch.setattr(cd, "_EJECUTADAS", tmp_path / "ejec.json")

    dura = AccionSalida("OKLO", "A", "SALIDA_TOTAL", "tier A: quiebra", "8-K:acc1")
    fills = cd._ejecutar_salidas([dura])
    assert fills, "debería haber ejecutado la venta"

    # reabrir el paper desde disco: la posición tiene que haber quedado en 0 (commiteada)
    s2 = orig(db, fecha=date(2026, 1, 4))
    assert _pos_shares(s2, "OKLO", {"OKLO": 12.0}) == 0
    s2.close()


def test_salida_idempotente_no_revende(tmp_path, monkeypatch):
    db = tmp_path / "paper.db"
    s = datos_reales.abrir_paper(db, capital_inicial=100_000.0, fecha=date(2026, 1, 1))
    core.registrar_fill(s, ticker="OKLO", lado="buy", shares=500, precio=10.0, fecha_fill=date(2026, 1, 2))
    s.commit()
    s.close()

    orig = datos_reales.abrir_paper
    monkeypatch.setattr(datos_reales, "abrir_paper", lambda **k: orig(db, **k))
    monkeypatch.setattr(datos_reales, "recolectar_snapshots", lambda tks: {t: {} for t in tks})
    monkeypatch.setattr(datos_reales, "precios_de", lambda snaps: {"OKLO": 12.0})
    monkeypatch.setattr(cd, "_EJECUTADAS", tmp_path / "ejec.json")

    dura = AccionSalida("OKLO", "A", "SALIDA_TOTAL", "tier A: quiebra", "8-K:acc1")
    cd._ejecutar_salidas([dura])
    fills2 = cd._ejecutar_salidas([dura])           # misma salida (misma clave) → no repite
    assert fills2 == []
