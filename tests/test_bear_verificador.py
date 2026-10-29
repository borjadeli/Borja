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


def test_gap_no_central_aislado_es_pass_con_nota():
    # doc 64 B1: un gap no-central aislado NO baja a REVIEW — queda como NOTA (antes daba review).
    d = _dossier([_claim("c1", "https://sec.gov/a"),
                  _claim("c2", "https://inventada.com/x", mat="secundaria")], soporte=["c1"])
    r = verificar(d, FUENTES)
    assert r.veredicto == "pass" and any("c2" in n for n in r.notas)


def test_tasa_alta_de_gaps_no_centrales_baja_a_review():
    # muchos no-centrales sin procedencia (>3 y >1/3) → el Analista citó de memoria → REVIEW
    claims = [_claim("c1", "https://sec.gov/a")]   # central ok
    claims += [_claim(f"n{i}", "https://inventada.com/x", mat="secundaria") for i in range(5)]  # 5 gaps
    r = verificar(_dossier(claims, soporte=["c1"]), FUENTES)
    assert r.veredicto == "review" and any("tasa alta" in m for m in r.motivos)


def test_review_si_central_de_fuente_no_primaria():
    # la clase la deriva la URL, NO la etiqueta del Analista: un press release (globenewswire) como central,
    # aunque el LLM lo marque confirmed_by_filing, cae a REVIEW (no es fuente primaria regulatoria).
    url = "https://www.globenewswire.com/news/x"
    d = _dossier([_claim("c1", url, tipo="hecho", verif="confirmed_by_filing")], soporte=["c1"])
    r = verificar(d, [url])
    assert r.veredicto == "review" and any("no primaria" in m.lower() for m in r.motivos)


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


def _dp_ref(metric, value, period="instant"):
    from backend.agentes.provenance import DataKind, DataPoint, Source
    return DataPoint(entity="OKLO", metric=metric, value=value, unit="USD", kind=DataKind.ORIGINAL,
                     source=Source(name="SEC XBRL"), period_type=period)


def test_numerico_matchea_xbrl_pasa_aunque_url_no_primaria():
    # caja ~1.4B citando alpha-sense (no primaria) PERO coincide con el XBRL del pack → PASS (la primaria la
    # tenemos nosotros). Es el unlock de OKLO.
    c = sc.Claim(claim_id="c1", contenido="caja ~1.4B", tipo="hecho", source_url="https://www.alpha-sense.com/x",
                 cited_text="x", source_date="2026-03-17", known_at="2026-03-17", materiality="central",
                 verification="media_report", ref_metrica="cash", valor_num=1.4, escala="B", periodo="instant")
    r = verificar(_dossier([c], soporte=["c1"]), ["https://www.alpha-sense.com/x"],
                  pack={"cash": _dp_ref("cash", 1_430_000_000)})
    assert r.veredicto == "pass"


def test_numerico_contradice_xbrl_es_fail():
    c = sc.Claim(claim_id="c1", contenido="caja 5B", tipo="hecho", source_url="https://sec.gov/a",
                 cited_text="x", source_date="2026-03-17", known_at="2026-03-17", materiality="central",
                 verification="confirmed_by_filing", ref_metrica="cash", valor_num=5.0, escala="B",
                 periodo="instant")
    r = verificar(_dossier([c], soporte=["c1"]), ["https://sec.gov/a"],
                  pack={"cash": _dp_ref("cash", 1_430_000_000)})
    assert r.veredicto == "fail" and any("CONTRADICE" in m for m in r.motivos)


def test_gap_no_central_queda_explicito_en_notas():
    # un gap no-central aislado deja NOTA explícita (no silencioso) — y el veredicto es PASS (doc 64 B1)
    d = _dossier([_claim("c1", "https://sec.gov/a"),
                  _claim("c2", "https://inventada.com/x", mat="secundaria")], soporte=["c1"])
    r = verificar(d, FUENTES)
    assert r.veredicto == "pass" and any("c2" in n for n in r.notas)


# --- r3 #1 frescura + #2 clase epistémica ---
from datetime import date as _date  # noqa: E402
from backend.agentes.verificador import clase_por_url  # noqa: E402


def test_r3_clase_ex99_en_sec_es_company_statement():
    # un EX-99 (press release adjunto) en sec.gov NO es primaria; mismo comunicado en IR → misma clase
    assert clase_por_url("https://www.sec.gov/Archives/edgar/data/1/000/ex99-1.htm") == "company_statement"
    assert clase_por_url("https://investors.archer.com/news/x") == "company_statement"
    # el cuerpo del 10-Q sí es primaria
    assert clase_por_url("https://www.sec.gov/Archives/edgar/data/1/000/oklo-20260630.htm") == "primaria_regulatoria"


def test_r3_central_mas_viejo_que_ultimo_filing_es_review():
    # central con source_date de hace ~12m y hay un filing más nuevo en el pack → REVIEW por dato viejo (1d)
    c = sc.Claim(claim_id="c1", contenido="caja", tipo="hecho", source_url="https://sec.gov/a",
                 cited_text="x", source_date="2025-10-01", known_at="2025-10-01", materiality="central",
                 verification="confirmed_by_filing")
    d = _dossier([c], soporte=["c1"])
    r = verificar(d, ["https://sec.gov/a"], ultimo_filing_periodico=_date(2026, 8, 7), hoy=_date(2026, 10, 28))
    assert r.veredicto == "review" and any("dato viejo" in m for m in r.motivos)


def test_r3_falsador_vencido_es_fail():
    c = _claim("c1", "https://sec.gov/a")
    d = sc.Dossier(meta=_META, ticker="OKLO", negocio_y_posicion_cuello="SMR", claims=[c],
                   tesis_claims_soporte=["c1"], valuacion_que_exige_el_precio="T*", bull=_ESC, bear=_ESC,
                   falsador=sc.Falsador(afirmacion="x", fecha_limite="2026-01-01", que_lo_mataria="y"),
                   conviccion_0_1=0.5)
    r = verificar(d, FUENTES, hoy=_date(2026, 10, 28))
    assert r.veredicto == "fail" and any("falsador vencido" in m for m in r.motivos)
