"""Productor del LibroPM (canal de juicio PM-LLM, Bloque 3 — oficialización, tajada 1).

Corre el pipeline nuevo sobre el universo del paper y produce el **LibroPM**: por cada nombre elegible,
la etiqueta del PM-LLM + su tamaño-objetivo DENTRO de la banda (cap determinista) + el memo auditable
(bull/bear/falsador/fuentes). Lo persiste a `data/nucleo_paper/libro_pm.json`.

ADITIVO: NO toca `libro.json` (el libro paper) todavía — eso es la tajada siguiente (que el ciclo despliegue
hacia estos targets). Acá solo se PRODUCE el juicio. Cadencia (decisión operador 2026-09-08): **evento +
semanal** — corre semanal junto a la re-extracción, y ad-hoc cuando salta un evento fuerte sobre un nombre.

Reusa la construcción de candidatos de la superficie nueva (misma que `ops/shadow_ranking`): dos superficies
(elegibilidad de 3 pilares + números cohort-free) → `CandidatoLex` + `HojaEvidencia`.
"""
from __future__ import annotations

import json
from pathlib import Path

from backend.nucleo import fact_store as FS
from backend.nucleo import juicio, ranking
from backend.nucleo.compilador import _cobertura
from backend.nucleo.flujo_pm import orquestar_pm
from backend.nucleo.hoja_evidencia import hoja
from backend.nucleo.ranking_lexicografico import candidato_desde
from backend.services import market_data
from backend.utils import get_logger

log = get_logger(__name__)

PM_LIBRO_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "nucleo_paper" / "libro_pm.json"


def construir_item(session, ticker: str):
    """(candidato, hoja) para un ticker, o None si falla (se saltea). Mismas dos superficies que shadow_ranking."""
    try:
        ev = ranking.evaluar_ticker(session, ticker)               # elegibilidad (3 pilares)
        h = hoja(ticker, session=session)                          # números cohort-free
        snap = FS.snapshot_vigente(session, ticker)
        cob = _cobertura(snap) if snap else 0.0
        sn = market_data.get_price_snapshot(ticker)
        liq = sn.volumen_diario_promedio_30d if sn else None
        c = candidato_desde(ev, h, cobertura=cob, liquidez_adv=liq)
        return (c, h)
    except Exception as e:  # noqa: BLE001 — un nombre que falla no tumba la corrida
        log.warning("pm_run construir %s: %s", ticker, e)
        return None


def correr(session, tickers: list[str], fecha: str, *, judge=None, usar_web: bool = True,
           max_searches: int = 5, dry_run: bool = False, presupuesto: int | None = None):
    """Arma los items del universo y corre `orquestar_pm` → LibroPM. `judge` inyectable (tests)."""
    items = []
    for t in tickers:
        it = construir_item(session, t.upper())
        if it is not None:
            items.append(it)
    log.info("pm_run: %d/%d items construidos", len(items), len(tickers))
    return orquestar_pm(items, fecha, session=session, judge=judge, usar_web=usar_web,
                        max_searches=max_searches, dry_run=dry_run, presupuesto=presupuesto)


def serializar(libro_pm) -> dict:
    """LibroPM → dict JSON-serializable (targets + memo auditable por nombre)."""
    from backend.nucleo.juicio_llm import PROMPT_VERSION
    decisiones = []
    for d in libro_pm.decisiones:
        m = d.memo
        promovido = d.etiqueta in juicio.PROMOCIONES and (d.size_final or 0) > (d.banda.base + 1e-9)
        decisiones.append({
            "ticker": d.ticker,
            "etiqueta": d.etiqueta,
            "size_final": round(d.size_final or 0.0, 4),
            "base": round(d.banda.base, 4),
            "techo": round(d.banda.techo, 4),
            "promovido": promovido,
            "falsador": m.falsador,
            "fecha_falsador": m.fecha_falsador,
            "bull": m.bull,
            "bear": m.bear,
            "razon": m.razon,
            "fuentes": m.fuentes,
            "web_searches": m.web_searches,
            "valido": m.valido,
            "flags": m.flags,
            "memo_hash": d.intervencion.memo_hash,
            "motivo": d.motivo,
        })
    return {
        "fecha": libro_pm.fecha,
        "prompt_version": PROMPT_VERSION,
        "presupuesto": libro_pm.presupuesto,
        "promos_usadas": libro_pm.promos_usadas,
        "n": len(decisiones),
        "decisiones": decisiones,
    }


def persistir(libro_pm, path: Path = PM_LIBRO_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(serializar(libro_pm), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def persistir_merge(libro_pm, path: Path = PM_LIBRO_PATH) -> Path:
    """Actualiza SOLO las decisiones de los tickers de `libro_pm` sobre el archivo existente (disparo por evento):
    reemplaza esos nombres, conserva el resto de la última corrida semanal. Si no hay archivo previo, es como persistir."""
    prev = cargar(path) or {"decisiones": []}
    nuevo = serializar(libro_pm)
    tickers_nuevos = {d["ticker"] for d in nuevo["decisiones"]}
    conservadas = [d for d in prev.get("decisiones", []) if d["ticker"] not in tickers_nuevos]
    nuevo["decisiones"] = nuevo["decisiones"] + conservadas
    nuevo["n"] = len(nuevo["decisiones"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(nuevo, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def cargar(path: Path = PM_LIBRO_PATH) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        log.warning("pm_run cargar %s: %s", path, e)
        return None
