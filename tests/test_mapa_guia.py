"""Pieza 4 del mapa MVP (doc 89 §3.4/§9.4): el cuello como FILTRO/guía al PM, SIN bonus."""
from __future__ import annotations

from backend.agentes.mapa_vivo import EstadoCuello, guia_de_cuello


def _estado(estado, *, cobertura=0.85, cobertura_baja=False):
    return EstadoCuello(cuello="fotonica", estado=estado, razon="", cobertura=cobertura,
                        cobertura_baja=cobertura_baja, checks={}, economia={})


def test_confirmado_es_contexto():
    g = guia_de_cuello(_estado("confirmado"))
    assert g["accion"] == "contexto"


def test_promesa_a_watchlist():
    g = guia_de_cuello(_estado("promesa"))
    assert g["accion"] == "watchlist"
    assert "WATCHLIST" in g["nota"]


def test_disolucion_pide_normalizar_margenes():
    g = guia_de_cuello(_estado("resolviendose"))
    assert g["accion"] == "normalizar_margenes"
    assert "value-trap" in g["nota"]


def test_no_medible_es_manual():
    g = guia_de_cuello(_estado("no_medible"))
    assert g["accion"] == "manual"


def test_cobertura_baja_se_agrega_como_advertencia():
    g = guia_de_cuello(_estado("confirmado", cobertura=0.30, cobertura_baja=True))
    assert "cobertura baja" in g["nota"]
    assert "30%" in g["nota"]
