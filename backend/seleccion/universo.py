"""Universo vivo del núcleo nuevo — tickers sobre los que opera el paper.

Reubicado desde `backend/nucleo/shadow.py` (que era andamiaje de comparación viejo-vs-nuevo y arrastraba
`backend.agents.portfolio`). Los jobs del paper solo necesitaban esta query a Ficha, no el shadow completo.
"""
from __future__ import annotations

from backend.database import session_scope
from backend.models import EstadoFicha, Ficha

# Estados de fichas que cuentan como "vivas" para el ciclo del paper.
ESTADOS_VIVOS = [
    EstadoFicha.PORTFOLIO_ACTIVO.value,
    EstadoFicha.WL_PRIORITARIA.value,
    EstadoFicha.WL_ACTIVA.value,
    EstadoFicha.WL_SEGUIMIENTO.value,
    EstadoFicha.BUCKET_EXPLORATORIO.value,
    EstadoFicha.CANDIDATA.value,
]


def tickers_vivos() -> list[str]:
    with session_scope() as s:
        return [f.ticker for f in s.query(Ficha).filter(Ficha.estado.in_(ESTADOS_VIVOS)).all()]
