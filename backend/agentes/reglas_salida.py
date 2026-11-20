"""Reglas de salida (doc 85 §6 + r10) — DETERMINISMO AL MÍNIMO: el PM decide, el Auditor cuestiona.

Decisión del operador (r10): la ÚNICA salida que se ejecuta sola es la catastrófica e inequívoca (tier A: quiebra
1.03 · restatement/non-reliance 4.02) — es risk-off puro, parte del IPS. TODO lo demás (falsador DURO, going
concern, salida de CEO, material weakness, aviso de deslistado, zona SALIDA) **DESPIERTA al PM** con respuesta
obligatoria; el PM + el Auditor deciden. No hay auto-trim determinista por nivel ni por precio.

El poller (F1) clasifica filings; este módulo mapea solo los catastróficos a SALIDA_TOTAL automática y el resto a
DESPERTAR. Puro, $0. Solo aplica a POSICIONES (lo que no se tiene, no se vende).
"""
from __future__ import annotations

from dataclasses import dataclass

# 8-K por ítem → tier (r10). Tier A = SOLO lo catastrófico e inequívoco (auto). 4.01 (cambio de auditor) NO es
# duro por sí solo — sin desacuerdos es rutina → DESPERTAR (tier C), no salida total.
_ITEMS_TIER_A = {"1.03": "quiebra", "4.02": "non-reliance/restatement"}
_ITEMS_TIER_C = {"5.02": "salida de CEO/CFO", "3.01": "aviso de deslistado / precio mínimo",
                 "4.01": "cambio de auditor (revisar si hay desacuerdos)"}

ACCIONES = ("SALIDA_TOTAL", "DESPERTAR")   # r10: tier B/C → DESPERTAR (sin auto-trim); solo tier A auto-ejecuta


@dataclass
class AccionSalida:
    ticker: str
    tier: str           # A | B | C
    accion: str         # SALIDA_TOTAL | RECORTE_50 | DESPERTAR
    motivo: str
    fuente: str = ""    # accession / falsador id


def _items(e) -> set[str]:
    return set(getattr(e, "items", []) or [])


def evaluar_reglas_salida(eventos, *, posiciones: set[str],
                          banderas_base: dict[str, set[str]] | None = None,
                          falsadores_confirmados: dict[str, list[dict]] | None = None) -> list[AccionSalida]:
    """`eventos` = EventoClasificado del poller. `posiciones` = tickers en cartera. `banderas_base` = ticker →
    banderas que YA estaban al deep (going_concern, material_weakness) → no disparan. `falsadores_confirmados` =
    ticker → [{id, tipo, consecuencia}]. Devuelve las acciones de salida sobre POSICIONES, tier A primero."""
    pos = {t.upper() for t in (posiciones or set())}
    base = {t.upper(): set(v) for t, v in (banderas_base or {}).items()}
    out: list[AccionSalida] = []
    vistos: set[tuple[str, str]] = set()      # dedup (ticker, accion)

    for e in (eventos or []):
        tk = getattr(e, "ticker", "").upper()
        if tk not in pos:
            continue
        its = _items(e)
        dur = its & set(_ITEMS_TIER_A)
        if dur and (tk, "SALIDA_TOTAL") not in vistos:
            motivo = "; ".join(_ITEMS_TIER_A[i] for i in sorted(dur))
            out.append(AccionSalida(tk, "A", "SALIDA_TOTAL", f"tier A: {motivo}", getattr(e, "accession", "") or ""))
            vistos.add((tk, "SALIDA_TOTAL"))
        tc = its & set(_ITEMS_TIER_C)
        if tc and (tk, "DESPERTAR") not in vistos:
            out.append(AccionSalida(tk, "C", "DESPERTAR", f"tier C: {'; '.join(_ITEMS_TIER_C[i] for i in sorted(tc))}",
                                    getattr(e, "accession", "") or ""))
            vistos.add((tk, "DESPERTAR"))

    # tier B: falsador DURO cumplido → DESPIERTA al PM (r10: NO auto-trim; el PM + Auditor deciden recortar/salir)
    for tk, fls in (falsadores_confirmados or {}).items():
        tk = tk.upper()
        if tk not in pos:
            continue
        for fl in fls:
            if (fl.get("tipo") or "").upper() != "DURO":
                continue
            if (tk, "DESPERTAR") in vistos:
                continue
            cons = (fl.get("consecuencia") or "REVISION").upper()
            est = (fl.get("estado") or "").upper()
            desc = {"CONFIRMED": "DISPARADO (verificado)",
                    "SUSPECTED": "SIN VERIFICAR (falta el dato — NO confirmado)"}.get(est, est or "?")
            out.append(AccionSalida(tk, "B", "DESPERTAR",
                                    f"tier B: falsador DURO '{fl.get('id', '?')}' {desc} (sugerencia: {cons})",
                                    fl.get("id", "")))
            vistos.add((tk, "DESPERTAR"))

    out.sort(key=lambda a: ("A", "B", "C").index(a.tier))
    return out


def pesos_tras_salidas(pesos: dict[str, float], salidas: list[AccionSalida]) -> dict[str, float]:
    """Aplica las salidas DETERMINISTAS a los pesos actuales para la ejecución: SALIDA_TOTAL → 0 · RECORTE_50 →
    mitad · DESPERTAR → no toca pesos (lo decide el PM). Devuelve los pesos-objetivo (sin ceros)."""
    out = {t.upper(): w for t, w in (pesos or {}).items()}
    for s in salidas or []:
        tk = s.ticker.upper()
        if tk not in out:
            continue
        if s.accion == "SALIDA_TOTAL":
            out[tk] = 0.0
        elif s.accion == "RECORTE_50":
            out[tk] = round(out[tk] * 0.5, 6)
    return {t: w for t, w in out.items() if w > 0}
