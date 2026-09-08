"""Sizing continuo del bucket growth/BURDEN (doc 47) — techo con distribución, no masa puntual."""
from backend.nucleo import sizing_burden as SB
from backend.nucleo import politica


# --- t_fade: normaliza el burden por crecimiento (la variable de sizing correcta) ---
def test_t_fade_burden_bajo_pocos_anos():
    # burden 2.6× creciendo 23% → ~5 años (S). Barato en años.
    t = SB.t_fade(2.6, 0.23)
    assert t is not None and 4.0 <= t <= 6.0


def test_t_fade_alto_crecimiento_baja_T_pese_a_burden_alto():
    # RKLB burden 41× pero g 87% → MENOS años que NET burden 17× g 26% (la bombshell de la #3).
    t_rklb = SB.t_fade(41.0, 0.87)
    t_net = SB.t_fade(17.0, 0.26)
    assert t_rklb is not None and t_net is not None
    assert t_rklb < t_net          # el burden crudo ordena AL REVÉS


def test_t_fade_cubierto_es_cero():
    assert SB.t_fade(0.9, 0.20) == 0.0    # burden ≤ 1 → ya cubierto


# --- factores continuos, sin acantilados ---
def test_f_val_continuo():
    assert SB.f_val(3.0) == 1.0            # T_min → full
    assert SB.f_val(12.0) == 0.0          # T_max → cero
    assert 0.0 < SB.f_val(7.5) < 1.0      # en el medio, continuo
    assert SB.f_val(None) == 0.0          # sin raíz → cero


def test_q_apal_no_acantilado():
    # apal 0.94 (PL) NO se trata igual que apal −1 (cadáver): rampa, no cliff en 1.0
    assert SB.q_apal(0.94) > SB.q_apal(0.60)
    assert SB.q_apal(None) == 0.70        # no medible → neutral penalizado, no cero


def test_q_ps_acretividad_gate():
    assert SB.q_ps(0.167) == 1.00         # S +16.7% → acretivo (dilución financia algo)
    assert SB.q_ps(0.074) == 0.60         # VRNS +7.4% → modesto
    assert SB.q_ps(-0.05) == 0.25         # diluidor: pagás la fiesta


# --- comportamiento de régimen (los 3 destinos) ---
def test_gate_a_pre_profit_pura_opcion_va_al_carril():
    # RKLB: quema caja PRE-SBC Y burden ALTO (41× = pura opción) → carril (donde vive el 10×), no libro duro
    sb = SB.size_burden("RKLB", t_star=6.1, gross_margin=0.37, apal_lag=1.13,
                        g_gp_por_accion=0.65, fcf_pre_sbc=-371e6, burden=41.8)
    assert sb.a_carril is True and sb.size == 0.0


def test_comercial_que_invierte_burden_moderado_queda_en_duro():
    # KTOS-fix: quema caja pre-SBC PERO burden moderado (7.5× < 15) → NO es lotería → libro duro (no carril)
    sb = SB.size_burden("KTOS", t_star=9.0, gross_margin=0.22, apal_lag=0.98,
                        g_gp_por_accion=0.10, fcf_pre_sbc=-129e6, burden=7.5)
    assert sb.a_carril is False           # se queda en el duro (chico), no al sleeve especulativo


def test_caro_pero_genera_caja_recibe_cap_piso_no_cero():
    # NET: genera caja pero T 22.7 > 12 (mérito f_val=0) → cap = PISO 4% (NO 0): el PM puede tener tesis de
    # aceleración; el determinismo solo pone el techo bajo. NO carril (no es pura opción).
    sb = SB.size_burden("NET", t_star=22.7, gross_margin=0.73, apal_lag=1.20,
                        g_gp_por_accion=0.235, fcf_pre_sbc=348e6, burden=17.3)
    assert sb.a_carril is False
    assert abs(sb.size - politica.CAP_FLOOR_BURN) < 1e-6      # cap = piso, no 0


def test_barato_genera_caja_cap_alto():
    # S: genera caja, T 4.8 barato (mérito alto) → cap ALTO (cerca del máximo), mayor que el piso
    sb = SB.size_burden("S", t_star=4.8, gross_margin=0.73, apal_lag=0.85,
                        g_gp_por_accion=0.167, fcf_pre_sbc=57e6, burden=2.65)
    assert sb.a_carril is False
    assert politica.CAP_FLOOR_BURN < sb.size <= politica.CAP_BURN_BUCKET   # entre piso y techo
    assert sb.size > politica.CAP_FLOOR_BURN                                # el barato tiene MÁS techo que un caro


def test_cap_cluster_escala_pro_rata():
    # Σ > 2×CAP → escala todo pro-rata (riesgo de financiamiento correlacionado)
    sizes = [SB.SizeBurden("A", 0.10, {}), SB.SizeBurden("B", 0.10, {}), SB.SizeBurden("C", 0.10, {})]
    SB.aplicar_cap_cluster(sizes)                    # Σ=0.30 > 2×0.08=0.16
    total = sum(s.size for s in sizes)
    assert abs(total - politica.CLUSTER_CAP_MULT * politica.CAP_BURN_BUCKET) < 1e-3   # redondeo a 4 dec
