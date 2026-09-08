"""Bridge mínimo revenue→precio + CAGR implícito FALSADOR (doc 28 §2, §4).

Bridge de diagnóstico en estado estacionario (perpetuidad UFCF/r): EV = (revenue × margen) / r —
la forma más simple consistente con "terminal = UFCF/r, g=0" (doc 28 §2). NO es el generador de
precio final (eso son los templates completos por arquetipo); acá alcanza para el FALSADOR, que es
un diagnóstico, no un price target.

El falsador (doc 28 §4) responde una sola pregunta, en todos los arquetipos: invirtiendo el bridge
desde el precio actual con la r del arquetipo, ¿qué revenue(T) descuenta hoy el mercado? Si ese
revenue implícito ya iguala o supera el bull OPERABLE (evidencia contratada), el mercado ya paga
la tesis entera → NO hay upside de evidencia dura → el nombre es PURA OPCIONALIDAD: fuera del libro
duro, solo puede entrar vía el CARRIL ESPECULATIVO si pasa su gate (doc 29 — reemplazó al viejo
"sleeve 2%" de doc 28 §4). Es el chequeo que más tesis mata y el más barato de correr.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.nucleo import politica


def precio_desde_revenue(revenue_t: float, margen: float | None, r: float,
                         shares: float | None, caja_neta: float = 0.0) -> float | None:
    """Bridge forward (perpetuidad): revenue → UFCF(×margen) → EV(/r) → equity → precio."""
    if not shares or shares <= 0 or r <= 0 or margen is None:
        return None
    ev = (revenue_t * margen) / r
    equity = ev + caja_neta
    return equity / shares


def revenue_implicito(precio: float, margen: float | None, r: float,
                      shares: float | None, caja_neta: float = 0.0) -> float | None:
    """Inverso: dado el precio, ¿qué revenue(T) descuenta el mercado? (doc 28 §4)."""
    if not shares or shares <= 0 or r <= 0 or not margen or margen <= 0:
        return None
    equity = precio * shares
    ev = equity - caja_neta
    return ev * r / margen


@dataclass
class Falsador:
    revenue_implicito: float | None
    revenue_bull_operable: float | None
    ya_priceado: bool               # el precio ya paga el bull operable entero
    ratio: float | None             # revenue_implícito / revenue_bull_operable
    veredicto: str


def falsador_cagr(precio: float, revenue_bull_operable: float | None, margen: float | None,
                  arquetipo: str, shares: float | None, caja_neta: float = 0.0) -> Falsador:
    """¿El precio ya paga el bull operable? Si sí, la tesis vive solo en el option ledger."""
    r = politica.r_efectiva(arquetipo)
    # Guarda 1 (causa raíz): margen bajo → la perpetuidad sobre el margen ACTUAL no es fiable
    # (el mercado pricea expansión de margen, no revenue explotando). No se emite número.
    if margen is not None and 0 < margen < politica.MARGEN_MIN_PERPETUIDAD:
        return Falsador(None, revenue_bull_operable, False, None,
                        f"no_evaluable: margen {margen:.1%} < {politica.MARGEN_MIN_PERPETUIDAD:.0%} "
                        "→ margen no normalizado (requiere template por arquetipo)")
    rimp = revenue_implicito(precio, margen, r, shares, caja_neta)
    if rimp is None or not revenue_bull_operable or revenue_bull_operable <= 0:
        return Falsador(rimp, revenue_bull_operable, False, None, "no_evaluable")
    ratio = rimp / revenue_bull_operable
    # Guarda 2 (backstop): revenue implícito absurdamente alto vs el operable → no se emite número.
    if ratio > politica.MULT_REVENUE_IMPLICITO_MAX:
        return Falsador(None, revenue_bull_operable, False, round(ratio, 1),
                        f"no_evaluable: revenue implícito {ratio:.0f}× el operable → implausible")
    ya = rimp >= revenue_bull_operable
    veredicto = ("el precio YA paga el bull operable → sin upside de evidencia dura: pura opcionalidad "
                 "(option ledger / carril especulativo, doc 29), fuera del libro duro"
                 if ya else "el precio deja aire sobre el bull operable")
    return Falsador(rimp, revenue_bull_operable, ya, round(ratio, 3), veredicto)
