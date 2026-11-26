"""Gate 0 (doc 91 §8.ter) — tests de MUTACIÓN: una propiedad, no casos sueltos. Partiendo de un input VÁLIDO, CUALQUIER
mutación que lo corrompa (%/fracción, precio 0, rango invertido, clave ausente, NaN, typo) NUNCA puede producir un
resultado MÁS PERMISIVO: una banda inválida → None, una apertura corrupta → nunca EJECUTAR. Es la red que evita que el
fail-open vuelva a entrar por un camino nuevo. Determinista, $0."""
import math

import pytest

from backend.agentes.banda import banda_ciclica, banda_compounder, banda_infra
from backend.agentes.permiso_ejecucion import execution_permission

NAN, INF = float("nan"), float("inf")

TIERS = {"CORE": {"min": 0.05, "max": 0.10}}
# Apertura VÁLIDA que ejecuta: la línea base de la que parten todas las mutaciones.
APERTURA_OK = {
    "accion": "abrir", "motivo_accion": "discrecional", "ticker": "XYZ", "verificacion": "PASS",
    "tier": "CORE", "tiers_cfg": TIERS, "arquetipo": "ciclica", "peso_objetivo": 0.07, "cap": 0.10,
    "falsador_id": "f1", "falsador_sobre_metrica": True, "metrica_obligatoria_null": False,
    "flags_alta_sin_responder": False, "bloqueo_datos": [], "crea_stub_o_viola_ips": False,
}
# claves PORTANTES de una APERTURA: si cualquiera se cae, NO puede seguir ejecutando (confirmación positiva).
# (motivo_accion no entra: solo es material para reducciones, no para aperturas.)
_PORTANTES = ["accion", "verificacion", "tier", "tiers_cfg", "peso_objetivo", "cap",
              "falsador_id", "falsador_sobre_metrica", "metrica_obligatoria_null", "flags_alta_sin_responder",
              "bloqueo_datos", "crea_stub_o_viola_ips"]


def test_la_linea_base_ejecuta():
    # sin esto, 'bloquear todo' pasaría todas las mutaciones trivialmente.
    assert execution_permission(APERTURA_OK) == ("EJECUTAR", [])


@pytest.mark.parametrize("clave", _PORTANTES)
def test_quitar_cualquier_clave_portante_no_ejecuta(clave):
    ctx = dict(APERTURA_OK); ctx.pop(clave)
    assert execution_permission(ctx)[0] != "EJECUTAR"


@pytest.mark.parametrize("clave", ["peso_objetivo", "cap"])
@pytest.mark.parametrize("valor", [NAN, INF, -INF, None])
def test_corromper_numericos_no_ejecuta(clave, valor):
    assert execution_permission({**APERTURA_OK, clave: valor})[0] != "EJECUTAR"


@pytest.mark.parametrize("peso", [5.0, 0.7, 70])   # fracción escrita como % / escala x10 → sobre el cap o la banda
def test_confusion_fraccion_porcentaje_en_peso_no_ejecuta(peso):
    assert execution_permission({**APERTURA_OK, "peso_objetivo": peso})[0] != "EJECUTAR"


@pytest.mark.parametrize("hecho", ["metrica_obligatoria_null", "flags_alta_sin_responder", "crea_stub_o_viola_ips"])
def test_poner_un_hecho_operativo_en_problema_no_ejecuta(hecho):
    assert execution_permission({**APERTURA_OK, hecho: True})[0] != "EJECUTAR"


def test_bloqueo_datos_none_es_no_chequeado_no_ejecuta():
    assert execution_permission({**APERTURA_OK, "bloqueo_datos": None})[0] != "EJECUTAR"


@pytest.mark.parametrize("accion", ["abr", "comprar", "aumenta", "", None, 7, "mantenerr"])
def test_typo_en_accion_bloquea(accion):
    # un typo / tipo inválido (incluso un int) → BLOQUEAR, nunca crashea ni ejecuta.
    assert execution_permission({**APERTURA_OK, "accion": accion})[0] == "BLOQUEAR"


# ── banda: una mutación de unidad/dominio NUNCA da una banda (y menos una más permisiva) ──
@pytest.mark.parametrize("precio", [0, -1, NAN, INF, 30_000])   # 0/neg/NaN/inf y escala x1000 (95 vs 40.000)
def test_mutar_precio_ciclica_no_da_banda(precio):
    assert banda_ciclica(30, 40, 80) == "COMPRA_FUERTE"        # la base es válida
    assert banda_ciclica(precio, 40, 80) is None


def test_rango_ciclica_invertido_no_da_banda():
    assert banda_ciclica(60, 80, 40) is None


@pytest.mark.parametrize("c", [90, 30, 4.0, True, NAN, -0.1, INF])   # % en vez de fracción / bool / fuera de [0,3]
def test_mutar_cobertura_infra_no_da_banda(c):
    assert banda_infra(0.9) == "COMPRA"                        # la base es válida
    assert banda_infra(c) is None


@pytest.mark.parametrize("g", [7, 70, NAN, INF, True])         # fracción escrita como % / bool / no finito
def test_mutar_g_compounder_no_da_banda(g):
    assert banda_compounder(0.07, 0.08, 0.12) == "COMPRA"      # la base es válida
    assert banda_compounder(g, 0.08, 0.12) is None


def test_bordes_de_compounder_en_porcentaje_no_dan_banda():
    # g en fracción pero el rango sostenible en % (8,12 en vez de 0.08,0.12) → unidad incoherente → None.
    assert banda_compounder(0.07, 8, 12) is None


def test_ninguna_mutacion_de_banda_es_mas_permisiva_que_la_valida():
    """Propiedad global: toda mutación de los insumos de una banda válida cae a None (nunca a una banda, menos a una
    más alta). COMPRA_FUERTE es la banda más permisiva (habilita el cap más grande)."""
    base = banda_ciclica(30, 40, 80)
    assert base == "COMPRA_FUERTE"
    for mut in [banda_ciclica(0, 40, 80), banda_ciclica(NAN, 40, 80), banda_ciclica(30, 80, 40),
                banda_ciclica(30_000, 40, 80), banda_ciclica(30, -40, 80)]:
        assert mut is None
