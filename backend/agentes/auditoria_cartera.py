"""Chequeos de cartera deterministas para el Auditor (v2 doc 70 D3 + adenda) — hechos que el análisis
individual (por nombre) no ve.

Dos piezas, puras y testeables, que el orquestador de decisión computa y le pasa al Auditor como insumo:
- **Correlaciones ocultas por FACTOR DE TESIS:** 10 nombres "diversificados" pueden depender del mismo
  cuello, el mismo cliente, la misma ventana de financiamiento o el mismo programa de gobierno. Se mide la
  exposición agregada por factor, no solo por sector/ticker.
- **Tesis CONGELADA:** una posición cuya tesis actual difiere de la de ENTRADA es una decisión nueva
  disfrazada de continuación (el error más caro, doc 70 adenda). Se detecta contra el ledger append-only.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExposicionFactor:
    factor: str                       # p.ej. "cuello:SMR", "financiacion:ventana_abierta", "cliente:hyperscaler"
    peso: float                       # suma de pesos de la cartera expuestos a ese factor
    tickers: list[str] = field(default_factory=list)


def exposicion_por_factor(pesos: dict[str, float], factores: dict[str, list[str]], *,
                          umbral: float = 0.30) -> list[ExposicionFactor]:
    """Agrega el peso de la cartera por FACTOR DE TESIS (doc 70). `factores` = ticker → lista de factores
    (cuello, fuente de financiación, cliente, programa de gobierno). Devuelve los factores cuyo peso agregado
    supera `umbral` — concentración oculta que el análisis por nombre no ve. Ordenado por peso desc."""
    acc: dict[str, ExposicionFactor] = {}
    for tk, w in pesos.items():
        if w <= 0:
            continue
        for f in factores.get(tk.upper(), []):
            e = acc.setdefault(f, ExposicionFactor(factor=f, peso=0.0))
            e.peso = round(e.peso + w, 6)
            e.tickers.append(tk.upper())
    return sorted((e for e in acc.values() if e.peso > umbral + 1e-9), key=lambda e: -e.peso)


def tesis_cambiada(ledger_decisiones, posiciones: set[str]) -> list[dict]:
    """Posiciones VIVAS cuya tesis ACTUAL difiere de la de ENTRADA (doc 70 adenda: 'congelar la tesis'). Una
    tesis nueva es una decisión nueva que debe pasar por el gate desde cero, no una continuación silenciosa.
    Compara, por ticker en cartera, la tesis de la PRIMERA decisión de compra vs la última registrada."""
    por_ticker: dict[str, list] = {}
    for d in ledger_decisiones.decisiones():
        if d.ticker.upper() in {p.upper() for p in posiciones}:
            por_ticker.setdefault(d.ticker.upper(), []).append(d)
    out = []
    for tk, decs in por_ticker.items():
        decs.sort(key=lambda d: d.ts)
        entrada = next((d for d in decs if d.accion in ("comprar", "aumentar")), decs[0])
        ultima = decs[-1]
        if _norm(entrada.tesis) and _norm(ultima.tesis) and _norm(entrada.tesis) != _norm(ultima.tesis):
            out.append({"ticker": tk, "tesis_entrada": entrada.tesis, "tesis_actual": ultima.tesis})
    return out


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def render_para_auditor(exposiciones: list[ExposicionFactor], tesis_cambiadas: list[dict]) -> str:
    """Texto para inyectar en el prompt del Auditor (insumo, no instrucción)."""
    partes = []
    if exposiciones:
        partes.append("CONCENTRACIÓN POR FACTOR DE TESIS (no solo sector):")
        for e in exposiciones:
            partes.append(f"  · {e.factor}: {e.peso:.0%} ({', '.join(e.tickers)})")
    if tesis_cambiadas:
        partes.append("POSICIONES CON TESIS CAMBIADA vs ENTRADA (revisar como decisión nueva):")
        for t in tesis_cambiadas:
            partes.append(f"  · {t['ticker']}: entrada «{t['tesis_entrada'][:60]}» → actual «{t['tesis_actual'][:60]}»")
    return "\n".join(partes) if partes else "(sin concentraciones por factor ni tesis cambiadas)"
