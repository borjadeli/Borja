"""Falsadores estructurados (doc 85 F2): evaluación determinista + verificabilidad + tier B."""
from datetime import date

from backend.agentes.falsadores import Falsador, confirmados_para_salida, es_verificable, evaluar


def test_evaluar_numerico():
    # r10: numérico SOLO con tag XBRL en `fuente`; necesita valor (sin dato → SUSPECTED, no OK ni CONFIRMED)
    f = Falsador(id="rev27", metrica="revenue", fuente="xbrl:Revenues", operador="<", umbral=100e6, tipo="DURO")
    assert evaluar(f, valor=60e6) == "CONFIRMED"      # 60M < 100M → la tesis falló
    assert evaluar(f, valor=150e6) == "OK"            # cumple el umbral
    assert evaluar(f, valor=None) == "SUSPECTED"      # sin dato → SUSPECTED (pide, NO vende, NO inventa)


def test_numerico_con_fecha_vencida_no_vende():
    # EL BUG r10: numérico con ventana vencida sin cruzar el umbral → EXPIRED (renovar), NUNCA CONFIRMED por ausencia
    f = Falsador(id="liq", metrica="liquidez", fuente="xbrl:Liquidity", operador="<", umbral=1e9,
                 fecha_limite="2026-09-30", tipo="DURO")
    assert evaluar(f, valor=3e9, hoy=date(2026, 11, 1)) == "EXPIRED"   # liquidez 3e9 ≥ 1e9 + vencido → NO vende
    assert evaluar(f, valor=None, hoy=date(2026, 11, 1)) == "SUSPECTED"  # sin dato → al PM, NO auto-venta


def test_evaluar_hito_textual():
    # r10: hito textual → CONFIRMED SOLO con evidencia de incumplimiento (cumplido=False); vencer sin evidencia → SUSPECTED
    f = Falsador(id="aurora", metrica="aurora_online", fecha_limite="2028-06-30", tipo="DURO")
    assert evaluar(f, hoy=date(2028, 7, 1)) == "SUSPECTED"                 # venció sin resolver → al PM, NO vende
    assert evaluar(f, hoy=date(2028, 7, 1), cumplido=False) == "CONFIRMED"  # evidencia de que NO se cumplió
    assert evaluar(f, hoy=date(2028, 7, 1), cumplido=True) == "OK"         # se cumplió


def test_es_verificable():
    # r10: solo numérico con tag XBRL es verificable por máquina (→ puede ser DURO)
    assert es_verificable(Falsador(id="a", metrica="rev", fuente="xbrl:Revenues", operador=">=", umbral=1.0)) is True
    assert es_verificable(Falsador(id="b", metrica="hito", fecha_limite="2027-01-01")) is False   # hito textual → NO
    assert es_verificable(Falsador(id="c", metrica="revenue_2027", operador="<", umbral=1.0)) is False  # sin tag → NO


def test_confirmados_para_salida_tier_B():
    # r10: un DURO numérico con tag que CRUZA el umbral → CONFIRMED; uno sin resolver → SUSPECTED; los dos van al
    # PM (DESPERTAR). Un BLANDO no dispara regla.
    class _F:
        def __init__(self, fals):
            self.falsadores = fals
    fichas = {
        "WOLF": _F([Falsador(id="liq", metrica="liquidez", fuente="xbrl:Liquidity", operador="<", umbral=1e9,
                             tipo="DURO").to_dict()]),
        "MP": _F([Falsador(id="blando", metrica="x", fuente="xbrl:X", operador="<", umbral=1.0, tipo="BLANDO").to_dict()]),
    }
    conf = confirmados_para_salida(fichas, valor_fn=lambda tk, m: 0.5e9 if tk == "WOLF" else None, hoy=date(2026, 11, 1))
    assert "WOLF" in conf and conf["WOLF"][0]["estado"] == "CONFIRMED"   # 0.5e9 < 1e9 → la tesis falló
    assert "MP" not in conf                             # BLANDO no dispara (va a juicio del PM)
