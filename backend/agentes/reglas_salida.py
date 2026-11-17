"""Reglas de salida (doc 85 F2/§6) — regla para lo objetivo/binario/asimétrico; juicio para lo continuo/ruidoso.

El poller (F1) clasifica filings; este módulo mapea los que ROMPEN la base informativa de la tesis a una ACCIÓN
determinista sobre una POSICIÓN. Lo crujiente no es automatizar el precio: es el PRE-COMPROMISO + disparar por
CAMBIO, no por nivel (cada ficha guarda una `línea base` de banderas endémicas; la regla dispara solo si aparece
algo que NO estaba — en small caps pre-revenue going concern/material weakness son casi endémicos).

Tiers:
- **A (regla):** quiebra (8-K 1.03), non-reliance/restatement (4.02), renuncia de auditor con desacuerdos (4.01)
  → SALIDA_TOTAL (advisory: vender urgente; paper: apertura siguiente con slippage).
- **B (regla):** going concern NUEVO (ausente en la línea base) · falsador DURO cumplido → RECORTE_50 + deep P0.
- **C (juicio con escalada):** material weakness nueva · salida CEO/CFO · otro cambio de auditor · aviso de precio
  mínimo · falsador BLANDO → DESPERTAR al PM con respuesta obligatoria.
Puro, determinista, $0. Solo aplica a POSICIONES (lo que no se tiene, no se vende).
"""
from __future__ import annotations

from dataclasses import dataclass

# 8-K por ítem → tier de salida (doc 85 §6). Subconjunto "duro" del event_monitor, con su consecuencia.
_ITEMS_TIER_A = {"1.03": "quiebra", "4.02": "non-reliance/restatement", "4.01": "cambio de auditor con desacuerdos"}
_ITEMS_TIER_C = {"5.02": "salida de CEO/CFO", "3.01": "aviso de deslistado / precio mínimo"}

ACCIONES = ("SALIDA_TOTAL", "RECORTE_50", "DESPERTAR")


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

    # tier B: falsador DURO cumplido → su consecuencia pre-comprometida
    for tk, fls in (falsadores_confirmados or {}).items():
        tk = tk.upper()
        if tk not in pos:
            continue
        for fl in fls:
            if (fl.get("tipo") or "").upper() != "DURO":
                continue
            cons = (fl.get("consecuencia") or "RECORTE_50").upper()
            acc = "SALIDA_TOTAL" if cons == "SALIDA" else "RECORTE_50"
            if (tk, acc) in vistos:
                continue
            out.append(AccionSalida(tk, "B", acc, f"tier B: falsador DURO '{fl.get('id', '?')}' cumplido",
                                    fl.get("id", "")))
            vistos.add((tk, acc))

    out.sort(key=lambda a: ("A", "B", "C").index(a.tier))
    return out
