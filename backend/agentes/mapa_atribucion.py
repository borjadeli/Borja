"""Atribución empresa→cuello (doc 89 §8, pieza 2 del mapa MVP).

El tablero agrega XBRL por EMPRESA = economía del ECOSISTEMA, no del CUELLO. Este módulo aplica un peso de
PUREZA manual por vínculo (de `config/mapa_atribucion.yaml`) para quedarse con el revenue ATRIBUIBLE al cuello,
y reporta la COBERTURA (qué fracción del revenue tiene peso conocido). Lo no anotado = DESCONOCIDA: no suma al
atribuible y baja la cobertura. Nunca se presenta economía-de-ecosistema como economía-de-cuello (§8.1).

Determinista, $0 LLM. Desacoplado de la DB: el overlay es por `(cuello, ticker)` en texto.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

_ATRIB_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "mapa_atribucion.yaml"


@dataclass
class Exposicion:
    """La exposición estructurada de un vínculo empresa→cuello. `peso_pureza is None` = DESCONOCIDA."""
    cuello: str
    ticker: str
    peso_pureza: float | None = None
    rol: str | None = None
    captura: str | None = None
    dependencia: str | None = None
    fuente: str | None = None

    @property
    def desconocida(self) -> bool:
        return self.peso_pureza is None


@dataclass
class Atribuible:
    """El revenue atribuible al cuello + el aviso de cobertura (doc 89 §8.1)."""
    cuello: str
    revenue_atribuible: float | None            # Σ revenue × peso_pureza (solo vínculos con peso conocido)
    revenue_total: float                        # Σ revenue crudo del cuello (ecosistema)
    cobertura: float | None                     # revenue con peso conocido / revenue total (None si total=0)
    n_conocidas: int
    n_total: int
    desconocidas: list[str] = field(default_factory=list)   # tickers sin peso → el aviso
    atribuible_por_empresa: dict[str, float] = field(default_factory=dict)   # {ticker: revenue×peso} (materialidad)


class MapaAtribucion:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else _ATRIB_PATH
        self._m: dict[str, dict[str, dict]] = {}
        if self.path.exists():
            try:
                self._m = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError):
                self._m = {}

    def get(self, cuello: str, ticker: str) -> Exposicion:
        """La exposición del vínculo. Ausente → DESCONOCIDA (peso_pureza=None). Nunca inventa."""
        d = (self._m.get(cuello) or {}).get(ticker.upper()) or {}
        peso = d.get("peso_pureza")
        return Exposicion(cuello=cuello, ticker=ticker.upper(),
                          peso_pureza=(float(peso) if peso is not None else None),
                          rol=d.get("rol"), captura=d.get("captura"),
                          dependencia=d.get("dependencia"), fuente=d.get("fuente"))


def revenue_atribuible(cuello: str, empresas_revenue: dict[str, float],
                       atrib: MapaAtribucion | None = None) -> Atribuible:
    """Aplica los pesos de pureza al revenue por empresa del cuello. Las DESCONOCIDAS no suman al atribuible y
    bajan la cobertura (default honesto §8.1). Si NINGUNA empresa tiene peso conocido, `revenue_atribuible=None`
    (no hay base para medir economía-de-cuello) y `cobertura=0`."""
    atrib = atrib or MapaAtribucion()
    total = sum(v for v in empresas_revenue.values() if v)
    atribuible = 0.0
    rev_conocido = 0.0
    por_empresa: dict[str, float] = {}
    desconocidas: list[str] = []
    for tk, rev in empresas_revenue.items():
        if not rev:
            continue
        exp = atrib.get(cuello, tk)
        if exp.desconocida:
            desconocidas.append(tk.upper())
            continue
        val = rev * exp.peso_pureza
        por_empresa[tk.upper()] = round(val, 2)
        atribuible += val
        rev_conocido += rev
    return Atribuible(
        cuello=cuello,
        revenue_atribuible=(round(atribuible, 2) if por_empresa else None),
        revenue_total=round(total, 2),
        cobertura=(round(rev_conocido / total, 4) if total else None),
        n_conocidas=len(por_empresa), n_total=len([v for v in empresas_revenue.values() if v]),
        desconocidas=sorted(desconocidas), atribuible_por_empresa=por_empresa)
