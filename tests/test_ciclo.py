"""run_cycle (doc 85): encadenado + decisión de despertar al PM + plan de salidas (lógica pura)."""
from backend.agentes.ciclo import correr_ciclo, razones_despertar
from backend.agentes.reglas_salida import AccionSalida
from ops.ciclo_diario import _planear_salidas


def test_planear_salidas_solo_total_toca_solo_su_ticker():
    # SALIDA_TOTAL de WOLF → WOLF a 0 (sale del dict), el RESTO de la cartera intacto.
    pesos = {"WOLF": 0.1, "MP": 0.2, "OKLO": 0.05}
    finales, claves = _planear_salidas([AccionSalida("WOLF", "A", "SALIDA_TOTAL", "quiebra", "acc1")], set(), pesos)
    assert finales == {"MP": 0.2, "OKLO": 0.05} and claves == {"WOLF:acc1"}


def test_planear_salidas_tier_B_C_no_auto_ejecutan():
    # r10: tier B (RECORTE_50) y tier C (DESPERTAR) NO se auto-ejecutan (despiertan al PM) → nada que planear.
    pesos = {"WOLF": 0.1, "MP": 0.2}
    assert _planear_salidas([AccionSalida("WOLF", "C", "DESPERTAR", "ceo")], set(), pesos) == (None, set())
    assert _planear_salidas([AccionSalida("WOLF", "B", "RECORTE_50", "falsador")], set(), pesos) == (None, set())


def test_planear_salidas_idempotente():
    # una salida YA ejecutada (misma clave ticker:fuente) NO se repite.
    pesos = {"WOLF": 0.1, "MP": 0.2}
    sal = [AccionSalida("WOLF", "A", "SALIDA_TOTAL", "quiebra", "acc1")]
    assert _planear_salidas(sal, {"WOLF:acc1"}, pesos) == (None, set())       # ya está → no repite
    finales, claves = _planear_salidas(sal, set(), pesos)                     # distinta corrida sin la clave → sí
    assert "WOLF" not in finales and claves == {"WOLF:acc1"}


def test_lock_anti_duplicados_y_huerfano(tmp_path, monkeypatch):
    # garantía pre-restart (doc 85: 'duplicar al reiniciar es peor que manual'): dos ciclos no corren a la vez,
    # pero un lock huérfano (proceso muerto, mtime viejo) NO bloquea para siempre.
    import os
    import time

    import ops.ciclo_diario as cd
    monkeypatch.setattr(cd, "_LOCK", tmp_path / "ciclo.lock")
    assert cd._tomar_lock() is True         # libre → lo toma
    assert cd._tomar_lock() is False        # lock vivo → NO duplica
    cd._soltar_lock()
    assert cd._tomar_lock() is True         # liberado → vuelve a tomar
    old = time.time() - cd._LOCK_TTL - 10   # simula un lock huérfano (proceso que murió sin soltarlo)
    os.utime(cd._LOCK, (old, old))
    assert cd._tomar_lock() is True         # TTL vencido → retoma (no queda trabado para siempre)


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
