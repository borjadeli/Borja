"""Tests de las calculadoras de futuro deterministas (v2 doc 70 D4). Puras, sin red."""
from backend.agentes.futuro import (
    Escenario,
    base_rate_cagr,
    dilucion_por_gap,
    funded_hasta_hito,
    meses_runway,
    retorno_por_escenario,
)


def test_runway_base_y_estres():
    r = meses_runway(1_200e6, -120e6)          # caja 1.2B / quema 10M/mes = 120 meses
    assert r.estado == "COMPUTED" and abs(r.valor - 120) < 0.5
    r2 = meses_runway(1_200e6, -120e6, estres=1.5)   # quema 15M/mes → 80 meses
    assert abs(r2.valor - 80) < 0.5


def test_runway_unknown_sin_insumos_o_sin_quema():
    assert meses_runway(None, -1).estado == "UNKNOWN"
    assert meses_runway(1e9, 50e6).estado == "UNKNOWN"   # flujo positivo: no quema


def test_funded_hasta_hito_cubre_y_gap():
    cubre = funded_hasta_hito(1_000e6, -100e6, meses_al_hito=12)   # runway ~92m (estrés 1.3) >> 12+6
    assert cubre.estado == "COMPUTED" and cubre.valor > 0 and "cubre" in cubre.detalle
    gap = funded_hasta_hito(100e6, -100e6, meses_al_hito=18)       # runway ~9m < 18+6 → gap
    assert gap.valor < 0 and "GAP" in gap.detalle


def test_funded_unknown_sin_hito():
    assert funded_hasta_hito(1e9, -1e8, meses_al_hito=None).estado == "UNKNOWN"


def test_dilucion_por_gap():
    # gap 200M, precio 50, shares 100M → 4M acciones nuevas = 4%
    r = dilucion_por_gap(200e6, 50.0, 100e6)
    assert r.estado == "COMPUTED" and abs(r.valor - 4.0) < 0.1
    # con descuento 20% → emite más barato → más dilución
    r2 = dilucion_por_gap(200e6, 50.0, 100e6, descuento=0.2)
    assert r2.valor > r.valor
    assert dilucion_por_gap(0, 50, 100e6).valor == 0.0           # sin gap
    assert dilucion_por_gap(200e6, None, 100e6).estado == "UNKNOWN"


def test_base_rate_cagr_anti_especulacion():
    # el caso del doc: 60% CAGR por 7 años → fracción muy baja
    r = base_rate_cagr(0.60, 7)
    assert r.estado == "COMPUTED" and r.valor < 1.0             # <1%
    # un crecimiento modesto es mucho más común
    r2 = base_rate_cagr(0.20, 3)
    assert r2.valor > r.valor and r2.valor > 10
    # CAGR por encima de la tabla → extrapola al más alto
    r3 = base_rate_cagr(0.90, 7)
    assert r3.estado == "COMPUTED" and "extrapolado" in r3.detalle


def test_base_rate_unknown():
    assert base_rate_cagr(None, 5).estado == "UNKNOWN"


# --------------------------------------------------------------------------- D1: retorno por escenario (doc 73)

def test_retorno_rgti_caso_limite_se_paga_de_mas():
    # el caso que las 3 IAs marcaron: $400M revenue @ 8x en 8 años = $3.2B = el MISMO EV que hoy → el valor
    # descontado hoy es muy inferior al precio (IA3: "$3.2B en 8a al 15% valen ~$1.05B hoy").
    r = retorno_por_escenario(3.2e9, [Escenario("base", 400e6, 8.0, 8, 1.0)], tasa=0.15)
    assert r.estado == "COMPUTED"
    assert abs(r.filas[0]["cagr_accionista"]) < 1e-6          # EV terminal = EV hoy → CAGR 0
    assert abs(r.filas[0]["vp"] - 3.2e9 / 1.15 ** 8) < 1e6    # ~$1.05B
    assert r.ratio_vp_precio < 0.35                            # se paga de más
    assert "se paga de más" in r.detalle


def test_retorno_pondera_por_probabilidad():
    # bull y bear simétricos pero prob distinta → el VP esperado se inclina al más probable
    escs = [Escenario("bull", 300e6, 10.0, 5, 0.3), Escenario("bear", 50e6, 6.0, 5, 0.7)]
    r = retorno_por_escenario(1.0e9, escs, tasa=0.15)
    vp_bull = (300e6 * 10) / 1.15 ** 5
    vp_bear = (50e6 * 6) / 1.15 ** 5
    assert abs(r.vp_esperado - (0.3 * vp_bull + 0.7 * vp_bear)) < 1e6


def test_retorno_dilucion_reduce_cagr_y_vp():
    base = retorno_por_escenario(1.0e9, [Escenario("base", 200e6, 10.0, 5, 1.0)], tasa=0.15)
    dil = retorno_por_escenario(1.0e9, [Escenario("base", 200e6, 10.0, 5, 1.0)], tasa=0.15, dilucion_pct=0.25)
    assert dil.filas[0]["cagr_accionista"] < base.filas[0]["cagr_accionista"]   # +25% acciones → menos por acción
    assert dil.vp_esperado < base.vp_esperado


def test_retorno_normaliza_probs_y_avisa():
    escs = [Escenario("a", 200e6, 10.0, 5, 2.0), Escenario("b", 100e6, 10.0, 5, 2.0)]   # suman 4, no 1
    r = retorno_por_escenario(1.0e9, escs)
    assert abs(sum(f["prob"] for f in r.filas) - 1.0) < 1e-6    # renormalizadas a 1
    assert "renormalizadas" in r.detalle


def test_retorno_unknown_sin_insumos():
    assert retorno_por_escenario(None, [Escenario("x", 1e6, 1.0, 1, 1.0)]).estado == "UNKNOWN"
    assert retorno_por_escenario(1e9, []).estado == "UNKNOWN"
    assert retorno_por_escenario(1e9, [Escenario("x", 1e6, 1.0, 0, 1.0)]).estado == "UNKNOWN"  # años=0


# --------------------------------------------------------------------------- D1 inverso (doc 74 §0)

def test_reverse_burden_rgti():
    # IA (las 3): para justificar $3.2B EV hoy con 15%/8a hace falta ~$9.8B terminal = $1.2B rev @ 8x o $400M @ 24x
    from backend.agentes.futuro import metrica_requerida_por_precio
    rb = metrica_requerida_por_precio(3.2e9, 8.0, 8, tasa=0.15, metrica_escenario=400e6)
    assert rb.estado == "COMPUTED"
    assert abs(rb.equity_terminal_requerida - 3.2e9 * 1.15 ** 8) < 1e6     # ~$9.79B
    assert abs(rb.metrica_requerida - 1.22e9) < 2e7                        # ~$1.22B revenue
    assert abs(rb.multiplo_requerido - 24.5) < 0.6                         # o $400M a ~24.5x


def test_reverse_burden_dilucion_y_caja_neta():
    from backend.agentes.futuro import metrica_requerida_por_precio
    base = metrica_requerida_por_precio(1.0e9, 10.0, 5, tasa=0.15)
    dil = metrica_requerida_por_precio(1.0e9, 10.0, 5, tasa=0.15, dilucion_pct=0.3)
    assert dil.metrica_requerida > base.metrica_requerida                  # diluir exige MÁS métrica terminal
    caja = metrica_requerida_por_precio(1.0e9, 10.0, 5, tasa=0.15, caja_neta_terminal=500e6)
    assert caja.metrica_requerida < base.metrica_requerida                 # caja neta terminal baja la exigencia


def test_reverse_burden_unknown():
    from backend.agentes.futuro import metrica_requerida_por_precio
    assert metrica_requerida_por_precio(None, 8.0, 8).estado == "UNKNOWN"
    assert metrica_requerida_por_precio(1e9, 0, 8).estado == "UNKNOWN"
    assert metrica_requerida_por_precio(1e9, 8.0, 0).estado == "UNKNOWN"


def test_probabilidad_implicita_bull():
    from backend.agentes.futuro import probabilidad_implicita_bull
    bull = Escenario("bull", 300e6, 10.0, 5, 0.0)      # MOIC 3.0
    bear = Escenario("bear", 50e6, 6.0, 5, 1.0)        # MOIC 0.3
    r = probabilidad_implicita_bull(1.0e9, bull, [bear], tasa=0.15, anios=5)
    # target = 1.15^5 ≈ 2.011; p = (2.011-0.3)/(3.0-0.3) ≈ 0.634
    assert r.estado == "COMPUTED" and abs(r.p_bull - 0.634) < 0.01
    assert abs(r.moic_bull - 3.0) < 1e-6 and abs(r.moic_resto - 0.3) < 1e-6


def test_probabilidad_implicita_con_base_y_bear():
    from backend.agentes.futuro import probabilidad_implicita_bull
    bull = Escenario("bull", 300e6, 10.0, 5, 0.0)      # MOIC 3.0
    base = Escenario("base", 150e6, 8.0, 5, 0.5)       # MOIC 1.2
    bear = Escenario("bear", 50e6, 6.0, 5, 0.5)        # MOIC 0.3
    r = probabilidad_implicita_bull(1.0e9, bull, [base, bear], tasa=0.15, anios=5)
    # m_resto = 0.5*1.2 + 0.5*0.3 = 0.75; p = (2.011-0.75)/(3.0-0.75) ≈ 0.56
    assert abs(r.p_bull - 0.56) < 0.01


def test_probabilidad_implicita_caro_y_barato():
    from backend.agentes.futuro import probabilidad_implicita_bull
    # caro: ni con 100% bull alcanza (bull MOIC < target)
    caro = probabilidad_implicita_bull(1.0e9, Escenario("bull", 100e6, 10.0, 5, 0.0),
                                       [Escenario("bear", 10e6, 5.0, 5, 1.0)], tasa=0.15, anios=5)
    assert caro.p_bull > 1.0 and "caro" in caro.detalle
    # barato: hasta el downside bate la hurdle (resto MOIC > target)
    barato = probabilidad_implicita_bull(1.0e9, Escenario("bull", 500e6, 10.0, 5, 0.0),
                                         [Escenario("bear", 400e6, 8.0, 5, 1.0)], tasa=0.15, anios=5)
    assert barato.p_bull < 0.0 and "barato" in barato.detalle


def test_probabilidad_implicita_horizontes_distintos_unknown():
    from backend.agentes.futuro import probabilidad_implicita_bull
    bull = Escenario("bull", 300e6, 10.0, 5, 0.0)
    bear = Escenario("bear", 50e6, 6.0, 8, 1.0)        # horizonte distinto → MOIC no comparable
    assert probabilidad_implicita_bull(1.0e9, bull, [bear], anios=5).estado == "UNKNOWN"


def test_dilucion_en_porcentaje_no_explota():
    # smoke 2026-11-03: el LLM emite dilución como % (35.0 = 35%); el puente la usa como fracción.
    from backend.agentes.futuro import _frac_dil, metrica_requerida_por_precio, probabilidad_implicita_bull
    assert _frac_dil(35.0) == 0.35 and _frac_dil(0.35) == 0.35 and _frac_dil(None) == 0.0
    # con dil=35 (mal) vs 0.35 (bien) el resultado es idéntico (se normaliza)
    a = metrica_requerida_por_precio(1e9, 8.0, 5, dilucion_pct=35.0).metrica_requerida
    b = metrica_requerida_por_precio(1e9, 8.0, 5, dilucion_pct=0.35).metrica_requerida
    assert a == b
    bull = Escenario("bull", 300e6, 10.0, 5, 0.0)
    bear = Escenario("bear", 50e6, 6.0, 5, 1.0)
    p = probabilidad_implicita_bull(1e9, bull, [bear], anios=5, dilucion_pct=35.0).p_bull
    assert p is not None and -1.0 <= p <= 2.0     # sano, no 23 millones
