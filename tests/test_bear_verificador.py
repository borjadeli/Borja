"""Tests de Bear (ScriptedLLM) y Verificador (determinista, sin API) — v2 Fase 3."""
from datetime import date

from backend.agentes import schemas as sc
from backend.agentes.base import Agente, FakeUsage, ScriptedLLM, resp_tool
from backend.agentes.bear import Bear
from backend.agentes.verificador import flags_supervivencia, verificar

_META = sc.AgentMeta(agent="analista", prompt_version="v1", model="claude-opus-5-5")
_ESC = sc.Escenario(tesis="t", supuestos=["a"], contraste_con_calculadoras="vs T*")
_FALS = sc.Falsador(afirmacion="no firma", fecha_limite="2027-06-30", que_lo_mataria="sin contrato")


def _claim(cid, url, *, tipo="hecho", verif="confirmed_by_filing", mat="central"):
    return sc.Claim(claim_id=cid, contenido="x", tipo=tipo, source_url=url, cited_text="c",
                    source_date="2026-01-01", known_at="2026-01-01", materiality=mat, verification=verif)


def _dossier(claims, soporte, red_flags=None):
    return sc.Dossier(meta=_META, ticker="OKLO", negocio_y_posicion_cuello="SMR",
                      claims=claims, tesis_claims_soporte=soporte,
                      valuacion_que_exige_el_precio="T*", bull=_ESC, bear=_ESC,
                      red_flags=red_flags or [], falsador=_FALS, conviccion_0_1=0.5)


FUENTES = ["https://sec.gov/a", "https://nrc.gov/b"]


# ---- Verificador ----

def test_pass_cuando_todo_trazable():
    d = _dossier([_claim("c1", "https://sec.gov/a"), _claim("c2", "https://nrc.gov/b", mat="soporte")],
                 soporte=["c1"])
    r = verificar(d, FUENTES)
    assert r.veredicto == "pass"
    assert r.meta.cost_usd == 0.0        # determinista: no gasta LLM


def test_fail_si_claim_central_sin_procedencia():
    d = _dossier([_claim("c1", "https://inventada.com/x")], soporte=["c1"])   # url no está en fuentes
    r = verificar(d, FUENTES)
    assert r.veredicto == "fail"
    assert any("c1" in m for m in r.motivos)


def test_review_si_claim_no_central_sin_procedencia():
    d = _dossier([_claim("c1", "https://sec.gov/a"),
                  _claim("c2", "https://inventada.com/x", mat="secundaria")], soporte=["c1"])
    r = verificar(d, FUENTES)
    assert r.veredicto == "review"


def test_review_si_tesis_se_apoya_en_declaracion_de_empresa():
    d = _dossier([_claim("c1", "https://sec.gov/a", tipo="declaracion_empresa",
                         verif="company_statement")], soporte=["c1"])
    r = verificar(d, FUENTES)
    assert r.veredicto == "review"        # trazable pero es declaración tratada como central


def test_flags_supervivencia_detectadas():
    rf = sc.RedFlag(tipo="material weakness en controles internos", severidad="alta",
                    cita=sc.Evidence(claim="10-K", source_url="https://sec.gov/a",
                                     source_date="2026-01-01", verification="confirmed_by_filing"))
    d = _dossier([_claim("c1", "https://sec.gov/a")], soporte=["c1"], red_flags=[rf])
    r = verificar(d, FUENTES)
    assert "material_weakness" in r.flags_supervivencia


def test_consistencia_llm_degrada_pero_no_mejora():
    d = _dossier([_claim("c1", "https://sec.gov/a")], soporte=["c1"])
    def degrada(_d):
        return "fail", ["narrativa contradice los números"], None
    r = verificar(d, FUENTES, consistencia_fn=degrada)
    assert r.veredicto == "fail" and "narrativa contradice los números" in r.motivos


# ---- Bear ----

def test_bear_emite_objeciones():
    payload = {"objeciones": [{"afirmacion_atacada": "demanda asegurada",
                               "contraevidencia": "pipeline no vinculante",
                               "citas": [{"claim": "LOIs no firmes", "source_url": "https://x.com/y",
                                          "source_date": "2026-01-01", "verification": "media_report"}],
                               "severidad": "alta"}]}
    scripted = ScriptedLLM([resp_tool("emitir_ataque", payload,
                                      FakeUsage(input_tokens=8000, output_tokens=300))])
    d = _dossier([_claim("c1", "https://sec.gov/a")], soporte=["c1"])
    bear = Bear(Agente("bear", "bear_v1", "claude-sonnet-5-5", cliente=scripted))
    atk = bear.atacar(d)
    assert len(atk.objeciones) == 1 and atk.objeciones[0].severidad == "alta"
    assert atk.replica_analista is None and atk.meta.cost_usd > 0


def test_fail_si_central_vacio():
    # tesis_claims_soporte vacío → no hay respaldo verificable → FAIL (antes daba PASS; auditoría P1)
    d = _dossier([_claim("c1", "https://sec.gov/a")], soporte=[])
    r = verificar(d, FUENTES)
    assert r.veredicto == "fail" and any("vacío" in m or "sin claims centrales" in m for m in r.motivos)


def test_fail_si_central_colgante():
    # un id central que no existe como claim → FAIL (antes daba PASS)
    d = _dossier([_claim("c1", "https://sec.gov/a")], soporte=["c1", "NO_EXISTE"])
    r = verificar(d, FUENTES)
    assert r.veredicto == "fail" and any("NO_EXISTE" in m for m in r.motivos)
