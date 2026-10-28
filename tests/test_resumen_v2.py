"""Tests del digest advisory v2 (formatter puro). Sin API."""
from dataclasses import dataclass

from backend.agentes.resumen_v2 import DossierResumen, PosicionResumen, render_digest


@dataclass
class _Dec:
    ticker: str
    accion: str
    peso_resultante: float
    conviccion_0_1: float
    verif_veredicto: str
    tesis: str
    falsador_afirmacion: str
    falsador_fecha_limite: str
    ejecutada: bool = True


def test_render_incluye_posiciones_decision_y_dossier():
    pos = [PosicionResumen("OKLO", 112, 26.56, 0.03)]
    dec = [_Dec("OKLO", "comprar", 0.03, 0.35, "pass", "opción regulatoria barata",
                "no firma PPA al 2028", "2028-06-30")]
    dos = {"OKLO": DossierResumen(veredicto="pass", bull="mejor capitalizada", bear="historia de financiamiento",
                                  falsador="no cumple hito", falsador_fecha="2028-06-30",
                                  red_flags=["dilucion[media]"])}
    out = render_digest(ciclo="2026-10-28", equity=100_000, caja_pct=0.97, posiciones=pos,
                        decisiones=dec, dossiers=dos, gasto_mes=25.46, tope_mes=40.0)
    assert "OKLO" in out and "112 acc @ $26.56" in out and "3.0%" in out
    assert "COMPRAR OKLO" in out and "verif PASS" in out and "opción regulatoria barata" in out
    assert "bull: mejor capitalizada" in out and "red flags: dilucion[media]" in out
    assert "$25.46 / $40" in out


def test_render_cartera_vacia_y_sin_decisiones():
    out = render_digest(ciclo="c", equity=100_000, caja_pct=1.0, posiciones=[], decisiones=[],
                        dossiers={}, gasto_mes=0.0, tope_mes=40.0)
    assert "100% caja" in out and "(ninguna)" in out


def test_render_marca_no_ejecutada():
    dec = [_Dec("OKLO", "comprar", 0.0, 0.3, "review", "t", "f", "2027-01-01", ejecutada=False)]
    out = render_digest(ciclo="c", equity=100_000, caja_pct=1.0, posiciones=[], decisiones=dec,
                        dossiers={}, gasto_mes=0.0, tope_mes=40.0)
    assert "NO EJECUTADA" in out
