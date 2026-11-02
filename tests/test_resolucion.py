"""Tests del ciclo de resolución (doc 74) — cierra el loop del ledger para el Brier real."""
from datetime import date

from backend.agentes.ledger_decisiones import LedgerDecisiones
from backend.agentes.resolucion import (
    aplicar_silencio_falsadores,
    consecuencia,
    pendientes,
    render_pendientes,
    resolver,
)
from backend.agentes.schemas import Falsador, PMAccion, VaraExterna

_VARA = VaraExterna(tipo="competitivo", metrica="m", umbral="u", comparador="c", fuente_medicion="f")


def _accion(ticker="OKLO", fecha="2026-01-01", conv=0.6):
    return PMAccion(ticker=ticker, accion="comprar", peso_objetivo=0.1, conviccion_0_1=conv,
                    por_que_ese_tamano="x", tesis="t",
                    falsador=Falsador(afirmacion="no firma contrato", fecha_limite=fecha,
                                      que_lo_mataria="x", vara_externa=_VARA),
                    que_me_haria_vender="y")


_BULL = {"prob": 0.3, "horizonte_fecha": "2026-02-01", "escenarios": []}


def test_pendientes_lista_falsador_y_bull_vencidos(tmp_path):
    ld = LedgerDecisiones(path=tmp_path / "ld.jsonl")
    ld.registrar_decision(_accion("OKLO", fecha="2026-01-01"), ciclo="c", bull=_BULL)   # ambos vencidos
    ld.registrar_decision(_accion("MP", fecha="2027-12-01"), ciclo="c")                 # futuro: no pendiente
    pend = pendientes(ld, date(2026, 10, 30))
    tipos = {(p.ticker, p.tipo) for p in pend}
    assert ("OKLO", "falsador") in tipos and ("OKLO", "bull") in tipos
    assert ("MP", "falsador") not in tipos
    # el falsador sugiere disparado por silencio; el bull requiere evidencia
    assert next(p for p in pend if p.tipo == "falsador").default_sugerido == "disparado"
    assert next(p for p in pend if p.tipo == "bull").default_sugerido == ""


def test_silencio_marca_disparado_y_devuelve_consecuencia(tmp_path):
    ld = LedgerDecisiones(path=tmp_path / "ld.jsonl")
    ld.registrar_decision(_accion("OKLO", fecha="2026-01-01"), ciclo="c")
    alertas = aplicar_silencio_falsadores(ld, date(2026, 10, 30))
    assert len(alertas) == 1 and "FALSADOR DISPARADO" in alertas[0] and "OKLO" in alertas[0]
    # idempotente: ya resuelto → no vuelve a estar pendiente ni se re-resuelve
    assert pendientes(ld, date(2026, 10, 30)) == [] or all(p.tipo == "bull" for p in pendientes(ld, date(2026, 10, 30)))
    assert aplicar_silencio_falsadores(ld, date(2026, 10, 30)) == []
    # el Brier ahora SÍ puntúa (outcome=0 por disparado, conv=0.6 → (0.6)^2=0.36)
    m = ld.metricas()
    assert m.n_resueltos == 1 and abs(m.brier - 0.36) < 1e-9


def test_resolver_explicito_bull_materializado(tmp_path):
    ld = LedgerDecisiones(path=tmp_path / "ld.jsonl")
    did = ld.registrar_decision(_accion("RGTI"), ciclo="c", bull=_BULL)
    resolver(ld, did, "bull", "materializado", nota="llegó al hito")
    m = ld.metricas()
    assert m.n_bull_resueltos == 1 and abs(m.brier_bull - (0.3 - 1.0) ** 2) < 1e-9


def test_render_pendientes_y_consecuencia():
    assert "sin predicciones" in render_pendientes([])
    assert "revisá" in consecuencia("OKLO", "no firma").lower() and "no se vende solo" in consecuencia("OKLO", "x")
