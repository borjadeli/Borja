"""Tests de la cola de propuestas de discovery (doc 76 §4). Determinista, sin API."""
from datetime import date

from backend.agentes.descubrimiento import ColaPropuestas, PropuestaEmpresa, validar_propuesta

_IPS = {"market_cap_min_usd": 150e6, "market_cap_max_usd": 60e9}


def _p(ticker="NUVL", mc=5e9, fuentes=None, cuello="qc", por_que="8-K contrato DoD"):
    return PropuestaEmpresa(ticker=ticker, cuello=cuello, tesis_corta="t", por_que_ahora=por_que,
                            fuentes=fuentes if fuentes is not None else ["https://sec.gov/x"], market_cap=mc)


def test_validador_acepta_una_buena():
    ok, motivos = validar_propuesta(_p(), ips_cfg=_IPS, universo_actual=set())
    assert ok and motivos == []


def test_validador_rechaza_fuera_de_rango_y_duplicado_y_sin_fuente():
    ok, m = validar_propuesta(_p(mc=200e9), ips_cfg=_IPS, universo_actual=set())      # gigante
    assert not ok and any("fuera del rango" in x for x in m)
    ok2, m2 = validar_propuesta(_p("MP"), ips_cfg=_IPS, universo_actual={"MP"})       # duplicado
    assert not ok2 and any("duplicado" in x for x in m2)
    ok3, m3 = validar_propuesta(_p(fuentes=[]), ips_cfg=_IPS, universo_actual=set())  # sin fuente
    assert not ok3 and any("fuente" in x for x in m3)


def test_validador_sin_market_cap_es_blando():
    # sin market cap NO es inelegible definitivo (pendiente de verificación) → pasa a observación
    ok, m = validar_propuesta(_p(mc=None), ips_cfg=_IPS, universo_actual=set())
    assert ok and any("pendiente de verificación" in x for x in m)


def test_liquidez_no_se_valida():
    # no hay ningún validador de ADV/liquidez (decisión del operador)
    ok, m = validar_propuesta(_p(), ips_cfg=_IPS, universo_actual=set())
    assert ok and not any("liquid" in x.lower() or "adv" in x.lower() for x in m)


def test_cola_registra_observacion_y_rechaza(tmp_path):
    cola = ColaPropuestas(path=tmp_path / "cola.jsonl")
    est, _ = cola.registrar(_p("NUVL"), ips_cfg=_IPS, universo_actual=set())
    assert est == "observacion"
    est2, mot = cola.registrar(_p("BIGCO", mc=200e9), ips_cfg=_IPS, universo_actual=set())
    assert est2 == "rechazada" and mot
    obs = {v["propuesta"]["ticker"] for v in cola.en_observacion()}
    assert obs == {"NUVL"}                        # solo la que validó espera al humano


def test_cola_humano_promueve_y_sale_de_observacion(tmp_path):
    cola = ColaPropuestas(path=tmp_path / "cola.jsonl")
    cola.registrar(_p("NUVL"), ips_cfg=_IPS, universo_actual=set())
    cola.resolver("NUVL", "aprobada", nota="ok operador")
    assert cola.en_observacion() == []            # ya no espera; fue promovida


def test_cola_vence_sin_aprobacion_nunca_por_silencio(tmp_path):
    cola = ColaPropuestas(path=tmp_path / "cola.jsonl")
    cola.registrar(PropuestaEmpresa(ticker="NUVL", cuello="qc", tesis_corta="t", por_que_ahora="x",
                                    fuentes=["https://sec.gov/x"], market_cap=5e9, dias_vigencia=30),
                   ips_cfg=_IPS, universo_actual=set())
    assert cola.vencer_pendientes(date.today()) == []        # recién registrada, no vence
    # 40 días después → vence (NO se acepta por silencio)
    from datetime import timedelta
    vencidos = cola.vencer_pendientes(date.today() + timedelta(days=40))
    assert vencidos == ["NUVL"] and cola.en_observacion() == []
