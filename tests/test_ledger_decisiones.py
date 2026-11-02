"""Tests del ledger de decisiones del PM (v2 Fase 4, doc 55). Append-only, sin API."""
from datetime import date

from backend.agentes.ledger_decisiones import LedgerDecisiones
from backend.agentes.schemas import (
    AgentMeta,
    AuditObjecion,
    AuditReport,
    Falsador,
    PMAccion,
)


def _accion(ticker="OKLO", peso=0.1, conv_fecha="2026-12-01", conviccion=0.6) -> PMAccion:
    return PMAccion(
        ticker=ticker, accion="comprar", peso_objetivo=peso, conviccion_0_1=conviccion,
        por_que_ese_tamano="convicción media, burden tolerable",
        tesis="despliegue de SMRs con offtake contratado",
        falsador=Falsador(afirmacion="pierde el contrato con el DoE", fecha_limite=conv_fecha,
                          que_lo_mataria="cancelación anunciada"),
        que_me_haria_vender="dilución > 20% sin hito", dossier_hash="abc123")


def _ledger(tmp_path) -> LedgerDecisiones:
    return LedgerDecisiones(path=tmp_path / "ld.jsonl")


def test_registrar_devuelve_id_y_es_append(tmp_path):
    ld = _ledger(tmp_path)
    id1 = ld.registrar_decision(_accion("OKLO", conviccion=0.7), ciclo="2026-10-27")
    id2 = ld.registrar_decision(_accion("MP", conviccion=0.5), ciclo="2026-10-27")
    assert id1 != id2
    ds = ld.decisiones()
    assert [d.ticker for d in ds] == ["OKLO", "MP"]
    assert ds[0].conviccion_0_1 == 0.7 and ds[0].clip == "none"


def test_clip_marca_pm_clip(tmp_path):
    ld = _ledger(tmp_path)
    ld.registrar_decision(_accion("OKLO", peso=0.25), ciclo="c",
                          peso_resultante=0.20, clip="local_simple")
    d = ld.decisiones()[0]
    assert d.peso_objetivo == 0.25 and d.peso_resultante == 0.20 and d.clip == "local_simple"


def test_objeciones_auditor_se_registran(tmp_path):
    ld = _ledger(tmp_path)
    audit = AuditReport(
        meta=AgentMeta(agent="auditor", prompt_version="v1", model="claude-opus-5-5"),
        objeciones=[AuditObjecion(tipo="concentracion", detalle="3 nombres = 1 apuesta nuclear",
                                  severidad="alta")],
        devuelve_al_pm=True)
    ld.registrar_decision(_accion(), ciclo="c", auditoria=audit)
    d = ld.decisiones()[0]
    assert len(d.objeciones_auditor) == 1 and d.objeciones_auditor[0].tipo == "concentracion"


def test_pendientes_solo_vencidos_sin_resolver(tmp_path):
    ld = _ledger(tmp_path)
    vencido = ld.registrar_decision(_accion("OKLO", conv_fecha="2026-01-01"), ciclo="c")
    futuro = ld.registrar_decision(_accion("MP", conv_fecha="2027-01-01"), ciclo="c")
    pend = ld.pendientes(hoy=date(2026, 10, 27))
    assert [d.decision_id for d in pend] == [vencido]
    assert futuro not in [d.decision_id for d in pend]
    # al resolver, deja de estar pendiente
    ld.resolver_falsador(vencido, "no_disparado")
    assert ld.pendientes(hoy=date(2026, 10, 27)) == []


def test_metricas_brier_y_hit_rate_por_bucket(tmp_path):
    ld = _ledger(tmp_path)
    # alta convicción (0.8) que se sostiene → buena calibración
    a = ld.registrar_decision(_accion("OKLO", conviccion=0.8), ciclo="c")
    # alta convicción (0.9) que se FALSA → mala calibración
    b = ld.registrar_decision(_accion("MP", conviccion=0.9), ciclo="c")
    ld.resolver_falsador(a, "no_disparado")   # outcome=1, pred=0.8 → (0.2)^2=0.04
    ld.resolver_falsador(b, "disparado")       # outcome=0, pred=0.9 → (0.9)^2=0.81
    m = ld.metricas()
    assert m.n_resueltos == 2
    assert m.brier == round((0.04 + 0.81) / 2, 4)
    assert m.hit_rate_falsadores == 0.5        # 1 de 2 falsadores se disparó
    alta = next(b for b in m.por_bucket if b.bucket == "alta")
    assert alta.n == 2 and alta.sostenidos == 1 and alta.falsados == 1


def test_metricas_vacias_sin_resueltos(tmp_path):
    ld = _ledger(tmp_path)
    ld.registrar_decision(_accion(), ciclo="c")
    m = ld.metricas()
    assert m.n_resueltos == 0 and m.brier is None and m.hit_rate_falsadores is None


def test_resolver_objecion_se_proyecta(tmp_path):
    ld = _ledger(tmp_path)
    did = ld.registrar_decision(_accion(), ciclo="c")
    ld.resolver_objecion(did, 0, "acertada")
    ld.resolver_objecion(did, 0, "errada")     # otra objeción puntuada (idx distinto en la práctica)
    m = ld.metricas()
    assert m.objeciones_resueltas == 2 and m.objeciones_acertadas == 1


def test_persistencia_releyendo_desde_disco(tmp_path):
    ruta = tmp_path / "ld.jsonl"
    LedgerDecisiones(path=ruta).registrar_decision(_accion(conviccion=0.7), ciclo="c")
    # un ledger nuevo sobre el mismo archivo ve la decisión (la verdad vive en el log)
    assert len(LedgerDecisiones(path=ruta).decisiones()) == 1


# --------------------------------------------------------------------------- D1: persistencia + Brier de bull

_BULL = {"prob": 0.3, "prob_implicita": 0.63, "horizonte_fecha": "2027-01-01",
         "escenarios": [{"nombre": "bull", "metrica_terminal": 9e8, "multiplo_salida": 8, "anios": 1, "prob": 0.3}]}


def test_persiste_snapshot_del_puente():
    from backend.agentes.ledger_decisiones import LedgerDecisiones
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        ld = LedgerDecisiones(path=Path(tmp) / "ld.jsonl")
        did = ld.registrar_decision(_accion("RGTI"), ciclo="c", bull=_BULL)
        d = {x.decision_id: x for x in ld.decisiones()}[did]
        assert d.prob_bull == 0.3 and d.prob_bull_implicita == 0.63
        assert d.horizonte_bull_fecha == "2027-01-01" and len(d.escenarios) == 1


def test_pendientes_bull_solo_vencidos_sin_resolver(tmp_path):
    from backend.agentes.ledger_decisiones import LedgerDecisiones
    from datetime import date
    ld = LedgerDecisiones(path=tmp_path / "ld.jsonl")
    vencido = ld.registrar_decision(_accion("A"), ciclo="c", bull={**_BULL, "horizonte_fecha": "2026-01-01"})
    ld.registrar_decision(_accion("B"), ciclo="c", bull={**_BULL, "horizonte_fecha": "2027-06-01"})
    pend = ld.pendientes_bull(date(2026, 10, 30))
    assert [p.decision_id for p in pend] == [vencido]          # solo el vencido
    ld.resolver_bull(vencido, "materializado")
    assert ld.pendientes_bull(date(2026, 10, 30)) == []        # ya resuelto


def test_brier_bull_se_calcula(tmp_path):
    from backend.agentes.ledger_decisiones import LedgerDecisiones
    ld = LedgerDecisiones(path=tmp_path / "ld.jsonl")
    a = ld.registrar_decision(_accion("A"), ciclo="c", bull={**_BULL, "prob": 0.3})
    b = ld.registrar_decision(_accion("B"), ciclo="c", bull={**_BULL, "prob": 0.8})
    ld.resolver_bull(a, "no_materializado")    # outcome=0, pred=0.3 → 0.09
    ld.resolver_bull(b, "materializado")       # outcome=1, pred=0.8 → 0.04
    m = ld.metricas()
    assert m.n_bull_resueltos == 2 and abs(m.brier_bull - (0.09 + 0.04) / 2) < 1e-9
    # el Brier de FALSADORES es independiente (no se mezcla)
    assert m.n_resueltos == 0 and m.brier is None


def test_sin_bull_no_rompe_metricas(tmp_path):
    from backend.agentes.ledger_decisiones import LedgerDecisiones
    ld = LedgerDecisiones(path=tmp_path / "ld.jsonl")
    ld.registrar_decision(_accion("A"), ciclo="c")             # decisión legacy sin bull
    m = ld.metricas()
    assert m.brier_bull is None and m.n_bull_resueltos == 0
