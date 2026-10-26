"""Tests del validador del IPS (v2 Fase 4). Determinista, sin API."""
from backend.agentes.ips import IPS, ContextoTicker, Violacion


def _ips(**over):
    cfg = {"max_posiciones": 12, "peso_max_nombre": 0.20, "max_por_sector": 0.30, "max_por_cuello": 0.35,
           "caja_min": 0.0, "caja_max": 1.0, "max_ops_semana": 2, "market_cap_min_usd": 150e6,
           "market_cap_max_usd": 60e9, "adv_min_usd": 3e6, "cap_flag_supervivencia": 0.04}
    cfg.update(over)
    return IPS(cfg)


def _ctx(sector=None, cuello=None, market_cap=5e9, adv_usd=10e6):
    return ContextoTicker(sector=sector, cuello=cuello, market_cap=market_cap, adv_usd=adv_usd)


def test_carga_real_y_hash_estable():
    ips = IPS.cargar()
    assert ips.cfg["peso_max_nombre"] == 0.20
    assert ips.hash() == ips.hash() and len(ips.hash()) == 16


def test_cartera_limpia_sin_violaciones():
    ips = _ips()
    pesos = {"OKLO": 0.1, "MP": 0.1}
    ctx = {"OKLO": _ctx(sector="energia"), "MP": _ctx(sector="commodities")}
    assert ips.validar(pesos, ctx, caja=0.8) == []


def test_peso_por_nombre_es_local_simple():
    ips = _ips()
    v = ips.validar({"OKLO": 0.25}, {"OKLO": _ctx()}, caja=0.75)
    assert len(v) == 1 and v[0].regla == "peso_max_nombre" and v[0].tipo == "local_simple"
    assert v[0].holgura < 0                         # negativo = excede


def test_cap_de_flag_supervivencia():
    ips = _ips()
    # 6% con flag no resuelto → viola el cap de 4% (si no hubiera flag, 6% < 20% pasaría)
    v = ips.validar({"OKLO": 0.06}, {"OKLO": _ctx()}, caja=0.94, flags_no_resueltos={"OKLO"})
    assert len(v) == 1 and "flag supervivencia" in v[0].detalle and v[0].tipo == "local_simple"
    assert ips.validar({"OKLO": 0.06}, {"OKLO": _ctx()}, caja=0.94) == []   # sin flag, 6% pasa


def test_market_cap_y_adv_local_simple():
    ips = _ips()
    v = ips.validar({"BIG": 0.1, "ILL": 0.1},
                    {"BIG": _ctx(market_cap=80e9), "ILL": _ctx(adv_usd=1e6)}, caja=0.8)
    reglas = {x.regla for x in v}
    assert reglas == {"market_cap_rango", "adv_min"} and all(x.tipo == "local_simple" for x in v)


def test_concentracion_sector_es_agregada():
    ips = _ips()
    pesos = {"A": 0.18, "B": 0.18}                  # mismo sector = 36% > 30%
    ctx = {"A": _ctx(sector="ai_infra"), "B": _ctx(sector="ai_infra")}
    v = ips.validar(pesos, ctx, caja=0.64)
    agg = [x for x in v if x.regla == "max_por_sector"]
    assert len(agg) == 1 and agg[0].tipo == "agregada"
    assert IPS.hay_agregada(v) is True              # → NO_ACTION, el código no recorta


def test_caja_y_ops_agregadas():
    ips = _ips()
    v = ips.validar({"A": 0.1}, {"A": _ctx(sector="x")}, caja=-0.05, ops_semana=5)
    reglas = {x.regla for x in v}
    assert "caja" in reglas and "max_ops_semana" in reglas
    assert all(x.tipo == "agregada" for x in v if x.regla in ("caja", "max_ops_semana"))


def test_helpers_admisible():
    assert IPS.admisible([]) is True
    assert IPS.admisible([Violacion("x", "y", -0.1, "local_simple")]) is False
