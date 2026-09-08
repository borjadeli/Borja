"""Construcción de cartera por celdas (doc 34 §3bis): cuotas ex-ante + caps + piso + max posiciones + cash."""
from backend.nucleo.cartera_celdas import construir_cartera
from backend.nucleo.ranking_lexicografico import CandidatoLex, rankear_por_celda


def _c(t, arq="Growth", tier="A", cap=0.08, asim=1.0):
    return CandidatoLex(ticker=t, elegible=True, valuacion_ok=True, tier_capital=tier, cobertura=0.5,
                        asimetria_operable=asim, arquetipo=arq, cap=cap, route="FCFE_OPERABLE")


def test_asigna_min_cap_y_deja_cash_sellado():
    cart = construir_cartera(rankear_por_celda([_c("A", cap=0.08), _c("B", cap=0.05)]), presupuesto=1.0)
    sizes = {p.ticker: p.size for p in cart.posiciones}
    assert sizes["A"] == 0.08 and sizes["B"] == 0.05
    assert cart.invertido == 0.13 and cart.cash == 0.87
    assert cart.politica_version and cart.politica_hash          # output auditable (sellado)


def test_respeta_cuota_ex_ante_por_arquetipo():
    # 6 pre-revenue a cap 0.08; cuota Pre-revenue = 0.35 → el agregado del arquetipo no la supera
    cands = [_c(f"P{i}", arq="Pre-revenue", cap=0.08) for i in range(6)]
    cart = construir_cartera(rankear_por_celda(cands), presupuesto=1.0)
    total_pre = sum(p.size for p in cart.posiciones if p.arquetipo == "Pre-revenue")
    assert total_pre <= 0.35 + 1e-9


def test_max_posiciones():
    cart = construir_cartera(rankear_por_celda([_c(f"T{i}", cap=0.02) for i in range(20)]),
                             max_posiciones=12)
    assert len(cart.posiciones) <= 12


def test_caps_no_cuotas_no_fuerza_subinvertido():
    # un solo nombre → cartera subinvertida, el resto queda en CASH (no se fuerza)
    cart = construir_cartera(rankear_por_celda([_c("X", cap=0.08)]), presupuesto=1.0)
    assert cart.invertido == 0.08 and cart.cash == 0.92


def test_option_priced_2pct_entra_como_posicion_chica():
    # doc 34 §3ter: una OPTION_PRICED al 2% ES posición chica válida (piso = MIN_VIABLE 1.5%, no el 5% viejo)
    cart = construir_cartera(rankear_por_celda([_c("OPT", cap=0.02)]), presupuesto=1.0)
    assert [p.ticker for p in cart.posiciones] == ["OPT"] and cart.posiciones[0].size == 0.02


def test_bajo_min_viable_no_entra():
    cart = construir_cartera(rankear_por_celda([_c("TINY", cap=0.01)]), presupuesto=1.0)   # < MIN_VIABLE 0.015
    assert cart.posiciones == [] and cart.cash == 1.0


def test_gate_fail_no_entra():
    fail = CandidatoLex(ticker="F", elegible=False, valuacion_ok=True, tier_capital="A", cobertura=0.5,
                        asimetria_operable=1.0, arquetipo="Growth", cap=0.08)
    cart = construir_cartera(rankear_por_celda([fail]))
    assert cart.posiciones == [] and cart.cash == 1.0


# --- capa de juicio (doc 39 §2.6, Bloque 3): VETO + ADMIT_PROBE desacoplados de la banda ---
def test_juicio_veto_saca_del_libro():
    cart = construir_cartera(rankear_por_celda([_c("A", cap=0.08), _c("B", cap=0.05)]),
                             presupuesto=1.0, juicio={"A": "VETO"})
    tickers = [p.ticker for p in cart.posiciones]
    assert "A" not in tickers and "B" in tickers
    assert any("VETO" in s["motivo"] for s in cart.saltados)


def test_juicio_thesis_broken_saca():
    cart = construir_cartera(rankear_por_celda([_c("A", cap=0.08)]), juicio={"A": "THESIS_BROKEN"})
    assert cart.posiciones == []


def test_juicio_admit_probe_rescata_falso_negativo():
    # un nombre con cap < piso (el determinista lo saltearía) → ADMIT_PROBE lo rescata al piso
    cart = construir_cartera(rankear_por_celda([_c("TINY", cap=0.005)]), presupuesto=1.0,
                             juicio={"TINY": "ADMIT_PROBE"})
    assert [p.ticker for p in cart.posiciones] == ["TINY"]
    from backend.nucleo import politica
    assert cart.posiciones[0].size == politica.MIN_VIABLE


def test_juicio_pass_no_cambia():
    cart_sin = construir_cartera(rankear_por_celda([_c("A", cap=0.08)]))
    cart_con = construir_cartera(rankear_por_celda([_c("A", cap=0.08)]), juicio={"A": "PASS"})
    assert cart_sin.posiciones[0].size == cart_con.posiciones[0].size   # PASS = determinista, sin cambio


def test_juicio_no_supera_cap_supervivencia():
    # ADMIT_PROBE NO puede inflar por encima del cap; un nombre con cap normal se sizea normal, no al piso
    cart = construir_cartera(rankear_por_celda([_c("A", cap=0.08)]), juicio={"A": "ADMIT_PROBE"})
    assert cart.posiciones[0].size == 0.08   # cap>piso → size normal, ADMIT_PROBE no lo baja
