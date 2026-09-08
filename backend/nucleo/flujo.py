"""Flujo del núcleo de punta a punta — Núcleo consolidado v3, §2.

Compone las piezas deterministas en el flujo único cerrado:

    arquetipo → gate de evidencia → Quality × Asimetría (mérito) → Fragility →
    Hard Cap → [Selector normaliza] → sizing → [5 vías para salida].

Dos funciones:
  evaluar_empresa() — corre el flujo POR empresa hasta el mérito + Hard Cap.
                      El sizing final NO se decide acá: depende de la
                      normalización RELATIVA del Selector sobre todo el conjunto.
  armar_cartera()   — toma las evaluaciones, el Selector normaliza por ranking
                      top-N, sizing recorta a [5%, Hard Cap] y se aplica el cubo
                      agregado de residual-cero (§11.2).

Puro y determinista: recibe hechos ya extraídos. Es la base del shadow-runner
que comparará el núcleo nuevo contra el Portfolio viejo.

Dos vías de rechazo (§3): el gate y CRR-crítico. CRR-crítico lo resuelve el
sub-gate financiero (capital_raise_risk + going concern de Fase 0) ANTES de
llamar acá; este flujo asume que CRR-crítico ya rechazó si correspondía y recibe
cap_crr como cap (no multiplicador).
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.nucleo.arquetipo import HechosArquetipo, clasificar_arquetipo
from backend.nucleo.constantes import TOPE_INVERTIDO
from backend.nucleo.fragility import (
    HechosFragility,
    calcular_fragility_score,
    cap_celda,
    es_residual_cero,
    exposicion_cubo_excede,
)
from backend.nucleo.gate import HechosGate, evaluar_gate
from backend.nucleo.quality import HechosQuality, calcular_quality_tier
from backend.nucleo.selector import normalizar_merito
from backend.nucleo.sizing import asimetria_vigente, hard_cap, merito, sizing_final


@dataclass
class EntradaEmpresa:
    """Todo lo que el núcleo necesita para evaluar una empresa. Cada bloque de
    hechos lo trae el extractor LLM con fuente; acá llegan como datos."""
    ticker: str
    hechos_arquetipo: HechosArquetipo
    hechos_gate: HechosGate
    hechos_fragility: HechosFragility
    hechos_quality: HechosQuality
    precio: float
    bull: float
    bear: float
    cap_crr: float | None = None      # cap de CRR (Medio/Alto); None = no restringe.
    crr_critico: bool = False         # vía de rechazo financiera (sub-gate).


def evaluar_empresa(e: EntradaEmpresa) -> dict:
    """Corre el flujo por empresa hasta mérito + Hard Cap. Determinista.

    Devuelve dict con la decisión ('rechazo' | 'watchlist' | 'candidata') y la
    traza completa. 'candidata' = pasó las dos vías de rechazo y tiene mérito;
    el sizing definitivo lo fija armar_cartera() con la normalización relativa.
    """
    res = {"ticker": e.ticker}

    # Vía de rechazo financiera (§3): CRR-crítico.
    if e.crr_critico:
        res.update({"decision": "rechazo", "motivo": "CRR-crítico (sub-gate financiero)"})
        return res

    # Paso 1 — arquetipo.
    arq = clasificar_arquetipo(e.hechos_arquetipo)
    arquetipo = arq["arquetipo"]
    res["arquetipo"] = arq

    # Paso 2 — gate de evidencia (la otra vía de rechazo).
    e.hechos_gate.arquetipo = arquetipo
    g = evaluar_gate(e.hechos_gate)
    res["gate"] = g
    if not g["pasa"]:
        # 'todavia_no' → watchlist por timing (§5.5); 'no_pasa' → rechazo.
        res["decision"] = "watchlist" if g["estado"] == "todavia_no" else "rechazo"
        res["motivo"] = f"gate {g['estado']}: {'; '.join(g['fallos'] or g['timing'])}"
        return res

    # Paso 3 — Quality × Asimetría → mérito.
    q = calcular_quality_tier(e.hechos_quality)
    asim = asimetria_vigente(e.bull, e.precio, e.bear)
    m = merito(q["tier"], asim)
    res.update({"quality": q, "asimetria": asim, "merito": m})

    # Paso 4 — Fragility → cap de celda → Hard Cap.
    frag = calcular_fragility_score(e.hechos_fragility)
    cap_c = cap_celda(arquetipo, frag["score"])
    hc = hard_cap(cap_c, e.cap_crr)
    res.update({
        "fragility": frag,
        "cap_celda": cap_c,
        "hard_cap": hc,
        "residual_cero": es_residual_cero(arquetipo, frag["score"]),
        "decision": "candidata",
    })
    return res


def armar_cartera(evaluaciones: list[dict], target_invertido: float = TOPE_INVERTIDO) -> dict:
    """Selector normaliza por ranking top-N → sizing recorta a [5%, Hard Cap] →
    cubo agregado de residual-cero (§9, §11.2).

    evaluaciones: salidas de evaluar_empresa(). Solo entran las 'candidata' con
    mérito calculable. Devuelve el mix propuesto + el chequeo del cubo.
    """
    candidatas = [ev for ev in evaluaciones
                  if ev.get("decision") == "candidata" and ev.get("merito") is not None]

    # Selector — ranking relativo top-N (target = capital bruto a repartir).
    rankeadas = normalizar_merito(
        [{"ticker": c["ticker"], "merito": c["merito"], "_ev": c} for c in candidatas],
        target=target_invertido,
    )

    mix: list[dict] = []
    for r in rankeadas:
        ev = r["_ev"]
        s = sizing_final(r["bruto"], ev["hard_cap"]) if r["en_top_n"] else {
            "entra": False, "sizing": 0.0, "destino": "watchlist",
            "motivo": "fuera del top-N por mérito",
        }
        mix.append({
            "ticker": ev["ticker"],
            "arquetipo": ev["arquetipo"]["arquetipo"],
            "merito": ev["merito"],
            "bruto_pedido": r["bruto"],
            "hard_cap": ev["hard_cap"],
            "residual_cero": ev["residual_cero"],
            **s,
        })

    # Cubo agregado de residual-cero (§11.2): máx 8% en posiciones de ruptura ~total.
    pesos_rc = [m["sizing"] for m in mix if m["entra"] and m["residual_cero"]]
    cubo = exposicion_cubo_excede(pesos_rc)

    return {
        "mix": mix,
        "invertido_total": sum(m["sizing"] for m in mix if m["entra"]),
        "cubo_residual_cero": cubo,
    }
