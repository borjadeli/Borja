"""Tests de los evaluadores de pilares (doc 26 v3 §3). Sin LLM."""
from backend.nucleo.evaluacion import Banda
from backend.nucleo.pilares import (
    HechosEjecucion, HechosValuacion, pilar_demanda, pilar_ejecucion,
    pilar_economia, pilar_valuacion,
)
from backend.nucleo.quality import HechosQuality


# ---- economía ----
def test_economia_fuerte():
    h = HechosQuality(margen_bruto=0.60, margen_en_expansion=True,
                      crecimiento_organico_elegible=0.30, revenue_recurrente=True,
                      hechos_comerciales_independientes=3, ventaja_estructural=True)
    p = pilar_economia(h)
    assert p.banda == Banda.FUERTE and p.confianza == "suficiente"


def test_economia_margen_negativo_es_critico():
    h = HechosQuality(margen_bruto=-0.10, crecimiento_organico_elegible=0.5)
    assert pilar_economia(h).banda == Banda.CRITICO   # unit economics rotas


def test_economia_confianza_insuficiente_si_falta_dato():
    h = HechosQuality(margen_bruto=None, crecimiento_organico_elegible=0.3)
    assert pilar_economia(h).confianza == "insuficiente"


def test_economia_tier1_es_debil_no_critico():
    h = HechosQuality(margen_bruto=0.20, crecimiento_organico_elegible=0.02)  # 0 puntos → tier 1
    assert pilar_economia(h).banda == Banda.DEBIL     # pasó el gate: débil, no crítico


# ---- demanda ----
def test_demanda_realized_en_nodo_es_fuerte():
    assert pilar_demanda(3, en_nodo=True, materialidad="ALTA").banda == Banda.FUERTE


def test_demanda_realized_sin_nodo_no_llega_a_fuerte():
    assert pilar_demanda(3, en_nodo=False, materialidad="ALTA").banda == Banda.SUFICIENTE


def test_demanda_validated_es_debil():
    assert pilar_demanda(1, en_nodo=True, materialidad="MEDIA").banda == Banda.DEBIL


def test_demanda_unknown_no_auto_vetea():
    # doc 34 §3bis (triangulado IA1+IA2): UNKNOWN = ausencia de evidencia, NO "no hay demanda".
    # Auto-vetar por ausencia (CRÍTICO) es "el peor error" (falso-negativo del retrieval con cara de
    # objetividad). UNKNOWN → DÉBIL + confianza insuficiente, NO crítico. (Target: abstención determinista.)
    p = pilar_demanda(0, en_nodo=True)
    assert p.banda == Banda.DEBIL and p.confianza == "insuficiente"
    assert p.banda != Banda.CRITICO   # no descalifica por ausencia


def test_demanda_materialidad_unknown_baja_confianza():
    # AAOI/Amazon: COMMITTED/VALIDATED pero volumen redactado → materialidad UNKNOWN
    assert pilar_demanda(1, en_nodo=True, materialidad="UNKNOWN").confianza == "insuficiente"


# ---- ejecución ----
def test_ejecucion_fuerte():
    h = HechosEjecucion(guidance_cumplido_ratio=0.75, insider_net_usd=5e6,
                        dilucion_3y=0.05, crecimiento_por_accion=0.30)
    p = pilar_ejecucion(h)
    assert p.banda == Banda.FUERTE and p.confianza == "suficiente"


def test_ejecucion_restatement_es_critico():
    h = HechosEjecucion(guidance_cumplido_ratio=1.0, dilucion_3y=0.05, restatement_reciente=True)
    assert pilar_ejecucion(h).banda == Banda.CRITICO   # integridad rota topea todo


def test_ejecucion_dilucion_masiva_sin_crecimiento_es_critico():
    # 60% de dilución en 3y y crecimiento por acción NEGATIVO → destrucción de valor por acción
    h = HechosEjecucion(guidance_cumplido_ratio=0.75, dilucion_3y=0.60, crecimiento_por_accion=-0.05)
    assert pilar_ejecucion(h).banda == Banda.CRITICO


def test_ejecucion_insider_selling_y_guidance_miss_es_debil():
    h = HechosEjecucion(guidance_cumplido_ratio=0.25, insider_net_usd=-3e6, dilucion_3y=0.20)
    assert pilar_ejecucion(h).banda == Banda.DEBIL


def test_ejecucion_confianza_insuficiente_si_falta_dato():
    assert pilar_ejecucion(HechosEjecucion(insider_net_usd=1e6)).confianza == "insuficiente"


# ---- valuación + asimetría ----
def test_valuacion_barata_con_downside_protegido_es_fuerte():
    # EV bajo vs revenue → el precio exige poco crecimiento; bear shallow → FUERTE
    h = HechosValuacion(ev_actual=300e6, revenue_ltm=100e6, multiplo_terminal=5.0,
                        bear_downside_pct=-0.15)
    assert pilar_valuacion(h).banda == Banda.FUERTE


def test_valuacion_priced_for_perfection_es_critico():
    # EV altísimo vs revenue, sin backlog ni capacidad → exige lo imposible → CRÍTICO
    h = HechosValuacion(ev_actual=3000e6, revenue_ltm=100e6, multiplo_terminal=5.0,
                        respaldo_backlog=False, bear_downside_pct=-0.40)
    assert pilar_valuacion(h).banda == Banda.CRITICO


def test_valuacion_razonable_es_suficiente():
    h = HechosValuacion(ev_actual=1000e6, revenue_ltm=100e6, multiplo_terminal=5.0,
                        bear_downside_pct=-0.40)
    assert pilar_valuacion(h).banda == Banda.SUFICIENTE


def test_valuacion_bear_dilucion_profundo_baja_la_banda():
    base = HechosValuacion(ev_actual=1000e6, revenue_ltm=100e6, multiplo_terminal=5.0)
    protegido = pilar_valuacion(HechosValuacion(**{**base.__dict__, "bear_downside_pct": -0.15}))
    profundo = pilar_valuacion(HechosValuacion(**{**base.__dict__, "bear_downside_pct": -0.70}))
    assert profundo.banda < protegido.banda    # el downside por dilución empeora la asimetría


def test_valuacion_falta_input_es_insuficiente():
    assert pilar_valuacion(HechosValuacion(ev_actual=1000e6)).confianza == "insuficiente"


def test_pilar_ejecucion_sbc_alto_penaliza():
    from backend.nucleo.pilares import pilar_ejecucion, HechosEjecucion
    alto = pilar_ejecucion(HechosEjecucion(dilucion_3y=0.05, sbc_pct_revenue=0.30))   # SBC 30% → −1
    bajo = pilar_ejecucion(HechosEjecucion(dilucion_3y=0.05, sbc_pct_revenue=0.02))   # SBC 2% → +1
    assert "SBC 30%" in str(alto.hechos) and "silenciosa alta" in str(alto.hechos)
    assert "SBC 2%" in str(bajo.hechos)
