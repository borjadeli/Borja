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


# --- A3: cobertura / bootstrap ---
from types import SimpleNamespace as _NS  # noqa: E402
from backend.agentes.embudo import cupo_bootstrap, gate_invertibilidad, ordenar_cobertura  # noqa: E402

_IPS = {"market_cap_min_usd": 150e6, "market_cap_max_usd": 60e9, "adv_min_usd": 3e6}


def _ctx(mc=5e9, adv=10e6):
    return _NS(market_cap=mc, adv_usd=adv)


def test_gate_invertibilidad():
    assert gate_invertibilidad(_ctx(5e9, 10e6), _IPS) is True
    assert gate_invertibilidad(_ctx(70e9, 10e6), _IPS) is False   # market cap fuera de rango
    assert gate_invertibilidad(_ctx(5e9, 1e6), _IPS) is False     # ADV bajo
    assert gate_invertibilidad(_ctx(None, None), _IPS) is True    # sin datos → invertible (gate duro luego)


def test_cupo_bootstrap_acelerado_y_regimen():
    assert cupo_bootstrap(1) == 6 and cupo_bootstrap(10) == 6     # primeras 10 semanas
    assert cupo_bootstrap(11) == 2 and cupo_bootstrap(30) == 2    # régimen


def test_ordenar_cobertura_filtra_invertibles_y_ordena_por_cuello():
    nuevos = [("A", _NS(prioridad_cuello=1), ""), ("B", _NS(prioridad_cuello=3), ""),
              ("C", _NS(prioridad_cuello=2), "")]
    ctx = {"A": _ctx(5e9), "B": _ctx(70e9), "C": _ctx(5e9)}       # B no invertible
    orden = ordenar_cobertura(nuevos, ips_cfg=_IPS, ctx_fn=lambda t: ctx[t])
    tks = [c[0] for c in orden]
    assert "B" not in tks and tks == ["C", "A"]                   # B fuera; C(2) antes que A(1)


def test_ordenar_cobertura_excluye_earnings_proximos():
    nuevos = [("A", _NS(prioridad_cuello=1), ""), ("B", _NS(prioridad_cuello=1), "")]
    orden = ordenar_cobertura(nuevos, ips_cfg=_IPS, ctx_fn=lambda t: _ctx(),
                              dias_a_evento_fn=lambda t: 5 if t == "A" else 40)
    assert [c[0] for c in orden] == ["B"]                         # A reporta en 5d → se difiere


# --- A5: escalera mensual por categorías ---
from backend.agentes.presupuesto import categorias_habilitadas  # noqa: E402


def test_categorias_habilitadas_por_nivel_mensual():
    assert "bootstrap" in categorias_habilitadas(10, 40)          # <70% → todo
    h = categorias_habilitadas(30, 40)                            # 75% → sin bootstrap/cobertura
    assert "bootstrap" not in h and "cobertura" not in h and "novedad_material" in h
    h2 = categorias_habilitadas(37, 40)                           # 92% → solo posiciones+red flags
    assert h2 == {"red_flag_posicion", "posicion_con_evento"}
    assert categorias_habilitadas(40, 40) == {"red_flag_posicion"}  # 100% → solo red flag en posición


# --- selección de deep (fuente única dry-run = real; decisión de earnings del operador) ---
from backend.agentes.embudo import seleccionar_para_deep  # noqa: E402
from backend.agentes.triage import SenalesTriage  # noqa: E402


def _cand(tk, **kw):
    base = dict(dias_desde_dossier=10, hechos_nuevos=0, dias_a_evento=None, precio_vs_tesis_pct=None,
                es_posicion=False, tiene_evento_fuerte=False, prioridad_cuello=0)
    base.update(kw)
    return (tk, SenalesTriage(**base), "")


def test_seleccion_posicion_y_evento_fuerte_van_a_deep():
    cands = [_cand("POS", es_posicion=True), _cand("EVT", tiene_evento_fuerte=True), _cand("NADA")]
    sel = seleccionar_para_deep(cands, cupo=0)
    assert "POS" in sel["deep"] and "EVT" in sel["deep"] and "NADA" not in sel["deep"]


def test_seleccion_earnings_proximo_solo_top_n_no_posiciones():
    # 4 nombres con earnings próximo (no-posición), prioridad de cuello 3/2/1/0; top_n=2 → los 2 de mayor cuello
    cands = [_cand("A", dias_a_evento=5, prioridad_cuello=3, dias_desde_dossier=20),
             _cand("B", dias_a_evento=5, prioridad_cuello=2, dias_desde_dossier=20),
             _cand("C", dias_a_evento=5, prioridad_cuello=1, dias_desde_dossier=20),
             _cand("D", dias_a_evento=5, prioridad_cuello=0, dias_desde_dossier=20)]
    sel = seleccionar_para_deep(cands, cupo=0, pre_earnings_top_n=2, dias_earnings=10)
    assert {t for t, _ in sel["pre_earnings"]} == {"A", "B"}      # los 2 mejores por cuello
    assert "C" not in sel["deep"] and "D" not in sel["deep"]      # el resto espera post-earnings


def test_seleccion_posicion_con_earnings_proximo_igual_va():
    # una POSICIÓN con earnings próximo va a deep aunque no sea top (decisión del operador)
    sel = seleccionar_para_deep([_cand("P", es_posicion=True, dias_a_evento=3)], cupo=0, pre_earnings_top_n=0)
    assert "P" in sel["deep"]


def test_seleccion_cupo_promueve_nuevos_por_cuello():
    cands = [_cand("N1", dias_desde_dossier=None, prioridad_cuello=1),
             _cand("N2", dias_desde_dossier=None, prioridad_cuello=3)]
    sel = seleccionar_para_deep(cands, cupo=1)
    assert [t for t, _ in sel["promovidos"]] == ["N2"]           # el de mayor cuello
