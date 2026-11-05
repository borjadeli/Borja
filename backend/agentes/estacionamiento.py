"""Estacionamiento en ETFs temáticos (r7a #1, doc 78 + revisión r7a) — el capital que NO encuentra nombres con
margen de seguridad NO va a nombres caros para llegar al 90%: se APARCA en los ETFs temáticos (industrias del
futuro) ya definidos para las carteras sombra, ponderados por los clusters del mapa.

Principios (decisión del operador):
- Nunca a nombres sin margen de seguridad solo para desplegar; la caja alta sigue exigiendo tesis macro.
- El estacionamiento NO cuenta como 'operación' (max_ops_semana) ni como posición (max_posiciones).
- Se DESARMA PRIMERO cuando aparece un nombre con margen de seguridad (es residual: más nombres → menos ETF).

Determinista y puro: el residual se reparte mecánicamente por cluster → ETF. El PM no elige los ETFs.
"""
from __future__ import annotations


def tickers_parking(cfg: dict) -> set[str]:
    """Símbolos de los ETFs de estacionamiento (unión del mapa cluster→ETF + el default). Para que el IPS y la
    rotación los EXCLUYAN del conteo de posiciones/ops."""
    est = (cfg or {}).get("estacionamiento") or {}
    etfs = set((est.get("etfs_por_cluster") or {}).values())
    if est.get("etf_default"):
        etfs.add(est["etf_default"])
    return {str(t).upper() for t in etfs}


def pesos_estacionamiento(residual: float, clusters_peso: dict[str, float], *,
                          etfs_por_cluster: dict[str, str], etf_default: str = "SPY") -> dict[str, float]:
    """Reparte `residual` (fracción 0-1) entre ETFs temáticos, ponderando por `clusters_peso` (cluster→peso
    relativo, p.ej. cuántos nombres/EV tiene cada cluster activo). Clusters sin ETF temático → `etf_default`.
    Devuelve {ETF: fracción}. Vacío si no hay residual o no hay clusters."""
    if residual <= 1e-9 or not clusters_peso:
        return {}
    por = {k.lower(): v for k, v in etfs_por_cluster.items()}
    total = sum(w for w in clusters_peso.values() if w > 0) or 1.0
    out: dict[str, float] = {}
    for cluster, w in clusters_peso.items():
        if w <= 0:
            continue
        etf = (por.get((cluster or "").lower()) or etf_default).upper()
        out[etf] = out.get(etf, 0.0) + residual * (w / total)
    return {k: round(v, 6) for k, v in out.items() if v > 1e-9}


def aplicar_estacionamiento(pesos_nombres: dict[str, float], clusters_peso: dict[str, float], cfg: dict, *,
                            caja_macro: float = 0.0) -> tuple[dict[str, float], float]:
    """Dado los pesos de NOMBRES (ya elegidos por margen de seguridad) + la caja macro-justificada, aparca el
    RESIDUAL en ETFs temáticos. `residual = 1 − Σnombres − caja_macro`. Devuelve (pesos_con_ETFs, caja_final).

    'Desarme primero' es implícito: como el residual es `1 − nombres − caja_macro`, cuando aparece un nombre
    nuevo (sube Σnombres) el residual CAE → se achica el ETF, NO la caja macro. No agrega ETF si no está activo."""
    est = (cfg or {}).get("estacionamiento") or {}
    nombres = {t.upper(): w for t, w in pesos_nombres.items() if w > 1e-9}
    if not est.get("activo"):
        return nombres, round(1.0 - sum(nombres.values()), 6)
    residual = round(1.0 - sum(nombres.values()) - max(0.0, caja_macro), 6)
    etfs = pesos_estacionamiento(residual, clusters_peso,
                                 etfs_por_cluster=est.get("etfs_por_cluster") or {},
                                 etf_default=est.get("etf_default", "SPY"))
    finales = dict(nombres)
    for etf, w in etfs.items():                       # un ETF puede coincidir con un nombre (raro) → suma
        finales[etf] = round(finales.get(etf, 0.0) + w, 6)
    return finales, round(1.0 - sum(finales.values()), 6)
