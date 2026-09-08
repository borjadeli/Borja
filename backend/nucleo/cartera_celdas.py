"""Construcción de cartera por CELDAS (doc 34 §3bis) — el paso de sizing tras el ranking por celda.

Toma el ranking por celda (arquetipo × tier) y arma la cartera **llenando cada celda con el tope de su
ranking local**, respetando: cuota EX-ANTE por arquetipo (cap agregado, decidido a nivel política) ·
cap por posición (`CandidatoLex.cap` = min de caps) · piso por posición · máx posiciones · techo de
despliegue. **Caps, NO cuotas obligatorias:** si no hay más elegibles, el resto queda en CASH — no se
fuerza (disciplina sobre actividad). Determinista y auditable.

SHADOW: es la superficie nueva; NO reemplaza al `flujo.armar_cartera`/`selector` vivo (cutover posterior).
El trade-off cross-arquetipo NO se resuelve por nombre acá: lo fijó la política (`CUOTA_ARQUETIPO`).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.nucleo import politica
from backend.nucleo.constantes import MAX_POSICIONES, TOPE_INVERTIDO
from backend.nucleo.ranking_lexicografico import CandidatoLex, cola_operativa


@dataclass
class Posicion:
    ticker: str
    arquetipo: str
    tier: str
    size: float                 # peso asignado, dentro de [piso, cap]
    cap: float                  # el techo (min de caps) — el PM propone dentro de [piso, cap]
    celda: tuple[str, str]      # (arquetipo, tier)


@dataclass
class Cartera:
    posiciones: list[Posicion] = field(default_factory=list)
    invertido: float = 0.0
    cash: float = 1.0
    saltados: list[dict] = field(default_factory=list)   # trazabilidad de por qué un elegible NO entró
    politica_version: str = ""
    politica_hash: str = ""


def construir_cartera(por_celda: dict[tuple[str, str], list[CandidatoLex]], *,
                      presupuesto: float = TOPE_INVERTIDO, max_posiciones: int = MAX_POSICIONES,
                      piso: float | None = None, juicio: dict[str, str] | None = None) -> Cartera:
    """Llena las celdas por la COLA OPERATIVA (tier A→B→C, round-robin), cada nombre a `min(cap, disponible
    por cuota de arquetipo, disponible total)`. No fuerza: si el size no alcanza la posición mínima viable,
    no entra (queda cash). El piso es `MIN_VIABLE` (§3ter).

    `juicio` (opcional, doc 39 §2.6, Bloque 3): {ticker: etiqueta} del canal de juicio (PM-LLM → allocator).
    Capa DESACOPLADA de la banda plena (que espera la triangulación del add-on): solo las 2 direcciones seguras —
    **VETO/THESIS_BROKEN → 0** (el juicio saca lo malo) y **ADMIT_PROBE → rescata un falso-negativo** (le da al
    menos el piso a un nombre que el determinista habría salteado por cap<piso). PRIORITY/PASS/HOLD NO mueven el
    size acá (el push dentro de la banda es parte del add-on, a triangular). NUNCA supera el cap de supervivencia."""
    if piso is None:
        piso = politica.MIN_VIABLE
    juicio = juicio or {}
    sello = politica.sello()
    cart = Cartera(cash=presupuesto, politica_version=sello["politica_version"],
                   politica_hash=sello["politica_hash"])
    usado_arq: dict[str, float] = {}
    for c in cola_operativa(por_celda):
        etq = juicio.get(c.ticker)
        if etq in ("VETO", "THESIS_BROKEN"):                 # el juicio saca lo malo (siempre permitido)
            cart.saltados.append({"ticker": c.ticker, "motivo": f"juicio {etq} → 0"})
            continue
        if len(cart.posiciones) >= max_posiciones:
            cart.saltados.append({"ticker": c.ticker, "motivo": "max_posiciones"})
            continue
        disp_arq = politica.cuota_arquetipo(c.arquetipo) - usado_arq.get(c.arquetipo, 0.0)
        disp_total = presupuesto - cart.invertido
        cap = c.cap if c.cap is not None else piso
        size = min(cap, disp_arq, disp_total)
        # ADMIT_PROBE: rescate de falso-negativo — si el determinista lo saltearía (size<piso) pero hay espacio,
        # le da el piso (probe chico). NUNCA supera el cap de supervivencia ni el disponible.
        rescatado = False
        if size < piso and etq == "ADMIT_PROBE" and min(disp_arq, disp_total) >= piso:
            size, rescatado = piso, True
        if size < piso:            # no alcanza el piso y no fue rescatado → no se fuerza
            cart.saltados.append({"ticker": c.ticker, "motivo": "sin espacio (cuota arquetipo/total) para el piso"})
            continue
        cart.posiciones.append(Posicion(c.ticker, c.arquetipo, c.tier_capital, round(size, 4), cap,
                                        (c.arquetipo, c.tier_capital)))
        if rescatado:
            cart.saltados.append({"ticker": c.ticker, "motivo": "ADMIT_PROBE: rescatado a piso (falso-negativo)"})
        usado_arq[c.arquetipo] = usado_arq.get(c.arquetipo, 0.0) + size
        cart.invertido += size
    cart.invertido = round(cart.invertido, 4)
    cart.cash = round(presupuesto - cart.invertido, 4)
    return cart
