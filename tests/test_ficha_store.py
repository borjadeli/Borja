"""Store + backfill masivo + job diario + vigencia por evento de la ficha viva (r9, doc 80 §F · P0)."""
from dataclasses import dataclass
from datetime import date

from backend.agentes.ficha import backfill_desde_dossier, evaluar_vigencia
from backend.agentes.ficha_store import StoreFichas, backfill_fichas, recalcular_todas

_ESC = [{"nombre": "bear", "metrica_terminal": 200e6, "multiplo_salida": 5, "anios": 4, "prob": 0.25},
        {"nombre": "base", "metrica_terminal": 500e6, "multiplo_salida": 8, "anios": 4, "prob": 0.50},
        {"nombre": "bull", "metrica_terminal": 900e6, "multiplo_salida": 12, "anios": 4, "prob": 0.25}]


@dataclass
class _Inv:
    analyst_classification: str


@dataclass
class _E:
    nombre: str
    metrica_terminal: float
    multiplo_salida: float
    anios: int
    prob: float


@dataclass
class _Dossier:
    invertibilidad: _Inv
    escenarios: list
    falsador: object = None
    dilucion_esperada_pct: float = 0.0
    negocio_y_posicion_cuello: str = "neg"


@dataclass
class _Entry:
    dossier: object
    hash: str = "h1"


def _dossier():
    return _Dossier(_Inv("satelite"), [_E(**e) for e in _ESC])


def test_store_roundtrip(tmp_path):
    f = backfill_desde_dossier("XYZ", _dossier(), deuda_neta=0.0, acciones=100e6, precio=52.0)
    s = StoreFichas(path=tmp_path / "fichas.json")
    s.set(f)
    s.guardar()
    s2 = StoreFichas(path=tmp_path / "fichas.json")           # recarga desde disco
    g = s2.get("XYZ")
    assert g is not None and g.clase_d4 == "satelite"
    assert g.puente.precio == 52.0 and g.latido.zona in ("MANTENER", "RECORTE")
    assert [e.nombre for e in g.escenarios] == ["bear", "base", "bull"]


def test_backfill_fichas_saltea_sin_acciones(tmp_path):
    cache = {"AAA": _Entry(_dossier()), "BBB": _Entry(_dossier())}
    datos = {"AAA": {"acciones": 100e6, "deuda_neta": 0.0, "precio": 52.0}, "BBB": None}  # BBB sin datos
    s = StoreFichas(path=tmp_path / "f.json")
    fichas = backfill_fichas(cache, datos_fn=lambda tk: datos[tk], store=s)
    assert {f.ticker for f in fichas} == {"AAA"}              # BBB se saltea
    assert s.get("AAA") is not None and s.get("BBB") is None


def test_job_diario_emite_alerta_de_compra(tmp_path):
    cache = {"XYZ": _Entry(_dossier())}
    s = StoreFichas(path=tmp_path / "f.json")
    backfill_fichas(cache, datos_fn=lambda tk: {"acciones": 100e6, "deuda_neta": 0.0, "precio": 52.0}, store=s)
    # el precio cae a 18 → el job debe emitir alerta de cambio a COMPRA, comprable (tesis VIGENTE)
    alertas = recalcular_todas(s, precios_fn=lambda tk: 18.0)
    assert len(alertas) == 1 and alertas[0]["zona"] == "COMPRA" and alertas[0]["comprable"] is True
    # correr de nuevo al mismo precio NO re-emite (no cambió la zona)
    assert recalcular_todas(s, precios_fn=lambda tk: 18.0) == []


def test_vigencia_por_evento():
    f = backfill_desde_dossier("XYZ", _dossier(), deuda_neta=0.0, acciones=100e6, precio=52.0,
                               conocido_hasta="2026-08-01", hoy=date(2026, 9, 1))
    # un 10-Q POSTERIOR a lo que vio la tesis → EN_REVISION
    assert evaluar_vigencia(f, ultimo_filing="2026-11-05", hoy=date(2026, 11, 10)) == "EN_REVISION"
    # sin filing nuevo → sigue VIGENTE
    assert evaluar_vigencia(f, ultimo_filing="2026-07-01", hoy=date(2026, 11, 10)) == "VIGENTE"
    # pasó el tope duro → VENCIDA
    f.tope_duro = "2026-10-01"
    assert evaluar_vigencia(f, ultimo_filing=None, hoy=date(2026, 11, 10)) == "VENCIDA"


def test_job_marca_vencida_y_no_comprable(tmp_path):
    cache = {"XYZ": _Entry(_dossier())}
    s = StoreFichas(path=tmp_path / "f.json")
    backfill_fichas(cache, store=s, datos_fn=lambda tk: {"acciones": 100e6, "deuda_neta": 0.0,
                                                         "precio": 52.0, "conocido_hasta": "2026-08-01"})
    # llega un filing nuevo + el precio cae a zona → alerta COMPRA pero NO comprable (tesis EN_REVISION)
    alertas = recalcular_todas(s, precios_fn=lambda tk: 18.0, filings_fn=lambda tk: "2026-11-05",
                               hoy=date(2026, 11, 10))
    assert alertas and alertas[0]["zona"] == "COMPRA" and alertas[0]["comprable"] is False
    assert s.get("XYZ").estado == "EN_REVISION"


def test_datos_conflicted_no_es_comprable(tmp_path):
    # una ficha en zona COMPRA pero con datos_conflicted (acciones feed≠XBRL, p.ej. split) NO es comprable
    cache = {"XYZ": _Entry(_dossier())}
    s = StoreFichas(path=tmp_path / "f.json")
    backfill_fichas(cache, store=s, datos_fn=lambda tk: {"acciones": 100e6, "deuda_neta": 0.0,
                                                         "precio": 52.0, "datos_conflicted": True})
    alertas = recalcular_todas(s, precios_fn=lambda tk: 18.0)
    assert alertas and alertas[0]["zona"] == "COMPRA"
    assert alertas[0]["comprable"] is False and alertas[0]["datos_conflicted"] is True
