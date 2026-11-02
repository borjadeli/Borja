"""Tests de D3 — tabla curada de tasas base + calibración del bull (doc 74)."""
from backend.agentes.tasas_base import SIN_MUESTRA, calibracion_bull, filas, render_tabla, tasa_base


def test_tabla_tiene_filas_con_fuente_y_tasa():
    fs = filas()
    assert 12 <= len(fs) <= 30                       # tabla acotada y curada
    assert all(f.fuente and 0 <= f.tasa <= 1 and f.descripcion for f in fs)
    assert tasa_base("gr_sales_50_5y").tasa < tasa_base("gr_sales_20_5y").tasa   # decae con el umbral


def test_calibracion_bull_marca_optimismo_sin_sustento():
    # P(bull) 25% anclada a una tasa base de 6% → 25% > 2x6%=12% → no calibra
    ok, motivo = calibracion_bull(0.25, "gr_sales_30_5y")
    assert ok is False and "2x" in motivo
    # 10% sobre 6% → dentro de 2x → ok
    assert calibracion_bull(0.10, "gr_sales_30_5y")[0] is True


def test_calibracion_sin_muestra_o_sin_ancla_permitida():
    assert calibracion_bull(0.5, SIN_MUESTRA)[0] is True       # juicio explícito
    assert calibracion_bull(0.5, None)[0] is True
    assert calibracion_bull(None, "gr_sales_30_5y")[0] is True  # sin prob: nada que calibrar


def test_calibracion_ancla_desconocida_falla():
    ok, motivo = calibracion_bull(0.1, "fila_inventada")
    assert ok is False and "desconocida" in motivo


def test_render_tabla_incluye_ids_y_sin_muestra():
    t = render_tabla()
    assert "gr_sales_30_5y" in t and "mega_nuclear" in t and SIN_MUESTRA in t


# ---- integración con el Verificador ----

def _doss_bull(prob, ancla):
    from backend.agentes import schemas as sc
    meta = sc.AgentMeta(agent="analista", prompt_version="v1", model="m")
    esc = sc.Escenario(tesis="t", supuestos=["a"], contraste_con_calculadoras="c")
    vara = sc.VaraExterna(tipo="economico", metrica="ebitda", umbral="X", comparador="peers",
                          fuente_medicion="10-Q")
    return sc.Dossier(
        meta=meta, ticker="RGTI", negocio_y_posicion_cuello="QC",
        claims=[sc.Claim(claim_id="c1", contenido="x", tipo="hecho", source_url="https://sec.gov/a",
                         cited_text="c", source_date="2026-01-01", known_at="2026-01-01",
                         materiality="central", verification="confirmed_by_filing")],
        tesis_claims_soporte=["c1"], valuacion_que_exige_el_precio="T*", bull=esc, bear=esc,
        falsador=sc.Falsador(afirmacion="a", fecha_limite="2027-06-30", que_lo_mataria="x", vara_externa=vara),
        escenarios=[sc.EscenarioValuacion(nombre="bull", metrica_terminal=9e8, tipo_metrica="revenue",
                                          multiplo_salida=8, anios=5, prob=prob, ancla_tasa_base=ancla)],
        conviccion_0_1=0.5)


def test_verificador_review_si_bull_mal_calibrado():
    from backend.agentes.verificador import verificar
    r = verificar(_doss_bull(0.5, "gr_sales_30_5y"), ["https://sec.gov/a"])   # 50% >> 2x6%
    assert r.veredicto == "review" and any("calibración bull" in m for m in r.motivos)


def test_verificador_nota_si_bull_sin_ancla():
    from backend.agentes.verificador import verificar
    r = verificar(_doss_bull(0.3, None), ["https://sec.gov/a"])
    assert r.veredicto == "pass" and any("sin ancla de tasa base" in n for n in r.notas)
