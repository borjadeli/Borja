"""Parser de contratos (Bloque 2, r9a #3): pre-filtro Item 1.01 + bonus fresco + carril contrato nuevo."""
import json

from backend.agentes.base import FakeUsage, ScriptedLLM, resp_texto
from backend.agentes.contratos import (bonus_contrato, clasificar_contrato, es_item_contrato,
                                        VENTANA_DIAS)
from backend.agentes.oportunidad import FilaScore, asignar_carriles


def test_prefiltro_item_contrato():
    assert es_item_contrato("1.01") and es_item_contrato(["1.01", "9.01"])
    assert es_item_contrato("7.01") and es_item_contrato(["8.01", "9.01"])    # P1-5: anuncios también son candidatos
    assert not es_item_contrato("2.03") and not es_item_contrato(None) and not es_item_contrato([])


def test_no_contrato_no_gasta_llm():
    # sin ítem de contrato → no_cuenta SIN cliente LLM (si llamara a la API, no habría cliente y tiraría)
    c = clasificar_contrato("texto cualquiera", items="2.03", fecha="2026-01-01", cliente=None)
    assert c.label == "no_cuenta" and c.cuenta is False and c.tipo == "no_contrato"


def test_clasifica_con_cliente_scripted():
    payload = {"label": "firme", "tipo": "gobierno_offtake", "contraparte": "DOE",
               "monto_usd": 9e8, "razon": "offtake firme a precio fijo"}
    cli = ScriptedLLM([resp_texto(json.dumps(payload), FakeUsage(input_tokens=800, output_tokens=60))])
    c = clasificar_contrato("DOE firm fixed price HALEU $900M", items="1.01", fecha="2026-02-01", cliente=cli)
    assert c.label == "firme" and c.cuenta is True and c.contraparte == "DOE" and c.monto_usd == 9e8


def test_anuncio_801_capea_firme_a_condicional():
    # P1-5: un 8.01/7.01 (press release) que el LLM clasifica "firme" se CAPEA a condicional (no es acuerdo definitivo)
    payload = {"label": "firme", "tipo": "gobierno_offtake", "contraparte": "Walmart",
               "monto_usd": 6e9, "razon": "anuncia acuerdo de suministro"}
    cli = ScriptedLLM([resp_texto(json.dumps(payload), FakeUsage(input_tokens=800, output_tokens=60))])
    c = clasificar_contrato("announces $6B supply agreement with Walmart", items="8.01", fecha="2026-02-01", cliente=cli)
    assert c.label == "condicional" and c.cuenta is True and "capeado" in c.razon


def test_bonus_decae_y_filtra():
    assert bonus_contrato("firme", 0) == 0.05                      # fresco → máximo
    assert bonus_contrato("firme", VENTANA_DIAS / 2) == 0.025      # mitad de ventana → mitad
    assert bonus_contrato("firme", VENTANA_DIAS + 1) == 0.0        # viejo → 0
    assert bonus_contrato("condicional", 0) == 0.02               # condicional < firme
    assert bonus_contrato("no_cuenta", 0) == 0.0                  # no cuenta → 0
    assert bonus_contrato("firme", None) == 0.0                   # sin fecha → 0


def _f(tk, score):
    return FilaScore(tk, "c", score, 0.5, 0.5, 0.5, 1.0)


def test_carril_contrato_nuevo_garantiza_deep():
    sel = asignar_carriles(
        posiciones={"MP"}, fichas_zona={}, fichas_estado={},
        scores=[_f("TOP1", 0.9), _f("TOP2", 0.8), _f("CONTR", 0.1)],
        cupo_oportunidad=1, contratos_nuevos={"CONTR", "MP"})
    assert sel.contrato_nuevo == ["CONTR"]        # MP ya es posición → no duplica
    assert "CONTR" not in sel.oportunidad         # no come cupo de oportunidad (ya tiene deep)
    assert sel.oportunidad == ["TOP1"]            # el cupo 1 lo toma el top score, no el contrato


def test_carril_contrato_respeta_blackout():
    sel = asignar_carriles(
        posiciones=set(), fichas_zona={}, fichas_estado={}, scores=[],
        cupo_oportunidad=4, contratos_nuevos={"X"}, blackout={"X"})
    assert sel.contrato_nuevo == []               # ya analizado pre-earnings → no re-deep


def test_detectar_contratos_universo_feed_a_parser():
    from dataclasses import dataclass as _dc
    from datetime import date, datetime

    from backend.agentes.contratos import detectar_contratos_universo

    @_dc
    class _F:
        items: str
        fecha: datetime
        url: str

    hoy = date(2026, 3, 1)
    filings = {
        "LEU": [_F("1.01,9.01", datetime(2026, 2, 20), "u-firme"),      # 1.01 fresco → cuenta
                _F("2.03", datetime(2026, 2, 25), "u-fin")],            # no 1.01 → ni se clasifica
        "MP": [_F("1.01", datetime(2025, 1, 1), "u-viejo")],            # 1.01 pero fuera de ventana (>90d)
        "X": [_F("5.02", datetime(2026, 2, 28), "u-x")],               # sin 1.01
    }
    # el excerpt no importa (el cliente scripted decide); 1 respuesta porque solo LEU llega al parser
    cli = ScriptedLLM([resp_texto(json.dumps({"label": "firme", "tipo": "gobierno_offtake",
                                              "contraparte": "DOE", "monto_usd": 9e8, "razon": "offtake firme"}),
                                  FakeUsage(input_tokens=800, output_tokens=60))])
    out = detectar_contratos_universo(["LEU", "MP", "X"], filings_fn=lambda tk: filings.get(tk, []),
                                      excerpt_fn=lambda url: "texto", hoy=hoy, cliente=cli)
    assert set(out) == {"LEU"}                                          # solo el 1.01 fresco que cuenta
    assert out["LEU"].label == "firme" and out["LEU"].contraparte == "DOE" and out["LEU"].bonus > 0
