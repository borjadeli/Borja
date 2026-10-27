"""Tests del presupuesto MENSUAL persistente + logging de costos (v2 Fase 4, P0.4). Sin API."""
import json
from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import backend.agentes.base as base
from backend.agentes.base import Agente, FakeUsage, ScriptedLLM
from backend.agentes.presupuesto import gastado_mes_usd, ledger_mensual
from backend.models import Base, LLMCall


def _sesion():
    e = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(e)
    return Session(e, future=True)


def test_gastado_mes_suma_solo_el_mes_corriente():
    s = _sesion()
    s.add(LLMCall(agent="analista", model="m", cost_usd=1.5, timestamp=datetime(2026, 10, 5)))
    s.add(LLMCall(agent="pm", model="m", cost_usd=0.5, timestamp=datetime(2026, 10, 20)))
    s.add(LLMCall(agent="bear", model="m", cost_usd=9.0, timestamp=datetime(2026, 9, 30)))  # mes anterior
    s.flush()
    assert gastado_mes_usd(date(2026, 10, 27), session=s) == 2.0


def test_ledger_mensual_descuenta_lo_gastado_del_tope():
    s = _sesion()
    s.add(LLMCall(agent="analista", model="m", cost_usd=30.0, timestamp=datetime(2026, 10, 10)))
    s.flush()
    ld = ledger_mensual(40.0, date(2026, 10, 27), session=s)
    assert ld.sobre_semanal == 10.0            # 40 tope − 30 gastado este mes = 10 restante
    assert ld.disponible(para_evento=True) == 10.0


def test_gastado_mes_sin_datos_es_cero():
    assert gastado_mes_usd(date(2026, 10, 27), session=_sesion()) == 0.0


def test_agente_con_cliente_inyectado_NO_loguea(monkeypatch):
    # El gate: con ScriptedLLM (tests) no se toca la DB; solo el cliente real registra en llm_calls.
    registrados = []
    monkeypatch.setattr(base, "_persistir_costo", lambda meta: registrados.append(meta))
    schema = {"type": "object", "properties": {"a": {"type": "integer"}}, "required": ["a"],
              "additionalProperties": False}
    ag = Agente("x", "v1", "claude-haiku-5-5", cliente=ScriptedLLM([(json.dumps({"a": 1}), FakeUsage())]))
    ag.estructurado(system="s", user="u", payload_schema=schema)
    assert registrados == []
