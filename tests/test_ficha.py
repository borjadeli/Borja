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
    # satélite r9a: hurdle 15%, piso 50% como pérdida ESPERADA. E[V] = .25×10 + .5×40 + .25×108 = 49.5
    p = calcular_puente(_ESC, precio=40.0, clase="satelite", **_POL)
    assert p is not None
    puente, gat, lat = p
    assert puente.e_v == 49.5 and puente.horizonte == 4
    # compra = E[V]/(1.15)^4 = 49.5/1.749 = 28.30 (el piso esperado no ata: prob_bear 0.25 × pérdida < 0.50)
    assert abs(gat.compra - 28.30) < 0.1
    # recorte = 49.5/(1.08)^4 = 36.39 ; salida = 108/(1.08)^4 = 79.4
    assert abs(gat.recorte - 36.39) < 0.1 and abs(gat.salida - 79.4) < 0.2
    assert gat.compra < gat.recorte < gat.salida          # ordenamiento del espectro de precios


def test_zonas_segun_precio():
    def zona(precio):
        return calcular_puente(_ESC, precio=precio, clase="satelite", **_POL)[2].zona
    assert zona(25) == "COMPRA"      # ≤ 28.3
    assert zona(32) == "MANTENER"    # entre compra (28.3) y recorte (36.4)
    assert zona(50) == "RECORTE"     # entre recorte (36.4) y salida (79.4)
    assert zona(90) == "SALIDA"      # > 79.4 (ni el bull paga el mínimo)


def test_piso_perdida_esperada():
    # el piso ahora es pérdida ESPERADA (prob_bear × pérdida_bear ≤ piso). Con un piso muy chico, ata y baja la
    # compra; con uno holgado, no ata. prob_bear=0.25, V_bear=10.
    h = {"x": 0.15}
    # piso 0.05: P ≤ V_bear/(1 − 0.05/0.25) = 10/(1−0.2) = 12.5 → la compra baja a 12.5 (piso manda)
    con_piso = calcular_puente(_ESC, precio=40, clase="x", hurdles=h, pisos={"x": 0.05}, **_POL)[1].compra
    assert abs(con_piso - 12.5) < 1e-2
    # sin piso: compra = E[V]/1.15^4 = 28.30 (solo el hurdle)
    sin_piso = calcular_puente(_ESC, precio=40, clase="x", hurdles=h, pisos={"x": None}, **_POL)[1].compra
    assert abs(sin_piso - 28.30) < 0.1 and con_piso < sin_piso


def test_especulativa_exige_bull_5x():
    # especulativa: compra = min(E[V]/1.2^4=23.87, V_bull/5=108/5=21.6) → el bull≥5× ata
    g = calcular_puente(_ESC, precio=40, clase="especulativa", **_POL)[1]
    assert abs(g.compra - 21.6) < 0.1


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
