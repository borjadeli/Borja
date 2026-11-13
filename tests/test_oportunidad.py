"""Motor de oportunidad (r9, doc 80 §D · P1): score ficha-less + compuerta de supervivencia + carriles."""
from backend.agentes.oportunidad import (CandidatoOportunidad, asignar_carriles, candidato_desde_metricas,
                                         compuerta_supervivencia, cuello_score, g_exigido, percentiles_cluster,
                                         rankear_oportunidades, score_ficha_less)


def test_g_exigido_y_brecha():
    # EV 4B, ventas 1B, mult_ref 4x, 4a, hurdle 20%: rev_term_req = 4B×1.2^4/4 = 2.0736B → g = 2.0736^.25−1 ≈ 20%
    g = g_exigido(ev=4e9, revenue=1e9, mult_ref=4.0, anios=4, hurdle=0.20)
    assert abs(g - 0.2011) < 0.01
    # una growth real (40% YoY) que el precio solo exige ~20% → brecha POSITIVA (barata vs lo que entrega)
    cand = candidato_desde_metricas("A", cluster="x",
                                    metricas={"enterprise_value": 4e9, "revenue": 1e9, "revenue_growth_yoy": 40.0})
    assert cand.brecha_raw is not None and cand.brecha_raw > 0.15
    # sin ventas → brecha None (compite solo por exploración)
    assert candidato_desde_metricas("B", cluster="x", metricas={"enterprise_value": 2e9}).brecha_raw is None


def test_cuello_score():
    assert cuello_score("confirmado", prioridad_macro=1.0, rol="lider") == 1.0
    assert cuello_score("resuelto", rol="lider") == 0.0          # cuello que se disolvió → 0
    assert 0 < cuello_score("vigilancia", prioridad_macro=0.75, rol="retador") < 1


def test_compuerta_supervivencia():
    assert compuerta_supervivencia(going_concern=True) == 0.0
    assert compuerta_supervivencia(runway_meses=4) == 0.0       # <6m → 0
    assert compuerta_supervivencia(runway_meses=9) == 0.7       # <12m sin penal → 0.7
    assert compuerta_supervivencia(runway_meses=9, dilucion_overhang=True) == 0.5
    assert compuerta_supervivencia(runway_meses=40) == 1.0


def test_percentiles_cluster():
    p = percentiles_cluster({"A": 2.0, "B": 5.0, "C": 10.0})
    assert p["A"] == 0.0 and p["C"] == 1.0 and 0 < p["B"] < 1
    assert percentiles_cluster({"X": 3.0})["X"] == 0.5          # singleton → neutral
    assert percentiles_cluster({"X": None})["X"] is None


def test_score_cero_en_una_pata_mata():
    # media geométrica: C=0 (cuello resuelto) → score 0 pese a V y M altos
    assert score_ficha_less(v=1.0, m=1.0, c=0.0, a=1.0) == 0.0
    # A=0 (no sobrevive) → score 0
    assert score_ficha_less(v=1.0, m=1.0, c=1.0, a=0.0) == 0.0
    # sin ventas (V None) → score None (compite solo por exploración)
    assert score_ficha_less(v=None, m=1.0, c=1.0, a=1.0) is None
    # todo máximo → 1.0
    assert score_ficha_less(v=1.0, m=1.0, c=1.0, a=1.0) == 1.0


def test_rankear_percentil_dentro_del_cluster():
    cand = [
        CandidatoOportunidad("A", "nuclear", brecha_raw=0.3, momentum_raw=0.2, cuello_estado="confirmado",
                             cuello_rol="lider", prioridad_macro=1.0, runway_meses=40),
        CandidatoOportunidad("B", "nuclear", brecha_raw=-0.1, momentum_raw=0.0, cuello_estado="confirmado",
                             cuello_rol="lider", prioridad_macro=1.0, runway_meses=40),
        CandidatoOportunidad("C", "semis", brecha_raw=None, momentum_raw=0.1),   # sin ventas → score None
    ]
    filas = rankear_oportunidades(cand)
    d = {f.ticker: f for f in filas}
    assert d["A"].v == 1.0 and d["B"].v == 0.0        # A mejor brecha que B dentro de 'nuclear'
    assert d["A"].score > (d["B"].score or 0)
    assert d["C"].score is None                       # sin brecha
    assert filas[0].ticker == "A" and filas[-1].ticker == "C"   # None al final


def _fila(tk, score):
    from backend.agentes.oportunidad import FilaScore
    return FilaScore(ticker=tk, cluster="c", score=score, v=0.5, m=0.5, c=0.5, a=1.0)


def test_asignar_carriles():
    sel = asignar_carriles(
        posiciones={"MP"},
        fichas_zona={"OKLO": "COMPRA", "RKLB": "MANTENER", "VIEJA": "COMPRA"},
        fichas_estado={"OKLO": "VIGENTE", "RKLB": "VIGENTE", "VIEJA": "VENCIDA"},
        scores=[_fila("NUEVA1", 0.9), _fila("NUEVA2", 0.8), _fila("NUEVA3", 0.7)],
        cupo_oportunidad=2)
    assert sel.tenencias == ["MP"]                    # posición siempre
    assert sel.banca == ["OKLO"]                      # ficha vigente en COMPRA
    # oportunidad: la VENCIDA en zona primero + top score, capeado a 2
    assert sel.oportunidad == ["VIEJA", "NUEVA1"]
    assert ("NUEVA3", "sobre el cupo de oportunidad") in sel.espera


def test_blackout_excluye():
    sel = asignar_carriles(
        posiciones=set(), fichas_zona={"OKLO": "COMPRA"}, fichas_estado={"OKLO": "VIGENTE"},
        scores=[_fila("NUEVA1", 0.9)], cupo_oportunidad=4, blackout={"OKLO", "NUEVA1"})
    assert sel.banca == [] and sel.oportunidad == []   # ambos en blackout → no entran
