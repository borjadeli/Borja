"""Tests del data pack assembler (v2 Fase 3). Sin red — se inyecta el snapshot/fuentes."""
from dataclasses import dataclass
from datetime import date

from backend.agentes import data_pack as dp
from backend.agentes.provenance import DataKind

AS_OF = date(2026, 10, 26)


@dataclass
class FakeSnap:
    ticker: str
    precio_actual: float | None
    volumen_diario_promedio_30d: float | None
    market_cap: float | None
    shares_outstanding: float | None = None
    currency: str = "USD"


def _fuente_fake(snap):
    return lambda tk, as_of: dp.fuente_mercado(tk, as_of, snapshot_fn=lambda _t: snap)


def test_fuente_mercado_tagea_procedencia():
    snap = FakeSnap("OKLO", precio_actual=50.0, volumen_diario_promedio_30d=3e7,
                    market_cap=4.9e9, shares_outstanding=1e8)
    pack = dp.ensamblar("oklo", as_of=AS_OF, fuentes=[_fuente_fake(snap)])
    metrics = {p.metric: p for p in pack.puntos}
    assert pack.ticker == "OKLO"
    assert metrics["market_cap"].value == 4.9e9
    assert metrics["market_cap"].kind == DataKind.ORIGINAL        # vino del feed
    assert all(p.known_at == AS_OF for p in pack.puntos)          # point-in-time
    assert metrics["precio"].source.document_type == "api"


def test_market_cap_derivado_si_falta_en_el_feed():
    snap = FakeSnap("X", precio_actual=10.0, volumen_diario_promedio_30d=2e6,
                    market_cap=None, shares_outstanding=5e8)
    pack = dp.ensamblar("X", as_of=AS_OF, fuentes=[_fuente_fake(snap)])
    mc = next(p for p in pack.puntos if p.metric == "market_cap")
    assert mc.value == 10.0 * 5e8
    assert mc.kind == DataKind.DERIVED
    assert mc.inputs == ["precio", "shares_outstanding"]          # deja rastro de insumos


def test_snapshot_none_no_rompe():
    pack = dp.ensamblar("X", as_of=AS_OF, fuentes=[_fuente_fake(None)])
    assert pack.puntos == []


def test_fuente_que_falla_no_tumba_el_pack():
    def rota(tk, as_of):
        raise RuntimeError("boom")
    snap = FakeSnap("X", 10.0, 2e6, 1e9, 1e8)
    pack = dp.ensamblar("X", as_of=AS_OF, fuentes=[rota, _fuente_fake(snap)])
    assert any(p.metric == "market_cap" for p in pack.puntos)     # la buena igual entró


def test_datapoint_no_defaultea_a_confirmed_filing():
    # auditoría P1: un DataPoint sin `verification` NO debe quedar como confirmed_by_filing (marcaría datos de
    # mercado como "confirmados por filing"). Default seguro = None (no aseverado).
    from backend.agentes.provenance import DataPoint, Source
    p = DataPoint(entity="OKLO", metric="precio", value=27.37, source=Source(name="Yahoo", document_type="api"))
    assert p.verification is None


def test_fuente_mercado_no_queda_confirmada_por_filing():
    snap = FakeSnap("OKLO", precio_actual=27.37, volumen_diario_promedio_30d=1e7,
                    market_cap=5e9, shares_outstanding=1.8e8)
    pts = dp.fuente_mercado("OKLO", date(2026, 10, 27), snapshot_fn=lambda _t: snap)
    assert pts and all(p.verification is None for p in pts)   # precios/market cap NO son confirmed_by_filing
