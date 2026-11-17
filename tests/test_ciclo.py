"""run_cycle (doc 85): encadenado + decisión de despertar al PM."""
from backend.agentes.ciclo import correr_ciclo, razones_despertar
from backend.agentes.reglas_salida import AccionSalida


def test_razones_despertar():
    r = razones_despertar(
        cambios_zona=[{"ticker": "MP", "zona": "COMPRA"}, {"ticker": "OKLO", "zona": "RECORTE"},
                      {"ticker": "VST", "zona": "MANTENER"}],
        deeps_hechos=[{"ticker": "RXRX", "zona": "COMPRA"}, {"ticker": "ACHR", "zona": "SALIDA"}],
        salidas=[AccionSalida("WOLF", "A", "SALIDA_TOTAL", "quiebra")])
    assert "MP entró a COMPRA" in r and "OKLO entró a RECORTE" in r
    assert "VST" not in " ".join(r)                         # MANTENER no despierta
    assert "deep de RXRX → COMPRA" in r                      # ACHR→SALIDA no (solo COMPRA del deep despierta)
    assert any("tier A" in x and "WOLF" in x for x in r)


def test_ciclo_encadena_y_despierta_con_motivo():
    orden = []
    def _poller():
        orden.append("poller"); return {"en_revision": ["VST"], "salidas": []}
    def _latido():
        orden.append("latido"); return [{"ticker": "MP", "zona": "COMPRA"}]
    def _drenar():
        orden.append("drenar"); return [{"ticker": "RXRX", "zona": "MANTENER"}]
    def _pm(motivos):
        orden.append("pm"); return {"motivos": motivos}
    res = correr_ciclo(poller_fn=_poller, latido_fn=_latido, drenar_fn=_drenar, pm_fn=_pm)
    assert orden == ["poller", "latido", "drenar", "pm"]    # orden correcto (PM al final, fichas frescas)
    assert res.desperto_pm is True and "MP entró a COMPRA" in res.motivos_despertar


def test_ciclo_no_despierta_sin_motivo():
    res = correr_ciclo(poller_fn=lambda: {"salidas": []}, latido_fn=lambda: [], drenar_fn=lambda: [],
                       pm_fn=lambda m: "no deberia correr")
    assert res.desperto_pm is False and res.pm_resultado is None   # nada cambió → el PM no corre (válido)
    # forzar_pm (semanal) despierta igual
    res2 = correr_ciclo(poller_fn=lambda: {"salidas": []}, latido_fn=lambda: [], drenar_fn=lambda: [],
                        pm_fn=lambda m: "semanal", forzar_pm=True)
    assert res2.desperto_pm is True
