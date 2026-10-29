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
    # sobre para UN nombre (peor-caso ≈ $1.38/nombre con max_tokens 16384) pero no dos → el 2º se salta.
    orq = _orq(LedgerPresupuesto(sobre_semanal=2.0, reserva_eventos_pct=0.0), analista=an)
    r = orq.correr_semana([("OKLO", _sen(), "h"), ("NNE", _sen(), "h")], hoy=HOY)
    acc = [d.accion for d in r.decisiones]
    assert acc[0] == "analizado" and acc[1] == "saltado_presupuesto" and an.llamadas == 1


def test_dossier_fail_no_se_cachea():
    cache = CacheDossiers()
    orq = _orq(LedgerPresupuesto(sobre_semanal=10.0), verificar_fn=_verif("fail"), cache=cache)
    orq.correr_semana([("OKLO", _sen(), "h")], hoy=HOY)
    assert cache.vigente("OKLO", hash_pack(_pack("OKLO")), HOY) is None    # un fail no queda reusable


# --------------------------------------------------------------------------- regresión P0.2 (auditoría)
from backend.agentes.provenance import DataKind, DataPoint, Source  # noqa: E402

_SRC = Source(name="Yahoo", document_type="api")


def _dp(metric, value, known):
    return DataPoint(entity="OKLO", metric=metric, value=value, unit="u", currency="USD",
                     kind=DataKind.ORIGINAL, source=_SRC, known_at=date.fromisoformat(known))


def test_2a_hash_ignora_volatiles_pero_no_materiales():
    # precio/ADV/shares distintos → MISMO hash (no invalidan el dossier)
    volatil_a = DataPack(ticker="OKLO", as_of=date(2026, 10, 20),
                         puntos=[_dp("precio", 50.0, "2026-10-20"), _dp("shares_outstanding", 1e8, "2026-10-20")])
    volatil_b = DataPack(ticker="OKLO", as_of=date(2026, 10, 21),
                         puntos=[_dp("precio", 99.0, "2026-10-21"), _dp("shares_outstanding", 2e8, "2026-10-21")])
    assert hash_pack(volatil_a) == hash_pack(volatil_b)
    # un dato MATERIAL nuevo (otro known_at) SÍ cambia el hash
    mat_a = DataPack(ticker="OKLO", as_of=date(2026, 10, 20), puntos=[_dp("owner_fcf", 10.0, "2026-06-30")])
    mat_b = DataPack(ticker="OKLO", as_of=date(2026, 10, 20), puntos=[_dp("owner_fcf", 10.0, "2026-09-30")])
    assert hash_pack(mat_a) != hash_pack(mat_b)


def test_2b_cache_persiste_a_disco(tmp_path):
    ruta = tmp_path / "cache.json"
    c1 = CacheDossiers(path=ruta)
    c1.guardar("OKLO", "h1", _dossier(), _verif_pass(), date(2026, 10, 26))
    # un cache NUEVO sobre el mismo archivo ve el dossier (sobrevive al reinicio del proceso)
    c2 = CacheDossiers(path=ruta)
    assert c2.vigente("OKLO", "h1", date(2026, 10, 27)) is not None
    assert c2.vigente("OKLO", "OTRO_HASH", date(2026, 10, 27)) is None   # hash distinto → no reutiliza


def _verif_pass():
    return sc.VerificationReport(meta=_META, ticker="OKLO", veredicto="pass")


# --------------------------------------------------------------------------- regresión P0.3 (auditoría)

def test_3_cupo_de_cobertura_promueve_un_nombre_nuevo():
    an = _Analista()
    orq = Orquestador(triage=_Triage(research=False), analista=an, bear=_Bear(),
                      ledger=LedgerPresupuesto(sobre_semanal=10.0), verificar_fn=_verif(), data_pack_fn=_pack)
    # sin cupo → el nombre nuevo se descarta (prioridad 1 < 2)
    assert orq.correr_semana([("NUEVA", _sen(), "")], hoy=HOY).decisiones[0].accion == "triage_descarta"
    assert an.llamadas == 0
    # con cupo=1 → se promueve y se analiza
    r = orq.correr_semana([("NUEVA", _sen(), "")], hoy=HOY, cupo_cobertura=1)
    assert r.decisiones[0].accion == "analizado" and an.llamadas == 1


def test_3_cupo_ordena_por_prioridad_de_cuello():
    an = _Analista()
    orq = Orquestador(triage=_Triage(research=False), analista=an, bear=_Bear(),
                      ledger=LedgerPresupuesto(sobre_semanal=10.0), verificar_fn=_verif(), data_pack_fn=_pack)
    # dos nuevos, cupo 1 → entra el de cuello más prioritario (B)
    r = orq.correr_semana([("A", _sen(prioridad_cuello=1), ""), ("B", _sen(prioridad_cuello=3), "")],
                          hoy=HOY, cupo_cobertura=1)
    analizados = [d.ticker for d in r.decisiones if d.accion == "analizado"]
    assert analizados == ["B"]


def test_3_bootstrap_promueve_todos_los_nuevos():
    an = _Analista()
    orq = Orquestador(triage=_Triage(research=False), analista=an, bear=_Bear(),
                      ledger=LedgerPresupuesto(sobre_semanal=10.0), verificar_fn=_verif(), data_pack_fn=_pack)
    r = orq.correr_semana([("A", _sen(), ""), ("B", _sen(), "")], hoy=HOY, bootstrap=True)
    assert sorted(d.accion for d in r.decisiones) == ["analizado", "analizado"]


def test_3_evento_fuerte_saltea_el_cache(tmp_path):
    an = _Analista()
    cache = CacheDossiers()
    cache.guardar("OKLO", hash_pack(_pack("OKLO")), _dossier(), _verif()(_dossier(), []), HOY)
    orq = _orq(LedgerPresupuesto(sobre_semanal=10.0), analista=an, cache=cache)
    # con evento fuerte NO reutiliza: re-analiza (el dossier vigente pudo quedar viejo por el evento)
    r = orq.correr_semana([("OKLO", _sen(tiene_evento_fuerte=True), "h")], hoy=HOY)
    assert r.decisiones[0].accion == "analizado" and an.llamadas == 1


def test_falla_en_un_nombre_no_tumba_el_ciclo():
    # resiliencia (smoke #6): si el análisis de un nombre explota, se saltea y el ciclo sigue con el resto.
    class _AnalistaRompe:
        def __init__(self): self.llamadas = 0
        def analizar(self, ticker, **kw):
            self.llamadas += 1
            if ticker == "BOOM":
                raise RuntimeError("dossier inválido (sin falsador)")
            return ResultadoAnalista(dossier=_dossier(ticker), fuentes=["https://sec.gov/a"],
                                     meta=_META.model_copy(update={"cost_usd": 0.5}))
    orq = Orquestador(triage=_Triage(), analista=_AnalistaRompe(), bear=_Bear(),
                      ledger=LedgerPresupuesto(sobre_semanal=10.0), verificar_fn=_verif(), data_pack_fn=_pack)
    r = orq.correr_semana([("BOOM", _sen(), "h"), ("OKLO", _sen(), "h")], hoy=HOY)
    acc = {d.ticker: d.accion for d in r.decisiones}
    assert acc["BOOM"] == "error_analisis" and acc["OKLO"] == "analizado"


def test_r3_hash_ignora_derivadas_volatiles():
    # r3 #4: el hash NO debe cambiar si una métrica DERIVED (dilucion_12m_pct, que depende de shares Yahoo)
    # varía; solo los ORIGINAL materiales cuentan.
    from backend.agentes.provenance import DataKind, DataPoint, Source
    src = Source(name="x")
    def _pk(dil):
        return DataPack(ticker="OKLO", as_of=HOY, puntos=[
            DataPoint(entity="OKLO", metric="cash", value=1e9, unit="USD", kind=DataKind.ORIGINAL,
                      source=src, known_at=HOY),
            DataPoint(entity="OKLO", metric="dilucion_12m_pct", value=dil, unit="pct",
                      kind=DataKind.DERIVED, source=src, known_at=HOY)])
    assert hash_pack(_pk(19.0)) == hash_pack(_pk(19.3))
