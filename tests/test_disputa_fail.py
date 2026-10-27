"""Tests del canal de disputa del FAIL (v2 Fase 4, doc 55 §4.1). Sin API."""
from backend.agentes.disputa_fail import DisputaFAIL, LedgerDisputas, disputar
from backend.agentes.schemas import AgentMeta, Claim, Dossier, Escenario, Falsador


def _esc():
    return Escenario(tesis="t", supuestos=["a"], contraste_con_calculadoras="c")


def _claim(cid="C1", url="http://x", tipo="hecho", verification="media_report"):
    return Claim(claim_id=cid, contenido="hecho central", tipo=tipo, source_url=url,
                 materiality="central", verification=verification)


def _dossier_fail():
    """Dossier cuyo claim central C1 (source_url http://x) no tiene procedencia → FAIL con fuentes=[]."""
    return Dossier(meta=AgentMeta(agent="analista", prompt_version="v1", model="claude-opus-5-5"),
                   ticker="OKLO", negocio_y_posicion_cuello="SMR", valuacion_que_exige_el_precio="v",
                   claims=[_claim()], tesis_claims_soporte=["C1"], bull=_esc(), bear=_esc(),
                   falsador=Falsador(afirmacion="a", fecha_limite="2027-01-01", que_lo_mataria="b"),
                   conviccion_0_1=0.6)


def test_disputa_ganada_saca_del_fail():
    d = _dossier_fail()
    disputa = DisputaFAIL(claim_id="C1", por_que_artefacto="dato mal escalado",
                          fuente_propuesta="http://x", cited_text="...")
    # el re-chequeo independiente CONFIRMA la fuente propuesta
    res = disputar(d, [], disputa, refetch_fn=lambda _dsp: ["http://x"])
    assert res.veredicto_previo == "fail" and res.veredicto_nuevo != "fail"
    assert res.a_favor_pm is True and res.fuentes_confirmadas == ["http://x"]


def test_disputa_perdida_sostiene_el_fail():
    d = _dossier_fail()
    disputa = DisputaFAIL(claim_id="C1", por_que_artefacto="x", fuente_propuesta="http://x")
    # el re-chequeo NO confirma (fuente no verificable) → el FAIL se sostiene
    res = disputar(d, [], disputa, refetch_fn=lambda _dsp: [])
    assert res.veredicto_nuevo == "fail" and res.a_favor_pm is False


def test_pm_no_overridea_sin_confirmacion_independiente():
    # aunque el PM proponga la URL exacta del claim, si el re-chequeo no la confirma, no se agrega → FAIL.
    d = _dossier_fail()
    disputa = DisputaFAIL(claim_id="C1", por_que_artefacto="x", fuente_propuesta="http://x")
    res = disputar(d, [], disputa, refetch_fn=lambda _dsp: [])
    assert res.fuentes_confirmadas == [] and res.veredicto_nuevo == "fail"


def test_ledger_disputas_cuenta_ganadas_y_perdidas(tmp_path):
    ld = LedgerDisputas(path=tmp_path / "disp.jsonl")
    d = _dossier_fail()
    disputa = DisputaFAIL(claim_id="C1", por_que_artefacto="x", fuente_propuesta="http://x")
    ganada = disputar(d, [], disputa, refetch_fn=lambda _dsp: ["http://x"])
    perdida = disputar(d, [], disputa, refetch_fn=lambda _dsp: [])
    ld.registrar("OKLO", disputa, ganada)
    ld.registrar("OKLO", disputa, perdida)
    m = ld.metricas()
    assert m.total == 2 and m.ganadas_pm == 1 and m.perdidas_pm == 1 and m.ratio_ganadas == 0.5
