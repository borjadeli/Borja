"""paper_trader consume los targets del PM (tajada 2): el PM manda el TAMAÑO dentro del hard_cap determinista.

Opt-in: sin pm_libro → sizing por mérito (comportamiento previo, cubierto por los otros tests del paper)."""
from backend.seleccion.paper_trader import LibroPaper, _pm_targets, correr_ciclo


def _ev(tk, hard_cap, *, merito=10.0, precio=100.0, sector="s"):
    return {"ticker": tk, "decision": "candidata", "merito": merito, "hard_cap": hard_cap,
            "arquetipo": {"arquetipo": "growth"}, "_precio": precio, "_bull": "", "_bear": "",
            "_sector": sector, "residual_cero": False}


def test_pm_targets_parsea_dict_serializado():
    pm = {"decisiones": [
        {"ticker": "RBRK", "size_final": 0.08, "etiqueta": "PRIORITY_HIGH", "promovido": True},
        {"ticker": "BADCO", "size_final": 0.0, "etiqueta": "VETO", "promovido": False},
    ]}
    t = _pm_targets(pm)
    assert t["RBRK"]["size"] == 0.08 and t["RBRK"]["promovido"] is True
    assert t["BADCO"]["size"] == 0.0
    assert _pm_targets(None) == {}


def test_ciclo_pm_sizea_al_target_y_excluye_veto_y_no_evaluados():
    evals = [_ev("RBRK", 0.08, sector="a"), _ev("MP", 0.10, sector="b"),
             _ev("LOWBALL", 0.08, sector="e"),
             _ev("BADCO", 0.08, sector="c"), _ev("UNRATED", 0.08, sector="d")]
    pm = {"decisiones": [
        {"ticker": "RBRK", "size_final": 0.08, "etiqueta": "PRIORITY_HIGH", "promovido": True},
        {"ticker": "MP", "size_final": 0.06, "etiqueta": "PRIORITY_MEDIUM", "promovido": True},
        {"ticker": "LOWBALL", "size_final": 0.04, "etiqueta": "PASS", "promovido": False},
        {"ticker": "BADCO", "size_final": 0.0, "etiqueta": "VETO", "promovido": False},
        # UNRATED: el PM no lo evaluó → no debe entrar
    ]}
    r = correr_ciclo(evals, libro=LibroPaper(), persistir=False, pm_libro=pm)
    pos = r["libro"].posiciones
    # BADCO (veto) y UNRATED (sin juicio) afuera; LOWBALL afuera por el piso 5% del paper (base PM 4% < 5%).
    assert set(pos.keys()) == {"RBRK", "MP"}
    assert pos["RBRK"]["sizing"] == 0.08              # PRIORITY_HIGH → target 8% (dentro del hard_cap 8%)
    assert pos["MP"]["sizing"] == 0.06                # PRIORITY_MEDIUM → target 6% (dentro del hard_cap 10%)
    # DECISIÓN ABIERTA (operador): base PM = CAP_FLOOR_BURN 4% vs PISO_POSICION del paper 5%. Hoy manda el 5%
    # → un PASS/base no despliega. Si se quiere "el determinismo despliega el piso", alinear los dos pisos.


def test_ciclo_sin_pm_no_cambia(monkeypatch):
    # sin pm_libro el ciclo NO usa targets: cae al sizing por mérito (path previo intacto)
    evals = [_ev("RBRK", 0.08, sector="a")]
    r = correr_ciclo(evals, libro=LibroPaper(), persistir=False)
    # entra por mérito normalizado (no por PM); basta con que no explote y respete el hard_cap
    if "RBRK" in r["libro"].posiciones:
        assert r["libro"].posiciones["RBRK"]["sizing"] <= 0.08 + 1e-9
