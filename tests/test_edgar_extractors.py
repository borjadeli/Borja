"""Extractores de balance robustos (deuda multi-tag, caja+ST inv, shares recientes) — auditoría 2026-08."""
from backend.services import edgar


def _facts(**tags):
    """Minimal companyfacts: cada tag → un valor instantáneo (end 2026-03-31, sin start)."""
    return {"facts": {"us-gaap": {t: {"units": {"USD": [{"end": "2026-03-31", "val": float(v)}]}}
                                   for t, v in tags.items()}}}


def _facts_shares(rows):
    """rows: tag → (end, val). Para outstanding/issued (instantáneo)."""
    return {"facts": {"us-gaap": {t: {"units": {"shares": [{"end": end, "val": float(v)}]}}
                                  for t, (end, v) in rows.items()}}}


def test_debt_rollup_parcial_usa_familias():
    # AAOI: LongTermDebt=34 (parcial) vs convertibles 129.5 + current 41.2 = 170.7 → familias.
    f = _facts(LongTermDebt=34e6, ConvertibleLongTermNotesPayable=129.5e6, LongTermDebtCurrent=41.2e6)
    assert abs(edgar._extract_total_debt(f) - 170.7e6) < 1e5


def test_debt_rollup_completo_gana_a_familias_que_solapan():
    # COHR: rollup 3193 completo; familias solaparían (LongTermDebtNoncurrent ya incluye convertibles).
    f = _facts(LongTermDebt=3193.8e6, LongTermDebtNoncurrent=3193.8e6, ConvertibleDebtNoncurrent=980e6)
    assert abs(edgar._extract_total_debt(f) - 3193.8e6) < 1e5


def test_debt_solo_convertibles():
    # VRNS: sin rollup estándar, solo convertibles.
    f = _facts(ConvertibleDebtNoncurrent=453.3e6)
    assert abs(edgar._extract_total_debt(f) - 453.3e6) < 1e5


def test_cash_incluye_short_term_investments():
    # S: cash 153 + ST inv 503.6 = 656.6 (el piso debe ser líquido, no net cash).
    f = _facts(CashAndCashEquivalentsAtCarryingValue=153.2e6, ShortTermInvestments=503.6e6)
    assert abs(edgar._extract_cash(f) - 656.8e6) < 1e5


def test_cash_combinado_parcial_no_gana():
    # AAOI: tag combinado parcial (8M) no le gana a caja real (439.7M).
    f = _facts(CashCashEquivalentsAndShortTermInvestments=8.2e6,
               CashAndCashEquivalentsAtCarryingValue=439.7e6)
    assert abs(edgar._extract_cash(f) - 439.7e6) < 1e5


def test_shares_mas_reciente_gana_al_dei_stale():
    # LEU: EntityCommonStockSharesOutstanding congelado en 2022 (13.67M); Issued 2025 = 19.66M gana.
    f = _facts_shares({
        "EntityCommonStockSharesOutstanding": ("2022-03-01", 13.67e6),
        "CommonStockSharesIssued": ("2025-12-31", 19.66e6),
    })
    val, asof = edgar._extract_shares(f)
    assert abs(val - 19.66e6) < 1e4
    assert asof == "2025-12-31"                 # devuelve también la fecha del dato elegido (para stale)


# --- Form 4 real: parseo de compra/venta a MERCADO (código P/S), doc 14 §Pilar3 ---
_FORM4_XML = """<?xml version="1.0"?>
<ownershipDocument>
  <nonDerivativeTransaction>
    <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
    <transactionAmounts>
      <transactionShares><value>1000</value></transactionShares>
      <transactionPricePerShare><value>10.00</value></transactionPricePerShare>
      <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
    </transactionAmounts>
  </nonDerivativeTransaction>
  <nonDerivativeTransaction>
    <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
    <transactionAmounts>
      <transactionShares><value>400</value></transactionShares>
      <transactionPricePerShare><value>25.00</value></transactionPricePerShare>
      <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
    </transactionAmounts>
  </nonDerivativeTransaction>
  <nonDerivativeTransaction>
    <transactionCoding><transactionCode>A</transactionCode></transactionCoding>
    <transactionAmounts>
      <transactionShares><value>5000</value></transactionShares>
      <transactionPricePerShare><value>0</value></transactionPricePerShare>
      <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
    </transactionAmounts>
  </nonDerivativeTransaction>
</ownershipDocument>"""


def test_parse_form4_solo_compra_venta_a_mercado():
    txs = edgar._parse_form4(_FORM4_XML)
    # P: +1000×10=+10000 · S: −400×25=−10000 · A (grant, precio 0): EXCLUIDO
    assert [t["code"] for t in txs] == ["P", "S"]
    assert txs[0]["usd"] == 10000.0 and txs[1]["usd"] == -10000.0


def test_parse_form4_xml_basura_no_rompe():
    assert edgar._parse_form4("<no-es-form4/>") == []
    assert edgar._parse_form4("basura {") == []


def test_form4_raw_xml_url_saca_prefijo_xsl():
    u = "https://www.sec.gov/Archives/edgar/data/1/000199/xslF345X06/ownership.xml"
    assert edgar._form4_raw_xml_url(u) == "https://www.sec.gov/Archives/edgar/data/1/000199/ownership.xml"


def test_get_insider_activity_net_usd(monkeypatch):
    from backend.services.edgar import RecentFiling
    from datetime import datetime
    monkeypatch.setattr(edgar, "_cache_read", lambda k: None)
    monkeypatch.setattr(edgar, "_cache_write", lambda k, d: None)
    monkeypatch.setattr(edgar, "get_recent_filings",
                        lambda t, **k: [RecentFiling("4", datetime(2026, 6, 1), "a-1", "d.xml", "u/xslF345X06/o.xml")])
    monkeypatch.setattr(edgar, "_fetch_text", lambda u: _FORM4_XML)
    a = edgar.get_insider_activity("X", dias=365)
    assert a.compras_netas_90d == 10000.0 and a.ventas_ejecutivos_90d == 10000.0
    assert a.net_usd == 0.0                                   # +10000 compra − 10000 venta
