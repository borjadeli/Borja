"""Selector determinista — Núcleo consolidado v3, §2, §9; Bloque C §0.

El Selector del núcleo SOLO ordena por mérito (determinista). El "selector que
elige por sector/momentum/pala" es el Portfolio Manager (Bloque C, Fase 3) — son
dos piezas distintas y acá NO se mezcla momentum ni sesgo sectorial.

mérito = Quality(tier) × Asimetría. La normalización (decisión del operador
2026-06-24) es RANKING RELATIVO top-N: el capital bruto que pide cada candidata
es su proporción del mérito sobre la suma de méritos de las top-N. El mejor del
universo pide más; el Hard Cap y el piso de 5% (sizing.sizing_final) recortan
después, y lo que sobra queda en cash. El 70% es PISO, no techo: se despliega
hasta el techo 100% guiado por mérito (ver paper_trader / armar_cartera).
"""
from __future__ import annotations

from backend.nucleo.constantes import MAX_POSICIONES


def rankear_por_merito(candidatas: list[dict]) -> list[dict]:
    """Ordena candidatas por mérito descendente. candidatas: lista de dicts con
    al menos {ticker, merito}. mérito None (asimetría no calculable) va al final.
    Determinista y estable (desempata por ticker)."""
    def clave(c: dict):
        m = c.get("merito")
        return (m is None, -(m or 0.0), c.get("ticker", ""))
    return sorted(candidatas, key=clave)


def normalizar_merito(candidatas: list[dict], n: int = MAX_POSICIONES,
                      target: float = 1.0) -> list[dict]:
    """Normalización ranking relativo top-N (§9).

    Toma las top-N por mérito (mérito > 0) y reparte `target` (capital bruto total,
    fracción de cartera; 1.0 = 100% bruto antes de caps) proporcional al mérito.
    Devuelve la lista rankeada; cada dict gana 'bruto' (% pedido) y 'en_top_n'.
    Las que quedan fuera del top-N o con mérito None/≤0 reciben bruto 0.

    El bruto es el "capital bruto que pide el mérito"; sizing.sizing_final lo
    recorta a [5%, Hard Cap]. El cash residual emerge de los caps; no se fuerza el
    despliegue (el 70% es piso, el techo es 100% — `target` lo fija quien llama).
    """
    rankeadas = rankear_por_merito(candidatas)
    elegibles = [c for c in rankeadas if (c.get("merito") or 0.0) > 0.0][:n]
    suma = sum((c["merito"] for c in elegibles), 0.0)

    ids_top = {id(c) for c in elegibles}
    for c in rankeadas:
        if id(c) in ids_top and suma > 0:
            c["bruto"] = target * (c["merito"] / suma)
            c["en_top_n"] = True
        else:
            c["bruto"] = 0.0
            c["en_top_n"] = False
    return rankeadas
