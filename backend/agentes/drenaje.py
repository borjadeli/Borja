"""Drenaje de la Research Queue (doc 85 F2/§4) — cierra el bucle: cola → comité → ficha.

Toma las solicitudes PENDIENTE por prioridad (P0 primero), y mientras haya presupuesto corre el deep de cada una
(`deep_fn`, inyectable: en real = comité Analista→Bear→Verificador + backfill de la ficha). Marca cada solicitud
HECHO con el resultado (estado de ficha + zona) o DESCARTADO. Núcleo PURO (el deep_fn hace la red/LLM).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ResultadoDrenaje:
    corridos: list[dict]          # [{ticker, estado_ficha, zona, costo}]
    saltados: list[dict]          # [{ticker, motivo}] (sin presupuesto)
    costo_total: float = 0.0


def drenar(queue, *, deep_fn, presupuesto_disponible: float, costo_estimado: float = 2.0,
           max_n: int | None = None) -> ResultadoDrenaje:
    """`queue` = ResearchQueue. `deep_fn(ticker, *, ciego) -> {estado_ficha, zona, costo}`. Reserva el costo
    estimado ANTES de cada deep (no rompe el presupuesto). Devuelve el resultado; marca las solicitudes."""
    res = ResultadoDrenaje(corridos=[], saltados=[])
    restante = float(presupuesto_disponible or 0.0)
    pend = queue.pendientes()
    if max_n is not None:
        pend = pend[:max_n]
    for req in pend:
        if restante < costo_estimado:                 # reserva peor-caso: sin presupuesto → a cola (no se rompe)
            res.saltados.append({"ticker": req.ticker, "motivo": "sin presupuesto"})
            continue
        queue.marcar(req.id, "CORRIENDO")
        try:
            r = deep_fn(req.ticker, ciego=req.ciego_a_ficha_previa) or {}
        except Exception as e:  # noqa: BLE001 — un deep que falla no tumba el drenaje; la solicitud queda DESCARTADA
            queue.marcar(req.id, "DESCARTADO", resultado={"error": str(e)[:200]})
            res.saltados.append({"ticker": req.ticker, "motivo": f"deep falló: {e}"})
            continue
        costo = float(r.get("costo", 0.0) or 0.0)
        restante -= costo
        res.costo_total += costo
        queue.marcar(req.id, "HECHO", costo_usd=costo,
                     resultado={"estado_ficha": r.get("estado_ficha"), "zona": r.get("zona")})
        res.corridos.append({"ticker": req.ticker, "estado_ficha": r.get("estado_ficha"),
                             "zona": r.get("zona"), "costo": costo})
    return res
