"""Ablation del PM-LLM (revisión, punto 1 — método): ¿el input determinista suma o ancla? ¿qué modelo? ¿web?

    .venv/bin/python -m ops.ablation_pm [--tickers RBRK,VRNS,NABL] [--configs opus_noweb,haiku_web,...]

Corre el MISMO nombre bajo varias configs y compara la ETIQUETA + memo + COSTO. Ejes:
  · determinista: aterrizado (le pasamos los fundamentals) vs PELADO (solo ticker, que junte todo él).
  · modelo: opus (None=default) vs haiku.
  · web: on (el PM busca) vs off (juzga solo con lo que tiene).

Baseline "opus_web aterrizado" = la corrida real ya hecha (data/nucleo_paper/libro_pm.json) — NO se re-corre
(ahorra plata). Los configs caros (pelado con web, opus con web) son opt-in. Default = configs BARATOS.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.database import session_scope
from backend.models import LLMCall
from backend.nucleo import juicio_llm
from backend.nucleo.flujo_pm import evidencia_desde_candidato
from backend.seleccion import pm_run
from backend.seleccion.paper_trader import _hoy
from backend.services import llm
from backend.utils import get_logger

log = get_logger(__name__)

HAIKU = "claude-haiku-4-5-20251001"

_GATHER_SYSTEM = """Sos un analista junior que SOLO junta evidencia fresca y CITADA — no opinás, no decidís.
Buscá en la web hechos recientes y verificables sobre la empresa: contratos/pedidos nuevos, cambios de
management/insiders, dinámica competitiva, avance de hitos, señales de demanda del cliente final, salud de la
cadena de suministro, y RED FLAGS (restatement, material weakness, going concern, litigio, dilución tóxica).
DESCONTÁ hype: price targets sell-side, TAM de la empresa, comunicados promocionales, foros. Solo HECHOS.
Devolvé JSON {"hechos":[{"hecho":"...","fuente":"URL o publicación + fecha"}], "resumen":"2-3 líneas neutrales"}.
Cada hecho DEBE tener fuente concreta; sin fuente, no lo incluyas."""


def _gather_haiku(ticker: str, max_searches: int = 5) -> dict:
    """Paso 1 del patrón gather→judge: Haiku busca y devuelve hechos citados (barato). No juzga."""
    r = llm.call_llm_json_with_web_search(
        _GATHER_SYSTEM, f"Empresa: {ticker}. Juntá la evidencia fresca y citada.",
        model=HAIKU, temperature=0.0, max_searches=max_searches,
        extra_metadata={"agent": "pm_gather", "ticker": ticker})
    j = r.parsed_json or {}
    return {"web_hechos_citados": j.get("hechos", []), "web_resumen": j.get("resumen", "")}

# nombre -> (model, usar_web, max_searches, pelado). model=None => Opus (default settings).
CONFIGS = {
    "opus_web":     (None,  True,  5, False),   # CARO — baseline (se reusa de libro_pm.json si está)
    "opus_noweb":   (None,  False, 0, False),   # barato — ¿le alcanza nuestra evidencia sin buscar?
    "haiku_web":    (HAIKU, True,  3, False),   # barato — modelo chico + web
    "haiku_noweb":  (HAIKU, False, 0, False),   # el más barato
    "pelado_opus":  (None,  True,  5, True),    # CARO — sin determinista: ¿el LLM solo llega igual?
    "pelado_haiku": (HAIKU, True,  3, True),    # sin determinista, modelo chico
    "gather_judge": (None,  False, 0, False),   # ★ Haiku junta (web) → Opus juzga (sin web). Manejado aparte.
}
DEFAULT_CONFIGS = ["opus_noweb", "haiku_web", "haiku_noweb"]   # baratos por defecto


def _pelado(ticker: str) -> dict:
    return {"nota": f"Sin inputs deterministas. Evaluá {ticker} desde cero: buscá/leé los filings y la web y "
                    "formá tu juicio de calidad/durabilidad, moat, catalizadores. No tenés fundamentals precomputados."}


def _ultimo_costo(session) -> float:
    row = session.query(LLMCall).order_by(LLMCall.id.desc()).first()
    return round((row.cost_usd or 0.0), 4) if row else 0.0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default="RBRK,VRNS,NABL")
    ap.add_argument("--configs", default=",".join(DEFAULT_CONFIGS))
    args = ap.parse_args(argv)
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    configs = [c.strip() for c in args.configs.split(",") if c.strip() in CONFIGS]
    fecha = _hoy()

    # baseline opus_web desde la corrida real ya hecha (no re-corre)
    base = {d["ticker"]: d for d in (pm_run.cargar() or {}).get("decisiones", [])}

    filas = []
    with session_scope() as s:
        for t in tickers:
            it = pm_run.construir_item(s, t)
            if it is None:
                log.warning("ablation: %s sin item, se saltea", t); continue
            c, hoja = it
            ev_full = evidencia_desde_candidato(c, hoja, session=s)
            for cfg in configs:
                if cfg == "gather_judge":
                    # Haiku junta (web, barato) → Opus juzga sobre esa evidencia (sin web propia).
                    gathered = _gather_haiku(t, max_searches=5)
                    costo = _ultimo_costo(s)
                    memo = juicio_llm.evaluar_juicio(t, {**ev_full, **gathered}, model=None, usar_web=False)
                    costo = round(costo + _ultimo_costo(s), 4)
                    filas.append({"ticker": t, "config": cfg, "etiqueta": memo.etiqueta, "valido": memo.valido,
                                  "web": len(gathered.get("web_hechos_citados", [])), "costo_usd": costo,
                                  "falsador": (memo.falsador or "")[:80], "bull": (memo.bull or "")[:100],
                                  "bear": (memo.bear or "")[:100]})
                    continue
                model, usar_web, msearch, pelado = CONFIGS[cfg]
                ev = _pelado(t) if pelado else ev_full
                memo = juicio_llm.evaluar_juicio(t, ev, model=model, usar_web=usar_web, max_searches=msearch)
                filas.append({
                    "ticker": t, "config": cfg,
                    "etiqueta": memo.etiqueta, "valido": memo.valido,
                    "web": memo.web_searches, "costo_usd": _ultimo_costo(s),
                    "falsador": (memo.falsador or "")[:80],
                    "bull": (memo.bull or "")[:100], "bear": (memo.bear or "")[:100],
                })
            # baseline reusado
            if t in base:
                b = base[t]
                filas.append({"ticker": t, "config": "opus_web*", "etiqueta": b["etiqueta"], "valido": b["valido"],
                              "web": b["web_searches"], "costo_usd": None, "falsador": (b.get("falsador") or "")[:80],
                              "bull": (b.get("bull") or "")[:100], "bear": (b.get("bear") or "")[:100]})

    out = Path("data/ablation_pm.json")
    out.write_text(json.dumps({"fecha": fecha, "filas": filas}, indent=2, ensure_ascii=False), encoding="utf-8")

    # tabla
    print(f"\nABLATION PM · {fecha[:19]} · (* = baseline reusado de la corrida real)\n" + "=" * 78)
    print(f"{'TICKER':6} {'CONFIG':13} {'ETIQUETA':16} {'web':>4} {'costo':>8}")
    print("-" * 78)
    tot = 0.0
    for f in filas:
        cost = f["costo_usd"]
        tot += cost or 0.0
        cs = f"${cost:.3f}" if cost is not None else "  reuso"
        flag = "" if f["valido"] else " ⚠fallback"
        print(f"{f['ticker']:6} {f['config']:13} {f['etiqueta']:16} {f['web']:>4} {cs:>8}{flag}")
    print("-" * 78)
    print(f"costo total de esta corrida (sin baseline): ${tot:.2f} → {out}")
    print("\nComparar: ¿la ETIQUETA cambia entre pelado vs aterrizado? ¿entre opus vs haiku? ¿el barato coincide con opus_web*?")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
