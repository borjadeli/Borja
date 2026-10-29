"""SEC EDGAR client — fuente oficial de financials + insider activity + filings.

Endpoints usados:
- https://www.sec.gov/files/company_tickers.json (ticker ↔ CIK)
- https://data.sec.gov/submissions/CIK{10}.json (filings recientes)
- https://data.sec.gov/api/xbrl/companyfacts/CIK{10}.json (XBRL fundamentals)

Requisitos SEC:
- User-Agent identificable con email (doc: edgar.sec.gov/os-information.htm).
- Máx 10 req/s (respetado con cache en disco de 24h para companyfacts).

Diseño: si la API falla, se loguea y se devuelve None/estructura vacía.
Nunca raisea al llamador.
"""
from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from curl_cffi import requests as cffi_requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from backend.config import get_settings
from backend.utils import get_logger, utcnow

log = get_logger(__name__)

_BASE_TICKERS = "https://www.sec.gov/files/company_tickers.json"
_BASE_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik10}.json"
_BASE_COMPANYFACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"

_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "cache" / "edgar"
_CACHE_TTL_HOURS = 24
_MIN_REQ_INTERVAL = 0.11  # 10 req/s conservador


# ---------- Data classes (contrato estable para el Analista) ----------

@dataclass
class FinancialsQuarterly:
    ticker: str
    cik: str | None = None
    quarters: list[dict[str, Any]] = field(default_factory=list)  # ordenado viejo → nuevo
    cash: float | None = None
    total_debt: float | None = None
    fcf_ttm: float | None = None
    capex_ttm: float | None = None
    sbc_ttm: float | None = None      # stock-based compensation (add-back no-cash del CFO)
    diluted_shares_qtrs: list[float] = field(default_factory=list)  # weighted-avg diluidas por trimestre
    margen_bruto_ultimo: float | None = None
    margen_bruto_tendencia: list[float] = field(default_factory=list)
    revenue_ttm: float | None = None
    revenue_qtrs: list[float] = field(default_factory=list)
    organic_growth_yoy: float | None = None
    burn_rate_monthly: float | None = None
    shares_outstanding: float | None = None
    shares_as_of: str | None = None   # fecha 'end' del dato de shares (para flag de stale, doc 30)
    rpo: float | None = None          # Remaining Performance Obligations = backlog contratado no reconocido
    rpo_as_of: str | None = None      # fecha 'end' del RPO (vigencia del término operable, doc 28 §1)
    fuente: str = "SEC EDGAR"


@dataclass
class Form4Activity:
    ticker: str
    compras_netas_90d: float = 0.0  # USD comprado a MERCADO (código P) en la ventana
    ventas_ejecutivos_90d: float = 0.0  # USD vendido a MERCADO (código S) en la ventana
    transacciones: list[dict[str, Any]] = field(default_factory=list)
    ventana_dias: int = 90

    @property
    def net_usd(self) -> float:
        """Neto de compra/venta a mercado (código P − S) — el insumo de Pilar 3 (plata propia)."""
        return self.compras_netas_90d - self.ventas_ejecutivos_90d


@dataclass
class RecentFiling:
    tipo: str  # 10-Q, 10-K, 8-K, 4, etc.
    fecha: datetime
    accession_number: str
    primary_doc: str
    url: str
    items: str = ""   # ítems del 8-K separados por coma (p.ej. "1.01,2.02,9.01"); "" si no aplica


# ---------- Session y cache ----------

_session = None
_last_req = 0.0


def _get_session():
    global _session
    if _session is None:
        _session = cffi_requests.Session(impersonate="chrome")
    return _session


def _rate_limit():
    global _last_req
    now = time.time()
    elapsed = now - _last_req
    if elapsed < _MIN_REQ_INTERVAL:
        time.sleep(_MIN_REQ_INTERVAL - elapsed)
    _last_req = time.time()


def _cache_path(key: str) -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe = key.replace("/", "_").replace(":", "_")
    return _CACHE_DIR / f"{safe}.json"


def _cache_read(key: str) -> dict | None:
    path = _cache_path(key)
    if not path.exists():
        return None
    age_hours = (time.time() - path.stat().st_mtime) / 3600
    if age_hours > _CACHE_TTL_HOURS:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _cache_write(key: str, data: dict) -> None:
    try:
        _cache_path(key).write_text(json.dumps(data), encoding="utf-8")
    except Exception as e:
        log.warning("cache_write(%s) fallo: %s", key, e)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((Exception,)),
    reraise=False,
)
def _fetch(url: str) -> dict | None:
    _rate_limit()
    settings = get_settings()
    headers = {
        "User-Agent": settings.edgar_user_agent,
        "Accept-Encoding": "gzip, deflate",
        "Accept": "application/json",
        "Host": url.split("/")[2],
    }
    r = _get_session().get(url, headers=headers, timeout=20)
    if r.status_code == 429:
        raise RuntimeError("EDGAR 429 Too Many Requests")
    r.raise_for_status()
    return r.json()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((Exception,)),
    reraise=False,
)
def _fetch_text(url: str) -> str | None:
    """Como _fetch pero devuelve el cuerpo crudo (HTML/texto) de un documento.

    Para los documentos de filing (10-K), que no son JSON. Trunca a ~5 MB para
    no cargar a memoria un documento patológico en el thread único.
    """
    _rate_limit()
    settings = get_settings()
    headers = {
        "User-Agent": settings.edgar_user_agent,
        "Accept-Encoding": "gzip, deflate",
        "Accept": "text/html,application/xhtml+xml,text/plain",
        "Host": url.split("/")[2],
    }
    r = _get_session().get(url, headers=headers, timeout=30)
    if r.status_code == 429:
        raise RuntimeError("EDGAR 429 Too Many Requests")
    r.raise_for_status()
    return (r.text or "")[:5_000_000]


# ---------- Ticker → CIK ----------

_ticker_map_cache: dict[str, str] | None = None


def _load_ticker_map() -> dict[str, str]:
    global _ticker_map_cache
    if _ticker_map_cache is not None:
        return _ticker_map_cache
    cached = _cache_read("company_tickers")
    if cached is None:
        cached = _fetch(_BASE_TICKERS)
        if cached is None:
            return {}
        _cache_write("company_tickers", cached)
    # estructura: {"0":{"cik_str":320193,"ticker":"AAPL","title":"Apple Inc."},...}
    mapping: dict[str, str] = {}
    for _, row in (cached or {}).items():
        if isinstance(row, dict) and "ticker" in row and "cik_str" in row:
            mapping[row["ticker"].upper()] = str(row["cik_str"]).zfill(10)
    _ticker_map_cache = mapping
    return mapping


def get_cik(ticker: str) -> str | None:
    """Devuelve CIK de 10 dígitos para el ticker dado."""
    try:
        return _load_ticker_map().get(ticker.upper())
    except Exception as e:
        log.warning("get_cik(%s) fallo: %s", ticker, e)
        return None


# ---------- Company facts (fundamentals XBRL) ----------

def _get_companyfacts(cik10: str) -> dict | None:
    key = f"companyfacts_{cik10}"
    cached = _cache_read(key)
    if cached is not None:
        return cached
    data = _fetch(_BASE_COMPANYFACTS.format(cik10=cik10))
    if data:
        _cache_write(key, data)
    return data


def _extract_concept(facts: dict, tag: str, unit: str = "USD") -> list[dict]:
    """Devuelve lista de valores del concepto us-gaap o dei si existen."""
    for ns in ("us-gaap", "dei"):
        try:
            units = facts.get("facts", {}).get(ns, {}).get(tag, {}).get("units", {})
            if unit in units:
                return units[unit] or []
            if units:
                # tomar primer unit disponible (shares)
                return list(units.values())[0] or []
        except Exception:
            continue
    return []


def _revenue_concept(facts: dict) -> list[dict]:
    """Concatena entries de TODOS los tags de revenue conocidos.

    Empresas cambian tags en el tiempo (ej. Revenues → RevenueFromContract...
    con la adopción de ASC 606 en 2018-19). Concatenar asegura continuidad.
    La deduplicación posterior por end-date elige la entry correcta.
    """
    merged: list[dict] = []
    for tag in (
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
    ):
        data = _extract_concept(facts, tag)
        if data:
            merged.extend(data)
    return merged


def _is_quarterly(entry: dict) -> bool:
    """Un entry es un Q si es 10-Q y fp in Q1/Q2/Q3, o es el Q4 derivado de 10-K (start-end ~90d)."""
    if entry.get("form") not in ("10-Q", "10-K", "10-K/A", "10-Q/A"):
        return False
    try:
        start = datetime.fromisoformat(entry["start"])
        end = datetime.fromisoformat(entry["end"])
        delta_days = (end - start).days
        return 80 <= delta_days <= 100  # ~90 días
    except Exception:
        return False


def _quarterize_flow(entries: list[dict]) -> list[dict]:
    """Reconstruye trimestres de conceptos de FLUJO (revenue, income, OCF, capex) de-acumulando los
    períodos YTD. Los 10-Q/10-K reportan acumulado desde el inicio del año fiscal (3M/6M/9M/12M) y el
    **Q4 standalone NUNCA se reporta** (solo el 10-K anual) → sin esto falta el Q4 y el TTM se arma
    sobre 4 trimestres NO consecutivos. Q_n = YTD_n − YTD_{n-1}, solo si el delta abarca ~90 días."""
    es = [e for e in entries if e.get("start") and e.get("end") and e.get("val") is not None]
    # Agrupar por START: los períodos acumulados de un mismo año fiscal comparten el inicio (el FY
    # start), sea calendario o no (COHR jul, S ene). Agrupar por año calendario del end desalinea los
    # FY no calendario. Cada grupo con un start común es la escalera acumulada 3M/6M/9M/12M de ese FY.
    by_start: dict[str, list] = {}
    for e in es:
        by_start.setdefault(e["start"], []).append(e)
    out: list[dict] = []
    for lst in by_start.values():
        by_end: dict[str, dict] = {}                 # dedup por end dentro del grupo (última filing gana)
        for e in lst:
            k = e["end"]
            if k not in by_end or e.get("accn", "") > by_end[k].get("accn", ""):
                by_end[k] = e
        cum = sorted(by_end.values(), key=lambda e: e["end"])
        prev_val, prev_end = 0.0, None
        for e in cum:
            span_start = prev_end or e["start"]
            try:
                days = (datetime.fromisoformat(e["end"]) - datetime.fromisoformat(span_start)).days
            except (ValueError, TypeError):
                prev_val, prev_end = e["val"], e["end"]
                continue
            if 80 <= days <= 100:
                out.append({"end": e["end"], "start": span_start, "val": e["val"] - prev_val,
                            "form": e.get("form"), "accn": e.get("accn")})
            prev_val, prev_end = e["val"], e["end"]
    return out


def _sorted_flow_quarters(entries: list[dict], n: int = 12) -> list[dict]:
    """Como _sorted_quarters pero para conceptos de FLUJO: reconstruye los trimestres faltantes
    (sobre todo Q4) de-acumulando los YTD, y prefiere el standalone reportado donde existe."""
    by_end: dict[str, dict] = {e["end"]: e for e in _quarterize_flow(entries)}
    for e in entries:                          # el trimestre reportado directo manda sobre el derivado
        if _is_quarterly(e):
            by_end[e["end"]] = e
    ordered = sorted(by_end.values(), key=lambda x: x["end"])
    return ordered[-n:]


def _sorted_quarters(entries: list[dict], n: int = 12) -> list[dict]:
    """Filtra quarters (~90 días) y deduplica por end-date.

    Dedup priority: 10-Q > 10-K > resto. En empate, el de mayor accn (más reciente).
    """
    quarterly = [e for e in entries if _is_quarterly(e)]

    def _priority(e: dict) -> tuple:
        form = e.get("form", "")
        form_rank = {"10-Q": 0, "10-Q/A": 1, "10-K": 2, "10-K/A": 3}.get(form, 9)
        return (form_rank, e.get("accn", ""))

    by_end: dict[str, dict] = {}
    for e in quarterly:
        key = e["end"]
        current = by_end.get(key)
        if current is None or _priority(e) < _priority(current):
            by_end[key] = e
    ordered = sorted(by_end.values(), key=lambda x: x["end"])
    return ordered[-n:]


def _sorted_instantaneous(entries: list[dict], n: int = 1) -> list[dict]:
    """Para balance sheet items — un valor por fecha 'end' sin 'start'."""
    instantaneous = [e for e in entries if "end" in e and "start" not in e]
    by_end: dict[str, dict] = {}
    for e in instantaneous:
        key = e["end"]
        if key not in by_end or e.get("form", "") in ("10-Q", "10-K"):
            by_end[key] = e
    ordered = sorted(by_end.values(), key=lambda x: x["end"])
    return ordered[-n:]


def _latest_inst(facts: dict, tag: str) -> float | None:
    e = _sorted_instantaneous(_extract_concept(facts, tag), n=1)
    return e[0]["val"] if e else None


def _extract_rpo(facts: dict) -> tuple[float | None, str | None]:
    """RPO agregado (RevenueRemainingPerformanceObligation) = backlog contratado NO reconocido.
    Instantáneo (as-of). Dato DURO (XBRL, sin LLM) para el escenario operable del compiler (doc 28 §1).
    El tag agregado sí está en companyfacts (verificado OKTA/TENB/LEU/BWXT/S); el desglose por banda de
    tiempo es dimensional y cae en el techo estructural → acá solo el total. Devuelve (val, fecha end)."""
    e = _sorted_instantaneous(_extract_concept(facts, "RevenueRemainingPerformanceObligation"), n=1)
    if not e:
        return None, None
    return e[0].get("val"), e[0].get("end")


def _extract_total_debt(facts: dict) -> float | None:
    """Deuda total. Los emisores la etiquetan distinto (term loan, convertibles, finance leases):
    primero un rollup total; si no existe, suma de FAMILIAS de instrumentos (cada familia = un
    instrumento, se toma el primer tag disponible → evita doble conteo del mismo instrumento)."""
    rollup = None                                # 1. rollup total (si existe y es plausible)
    for tag in ("LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities",
                "LongTermDebt", "DebtLongtermAndShorttermCombinedAmount"):
        v = _latest_inst(facts, tag)
        if v is not None and v > 0:
            rollup = v
            break
    familias = (                                  # 2. suma de familias (cada familia = un instrumento)
        ("SecuredLongTermDebt", "LongTermDebtNoncurrent", "SecuredDebt", "LongTermLoansPayable"),
        ("ConvertibleDebtNoncurrent", "ConvertibleLongTermNotesPayable", "ConvertibleNotesPayable",
         "ConvertibleDebtCurrent", "ConvertibleSeniorNotesNoncurrent"),
        ("SeniorNotesNoncurrent", "SeniorNotes"),
        ("LongTermDebtCurrent", "SecuredDebtCurrent"),
    )
    total, found = 0.0, False
    for fam in familias:
        for tag in fam:
            v = _latest_inst(facts, tag)
            if v is not None:
                total += v
                found = True
                break
    fam_sum = total if found else None
    # Preferir el rollup (evita el doble conteo de familias que solapan, ej. COHR), SALVO que sea
    # claramente parcial (<50% de la suma de instrumentos, ej. AAOI LongTermDebt=34 vs 170.7 real).
    if rollup is not None and fam_sum is not None:
        return rollup if rollup >= 0.5 * fam_sum else fam_sum
    return rollup if rollup is not None else fam_sum


def _extract_cash(facts: dict) -> float | None:
    """Caja + inversiones líquidas de corto plazo. El 'piso' debe ser valor líquido, no net cash
    (excluir short-term investments hace el piso demasiado conservador — auditoría 2026-08)."""
    combined = _latest_inst(facts, "CashCashEquivalentsAndShortTermInvestments")
    # cash&equiv: elegir el tag con la fecha MÁS RECIENTE (evita el stale — LTBR quedó en 2023).
    cash_cands = []
    for t in ("CashAndCashEquivalentsAtCarryingValue",
              "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"):
        e = _sorted_instantaneous(_extract_concept(facts, t), n=1)
        if e:
            cash_cands.append((e[0].get("end", ""), e[0]["val"]))
    cash = max(cash_cands, key=lambda c: c[0])[1] if cash_cands else None
    sti = (_latest_inst(facts, "ShortTermInvestments")
           or _latest_inst(facts, "MarketableSecuritiesCurrent")
           or _latest_inst(facts, "AvailableForSaleSecuritiesDebtSecuritiesCurrent"))
    cash_sti = None if (cash is None and sti is None) else (cash or 0.0) + (sti or 0.0)
    # MAX: un tag combinado parcial (ej. AAOI = 8M) no le gana a caja+ST inv real.
    vals = [v for v in (combined, cash_sti) if v is not None]
    return max(vals) if vals else None


def _extract_shares(facts: dict) -> tuple[float | None, str | None]:
    """Acciones en circulación: el candidato MÁS RECIENTE (evita el dei stale — LEU quedó en 13.67M
    de 2022); en empate de fecha, prefiere outstanding/issued sobre weighted-average.
    Devuelve (valor, fecha 'end' del dato elegido) — la fecha permite flaggear shares STALE (doc 30)."""
    cands: list[tuple] = []                      # (end, val, prioridad) — prioridad menor = mejor
    for tag, prio in (("EntityCommonStockSharesOutstanding", 0), ("CommonStockSharesIssued", 1)):
        e = _sorted_instantaneous(_extract_concept(facts, tag), n=1)
        if e:
            cands.append((e[0].get("end", ""), e[0]["val"], prio))
    e = _sorted_quarters(_extract_concept(facts, "WeightedAverageNumberOfSharesOutstandingBasic"), n=1)
    if e:
        cands.append((e[0].get("end", ""), e[0]["val"], 2))
    if not cands:
        return None, None
    best = max(cands, key=lambda c: (c[0], -c[2]))
    return best[1], best[0]


def _capex_quarters(facts: dict, n: int = 8) -> list[dict]:
    """CapEx por trimestre. Los emisores lo parten en tags distintos (PP&E + Other; algunos usan
    ProductiveAssets). Suma los componentes de PP&E por end-date (complementarios); si están stale/
    ausentes, cae a otros tags. Evita tomar un tag congelado (UUUU: PP&E en 2019=0, capex real en Other)."""
    def _by(tag: str) -> dict:
        return {e["end"]: e["val"] for e in _quarterize_flow(_extract_concept(facts, tag))}
    ppe = _by("PaymentsToAcquirePropertyPlantAndEquipment")
    other = _by("PaymentsToAcquireOtherPropertyPlantAndEquipment")
    ends = set(ppe) | set(other)
    comb = [{"end": e, "start": e, "val": ppe.get(e, 0.0) + other.get(e, 0.0)} for e in ends]
    comb = [c for c in comb if c["val"]]                    # descarta ceros (tags congelados)
    if comb:
        return sorted(comb, key=lambda x: x["end"])[-n:]
    for tag in ("PaymentsToAcquireProductiveAssets", "PaymentsForCapitalImprovements",
                "PaymentsToAcquireMachineryAndEquipment"):
        d = _quarterize_flow(_extract_concept(facts, tag))
        if d:
            return sorted(d, key=lambda x: x["end"])[-n:]
    return []


@dataclass
class SerieCrecimiento:
    """Series trimestrales ALINEADAS por fecha (viejo→nuevo) para el reverse-DCF (doc 36 §3). Todo XBRL.
    revenue/gross_profit son flujos de-acumulados; diluted_shares es el promedio ponderado del período
    (para per-share: crecer emitiendo NO es crecer para el accionista)."""
    ticker: str
    fechas: list[str] = field(default_factory=list)
    revenue: list[float | None] = field(default_factory=list)
    gross_profit: list[float | None] = field(default_factory=list)
    diluted_shares: list[float | None] = field(default_factory=list)
    operating_income: list[float | None] = field(default_factory=list)   # para opex = GP − OI (ruteo, doc 42)


def _filed_hasta(entries: list[dict], as_of: str | None) -> list[dict]:
    """Filtra entries XBRL a las conocidas públicamente en `as_of` (`filed ≤ as_of`) — reconstrucción
    POINT-IN-TIME sin look-ahead (doc 40 Bloque 0.2). None = sin filtro (todas). Entry sin `filed` → se descarta
    bajo filtro (conservador: si no sé cuándo se conoció, no la uso as-of)."""
    if as_of is None:
        return entries
    return [e for e in entries if e.get("filed") and e["filed"][:10] <= as_of[:10]]


def serie_crecimiento(ticker: str, n_q: int = 16, *, as_of: str | None = None) -> SerieCrecimiento:
    """Series trimestrales alineadas (revenue, gross profit, diluted shares) por end-date, para computar
    `g_D` per-share (doc 36 §3). Reúsa `_sorted_flow_quarters` (rev/GP de-acumulados) + `_sorted_quarters`
    (diluted, promedio del período). n_q=16 → alcanza para CAGR 3FY (TTM vigente vs TTM de hace 3 años).
    `as_of` (ISO date) reconstruye la serie como se conocía en esa fecha (backtest point-in-time, filed ≤ as_of)."""
    out = SerieCrecimiento(ticker=ticker.upper())
    cik = get_cik(ticker)
    if not cik:
        return out
    facts = _get_companyfacts(cik)
    if not facts:
        return out
    rev_by = {e["end"]: e["val"] for e in _sorted_flow_quarters(_filed_hasta(_revenue_concept(facts), as_of), n=n_q + 4)}
    gp_by = {e["end"]: e["val"] for e in _sorted_flow_quarters(_filed_hasta(_extract_concept(facts, "GrossProfit"), as_of), n=n_q + 4)}
    if not gp_by:                         # fallback: GP = revenue − COGS
        cogs_by = {e["end"]: e["val"] for e in _sorted_flow_quarters(_filed_hasta(
            _extract_concept(facts, "CostOfRevenue") or _extract_concept(facts, "CostOfGoodsAndServicesSold"), as_of),
            n=n_q + 4)}
        gp_by = {end: rev_by[end] - cogs_by[end] for end in rev_by if end in cogs_by}
    dsh_by = {e["end"]: e["val"] for e in _sorted_quarters(_filed_hasta(
        _extract_concept(facts, "WeightedAverageNumberOfDilutedSharesOutstanding"), as_of), n=n_q + 4)}
    oi_by = {e["end"]: e["val"] for e in _sorted_flow_quarters(_filed_hasta(
        _extract_concept(facts, "OperatingIncomeLoss"), as_of), n=n_q + 4)}
    for end in sorted(rev_by.keys())[-n_q:]:
        out.fechas.append(end)
        out.revenue.append(rev_by.get(end))
        out.gross_profit.append(gp_by.get(end))
        out.diluted_shares.append(dsh_by.get(end))
        out.operating_income.append(oi_by.get(end))
    return out


def get_financials_quarterly(ticker: str, periodos: int = 8) -> FinancialsQuarterly:
    """Revenue, margen bruto, cash, deuda, FCF por trimestre desde XBRL EDGAR."""
    result = FinancialsQuarterly(ticker=ticker.upper())
    cik = get_cik(ticker)
    if not cik:
        log.warning("get_financials_quarterly(%s): CIK no encontrado", ticker)
        return result
    result.cik = cik

    facts = _get_companyfacts(cik)
    if not facts:
        return result

    # Revenue (quarterly) — de-acumulando YTD (reconstruye Q4 y trimestres faltantes)
    rev_entries = _sorted_flow_quarters(_revenue_concept(facts), n=periodos + 4)

    # COGS / Gross profit
    gp_entries = _sorted_flow_quarters(_extract_concept(facts, "GrossProfit"), n=periodos + 4)
    cogs_entries = []
    if not gp_entries:
        cogs_entries = _sorted_flow_quarters(
            _extract_concept(facts, "CostOfRevenue") or _extract_concept(facts, "CostOfGoodsAndServicesSold"),
            n=periodos + 4,
        )

    # Operating / Net income
    op_entries = _sorted_flow_quarters(_extract_concept(facts, "OperatingIncomeLoss"), n=periodos)
    ni_entries = _sorted_flow_quarters(_extract_concept(facts, "NetIncomeLoss"), n=periodos)

    # Index by end-date
    def _by_end(lst: list[dict]) -> dict[str, float]:
        return {e["end"]: e["val"] for e in lst}

    rev_by = _by_end(rev_entries)
    gp_by = _by_end(gp_entries)
    cogs_by = _by_end(cogs_entries)
    op_by = _by_end(op_entries)
    ni_by = _by_end(ni_entries)

    ends_ordered = sorted(rev_by.keys())[-periodos:]
    for end in ends_ordered:
        rev = rev_by.get(end)
        gp = gp_by.get(end)
        if gp is None and rev is not None and cogs_by.get(end) is not None:
            gp = rev - cogs_by[end]
        margen = round(gp / rev * 100, 2) if (rev and gp) else None
        result.quarters.append({
            "fecha": end,
            "revenue": rev,
            "gross_profit": gp,
            "operating_income": op_by.get(end),
            "net_income": ni_by.get(end),
            "margen_bruto_pct": margen,
        })

    revs = [q["revenue"] for q in result.quarters if q["revenue"]]
    if len(revs) >= 4:
        result.revenue_ttm = sum(revs[-4:])
    result.revenue_qtrs = revs

    margenes = [q["margen_bruto_pct"] for q in result.quarters if q["margen_bruto_pct"] is not None]
    result.margen_bruto_tendencia = margenes[-4:]
    if margenes:
        result.margen_bruto_ultimo = margenes[-1]

    # Crecimiento YoY proxy
    if len(revs) >= 5 and revs[-5] > 0:
        result.organic_growth_yoy = round((revs[-1] / revs[-5] - 1) * 100, 2)

    # Balance sheet (helpers robustos — ver auditoría 2026-08: deuda multi-tag, caja+ST inv, shares recientes)
    result.cash = _extract_cash(facts)
    result.total_debt = _extract_total_debt(facts)
    sh, sh_asof = _extract_shares(facts)
    if sh is not None:
        result.shares_outstanding = sh
        result.shares_as_of = sh_asof
    result.rpo, result.rpo_as_of = _extract_rpo(facts)   # backlog contratado (doc 28 §1)

    # FCF trailing 4Q = OperatingCashFlow - CapEx
    ocf = _sorted_flow_quarters(_extract_concept(facts, "NetCashProvidedByUsedInOperatingActivities"), n=8)
    capex = _capex_quarters(facts, n=8)     # suma componentes PP&E + fallback; evita tags congelados
    ocf_by = _by_end(ocf)
    capex_by = _by_end(capex)
    # FCF por trimestre en cada quarter (para el gate/margen de valuación, doc 28 §3): OCF − CapEx.
    for q in result.quarters:
        end = q.get("fecha")
        if end in ocf_by:
            q["ocf"] = ocf_by[end]
            q["fcf"] = ocf_by[end] - capex_by.get(end, 0.0)
        else:
            q["ocf"] = None
            q["fcf"] = None
    fcf_vals = []
    for end in sorted(ocf_by.keys())[-4:]:
        if end in capex_by:
            fcf_vals.append(ocf_by[end] - capex_by[end])  # capex es positivo en XBRL
        else:
            fcf_vals.append(ocf_by[end])
    if fcf_vals:
        result.fcf_ttm = sum(fcf_vals)
        if result.fcf_ttm < 0:
            result.burn_rate_monthly = abs(result.fcf_ttm) / 12
    # CapEx TTM (para el cross-validator: capex nulo con revenue material = tag faltante).
    caps = [capex_by[end] for end in sorted(ocf_by.keys())[-4:] if end in capex_by]
    result.capex_ttm = sum(caps) if caps else None

    # Acciones diluidas por trimestre (weighted-avg) — para la trayectoria de dilución (doc 31 §5).
    # NO es aditivo (es un promedio del período) → _sorted_quarters (standalone ~90d), NO de-acumular.
    dsh = _sorted_quarters(_extract_concept(facts, "WeightedAverageNumberOfDilutedSharesOutstanding"), n=8)
    result.diluted_shares_qtrs = [e["val"] for e in dsh]

    # SBC TTM — costo real para el accionista (dilución); owner_fcf = FCF − SBC (auditoría build 2026-08).
    sbc_raw = (_extract_concept(facts, "ShareBasedCompensation")
               or _extract_concept(facts, "AllocatedShareBasedCompensationExpense")
               or _extract_concept(facts, "ShareBasedCompensationExpense"))
    sbc = _sorted_flow_quarters(sbc_raw, n=8)
    sbc_by = _by_end(sbc)
    sbc_vals = [sbc_by[end] for end in sorted(sbc_by.keys())[-4:]]
    result.sbc_ttm = sum(sbc_vals) if len(sbc_vals) >= 4 else None

    return result


# ---------- Submissions (filings recientes + Form 4) ----------

def _get_submissions(cik10: str) -> dict | None:
    # submissions se actualizan más seguido → cache más corto
    key = f"submissions_{cik10}"
    cached = _cache_read(key)
    if cached is not None:
        age_h = (time.time() - _cache_path(key).stat().st_mtime) / 3600
        if age_h < 2:
            return cached
    data = _fetch(_BASE_SUBMISSIONS.format(cik10=cik10))
    if data:
        _cache_write(key, data)
    return data


def get_recent_filings(ticker: str, tipos: tuple[str, ...] = ("10-Q", "10-K", "8-K", "4"),
                       dias: int = 90) -> list[RecentFiling]:
    """Filings recientes filtrados por tipo."""
    cik = get_cik(ticker)
    if not cik:
        return []
    sub = _get_submissions(cik)
    if not sub:
        return []
    recent = sub.get("filings", {}).get("recent", {})
    if not recent:
        return []
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accns = recent.get("accessionNumber", [])
    prim_docs = recent.get("primaryDocument", [])
    items_l = recent.get("items", [])

    result: list[RecentFiling] = []
    cutoff = utcnow() - timedelta(days=dias)
    for i, form in enumerate(forms):
        if form not in tipos:
            continue
        try:
            fecha = datetime.fromisoformat(dates[i])
        except Exception:
            continue
        if fecha < cutoff:
            continue
        accn = accns[i]
        prim = prim_docs[i] if i < len(prim_docs) else ""
        accn_clean = accn.replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn_clean}/{prim}"
        items = items_l[i] if i < len(items_l) else ""
        result.append(RecentFiling(tipo=form, fecha=fecha, accession_number=accn, primary_doc=prim,
                                   url=url, items=items))
    return result


# Códigos de transacción Form 4 que son compra/venta A MERCADO (plata propia, señal discrecional).
# Se EXCLUYE todo lo demás: A (grant/award), M (ejercicio de opción), F (retención p/ impuestos),
# G (regalo), C (conversión), X (ejercicio in-the-money)… no informan convicción del insider.
_FORM4_MERCADO = {"P": 1.0, "S": -1.0}   # P = compra abierta (+), S = venta abierta (−)


def _form4_raw_xml_url(url: str) -> str:
    """El `primaryDocument` de un Form 4 es el render XSL (HTML); el XML crudo está en la misma carpeta
    SIN el prefijo `xslF345X0N/`. Ej: `.../accn/xslF345X06/ownership.xml` → `.../accn/ownership.xml`."""
    return re.sub(r"xslF345X\d+/", "", url)


def _parse_form4(xml_text: str) -> list[dict]:
    """Transacciones NO derivadas A MERCADO (código P/S) de un Form 4 → [{code, usd_firmado}]. Ignora
    grants/ejercicios/tax/regalos (no son compra/venta discrecional). `usd_firmado` > 0 compra, < 0 venta."""
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return []
    out: list[dict] = []
    for t in root.findall(".//nonDerivativeTransaction"):
        code = (t.findtext(".//transactionCoding/transactionCode") or "").strip()
        signo = _FORM4_MERCADO.get(code)
        if signo is None:
            continue
        try:
            shares = float(t.findtext(".//transactionShares/value") or 0)
            price = float(t.findtext(".//transactionPricePerShare/value") or 0)
        except (ValueError, TypeError):
            continue
        usd = shares * price
        if usd <= 0:                          # sin precio (grant embebido) o basura → no computa
            continue
        out.append({"code": code, "usd": signo * usd})
    return out


def get_insider_activity(ticker: str, dias: int = 180, max_filings: int = 60) -> Form4Activity:
    """Form 4 real: parsea el XML de cada filing y suma compra/venta A MERCADO (código P/S) en USD.

    `net_usd` = comprado − vendido a mercado (plata propia) → insumo de Pilar 3 (Ejecución por evidencia).
    Solo P/S (compra/venta discrecional); grants, ejercicios y tax-withholding NO cuentan. Cacheado por
    (ticker, ventana) 24h — el XML de un Form 4 es inmutable, y así una re-evaluación no re-baja 60 docs.
    `max_filings` acota el costo de red (los más recientes primero)."""
    key = f"insider_{ticker.upper()}_{dias}"
    cached = _cache_read(key)
    if cached is not None:
        return Form4Activity(**cached)
    form4s = get_recent_filings(ticker, tipos=("4",), dias=dias)
    compras = ventas = 0.0
    txs: list[dict] = []
    for f in form4s[:max_filings]:
        xml = _fetch_text(_form4_raw_xml_url(f.url))
        if not xml:
            continue
        for tx in _parse_form4(xml):
            if tx["usd"] > 0:
                compras += tx["usd"]
            else:
                ventas += -tx["usd"]
            txs.append({"fecha": f.fecha.isoformat(), "code": tx["code"], "usd": round(tx["usd"], 2)})
    act = Form4Activity(ticker=ticker.upper(), compras_netas_90d=round(compras, 2),
                        ventas_ejecutivos_90d=round(ventas, 2), transacciones=txs, ventana_dias=dias)
    _cache_write(key, asdict(act))
    return act


def get_shares_outstanding(ticker: str) -> float | None:
    """Último valor reportado de shares outstanding — para computar market cap."""
    f = get_financials_quarterly(ticker, periodos=1)
    return f.shares_outstanding


def get_ipo_date(ticker: str) -> datetime | None:
    """Aproxima la fecha de IPO usando el filing más antiguo en submissions.json."""
    cik = get_cik(ticker)
    if not cik:
        return None
    sub = _get_submissions(cik)
    if not sub:
        return None
    recent = sub.get("filings", {}).get("recent", {})
    files_pages = sub.get("filings", {}).get("files", []) or []
    fechas: list[datetime] = []
    for d in (recent.get("filingDate") or []):
        try:
            fechas.append(datetime.fromisoformat(d))
        except Exception:
            continue
    # Si hay páginas históricas, no se cargan acá (alcanza con la "recent" para detectar IPO < 2y).
    if not fechas:
        return None
    return min(fechas)


def count_capital_raise_filings(ticker: str, dias: int = 730) -> dict:
    """Cuenta filings S-1, S-3, 424B en los últimos N días — proxy de Capital Raise Risk.

    S-1/S-3 son shelf registrations (potencial dilución).
    424B es prospectus supplement (oferta concreta).
    """
    filings = get_recent_filings(ticker, tipos=("S-1", "S-3", "S-3ASR", "424B5", "424B3", "424B4"), dias=dias)
    s_filings = [f for f in filings if f.tipo.startswith("S-")]
    prospectus = [f for f in filings if f.tipo.startswith("424B")]
    return {
        "ticker": ticker.upper(),
        "ventana_dias": dias,
        "shelf_total": len(s_filings),
        "prospectus_total": len(prospectus),
        "ultimo_shelf_fecha": s_filings[0].fecha.isoformat() if s_filings else None,
        "ultimo_prospectus_fecha": prospectus[0].fecha.isoformat() if prospectus else None,
    }


def get_dilution_pct_3y(ticker: str) -> float | None:
    """% de dilución de shares en ~3 años. None si no hay datos suficientes.

    Lee la serie de CommonStockSharesOutstanding desde companyfacts y compara
    el valor más reciente contra uno de hace 36 meses (±6 meses tolerancia).
    """
    cik = get_cik(ticker)
    if not cik:
        return None
    facts = _get_companyfacts(cik)
    if not facts:
        return None
    candidates = (
        "CommonStockSharesOutstanding",
        "EntityCommonStockSharesOutstanding",
        "CommonStockSharesIssued",
    )
    entries: list[dict] = []
    for tag in candidates:
        e = _extract_concept(facts, tag, unit="shares")
        if e:
            entries = e
            break
    if not entries:
        return None
    # ordenar por fecha 'end' descendente
    entries_sorted = sorted(
        [x for x in entries if x.get("end") and x.get("val")],
        key=lambda x: x["end"],
        reverse=True,
    )
    if not entries_sorted:
        return None
    actual = entries_sorted[0].get("val")
    actual_fecha = datetime.fromisoformat(entries_sorted[0]["end"])
    objetivo = actual_fecha - timedelta(days=3 * 365)
    # Buscar la entrada cuya fecha esté más cerca a "hace 3 años"
    pasado_entry = min(
        entries_sorted,
        key=lambda x: abs((datetime.fromisoformat(x["end"]) - objetivo).days),
        default=None,
    )
    if not pasado_entry:
        return None
    delta_dias = abs((datetime.fromisoformat(pasado_entry["end"]) - objetivo).days)
    if delta_dias > 365:
        return None  # tolerancia de ±1 año
    pasado = pasado_entry.get("val")
    if not actual or not pasado:
        return None
    return round(((actual - pasado) / pasado) * 100.0, 2)


def get_shares_growth(ticker: str) -> dict:
    """Crecimiento REALIZADO de acciones a 12 y 24 meses (doc 31 §5, eje dilución construible hoy).

    Regla defensiva multi-clase (triangulación 2026-08): companyfacts puede traer varias entries por la
    misma fecha `end` (una por clase de acción). Para cada fecha se SUMA el conjunto de valores distintos
    del filing más reciente (accn) → total de acciones de la portada. **Sumar clases neutraliza el
    artefacto Up-C**: si Class B se convierte en A, A sube y B baja pero el TOTAL A+B queda plano (la
    conversión no es dilución económica — era el "236%/año" espurio de SMR). Cuando se detecta ≥2 clases
    simultáneas se marca `up_c_suspect` igual: no siempre companyfacts trae todas las clases, así que el
    consumidor debe anclar en burn_yield forward y tratar el número como informativo, no decisorio.

    Devuelve {g_12m, g_24m (fracción, no %), fuente, up_c_suspect, as_of} — campos None si no computable.
    """
    vacio = {"g_12m": None, "g_24m": None, "fuente": None, "up_c_suspect": False, "as_of": None}
    cik = get_cik(ticker)
    if not cik:
        return vacio
    facts = _get_companyfacts(cik)
    if not facts:
        return vacio
    raw: list[dict] = []
    fuente = None
    for tag in ("EntityCommonStockSharesOutstanding", "CommonStockSharesOutstanding", "CommonStockSharesIssued"):
        e = _extract_concept(facts, tag, unit="shares")
        if e:
            raw, fuente = e, f"dei:{tag}"
            break
    if not raw:
        return vacio
    # end -> accn -> set(vals distintos). Solo instantáneos (cover-page/balance: 'end' sin 'start').
    by_end_accn: dict[str, dict[str, set]] = {}
    for x in raw:
        if x.get("end") and x.get("val") and "start" not in x:
            by_end_accn.setdefault(x["end"], {}).setdefault(x.get("accn") or "", set()).add(x["val"])
    serie: list[tuple[str, float]] = []            # (end, total shares) una fila por fecha
    up_c = False
    for end, accns in by_end_accn.items():
        vals = accns[max(accns)]                   # el filing más reciente para esa fecha
        if len(vals) >= 2:                         # ≥2 clases simultáneas → Up-C/multi-clase
            up_c = True
        serie.append((end, float(sum(vals))))      # suma de clases = total (neutraliza B→A)
    if len(serie) < 2:
        return {**vacio, "fuente": fuente, "up_c_suspect": up_c}
    serie.sort(key=lambda p: p[0])
    as_of, actual = serie[-1]
    actual_fecha = datetime.fromisoformat(as_of)

    def _delta(dias: int) -> float | None:
        objetivo = actual_fecha - timedelta(days=dias)
        cand = min(serie, key=lambda p: abs((datetime.fromisoformat(p[0]) - objetivo).days))
        if abs((datetime.fromisoformat(cand[0]) - objetivo).days) > 75:   # tolerancia ±75d (desfasaje filing)
            return None
        base = cand[1]
        if not base or base <= 0:
            return None
        return round((actual - base) / base, 4)

    return {"g_12m": _delta(365), "g_24m": _delta(730), "fuente": fuente,
            "up_c_suspect": up_c, "as_of": as_of}


def get_related_party_pct(ticker: str) -> dict:
    """Fracción del revenue que viene de PARTE RELACIONADA — DETERMINISTA desde XBRL (sin LLM).

    Separa el caso dominante (SMR: Fluor ~92%) del inmaterial (SDGR ~0.005%, MTSI ~0.14%) que casi todo
    10-Q tiene. `RevenueFromRelatedParties` (flujo) se cuarteriza y se alinea por `end` con el revenue
    total (`_revenue_concept`). Se toma el trimestre MÁS RECIENTE con rp>0; si ese no es el último Q, la
    relación terminó (SMR: Fluor divistió) → `stale=True` (el operador ve el flag). Si no hay tag →
    pct=None (nombres text-only con related-party inmaterial → correctamente NO se excluyen).

    Devuelve {pct, rp_amount, total, xbrl, as_of, stale}. Reemplaza el hecho binario del LLM (que
    sobre-disparaba ante cualquier mención de related-party sin juzgar materialidad).
    """
    vacio = {"pct": None, "rp_amount": None, "total": None, "xbrl": False, "as_of": None, "stale": False}
    cik = get_cik(ticker)
    if not cik:
        return vacio
    facts = _get_companyfacts(cik)
    if not facts:
        return vacio
    rp_raw = _extract_concept(facts, "RevenueFromRelatedParties")
    if not rp_raw:
        return vacio                                   # sin tag XBRL → related-party inmaterial/ausente
    # Revenue total por PERÍODO EXACTO (start,end) — el numerador y el denominador deben ser el MISMO
    # período (así el ratio es correcto sea 3M/6M/FY). Es la alineación que verifican los filings.
    rev_by = {}
    for e in _revenue_concept(facts):
        if e.get("start") and e.get("end") and e.get("val"):
            rev_by[(e["start"], e["end"])] = e["val"]
    pares = []                                          # (end, rp_val, total) de períodos con rp>0 alineados
    for e in rp_raw:
        tot = rev_by.get((e.get("start"), e.get("end")))
        if e.get("val") and tot and tot > 0:
            pares.append((e["end"], e["val"], tot))
    if not pares:
        return {**vacio, "xbrl": True}
    pares.sort()
    end, rp_val, total = pares[-1]                      # el período MÁS RECIENTE con rp>0
    ult_rev = max((k[1] for k in rev_by), default=end)  # revenue más nuevo → medir antigüedad del rp
    try:
        gap = (datetime.fromisoformat(ult_rev[:10]) - datetime.fromisoformat(end[:10])).days
    except (ValueError, TypeError):
        gap = 0
    if gap > 730:                                       # rp >2 años más viejo que el revenue → histórico, ignorar
        return {**vacio, "xbrl": True, "as_of": end, "stale": True}
    return {"pct": round(rp_val / total, 4), "rp_amount": rp_val, "total": total,
            "xbrl": True, "as_of": end, "stale": gap > 100}


# ---------- Going concern (Fase 0 migración — fuga activa → CRR-crítico) ----------

# Términos que, pegados a "substantial doubt", indican que la duda fue NEGADA o
# disuelta (no hay going concern real). Filtran los falsos positivos más comunes.
# Word-boundary para no fallar cuando la negación abre la ventana (sin espacio
# previo) y para cubrir variantes (alleviate/alleviated/alleviating).
_GC_NEGACION_RE = re.compile(
    r"\b(no|not|without|any|no longer|"
    r"alleviat\w*|eliminat\w*|mitigat\w*|removed|relieved|resolved)\b",
    re.IGNORECASE,
)


def _scan_going_concern(text: str | None) -> tuple[bool, str | None]:
    """Detecta lenguaje afirmativo de going concern (ASC 205-40) en un filing.

    Función pura y testeable. La firma dura es la coexistencia de "substantial
    doubt" y "going concern" en proximidad, descartando las formas negadas
    ("no substantial doubt … going concern", "plans alleviate the substantial
    doubt"). Conservadora a propósito: un falso positivo fuerza CRR-crítico
    (→ Eliminada), así que prioriza precisión sobre recall.

    Devuelve (detectado, snippet_evidencia).
    """
    if not text:
        return False, None
    clean = re.sub(r"<[^>]+>", " ", text)        # tags HTML
    clean = re.sub(r"&#?\w+;", " ", clean)        # entidades HTML
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean:
        return False, None

    for m in re.finditer(r"substantial doubt", clean, re.IGNORECASE):
        start, end = m.start(), m.end()
        # Proximidad: "going concern" hasta 200 chars antes o después.
        around = clean[max(0, start - 200):end + 200].lower()
        if "going concern" not in around:
            continue
        # Guarda de negación: 45 chars antes de "substantial doubt".
        pre = clean[max(0, start - 45):start]
        if _GC_NEGACION_RE.search(pre):
            continue
        snippet = clean[max(0, start - 70):end + 130].strip()
        return True, snippet
    return False, None


def detect_going_concern(ticker: str) -> dict:
    """Busca going concern afirmativo en el último 10-K del ticker.

    Resultado cacheado por accession number (un filing es inmutable). Nunca
    raisea: si EDGAR no responde devuelve detected=False, igual que el resto
    del módulo.

    Devuelve {detected, evidencia, filing_url, filing_fecha}.
    """
    result = {"detected": False, "evidencia": None, "filing_url": None, "filing_fecha": None}
    try:
        filings = get_recent_filings(ticker, tipos=("10-K", "10-K/A"), dias=420)
        if not filings:
            return result
        latest = max(filings, key=lambda f: f.fecha)
        cache_key = f"going_concern_{latest.accession_number}"
        cached = _cache_read(cache_key)
        if cached is not None:
            return cached

        result["filing_url"] = latest.url
        result["filing_fecha"] = latest.fecha.isoformat()
        text = _fetch_text(latest.url)
        detected, snippet = _scan_going_concern(text)
        if detected:
            result["detected"] = True
            result["evidencia"] = (
                f"going concern en {latest.tipo} ({latest.fecha.date()}): \"…{snippet}…\""
            )
        _cache_write(cache_key, result)
    except Exception as e:  # noqa: BLE001
        log.warning("detect_going_concern(%s) falló: %s", ticker, e)
    return result


def ping() -> bool:
    """Healthcheck: verifica que el mapa de tickers se puede cargar."""
    try:
        m = _load_ticker_map()
        return bool(m) and len(m) > 1000
    except Exception:
        return False
