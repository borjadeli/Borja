"""Estacionamiento en ETFs temáticos (r7a #1): el residual sin margen de seguridad va a ETFs, nunca a nombres;
se desarma primero al aparecer un nombre; y los ETFs no cuentan como posición en el IPS."""
from backend.agentes.estacionamiento import (aplicar_estacionamiento, pesos_estacionamiento, tickers_parking)
from backend.agentes.ips import ContextoTicker, IPS

_CFG = {
    "estacionamiento": {
        "activo": True, "etf_default": "SPY",
        "etfs_por_cluster": {"nuclear": "URA", "semis": "SMH", "defensa": "ITA"},
    }
}


def test_tickers_parking():
    assert tickers_parking(_CFG) == {"URA", "SMH", "ITA", "SPY"}


def test_sin_nombres_el_residual_va_a_etfs():
    # sin nombres con margen de seguridad → todo el residual a ETFs ponderados por cluster, NADA a nombres
    finales, caja = aplicar_estacionamiento({}, {"nuclear": 2.0, "semis": 1.0}, _CFG)
    assert set(finales) == {"URA", "SMH"}
    assert abs(finales["URA"] - 2 / 3) < 1e-6 and abs(finales["SMH"] - 1 / 3) < 1e-6
    assert abs(caja) < 1e-6                                   # desplegado 100% en ETFs
    assert all(not tk.isalpha() or tk in ("URA", "SMH") for tk in finales)  # no hay nombres


def test_aparece_nombre_se_desarma_el_etf():
    clusters = {"nuclear": 1.0}
    sin = aplicar_estacionamiento({}, clusters, _CFG)[0]
    con = aplicar_estacionamiento({"OKLO": 0.6}, clusters, _CFG)[0]
    assert sin["URA"] == 1.0                                  # sin nombres: todo al ETF
    assert con["OKLO"] == 0.6 and abs(con["URA"] - 0.4) < 1e-6   # el nombre entra, el ETF se achica (no la caja)


def test_caja_macro_no_se_aparca():
    # la caja macro-justificada NO se parkea: residual = 1 − nombres − caja_macro
    finales, caja = aplicar_estacionamiento({"MP": 0.3}, {"nuclear": 1.0}, _CFG, caja_macro=0.2)
    assert abs(finales["URA"] - 0.5) < 1e-6 and abs(caja - 0.2) < 1e-6


def test_estacionamiento_inactivo_no_agrega_etfs():
    finales, caja = aplicar_estacionamiento({"MP": 0.3}, {"nuclear": 1.0}, {"estacionamiento": {"activo": False}})
    assert finales == {"MP": 0.3} and abs(caja - 0.7) < 1e-6


def test_cluster_sin_etf_va_al_default():
    out = pesos_estacionamiento(1.0, {"biotech": 1.0}, etfs_por_cluster={"nuclear": "URA"}, etf_default="SPY")
    assert out == {"SPY": 1.0}


def test_ips_excluye_etfs_de_max_posiciones():
    ips = IPS(cfg={"max_posiciones": 3, "peso_max_nombre": 1.0,
                   "estacionamiento": {"activo": True, "etf_default": "SPY",
                                       "etfs_por_cluster": {"nuclear": "URA"}}})
    ctx: dict = {}
    # 3 nombres + 1 ETF de parking → NO viola max_posiciones (el ETF no cuenta)
    pesos = {"A": 0.2, "B": 0.2, "C": 0.2, "URA": 0.4}
    assert not any(v.regla == "max_posiciones" for v in ips.validar(pesos, ctx, caja=0.0))
    # 4 nombres + ETF → sí viola (4 > 3), el ETF sigue sin contar
    pesos2 = {"A": 0.2, "B": 0.2, "C": 0.2, "D": 0.1, "URA": 0.3}
    assert any(v.regla == "max_posiciones" for v in ips.validar(pesos2, ctx, caja=0.0))
