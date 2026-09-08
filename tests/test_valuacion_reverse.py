"""Reverse-DCF (doc 36): solver de T* + estado. Colapso a madura, orden de la superficie de margen, worse-of."""
from backend.nucleo import valuacion_reverse as VR


def test_colapsa_a_madura_precio_bajo_el_piso():
    # P_ops ≤ owner-FCF/r (piso g=0) → T*=0 (madura, la caja sin crecimiento ya lo paga)
    r = VR.t_star(P_ops=60.0, R0=100.0, g_D=0.30, m0=0.10, mj=0.20, r=0.15)   # piso = 100*0.10/0.15 = 66.7
    assert r["t_star"] == 0.0


def test_precio_arriba_del_piso_requiere_tiempo():
    r = VR.t_star(P_ops=150.0, R0=100.0, g_D=0.30, m0=0.10, mj=0.25, r=0.15)
    assert r["t_star"] is not None and r["t_star"] > 0


def test_superficie_margen_menor_margen_mas_anios():
    # a MENOR margen terminal, el precio exige MÁS años (o directamente no hay raíz)
    alto = VR.t_star(P_ops=300.0, R0=100.0, g_D=0.30, m0=0.10, mj=0.30, r=0.15)["t_star"]
    bajo = VR.t_star(P_ops=300.0, R0=100.0, g_D=0.30, m0=0.10, mj=0.10, r=0.15)["t_star"]
    assert alto is not None
    assert bajo is None or bajo >= alto


def test_precio_absurdo_no_underwritable():
    r = VR.t_star(P_ops=1e12, R0=100.0, g_D=0.30, m0=0.10, mj=0.20, r=0.15)
    assert r["t_star"] is None


def test_valor_monotono_creciente_en_T():
    v = [VR.valor_a_T(T, 100.0, 0.30, 0.10, 0.20, 0.15)[0] for T in range(1, 12)]
    assert all(v[i] <= v[i + 1] + 1e-6 for i in range(len(v) - 1))


def test_estado_covered_precio_bajo_el_piso():
    res = VR.estado_valuacion_reverse("X", P_ops=60.0, R0=100.0, g_D=0.30, m0=0.10, r=0.15,
                                      modelo="software", owner_fcf_positivo=True)
    assert res.estado == "COVERED" and res.t_star["P25"] == 0.0


def test_estado_non_underwritable_precio_absurdo():
    res = VR.estado_valuacion_reverse("X", P_ops=1e12, R0=100.0, g_D=0.30, m0=0.10, r=0.15, modelo="software")
    assert res.estado == "NON_UNDERWRITABLE"


def test_data_state_empeora_el_estado():
    # growth COVERED pero cobertura pobre (data_state=OPTION_PRICED) → el peor manda
    res = VR.estado_valuacion_reverse("X", P_ops=60.0, R0=100.0, g_D=0.30, m0=0.10, r=0.15,
                                      modelo="software", data_state="OPTION_PRICED", owner_fcf_positivo=True)
    assert res.estado == "OPTION_PRICED"


def test_owner_fcf_negativo_no_puede_ser_covered():
    res = VR.estado_valuacion_reverse("X", P_ops=60.0, R0=100.0, g_D=0.30, m0=0.10, r=0.15,
                                      modelo="software", owner_fcf_positivo=False)
    assert res.estado != "COVERED"


def test_peor_de_dos_estados():
    assert VR._peor("COVERED", "OPTION_PRICED") == "OPTION_PRICED"
    assert VR._peor("STRETCH", "COVERED") == "STRETCH"
