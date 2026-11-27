"""Poller de filings (doc 85 F1) — el corazón del "vigilar". Núcleo PURO (inyectable); el ops hace la red.

Para los nombres vigilados (posiciones + banca), trae filings recientes, los clasifica (event_monitor) y:
- un filing REVISION/periódico POSTERIOR a lo que vio la tesis → marca la ficha EN_REVISION (invalida vigencia);
- junta los eventos materiales (DURO/REVISION/DILUCION) como ALERTAS para el PM.
Marca su corrida en pipeline_estado (el dead-man's-switch). NO llama a LLM.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from backend.agentes.event_monitor import EventoClasificado, clasificar_filings


@dataclass
class ResultadoPoll:
    eventos: list[EventoClasificado] = field(default_factory=list)   # materiales (no IGNORAR), por nombre
    en_revision: list[str] = field(default_factory=list)            # tickers que pasaron a EN_REVISION
    duros: list[EventoClasificado] = field(default_factory=list)    # tier DURO (→ regla de salida, F2)


def _fecha_de(e: EventoClasificado) -> date | None:
    try:
        return date.fromisoformat(e.fecha) if e.fecha else None
    except Exception:  # noqa: BLE001
        return None


def pollear(fichas: dict, *, filings_fn, hoy: date | None = None) -> ResultadoPoll:
    """Núcleo puro. `fichas` = ticker→Ficha. `filings_fn(ticker)` → lista de filings recientes (inyectable).
    Marca EN_REVISION las fichas con un evento REVISION/periódico POSTERIOR a `conocido_hasta`/`visto_hasta`.
    NO guarda (el caller persiste); muta `ficha.estado` in-place para que el store lo escriba."""
    hoy = hoy or date.today()
    res = ResultadoPoll()
    for tk, f in (fichas or {}).items():
        eventos = clasificar_filings(tk, filings_fn(tk))
        if not eventos:
            continue
        res.eventos.extend(eventos)
        res.duros.extend([e for e in eventos if e.tier == "DURO"])
        # vigencia: un REVISION posterior a lo que vio la tesis → EN_REVISION (si ya no está VENCIDA/ROTA)
        ref = (getattr(f, "conocido_hasta", None) or "")
        recientes = [e for e in eventos if e.tier == "REVISION"
                     and (_fecha_de(e) is None or not ref or (e.fecha or "") > ref)]
        if recientes and getattr(f, "estado", None) == "VIGENTE":
            f.estado = "EN_REVISION"
            res.en_revision.append(tk.upper())
    return res


def revalidaciones_a_encolar(en_revision, *, posiciones, cap: int = 3) -> list[str]:
    """De las fichas que pasaron a EN_REVISION, cuáles mandar a REVALIDACIÓN (delta-deep barato). Auditoría 2026-11-27:
    hoy una no-tenencia que pasa a EN_REVISION sale del packet del PM y NADIE la re-analiza → la MEJORA de fundamentals
    (que llega por 10-Q/8-K) deja al nombre afuera, mientras el deterioro sí llega vía caída de precio. Fix: encolar las
    NO-tenencias (las tenencias ya las cubre la regla de salida), hasta `cap` por corrida (tope de costo). v1: FIFO; la
    priorización por materialidad/distancia a zona es un refinamiento posterior."""
    pos = {t.upper() for t in (posiciones or set())}
    cand = [t.upper() for t in (en_revision or []) if t.upper() not in pos]
    return cand[:max(0, cap)]


def _es_extranjero(ticker: str) -> bool:
    """Heurística: ticker con punto (mercado no-US) o numérico → sin filings SEC → el poller por EVENTO no lo alcanza."""
    t = (ticker or "").upper()
    return ("." in t) or t[:1].isdigit()


def revalidaciones_por_tiempo(fichas, *, posiciones, hoy, dias: int = 30, cap: int = 2) -> list[str]:
    """TTL para los nombres que el poller por EVENTO NO puede ver (EXTRANJEROS sin filings SEC): una ficha VIGENTE
    no-tenencia cuya evidencia (`conocido_hasta`) tiene más de `dias` → revalidar por tiempo. Auditoría 2026-11-27:
    sin esto la ficha de un extranjero nunca se refresca (su vigencia es por evento, y el evento es un filing SEC que
    no existe). ~42% de las altas del operador son extranjeras. Las US las cubre el poller por evento."""
    pos = {t.upper() for t in (posiciones or set())}
    try:
        hoy_d = hoy if hasattr(hoy, "year") else date.fromisoformat(str(hoy)[:10])
    except Exception:  # noqa: BLE001
        return []
    out: list[str] = []
    for tk, f in (fichas or {}).items():
        tku = tk.upper()
        if tku in pos or not _es_extranjero(tku) or getattr(f, "estado", None) != "VIGENTE":
            continue
        ch = getattr(f, "conocido_hasta", None)
        try:
            viejo = ch is None or (hoy_d - date.fromisoformat(str(ch)[:10])).days >= dias
        except Exception:  # noqa: BLE001 — fecha ilegible → tratar como vieja (fail-closed hacia revalidar)
            viejo = True
        if viejo:
            out.append(tku)
    return out[:max(0, cap)]
