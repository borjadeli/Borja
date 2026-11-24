"""Market data wrapper — Fase 1 (precios, volumen, liquidez).

Responsabilidad: **precio actual, histórico OHLCV, volumen diario promedio, liquidez**.
Los fundamentals (revenue, márgenes, cash, deuda, FCF) viven en
`backend.services.edgar` (fuente oficial SEC, más estable).

Diseño crítico: firmas estables. Cuando se active Fase 2 con FMP/Polygon,
sólo se reemplaza la implementación interna.

Fuente Fase 1: Yahoo chart API vía curl_cffi (impersona Chrome → bypass de 429).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from curl_cffi import requests as cffi_requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from backend.utils import get_logger, utcnow

log = get_logger(__name__)

_YF_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
_BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
_HTTP_TIMEOUT = 15.0


def _new_session():
    return cffi_requests.Session(impersonate="chrome")


@dataclass
class PriceSnapshot:
    ticker: str
    precio_actual: float | None
    volumen_diario_promedio_30d: float | None  # USD
    market_cap: float | None
    shares_outstanding: float | None = None    # del feed de mercado (no de XBRL) — market cap es una
    currency: str = "USD"                       #   cantidad de mercado; evita el bug de weighted-avg Class A
    timestamp: datetime = field(default_factory=utcnow)


# Auth cacheada para el endpoint de quote de Yahoo (pide crumb; el chart no).
_yf_auth: dict = {"session": None, "crumb": None}


def _yahoo_auth():
    if _yf_auth["crumb"]:
        return _yf_auth["session"], _yf_auth["crumb"]
    try:
        s = _new_session()
        s.get("https://finance.yahoo.com/quote/AAPL", timeout=_HTTP_TIMEOUT)
        crumb = s.get("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=_HTTP_TIMEOUT).text.strip()
        if crumb and len(crumb) < 30:
            _yf_auth["session"], _yf_auth["crumb"] = s, crumb
    except Exception as e:
        log.warning("yahoo auth fallo: %s", e)
    return _yf_auth["session"], _yf_auth["crumb"]


def _fetch_yahoo_quote(ticker: str) -> dict | None:
    """sharesOutstanding + marketCap del feed de mercado (v7 quote con crumb)."""
    s, crumb = _yahoo_auth()
    if not s or not crumb:
        return None
    try:
        url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={ticker}&crumb={crumb}"
        r = s.get(url, timeout=_HTTP_TIMEOUT)
        if r.status_code == 401:
            _yf_auth["crumb"] = None          # crumb venció → forzar refresh en el próximo intento
            return None
        r.raise_for_status()
        res = r.json().get("quoteResponse", {}).get("result", [])
        return res[0] if res else None
    except Exception as e:
        log.warning("yahoo quote(%s) fallo: %s", ticker, e)
        return None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((Exception,)),
    reraise=False,
)
def _fetch_yahoo_chart(ticker: str, range_: str = "3mo", interval: str = "1d") -> dict | None:
    url = _YF_CHART_URL.format(ticker=ticker)
    params = {"interval": interval, "range": range_, "includePrePost": "false"}
    headers = {
        "User-Agent": _BROWSER_UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://finance.yahoo.com/",
    }
    session = _new_session()
    r = session.get(url, params=params, headers=headers, timeout=_HTTP_TIMEOUT)
    if r.status_code == 429:
        raise RuntimeError("429 Too Many Requests")
    r.raise_for_status()
    return r.json()


def _parse_chart(payload: dict) -> tuple[list[dict], dict]:
    if not payload:
        return [], {}
    result = payload.get("chart", {}).get("result") or []
    if not result:
        return [], {}
    r0 = result[0]
    meta = r0.get("meta", {}) or {}
    timestamps = r0.get("timestamp") or []
    indicators = (r0.get("indicators") or {}).get("quote") or [{}]
    q = indicators[0] if indicators else {}
    closes = q.get("close") or []
    opens = q.get("open") or []
    highs = q.get("high") or []
    lows = q.get("low") or []
    volumes = q.get("volume") or []
    rows = []
    for i, ts in enumerate(timestamps):
        close = closes[i] if i < len(closes) else None
        if close is None:
            continue
        rows.append({
            "date": datetime.utcfromtimestamp(ts),
            "open": opens[i] if i < len(opens) else None,
            "high": highs[i] if i < len(highs) else None,
            "low": lows[i] if i < len(lows) else None,
            "close": close,
            "volume": volumes[i] if i < len(volumes) else None,
        })
    return rows, meta


def get_price_snapshot(ticker: str) -> PriceSnapshot | None:
    """Precio actual + volumen diario promedio 30d. Market cap viene vacío — se computa
    externamente combinando precio × shares de EDGAR."""
    try:
        payload = _fetch_yahoo_chart(ticker, range_="3mo", interval="1d")
        rows, meta = _parse_chart(payload or {})
        if not rows:
            return None
        precio_actual = meta.get("regularMarketPrice") or rows[-1]["close"]

        last_30 = rows[-30:] if len(rows) >= 30 else rows
        vol_usd = None
        if last_30:
            vols = [r["volume"] * r["close"] for r in last_30 if r["volume"] and r["close"]]
            if vols:
                vol_usd = sum(vols) / len(vols)

        # Shares/market cap del FEED (no de XBRL): market cap es cantidad de mercado; evita el
        # bug de weighted-avg Class A y el stale de XBRL en de-SPAC/Up-C (review 2026-08).
        q = _fetch_yahoo_quote(ticker) or {}
        return PriceSnapshot(
            ticker=ticker.upper(),
            precio_actual=float(precio_actual) if precio_actual else None,
            volumen_diario_promedio_30d=vol_usd,
            market_cap=q.get("marketCap"),
            shares_outstanding=q.get("sharesOutstanding"),
            currency=meta.get("currency", "USD"),
        )
    except Exception as e:
        log.warning("get_price_snapshot(%s) fallo: %s", ticker, e)
        return None


def get_price_history(ticker: str, period: str = "1y") -> list[dict[str, Any]]:
    """Histórico OHLCV. period: 1mo, 3mo, 6mo, 1y, 2y, 5y, max."""
    try:
        payload = _fetch_yahoo_chart(ticker, range_=period, interval="1d")
        rows, _ = _parse_chart(payload or {})
        return rows
    except Exception as e:
        log.warning("get_price_history(%s) fallo: %s", ticker, e)
        return []


def historico_diario(ticker: str, period: str = "3mo") -> dict:
    """{date: close} para un ticker — reshape de get_price_history (usado por el MtM del paper vs SPY)."""
    rows = get_price_history(ticker, period=period)
    return {row["date"].date(): float(row["close"]) for row in rows if row.get("close")}


def check_liquidity(ticker: str, umbral_usd: float = 1_000_000) -> dict[str, Any]:
    """Liquidez — volumen diario >$1M según doc 01 sec. 6."""
    snap = get_price_snapshot(ticker)
    vol = snap.volumen_diario_promedio_30d if snap else None
    return {
        "ticker": ticker.upper(),
        "volumen_diario_usd": vol,
        "umbral": umbral_usd,
        "suficiente": (vol is not None and vol >= umbral_usd),
    }


def fx_a_usd(currency: str) -> float | None:
    """USD por 1 unidad de `currency` (para pasar un monto en moneda local → USD). None si no se pudo.
    Soporte extranjero (doc 76): el market cap de Yahoo viene en moneda de cotización; sin esto, 17.652B KRW
    leído como USD parece un gigante de $17 billones y el gate del IPS se rompe."""
    cur = (currency or "USD").upper()
    if cur == "USD":
        return 1.0
    snap = get_price_snapshot(f"USD{cur}=X")        # precio del par = unidades de `cur` por 1 USD
    if snap and snap.precio_actual:
        return 1.0 / snap.precio_actual
    return None


# Monedas cotizadas en UNIDAD MENOR (el precio viene en 1/100 de la moneda mayor). Se chequean case-sensitive
# (GBp ≠ GBP): Yahoo usa "GBp" para peniques de Londres. r6 lo marcó como caso a cubrir.
_UNIDAD_MENOR: dict[str, tuple[str, float]] = {
    "GBp": ("GBP", 100.0), "GBX": ("GBP", 100.0), "ZAc": ("ZAR", 100.0), "ILA": ("ILS", 100.0),
}


def precio_a_usd(precio: float | None, currency: str | None, *, fx_fn=None) -> float | None:
    """Convierte un precio POR ACCIÓN a USD. Maneja monedas en unidad menor (GBp/GBX = peniques). None si no
    hay FX. Este es el borde donde el paper y las sombras pasan a USD (todo el libro razona en USD)."""
    if precio is None:
        return None
    if fx_fn is None:
        fx_fn = fx_a_usd
    cur = currency or "USD"
    if cur in _UNIDAD_MENOR:                                  # peniques, etc. → moneda mayor / 100 → USD
        mayor, div = _UNIDAD_MENOR[cur]
        fx = fx_fn(mayor)
        return (float(precio) / div) * fx if fx else None
    if cur.upper() == "USD":
        return float(precio)
    fx = fx_fn(cur.upper())
    return float(precio) * fx if fx else None


_YQ: dict = {"session": None, "crumb": None}


def _yahoo_quote_session():
    """Sesión + crumb de Yahoo (cacheados). None si el handshake falla (Yahoo pelea el scraping) — fail-safe."""
    if _YQ["crumb"]:
        return _YQ["session"], _YQ["crumb"]
    try:
        s = cffi_requests.Session(impersonate="chrome")
        s.get("https://fc.yahoo.com", timeout=15)
        crumb = s.get("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=15).text.strip()
        if crumb and "<" not in crumb and len(crumb) < 40:
            _YQ["session"], _YQ["crumb"] = s, crumb
            return s, crumb
    except Exception as e:  # noqa: BLE001
        log.warning("yahoo crumb handshake falló: %s", e)
    return None, None


def financials_yahoo(ticker: str) -> dict | None:
    """Financials (ANUAL/TTM, convertidos a USD) de un ticker — incl. EXTRANJERO sin SEC — vía Yahoo
    quoteSummary (crumb). MENOR CONFIANZA que XBRL: NO es point-in-time ni verificable por filing. `None` si el
    crumb falla o no hay datos (el caller cae a solo-precio). Fuente FRÁGIL (Yahoo puede romper el crumb)."""
    s, crumb = _yahoo_quote_session()
    if not crumb:
        return None
    try:
        r = s.get(f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}",
                  params={"modules": "financialData,defaultKeyStatistics,incomeStatementHistory", "crumb": crumb},
                  timeout=20)
        if r.status_code != 200:
            return None
        d = r.json()["quoteSummary"]["result"][0]
    except Exception as e:  # noqa: BLE001
        log.warning("quoteSummary(%s) falló: %s", ticker, e)
        return None
    fd = d.get("financialData") or {}
    ks = d.get("defaultKeyStatistics") or {}
    ish = (d.get("incomeStatementHistory") or {}).get("incomeStatementHistory") or []

    def raw(node, key):
        return (node.get(key) or {}).get("raw")

    cur = fd.get("financialCurrency") or "USD"
    fx = (fx_a_usd(cur) or 1.0) if cur != "USD" else 1.0        # USD por unidad local → MULTIPLICAR

    def usd(v):
        return round(v * fx, 2) if (v is not None) else None

    rev, opm, gpm = raw(fd, "totalRevenue"), raw(fd, "operatingMargins"), raw(fd, "grossMargins")
    out = {
        "currency": cur, "fx": fx,
        "revenue": usd(rev),
        "operating_income_loss": usd(rev * opm) if (rev is not None and opm is not None) else None,
        "gross_profit": usd(rev * gpm) if (rev is not None and gpm is not None) else None,
        "cash": usd(raw(fd, "totalCash")),
        "total_debt": usd(raw(fd, "totalDebt")),
        "shares": raw(ks, "sharesOutstanding"),
    }
    if len(ish) >= 2:
        out["revenue_fy_prev"] = usd(raw(ish[1], "totalRevenue"))
    return out


def market_cap_usd(ticker: str) -> float | None:
    """Market cap del ticker en USD (convierte desde la moneda de cotización). None si no hay dato/FX.
    Determinista — base del gate de banda para extranjeros (y verificación del null que manda el LLM)."""
    snap = get_price_snapshot(ticker)
    if not snap or snap.market_cap is None:
        return None
    rate = fx_a_usd(snap.currency)
    return round(snap.market_cap * rate, 2) if rate else None


def ping() -> bool:
    snap = get_price_snapshot("SPY")
    return snap is not None and snap.precio_actual is not None
