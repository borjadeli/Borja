"""News RSS client — Fase 1 sin APIs pagas.

Fuentes:
- Yahoo Finance RSS por ticker (cobertura amplia, latencia baja).
- Google News search query por ticker (backup, cobertura internacional).

Output estándar: lista de items normalizados con detección de categoría por keywords
según la tabla del doc 02 sec. 2.1.

Diseño: firma estable. Fase 2 reemplaza por Benzinga/NewsAPI sin tocar el Research.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import feedparser
from curl_cffi import requests as cffi_requests

from backend.utils import get_logger, utcnow

log = get_logger(__name__)

_YF_RSS = "https://feeds.finance.yahoo.com/rss/2.0/headline"
_GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"
_BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


# ---------- Categorías de keywords (doc 02 sec. 2.1) ----------

KEYWORDS_NEGATIVOS = [
    "short report", "short seller", "sec investigation", "sec probe", "fraud",
    "restatement", "guidance cut", "cut guidance", "lowered guidance",
    "ATM offering", "at-the-market offering", "class action", "securities lawsuit",
    "going concern", "delisting", "bankruptcy", "auditor resigned",
    "subpoena", "wells notice",
]

KEYWORDS_CONTRATOS = [
    "contract award", "contract awarded", "supply agreement", "design win",
    "customer qualification", "pilot program", "strategic partnership",
    "capacity expansion", "multi-year contract", "LOI signed", "letter of intent",
    "new customer", "DoD contract", "department of defense",
    "NASA contract", "DOE contract",
]

KEYWORDS_INSIDER = [
    "form 4", "insider transaction", "insider selling", "insider buying",
]


@dataclass
class NewsItem:
    ticker: str
    titulo: str
    resumen: str
    url: str
    fuente: str
    publicado: datetime
    categoria: str | None = None  # "negativo" | "contrato" | "insider" | None
    keywords_match: list[str] = field(default_factory=list)


# ---------- Fetchers ----------

def _http_get(url: str) -> str | None:
    try:
        session = cffi_requests.Session(impersonate="chrome")
        r = session.get(url, headers={"User-Agent": _BROWSER_UA}, timeout=15)
        r.raise_for_status()
        return r.text
    except Exception as e:
        log.warning("news _http_get(%s) fallo: %s", url, e)
        return None


def _parse_yahoo_rss(ticker: str, xml: str) -> list[NewsItem]:
    feed = feedparser.parse(xml)
    items: list[NewsItem] = []
    for entry in feed.entries:
        pub = _parse_date(entry.get("published") or entry.get("updated") or "")
        items.append(NewsItem(
            ticker=ticker.upper(),
            titulo=entry.get("title", "").strip(),
            resumen=_strip_html(entry.get("summary", "")).strip(),
            url=entry.get("link", ""),
            fuente="Yahoo Finance",
            publicado=pub or utcnow(),
        ))
    return items


def _parse_google_rss(ticker: str, xml: str) -> list[NewsItem]:
    feed = feedparser.parse(xml)
    items: list[NewsItem] = []
    for entry in feed.entries:
        pub = _parse_date(entry.get("published") or entry.get("updated") or "")
        items.append(NewsItem(
            ticker=ticker.upper(),
            titulo=entry.get("title", "").strip(),
            resumen=_strip_html(entry.get("summary", "")).strip(),
            url=entry.get("link", ""),
            fuente="Google News",
            publicado=pub or utcnow(),
        ))
    return items


# ---------- API pública ----------

def fetch_yahoo_news(ticker: str) -> list[NewsItem]:
    url = f"{_YF_RSS}?s={ticker}&region=US&lang=en-US"
    xml = _http_get(url)
    if not xml:
        return []
    return _parse_yahoo_rss(ticker, xml)


def fetch_google_news(ticker: str, nombre: str | None = None) -> list[NewsItem]:
    query = f"{ticker} stock"
    if nombre:
        query = f'"{nombre}" OR {ticker} stock'
    params_q = query.replace(" ", "+")
    url = f"{_GOOGLE_NEWS_RSS}?q={params_q}&hl=en-US&gl=US&ceid=US:en"
    xml = _http_get(url)
    if not xml:
        return []
    return _parse_google_rss(ticker, xml)


def get_news_for_ticker(ticker: str, nombre: str | None = None,
                       dias: int = 7, categorias_filtrar: tuple[str, ...] = (),
                       limit: int = 30) -> list[NewsItem]:
    """Combina Yahoo + Google, clasifica por categoría, filtra por antigüedad."""
    cutoff = utcnow() - timedelta(days=dias)
    items = fetch_yahoo_news(ticker) + fetch_google_news(ticker, nombre)

    # Filtrar por fecha y deduplicar por URL
    seen_urls: set[str] = set()
    filtered: list[NewsItem] = []
    for it in items:
        if not it.url or it.url in seen_urls:
            continue
        if it.publicado < cutoff:
            continue
        seen_urls.add(it.url)
        it.categoria, it.keywords_match = _classify(it.titulo, it.resumen)
        if categorias_filtrar and it.categoria not in categorias_filtrar:
            continue
        filtered.append(it)

    filtered.sort(key=lambda x: x.publicado, reverse=True)
    return filtered[:limit]


def get_material_news(ticker: str, nombre: str | None = None, dias: int = 7) -> list[NewsItem]:
    """Sólo noticias con match de keywords materiales (para el Radar)."""
    all_news = get_news_for_ticker(ticker, nombre, dias=dias, limit=100)
    return [n for n in all_news if n.categoria in ("negativo", "contrato", "insider")]


# ---------- Classifier ----------

def _classify(titulo: str, resumen: str) -> tuple[str | None, list[str]]:
    text = (titulo + " " + resumen).lower()
    matches: list[str] = []
    categoria: str | None = None

    for kw in KEYWORDS_NEGATIVOS:
        if kw.lower() in text:
            matches.append(kw)
            categoria = "negativo"

    if not categoria:
        for kw in KEYWORDS_CONTRATOS:
            if kw.lower() in text:
                matches.append(kw)
                categoria = "contrato"

    if not categoria:
        for kw in KEYWORDS_INSIDER:
            if kw.lower() in text:
                matches.append(kw)
                categoria = "insider"

    return categoria, matches


# ---------- Helpers ----------

def _strip_html(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text)


def _parse_date(raw: str) -> datetime | None:
    if not raw:
        return None
    # feedparser ya parsea la mayoría — intentar varios formatos
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
    ):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.replace(tzinfo=None) if dt.tzinfo else dt
        except (ValueError, TypeError):
            continue
    try:
        import email.utils as eu
        parsed = eu.parsedate_tz(raw)
        if parsed:
            ts = eu.mktime_tz(parsed)
            return datetime.utcfromtimestamp(ts)
    except Exception:
        pass
    return None


def ping() -> bool:
    items = fetch_yahoo_news("SPY")
    return len(items) > 0
