"""Drenaje de la Research Queue (doc 85 F2/§4) — cierra el bucle: cola → comité → ficha.

Toma las solicitudes PENDIENTE por prioridad (P0 primero), y mientras haya presupuesto corre el deep de cada una
(`deep_fn`, inyectable: en real = comité Analista→Bear→Verificador + backfill de la ficha). Marca cada solicitud
HECHO con el resultado (estado de ficha + zona) o DESCARTADO. Núcleo PURO (el deep_fn hace la red/LLM).
"""
from __future__ import annotations

from dataclasses import dataclass

# Errores TRANSITORIOS (infra/facturación): NO descartan el nombre — se reintenta. Un error de crédito o rate-limit
# además FRENA el drenaje (si no hay crédito, cada deep siguiente falla igual y borraría toda la cola — el bug del
# 2026-11-24: 58 nombres del operador descartados en fila por "credit balance too low").
_TRANSITORIOS = ("credit balance", "rate limit", "rate_limit", "429", "overloaded", "timeout", "timed out",
                 "connection", "econnreset", "500", "502", "503", "504", "internal server error",
                 "service unavailable", "temporarily")
_FRENA_DRENAJE = ("credit balance", "rate limit", "rate_limit", "429", "overloaded", "insufficient")


def _es_transitorio(msg: str) -> bool:
    m = msg.lower()
    return any(k in m for k in _TRANSITORIOS)


def _frena_drenaje(msg: str) -> bool:
    m = msg.lower()
    return any(k in m for k in _FRENA_DRENAJE)


@dataclass
class ResultadoDrenaje:
    corridos: list[dict]          # [{ticker, estado_ficha, zona, costo}]
    saltados: list[dict]          # [{ticker, motivo}] (sin presupuesto / transitorios)
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
        except Exception as e:  # noqa: BLE001 — un deep que falla no tumba el drenaje
            msg = str(e)
            if _es_transitorio(msg):
                queue.marcar(req.id, "PENDIENTE")   # infra/crédito → NO se descarta: queda para reintentar
                res.saltados.append({"ticker": req.ticker, "motivo": f"transitorio (reintenta): {msg[:120]}"})
                if _frena_drenaje(msg):             # sin crédito/rate-limit: todo lo que siga falla igual → frená
                    res.saltados.append({"ticker": "*", "motivo": "drenaje FRENADO (crédito/rate-limit agotado)"})
                    break
                continue
            queue.marcar(req.id, "DESCARTADO", resultado={"error": msg[:200]})   # terminal (ticker inválido/sin datos)
            res.saltados.append({"ticker": req.ticker, "motivo": f"deep falló: {msg}"})
            continue
        costo = float(r.get("costo", 0.0) or 0.0)
        restante -= costo
        res.costo_total += costo
        queue.marcar(req.id, "HECHO", costo_usd=costo,
                     resultado={"estado_ficha": r.get("estado_ficha"), "zona": r.get("zona")})
        res.corridos.append({"ticker": req.ticker, "estado_ficha": r.get("estado_ficha"),
                             "zona": r.get("zona"), "costo": costo})
    return res
