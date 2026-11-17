"""Ficha viva (r9, doc 80 §F): puente, zonas/gatillos y el caso del operador (cara → cae → COMPRA sin re-deep)."""
from dataclasses import dataclass

from backend.agentes.ficha import (EscenarioF, Instrumento, backfill_desde_dossier, bajo_caja_neta,
                                    calcular_puente, cash_bridge_ok, cash_terminal, recalcular,
                                    resolver_instrumentos, valor_accion)


def test_recompra_achica_acciones_y_sube_valor():
    # NNDM (bache del cruce): una recompra baja la caja (en distributions) Y retira acciones (buyback_shares).
    # Comprar barato achica el denominador → sube V/acción. Sin buyback_shares sería pura destrucción.
    base = EscenarioF("base", 100e6, 1.0, 4, 1.0)                 # EV $100M
    sin = valor_accion(base, deuda_neta=-300e6, acciones=200e6, dilucion_total=0.0)   # caja neta $300M
    con = EscenarioF("base", 100e6, 1.0, 4, 1.0, distributions=60e6, buyback_shares=43e6)
    v = valor_accion(con, deuda_neta=-300e6, acciones=200e6, dilucion_total=0.0)
    # sin: (100M+300M)/200M = $2.00 ; con: (100M+300M−60M)/(200M−43M) = 340M/157M = $2.17 → MÁS por la recompra
    assert abs(sin - 2.0) < 1e-6 and v > sin and abs(v - (340e6 / 157e6)) < 1e-4


def test_warrant_sin_strike_se_ejerce_no_se_tira():
    # ACHR (bache del cruce): un warrant listado sin strike (penny/vested, ITM) debe DILUIR, no caer al vacío.
    base = EscenarioF("base", 500e6, 2.0, 4, 1.0)                 # EV $1B, V alto
    warr = Instrumento("penny", "warrant", potential_shares=20e6, strike=None)
    v, det = resolver_instrumentos(base, deuda_neta=0.0, acciones=100e6, dilucion_total=0.0, instrumentos=[warr])
    assert det["convertidos"] == ["penny"] and det["acciones_nuevas"] == 20e6   # se ejerció (diluyó), no se ignoró


def test_bajo_caja_neta():
    # E[V] $1.04 con caja neta $1.59/acción → bajo_caja True (el caso NNDM)
    assert bajo_caja_neta(1.04, deuda_neta=-315e6, acciones=198e6) is True    # net cash/sh = 315/198 = $1.59
    assert bajo_caja_neta(5.0, deuda_neta=-315e6, acciones=198e6) is False    # E[V] arriba de la caja → ok
    assert bajo_caja_neta(1.0, deuda_neta=500e6, acciones=100e6) is False     # con deuda (no caja neta) → no aplica

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


# ----------------------------------------------------------------- Fase 2 (doc 83): resolver de instrumentos (MP)

# Inventario estilo MP: convertible 2030 YA en la deuda XBRL + preferida del DoD + warrant del DoD + capped call.
_MP_INSTR = [
    Instrumento("conv2030", "convertible", principal=862.8e6, conversion_price=21.74, potential_shares=39.68e6,
                en_deuda_xbrl=True, hedge_cap=31.06),                      # capped call hasta $31.06
    Instrumento("pref_dod", "convertible_preferred", principal=400e6, conversion_price=30.03,
                potential_shares=13.32e6, liq_preference=435.6e6),         # preferida: senior si no convierte
    Instrumento("warr_dod", "warrant", potential_shares=11.2e6, strike=30.03),
]


def test_resolver_bear_converts_no_convierten_preferida_senior():
    # bear barato: V bien abajo de $21,74 → nada convierte. La convertible ya está en la deuda (no se re-resta);
    # la preferida queda como claim SENIOR ($435,6M) delante del común; el warrant out-of-money no hace nada.
    bear = EscenarioF("bear", 300e6, 6.0, 4, 0.3)                          # EV $1.8B
    v, det = resolver_instrumentos(bear, deuda_neta=1.0e9, acciones=178e6, dilucion_total=0.0, instrumentos=_MP_INSTR)
    assert det["convertidos"] == []                                        # nada convierte en el bear
    assert abs(det["claims_senior"] - 435.6e6) < 1                         # la preferida pesa senior al común
    # equity = 1.8B − 1.0B(deuda, incluye el conv) − 435.6M(pref) = 364.4M / 178M = $2.05
    assert abs(v - (364.4e6 / 178e6)) < 1e-2


def test_resolver_bull_todo_convierte_sube_acciones_baja_deuda():
    # bull caro: V bien arriba de $31 → todo convierte. El conv (en deuda) suma acciones Y resta deuda; la
    # preferida convierte (deja de ser senior) y suma acciones; el warrant se ejerce (acciones + caja de strike).
    bull = EscenarioF("bull", 2.0e9, 10.0, 4, 0.3)                         # EV $20B → V alto
    v, det = resolver_instrumentos(bull, deuda_neta=1.0e9, acciones=178e6, dilucion_total=0.0, instrumentos=_MP_INSTR)
    assert set(det["convertidos"]) == {"conv2030", "pref_dod", "warr_dod"}
    assert abs(det["deuda_convertida"] - 862.8e6) < 1 and det["claims_senior"] == 0.0
    # acciones nuevas: conv 39.68M (V>cap 31.06 → capped call NO cubre) + pref 13.32M + warr 11.2M = 64.2M
    assert abs(det["acciones_nuevas"] - 64.2e6) < 1e5
    # equity = 20B − 1.0B + 0.8628B(conv vuelve) + warr_cash(30.03×11.2M=336.3M) = 20.199B / (178+64.2)M = $83.4
    assert abs(v - (20.1991e9 / 242.2e6)) < 0.5


def test_resolver_mandatory_convierte_aunque_OTM():
    # ALB (bache del bug-hunt): preferida MANDATORY convertible a $109.41. En el bear (V < $109) una opcional
    # quedaría como claim senior ($2.3B); una MANDATORY convierte igual → diluye, NO resta senior → bear MÁS ALTO.
    bear = EscenarioF("bear", 900e6, 7.0, 5, 0.3)              # EV $6.3B
    pref_mand = Instrumento("alb_pref", "convertible_preferred", principal=2.3e9, conversion_price=109.41,
                            potential_shares=21.0e6, en_deuda_xbrl=False, liq_preference=2.3e9, mandatory=True)
    v_mand, det_m = resolver_instrumentos(bear, deuda_neta=-100e6, acciones=118e6, dilucion_total=0.0,
                                          instrumentos=[pref_mand])
    assert det_m["convertidos"] == ["alb_pref"] and det_m["claims_senior"] == 0.0   # convirtió, no es senior
    # la MISMA preferida como OPCIONAL (mandatory=False) en el bear quedaría senior → vale MENOS
    pref_opt = Instrumento("alb_pref", "convertible_preferred", principal=2.3e9, conversion_price=109.41,
                           potential_shares=21.0e6, en_deuda_xbrl=False, liq_preference=2.3e9, mandatory=False)
    v_opt, det_o = resolver_instrumentos(bear, deuda_neta=-100e6, acciones=118e6, dilucion_total=0.0,
                                         instrumentos=[pref_opt])
    assert det_o["claims_senior"] == 2.3e9 and v_mand > v_opt   # la mandatory NO castiga el bear como la opcional


def test_resolver_capped_call_neutraliza_dilucion_bajo_el_cap():
    # V entre conv_price ($21.74) y cap ($31.06): el convertible convierte pero el capped call tapa su dilución.
    medio = EscenarioF("base", 600e6, 8.0, 4, 0.4)                         # EV $4.8B
    v, det = resolver_instrumentos(medio, deuda_neta=1.0e9, acciones=178e6, dilucion_total=0.0,
                                   instrumentos=[_MP_INSTR[0]])             # solo el convertible con capped call
    # si V cae en la ventana [21.74, 31.06], _shares_efectivas = 0 (hedge cubre) → no diluye
    if 21.74 <= v <= 31.06:
        assert det["acciones_nuevas"] == 0.0


def test_puente_usa_instrumentos_si_los_hay():
    escen = [EscenarioF("bear", 300e6, 6.0, 4, 0.3), EscenarioF("base", 600e6, 10.0, 4, 0.4),
             EscenarioF("bull", 2.0e9, 10.0, 4, 0.3)]
    con = calcular_puente(escen, precio=25.0, deuda_neta=1.0e9, acciones=178e6, dilucion_total=0.0,
                          clase="satelite", instrumentos=_MP_INSTR)
    sin = calcular_puente(escen, precio=25.0, deuda_neta=1.0e9, acciones=178e6, dilucion_total=0.0, clase="satelite")
    # el bear con la preferida senior vale MENOS que ignorando los instrumentos (que no restaría los $435.6M)
    assert con[0].valor_accion["bear"] < sin[0].valor_accion["bear"]


def test_backfill_mapea_flujos_del_cash_bridge():
    # F1 (doc 83): un dossier cuyos escenarios traen flujos de cash bridge → la ficha los mapea y el puente los usa.
    from backend.agentes.schemas import EscenarioValuacion
    escen = [
        EscenarioValuacion(nombre="bear", metrica_terminal=700e6, tipo_metrica="ebitda", multiplo_salida=1.0,
                           anios=6, prob=0.5, fcf_cumulative=-2.5e9),       # OKLO-like: quema la caja de obra
        EscenarioValuacion(nombre="base", metrica_terminal=900e6, tipo_metrica="ebitda", multiplo_salida=2.0,
                           anios=6, prob=0.3, fcf_cumulative=-1.5e9),
        EscenarioValuacion(nombre="bull", metrica_terminal=1.2e9, tipo_metrica="ebitda", multiplo_salida=4.0,
                           anios=6, prob=0.2, fcf_cumulative=-1.0e9),
    ]
    dossier = _Dossier(_Inv("especulativa"), escen, _Fals("no construye", "2028-06-30"), dilucion_esperada_pct=0.0)
    ficha = backfill_desde_dossier("OKLO", dossier, deuda_neta=-3e9, acciones=100e6, precio=20.0, caja=3e9)
    assert ficha.escenarios[0].fcf_cumulative == -2.5e9         # el flujo llegó a la ficha
    assert ficha.caja == 3e9
    # el bear ya NO suma los $3B de caja intactos: (700M + 3B − 2.5B)/100M = $12 (no $37 del puente viejo)
    assert abs(ficha.puente.valor_accion["bear"] - 12.0) < 1e-6


def test_reconciliacion_deuda_inventario_vs_pack():
    # VST (doc 83): el pack trae deuda_neta con $13.4B pero el Analista inventarió $21B de term_debt → el puente
    # debe usar la verificada ($21B) + marcar conflicted (el pack no manda sobre el filing).
    class _I:
        tipo = "term_debt"; en_deuda_xbrl = True; principal = 21.146e9
        id = "td"; conversion_price = None; potential_shares = 0.0; liq_preference = 0.0
        strike = None; hedge_cap = None; cita = "10-Q"
    dossier = _Dossier(_Inv("satelite"),
                       [_Esc("bear", 6e9, 7, 4, 0.3), _Esc("base", 8e9, 8, 4, 0.5), _Esc("bull", 10e9, 10, 4, 0.2)],
                       _Fals("x", "2027-01-01"), dilucion_esperada_pct=0.0)
    dossier.instrumentos = [_I()]
    # pack: deuda_neta $13.4B, caja $1B → gross $14.4B; inventario $21.146B > 14.4×1.2 → corrige
    f = backfill_desde_dossier("VST", dossier, deuda_neta=13.4e9, acciones=339e6, precio=128.0, caja=1e9)
    assert f.datos_conflicted is True
    assert abs(f.deuda_neta - (21.146e9 - 1e9)) < 1e6     # usa la verificada − caja


def test_reconciliacion_deuda_incluye_convertibles_en_deuda():
    # WOLF (bache del bug-hunt): el pack da caja neta pero el Analista inventarió converts + term_debt en deuda.
    # La reconciliación debe sumar TODOS los en_deuda_xbrl (no solo term_debt) para cazar la deuda real.
    class _C:
        tipo = "convertible"; en_deuda_xbrl = True; principal = 840e6
        id = "c"; conversion_price = 15.0; potential_shares = 50e6; liq_preference = 0.0
        strike = None; hedge_cap = None; mandatory = False; cita = "10-Q"
    class _T:
        tipo = "term_debt"; en_deuda_xbrl = True; principal = 1.3e9
        id = "t"; conversion_price = None; potential_shares = 0.0; liq_preference = 0.0
        strike = None; hedge_cap = None; mandatory = False; cita = "10-Q"
    dossier = _Dossier(_Inv("satelite"),
                       [_Esc("bear", 100e6, 8, 4, 0.4), _Esc("base", 250e6, 10, 4, 0.4), _Esc("bull", 540e6, 13, 4, 0.2)],
                       _Fals("x", "2027-01-01"), dilucion_esperada_pct=0.0)
    dossier.instrumentos = [_C(), _T()]
    # pack: deuda_neta −$1.04B (caja neta), caja $0.995B → gross ~−$45M; inventario $840M+$1.3B=$2.14B → corrige
    f = backfill_desde_dossier("WOLF", dossier, deuda_neta=-1.04e9, acciones=53e6, precio=22.65, caja=0.995e9)
    assert f.datos_conflicted is True
    assert abs(f.deuda_neta - (2.14e9 - 0.995e9)) < 1e6     # suma convert + term_debt, no solo term_debt


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
