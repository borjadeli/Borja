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


def test_dossier_bull_bear_independientes_y_falsador():
    esc = sc.Escenario(tesis="t", supuestos=["a"], contraste_con_calculadoras="vs T*")
    d = sc.Dossier(
        meta=sc.AgentMeta(agent="analista", prompt_version="v1", model="claude-opus-5-5"),
        ticker="OKLO", negocio_y_posicion_cuello="SMR",
        valuacion_que_exige_el_precio="precio exige T*=12a",
        bull=esc, bear=esc.model_copy(update={"tesis": "bear"}),
        falsador=sc.Falsador(afirmacion="no firma contrato DOE", fecha_limite="2027-06-30",
                             que_lo_mataria="sin orden firme"),
        conviccion_0_1=0.6,
    )
    assert d.bull.tesis != d.bear.tesis            # independientes
    assert d.falsador.fecha_limite == "2027-06-30"  # falsador con fecha


def test_verificador_fail_bloquea():
    v = sc.VerificationReport(
        meta=_META.model_copy(update={"agent": "verificador"}),
        ticker="OKLO", veredicto="fail",
        checks=[sc.Check(afirmacion="rev $10M", fuente_ok=False, fecha_ok=True,
                        es_declaracion_corporativa=True, consistente_con_numeros=False, motivo="sin filing")],
        motivos=["cita no verificada"],
    )
    assert v.veredicto == "fail"


def test_pm_peso_objetivo_acotado():
    acc = sc.PMAccion(ticker="OKLO", accion="comprar", peso_objetivo=0.08,
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
