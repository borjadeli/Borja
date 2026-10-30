"""Tests de los contratos de datos + schemas de agentes (v2 Fase 3)."""
from datetime import date

import pytest
from pydantic import ValidationError

from backend.agentes import schemas as sc
from backend.agentes.provenance import DataKind, DataPack, DataPoint, Source, Verification


# ---- provenance / data pack ----

def _dp(metric, value, known_at):
    return DataPoint(entity="OKLO", metric=metric, value=value,
                     source=Source(name="EDGAR", document_type="10-Q"), known_at=known_at)


def test_datapoint_rechaza_no_finito():
    with pytest.raises(ValidationError):
        _dp("owner_fcf", float("nan"), date(2026, 1, 1))


def test_datapack_point_in_time():
    pack = DataPack(ticker="OKLO", as_of=date(2026, 10, 1), puntos=[
        _dp("revenue", 1.0, date(2026, 8, 1)),      # visible
        _dp("revenue", 2.0, date(2026, 11, 1)),     # futuro → no visible al 2026-10-01
    ])
    vis = pack.visible_en(date(2026, 10, 1))
    assert len(vis) == 1 and vis[0].value == 1.0


def test_datakind_y_verification_son_enums():
    dp = _dp("g_D", 0.2, None)
    dp = dp.model_copy(update={"kind": DataKind.DERIVED, "verification": Verification.COMPANY_STATEMENT})
    assert dp.kind == "derived" and dp.verification == "company_statement"


# ---- schemas de agentes ----

_META = sc.AgentMeta(agent="triage", prompt_version="v1", model="claude-haiku-5-5")
_ESC = sc.Escenario(tesis="t", supuestos=["a"], contraste_con_calculadoras="vs T*")
_FALS = sc.Falsador(afirmacion="x", fecha_limite="2027-01-01", que_lo_mataria="y")


def test_triage_valida_rangos():
    t = sc.TriageDecision(meta=_META, ticker="OKLO", prioridad_0_3=3,
                          incertidumbre_0_1=0.7, research_profundo=True, motivo="borde")
    assert t.research_profundo
    with pytest.raises(ValidationError):
        sc.TriageDecision(meta=_META, ticker="X", prioridad_0_3=5,   # fuera de 0-3
                          incertidumbre_0_1=0.5, research_profundo=False, motivo="")
    with pytest.raises(ValidationError):
        sc.TriageDecision(meta=_META, ticker="X", prioridad_0_3=1,
                          incertidumbre_0_1=1.5, research_profundo=False, motivo="")  # >1


def test_dossier_claims_y_falsador():
    esc = sc.Escenario(tesis="t", supuestos=["a"], contraste_con_calculadoras="vs T*")
    claim = sc.Claim(claim_id="c1", contenido="$1.41B caja per 10-K", tipo="hecho",
                     source_url="https://sec.gov/...", cited_text="cash of $1.41 billion",
                     materiality="central", verification="confirmed_by_filing")
    d = sc.Dossier(
        meta=sc.AgentMeta(agent="analista", prompt_version="v1", model="claude-opus-5-5"),
        ticker="OKLO", negocio_y_posicion_cuello="SMR",
        claims=[claim], tesis_claims_soporte=["c1"],
        valuacion_que_exige_el_precio="precio exige T*=12a",
        bull=esc, bear=esc.model_copy(update={"tesis": "bear"}),
        falsador=sc.Falsador(afirmacion="no firma contrato DOE", fecha_limite="2027-06-30",
                             que_lo_mataria="sin orden firme"),
        conviccion_0_1=0.6,
    )
    assert d.bull.tesis != d.bear.tesis            # independientes
    assert d.tesis_claims_soporte == ["c1"]        # gate del Verificador
    assert d.claims[0].materiality == "central"


def test_verificador_tres_estados():
    v = sc.VerificationReport(
        meta=_META.model_copy(update={"agent": "verificador"}),
        ticker="OKLO", veredicto="fail",
        checks=[sc.Check(claim_id="c1", procedencia_ok=False, numeros_ok=False,
                        es_declaracion_corporativa=True, dato_vigente=True, motivo="URL no trazable")],
        flags_supervivencia=["going_concern"],
        motivos=["claim central sin procedencia"],
    )
    assert v.veredicto == "fail"
    assert v.flags_supervivencia == ["going_concern"]
    with pytest.raises(ValidationError):
        sc.VerificationReport(meta=_META, ticker="X", veredicto="maybe")   # fuera de pass/review/fail


def test_pm_peso_objetivo_acotado():
    acc = sc.PMAccion(ticker="OKLO", accion="comprar", peso_objetivo=0.08, conviccion_0_1=0.6,
                      por_que_ese_tamano="carril", tesis="opción",
                      falsador=sc.Falsador(afirmacion="x", fecha_limite="2027-01-01", que_lo_mataria="y"),
                      que_me_haria_vender="dilución")
    sc.PMDecision(meta=_META.model_copy(update={"agent": "pm"}), acciones=[acc],
                  operar_ahora=True, razon_timing="evento")
    with pytest.raises(ValidationError):
        sc.PMAccion(ticker="X", accion="comprar", peso_objetivo=1.5,   # >1
                    por_que_ese_tamano="", tesis="",
                    falsador=sc.Falsador(afirmacion="x", fecha_limite="2027-01-01", que_lo_mataria="y"),
                    que_me_haria_vender="")


def test_invertibilidad_ficha_opcional_y_valida():
    import backend.agentes.schemas as s
    inv = s.Invertibilidad(
        riesgo_remanente="comercial", next_value_inflection="PPA firme con hyperscaler",
        months_to_inflection=12, fundamental_impact_if_successful="valida demanda y margen",
        independent_evidence="8-K con el contrato", traccion_0_4=3,
        milestone_funding_coverage="caja cubre 18m", stress_funding_gap="gap 0 bajo estrés",
        subsequent_capital_need="~$400M capex a 2030", dilution_exposure="ATM $1B vigente",
        price_implied_requirements="exige 2GW a 2032; base rate <5%",
        critical_unverified_assumption="que la NRC licencie antes de 2028",
        test_de_atraso="si arranca en 2030 en vez de 2028, el EV se recorta ~30% por dilución",
        analyst_classification="satelite")
    d = s.Dossier(meta=_META.model_copy(update={"agent": "analista"}), ticker="OKLO",
                  negocio_y_posicion_cuello="n", valuacion_que_exige_el_precio="v",
                  bull=_ESC, bear=_ESC, falsador=_FALS, conviccion_0_1=0.4, invertibilidad=inv)
    assert d.invertibilidad.riesgo_remanente == "comercial" and d.invertibilidad.traccion_0_4 == 3


def test_dossier_sin_invertibilidad_sigue_valido():
    import backend.agentes.schemas as s
    d = s.Dossier(meta=_META, ticker="X", negocio_y_posicion_cuello="n", valuacion_que_exige_el_precio="v",
                  bull=_ESC, bear=_ESC, falsador=_FALS, conviccion_0_1=0.3)
    assert d.invertibilidad is None       # legacy / opcional
