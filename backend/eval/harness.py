"""Harness de evaluación del extractor — la vara objetiva del P0 (doc 22 §12).

Mide tres cosas sobre un conjunto de corridas del extractor contra el gold set:
  1. ESTABILIDAD  — ¿las K corridas dan el mismo hecho? (el bug COHR: 2/4 flip)
  2. CORRECCIÓN   — ¿el hecho estable coincide con la verdad de terreno (valor + support_type)?
  3. GROUNDING    — ¿la cita del hecho existe literalmente en el filing? (anti-confabulación)

No llama al LLM: puntúa lo que se le pasa. Así comparás extractor viejo vs nuevo con la
misma regla. Foco en los hechos gate-críticos (los que voltean la decisión de cartera).
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

GOLD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "gold_set"

TOL = 0.02  # tolerancia relativa para comparar valores numéricos (fracciones/montos).


def normalizar(s: str) -> str:
    """Normaliza para comparación de citas: unicode NFKC, comillas/guiones/NBSP, whitespace, casefold."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = (s.replace(" ", " ").replace("’", "'").replace("‘", "'")
          .replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-"))
    s = re.sub(r"\s+", " ", s)
    return s.strip().casefold()


def cargar_gold(ticker: str) -> dict:
    return json.loads((GOLD_DIR / f"{ticker.lower()}.json").read_text(encoding="utf-8"))


def verificar_grounding(quote: str | None, texto_filing: str | None) -> bool | None:
    """¿La cita existe literalmente en el filing? None si no hay texto para chequear."""
    if texto_filing is None:
        return None
    if not quote:
        return False
    return normalizar(quote) in normalizar(texto_filing)


def _valores_iguales(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if b == 0:
            return abs(a) < TOL
        return abs(a - b) / abs(b) <= TOL
    return a == b


def puntuar(gold: dict, corridas: list[dict], *, texto_filing: str | None = None) -> dict:
    """gold: dict del gold set. corridas: lista de K dicts {fact_key: {value, support_type, quote}}.

    Devuelve reporte por hecho gate-crítico + agregados.
    """
    criticos = [f for f in gold["facts"] if f.get("gate_critical")]
    filas = []
    for gf in criticos:
        fk = gf["fact_key"]
        preds = [c.get(fk) for c in corridas]
        vals = [p.get("value") if isinstance(p, dict) else None for p in preds]
        estable = len({json.dumps(v, sort_keys=True) for v in vals}) == 1
        pred0 = preds[0] if preds and isinstance(preds[0], dict) else {}
        correcto = bool(estable and vals and _valores_iguales(vals[0], gf.get("value"))
                        and (pred0.get("support_type") == gf.get("support_type")))
        gnd = [verificar_grounding(p.get("quote") if isinstance(p, dict) else None, texto_filing)
               for p in preds]
        filas.append({
            "fact_key": fk, "gate_item": gf.get("gate_item"),
            "gold_value": gf.get("value"), "gold_support": gf.get("support_type"),
            "pred_values": vals, "pred_support": [p.get("support_type") if isinstance(p, dict) else None for p in preds],
            "estable": estable, "correcto": correcto,
            "grounding": gnd,
        })
    n = len(filas) or 1
    agg = {
        "n_gate_critical": len(filas),
        "estabilidad": sum(f["estable"] for f in filas) / n,
        "correccion": sum(f["correcto"] for f in filas) / n,
        "grounding_violaciones": sum(
            1 for f in filas for g, ps in zip(f["grounding"], f["pred_support"])
            if g is False and ps in ("DIRECT", "DERIVED")
        ),
    }
    return {"ticker": gold["ticker"], "accession": gold["accession"], "filas": filas, "agregado": agg}


def imprimir(reporte: dict) -> None:
    print(f"\n=== {reporte['ticker']} ({reporte['accession']}) ===")
    for f in reporte["filas"]:
        est = "ESTABLE" if f["estable"] else "FLIP"
        ok = "OK" if f["correcto"] else "MAL"
        print(f"  [{f['gate_item']}] {f['fact_key']}: {est}/{ok}")
        print(f"      gold={f['gold_value']} ({f['gold_support']})  pred={f['pred_values']} support={f['pred_support']}")
        if any(g is not None for g in f["grounding"]):
            print(f"      grounding={f['grounding']}")
    a = reporte["agregado"]
    print(f"  --- estabilidad={a['estabilidad']:.0%}  corrección={a['correccion']:.0%}  "
          f"grounding_violaciones={a['grounding_violaciones']} / {a['n_gate_critical']} hechos gate-críticos")


if __name__ == "__main__":
    # Demo: puntúa el comportamiento MEDIDO del extractor VIEJO en COHR (4 corridas reales).
    # organic_growth_available osciló True/False/False/True, etiquetado como DIRECT ("fuente A"),
    # cuando la verdad es DERIVED y la palabra 'organic' ni aparece en el filing.
    gold = cargar_gold("COHR")
    corridas_viejo = [
        {"organic_growth_available": {"value": True, "support_type": "DIRECT", "quote": "organic growth 100%"}},
        {"organic_growth_available": {"value": False, "support_type": "DIRECT", "quote": ""}},
        {"organic_growth_available": {"value": False, "support_type": "DIRECT", "quote": ""}},
        {"organic_growth_available": {"value": True, "support_type": "DIRECT", "quote": "organic growth 100%"}},
    ]
    texto = ""
    p = Path("/tmp/claude-1000/-opt-BORJA/47e44975-1d03-47ab-b6ea-0eb650d465a9/scratchpad/cohr_10q.txt")
    if p.exists():
        texto = p.read_text(encoding="utf-8")
    imprimir(puntuar(gold, corridas_viejo, texto_filing=texto or None))
    print("\n  (Lectura: el harness detecta FLIP + support MAL (DIRECT vs DERIVED) + grounding roto:")
    print("   'organic growth 100%' no existe en el 10-Q real. Exactamente el bug de COHR.)")
