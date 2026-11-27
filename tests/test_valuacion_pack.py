"""Tests de la lente de valuación (r7 §1, doc 78) — fuente_valuacion + ops de cobertura (Gate A).

Scripted (sin red): arma DataPoints ORIGINAL a mano y chequea EV/múltiplos/FCF yield/crecimiento/backlog, los
estados COMPUTED/MISSING/NOT_APPLICABLE, y que la lente quede FUERA del hash de reutilización (es toda DERIVED).
"""
from datetime import date

from backend.agentes import data_pack as dp
from backend.agentes.orquestador import hash_pack
from backend.agentes.provenance import DataKind, DataPack, DataPoint, Source

AS_OF = date(2026, 1, 1)


def _op(metric, value, unit="USD"):
    return DataPoint(entity="TST", metric=metric, value=value, unit=unit, kind=DataKind.ORIGINAL,
                     source=Source(name="scripted"), known_at=AS_OF)


def _lente(pts):
    return {p.metric: p for p in dp.fuente_valuacion("TST", AS_OF, pts)}


def test_lente_completa_computa():
    pts = [_op("market_cap", 2e9), _op("liquidez", 5e8), _op("long_term_debt", 1e8),
           _op("revenue", 4e8), _op("revenue_fy_prev", 3e8), _op("gross_profit", 1.6e8),
           _op("cash_used_ops", 1.2e8), _op("capex", 2e7), _op("rpo", 1.2e9)]
    out = _lente(pts)
    assert out["enterprise_value"].value == 1.6e9           # 2e9 + 1e8 − 5e8
    assert out["ev_revenue"].value == 4.0
    assert out["ev_gross_profit"].value == 10.0
    assert out["fcf_yield"].value == 5.0                    # (1.2e8 − 2e7)/2e9
    assert out["revenue_growth_yoy"].value == 33.3
    assert out["ev_rpo"].value == 1.33
    assert out["backlog_coverage"].value == 3.0
    assert out["valor_contratado_ajustado"].value == 4.8e8  # 1.2e9 × 40%
    assert all(p.kind == DataKind.DERIVED for p in out.values())


def test_pre_revenue_rpo_computa_pero_multiplos_no():
    # el corazón de r7: pre-revenue con backlog contratado → EV/RPO computa, el múltiplo de ventas no aplica.
    pts = [_op("market_cap", 2e9), _op("liquidez", 5e8), _op("rpo", 8e8)]
    out = _lente(pts)
    assert out["ev_rpo"].estado == "COMPUTED"
    assert out["ev_revenue"].estado == "MISSING"
    assert out["fcf_yield"].estado == "MISSING"
    # auditoría: pre-revenue con RPO ahora SÍ emite valor_contratado (margen supuesto) → score ≠ None → visible al PM.
    assert out["valor_contratado_ajustado"].value == 8e8 * 0.40          # RPO × margen supuesto
    assert "SUPUESTO" in (out["valor_contratado_ajustado"].note or "")   # el supuesto queda declarado


def test_revenue_cero_es_not_applicable():
    out = _lente([_op("market_cap", 1e9), _op("liquidez", 2e8), _op("revenue", 0.0)])
    assert out["ev_revenue"].estado == "NOT_APPLICABLE"


def test_fcf_negativo_not_applicable():
    out = _lente([_op("market_cap", 1e9), _op("liquidez", 2e8),
                  _op("cash_used_ops", -5e7), _op("capex", 1e7)])
    assert out["fcf_yield"].estado == "NOT_APPLICABLE"


def test_ev_sin_insumo_es_missing():
    out = _lente([_op("liquidez", 2e8), _op("revenue", 1e8)])    # sin market_cap
    assert out["enterprise_value"].estado == "MISSING"
    assert out["ev_revenue"].estado == "MISSING"


def test_ev_usa_deuda_cero_y_lo_nota():
    out = _lente([_op("market_cap", 1e9), _op("liquidez", 2e8)])  # sin long_term_debt
    assert out["enterprise_value"].value == 8e8
    assert "deuda=0" in out["enterprise_value"].note


def test_lente_fuera_del_hash():
    # el pack con y sin la lente tiene el MISMO hash: la lente es toda DERIVED (hash_pack excluye DERIVED).
    orig = [_op("market_cap", 2e9), _op("revenue", 4e8), _op("liquidez", 5e8)]

    def f_orig(tk, as_of):
        return list(orig)

    sin = dp.ensamblar("TST", as_of=AS_OF, fuentes=[f_orig], fuentes_derivadas=[])
    con = dp.ensamblar("TST", as_of=AS_OF, fuentes=[f_orig], fuentes_derivadas=[dp.fuente_valuacion])
    assert hash_pack(sin) == hash_pack(con)


def test_ops_cobertura_offline():
    from ops.medir_cobertura_valuacion import medir

    def fake_ensamblar(tk, as_of):
        pts = [_op("market_cap", 2e9), _op("liquidez", 5e8), _op("revenue", 4e8), _op("rpo", 1e9)]
        pts += dp.fuente_valuacion(tk, as_of, pts)
        return DataPack(ticker=tk, as_of=as_of, puntos=pts)

    res = medir(["AAA", "BBB"], AS_OF, ensamblar=fake_ensamblar)
    assert res["n"] == 2
    assert res["cobertura"]["rpo"]["computed"] == 2
    assert res["cobertura"]["enterprise_value"]["computed"] == 2
    assert res["cobertura"]["ev_rpo"]["computed"] == 2
