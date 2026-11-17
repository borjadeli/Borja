"""Input del operador (doc 85 F2/§5) — pasar tickers a la cola de investigación.

    .venv/bin/python -m ops.solicitar research OKLO   # deep en el próximo cupo (P1, carril operador)
    .venv/bin/python -m ops.solicitar watch RXRX      # a observación (P2)
    .venv/bin/python -m ops.solicitar review MP        # reconsiderar una tesis existente (P1)

El ticker del operador SALTA la selección del discovery, NO sus filtros: va por el MISMO comité + verificador
ciego cuando se drena la cola, y para COMPRARLO tiene que pasar liquidez + IPS (el gate). Fuera del mapa se
analiza igual. $0 (solo encola; el deep lo corre el drenaje de la cola).
"""
from __future__ import annotations

import sys

from backend.agentes.research_queue import ResearchQueue

_COMANDOS = {
    "research": ("P1", "deep en el próximo cupo"),
    "watch": ("P2", "observación + scoring"),
    "review": ("P1", "reconsiderar tesis existente"),
}


def main() -> int:
    args = sys.argv[1:]
    if len(args) < 2 or args[0].lower() not in _COMANDOS:
        print("uso: ops.solicitar {research|watch|review} TICKER [motivo...]")
        return 1
    cmd = args[0].lower()
    ticker = args[1].upper()
    motivo = " ".join(args[2:]) if len(args) > 2 else ""
    prioridad, desc = _COMANDOS[cmd]
    q = ResearchQueue()
    req = q.encolar(ticker, origen="OPERADOR", prioridad=prioridad, motivo=motivo or desc)
    print(f"{cmd.upper()} {ticker} → cola (id {req.id}, {prioridad}, origen {req.origen}). "
          f"Se analiza en el próximo drenaje; para COMPRARLO tiene que pasar liquidez + IPS.")
    print(f"pendientes: {[(r.ticker, r.prioridad) for r in q.pendientes()]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
