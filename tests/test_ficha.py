"""Ficha viva (r9, doc 80 §F): puente, zonas/gatillos y el caso del operador (cara → cae → COMPRA sin re-deep)."""
from dataclasses import dataclass

from backend.agentes.ficha import (EscenarioF, backfill_desde_dossier, calcular_puente, recalcular,
                                    valor_accion)

# escenarios de una empresa con equity bridge limpio (sin deuda neta, 100M acciones, sin dilución)
_ESC = [
    EscenarioF("bear", metrica_terminal=200e6, multiplo_salida=5, anios=4, prob=0.25),   # EV 1.0B → $10/acc
    EscenarioF("base", metrica_terminal=500e6, multiplo_salida=8, anios=4, prob=0.50),   # EV 4.0B → $40/acc
    EscenarioF("bull", metrica_terminal=900e6, multiplo_salida=12, anios=4, prob=0.25),  # EV 10.8B → $108/acc
]
_POL = dict(deuda_neta=0.0, acciones=100e6, dilucion_total=0.0)


def test_valor_accion_equity_bridge():
    # bear: (200M×5 − 0) / (100M×1) = $10/acc
    assert valor_accion(_ESC[0], **_POL) == 10.0
    # con deuda neta 500M: (1.0B − 500M)/100M = $5
    assert valor_accion(_ESC[0], deuda_neta=500e6, acciones=100e6, dilucion_total=0.0) == 5.0
    # con 50% de dilución: 1.0B / (100M×1.5) = $6.67
    assert abs(valor_accion(_ESC[0], deuda_neta=0, acciones=100e6, dilucion_total=0.5) - 6.6667) < 1e-3


def test_puente_ordena_zonas():
    # satélite (hurdle 20%, piso 50%). E[V] = .25×10 + .5×40 + .25×108 = 49.5
    p = calcular_puente(_ESC, precio=40.0, clase="satelite", **_POL)
    assert p is not None
    puente, gat, lat = p
    assert puente.e_v == 49.5 and puente.horizonte == 4
    # compra = min(E[V]/(1.2)^4 , V_bear/(1−.5)) = min(49.5/2.0736, 10/0.5=20) = min(23.87, 20) = 20 (piso manda)
    assert abs(gat.compra - 20.0) < 1e-2
    # recorte = 49.5/(1.08)^4 = 36.39 ; salida = 108/(1.08)^4 = 79.4
    assert abs(gat.recorte - 36.39) < 0.1 and abs(gat.salida - 79.4) < 0.2
    assert gat.compra < gat.recorte < gat.salida          # ordenamiento del espectro de precios


def test_zonas_segun_precio():
    def zona(precio):
        return calcular_puente(_ESC, precio=precio, clase="satelite", **_POL)[2].zona
    assert zona(18) == "COMPRA"      # ≤ 20
    assert zona(30) == "MANTENER"    # entre compra (20) y recorte (36.4)
    assert zona(50) == "RECORTE"     # entre recorte (36.4) y salida (79.4)
    assert zona(90) == "SALIDA"      # > 79.4 (ni el bull paga el mínimo)


def test_piso_bear_limita_la_compra():
    # aislado: MISMO hurdle, con piso vs sin piso → el piso solo puede EXIGIR comprar más abajo (o igual)
    h = {"x": 0.20}
    sin_piso = calcular_puente(_ESC, precio=40, clase="x", hurdles=h, pisos={"x": None}, **_POL)[1].compra
    con_piso = calcular_puente(_ESC, precio=40, clase="x", hurdles=h, pisos={"x": 0.50}, **_POL)[1].compra
    assert con_piso <= sin_piso
    # hurdle-only = 49.5/1.2^4 = 23.87; con piso = min(23.87, V_bear/0.5=20) = 20 (el piso manda)
    assert abs(sin_piso - 23.87) < 0.1 and abs(con_piso - 20.0) < 1e-2


@dataclass
class _Inv:
    analyst_classification: str


@dataclass
class _Esc:
    nombre: str
    metrica_terminal: float
    multiplo_salida: float
    anios: int
    prob: float


@dataclass
class _Fals:
    afirmacion: str
    fecha_limite: str


@dataclass
class _Dossier:
    invertibilidad: _Inv
    escenarios: list
    falsador: _Fals
    dilucion_esperada_pct: float
    negocio_y_posicion_cuello: str = "Proveedor líder del cuello X."


def test_caso_del_operador_cara_cae_compra_sin_redeep():
    """El corazón del doc 80: deep sobre una buenísima pero CARA → ficha en BANCA (MANTENER). Dos meses después
    cae a zona → el código la marca COMPRA recalculando SOLO el reloj rápido, sin re-correr el comité."""
    dossier = _Dossier(
        invertibilidad=_Inv("satelite"),
        escenarios=[_Esc("bear", 200e6, 5, 4, 0.25), _Esc("base", 500e6, 8, 4, 0.50),
                    _Esc("bull", 900e6, 12, 4, 0.25)],
        falsador=_Fals("no logra el contrato", "2027-06-30"), dilucion_esperada_pct=0.0)
    # analizada CARA a $52 → ficha viva, zona MANTENER/RECORTE, sin señal de compra
    ficha = backfill_desde_dossier("XYZ", dossier, deuda_neta=0.0, acciones=100e6, precio=52.0)
    assert ficha.estado == "VIGENTE" and ficha.clase_d4 == "satelite"
    assert ficha.latido.zona in ("MANTENER", "RECORTE")
    escen_antes = [e.metrica_terminal for e in ficha.escenarios]

    # dos meses después cae a $18 — SOLO se recalcula el reloj rápido (cero LLM, cero comité)
    recalcular(ficha, precio=18.0)
    assert ficha.latido.zona == "COMPRA"                   # ahora SÍ es compra
    assert ficha.puente.precio == 18.0
    # la TESIS no se tocó (reloj lento intacto): mismos escenarios, mismo dossier
    assert [e.metrica_terminal for e in ficha.escenarios] == escen_antes
    assert ficha.estado == "VIGENTE"
