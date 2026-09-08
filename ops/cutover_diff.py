"""Reporte de IMPACTO del cutover (doc 34 §4, paso previo al switch) — superficie NUEVA vs libro paper VIVO.

    .venv/bin/python -m ops.cutover_diff [TICKER ...]

Corre la superficie nueva (celdas + sizing 2-ejes) sobre el universo (libro vivo ∪ muestra) y la diffea
contra el libro paper REAL (`data/nucleo_paper/libro.json`, merito-based). Responde la pregunta del cutover:
**si cortáramos hoy, cómo cambia el libro** — qué nombres se caen, cuáles entran, cómo cambia el size y POR QUÉ
(reason code de sizing). NO toca el paper: es solo lectura + shadow. Sin LLM (fact_store + XBRL + market).

Los nombres del libro vivo SIN evidencia extraída en el fact_store salen como ABSTENCIÓN — es el estado real:
la superficie nueva no decide sin evidencia, y el reporte cuantifica ese gap de extracción que bloquea el cutover.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from backend.database import session_scope
from backend.nucleo import fact_store as FS
from backend.nucleo.carril import construir_carril, construir_hechos_carril
from backend.nucleo.cartera_celdas import construir_cartera
from backend.nucleo.ranking_lexicografico import (
    clasificacion_2ejes, rankear_por_celda, tasa_abstencion,
)
from ops.shadow_ranking import MUESTRA, construir

LIBRO = Path(__file__).resolve().parent.parent / "data" / "nucleo_paper" / "libro.json"


def cargar_libro_vivo() -> dict[str, dict]:
    """{ticker: {sizing, merito, arquetipo}} del libro paper vivo (merito-based)."""
    if not LIBRO.exists():
        return {}
    return json.loads(LIBRO.read_text(encoding="utf-8")).get("posiciones", {})


def main(argv: list[str]) -> int:
    vivo = cargar_libro_vivo()
    universo = sorted(set([t.upper() for t in argv]) or set(vivo) | set(MUESTRA))

    cands = []
    with session_scope() as s:
        for t in universo:
            c = construir(s, t)
            if c is not None:
                cands.append(c)

    por_celda = rankear_por_celda(cands)
    cart = construir_cartera(por_celda)
    nuevo = {p.ticker: p for p in cart.posiciones}
    por_ticker = {c.ticker: c for c in cands}

    # Buckets del diff — los que salen del libro duro se rutean por DESTINO real (doc 29): no todo es cash.
    entra, en_ambos = [], []
    a_carril, a_investigacion, a_descarte, sin_datos = [], [], [], []
    for t in sorted(set(vivo) | set(nuevo)):
        en_v, en_n = t in vivo, t in nuevo
        c = por_ticker.get(t)
        cls = clasificacion_2ejes(c) if c is not None else {"eje_evidencia": "SIN_DATOS", "etiqueta": "SIN_DATOS"}
        etiqueta = cls["etiqueta"]
        if en_v and en_n:
            en_ambos.append((t, vivo[t]["sizing"], nuevo[t].size, etiqueta, nuevo[t].cap))
        elif en_v and not en_n:
            sz = vivo[t]["sizing"]
            destino = cls["eje_evidencia"]
            if c is None:
                sin_datos.append((t, sz, "sin snapshot en fact_store (no extraído)"))
            elif destino == "CARRIL":
                a_carril.append((t, sz, f"opcionalidad ({c.estado_valuacion}) — ya-priceada/pura opción"))
            elif destino == "INVESTIGACION":
                a_investigacion.append((t, sz, c.motivo_abstencion))
            elif destino == "DESCARTE":
                a_descarte.append((t, sz, "no elegible (falla 3 pilares)"))
            else:
                a_descarte.append((t, sz, f"elegible sin entrar (cuota/piso/max-pos) — {etiqueta}"))
        elif en_n and not en_v:
            entra.append((t, nuevo[t].size, etiqueta, c.cap_reason if c is not None else "?"))

    print("=" * 100)
    print("CUTOVER IMPACT — superficie NUEVA (celdas+sizing 2-ejes) vs libro paper VIVO (merito). SHADOW, no toca el paper.")
    print("=" * 100)
    print(f"Universo evaluado: {len(universo)} · candidatos construidos: {len(cands)} · "
          f"tasa de abstención: {tasa_abstencion(cands):.0%}")
    print(f"Libro vivo: {len(vivo)} posiciones · Cartera nueva: {len(nuevo)} posiciones "
          f"(invertido {cart.invertido:.0%}, cash {cart.cash:.0%}) · política {cart.politica_version}/{cart.politica_hash}")

    def _bloque(titulo, items):
        print("-" * 100)
        print(f"{titulo} ({len(items)}):")
        for t, sz, motivo in sorted(items, key=lambda x: -x[1]):
            print(f"  {t:6} (vivo {sz:.1%})  →  {motivo}")

    print("\n" + "-" * 100)
    print(f"EN AMBOS — libro duro nuevo, cambio de size (merito → 2-ejes) ({len(en_ambos)}):")
    for t, sv, sn, etq, cap in sorted(en_ambos, key=lambda x: -x[2]):
        flecha = "↑" if sn > sv + 1e-4 else ("↓" if sn < sv - 1e-4 else "=")
        print(f"  {flecha} {t:6} {sv:.1%} → {sn:.1%}  [{etq}]  (cap {cap:.1%})")
    print("-" * 100)
    print(f"ENTRAN al libro duro — no estaban en el vivo ({len(entra)}):")
    for t, sz, etq, reason in sorted(entra, key=lambda x: -x[1]):
        print(f"  ⬆ {t:6} → {sz:.1%}  [{etq}]  (ligó: {reason})")

    # Carril: los candidatos de opcionalidad → construir_carril (gate §2 + sizing §4). Hoy SIN hechos del gate
    # (no extraídos) → admite 0; el reporte muestra el sizing que TENDRÍAN cuando la rúbrica exista (doc 29 §9).
    carril_cands = [por_ticker[t] for t, _, _ in a_carril if t in por_ticker]
    carril_hechos = {}
    with session_scope() as s:
        for c in carril_cands:
            carril_hechos[c.ticker] = construir_hechos_carril(c.ticker, FS.snapshot_vigente(s, c.ticker),
                                                              runway_anos=c.runway)
    carril = construir_carril(carril_cands, carril_hechos)
    _bloque("→ CARRIL ESPECULATIVO (doc 29) — elegibles pero opcionalidad, NO cash (sizing PROPIO acá)", a_carril)
    print(f"    carril admitidos: {len(carril.posiciones)}/{len(carril_cands)} · invertido {carril.invertido:.0%} "
          f"(presupuesto piso {carril.presupuesto:.0%}). {len(carril.rechazados)} pendientes del gate §2:")
    for r in carril.rechazados[:3]:
        print(f"      · {r['ticker']}: {r['motivo'][:88]}")
    if carril.orden_placeholder:
        print("    ⚠ orden y admisión NO definitivos: falta extraer los hechos del gate §2 + la rúbrica §3 (PM-LLM).")
    _bloque("→ INVESTIGACIÓN — evidencia insuficiente (NO venta: gap de extracción)", a_investigacion)
    _bloque("→ SIN DATOS — no extraído al fact_store (gap de extracción)", sin_datos)
    _bloque("→ DESCARTE — no elegible", a_descarte)

    print("=" * 100)
    hard = len(en_ambos) + len(entra)
    print(f"RECLASIFICACIÓN del libro vivo ({len(vivo)}): {len(en_ambos)} siguen en libro duro · {len(entra)} nuevos al duro · "
          f"{len(a_carril)} → carril · {len(a_investigacion)+len(sin_datos)} → investigación/sin-datos · {len(a_descarte)} descarte.")
    print(f"Libro duro nuevo: {hard} posiciones, {cart.invertido:.0%} invertido. Carril NO construido aún (falta rúbrica §3 + sizing §4/§5).")
    print("CLAVE: la nueva NO liquida a cash — RE-RUTEA. El grueso va al carril (opcionalidad), que todavía no se")
    print("dimensiona. Bloqueos del switch: (1) extraer investigación/sin-datos, (2) construir el carril, (3) revisar los del duro.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
