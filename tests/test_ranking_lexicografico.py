"""Ranking lexicográfico (doc 27 §10 / doc 34 §6) — el orden estricto sin score cardinal.

Verifica que cada clave desempata SOLO cuando las anteriores empatan, y que el gate manda.
"""
from backend.nucleo.ranking_lexicografico import (
    CandidatoLex, clave_lexicografica, elegibles_ordenados, rankear_lexicografico,
)


def _c(ticker, **kw):
    base = dict(elegible=True, valuacion_ok=True, tier_capital="A", cobertura=0.5,
                asimetria_operable=1.0, catalizador=False, liquidez_adv=1e6)
    base.update(kw)
    return CandidatoLex(ticker=ticker, **base)


def test_gate_manda_sobre_todo():
    # un gate-fail con tier A + asimetría enorme va DESPUÉS de un gate-ok tier C mediocre
    bueno_gate = _c("OK", tier_capital="C", asimetria_operable=0.1)
    fail_gate = _c("FAIL", elegible=False, tier_capital="A", asimetria_operable=5.0)
    orden = rankear_lexicografico([fail_gate, bueno_gate])
    assert [c.ticker for c in orden] == ["OK", "FAIL"]


def test_valuacion_gate_tambien_manda():
    ok = _c("OK", tier_capital="B")
    ya_priceada = _c("PRICED", valuacion_ok=False, tier_capital="A", asimetria_operable=5.0)
    assert rankear_lexicografico([ya_priceada, ok])[0].ticker == "OK"


def test_tier_desempata_antes_que_asimetria():
    # tier A con asimetría baja gana a tier B con asimetría alta (tier va antes)
    a = _c("A_baja", tier_capital="A", asimetria_operable=0.2)
    b = _c("B_alta", tier_capital="B", asimetria_operable=5.0)
    assert rankear_lexicografico([b, a])[0].ticker == "A_baja"


def test_cobertura_desempata_dentro_del_tier():
    alta = _c("cov_alta", cobertura=0.9, asimetria_operable=0.1)
    baja = _c("cov_baja", cobertura=0.3, asimetria_operable=5.0)   # misma tier
    assert rankear_lexicografico([baja, alta])[0].ticker == "cov_alta"


def test_asimetria_desempata_con_todo_lo_anterior_igual():
    alta = _c("asim_alta", asimetria_operable=3.0)
    baja = _c("asim_baja", asimetria_operable=0.5)
    assert rankear_lexicografico([baja, alta])[0].ticker == "asim_alta"


def test_asimetria_capada_a_5x():
    # 8× y 5× empatan tras el cap → desempata la siguiente clave (catalizador)
    ocho = _c("ocho", asimetria_operable=8.0, catalizador=False)
    cinco_cat = _c("cinco_cat", asimetria_operable=5.0, catalizador=True)
    assert rankear_lexicografico([ocho, cinco_cat])[0].ticker == "cinco_cat"


def test_catalizador_y_liquidez_ultimos_desempates():
    con_cat = _c("con_cat", catalizador=True, liquidez_adv=1e5)
    sin_cat = _c("sin_cat", catalizador=False, liquidez_adv=1e9)
    assert rankear_lexicografico([sin_cat, con_cat])[0].ticker == "con_cat"    # catalizador antes que liquidez
    # con catalizador igual, desempata liquidez
    liq_alta = _c("liq_alta", catalizador=True, liquidez_adv=1e9)
    liq_baja = _c("liq_baja", catalizador=True, liquidez_adv=1e5)
    assert rankear_lexicografico([liq_baja, liq_alta])[0].ticker == "liq_alta"


def test_asimetria_none_es_lo_peor():
    con = _c("con", asimetria_operable=0.1)
    sin = _c("sin", asimetria_operable=None)
    assert rankear_lexicografico([sin, con])[0].ticker == "con"


def test_elegibles_ordenados_filtra_gate_fail():
    ok = _c("OK")
    fail = _c("FAIL", valuacion_ok=False)
    res = elegibles_ordenados([ok, fail])
    assert [c.ticker for c in res] == ["OK"]


def test_no_hay_score_cardinal():
    # la clave es una tupla ordinal, no un número único
    assert isinstance(clave_lexicografica(_c("X")), tuple)


# --- candidato_desde: mapea las dos superficies reales (elegibilidad + números) ---
from types import SimpleNamespace


def _ev(tier="A", ticker="X"):
    return SimpleNamespace(ticker=ticker, tier=tier)


def _hoja(ya_priceado=False, capital_risk_tier="A", asim=1.5):
    return SimpleNamespace(falsador_ya_priceado=ya_priceado, capital_risk_tier=capital_risk_tier,
                           asimetria_operable=asim)


def test_candidato_desde_mapea_gates_y_numeros():
    from backend.nucleo.ranking_lexicografico import candidato_desde
    c = candidato_desde(_ev(tier="B"), _hoja(ya_priceado=False, capital_risk_tier="B", asim=2.0),
                        cobertura=0.7, liquidez_adv=5e6, catalizador=True)
    assert c.ticker == "X" and c.elegible is True and c.valuacion_ok is True
    assert c.tier_capital == "B" and c.cobertura == 0.7 and c.asimetria_operable == 2.0
    assert c.catalizador is True and c.liquidez_adv == 5e6


def test_candidato_desde_tier_C_no_elegible():
    from backend.nucleo.ranking_lexicografico import candidato_desde
    c = candidato_desde(_ev(tier="C"), _hoja(), cobertura=0.5)
    assert c.elegible is False and c.gate_ok is False


def test_candidato_desde_falsador_ya_priceado_se_queda_chico():
    # FIX 2026-08-18: ya-priceada NO expulsa del libro duro — la achica a OPTION_PRICED (RKLB = HARD/OPTION_PRICED)
    from backend.nucleo.ranking_lexicografico import candidato_desde
    c = candidato_desde(_ev(tier="A"), _hoja(ya_priceado=True), cobertura=0.5)
    assert c.valuacion_ok is True and c.gate_ok is True      # SIGUE en el libro duro
    assert c.estado_valuacion == "OPTION_PRICED" and c.cap == 0.02   # pero chica (piso), no en el carril


def test_candidato_desde_capital_tier_NA_va_a_A():
    from backend.nucleo.ranking_lexicografico import candidato_desde
    c = candidato_desde(_ev(), _hoja(capital_risk_tier="NA"), cobertura=0.5)
    assert c.tier_capital == "A"   # cash-generative / NA → riesgo de capital bajo


def _hoja2(route="FCFE_OPERABLE", ya_priceado=False, price_anchor="NA", capital_risk_tier="A",
           asim=1.0, burden_gp=None, veredicto=""):
    return SimpleNamespace(falsador_ya_priceado=ya_priceado, capital_risk_tier=capital_risk_tier,
                           asimetria_operable=asim, route=route, price_anchor_status=price_anchor,
                           burden_gp=burden_gp, falsador_veredicto=veredicto)


def test_gate_falsador_evaluable_ya_priceado_es_option_priced_no_expulsa():
    # el falsador evaluable + ya-priceada (cualquier route) → OPTION_PRICED (chico, EN el duro), NO expulsión (fix 2026-08-18)
    from backend.nucleo.ranking_lexicografico import candidato_desde
    c = candidato_desde(_ev(), _hoja2(route="CASH_POSITIVE", ya_priceado=True, veredicto="ya paga el bull",
                                      price_anchor="ANCHORED"), cobertura=0.5)
    assert c.valuacion_ok is True and c.estado_valuacion == "OPTION_PRICED"   # se queda chica, no al carril


def test_gate_no_evaluable_usa_anchor_pure_option_fuera():
    from backend.nucleo.ranking_lexicografico import candidato_desde
    c = candidato_desde(_ev(), _hoja2(route="NON_FCFE", price_anchor="PURE_OPTION", veredicto="no_evaluable"),
                        cobertura=0.5)
    assert c.valuacion_ok is False   # falsador no_evaluable + pura opción → fuera


def test_gate_no_evaluable_anchored_pasa_aunque_ya_priceado():
    # falsador no_evaluable → NO manda; manda el anchor. ANCHORED → pasa (caso LEU).
    from backend.nucleo.ranking_lexicografico import candidato_desde
    c = candidato_desde(_ev(), _hoja2(route="NON_FCFE", price_anchor="ANCHORED", ya_priceado=True,
                                      veredicto="no_evaluable"), cobertura=0.5)
    assert c.valuacion_ok is True


def test_politica_cap_tier_capital():
    from backend.nucleo import politica
    assert politica.cap_tier_capital("A") == 0.08
    assert politica.cap_tier_capital("B") == 0.05
    assert politica.cap_tier_capital("C") == 0.025
    assert politica.cap_tier_capital("Z") == 0.025   # desconocido → C (conservador)


def test_cap_es_min_arquetipo_y_tier():
    from backend.nucleo.ranking_lexicografico import candidato_desde
    ev = SimpleNamespace(ticker="X", tier="A", hard_cap=0.27)   # cap arquetipo×fragility (Tracción frag0)
    assert candidato_desde(ev, _hoja2(capital_risk_tier="B"), cobertura=0.5).cap == 0.05   # min(0.27, 0.05)
    assert candidato_desde(ev, _hoja2(capital_risk_tier="A"), cobertura=0.5).cap == 0.08   # min(0.27, 0.08)


# --- Eje VALUACIÓN → tamaño: 4 estados + cap_valuacion (doc 34 §3ter) ---

def test_estado_valuacion_por_burden_bandas():
    from backend.nucleo import politica
    assert politica.estado_valuacion_por_burden(None) == "NON_UNDERWRITABLE"
    assert politica.estado_valuacion_por_burden(2.0) == "COVERED"      # ≤3
    assert politica.estado_valuacion_por_burden(8.0) == "STRETCH"      # 3<b≤12
    assert politica.estado_valuacion_por_burden(20.0) == "OPTION_PRICED"  # >12


def test_cap_valuacion_mapeo():
    from backend.nucleo import politica
    assert politica.cap_valuacion("COVERED") == 1.0
    assert politica.cap_valuacion("STRETCH") == 0.04
    assert politica.cap_valuacion("OPTION_PRICED") == 0.02
    assert politica.cap_valuacion("NON_UNDERWRITABLE") == 0.0
    assert politica.cap_valuacion("???") == 0.02   # desconocido → OPTION_PRICED (conservador)


def test_fcfe_gate_passer_es_covered_no_liga():
    # FCFE que pasa el gate → COVERED → cap_valuacion 1.0 no restringe (liga tier/arquetipo)
    from backend.nucleo.ranking_lexicografico import candidato_desde
    ev = SimpleNamespace(ticker="X", tier="A", hard_cap=0.27)
    c = candidato_desde(ev, _hoja2(route="FCFE_OPERABLE", capital_risk_tier="A"), cobertura=0.5)
    assert c.estado_valuacion == "COVERED" and c.cap == 0.08 and c.cap_reason == "tier"


def test_non_fcfe_burden_alto_es_option_priced_y_va_al_piso():
    # ACEPTACIÓN 2-ejes (RKLB/LEU): mejor evidencia (pasa gate) PERO precio-optionality → OPTION_PRICED → piso 2%.
    from backend.nucleo.ranking_lexicografico import candidato_desde
    ev = SimpleNamespace(ticker="RBRKish", tier="A", hard_cap=0.27)
    hoja = _hoja2(route="NON_FCFE", price_anchor="ANCHORED", veredicto="no_evaluable", burden_gp=53.0)
    c = candidato_desde(ev, hoja, cobertura=0.6)
    assert c.gate_ok is True                       # en el LIBRO DURO (evidencia OK)
    assert c.estado_valuacion == "OPTION_PRICED"   # pero el PRECIO exige opcionalidad
    assert c.cap == 0.02 and c.cap_reason == "valuacion"   # → piso, ligado por valuación (no por tier)


def test_non_fcfe_burden_medio_es_stretch():
    from backend.nucleo.ranking_lexicografico import candidato_desde
    ev = SimpleNamespace(ticker="Y", tier="A", hard_cap=0.27)
    hoja = _hoja2(route="NON_FCFE", price_anchor="ANCHORED", veredicto="no_evaluable", burden_gp=8.0)
    c = candidato_desde(ev, hoja, cobertura=0.6)
    assert c.estado_valuacion == "STRETCH" and c.cap == 0.04 and c.cap_reason == "valuacion"


def test_clasificacion_2ejes_hard_evidence_option_priced():
    # RKLB: en el libro duro (gate ok) pero piso por precio (OPTION_PRICED) — los dos ejes ortogonales
    from backend.nucleo.ranking_lexicografico import clasificacion_2ejes
    c = _c("RKLB", estado_valuacion="OPTION_PRICED")   # gate_ok True por default (_c elegible+valuacion_ok)
    cl = clasificacion_2ejes(c)
    assert cl["etiqueta"] == "HARD_EVIDENCE / OPTION_PRICED"


def test_clasificacion_2ejes_abstenido_es_investigacion():
    from backend.nucleo.ranking_lexicografico import clasificacion_2ejes
    c = _c("X", abstenido=True, estado_valuacion="COVERED")
    assert clasificacion_2ejes(c)["eje_evidencia"] == "INVESTIGACION"


def test_clasificacion_2ejes_elegible_pero_valuacion_reject_es_carril():
    # elegible (3 pilares OK) pero valuación lo saca → opcionalidad → CARRIL (no descarte, no cash)
    from backend.nucleo.ranking_lexicografico import clasificacion_2ejes
    c = _c("X", elegible=True, valuacion_ok=False, estado_valuacion="OPTION_PRICED")
    assert clasificacion_2ejes(c)["eje_evidencia"] == "CARRIL"


def test_clasificacion_2ejes_no_elegible_es_descarte():
    from backend.nucleo.ranking_lexicografico import clasificacion_2ejes
    c = _c("X", elegible=False, valuacion_ok=True, estado_valuacion="COVERED")
    assert clasificacion_2ejes(c)["eje_evidencia"] == "DESCARTE"


# --- ranking por CELDA + llave económica local (doc 34 §3bis) ---

def test_clave_economica_fcfe_por_asimetria():
    from backend.nucleo.ranking_lexicografico import clave_economica_local
    alta = _c("a", route="FCFE_OPERABLE", asimetria_operable=3.0)
    baja = _c("b", route="FCFE_OPERABLE", asimetria_operable=0.5)
    assert clave_economica_local(alta) < clave_economica_local(baja)   # más asimetría = menor clave = mejor


def test_clave_economica_pre_revenue_runway_antes_que_burden():
    from backend.nucleo.ranking_lexicografico import clave_economica_local
    r_alto = _c("ra", route="NON_FCFE", runway=5.0, burden=100)       # más runway gana
    r_bajo = _c("rb", route="NON_FCFE", runway=1.0, burden=10)
    assert clave_economica_local(r_alto) < clave_economica_local(r_bajo)


def test_rankear_por_celda_agrupa_arquetipo_x_tier():
    from backend.nucleo.ranking_lexicografico import rankear_por_celda
    cands = [_c("X", arquetipo="Growth", tier_capital="A"),
             _c("Y", arquetipo="Pre-revenue", tier_capital="B"),
             _c("Z", arquetipo="Growth", tier_capital="A")]
    celdas = rankear_por_celda(cands)
    assert set(celdas) == {("Growth", "A"), ("Pre-revenue", "B")}
    assert len(celdas[("Growth", "A")]) == 2


def test_rankear_por_celda_excluye_gate_fail():
    from backend.nucleo.ranking_lexicografico import rankear_por_celda
    cands = [_c("OK", arquetipo="Growth", tier_capital="A"),
             _c("FAIL", arquetipo="Growth", tier_capital="A", valuacion_ok=False)]
    celdas = rankear_por_celda(cands)
    assert [c.ticker for c in celdas[("Growth", "A")]] == ["OK"]


def test_cola_operativa_tier_A_antes_de_B():
    from backend.nucleo.ranking_lexicografico import rankear_por_celda, cola_operativa
    cands = [_c("B1", arquetipo="Growth", tier_capital="B"),
             _c("A1", arquetipo="Pre-revenue", tier_capital="A")]
    cola = cola_operativa(rankear_por_celda(cands))
    assert [c.ticker for c in cola] == ["A1", "B1"]   # el prefijo TIER manda (A antes que B)


# --- ABSTENCIÓN (doc 34 §3bis): evidencia insuficiente → no se decide, va a cola de investigación ---

def test_candidato_abstiene_por_cobertura_baja():
    from backend.nucleo.ranking_lexicografico import candidato_desde
    c = candidato_desde(_ev(), _hoja2(), cobertura=0.05)   # < umbral 0.10
    assert c.abstenido is True and c.gate_ok is False and "cobertura" in c.motivo_abstencion


def test_candidato_no_abstiene_con_cobertura_ok():
    from backend.nucleo.ranking_lexicografico import candidato_desde
    assert candidato_desde(_ev(), _hoja2(), cobertura=0.5).abstenido is False


def test_abstenido_excluido_del_ranking_por_celda():
    from backend.nucleo.ranking_lexicografico import rankear_por_celda
    ok = _c("OK", arquetipo="Growth", tier_capital="A")
    abst = _c("ABST", arquetipo="Growth", tier_capital="A", abstenido=True)
    celdas = rankear_por_celda([ok, abst])
    assert [c.ticker for c in celdas[("Growth", "A")]] == ["OK"]   # el abstenido NO entra al libro


def test_cola_investigacion_y_tasa_abstencion():
    from backend.nucleo.ranking_lexicografico import cola_investigacion, tasa_abstencion
    cands = [_c("A"), _c("B", abstenido=True), _c("C", abstenido=True)]
    assert [c.ticker for c in cola_investigacion(cands)] == ["B", "C"]
    assert tasa_abstencion(cands) == round(2 / 3, 3)


# --- 4 estados de decisión (doc 39 §2.7, Bloque 1.5) ---
def test_estado_decision_cuatro():
    from backend.nucleo.ranking_lexicografico import estado_decision
    # UNDERWRITTEN: elegible + evidencia + underwritable
    assert estado_decision(_c("A", elegible=True, valuacion_ok=True, estado_valuacion="COVERED")) == "UNDERWRITTEN"
    # PROBE: elegible pero NON_UNDERWRITABLE (opcionalidad)
    assert estado_decision(_c("B", elegible=True, valuacion_ok=False, estado_valuacion="NON_UNDERWRITABLE")) == "PROBE"
    # WATCH: abstenido (evidencia insuficiente)
    assert estado_decision(_c("C", elegible=True, abstenido=True)) == "WATCH"
    # REJECT: no elegible (veto de supervivencia)
    assert estado_decision(_c("D", elegible=False)) == "REJECT"


def test_estado_decision_reject_manda_sobre_abstencion():
    from backend.nucleo.ranking_lexicografico import estado_decision
    # no elegible (veto) tiene precedencia sobre abstención
    assert estado_decision(_c("X", elegible=False, abstenido=True)) == "REJECT"


# --- Guarda: veto-fact de supervivencia NO extraído ⇒ abstención (lección SYM 2026-08-31) ---
def test_guarda_veto_facts_incompletos_abstiene():
    """Un nombre con restatement NO extraído (veto_facts_completos=False) NO puede underwrite ni probe,
    aunque la cobertura agregada sea alta: se abstiene (WATCH) hasta tener el veto-fact. Ausencia de dato
    ≠ ausencia de veto — el bug que dejó a SYM (material weakness) salir COVERED/underwritable."""
    from backend.nucleo.ranking_lexicografico import candidato_desde, estado_decision

    class _EV:
        ticker = "SYM"; tier = "A"; arquetipo = "Madura"; hard_cap = 0.25
        veto_supervivencia = False; veto_facts_completos = False

    class _HOJA:
        ticker = "SYM"; capital_risk_tier = "A"; route = "FCFE_OPERABLE"
        price_anchor_status = "NA"; burden_gp = None; falsador_ya_priceado = False
        falsador_veredicto = "ok"; asimetria_operable = 2.0; revenue_ttm = 500e6
        estado_reverse = "COVERED"; estado_ruteo = "MADURO"; runway_anos = 10

    c = candidato_desde(_EV(), _HOJA(), cobertura=0.95)   # cobertura ALTA a propósito
    assert c.abstenido is True
    assert estado_decision(c) == "WATCH"                  # NO underwritten pese a cobertura 95%
    assert "restatement" in c.motivo_abstencion

    _EV.veto_facts_completos = True                       # con el veto-fact extraído → underwrite
    c2 = candidato_desde(_EV(), _HOJA(), cobertura=0.95)
    assert c2.abstenido is False
    assert estado_decision(c2) == "UNDERWRITTEN"
