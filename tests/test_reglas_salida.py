"""Reglas de salida (doc 85 F2): tier A/B/C deterministas, solo sobre posiciones."""
from backend.agentes.event_monitor import EventoClasificado
from backend.agentes.reglas_salida import evaluar_reglas_salida


def _ev(tk, items, tier="DURO", accn="a1"):
    return EventoClasificado(ticker=tk, tipo="8-K", tier=tier, items=items, fecha="2026-11-10", accession=accn)


def test_tier_A_quiebra_en_posicion_salida_total():
    ev = [_ev("WOLF", ["1.03"]), _ev("MP", ["4.02", "9.01"])]
    acc = evaluar_reglas_salida(ev, posiciones={"WOLF", "MP"})
    d = {a.ticker: a for a in acc}
    assert d["WOLF"].accion == "SALIDA_TOTAL" and d["WOLF"].tier == "A"
    assert d["MP"].accion == "SALIDA_TOTAL" and "non-reliance" in d["MP"].motivo


def test_solo_posiciones():
    # un DURO en un nombre que NO se tiene → no genera acción (lo que no se tiene, no se vende)
    acc = evaluar_reglas_salida([_ev("XYZ", ["1.03"])], posiciones={"WOLF"})
    assert acc == []


def test_tier_C_5_02_despierta_sin_afirmar_salida():
    # P0.3 (doc 91): el 5.02 DESPIERTA al PM, pero la etiqueta NO afirma "salida de CEO/CFO" (cubre también
    # nombramientos y compensación — el 5.02 de IESC era PSUs). Sin cuerpo del 8-K no se asume una salida.
    acc = evaluar_reglas_salida([_ev("EXE", ["5.02"], tier="REVISION")], posiciones={"EXE"})
    assert acc[0].accion == "DESPERTAR" and acc[0].tier == "C"
    assert "salida de CEO/CFO" not in acc[0].motivo and "verificar" in acc[0].motivo


def test_tier_B_falsador_duro_despierta_no_auto_vende():
    # r10: un falsador DURO cumplido NO auto-vende — DESPIERTA al PM (él + Auditor deciden). Determinismo al mínimo.
    acc = evaluar_reglas_salida([], posiciones={"OKLO"},
                                falsadores_confirmados={"OKLO": [{"id": "aurora_2028", "tipo": "DURO",
                                                                  "consecuencia": "SALIDA", "estado": "CONFIRMED"}]})
    assert acc[0].accion == "DESPERTAR" and acc[0].tier == "B" and "aurora_2028" in acc[0].motivo


def test_ordena_A_antes_que_C_y_dedup():
    ev = [_ev("MP", ["5.02"], tier="REVISION"), _ev("MP", ["1.03"]), _ev("MP", ["1.03"], accn="a2")]
    acc = evaluar_reglas_salida(ev, posiciones={"MP"})
    assert acc[0].tier == "A"                      # tier A primero
    assert len([a for a in acc if a.accion == "SALIDA_TOTAL"]) == 1   # dedup del 1.03 repetido


def test_pesos_tras_salidas():
    from backend.agentes.reglas_salida import AccionSalida, pesos_tras_salidas
    pesos = {"WOLF": 0.10, "MP": 0.08, "OKLO": 0.05}
    salidas = [AccionSalida("WOLF", "A", "SALIDA_TOTAL", "quiebra"),
               AccionSalida("MP", "B", "RECORTE_50", "falsador DURO"),
               AccionSalida("OKLO", "C", "DESPERTAR", "salida CEO")]
    out = pesos_tras_salidas(pesos, salidas)
    assert "WOLF" not in out                        # salida total → 0 (sacado)
    assert abs(out["MP"] - 0.04) < 1e-9             # recorte 50%
    assert out["OKLO"] == 0.05                      # DESPERTAR no toca el peso (lo decide el PM)
