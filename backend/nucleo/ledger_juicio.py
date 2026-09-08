"""Ledger de hit-rate del JUICIO (doc 39 §2.6, Bloque 3.3) — hace al juicio empíricamente responsable.

Cada intervención de juicio (promoción/veto) se registra con su falsador y fecha; después se marca su
retorno forward y si el falsador se cumplió. La métrica clave: ¿el juicio le GANA al baseline determinista?
Si sobre N decisiones resueltas no le gana, el **presupuesto de promociones se achica solo** — el juicio no
se amordaza (doc 39: eso sería doble conservadurismo), se hace RESPONSABLE. Determinista, versionado, sin LLM.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from backend.nucleo import politica
from backend.nucleo.juicio import Intervencion, PROMOCIONES

LEDGER_JUICIO_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "ledger_juicio.json"


def _cargar(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _guardar(path: Path, data: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def registrar(intervenciones: list[Intervencion], *, precios: dict[str, float],
              path: Path = LEDGER_JUICIO_PATH) -> int:
    """Registra las intervenciones de juicio con el precio al momento (para el retorno forward). DEDUP por
    (ticker, fecha, etiqueta). Solo registra las que MOVIERON (promociones ejecutadas / vetos) — un PASS no es
    una intervención de juicio. Devuelve cuántas nuevas."""
    data = _cargar(path)
    vistas = {(d["ticker"], d["fecha"], d["etiqueta"]) for d in data}
    nuevas = 0
    for iv in intervenciones:
        movio = iv.etiqueta in PROMOCIONES or iv.etiqueta in ("VETO", "THESIS_BROKEN")
        if not movio:
            continue
        k = (iv.ticker, iv.fecha, iv.etiqueta)
        if k in vistas:
            continue
        d = asdict(iv)
        d["precio"] = precios.get(iv.ticker)
        d["es_promocion"] = iv.etiqueta in PROMOCIONES
        data.append(d)
        vistas.add(k)
        nuevas += 1
    if nuevas:
        _guardar(path, data)
    return nuevas


def hit_rate(precios_actuales: dict[str, float], *, path: Path = LEDGER_JUICIO_PATH,
             baseline_ret: dict[str, float] | None = None) -> dict:
    """Hit-rate del juicio (doc 39 §2.6): de las PROMOCIONES resueltas, ¿qué fracción tuvo retorno forward
    positivo, y le ganó al baseline determinista? `baseline_ret[ticker]` = retorno que habría tenido el nombre
    con el size determinista (base). Devuelve métricas. Con pocos datos es RUIDO (gana valor con el tiempo)."""
    baseline_ret = baseline_ret or {}
    promos = []
    for d in _cargar(path):
        if not d.get("es_promocion"):
            continue
        p_act, p0 = precios_actuales.get(d["ticker"]), d.get("precio")
        if not (p_act and p0 and p0 > 0):
            continue
        ret = p_act / p0 - 1.0
        promos.append({"ticker": d["ticker"], "ret": ret, "vs_baseline": ret - baseline_ret.get(d["ticker"], 0.0)})
    n = len(promos)
    if n == 0:
        return {"n": 0, "hit_rate": None, "gana_baseline": None, "recomendacion_presupuesto": politica.PRESUPUESTO_PROMOCIONES}
    aciertos = sum(1 for p in promos if p["ret"] > 0)
    gana = sum(1 for p in promos if p["vs_baseline"] > 0)
    hr = round(aciertos / n, 3)
    gana_bl = round(gana / n, 3)
    # Regla de achique (doc 39): si sobre ≥8 resueltas el juicio NO le gana al baseline (<50%), achicar presupuesto.
    presup = politica.PRESUPUESTO_PROMOCIONES
    if n >= 8 and gana_bl < 0.5:
        presup = max(0, presup - 1)
    return {"n": n, "hit_rate": hr, "gana_baseline": gana_bl,
            "ret_medio": round(sum(p["ret"] for p in promos) / n, 4),
            "recomendacion_presupuesto": presup,
            "nota": "ruido con n<8" if n < 8 else ("achicar: el juicio no le gana al baseline" if gana_bl < 0.5 else "el juicio le gana al baseline")}
