"""Pieza 5 del mapa MVP (doc 89 §9.2): las 3 líneas del cuello (estado·economía·cobertura) en el packet del PM."""
from __future__ import annotations

from dataclasses import dataclass

from backend.agentes.mapa_vivo import EstadoCuello
from backend.agentes.packet_pm import construir_packet, render_packet

# reusa el stub de dossier del test de packet
from tests.test_packet_pm import _ficha


def _estado(cuello, estado, *, ra=12_000e6, op=0.07, cobertura=0.85):
    return EstadoCuello(cuello=cuello, estado=estado, razon="", cobertura=cobertura, cobertura_baja=(cobertura < 0.5),
                        checks={}, economia={"revenue_atribuible": ra, "op_sobre_ventas": op})


def test_cuello_confirmado_llega_al_packet():
    f = _ficha("LITE", 30.0)
    f.cuello = "fotonica"
    pack = construir_packet(fichas={"LITE": f}, posiciones={"LITE": 0.06}, caja_pct=0.5, equity=100_000.0,
                            estados_cuello={"fotonica": _estado("fotonica", "confirmado")})
    assert len(pack.cuellos) == 1
    assert pack.cuellos[0]["estado"] == "confirmado"
    assert pack.cuellos[0]["tickers"] == ["LITE"]
    assert "MAPA DE CUELLOS" in render_packet(pack)


def test_cuello_en_disolucion_genera_alerta_antitrap():
    f = _ficha("XYZ", 50.0)        # tenencia
    f.cuello = "optica_legacy"
    pack = construir_packet(fichas={"XYZ": f}, posiciones={"XYZ": 0.06}, caja_pct=0.5, equity=100_000.0,
                            estados_cuello={"optica_legacy": _estado("optica_legacy", "resolviendose")})
    assert any(a["tipo"] == "cuello_disolucion" and "XYZ" in a["ticker"] for a in pack.alertas)
    assert any("value-trap" in a["detalle"] for a in pack.alertas if a["tipo"] == "cuello_disolucion")


def test_sin_estados_cuello_no_rompe_el_packet():
    f = _ficha("MP", 50.0)
    pack = construir_packet(fichas={"MP": f}, posiciones={"MP": 0.06}, caja_pct=0.5, equity=100_000.0)
    assert pack.cuellos == []        # retrocompatible: sin estados_cuello, no hay sección
