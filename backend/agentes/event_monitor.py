"""Event Monitor (doc 85 F1/§3) — clasifica filings por tipo/ítem para decidir la ACCIÓN, determinista y $0.

El poller trae filings recientes (EDGAR por CIK); este módulo los mapea a un TIER de acción (doc 85):
- DURO: sale solo (tier A/B de salidas): quiebra, non-reliance, restatement, renuncia de auditor con desacuerdos.
- REVISION: va a la cola de deep (P0/P1): earnings, impairment, salida CEO/CFO, aceleración de deuda, deslistado,
  contratos materiales, y todo 10-Q/10-K de una posición (→ EN_REVISION).
- DILUCION: recalcular share count + zona el mismo día (3.02 / S-1 / S-3 / 424B).
- TRIAGE: ítems ambiguos (8.01 / 7.01) → modelo chico decide si toca la tesis.
- IGNORAR: el resto.
NO llama a LLM — solo lee tipo de filing + ítems del 8-K.
"""
from __future__ import annotations

from dataclasses import dataclass

# 8-K por número de ítem → tier (doc 85 §3 + r10). DURO = solo lo catastrófico e inequívoco. 4.01 (cambio de
# auditor) NO es duro por sí solo: sin desacuerdos es rutina → REVISION (el PM/comité mira si hay desacuerdos).
_ITEMS_DURO = {"1.03", "4.02"}                # quiebra · non-reliance/restatement
_ITEMS_REVISION = {"2.02", "2.06", "5.02", "2.04", "3.01", "1.01", "1.02", "2.01", "4.01"}
_ITEMS_DILUCION = {"3.02"}                     # venta de equity no registrada (dilución)
_ITEMS_TRIAGE = {"8.01", "7.01"}              # otros eventos / Reg FD → triage
FORMS_DILUCION = {"S-1", "S-3", "424B5", "424B3", "424B4"}
FORMS_PERIODICOS = {"10-Q", "10-K", "10-Q/A", "10-K/A", "20-F", "40-F", "6-K"}

TIERS = ("DURO", "REVISION", "DILUCION", "TRIAGE", "IGNORAR")


@dataclass
class EventoClasificado:
    ticker: str
    tipo: str                 # 8-K | 10-Q | 10-K | S-3 | …
    tier: str                 # DURO | REVISION | DILUCION | TRIAGE | IGNORAR
    items: list[str]
    fecha: str | None = None
    accession: str | None = None
    nota: str = ""


def _items_set(items) -> set[str]:
    if not items:
        return set()
    s = ",".join(items) if isinstance(items, (list, tuple)) else str(items)
    return {x.strip() for x in s.replace(" ", "").split(",") if x.strip()}


def clasificar_filing(tipo: str, items=None) -> tuple[str, str]:
    """(tier, nota) para un filing. 10-Q/10-K → REVISION (invalida vigencia). 8-K → por ítem. S-3/424B → DILUCION."""
    tipo = (tipo or "").upper()
    its = _items_set(items)
    if tipo in FORMS_PERIODICOS:
        return "REVISION", "reporte periódico → invalida vigencia (EN_REVISION)"
    if tipo in FORMS_DILUCION:
        return "DILUCION", f"{tipo} → recalcular share count + zona"
    if tipo == "8-K":
        if its & _ITEMS_DURO:
            return "DURO", f"8-K duro {sorted(its & _ITEMS_DURO)} → regla de salida (tier A/B)"
        if its & _ITEMS_DILUCION:
            return "DILUCION", "8-K 3.02 → dilución, recalcular zona"
        if its & _ITEMS_REVISION:
            return "REVISION", f"8-K material {sorted(its & _ITEMS_REVISION)} → cola de deep"
        if its & _ITEMS_TRIAGE:
            return "TRIAGE", f"8-K {sorted(its & _ITEMS_TRIAGE)} → triage (¿toca la tesis?)"
    return "IGNORAR", ""


def clasificar_filings(ticker: str, filings) -> list[EventoClasificado]:
    """Clasifica una lista de filings recientes de un nombre (objetos con .tipo/.items/.fecha/.accession_number).
    Devuelve solo los que NO son IGNORAR, ordenados por severidad (DURO primero)."""
    out: list[EventoClasificado] = []
    for f in (filings or []):
        tier, nota = clasificar_filing(getattr(f, "tipo", ""), getattr(f, "items", None))
        if tier == "IGNORAR":
            continue
        fdt = getattr(f, "fecha", None)
        out.append(EventoClasificado(
            ticker=ticker.upper(), tipo=(getattr(f, "tipo", "") or "").upper(), tier=tier,
            items=sorted(_items_set(getattr(f, "items", None))),
            fecha=(fdt.date().isoformat() if hasattr(fdt, "date") else (str(fdt) if fdt else None)),
            accession=getattr(f, "accession_number", None), nota=nota))
    out.sort(key=lambda e: TIERS.index(e.tier))
    return out
