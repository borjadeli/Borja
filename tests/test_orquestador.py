"""Tests del ledger de presupuesto + orquestador (v2 Fase 3). Agentes stub, sin API."""
from datetime import date

from backend.agentes import schemas as sc
from backend.agentes.analista import ResultadoAnalista
from backend.agentes.orquestador import CacheDossiers, Orquestador, hash_pack
from backend.agentes.presupuesto import LedgerPresupuesto, peor_caso_usd
from backend.agentes.provenance import DataPack
from backend.agentes.triage import SenalesTriage

HOY = date(2026, 10, 26)
_META = sc.AgentMeta(agent="x", prompt_version="v1", model="claude-opus-5-5")
_ESC = sc.Escenario(tesis="t", supuestos=["a"], contraste_con_calculadoras="c")
_FALS = sc.Falsador(afirmacion="a", fecha_limite="2027-01-01", que_lo_mataria="b")


# ---- ledger ----

def test_ledger_tope_evento_vs_agendado_y_degradacion():
    l = LedgerPresupuesto(sobre_semanal=10.0, reserva_eventos_pct=0.2)
    assert l.disponible() == 8.0                 # agendado = sobre×(1-0.2)
    assert l.disponible(para_evento=True) == 10.0
    l.gastado = 7.0
    assert l.modo() == "restringido"             # 70%
    l.gastado = 9.2
    assert l.modo() == "solo_reuso"              # 90%
    l.gastado = 10.0
    assert l.modo() == "corte"


def test_ledger_reserva_y_confirma():
    l = LedgerPresupuesto(sobre_semanal=10.0, reserva_eventos_pct=0.0)
    assert l.reservar(3.0) is True and l.reservado == 3.0
    assert l.disponible() == 7.0
    l.confirmar(3.0, 1.2)                         # costó menos que el peor-caso
    assert l.reservado == 0.0 and l.gastado == 1.2 and l.disponible() == 8.8


# ---- orquestador (stubs) ----

def _dossier(ticker="OKLO"):
    c = sc.Claim(claim_id="c1", contenido="x", tipo="hecho", source_url="https://sec.gov/a",
                 cited_text="c", source_date="2026-01-01", known_at="2026-01-01",
                 materiality="central", verification="confirmed_by_filing")
    return sc.Dossier(meta=_META, ticker=ticker, negocio_y_posicion_cuello="SMR", claims=[c],
                      tesis_claims_soporte=["c1"], valuacion_que_exige_el_precio="T*", bull=_ESC, bear=_ESC,
                      falsador=_FALS, conviccion_0_1=0.5)


class _Triage:
    def __init__(self, research=True, prioridad=3):
        self.research, self.prioridad = research, prioridad
    def evaluar(self, ticker, senales, resumen_hechos_nuevos=""):
        return sc.TriageDecision(meta=_META, ticker=ticker.upper(), prioridad_0_3=self.prioridad,
                                 incertidumbre_0_1=0.5, research_profundo=self.research, motivo="x")


class _Analista:
    def __init__(self, cost=0.5): self.cost, self.llamadas = cost, 0
    def analizar(self, ticker, **kw):
        self.llamadas += 1
        m = _META.model_copy(update={"cost_usd": self.cost})
        return ResultadoAnalista(dossier=_dossier(ticker), fuentes=["https://sec.gov/a"], meta=m)


class _Bear:
    def atacar(self, dossier, **kw):
        return sc.BearAttack(meta=_META.model_copy(update={"cost_usd": 0.1}), ticker=dossier.ticker,
                             objeciones=[], replica_analista=None)


def _verif(veredicto="pass"):
    def fn(dossier, fuentes, **kw):
        return sc.VerificationReport(meta=sc.AgentMeta(agent="verificador", prompt_version="v1",
                                                       model="claude-sonnet-5-5"),
                                     ticker=dossier.ticker, veredicto=veredicto)
    return fn


def _pack(ticker): return DataPack(ticker=ticker, as_of=HOY, puntos=[])


def _orq(ledger, analista=None, verificar_fn=None, cache=None):
    return Orquestador(triage=_Triage(), analista=analista or _Analista(), bear=_Bear(),
                       ledger=ledger, verificar_fn=verificar_fn or _verif(), cache=cache,
                       data_pack_fn=_pack)


def _sen(**kw):
    base = dict(dias_desde_dossier=None, hechos_nuevos=1, dias_a_evento=None, precio_vs_tesis_pct=None)
    base.update(kw)
    return SenalesTriage(**base)


def test_flujo_feliz_analiza_bajo_presupuesto():
    an = _Analista()
    orq = _orq(LedgerPresupuesto(sobre_semanal=10.0), analista=an)
    r = orq.correr_semana([("OKLO", _sen(), "hecho"), ("NNE", _sen(), "hecho")], hoy=HOY)
    acc = [d.accion for d in r.decisiones]
    assert acc == ["analizado", "analizado"] and an.llamadas == 2
    assert r.gastado_usd > 0 and all(d.verif.veredicto == "pass" for d in r.decisiones)


def test_triage_descarta_no_llama_analista():
    an = _Analista()
    orq = Orquestador(triage=_Triage(research=False), analista=an, bear=_Bear(),
                      ledger=LedgerPresupuesto(sobre_semanal=10.0), verificar_fn=_verif(),
                      data_pack_fn=_pack)
    r = orq.correr_semana([("OKLO", _sen(), "")], hoy=HOY)
    assert r.decisiones[0].accion == "triage_descarta" and an.llamadas == 0


def test_reutiliza_dossier_vigente_sin_llamar_analista():
    an = _Analista()
    cache = CacheDossiers()
    cache.guardar("OKLO", hash_pack(_pack("OKLO")), _dossier(), _verif()( _dossier(), []), HOY)
    orq = _orq(LedgerPresupuesto(sobre_semanal=10.0), analista=an, cache=cache)
    r = orq.correr_semana([("OKLO", _sen(), "")], hoy=HOY)
    assert r.decisiones[0].accion == "reutilizado" and an.llamadas == 0


def test_corte_de_presupuesto_salta_el_segundo():
    an = _Analista(cost=0.6)
    orq = _orq(LedgerPresupuesto(sobre_semanal=1.3, reserva_eventos_pct=0.0), analista=an)
    r = orq.correr_semana([("OKLO", _sen(), "h"), ("NNE", _sen(), "h")], hoy=HOY)
    acc = [d.accion for d in r.decisiones]
    assert acc[0] == "analizado" and acc[1] == "saltado_presupuesto" and an.llamadas == 1


def test_dossier_fail_no_se_cachea():
    cache = CacheDossiers()
    orq = _orq(LedgerPresupuesto(sobre_semanal=10.0), verificar_fn=_verif("fail"), cache=cache)
    orq.correr_semana([("OKLO", _sen(), "h")], hoy=HOY)
    assert cache.vigente("OKLO", hash_pack(_pack("OKLO")), HOY) is None    # un fail no queda reusable
