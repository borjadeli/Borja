"""Tests del embudo de priorización (v2 doc 64 §A1). Determinista, sin red."""
from datetime import date, datetime
from types import SimpleNamespace

from backend.agentes.embudo import (
    clasificar_candidato,
    es_material,
    es_red_flag,
    eventos_materiales_desde,
    precio_dispara,
    precio_z,
)


def _f(tipo, iso, items=""):
    return SimpleNamespace(tipo=tipo, fecha=datetime.fromisoformat(iso), items=items)


# --- materialidad (whitelist por tipo + ítem de 8-K) ---

def test_8k_material_solo_por_item_whitelisteado():
    assert es_material(_f("8-K", "2026-10-20", items="1.01,9.01")) is True   # 1.01 material
    assert es_material(_f("8-K", "2026-10-20", items="9.01")) is False        # solo 9.01 (exhibits) → no
    assert es_material(_f("8-K", "2026-10-20", items="7.01")) is False        # reg FD → no


def test_form4_y_ruido_no_son_materiales():
    assert es_material(_f("4", "2026-10-20")) is False
    assert es_material(_f("SC 13G", "2026-10-20")) is False
    assert es_material(_f("DEF 14A", "2026-10-20")) is False


def test_periodicos_dilucion_activismo_alarma_son_materiales():
    for tipo in ("10-Q", "10-K", "S-3", "424B5", "SC 13D", "NT 10-Q"):
        assert es_material(_f(tipo, "2026-10-20")) is True


def test_red_flag_detecta_gobernanza():
    assert es_red_flag(_f("8-K", "2026-10-20", items="4.02")) is True   # no-confiabilidad de estados
    assert es_red_flag(_f("NT 10-Q", "2026-10-20")) is True
    assert es_red_flag(_f("8-K", "2026-10-20", items="2.02")) is False  # earnings no es red flag


# --- evento material desde el cursor (la garantía: no reutilizar un dossier si pasó algo material) ---

def test_eventos_materiales_desde_el_cursor():
    filings = [_f("8-K", "2026-10-25", items="1.01"),   # nuevo y material
               _f("4", "2026-10-26"),                   # nuevo pero ruido
               _f("10-Q", "2026-08-07")]                # material pero viejo
    nuevos = eventos_materiales_desde(filings, desde=date(2026, 10, 20))
    assert len(nuevos) == 1 and nuevos[0].tipo == "8-K"


def test_eventos_materiales_sin_cursor_toma_todos_los_materiales():
    filings = [_f("8-K", "2026-01-01", items="1.01"), _f("4", "2026-01-02")]
    assert len(eventos_materiales_desde(filings, desde=None)) == 1


# --- prioridad (cola ordenada, no OR) ---

def test_posicion_con_evento_es_prioridad_maxima():
    ev = [_f("8-K", "2026-10-25", items="1.01")]
    motivo, p = clasificar_candidato(es_posicion=True, eventos_materiales=ev)
    assert motivo == "posicion_con_evento" and p == 0


def test_red_flag_antes_que_dilucion():
    ev = [_f("8-K", "2026-10-25", items="4.02"), _f("S-3", "2026-10-24")]
    motivo, _ = clasificar_candidato(es_posicion=False, eventos_materiales=ev)
    assert motivo == "red_flag"


def test_precio_fuerte_sin_filing_es_candidato_precio():
    motivo, p = clasificar_candidato(es_posicion=False, eventos_materiales=[], z_precio=3.1)
    assert motivo == "precio" and p == 4


def test_sin_trigger_no_amerita_deep():
    motivo, p = clasificar_candidato(es_posicion=False, eventos_materiales=[], z_precio=1.0)
    assert motivo == "sin_trigger" and p == 9


def test_earnings_proximo_en_no_posicion_se_difiere():
    # earnings dentro de 7 días en una no-posición → diferir (no gastar un deep que el balance invalida)
    motivo, _ = clasificar_candidato(es_posicion=False, eventos_materiales=[], z_precio=None, dias_a_evento=7)
    assert motivo == "diferido"
    # pero si ES posición, se maneja por el monitoreo (no se difiere por earnings próximo sin evento)
    motivo2, _ = clasificar_candidato(es_posicion=True, eventos_materiales=[], dias_a_evento=7)
    assert motivo2 == "sin_trigger"


# --- precio residual normalizado ---

def test_precio_z_normaliza_por_volatilidad():
    # serie tranquila con un salto final → z alto; serie volátil con el mismo salto → z menor
    tranquila = [100.0] * 25 + [100.5] * 5 + [130.0]       # casi plano y salta 30%
    volatil = [100 + (i % 7) * 8 for i in range(30)] + [130.0]
    zt = precio_z(tranquila)
    zv = precio_z(volatil)
    assert zt is not None and zv is not None and abs(zt) > abs(zv)


def test_precio_dispara_umbral_mas_bajo_para_posicion():
    assert precio_dispara(2.2, None, es_posicion=True) is True     # 2.2 >= 2.0 (posición)
    assert precio_dispara(2.2, None, es_posicion=False) is False   # 2.2 < 2.5 (no-posición)
    assert precio_dispara(0.5, 30.0, es_posicion=False) is True    # respaldo absoluto ±25%


def test_precio_z_sin_serie_suficiente_es_none():
    assert precio_z([100.0, 101.0]) is None
