"""Tests del runner semanal (v2 Fase 4, doc 55) — cablea research→PM→decisión→paper. Sin API."""
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.agentes.base import Agente, FakeUsage, ScriptedLLM, resp_tool
from backend.agentes.ips import IPS, ContextoTicker
from backend.agentes.ledger_decisiones import LedgerDecisiones
from backend.agentes.orquestador import DecisionOrq, ResultadoSemana
from backend.agentes.orquestador_decision import OrquestadorDecision
from backend.agentes.pm import PM
from backend.agentes.runner_semanal import RunnerSemanal
from backend.agentes.schemas import (
    AgentMeta,
    Dossier,
    Escenario,
    Falsador,
    TriageDecision,
    VerificationReport,
)
from backend.ledger import core
from backend.ledger.models import crear_tablas

F = date(2026, 10, 27)
_U = FakeUsage(input_tokens=500, output_tokens=100)


def _ips():
    return IPS({"max_posiciones": 12, "peso_max_nombre": 0.20, "max_por_sector": 0.30, "max_por_cuello": 0.35,
                "caja_min": 0.0, "caja_max": 1.0, "max_ops_semana": 9, "market_cap_min_usd": 150e6,
                "market_cap_max_usd": 60e9, "adv_min_usd": 3e6, "cap_flag_supervivencia": 0.04})


def _esc():
    return Escenario(tesis="t", supuestos=["a"], contraste_con_calculadoras="c")


def _dossier(ticker="OKLO"):
    return Dossier(meta=AgentMeta(agent="analista", prompt_version="v1", model="claude-opus-5-5"),
                   ticker=ticker, negocio_y_posicion_cuello="SMR", valuacion_que_exige_el_precio="v",
                   bull=_esc(), bear=_esc(),
                   falsador=Falsador(afirmacion="a", fecha_limite="2027-01-01", que_lo_mataria="b"),
                   conviccion_0_1=0.7)


def _verif(ticker="OKLO", veredicto="pass"):
    return VerificationReport(meta=AgentMeta(agent="verificador", prompt_version="v1", model="claude-sonnet-5-5"),
                              ticker=ticker, veredicto=veredicto)


def _research_con(ticker="OKLO", hash_="h1", veredicto="pass"):
    td = TriageDecision(meta=AgentMeta(agent="triage", prompt_version="v1", model="claude-haiku-5-5"),
                        ticker=ticker, prioridad_0_3=3, incertidumbre_0_1=0.5, research_profundo=True, motivo="x")
    dec = DecisionOrq(ticker=ticker, accion="analizado", triage=td, dossier=_dossier(ticker),
                      verif=_verif(ticker, veredicto), hash=hash_)
    return ResultadoSemana(memo=None, decisiones=[dec])


class _StubResearch:
    def __init__(self, resultado):
        self._r = resultado

    def correr_semana(self, candidatos, *, memo_macro=None, hoy=None):
        return self._r


def _decision_payload(acciones, operar=True):
    return {"acciones": acciones, "respuestas_flags": [], "operar_ahora": operar, "razon_timing": "evento"}


def _accion(ticker="OKLO", peso=0.1):
    return {"ticker": ticker, "accion": "comprar", "peso_objetivo": peso, "conviccion_0_1": 0.7,
            "por_que_ese_tamano": "x", "tesis": "SMRs",
            "falsador": {"afirmacion": "a", "fecha_limite": "2027-01-01", "que_lo_mataria": "b"},
            "que_me_haria_vender": "c"}


@pytest.fixture
def sesion():
    engine = create_engine("sqlite:///:memory:", future=True)
    crear_tablas(engine)
    with Session(engine, future=True) as s:
        core.depositar(s, 100_000.0, date(2026, 1, 1))
        yield s


def test_ciclo_completo_compra_y_registra(tmp_path, sesion):
    pm = PM(Agente("pm", "pm_v1", "claude-opus-5-5",
                   cliente=ScriptedLLM([resp_tool("emitir_decision", _decision_payload([_accion()]), _U)])), _ips())
    decision = OrquestadorDecision(_ips(), LedgerDecisiones(path=tmp_path / "ld.jsonl"))
    runner = RunnerSemanal(research=_StubResearch(_research_con()), pm=pm, decision=decision)

    res = runner.correr([], session=sesion, precios={"OKLO": 50.0},
                        contexto={"OKLO": ContextoTicker(sector="energia", cuello="smr",
                                                         market_cap=5e9, adv_usd=10e6)},
                        hoy=F, ciclo="2026-10-27")

    assert res.dossiers_considerados == ["OKLO"]
    assert res.resultado_decision.clip == "none" and res.resultado_decision.no_action is False
    assert res.paper.fills == [{"ticker": "OKLO", "lado": "buy", "shares": 200, "precio": 50.0}]
    # el ledger de decisiones registró con el hash del dossier
    ds = decision.ledger.decisiones()
    assert len(ds) == 1 and ds[0].dossier_hash == "h1" and ds[0].ciclo == "2026-10-27"
    # la posición quedó en el ledger fiel
    assert core.proyectar(sesion, {"OKLO": 50.0})["posiciones"]["OKLO"].shares == 200
    assert "insuficiente" in res.hit_rate_resumen


def test_pm_sin_accion_no_opera(tmp_path, sesion):
    pm = PM(Agente("pm", "pm_v1", "claude-opus-5-5",
                   cliente=ScriptedLLM([resp_tool("emitir_decision", _decision_payload([], operar=False), _U)])),
            _ips())
    decision = OrquestadorDecision(_ips(), LedgerDecisiones(path=tmp_path / "ld.jsonl"))
    runner = RunnerSemanal(research=_StubResearch(_research_con()), pm=pm, decision=decision)

    res = runner.correr([], session=sesion, precios={"OKLO": 50.0},
                        contexto={"OKLO": ContextoTicker(sector="energia")}, hoy=F)
    assert res.paper.fills == [] and decision.ledger.decisiones() == []
    assert core.proyectar(sesion, {"OKLO": 50.0})["posiciones"] == {}
