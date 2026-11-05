"""Embudo / hit-rate de discovery (doc 76, capa E) — ¿lo que discovery propone, sirve?

Determinista, API-free: proyecta las colas de discovery (empresas + cuellos) y las JOINea con el estado
downstream (nx_empresa, dossiers) para ver el EMBUDO: propuesta → entró al universo → se analizó → con qué
convicción/clasificación. Es la visibilidad que deja JUZGAR a discovery (y, con el tiempo, su hit-rate) antes
de darle más autonomía. No decide nada; informa.

Inyección de dependencias (universo_estado, dossier_fn) → testeable sin DB ni cache reales.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class FilaHitrate:
    ticker: str
    cuello: str
    estado_cola: str                 # aprobada | observacion | rechazada | vencida
    en_universo: bool
    estado_universo: str | None      # estado en nx_empresa (Candidata, …) si entró
    analizada: bool                  # ¿hay dossier?
    conviccion: float | None
    clasificacion: str | None        # core | satelite | especulativa | watchlist
    tesis_corta: str = ""            # por qué la propuso el agente (contexto, no sólo el ticker)
    por_que_ahora: str = ""          # el catalizador / razón de timing
    fuentes: list[str] | None = None # links primarios que citó la propuesta
    market_cap: float | None = None  # cap en USD si quedó resuelto (None en extranjeros sin resolver)


def embudo_discovery(*, propuestas: dict, universo_estado: dict[str, str],
                     dossier_fn: Callable[[str], object | None]) -> dict:
    """`propuestas`: proyección de ColaPropuestas (`{ticker: {estado, propuesta}}`). `universo_estado`: estado
    en nx_empresa de los tickers de fuente discovery. `dossier_fn(ticker)`: el último dossier o None."""
    filas: list[FilaHitrate] = []
    for tk, v in propuestas.items():
        d = dossier_fn(tk)
        inv = getattr(d, "invertibilidad", None) if d is not None else None
        p = v.get("propuesta") or {}
        filas.append(FilaHitrate(
            ticker=tk, cuello=p.get("cuello", ""),
            estado_cola=v.get("estado", "?"),
            en_universo=tk in universo_estado, estado_universo=universo_estado.get(tk),
            analizada=d is not None,
            conviccion=(getattr(d, "conviccion_0_1", None) if d is not None else None),
            clasificacion=(getattr(inv, "analyst_classification", None) if inv is not None else None),
            tesis_corta=p.get("tesis_corta", "") or "",
            por_que_ahora=p.get("por_que_ahora", "") or "",
            fuentes=list(p.get("fuentes") or []),
            market_cap=p.get("market_cap"),
        ))
    filas.sort(key=lambda f: (f.conviccion is None, -(f.conviccion or 0.0)))   # mayor convicción primero
    funnel = {
        "propuestas": len(filas),
        "al_universo": sum(1 for f in filas if f.en_universo),
        "analizadas": sum(1 for f in filas if f.analizada),
        "conviccion_alta": sum(1 for f in filas if (f.conviccion or 0.0) >= 0.6),
        "rechazadas": sum(1 for f in filas if f.estado_cola == "rechazada"),
    }
    return {"filas": filas, "funnel": funnel}


def embudo_nodos(nodos: dict) -> dict:
    """`nodos`: proyección de ColaNodos. Embudo de cuellos: propuestos → aprobados por el curador → al mapa."""
    detalle = [{"nombre": k, "estado": v.get("estado", "?")} for k, v in nodos.items()]
    return {
        "propuestos": len(detalle),
        "al_mapa": sum(1 for d in detalle if d["estado"] == "aprobada"),
        "rechazados": sum(1 for d in detalle if d["estado"] == "rechazada"),
        "detalle": detalle,
    }
