"""IPS — validador determinista de límites duros (v2 Fase 4, doc 55 §4).

El único lugar donde el código impone límites, con **inputs mecánicos solo** (pesos, market cap, ADV,
clasificación de fuente fija — nunca un juicio de LLM). `validar()` devuelve las violaciones con su holgura
y su TIPO:
- `local_simple`  (un nombre sobre su cap) → el orquestador recorta a cash + registra "PM+clip".
- `agregada`      (sector/cuello/liquidez/caja/ops) → el código NO elige qué recortar → NO_ACTION hasta una
  propuesta válida (doc 55 §4.1).
Se usa como **dry-run tool** del PM (devuelve holguras exactas) y como **gate final** sobre el estado
actualizado de la cartera. Versión + hash para el ledger.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

_IPS_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "ips.yaml"


@dataclass
class ContextoTicker:
    """Datos MECÁNICOS por ticker (de market data + nx_nodo / tabla fija). Nunca de un LLM."""
    sector: str | None = None
    cuello: str | None = None
    market_cap: float | None = None
    adv_usd: float | None = None


@dataclass
class Violacion:
    regla: str
    detalle: str
    holgura: float           # negativo = viola (cuánto excede); informativo para el dry-run
    tipo: str                # "local_simple" | "agregada"


class IPS:
    def __init__(self, cfg: dict):
        self.cfg = cfg

    @classmethod
    def cargar(cls, path: Path | str | None = None) -> "IPS":
        return cls(yaml.safe_load(Path(path or _IPS_PATH).read_text()))

    def hash(self) -> str:
        return hashlib.sha256(json.dumps(self.cfg, sort_keys=True).encode()).hexdigest()[:16]

    def _g(self, k: str, default=None):
        return self.cfg.get(k, default)

    def validar(self, pesos: dict[str, float], contexto: dict[str, ContextoTicker], *,
                caja: float, ops_semana: int = 0,
                flags_no_resueltos: set[str] | None = None,
                turnover: float | None = None) -> list[Violacion]:
        """`pesos` = cartera RESULTANTE (fracción por ticker, suma + caja ≈ 1). Devuelve violaciones."""
        flags_no_resueltos = {t.upper() for t in (flags_no_resueltos or set())}
        v: list[Violacion] = []
        tenencias = {t.upper(): w for t, w in pesos.items() if w > 0}

        # --- local_simple: peso por nombre (cap base, o cap de flag de supervivencia) ---
        peso_max = float(self._g("peso_max_nombre", 1.0))
        cap_flag = float(self._g("cap_flag_supervivencia", peso_max))
        for tk, w in tenencias.items():
            tope = min(peso_max, cap_flag) if tk in flags_no_resueltos else peso_max
            if w > tope + 1e-9:
                v.append(Violacion("peso_max_nombre", f"{tk}: {w:.1%} > {tope:.1%}"
                                   + (" (flag supervivencia)" if tk in flags_no_resueltos else ""),
                                   holgura=round(tope - w, 6), tipo="local_simple"))

        # --- local_simple: admisibilidad por nombre (market cap, liquidez) ---
        mc_min, mc_max = float(self._g("market_cap_min_usd", 0)), float(self._g("market_cap_max_usd", 1e18))
        adv_min = float(self._g("adv_min_usd", 0))
        for tk in tenencias:
            ctx = contexto.get(tk)
            if ctx is None:
                continue
            if ctx.market_cap is not None and not (mc_min <= ctx.market_cap <= mc_max):
                v.append(Violacion("market_cap_rango", f"{tk}: ${ctx.market_cap/1e9:.2f}B fuera de rango",
                                   holgura=0.0, tipo="local_simple"))
            if ctx.adv_usd is not None and ctx.adv_usd < adv_min:
                v.append(Violacion("adv_min", f"{tk}: ADV ${ctx.adv_usd/1e6:.1f}M < ${adv_min/1e6:.0f}M",
                                   holgura=round(ctx.adv_usd - adv_min, 2), tipo="local_simple"))

        # --- agregada: número de posiciones ---
        max_pos = int(self._g("max_posiciones", 999))
        if len(tenencias) > max_pos:
            v.append(Violacion("max_posiciones", f"{len(tenencias)} > {max_pos}",
                               holgura=max_pos - len(tenencias), tipo="agregada"))

        # --- agregada: concentración por sector y por cuello (clasificación de fuente fija) ---
        for eje, regla, topekey in (("sector", "max_por_sector", "max_por_sector"),
                                    ("cuello", "max_por_cuello", "max_por_cuello")):
            tope = float(self._g(topekey, 1.0))
            acc: dict[str, float] = {}
            for tk, w in tenencias.items():
                ctx = contexto.get(tk)
                clave = getattr(ctx, eje, None) if ctx else None
                if clave:
                    acc[clave] = acc.get(clave, 0.0) + w
            for clave, suma in acc.items():
                if suma > tope + 1e-9:
                    v.append(Violacion(regla, f"{eje}={clave}: {suma:.1%} > {tope:.1%}",
                                       holgura=round(tope - suma, 6), tipo="agregada"))

        # --- agregada: caja, operaciones, turnover ---
        caja_min, caja_max = float(self._g("caja_min", 0.0)), float(self._g("caja_max", 1.0))
        if caja < caja_min - 1e-9 or caja > caja_max + 1e-9:
            v.append(Violacion("caja", f"caja {caja:.1%} fuera de [{caja_min:.0%}, {caja_max:.0%}]",
                               holgura=0.0, tipo="agregada"))
        max_ops = int(self._g("max_ops_semana", 999))
        if ops_semana > max_ops:
            v.append(Violacion("max_ops_semana", f"{ops_semana} > {max_ops}",
                               holgura=max_ops - ops_semana, tipo="agregada"))
        if turnover is not None:
            tmax = float(self._g("turnover_max_semana", 1.0))
            if turnover > tmax + 1e-9:
                v.append(Violacion("turnover_max_semana", f"{turnover:.1%} > {tmax:.1%}",
                                   holgura=round(tmax - turnover, 6), tipo="agregada"))
        return v

    @staticmethod
    def admisible(violaciones: list[Violacion]) -> bool:
        return len(violaciones) == 0

    @staticmethod
    def hay_agregada(violaciones: list[Violacion]) -> bool:
        """True si hay alguna violación agregada → NO_ACTION (el código no elige qué recortar)."""
        return any(x.tipo == "agregada" for x in violaciones)
