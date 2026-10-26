"""Tests del Analista (v2 Fase 3). Sin API — ScriptedLLM con respuestas tool_use guionadas."""
from datetime import date

from backend.agentes.analista import Analista
from backend.agentes.base import Agente, FakeUsage, ScriptedLLM, resp_sin_emitir, resp_tool
from backend.agentes.provenance import DataPack

PACK = DataPack(ticker="OKLO", as_of=date(2026, 10, 26), puntos=[])

PAYLOAD = {
    "negocio_y_posicion_cuello": "SMR / reactores avanzados",
    "claims": [{"claim_id": "c1", "contenido": "$1.41B en caja per 10-K", "tipo": "hecho",
                "source_url": "https://sec.gov/oklo-10k", "cited_text": "cash of $1.41 billion",
                "source_date": "2026-02-01", "known_at": "2026-02-01",
                "materiality": "central", "verification": "confirmed_by_filing"}],
    "tesis_claims_soporte": ["c1"],
    "valuacion_que_exige_el_precio": "el precio exige T*~12 años de crecimiento",
    "bull": {"tesis": "demanda IA empuja SMRs", "supuestos": ["NRC aprueba"],
             "contraste_con_calculadoras": "vs T*=12a"},
    "bear": {"tesis": "pre-revenue dilutivo, timeline largo", "supuestos": ["NRC se demora"],
             "contraste_con_calculadoras": "vs burden alto"},
    "catalizadores": [{"descripcion": "permiso NRC Idaho", "fecha_esperada": "2027-01-01",
                       "tipo": "regulatorio"}],
    "red_flags": [{"tipo": "dilucion", "severidad": "media",
                   "cita": {"claim": "ventas de acciones ATM", "source_url": "", "source_date": "",
                            "verification": "hypothesis"}}],
    "falsador": {"afirmacion": "no firma contrato comercial firme", "fecha_limite": "2027-06-30",
                 "que_lo_mataria": "sin orden firme la tesis de demanda cae"},
    "conviccion_0_1": 1.5,       # fuera de rango a propósito → debe clampear a 1.0
}


def _analista(scripted):
    return Analista(Agente("analista", "analista_v1", "claude-opus-5-5", cliente=scripted))


def test_emite_dossier_en_una_llamada_y_junta_fuentes():
    scripted = ScriptedLLM([resp_tool("emitir_dossier", PAYLOAD,
                                      FakeUsage(input_tokens=20000, output_tokens=600),
                                      urls=["https://sec.gov/oklo-10k", "https://sec.gov/oklo-10k",
                                            "https://nrc.gov/idaho"])])
    r = _analista(scripted).analizar("oklo", data_pack=PACK)
    assert r.dossier is not None and r.dossier.ticker == "OKLO"
    assert r.dossier.tesis_claims_soporte == ["c1"]
    assert r.dossier.conviccion_0_1 == 1.0                       # clampeado
    assert r.fuentes == ["https://sec.gov/oklo-10k", "https://nrc.gov/idaho"]   # deduplicado
    assert r.meta.cost_usd > 0 and len(scripted.llamadas) == 1


def test_nudge_si_no_emite_al_terminar():
    scripted = ScriptedLLM([
        resp_sin_emitir(FakeUsage(input_tokens=15000, output_tokens=300)),      # termina sin emitir
        resp_tool("emitir_dossier", PAYLOAD, FakeUsage(input_tokens=500, output_tokens=600)),  # tras el empujón
    ])
    r = _analista(scripted).analizar("OKLO", data_pack=PACK)
    assert r.dossier is not None
    assert len(scripted.llamadas) == 2
    # el 2º request lleva el empujón como mensaje de usuario
    assert any(m["role"] == "user" and "emitir_dossier" in str(m["content"])
               for m in scripted.llamadas[1]["messages"])


def test_pause_turn_reenvia_sin_gastar_nudge():
    scripted = ScriptedLLM([
        resp_sin_emitir(FakeUsage(input_tokens=15000, output_tokens=200), stop_reason="pause_turn"),
        resp_tool("emitir_dossier", PAYLOAD, FakeUsage(input_tokens=500, output_tokens=600)),
    ])
    r = _analista(scripted).analizar("OKLO", data_pack=PACK)
    assert r.dossier is not None and len(scripted.llamadas) == 2


def test_falla_si_no_emite_tras_el_nudge():
    scripted = ScriptedLLM([
        resp_sin_emitir(FakeUsage(input_tokens=15000, output_tokens=300)),
        resp_sin_emitir(FakeUsage(input_tokens=400, output_tokens=200)),
    ])
    r = _analista(scripted).analizar("OKLO", data_pack=PACK)
    assert r.dossier is None            # no emitió ni tras el empujón
    assert r.meta.cost_usd > 0          # pero el costo gastado queda registrado
    assert len(scripted.llamadas) == 2
