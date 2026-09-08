"""Extrae la DEMANDA citada (3 hechos) + el tipo de contrato del backlog (E1) → fact store (nx_fact).

Por ticker: los 3 hechos de demanda (`extraer_demanda`) + `backlog_no_cancelable` (`extraer_e1`, doc 14
§E1) para que `/hoja` use el tipo de contrato REAL del RPO en vez del `cancelable ASUMIDO` conservador.
UNA transacción CORTA por ticker (no una larga que traba el scheduler / el logging de costo LLM).
Cacheado por filing (guards independientes): si el 10-Q no cambió, no re-gasta LLM. Único costo LLM
recurrente de la hoja (~$0.20 el universo la 1ª vez, ~$0 después). Correr offline (scheduler quieto):
    .venv/bin/python -m ops.extraer_demanda            # universo completo
    .venv/bin/python -m ops.extraer_demanda AAOI TENB  # subconjunto
"""
from __future__ import annotations

import sys
import time

from backend.database import session_scope
from backend.nucleo import analisis
from ops.generar_hoja import UNIVERSO

REINTENTOS = 3            # fallos TRANSITORIOS (lock de DB por el scheduler, JSON intermitente del LLM)


def _una(t: str) -> tuple[bool | None, Exception | None]:
    """Extrae un ticker con reintentos ante transitorios. El cache-guard adentro hace que un reintento
    NO re-gaste lo ya persistido → self-healing barato contra la contención con el scheduler."""
    ult: Exception | None = None
    for i in range(REINTENTOS):
        try:
            with session_scope() as s:                 # transacción CORTA por ticker → lock breve
                analisis.extraer_demanda(s, t)         # 3 hechos de demanda (guard propio)
                snap = analisis.extraer_e1(s, t)        # E1: tipo de contrato del backlog (guard propio, doc 14 §E1)
                return snap.get("cliente_nombrado") is not None, None
        except Exception as e:                          # lock / red / JSON intermitente → backoff y reintentar
            ult = e
            time.sleep(4 * (i + 1))
    return None, ult


def extraer(tickers: list[str]) -> None:
    ok = 0
    for t in tickers:
        tiene, err = _una(t)
        if err is not None:
            print(f"  {t:<6} ERROR {type(err).__name__}: {err}", flush=True)
        else:
            ok += 1 if tiene else 0
            print(f"  {t:<6} {'✓ con evidencia' if tiene else 's/d'}", flush=True)
    print(f"\ndemanda citada: {ok}/{len(tickers)} con evidencia")


def main() -> None:
    tickers = [a.upper() for a in sys.argv[1:]] or UNIVERSO
    extraer(tickers)


if __name__ == "__main__":
    main()
