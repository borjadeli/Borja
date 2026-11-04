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


def test_validador_exige_fuente_primaria_r6_3():
    # r6 #3: X/Reddit/blogs no cuentan como fuente — se necesita regulador/filing/IR
    ok, m = validar_propuesta(_p(fuentes=["https://reddit.com/r/stocks/x"]), ips_cfg=_IPS, universo_actual=set())
    assert not ok and any("fuente PRIMARIA" in x for x in m)
    ok2, _ = validar_propuesta(_p(fuentes=["https://www.sec.gov/Archives/edgar/data/1/x.htm"]),
                               ips_cfg=_IPS, universo_actual=set())
    assert ok2                                       # un filing SEC sí cuenta


def test_cap_requerido_rechaza_sin_market_cap_r6_3():
    # auto-entrada (sin humano): un market cap sin resolver NO entra; manual (cap_requerido=False) sí (blando)
    ok_auto, m = validar_propuesta(_p(mc=None), ips_cfg=_IPS, universo_actual=set(), cap_requerido=True)
    assert not ok_auto and any("no entra" in x for x in m)
    ok_manual, _ = validar_propuesta(_p(mc=None), ips_cfg=_IPS, universo_actual=set(), cap_requerido=False)
    assert ok_manual                                 # manual: queda a verificar (blando)


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


def test_market_cap_mal_escalado_no_rechaza_en_duro():
    # un cap sospechosamente chico (5 = probablemente $5B mal escalado) NO se rechaza en duro: a verificar
    ok, m = validar_propuesta(_p(mc=5), ips_cfg=_IPS, universo_actual=set())
    assert ok and any("mal escalado" in x for x in m)
    ok2, m2 = validar_propuesta(_p(mc=500), ips_cfg=_IPS, universo_actual=set())   # 500 = ¿$500M?
    assert ok2 and any("mal escalado" in x for x in m2)


def test_validar_propuesta_exige_encaje_en_el_mapa():
    # con nodos_conocidos, el cuello DEBE ser un nodo real (el mapa valida, no el humano)
    ok, m = validar_propuesta(_p(cuello="HBM"), ips_cfg=_IPS, universo_actual=set(), nodos_conocidos={"HBM"})
    assert ok and not m
    ok2, m2 = validar_propuesta(_p(cuello="tema de moda sin cuello"), ips_cfg=_IPS, universo_actual=set(),
                                nodos_conocidos={"HBM"})
    assert not ok2 and any("sin encaje en el mapa" in x for x in m2)


# --------------------------------------------------------------------------- los AGENTES (ScriptedLLM)

from backend.agentes.base import Agente, FakeUsage, ScriptedLLM, resp_tool          # noqa: E402
from backend.agentes.descubrimiento import (AgenteCurador, AgenteDiscovery, ColaNodos,  # noqa: E402
                                            PropuestaEmpresa, PropuestaNodo, encolar_nodos,
                                            encolar_propuestas, validar_nodo)

# nodos del mapa que le damos al agente: C01 → "Fotónica / CPO", C02 → "HBM"
_NODOS = [{"nombre": "Fotónica / CPO", "info": "[fotonica] Fotónica / CPO"},
          {"nombre": "HBM", "info": "[datacenter] HBM"}]


def _emite(propuestas=None, cuellos_nuevos=None, *, urls=None):
    payload = {"propuestas": propuestas or [], "cuellos_nuevos": cuellos_nuevos or []}
    cli = ScriptedLLM([resp_tool("emitir_propuestas", payload, FakeUsage(500, 200), urls=urls)])
    return AgenteDiscovery(Agente("discovery", "discovery_v1", "claude-sonnet-5-5", cliente=cli))


def _rawp(ticker="NUVL", nodo_ref="C01", mc=5e9, fuentes=None):
    return {"ticker": ticker, "nodo_ref": nodo_ref, "tesis_corta": "captura el valor del cuello",
            "por_que_ahora": "8-K 2026-10: contrato con hyperscaler", "market_cap": mc,
            "fuentes": fuentes if fuentes is not None else ["https://sec.gov/x"]}


def _rawn(nombre="Cuello nuevo X"):
    return {"nombre": nombre, "cluster": "semis", "factor_macro": None, "subnodos": [],
            "tesis_cuello": "oferta concentrada, pricing power", "por_que_ahora": "export control 2026",
            "fuentes": ["https://sec.gov/y"]}


def test_agente_devuelve_empresas_canonizadas_y_cuellos_nuevos():
    ag = _emite([_rawp("NUVL", "C01"), _rawp("AEHR", "C02", mc=2e9)], [_rawn("Cuello nuevo X")])
    r = ag.explorar(universo_actual={"MP"}, nodos_mapa=_NODOS)
    assert [p.ticker for p in r.empresas] == ["NUVL", "AEHR"]
    assert r.empresas[0].cuello == "Fotónica / CPO" and r.empresas[1].cuello == "HBM"  # nodo_ref → canónico
    assert [n.nombre for n in r.cuellos_nuevos] == ["Cuello nuevo X"]
    assert r.meta.agent == "discovery"


def test_agente_descarta_nodo_ref_invalido_con_motivo():
    # una empresa con nodo_ref que no existe → se descarta Y queda VISIBLE el motivo (observabilidad)
    r = _emite([_rawp("NUVL", "C01"), _rawp("ZZZ", "C99")]).explorar(universo_actual=set(), nodos_mapa=_NODOS)
    assert [p.ticker for p in r.empresas] == ["NUVL"]
    assert any(d["ticker"] == "ZZZ" and "nodo_ref" in d["motivo"] for d in r.descartes)


def test_agente_tope_y_dedup_y_universo():
    raws = [_rawp(t, "C01") for t in ("A", "B", "C")] + [_rawp("A", "C01")] + [_rawp("MP", "C02")]
    r = _emite(raws).explorar(universo_actual={"MP"}, nodos_mapa=_NODOS, max_propuestas=2)
    assert [p.ticker for p in r.empresas] == ["A", "B"]           # cap=2, sin dup, sin universo
    assert any(d["ticker"] == "MP" and "ya conocida" in d["motivo"] for d in r.descartes)  # universo visible


def test_agente_fallback_fuentes_a_urls():
    r = _emite([_rawp("NUVL", "C01", fuentes=[])],
               urls=["https://sec.gov/f", "https://x"]).explorar(universo_actual=set(), nodos_mapa=_NODOS)
    assert r.empresas[0].fuentes == ["https://sec.gov/f", "https://x"]


def test_encolar_propuestas_map_fit_entra_sola_al_universo(tmp_path):
    cola = ColaPropuestas(path=tmp_path / "cola.jsonl")
    p_ok = PropuestaEmpresa(ticker="NUVL", cuello="HBM", tesis_corta="t", por_que_ahora="x",
                            fuentes=["https://sec.gov/x"], market_cap=5e9)
    p_sinmapa = PropuestaEmpresa(ticker="ZZZ", cuello="cosa inventada", tesis_corta="t", por_que_ahora="x",
                                 fuentes=["https://sec.gov/x"], market_cap=5e9)
    altas = []
    res = encolar_propuestas(cola, [p_ok, p_sinmapa], ips_cfg=_IPS, universo_actual=set(),
                             nodos_conocidos={"HBM"}, alta_fn=lambda tk, p: altas.append(tk))
    est = {r["ticker"]: r["estado"] for r in res}
    assert est == {"NUVL": "aprobada", "ZZZ": "rechazada"}   # encaja → universo solo; sin encaje → rechazada
    assert altas == ["NUVL"]                                 # entró sola, sin humano


_2PRIM = ["https://www.sec.gov/Archives/edgar/data/1/a.htm", "https://www.sec.gov/Archives/edgar/data/2/b.htm"]


def test_validar_nodo_dedup_y_dos_fuentes_primarias():
    ok, _ = validar_nodo(PropuestaNodo(nombre="X", tesis_cuello="t", por_que_ahora="y", fuentes=_2PRIM),
                         nodos_conocidos=set())
    assert ok                                                    # 2 primarias → pasa
    ok1, m1 = validar_nodo(PropuestaNodo(nombre="Y", tesis_cuello="t", por_que_ahora="y",
                                         fuentes=["https://sec.gov/a", "https://reddit.com/x"]),
                           nodos_conocidos=set())
    assert not ok1 and any("≥2 fuentes primarias" in x for x in m1)   # solo 1 primaria → rechaza
    ok2, m2 = validar_nodo(PropuestaNodo(nombre="HBM", tesis_cuello="t", por_que_ahora="y", fuentes=_2PRIM),
                           nodos_conocidos={"HBM"})
    assert not ok2 and any("duplicado" in x for x in m2)


def test_encolar_nodos_curador_aprueba_y_rechaza(tmp_path):
    cola = ColaNodos(path=tmp_path / "nodos.jsonl")
    nodos = [PropuestaNodo(nombre="Cuello bueno", tesis_cuello="oferta concentrada", por_que_ahora="x", fuentes=_2PRIM),
             PropuestaNodo(nombre="Cuello narrativa", tesis_cuello="tema de moda", por_que_ahora="y", fuentes=_2PRIM)]
    cli = ScriptedLLM([
        resp_tool("emitir_veredicto", {"aprobar": True, "motivo": "oferta concentrada real"}, FakeUsage(100, 50)),
        resp_tool("emitir_veredicto", {"aprobar": False, "motivo": "es narrativa sin cuello"}, FakeUsage(100, 50)),
    ])
    curador = AgenteCurador(Agente("curador", "curador_mapa_v1", "claude-sonnet-5-5", cliente=cli))
    agregados = []
    res, costo = encolar_nodos(cola, nodos, curador, nodos_conocidos=set(),
                               alta_fn=lambda prop: agregados.append(prop["nombre"]))
    est = {r["nombre"]: r["estado"] for r in res}
    assert est == {"Cuello bueno": "aprobada", "Cuello narrativa": "rechazada"}
    assert agregados == ["Cuello bueno"]                     # solo el aprobado entra al mapa
    assert costo > 0


def test_overlay_round_trip_crece_el_mapa(tmp_path, monkeypatch):
    from backend.mapa import overlay
    from backend.mapa.brujula import nodos_conocidos, territorios_activos
    monkeypatch.setattr(overlay, "_OVERLAY_PATH", tmp_path / "ov.jsonl")
    antes = len(territorios_activos())
    overlay.agregar_overlay(nombre="Cuello nuevo Z", cluster="semis", nota="oferta concentrada")
    assert "Cuello nuevo Z" in overlay.nombres_overlay()
    assert "Cuello nuevo Z" in nodos_conocidos()              # ya es un nodo conocido para el encaje
    assert len(territorios_activos()) == antes + 1           # el mapa creció solo
