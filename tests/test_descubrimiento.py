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


def test_promover_inserta_al_universo_y_marca_aprobada(tmp_path):
    cola = ColaPropuestas(path=tmp_path / "cola.jsonl")
    cola.registrar(_p("NUVL"), ips_cfg=_IPS, universo_actual=set())
    altas = []
    cola.promover("NUVL", alta_fn=lambda tk, prop: altas.append((tk, prop["cuello"])))
    assert altas == [("NUVL", "qc")]                 # llamó al alta (insert a nx_empresa)
    assert cola.en_observacion() == []               # salió de observación (aprobada)


def test_promover_falla_si_no_esta_en_observacion(tmp_path):
    cola = ColaPropuestas(path=tmp_path / "cola.jsonl")
    cola.registrar(_p("BIGCO", mc=200e9), ips_cfg=_IPS, universo_actual=set())   # rechazada
    import pytest
    with pytest.raises(ValueError):
        cola.promover("BIGCO", alta_fn=lambda tk, prop: None)
    with pytest.raises(ValueError):
        cola.promover("INEXISTENTE", alta_fn=lambda tk, prop: None)


# --------------------------------------------------------------------------- el AGENTE LLM (ScriptedLLM)

from backend.agentes.base import Agente, FakeUsage, ScriptedLLM, resp_tool   # noqa: E402
from backend.agentes.descubrimiento import AgenteDiscovery, encolar_propuestas  # noqa: E402


def _agente_que_emite(propuestas, *, urls=None):
    cli = ScriptedLLM([resp_tool("emitir_propuestas", {"propuestas": propuestas},
                                 FakeUsage(input_tokens=500, output_tokens=200), urls=urls)])
    return Agente("discovery", "discovery_v1", "claude-sonnet-5-5", cliente=cli)


def _raw(ticker="NUVL", mc=5e9, cuello="fotónica co-packaged", fuentes=None):
    return {"ticker": ticker, "cuello": cuello, "tesis_corta": "captura el valor del cuello",
            "por_que_ahora": "8-K 2026-10: contrato con hyperscaler", "market_cap": mc,
            "fuentes": fuentes if fuentes is not None else ["https://sec.gov/x"]}


def test_agente_explora_y_devuelve_propuestas():
    ag = AgenteDiscovery(_agente_que_emite([_raw("NUVL"), _raw("AEHR", mc=2e9)]))
    props, meta = ag.explorar(universo_actual={"MP", "OKLO"}, foco="fotónica")
    assert [p.ticker for p in props] == ["NUVL", "AEHR"]
    assert props[0].cuello and props[0].por_que_ahora and props[0].fuentes
    assert meta.agent == "discovery"


def test_agente_respeta_tope_y_deduplica():
    raws = [_raw(t) for t in ("A", "B", "C", "D")] + [_raw("A")]      # D y un duplicado de A
    ag = AgenteDiscovery(_agente_que_emite(raws))
    props, _ = ag.explorar(universo_actual=set(), max_propuestas=2)
    assert [p.ticker for p in props] == ["A", "B"]                     # cap=2, sin duplicar


def test_agente_fallback_a_urls_de_busqueda_si_no_cita():
    # el modelo no puso fuentes en la propuesta → se usan las URLs que trajo web_search (procedencia)
    ag = AgenteDiscovery(_agente_que_emite([_raw("NUVL", fuentes=[])],
                                           urls=["https://sec.gov/edgar/filing", "https://x"]))
    props, _ = ag.explorar(universo_actual=set())
    assert props[0].fuentes == ["https://sec.gov/edgar/filing", "https://x"]


def test_agente_descarta_universo_y_observacion():
    # aunque el modelo re-proponga lo ya conocido, explorar lo filtra (no quema a los validadores aguas abajo)
    ag = AgenteDiscovery(_agente_que_emite([_raw("MP"), _raw("NUVL"), _raw("OBS1")]))
    props, _ = ag.explorar(universo_actual={"MP"}, en_observacion={"OBS1"})
    assert [p.ticker for p in props] == ["NUVL"]


def test_encolar_propuestas_valida_y_filtra(tmp_path):
    cola = ColaPropuestas(path=tmp_path / "cola.jsonl")
    ag = AgenteDiscovery(_agente_que_emite([_raw("NUVL", mc=5e9), _raw("BIGCO", mc=200e9), _raw("MP")]))
    props, _ = ag.explorar(universo_actual={"MP"})
    assert "MP" not in [p.ticker for p in props]              # explorar ya filtró el duplicado del universo
    res = encolar_propuestas(cola, props, ips_cfg=_IPS, universo_actual={"MP"})
    por_estado = {r["ticker"]: r["estado"] for r in res}
    assert por_estado == {"NUVL": "observacion", "BIGCO": "rechazada"}   # BIGCO gigante → rechazada
    assert {v["propuesta"]["ticker"] for v in cola.en_observacion()} == {"NUVL"}


def test_market_cap_mal_escalado_no_rechaza_en_duro():
    # un cap sospechosamente chico (5 = probablemente $5B mal escalado) NO se rechaza en duro: a verificar
    ok, m = validar_propuesta(_p(mc=5), ips_cfg=_IPS, universo_actual=set())
    assert ok and any("mal escalado" in x for x in m)
    ok2, m2 = validar_propuesta(_p(mc=500), ips_cfg=_IPS, universo_actual=set())   # 500 = ¿$500M?
    assert ok2 and any("mal escalado" in x for x in m2)
