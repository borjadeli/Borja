"""Pieza 3 del mapa MVP (doc 89 §3): clasificación de estado del cuello + same-store.
Incluye el GATE del test de $0 (§1): fotónica → confirmado, quantum → promesa."""
from __future__ import annotations

from backend.agentes.mapa_atribucion import Atribuible
from backend.agentes.mapa_vivo import (TableroCuello, clasificar_estado,
                                        crecimiento_same_store)

M = 1_000_000.0


def _tab(cuello, *, op, mb=0.35, crec=0.4, n=4, capex=0.10, inv=0.15, fecha="2026-09-30"):
    return TableroCuello(cuello=cuello, fecha=fecha, n_empresas=n, ventas_total=None,
                         margen_bruto_pond=mb, capex_sobre_ventas=capex, inventario_sobre_ventas=inv,
                         rpo_total=None, crecimiento_pond=crec, op_sobre_ventas=op)


def _atrib(cuello, por_empresa, *, cobertura=0.85):
    tot_atrib = sum(por_empresa.values())
    return Atribuible(cuello=cuello, revenue_atribuible=round(tot_atrib, 2), revenue_total=round(tot_atrib / cobertura, 2),
                      cobertura=cobertura, n_conocidas=len(por_empresa), n_total=len(por_empresa),
                      desconocidas=[], atribuible_por_empresa=por_empresa)


def test_gate_fotonica_confirmado():
    tab = _tab("fotonica", op=0.07)                       # +7% op margin (el test de $0)
    atrib = _atrib("fotonica", {"LITE": 8_000 * M, "COHR": 4_000 * M})
    e = clasificar_estado(tab, atrib)
    assert e.estado == "confirmado", e.razon
    assert all(e.checks.values())


def test_gate_quantum_promesa_por_perdida_operativa():
    tab = _tab("quantum", op=-5.06, crec=0.5)             # −506% op margin
    atrib = _atrib("quantum", {"IONQ": 100 * M, "RGTI": 62 * M})
    e = clasificar_estado(tab, atrib)
    assert e.estado == "promesa"
    assert e.checks["op_no_catastrofica"] is False        # el gate que lo caza
    assert e.checks["materialidad"] is True               # tiene revenue, pero no economía


def test_materialidad_falla_sin_dos_empresas_grandes():
    tab = _tab("nicho", op=0.10)
    atrib = _atrib("nicho", {"AAA": 200 * M, "BBB": 10 * M})   # solo 1 empresa ≥$25M
    e = clasificar_estado(tab, atrib)
    assert e.estado == "promesa"
    assert e.checks["materialidad"] is False


def test_disolucion_tiene_prioridad():
    actual = _tab("optica", op=0.08, mb=0.20, crec=0.10, capex=0.20, inv=0.30)
    previo = _tab("optica", op=0.15, mb=0.35, crec=0.40, capex=0.10, inv=0.15, fecha="2026-06-30")
    atrib = _atrib("optica", {"X": 8_000 * M, "Y": 4_000 * M})   # economía "confirmable", pero se disuelve
    e = clasificar_estado(actual, atrib, previo=previo)
    assert e.estado == "resolviendose"


def test_same_store_excluye_entrante_nuevo():
    # crecimiento sobre comunes (LITE,COHR); NEW entra y NO infla el crecimiento
    g = crecimiento_same_store({"LITE": 110, "COHR": 60, "NEW": 500}, {"LITE": 100, "COHR": 50})
    assert g == round((170 - 150) / 150, 4)

    tab = _tab("fotonica", op=0.07, crec=9.0)             # crec crudo inflado
    atrib = _atrib("fotonica", {"LITE": 8_000 * M, "COHR": 4_000 * M})
    e = clasificar_estado(tab, atrib, crec_same_store=g)  # el same-store manda
    assert e.economia["crecimiento"] == g


def test_no_medible_cuando_nadie_presenta():
    tab = _tab("modulos_800g", op=None, mb=None, crec=None, n=0)
    atrib = Atribuible("modulos_800g", None, 0.0, None, 0, 0, [], {})
    e = clasificar_estado(tab, atrib)
    assert e.estado == "no_medible"


def test_cobertura_baja_matiza_no_cambia_estado():
    tab = _tab("fotonica", op=0.07)
    atrib = _atrib("fotonica", {"LITE": 8_000 * M, "COHR": 4_000 * M}, cobertura=0.30)
    e = clasificar_estado(tab, atrib)
    assert e.estado == "confirmado"      # la economía atribuible alcanza
    assert e.cobertura_baja is True      # pero avisa que la cobertura es baja


def test_sostenido_2t_false_veta_confirmado():
    tab = _tab("fotonica", op=0.07)
    atrib = _atrib("fotonica", {"LITE": 8_000 * M, "COHR": 4_000 * M})
    e = clasificar_estado(tab, atrib, sostenido_2t=False)      # el 2T no se sostuvo
    assert e.estado == "promesa"
    assert e.checks["crecimiento_positivo"] is False


def test_historia_corta_marca_confirmado_provisional():
    tab = _tab("fotonica", op=0.07)
    atrib = _atrib("fotonica", {"LITE": 8_000 * M, "COHR": 4_000 * M})
    e = clasificar_estado(tab, atrib, historia_corta=True)
    assert e.estado == "confirmado"
    assert e.historia_corta is True
    assert "PROVISIONAL" in e.razon
