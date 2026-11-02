"""Tests de D4 — sizing por clasificación (doc 74). Puros + señal de sombra en el decision layer."""
from backend.agentes.clasificacion import (
    ClasifTicker,
    analisis_sizing,
    banda_de,
    clasificacion_efectiva,
    render_sizing,
    techo_clasificacion,
)

_BANDAS = {"especulativa": 0.015, "satelite": 0.05}


def _c(analyst, *, rev=False, puente=True, fcf_neg=None, runway=None):
    return ClasifTicker(analyst_clasif=analyst, revenue_recurrente=rev, tiene_puente=puente,
                        fcf_negativo=fcf_neg, runway_meses=runway)


def test_techo_sin_revenue_recurrente_es_especulativa():
    # OKLO: sin revenue recurrente → el analista no puede pasar de especulativa aunque pida satelite
    assert techo_clasificacion(_c("satelite", rev=False)) == "especulativa"
    assert clasificacion_efectiva(_c("satelite", rev=False)) == "especulativa"


def test_techo_sin_puente_es_especulativa():
    assert techo_clasificacion(_c("core", rev=True, puente=False)) == "especulativa"


def test_techo_fcf_neg_runway_corto_es_satelite():
    assert techo_clasificacion(_c("core", rev=True, fcf_neg=True, runway=18)) == "satelite"
    assert techo_clasificacion(_c("core", rev=True, fcf_neg=True, runway=30)) == "core"   # pista larga: core ok
    assert techo_clasificacion(_c("core", rev=True, fcf_neg=None, runway=None)) == "core"  # sin dato: no capea


def test_analista_puede_bajar_nunca_subir():
    assert clasificacion_efectiva(_c("watchlist", rev=True)) == "watchlist"       # más bajo: respeta
    assert clasificacion_efectiva(_c("core", rev=False)) == "especulativa"        # más alto: capea a techo


def test_banda_por_clasificacion():
    assert banda_de("watchlist", _BANDAS, 0.20) == 0.0
    assert banda_de("especulativa", _BANDAS, 0.20) == 0.015
    assert banda_de("satelite", _BANDAS, 0.20) == 0.05
    assert banda_de("core", _BANDAS, 0.20) == 0.20       # core = peso_max del IPS


def test_analisis_detecta_exceso_de_banda_e_inflada():
    # OKLO especulativa al 2,8% (el bug observado) → excede la banda 1,5% y la clasificación venía inflada
    pesos = {"OKLO": 0.028, "MP": 0.03}
    clasif = {"OKLO": _c("satelite", rev=False), "MP": _c("satelite", rev=True, fcf_neg=True, runway=30)}
    an = analisis_sizing(pesos, clasif, bandas=_BANDAS, cap_bucket=0.10, cap_cluster=0.20, peso_max_nombre=0.20)
    f = {x.ticker: x for x in an.filas}
    assert f["OKLO"].efectiva == "especulativa" and f["OKLO"].exceso is True and f["OKLO"].inflada is True
    assert f["MP"].efectiva == "satelite" and f["MP"].exceso is False      # 3% < banda satelite 5%


def test_analisis_caps_agregados_bucket_y_cluster():
    pesos = {"A": 0.014, "B": 0.014, "C": 0.014}       # 3 especulativas = 4,2% > bucket? no (cap 10%)
    clasif = {t: _c("especulativa", rev=False) for t in pesos}
    clusters = {"A": "quantum", "B": "quantum", "C": "quantum"}
    an = analisis_sizing(pesos, clasif, clusters, bandas=_BANDAS, cap_bucket=0.03, cap_cluster=0.03,
                         peso_max_nombre=0.20)
    assert an.viol_bucket is True and abs(an.bucket_especulativo - 0.042) < 1e-6   # 4,2% > cap 3%
    assert "quantum" in an.viol_cluster and abs(an.clusters["quantum"] - 0.042) < 1e-6


def test_render_sombra_marca_que_no_gatea():
    pesos = {"OKLO": 0.028}
    an = analisis_sizing(pesos, {"OKLO": _c("satelite", rev=False)}, bandas=_BANDAS, peso_max_nombre=0.20)
    txt = render_sizing(an, "sombra")
    assert "[SOMBRA]" in txt and "OKLO" in txt and "banda especulativa" in txt


def test_sin_clasificacion_no_inventa():
    an = analisis_sizing({"X": 0.1}, {}, bandas=_BANDAS, peso_max_nombre=0.20)   # sin clasif de X
    assert an.filas == []
