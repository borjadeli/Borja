"""Escalera de add-on (doc 46): w_target, gate de add (A1-A6), regla de trim (valuación congela no vende)."""
from backend.nucleo import escalera as E


def test_w_target_escala_el_techo():
    # comercial: stage 0=25%, 1=50%, 2=75%, 3=100% del techo
    assert E.w_target(0, 0.08) == 0.02 and E.w_target(1, 0.08) == 0.04
    assert E.w_target(3, 0.08) == 0.08
    # binaria: 20% / 50%
    assert E.w_target(0, 0.08, binaria=True) == 0.08 * 0.20


def test_probe_f0_por_densidad():
    assert E.probe_f0(2, None, True) == 0.30                 # ≥2 triggers en 4Q
    assert E.probe_f0(0, 18, True) == 0.50                   # próximo a >12m
    assert E.probe_f0(0, None, False) == 1.0                 # sin trigger falsable → techo o nada


# --- gate de add: evidencia dispara, valuación vetea, precio nunca ---
def test_add_requiere_trigger():
    r = E.puede_add(trigger_cumplido=False, estado_val="COVERED", es_binaria_0a1=False,
                    margen_actual=None, margen_previo=None, w_actual=0.02, w_target_next=0.04,
                    techo=0.08, add_ons_usados=0, max_add_ons=3)
    assert r["permite"] is False and "trigger" in r["motivo"]


def test_add_valuacion_vetea():
    r = E.puede_add(trigger_cumplido=True, estado_val="NON_UNDERWRITABLE", es_binaria_0a1=False,
                    margen_actual=None, margen_previo=None, w_actual=0.02, w_target_next=0.04,
                    techo=0.08, add_ons_usados=0, max_add_ons=3)
    assert r["permite"] is False and "veto" in r["motivo"]


def test_add_margen_falsacion_deteriorado_bloquea():
    # sapo hervido: margen bajó más que la tolerancia (0.5) → no add
    r = E.puede_add(trigger_cumplido=True, estado_val="STRETCH", es_binaria_0a1=False,
                    margen_actual=2.0, margen_previo=3.0, w_actual=0.02, w_target_next=0.04,
                    techo=0.08, add_ons_usados=0, max_add_ons=3)
    assert r["permite"] is False and "sapo" in r["motivo"]


def test_add_target_no_supera_peso():
    # la suba ya llevó el peso al target → SATISFIED_BY_DRIFT
    r = E.puede_add(trigger_cumplido=True, estado_val="COVERED", es_binaria_0a1=False,
                    margen_actual=None, margen_previo=None, w_actual=0.038, w_target_next=0.04,
                    techo=0.08, add_ons_usados=0, max_add_ons=3)
    assert r["permite"] is False and "DRIFT" in r["motivo"]


def test_add_admisible():
    r = E.puede_add(trigger_cumplido=True, estado_val="COVERED", es_binaria_0a1=False,
                    margen_actual=3.0, margen_previo=3.0, w_actual=0.02, w_target_next=0.06,
                    techo=0.08, add_ons_usados=0, max_add_ons=3)
    assert r["permite"] is True


def test_binaria_option_priced_admisible_solo_0a1():
    r = E.puede_add(trigger_cumplido=True, estado_val="OPTION_PRICED", es_binaria_0a1=True,
                    margen_actual=None, margen_previo=None, w_actual=0.01, w_target_next=0.04,
                    techo=0.08, add_ons_usados=0, max_add_ons=1)
    assert r["permite"] is True


# --- TRIM: la valuación CONGELA, no vende (guarda contra cortar al ganador) ---
def test_trim_kill_por_falsacion():
    r = E.regla_trim(w_actual=0.05, cap_anchor=0.04, estado_val="STRETCH",
                     tesis_falsificada=True, supervivencia_falla=False)
    assert r["accion"] == "KILL"


def test_trim_solo_por_peso():
    # ganador: cap_anchor 4%, probe hizo +200% → 8.1% > DRIFT_LIMIT (min(2×4%,10%)=8%) → trim a 6%
    r = E.regla_trim(w_actual=0.081, cap_anchor=0.04, estado_val="NON_UNDERWRITABLE",
                     tesis_falsificada=False, supervivencia_falla=False)
    assert r["accion"] == "TRIM" and abs(r["w_objetivo"] - 0.06) < 1e-6


def test_valuacion_cara_NO_vende():
    # NON_UNDERWRITABLE por precio pero peso ≤ DRIFT_LIMIT → HOLD (congela, no vende) — NO cortar al ganador
    r = E.regla_trim(w_actual=0.03, cap_anchor=0.04, estado_val="NON_UNDERWRITABLE",
                     tesis_falsificada=False, supervivencia_falla=False)
    assert r["accion"] == "HOLD" and "no cortar al ganador" in r["motivo"]


def test_no_trim_por_ganancia():
    # +200% (peso subió de 1% a 3%) pero < DRIFT_LIMIT → NO se toca (el % de ganancia no es trigger de trim)
    r = E.regla_trim(w_actual=0.03, cap_anchor=0.04, estado_val="STRETCH",
                     tesis_falsificada=False, supervivencia_falla=False)
    assert r["accion"] == "HOLD"
