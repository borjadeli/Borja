"""Carril especulativo (doc 29) — gate §2 + sizing/caps §4 + budget §5. El sizing de las PURA-OPCIÓN
vive acá, no en el libro duro. Orden §3 (rúbrica) es placeholder hasta el PM-LLM."""
from backend.nucleo.carril import HechosCarril, gate_carril, construir_carril
from backend.nucleo.ranking_lexicografico import CandidatoLex


def _hc(t, **kw):
    base = dict(runway_anos=3.0, evidencia_externa=True, hito_meses=12.0,
                materialidad_relativa=True, falsabilidad_escrita=True)
    base.update(kw)
    return HechosCarril(ticker=t, **base)


def _cand(t, cap=0.08, cob=0.5):
    return CandidatoLex(ticker=t, elegible=True, valuacion_ok=False, tier_capital="A",
                        cobertura=cob, asimetria_operable=None, arquetipo="Pre-revenue", cap=cap)


# --- gate §2: todas obligatorias ---
def test_gate_pasa_con_todo():
    assert gate_carril(_hc("X"))["pasa"] is True


def test_gate_falla_sin_evidencia_externa():
    r = gate_carril(_hc("X", evidencia_externa=None))
    assert r["pasa"] is False and any("evidencia externa" in m for m in r["motivos"])


def test_gate_falla_hito_lejano():
    assert gate_carril(_hc("X", hito_meses=30))["pasa"] is False


def test_gate_supervivencia_por_fragilidad():
    # sin runway pero dilución capturada en fragilidad → supervivencia OK
    assert gate_carril(_hc("X", runway_anos=None, dilucion_capturada_en_fragilidad=True))["pasa"] is True


def test_gate_none_no_pasa_conservador():
    # hechos sin extraer (todos None) → NO entra (sin evidencia citada, la historia no entra)
    assert gate_carril(HechosCarril("X"))["pasa"] is False


# --- sizing §4 + budget §5 ---
def test_pura_opcion_tiene_sizing_en_el_carril():
    # la clave: una pura-opción (0 en el libro duro) SÍ recibe tamaño acá
    car = construir_carril([_cand("MP")], {"MP": _hc("MP")})
    assert [p.ticker for p in car.posiciones] == ["MP"] and car.posiciones[0].size == 0.08


def test_cap_8pct_por_posicion():
    car = construir_carril([_cand("X", cap=0.20)], {"X": _hc("X")})   # cap arquetipo 20% → capado a 8%
    assert car.posiciones[0].size == 0.08


def test_max_2_plazas():
    cands = [_cand(f"T{i}") for i in range(4)]
    hechos = {f"T{i}": _hc(f"T{i}") for i in range(4)}
    car = construir_carril(cands, hechos)
    assert len(car.posiciones) == 2                         # máx 2 plazas (§4)


def test_max_1_por_catalizador():
    cands = [_cand("A"), _cand("B")]
    hechos = {"A": _hc("A", catalizador="DoD"), "B": _hc("B", catalizador="DoD")}
    car = construir_carril(cands, hechos)
    assert len(car.posiciones) == 1                         # máx 1 por catalizador (§4)


def test_presupuesto_piso_10pct():
    # 2 plazas a 8% = 16% pedido, pero el presupuesto piso es 10% → la 2ª no entra completa
    cands = [_cand("A"), _cand("B")]
    hechos = {"A": _hc("A"), "B": _hc("B")}
    car = construir_carril(cands, hechos)
    assert car.invertido <= 0.10 + 1e-9


def test_gate_fail_va_a_rechazados():
    car = construir_carril([_cand("X")], {"X": HechosCarril("X")})   # sin hechos → gate fail
    assert car.posiciones == [] and any("gate §2" in r["motivo"] for r in car.rechazados)


def test_orden_placeholder_sin_rubrica():
    car = construir_carril([_cand("X")], {"X": _hc("X")})   # sin grado_opcionalidad
    assert car.orden_placeholder is True                    # marca que el orden NO es definitivo (falta §3)
    assert car.politica_version and car.politica_hash


# --- §3 rúbrica → grado ordinal (doc 29) ---
def test_grado_opcionalidad_ordinal():
    from backend.nucleo import politica
    assert politica.grado_opcionalidad(False, False, False) == 0
    assert politica.grado_opcionalidad(True, False, False) == 2    # contraparte financiada = señal más fuerte
    assert politica.grado_opcionalidad(True, True, True) == 4       # máximo
    assert politica.grado_opcionalidad(False, True, True) == 2


# --- construir_hechos_carril: mapea fact_store → HechosCarril (determinista) ---
class _F:
    def __init__(self, value=True, support_type="DIRECT"):
        self.value = value
        self.support_type = support_type


def test_construir_hechos_carril_desde_snapshot():
    from backend.nucleo.carril import construir_hechos_carril, gate_carril
    snap = {
        "opcion_evidencia_externa": _F(True), "opcion_hito_cercano": _F(True),
        "opcion_materialidad": _F(True), "opcion_falsador_documento": _F(True),
        "opcion_contraparte_financiada": _F(True), "opcion_dinero_autorizado": _F(True),
        "opcion_transaccion_precedente": _F(False),
    }
    h = construir_hechos_carril("X", snap, runway_anos=3.0)
    assert h.evidencia_externa is True and h.materialidad_relativa is True and h.hito_meses == 12.0
    assert h.grado_opcionalidad == 3                 # contraparte(2)+dinero(1)+precedente(0)
    assert gate_carril(h)["pasa"] is True            # todas las obligatorias OK


def test_construir_hechos_carril_unknown_es_none():
    from backend.nucleo.carril import construir_hechos_carril, gate_carril
    snap = {"opcion_evidencia_externa": _F(True, support_type="UNKNOWN")}   # UNKNOWN → None
    h = construir_hechos_carril("X", snap, runway_anos=3.0)
    assert h.evidencia_externa is None and gate_carril(h)["pasa"] is False   # sin evidencia citada → no pasa
