"""Persistencia y orquestación de la ficha viva (r9, doc 80 §F · P0).

- `StoreFichas`: store JSON (como el cache de dossiers; son ~200-300 filas → no hace falta SQLite todavía).
- `backfill_fichas`: arma las fichas desde el cache de dossiers ($0). `datos_fn` inyectable (red en real, stub en test).
- `recalcular_todas`: el JOB DIARIO — recalcula el reloj rápido de cada ficha con el precio vivo y emite alertas
  de cambio de zona (COMPRA/RECORTE/SALIDA). 100% determinista, sin LLM.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Callable

from backend.agentes.ficha import Ficha, backfill_desde_dossier, evaluar_vigencia, recalcular

_FICHAS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "fichas_v2.json"


class StoreFichas:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else _FICHAS_PATH
        self._f: dict[str, Ficha] = {}
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self._f = {tk.upper(): Ficha.from_dict(d) for tk, d in data.items()}
            except (OSError, json.JSONDecodeError, TypeError):
                self._f = {}

    def guardar(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({tk: f.to_dict() for tk, f in self._f.items()},
                                        ensure_ascii=False, indent=2), encoding="utf-8")

    def set(self, ficha: Ficha) -> None:
        self._f[ficha.ticker.upper()] = ficha

    def get(self, ticker: str) -> Ficha | None:
        return self._f.get(ticker.upper())

    def todos(self) -> dict[str, Ficha]:
        return dict(self._f)


def backfill_fichas(cache_entries: dict, *, datos_fn: Callable[[str], dict | None],
                    store: StoreFichas | None = None, hoy: date | None = None, **pol) -> list[Ficha]:
    """Arma fichas desde el cache de dossiers (`{ticker: entry}` con `.dossier`/`.hash`). `datos_fn(ticker)` →
    {acciones, deuda_neta, precio, cuello, cobertura, conocido_hasta}. Un nombre sin acciones/escenarios se saltea."""
    fichas: list[Ficha] = []
    for tk, e in cache_entries.items():
        dossier = getattr(e, "dossier", None)
        if dossier is None:
            continue
        datos = datos_fn(tk) or {}
        if not datos.get("acciones"):
            continue
        f = backfill_desde_dossier(
            tk, dossier, deuda_neta=float(datos.get("deuda_neta") or 0.0), acciones=float(datos["acciones"]),
            precio=datos.get("precio"), cuello=datos.get("cuello"), cobertura=datos.get("cobertura", "FULL"),
            conocido_hasta=datos.get("conocido_hasta"), datos_conflicted=bool(datos.get("datos_conflicted")),
            caja=datos.get("caja"), dossier_id=getattr(e, "hash", None), hoy=hoy, **pol)
        if store is not None:
            store.set(f)
        fichas.append(f)
    if store is not None:
        store.guardar()
    return fichas


def recalcular_todas(store: StoreFichas, *, precios_fn: Callable[[str], float | None],
                     filings_fn: Callable[[str], str | None] | None = None, hoy: date | None = None,
                     **pol) -> list[dict]:
    """JOB DIARIO: recalcula el reloj rápido de cada ficha con el precio vivo + evalúa vigencia por evento.
    Devuelve las alertas de CAMBIO de zona a COMPRA/RECORTE/SALIDA (lo que el PM mira). Persiste al final."""
    hoy = hoy or date.today()
    alertas: list[dict] = []
    for tk, f in store.todos().items():
        if filings_fn is not None:
            nuevo = evaluar_vigencia(f, ultimo_filing=filings_fn(tk), hoy=hoy)
            if nuevo != f.estado:
                f.estado = nuevo
                f.historial.append({"fecha": hoy.isoformat(), "evento": "vigencia", "motivo_codigo": nuevo})
        precio = precios_fn(tk)
        if precio is None:
            continue
        zona_antes = f.latido.zona if f.latido else None
        recalcular(f, precio=precio, **pol)
        zona = f.latido.zona if f.latido else None
        if zona in ("COMPRA", "RECORTE", "SALIDA") and zona != zona_antes:
            alertas.append({"ticker": tk, "zona": zona, "precio": round(precio, 4), "zona_antes": zona_antes,
                            "estado": f.estado, "datos_conflicted": f.datos_conflicted,
                            # doc 80: solo compra con tesis VIGENTE y datos CONFIABLES (no acciones feed≠XBRL)
                            "comprable": zona == "COMPRA" and f.estado == "VIGENTE" and not f.datos_conflicted})
        store.set(f)
    store.guardar()
    return alertas


def comprable_por_ticker(fichas: dict) -> dict[str, bool]:
    """CANDADO (doc 85): ticker → ¿es comprable PLENO? = ficha VIGENTE en zona COMPRA con datos limpios. El gate
    lo consulta al momento de decidir (no confía en el packet). `fichas` = dict ticker→Ficha (del store)."""
    out: dict[str, bool] = {}
    for tk, f in (fichas or {}).items():
        zona = f.latido.zona if getattr(f, "latido", None) else None
        out[tk.upper()] = (zona == "COMPRA" and getattr(f, "estado", None) == "VIGENTE"
                           and not getattr(f, "datos_conflicted", False))
    return out


def admisible_duro_por_ticker(fichas: dict) -> dict[str, bool]:
    """CANDADO DURO (r10 / doc 80 §H): ticker → ¿ficha VIGENTE con datos limpios? (SIN exigir zona COMPRA). Es el
    requisito INEQUÍVOCO para abrir; la zona COMPRA es BLANDA (el PM puede entrar fuera de zona con peso chico +
    justificación + el Auditor revisa). Sin esto (ficha vencida / datos sucios / sin ficha) → NO se abre ni chico."""
    out: dict[str, bool] = {}
    for tk, f in (fichas or {}).items():
        out[tk.upper()] = (getattr(f, "estado", None) == "VIGENTE" and not getattr(f, "datos_conflicted", False))
    return out
