"""PM Decision Packet (r9, doc 80 §G · P2): armado determinista con corte congelado + alertas."""
from dataclasses import dataclass
from datetime import date

from backend.agentes.ficha import backfill_desde_dossier, recalcular
from backend.agentes.oportunidad import FilaScore
from backend.agentes.packet_pm import construir_packet, render_packet

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
class _Fals:
    afirmacion: str
    fecha_limite: str


@dataclass
class _Dossier:
    invertibilidad: _Inv
    escenarios: list
    falsador: object
    dilucion_esperada_pct: float = 0.0
    negocio_y_posicion_cuello: str = "Proveedor del cuello X."


def _ficha(ticker, precio, clase="satelite"):
    d = _Dossier(_Inv(clase), [_E(**e) for e in _ESC], _Fals("no logra el contrato", "2027-06-30"))
    return backfill_desde_dossier(ticker, d, deuda_neta=0.0, acciones=100e6, precio=precio)


def test_packet_arma_posiciones_banca_y_alertas():
    held = _ficha("MP", 50.0)        # caro → zona RECORTE → alerta de recorte
    banca = _ficha("OKLO", 18.0)     # barato → zona COMPRA (no tenencia) → candidata a entrada
    fichas = {"MP": held, "OKLO": banca}
    scores = [FilaScore("NUEVA", "nuclear", 0.8, 0.9, 0.7, 0.5, 1.0)]
    pack = construir_packet(fichas=fichas, posiciones={"MP": 0.06}, caja_pct=0.5, equity=100000.0,
                            scores=scores, decisiones_previas=[{"ticker": "MP", "accion": "mantener", "tesis": "x"}],
                            as_of=date(2026, 11, 13))
    assert pack.data_cutoff == "2026-11-13"                    # corte congelado
    assert [r.ticker for r in pack.posiciones] == ["MP"] and pack.posiciones[0].zona == "RECORTE"
    assert [r.ticker for r in pack.banca_en_zona] == ["OKLO"]  # ficha en COMPRA, no tenencia
    assert any(a["tipo"] == "recorte" and a["ticker"] == "MP" for a in pack.alertas)
    assert any(a["tipo"] == "entrada" and a["ticker"] == "OKLO" for a in pack.alertas)
    assert [o["ticker"] for o in pack.oportunidades_top] == ["NUEVA"]   # ficha-less top score


def test_radar_muestra_vigentes_fuera_de_zona_compra():
    # auditoría: una ficha VIGENTE que NO es tenencia y NO está en COMPRA aparece en el RADAR (antes desaparecía).
    radar_f = _ficha("CRDO", 50.0)                   # caro → zona MANTENER/RECORTE (no COMPRA)
    assert radar_f.latido.zona in ("MANTENER", "RECORTE")
    pack = construir_packet(fichas={"CRDO": radar_f}, posiciones={}, caja_pct=0.9, equity=100000.0)
    assert [r.ticker for r in pack.radar] == ["CRDO"]
    assert [r.ticker for r in pack.banca_en_zona] == []        # no está en COMPRA → no es banca
    assert "RADAR" in render_packet(pack)


def test_packet_marca_tesis_no_vigente():
    held = _ficha("MP", 50.0)
    held.estado = "VENCIDA"
    pack = construir_packet(fichas={"MP": held}, posiciones={"MP": 0.06}, caja_pct=0.5, equity=100000.0)
    assert any(a["tipo"] == "tesis" and "VENCIDA" in a["detalle"] for a in pack.alertas)


def test_recorte_sobre_tesis_vieja_exige_refresh():
    # #2 (doc 80 §F): zona RECORTE (precio, reloj rápido) + tesis NO vigente (reloj lento) → la señal de venta
    # por valuación se apoya en un V_i viejo; el packet marca requiere_refresh y NO corta al ganador por stale.
    held = _ficha("MP", 50.0)        # caro → zona RECORTE
    assert held.latido.zona in ("RECORTE", "SALIDA")
    held.estado = "VENCIDA"
    pack = construir_packet(fichas={"MP": held}, posiciones={"MP": 0.06}, caja_pct=0.5, equity=100000.0)
    rec = [a for a in pack.alertas if a["tipo"] == "recorte" and a["ticker"] == "MP"]
    assert rec and rec[0]["requiere_refresh"] is True and "SIN REFRESCAR" in rec[0]["detalle"]
    # con tesis VIGENTE la misma zona NO exige refresh (el número es fresco)
    held.estado = "VIGENTE"
    pack2 = construir_packet(fichas={"MP": held}, posiciones={"MP": 0.06}, caja_pct=0.5, equity=100000.0)
    rec2 = [a for a in pack2.alertas if a["tipo"] == "recorte" and a["ticker"] == "MP"]
    assert rec2 and rec2[0]["requiere_refresh"] is False


def test_packet_excluye_etf_de_posiciones():
    held = _ficha("MP", 50.0)
    pack = construir_packet(fichas={"MP": held}, posiciones={"MP": 0.06, "URA": 0.10}, caja_pct=0.3,
                            equity=100000.0, tickers_etf={"URA"})
    assert [r.ticker for r in pack.posiciones] == ["MP"]       # URA (ETF estacionamiento) no es tenencia
    assert pack.etf_pct == 0.10


def test_render_packet_texto():
    held = _ficha("MP", 50.0)
    pack = construir_packet(fichas={"MP": held}, posiciones={"MP": 0.06}, caja_pct=0.5, equity=100000.0)
    txt = render_packet(pack)
    assert "PAQUETE DE DECISIÓN" in txt and "MP" in txt and "TENENCIAS" in txt
