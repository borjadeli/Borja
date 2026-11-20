"""Pieza 2 del mapa MVP (doc 89 §8): atribución/pureza empresa→cuello + cobertura (DESCONOCIDA honesto)."""
from __future__ import annotations

import textwrap

from backend.agentes.mapa_atribucion import MapaAtribucion, revenue_atribuible


def _overlay(tmp_path):
    p = tmp_path / "atrib.yaml"
    p.write_text(textwrap.dedent("""
        fotonica:
          LITE:
            peso_pureza: 0.80
            rol: proveedor_critico
            fuente: "10-K"
          FN:
            peso_pureza: 0.30
    """), encoding="utf-8")
    return MapaAtribucion(p)


def test_desconocida_es_default(tmp_path):
    atrib = _overlay(tmp_path)
    exp = atrib.get("fotonica", "AAOI")       # no anotada
    assert exp.desconocida
    assert exp.peso_pureza is None


def test_exposicion_estructurada(tmp_path):
    atrib = _overlay(tmp_path)
    exp = atrib.get("fotonica", "lite")       # case-insensitive
    assert exp.peso_pureza == 0.80
    assert exp.rol == "proveedor_critico"
    assert exp.fuente == "10-K"
    assert not exp.desconocida


def test_atribuible_descuenta_desconocidas_y_pesos(tmp_path):
    atrib = _overlay(tmp_path)
    # LITE 10000 (peso .80 → 8000), FN 5000 (peso .30 → 1500), AAOI 2000 (DESCONOCIDA → no suma)
    r = revenue_atribuible("fotonica", {"LITE": 10_000.0, "FN": 5_000.0, "AAOI": 2_000.0}, atrib)
    assert r.revenue_total == 17_000.0
    assert r.revenue_atribuible == 9_500.0          # 8000 + 1500
    assert r.n_conocidas == 2
    assert r.n_total == 3
    assert r.desconocidas == ["AAOI"]
    # cobertura = revenue CON peso conocido / total = (10000+5000)/17000 (redondeada a 4 decimales)
    assert r.cobertura == round(15_000.0 / 17_000.0, 4)


def test_sin_ninguna_conocida_atribuible_none(tmp_path):
    atrib = _overlay(tmp_path)
    r = revenue_atribuible("quantum", {"IONQ": 100.0, "RGTI": 50.0}, atrib)   # cuello sin anotar
    assert r.revenue_atribuible is None             # no hay base para medir economía-de-cuello
    assert r.cobertura == 0.0
    assert r.desconocidas == ["IONQ", "RGTI"]


def test_seed_real_carga(tmp_path):
    # el YAML versionado real debe cargar con los nombres de nodo REALES de nx_*
    atrib = MapaAtribucion()
    fn = atrib.get("Manufactura óptica por contrato (EMS de precisión)", "FN")
    assert fn.peso_pureza == 0.60               # Fabrinet: EMS óptico, el caso de atribución (§8.1)
    assert fn.rol == "integrador"
    mp = atrib.get("Tierras raras (NdPr, Dy, Tb) e imanes", "MP")
    assert mp.peso_pureza == 0.90               # MP Materials ≈ tierras raras puro
