"""Carteras sombra (v2 Fase 5, doc 51/52 Capa E + doc 59 §6) — la vara para saber si el comité AGREGA.

Desde el día 1 se registran, en cada ciclo, varias carteras contrafácticas point-in-time y se comparan sus
curvas de equity contra la del PM. Baselines DETERMINISTAS (sin LLM; solo precios):
- `pm` — las posiciones reales del paper (valor del sizing del PM).
- `ew_pass` — equal-weight de los nombres PASS del ciclo (valor de la SELECCIÓN, sin el sizing).
- ETFs temáticos (`etf_smh/ura/ita/copx`) + índice amplio (`spy`) — ¿el picking le gana al tema y al mercado?
(La cartera "Opus+web solo" y la contrafáctica "PM+veto-auditor" se agregan cuando se cablee el runner; son
hooks, no están acá.)

Mecánica: cada ciclo se guarda un `SnapshotSombra` (fecha, cartera, pesos, precios). La curva encadena el
retorno PONDERADO entre snapshots consecutivos (los pesos del snapshot previo, repreciados prev→actual); la
caja (1−Σpesos) rinde 0. Append-only en JSONL. doc 59: no esperar nada significativo antes de 12-18 meses.
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

_SOMBRAS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "carteras_sombra_v2.jsonl"

# ETFs temáticos (industrias del futuro) + índice amplio, para comparar el picking (doc 59 §6c).
ETFS_DEFAULT = {"etf_smh": "SMH", "etf_ura": "URA", "etf_ita": "ITA", "etf_copx": "COPX", "spy": "SPY"}


class SnapshotSombra(BaseModel):
    fecha: str                                   # YYYY-MM-DD (ciclo)
    cartera: str                                 # pm | ew_pass | etf_smh | spy | ...
    pesos: dict[str, float] = Field(default_factory=dict)      # ticker → fracción (0-1); resto = caja
    precios: dict[str, float] = Field(default_factory=dict)    # ticker → precio en la fecha


def pesos_equal_weight(nombres: list[str]) -> dict[str, float]:
    n = len([t for t in nombres if t])
    return {t.upper(): 1.0 / n for t in nombres if t} if n else {}


class LedgerSombras:
    """Registro append-only de snapshots de carteras sombra. Inyectá `path` para tests."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path or _SOMBRAS_PATH)

    def registrar(self, snap: SnapshotSombra) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(snap.model_dump_json() + "\n")

    def registrar_ciclo(self, fecha: str, *, pm_pesos: dict[str, float], pass_nombres: list[str],
                        precios: dict[str, float], etfs: dict[str, str] | None = None) -> None:
        """Registra en un ciclo las carteras estándar: `pm`, `ew_pass` y los ETFs/índice.
        `precios` debe cubrir los tickers de pm/pass + los símbolos de los ETFs."""
        etfs = etfs if etfs is not None else ETFS_DEFAULT
        self.registrar(SnapshotSombra(fecha=fecha, cartera="pm", pesos=pm_pesos,
                                      precios={t: precios[t] for t in pm_pesos if t in precios}))
        ew = pesos_equal_weight(pass_nombres)
        self.registrar(SnapshotSombra(fecha=fecha, cartera="ew_pass", pesos=ew,
                                      precios={t: precios[t] for t in ew if t in precios}))
        for nombre, sym in etfs.items():
            if sym in precios:
                self.registrar(SnapshotSombra(fecha=fecha, cartera=nombre, pesos={sym: 1.0},
                                              precios={sym: precios[sym]}))

    def _snapshots(self, cartera: str) -> list[SnapshotSombra]:
        if not self.path.exists():
            return []
        snaps = [SnapshotSombra.model_validate_json(l) for l in self.path.read_text(
            encoding="utf-8").splitlines() if l.strip()]
        return sorted((s for s in snaps if s.cartera == cartera), key=lambda s: s.fecha)

    def curva(self, cartera: str) -> list[tuple[str, float]]:
        """Curva de equity (base 1.0 en el primer snapshot) encadenando el retorno ponderado prev→actual."""
        snaps = self._snapshots(cartera)
        if not snaps:
            return []
        curva = [(snaps[0].fecha, 1.0)]
        idx = 1.0
        for prev, cur in zip(snaps, snaps[1:]):
            ret = 0.0
            for t, w in prev.pesos.items():
                p0, p1 = prev.precios.get(t), cur.precios.get(t)
                if p0 and p1:
                    ret += w * (p1 / p0 - 1.0)       # la caja (1−Σw) rinde 0
            idx *= (1.0 + ret)
            curva.append((cur.fecha, round(idx, 6)))
        return curva

    def carteras(self) -> list[str]:
        if not self.path.exists():
            return []
        return sorted({SnapshotSombra.model_validate_json(l).cartera
                       for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()})

    def resumen(self) -> dict[str, float]:
        """cartera → índice de equity más reciente (1.0 = sin cambio desde el inicio)."""
        return {c: (self.curva(c)[-1][1] if self.curva(c) else 1.0) for c in self.carteras()}
