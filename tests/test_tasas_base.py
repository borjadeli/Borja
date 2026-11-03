"""Tests de D3 — tabla curada de tasas base + calibración del bull (doc 74, endurecido r5 item 1)."""
import backend.agentes.tasas_base as tb
from backend.agentes.tasas_base import SIN_MUESTRA, TasaBase, calibracion_bull, filas, render_tabla, tasa_base


def test_tabla_curada_con_fuente_sin_filas_a_computar():
    fs = filas()
    assert 8 <= len(fs) <= 30                        # tabla acotada y curada
    assert all(f.fuente and 0 <= f.tasa <= 1 and f.descripcion for f in fs)
    assert all("a computar" not in f.fuente and "universo" not in f.fuente.lower() for f in fs)  # r5: sacadas
    assert tasa_base("gr_sales_50_5y").tasa < tasa_base("gr_sales_20_5y").tasa   # decae con el umbral


def test_ninguna_fila_verificada_todavia_no_gatea():
    # r5 item 1: hasta verificar contra la fuente, ninguna fila gatea (solo informa)
    assert all(not f.verificada and not f.gatea for f in filas())


def test_flyvbjerg_nota_corregida():
    f = tasa_base("mega_ontime_onbudget")
    assert abs(f.tasa - 0.085) < 1e-9 and "tiempo+presupuesto" in f.nota and "0,5%" in f.nota


def test_calibracion_fila_no_verificada_informa_no_gatea():
    # anclada a una fila real pero NO verificada + prob alta → NOTA, no review
    estado, motivo = calibracion_bull(0.5, "gr_sales_30_5y")
    assert estado == "nota" and "no verificada" in motivo


def test_calibracion_fila_verificada_si_gatea(monkeypatch):
    # si la fila estuviera verificada, P(bull) > 2x la tasa base → REVIEW (el gate real cuando se verifique)
    verif = TasaBase("_v", "fila verificada de prueba", "fuente", 0.05, verificada=True, cita="tabla X")
    monkeypatch.setitem(tb._TABLA, "_v", verif)
    assert calibracion_bull(0.25, "_v")[0] == "review"      # 25% > 2x5%
    assert calibracion_bull(0.08, "_v")[0] == "ok"          # dentro de 2x


def test_calibracion_sin_muestra_y_sin_ancla_informan():
    assert calibracion_bull(0.5, SIN_MUESTRA)[0] == "nota"
    assert calibracion_bull(0.5, None)[0] == "nota"
    assert calibracion_bull(None, "gr_sales_30_5y")[0] == "ok"   # sin prob: nada que calibrar


def test_calibracion_ancla_inventada_es_review():
    estado, motivo = calibracion_bull(0.1, "fila_inventada")
    assert estado == "review" and "inventada" in motivo


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


def test_verificador_nota_no_review_con_fila_no_verificada():
    # r5: fila real pero no verificada → NOTA, el dossier NO baja a review por calibración
    from backend.agentes.verificador import verificar
    r = verificar(_doss_bull(0.5, "gr_sales_30_5y"), ["https://sec.gov/a"])
    assert r.veredicto == "pass" and any("calibración bull" in n for n in r.notas)


def test_verificador_review_con_fila_verificada(monkeypatch):
    from backend.agentes.verificador import verificar
    monkeypatch.setitem(tb._TABLA, "_v", TasaBase("_v", "x", "f", 0.05, verificada=True, cita="t"))
    r = verificar(_doss_bull(0.5, "_v"), ["https://sec.gov/a"])
    assert r.veredicto == "review" and any("calibración bull" in m for m in r.motivos)
