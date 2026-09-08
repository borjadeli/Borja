"""Tests del selector v3 (tiers → cartera). Sin LLM."""
from backend.nucleo.cartera import construir_cartera
from backend.nucleo.evaluacion import Evaluacion


def _ev(ticker, tier, delta="estable"):
    return Evaluacion(ticker=ticker, tier=tier, pilares=[], delta_evidencia=delta,
                      pilar_limitante=None, motivo="")


def test_solo_A_y_B_entran_C_a_watch():
    evs = [_ev("A1", "A"), _ev("B1", "B"), _ev("C1", "C")]
    caps = {"A1": 0.20, "B1": 0.15, "C1": 0.10}
    cart = construir_cartera(evs, hard_cap_por_ticker=caps)
    tickers = {p.ticker for p in cart.posiciones}
    assert tickers == {"A1", "B1"}
    assert any(t == "C1" and "watch" in m for t, m in cart.afuera)


def test_conviccion_por_tier():
    evs = [_ev("A1", "A"), _ev("B1", "B")]
    caps = {"A1": 0.20, "B1": 0.20}
    cart = construir_cartera(evs, hard_cap_por_ticker=caps)
    pa = next(p for p in cart.posiciones if p.ticker == "A1")
    pb = next(p for p in cart.posiciones if p.ticker == "B1")
    assert pa.peso == 0.20          # A usa el cap pleno
    assert pb.peso == 0.12          # B = 0.6 × 0.20


def test_prioridad_por_tier_y_delta():
    # A/sube antes que A/estable antes que B/sube
    evs = [_ev("Ae", "A", "estable"), _ev("Bs", "B", "sube"), _ev("As", "A", "sube")]
    caps = {t: 0.20 for t in ("Ae", "Bs", "As")}
    cart = construir_cartera(evs, hard_cap_por_ticker=caps)
    assert [p.ticker for p in cart.posiciones] == ["As", "Ae", "Bs"]


def test_cap_por_sector_recorta():
    evs = [_ev("X", "A"), _ev("Y", "A")]
    caps = {"X": 0.30, "Y": 0.30}
    sectores = {"X": "optica", "Y": "optica"}
    cart = construir_cartera(evs, hard_cap_por_ticker=caps, sector_por_ticker=sectores, cap_sector=0.40)
    total_optica = sum(p.peso for p in cart.posiciones if p.sector == "optica")
    assert total_optica <= 0.40 + 1e-9      # el sector no supera su cap


def test_max_posiciones():
    evs = [_ev(f"T{i}", "A") for i in range(15)]
    caps = {f"T{i}": 0.05 for i in range(15)}
    cart = construir_cartera(evs, hard_cap_por_ticker=caps, max_posiciones=12)
    assert len(cart.posiciones) == 12
    assert any("máx posiciones" in m for _, m in cart.afuera)


def test_tope_de_despliegue_y_cash():
    evs = [_ev(f"T{i}", "A") for i in range(5)]
    caps = {f"T{i}": 0.30 for i in range(5)}   # 5×0.30 = 1.5 > tope 1.0
    cart = construir_cartera(evs, hard_cap_por_ticker=caps, cap_sector=1.0)
    assert cart.invertido <= 1.0 + 1e-9
    assert abs(cart.cash - (1.0 - cart.invertido)) < 1e-9
