"""Falsadores estructurados (doc 85 F2): evaluación determinista + verificabilidad + tier B."""
from datetime import date

from backend.agentes.falsadores import Falsador, confirmados_para_salida, es_verificable, evaluar


def test_evaluar_numerico():
    f = Falsador(id="rev27", metrica="revenue_2027", operador="<", umbral=100e6, tipo="DURO", consecuencia="RECORTE_50")
    assert evaluar(f, valor=60e6) == "CONFIRMED"      # 60M < 100M → la tesis falló
    assert evaluar(f, valor=150e6) == "OK"            # cumple el umbral
    assert evaluar(f, valor=None) == "OK"             # sin dato → OK (no se inventa)


def test_evaluar_hito_vencido():
    f = Falsador(id="aurora", metrica="aurora_online", fecha_limite="2028-06-30", tipo="DURO", consecuencia="SALIDA")
    assert evaluar(f, hoy=date(2028, 7, 1)) == "CONFIRMED"              # venció sin cumplirse → plata muerta
    assert evaluar(f, hoy=date(2028, 7, 1), cumplido=True) == "OK"     # se cumplió antes → OK
    assert evaluar(f, hoy=date(2027, 1, 1)) == "OK"                    # todavía no venció


def test_evidencia_ambigua_es_suspected():
    f = Falsador(id="gc", metrica="going_concern", fecha_limite="2027-01-01", tipo="DURO", consecuencia="RECORTE_50")
    assert evaluar(f, evidencia_ambigua=True, hoy=date(2027, 6, 1)) == "SUSPECTED"   # textual dudoso → no liquida


def test_es_verificable():
    assert es_verificable(Falsador(id="a", metrica="rev", operador=">=", umbral=1.0)) is True
    assert es_verificable(Falsador(id="b", metrica="hito", fecha_limite="2027-01-01")) is True
    assert es_verificable(Falsador(id="c", metrica="algo vago")) is False   # el Verificador rechazaría un DURO así


def test_confirmados_para_salida_tier_B():
    class _F:
        def __init__(self, fals):
            self.falsadores = fals
    fichas = {
        "OKLO": _F([Falsador(id="aurora", metrica="aurora_online", fecha_limite="2028-06-30", tipo="DURO",
                             consecuencia="SALIDA").to_dict()]),
        "MP": _F([Falsador(id="blando", metrica="x", operador="<", umbral=1.0, tipo="BLANDO").to_dict()]),  # BLANDO → no
    }
    conf = confirmados_para_salida(fichas, hoy=date(2028, 7, 1))
    assert "OKLO" in conf and conf["OKLO"][0]["consecuencia"] == "SALIDA"
    assert "MP" not in conf                             # BLANDO no dispara regla (va a juicio del PM)
