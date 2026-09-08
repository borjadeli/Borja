"""Mide P(correcto | HIT) — la OTRA mitad del presupuesto de error (Bloque 0, doc 32 §5).

    .venv/bin/python -m ops.medir_extraccion

El retrieval (medir_retrieval) contesta "¿encontramos el párrafo?". Esto contesta lo otro:
DADO un párrafo bueno (un HIT), ¿el LLM extrae el VALOR correcto y CITA el pasaje correcto
(no un distractor / período equivocado)? Corre el extractor SOLO sobre los HITs evaluables
(barato: ~1 llamada Haiku por caso). Parte el error en miss_retrieval + error_extracción → dice
dónde está el cuello real (IA2: medir esto ANTES de sobre-invertir en período/distractores).
"""
from __future__ import annotations

from backend.nucleo import extractor_citado as EX
from backend.nucleo.analisis import _window
from backend.nucleo.fact_keys import FACT_KEYS
from backend.nucleo.gold_retrieval import GOLD, cargar_corpus, medir_caso


def _valor_ok(extraido, gold) -> bool:
    """¿El valor extraído coincide con el gold? Booleano por truthiness; numérico con tolerancia."""
    if isinstance(gold, bool):
        return bool(extraido) == gold
    if isinstance(gold, (int, float)):
        try:
            return abs(float(extraido) - float(gold)) <= 0.03   # ±3pp para fracciones de concentración
        except (TypeError, ValueError):
            return False
    return extraido == gold


def _span_norm(nt: str, s: str | None):
    """Offset de `s` dentro del texto YA normalizado `nt`, usando la MISMA normalización que el
    extractor (EX._norm: NBSP/comillas/guiones + casefold). Sin esto el localizador es más estricto
    que la cita del LLM y reporta falsos 'sin_cita'."""
    if not s:
        return None
    ns = EX._norm(s)
    off = nt.find(ns)
    return (off, off + len(ns)) if off >= 0 else None


def _solapa(a, b) -> bool:
    return a and b and a[0] < b[1] and b[0] < a[1]


def main() -> int:
    hits = [(c, medir_caso(c)) for c in GOLD]
    hits = [(c, r) for c, r in hits if r.evaluable and r.hit]

    print("=" * 96)
    print("EXTRACCIÓN — P(correcto | HIT) (corre el LLM sobre las ventanas buenas)")
    print("=" * 96)
    print(f"{'CASE_ID':40} {'VALOR':>10} {'gold':>8} {'VAL_OK':>7} {'CITA':>14}")
    print("-" * 96)

    val_ok = cita_ok = 0
    for c, _ in hits:
        texto = cargar_corpus(c)
        spec = next((s for s in FACT_KEYS if s.fact_key == c.fact_key), None)
        win = _window(texto, spec.anchors)
        h = EX.extraer_hecho(win, fact_key=c.fact_key, pregunta=spec.pregunta)

        nt = EX._norm(texto)                              # normalizado UNA vez; offsets consistentes
        v_ok = _valor_ok(h.value, c.gold_answer)
        qspan = _span_norm(nt, h.quote)
        gold_spans = [g for alt in c.evidence for span in alt if (g := _span_norm(nt, span))]
        dist_spans = [d for dd in c.distractors if (d := _span_norm(nt, dd))]
        en_gold = any(_solapa(qspan, g) for g in gold_spans)
        en_dist = any(_solapa(qspan, d) for d in dist_spans)
        cita = "gold" if en_gold else ("DISTRACTOR" if en_dist else ("otra" if qspan else "sin_cita"))

        val_ok += v_ok
        cita_ok += en_gold
        vstr = f"{h.value:.3f}" if isinstance(h.value, float) else str(h.value)
        gstr = f"{c.gold_answer:.2f}" if isinstance(c.gold_answer, float) else str(c.gold_answer)
        print(f"{c.case_id:40} {vstr:>10} {gstr:>8} {'✓' if v_ok else '✗':>7} {cita:>14}")

    n = len(hits)
    print("-" * 96)
    print(f"VALOR correcto | HIT:  {val_ok}/{n} = {val_ok/n*100:.0f}%")
    print(f"CITA en el gold | HIT: {cita_ok}/{n} = {cita_ok/n*100:.0f}%  (cita en DISTRACTOR = error de período/métrica)")
    print("\nLectura: recall alto + P(correcto|HIT) alto → retrieval esencialmente resuelto. "
          "Si P(correcto|HIT) cae, sobre todo con citas en DISTRACTOR → justifica extracción estructura-consciente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
