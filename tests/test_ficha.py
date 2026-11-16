"""Ficha viva (r9, doc 80 §F): puente, zonas/gatillos y el caso del operador (cara → cae → COMPRA sin re-deep)."""
from dataclasses import dataclass

from backend.agentes.ficha import (EscenarioF, backfill_desde_dossier, calcular_puente, cash_bridge_ok,
                                    cash_terminal, recalcular, valor_accion)

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


# ----------------------------------------------------------------- Fase 1 (doc 83): tests de aceptación del cash bridge

def test_aceptacion_A_caja_de_obra_no_se_cuenta_dos_veces():
    # OKLO-like: caja hoy $3B, EV terminal $700M (las plantas YA están en el EBITDA operativo). La caja es el
    # presupuesto de obra → se consume. El bridge NO debe sumar los $3B intactos + las plantas.
    oklo = EscenarioF("bear", metrica_terminal=700e6, multiplo_salida=1.0, anios=6, prob=0.5,
                      fcf_cumulative=-2.5e9)                    # quema $2.5B construyendo
    v_bridge = valor_accion(oklo, deuda_neta=-3e9, acciones=100e6, dilucion_total=0.0)  # deuda_neta −3B = caja neta 3B
    # frozen (viejo): sumaría la caja intacta → 700M + 3B = 3.7B / 100M = $37
    congelado = EscenarioF("bear", metrica_terminal=700e6, multiplo_salida=1.0, anios=6, prob=0.5)  # fcf=0
    v_congelado = valor_accion(congelado, deuda_neta=-3e9, acciones=100e6, dilucion_total=0.0)
    assert v_congelado == 37.0 and abs(v_bridge - 12.0) < 1e-6   # 700M+3B−2.5B = 1.2B/100M = $12 < $37
    # assert de caja: C_T = 3B − 2.5B = 0.5B ≥ 0 → ok; si quemara $3.5B, funding unresolved
    assert cash_bridge_ok(oklo, caja_hoy=3e9)[0] is True
    quema_de_mas = EscenarioF("bear", 700e6, 1.0, 6, 0.5, fcf_cumulative=-3.5e9)
    assert cash_bridge_ok(quema_de_mas, caja_hoy=3e9, caja_minima=0.0)[0] is False   # gastó caja que no tiene


def test_aceptacion_B_emision_sube_caja_Y_acciones():
    base = EscenarioF("base", 200e6, 10.0, 4, 0.5)              # EV $2B, sin raise → $20
    assert valor_accion(base, deuda_neta=0, acciones=100e6, dilucion_total=0.0) == 20.0
    # emitir $1B por 10M de acciones: la caja entra (+$1B al equity) Y las acciones entran (+10M al denominador)
    con_raise = EscenarioF("base", 200e6, 10.0, 4, 0.5, new_equity_proceeds=1e9, new_equity_shares=10e6)
    v = valor_accion(con_raise, deuda_neta=0, acciones=100e6, dilucion_total=0.0)
    assert abs(v - (3e9 / 110e6)) < 1e-6                        # 3B/110M = $27.27, los dos efectos reconciliados
    # error de doble conteo que EVITAMOS: diluir sin reconocer los fondos daría menos ($2B/110M = $18.18)
    solo_dilucion = EscenarioF("base", 200e6, 10.0, 4, 0.5, new_equity_shares=10e6)
    assert valor_accion(solo_dilucion, deuda_neta=0, acciones=100e6, dilucion_total=0.0) < 20.0


def test_aceptacion_C_conversion_borra_deuda_y_agrega_acciones():
    # EV $3B, deuda_neta $1B (incluye $500M de convertible). Sin conversión → $20.
    sin = EscenarioF("base", 300e6, 10.0, 4, 0.5)
    assert valor_accion(sin, deuda_neta=1e9, acciones=100e6, dilucion_total=0.0) == 20.0
    # conversión: la obligación de $500M desaparece (vuelve al equity) Y aparecen 20M de acciones — no se cuenta dos veces
    conv = EscenarioF("base", 300e6, 10.0, 4, 0.5, debt_converted=500e6, shares_converted=20e6)
    v = valor_accion(conv, deuda_neta=1e9, acciones=100e6, dilucion_total=0.0)
    assert abs(v - (2.5e9 / 120e6)) < 1e-6                      # (3B−1B+0.5B)/120M = $20.83


def test_aceptacion_D_bear_con_preferida_senior_puede_valer_cero():
    # EV $1B, deuda_neta $0.5B, preferida senior $2B (K). El común queda detrás → vale CERO (responsabilidad limitada).
    bear = EscenarioF("bear", 100e6, 10.0, 4, 0.4, senior_claims=2e9)
    assert valor_accion(bear, deuda_neta=0.5e9, acciones=100e6, dilucion_total=0.0) == 0.0
    # sin la preferida, el mismo escenario vale (1B−0.5B)/100M = $5 → la preferencia se respeta
    sin_pref = EscenarioF("bear", 100e6, 10.0, 4, 0.4)
    assert valor_accion(sin_pref, deuda_neta=0.5e9, acciones=100e6, dilucion_total=0.0) == 5.0


def test_dilucion_scenario_dependent():
    # la dilución SBC del escenario pisa a la de la ficha; bull diluye poco, bear más
    bull = EscenarioF("bull", 100e6, 10.0, 4, 0.3, dilucion_sbc=0.05)
    bear = EscenarioF("bear", 100e6, 10.0, 4, 0.3, dilucion_sbc=0.40)
    assert abs(valor_accion(bull, deuda_neta=0, acciones=100e6, dilucion_total=0.20) - (1e9 / 105e6)) < 1e-6
    assert abs(valor_accion(bear, deuda_neta=0, acciones=100e6, dilucion_total=0.20) - (1e9 / 140e6)) < 1e-6


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
