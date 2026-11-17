"""run_cycle (doc 85 F1-F2/§9) — el pipeline diario encadenado que hace correr al PM solo.

Encadena, idempotente: poller (vigila + invalida vigencia + reglas de salida) → latido (zonas + alertas) →
drenaje de la cola → decide si DESPERTAR al PM (cambio de zona / deep terminado en COMPRA / regla de salida) →
PM solo si hay motivo. Núcleo PURO (funciones inyectables); el ops cablea lo real. El orden importa: si el PM
corre antes del drenaje, decide con fichas viejas. Un reinicio NO debe duplicar (lock + idempotencia en el ops).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ResultadoCiclo:
    poller: dict = field(default_factory=dict)       # {en_revision, eventos, salidas}
    cambios_zona: list[dict] = field(default_factory=list)
    deeps_hechos: list[dict] = field(default_factory=list)
    motivos_despertar: list[str] = field(default_factory=list)
    desperto_pm: bool = False
    pm_resultado: object | None = None


def razones_despertar(*, cambios_zona, deeps_hechos, salidas) -> list[str]:
    """Doc 85 §3: el PM corre (además del semanal) si algo cambió — zona de una posición, un nombre que entró a
    COMPRA, un deep pedido que terminó, o una regla de salida que se disparó. 'No hacer nada' sigue siendo válido."""
    r: list[str] = []
    for c in (cambios_zona or []):
        z = (c.get("zona") or "").upper()
        if z == "COMPRA":
            r.append(f"{c.get('ticker')} entró a COMPRA")
        elif z in ("RECORTE", "SALIDA"):
            r.append(f"{c.get('ticker')} entró a {z}")
    for d in (deeps_hechos or []):
        if (d.get("zona") or "").upper() == "COMPRA":
            r.append(f"deep de {d.get('ticker')} → COMPRA")
    for s in (salidas or []):
        r.append(f"regla de salida tier {getattr(s, 'tier', '?')} en {getattr(s, 'ticker', '?')} ({getattr(s, 'accion', '?')})")
    return r


def correr_ciclo(*, poller_fn, latido_fn, drenar_fn, pm_fn=None, forzar_pm: bool = False) -> ResultadoCiclo:
    """Encadena las etapas (inyectables) y decide el despertar. `poller_fn()`→{en_revision,eventos,salidas};
    `latido_fn()`→[cambios_zona]; `drenar_fn()`→[deeps_hechos]; `pm_fn(motivos)`→resultado (opcional). `forzar_pm`
    = corrida semanal (despierta aunque no haya motivo). El PM corre DESPUÉS del drenaje (fichas frescas)."""
    res = ResultadoCiclo()
    res.poller = poller_fn() or {}
    res.cambios_zona = latido_fn() or []
    res.deeps_hechos = drenar_fn() or []
    res.motivos_despertar = razones_despertar(
        cambios_zona=res.cambios_zona, deeps_hechos=res.deeps_hechos, salidas=res.poller.get("salidas") or [])
    if pm_fn is not None and (forzar_pm or res.motivos_despertar):
        res.desperto_pm = True
        res.pm_resultado = pm_fn(res.motivos_despertar)
    return res
