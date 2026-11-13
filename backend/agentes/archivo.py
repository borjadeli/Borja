"""Archivo inteligente / lápida (r9, doc 80 §J · P3) — archivar NO es olvidar.

Cada empresa que sale del universo deja una LÁPIDA: por qué salió (motivo), su HUELLA de fundamentals al salir,
y la condición de REINGRESO (que depende del motivo). Así:
- una EXCELENTE que se puso cara y se abarata → vuelve por PRECIO (gatillo congelado), si la tesis sigue válida;
- una descartada por TESIS ROTA / CALIDAD → NO se re-propone mientras la huella no cambie (ahorra budget);
- una sacada por ROTACIÓN de universo → vuelve si su SCORE entra al cuartil superior.

Identidad por SECURITY (ticker acá; en producción CIK+instrumento). Puro y determinista (testeable)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

# motivo de salida → cómo puede volver (doc 80 §J)
_REINGRESO_POR_MOTIVO = {
    "VALUACION": "PRECIO",          # cara → gatillo congelado; si el precio cae, vuelve
    "REEMPLAZO": "PRECIO",          # salió por otra mejor con tesis intacta → gatillo congelado
    "ROTACION_UNIVERSO": "SCORE",   # salió por limpieza → vuelve si su score entra al cuartil superior
    "TESIS_ROTA": "FUNDAMENTAL",    # descartada → solo vuelve con evidencia de cambio (huella distinta)
    "CALIDAD": "FUNDAMENTAL",
    "FUERA_DE_IPS": "FUNDAMENTAL",  # market cap/elegibilidad → vuelve si cambia el fundamental que la sacó
    "CUELLO_RESUELTO": "NUNCA",     # el cuello se disolvió → no hay razón, salvo nueva evidencia manual
}
_PCT_CAMBIO_MATERIAL = 0.10        # >10% en ventas/acciones/RPO = "la huella cambió" (hay evidencia nueva)


@dataclass
class Lapida:
    ticker: str
    fecha_salida: str
    motivo: str
    huella: dict                    # {ventas_ttm, margen_bruto, acciones, rpo, ultimo_filing}
    reingreso_tipo: str             # PRECIO | FUNDAMENTAL | SCORE | NUNCA
    reingreso_condicion: float | None = None   # PRECIO: gatillo de compra congelado
    ficha_version_final: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def huella_de_metricas(metricas: dict) -> dict:
    """Foto de fundamentals para detectar luego si 'cambió algo'."""
    return {"ventas_ttm": metricas.get("revenue"), "margen_bruto": metricas.get("gross_profit"),
            "acciones": metricas.get("shares_outstanding"), "rpo": metricas.get("rpo"),
            "ultimo_filing": metricas.get("ultimo_filing")}


def archivar(ticker: str, *, motivo: str, metricas: dict, gatillo_compra: float | None = None,
             ficha_version: str | None = None, hoy: date | None = None) -> Lapida:
    """Arma la lápida. `gatillo_compra` = el precio de compra congelado de la ficha (para reingreso por PRECIO)."""
    motivo = motivo.upper()
    tipo = _REINGRESO_POR_MOTIVO.get(motivo, "FUNDAMENTAL")
    return Lapida(ticker=ticker.upper(), fecha_salida=(hoy or date.today()).isoformat(), motivo=motivo,
                  huella=huella_de_metricas(metricas), reingreso_tipo=tipo,
                  reingreso_condicion=(gatillo_compra if tipo == "PRECIO" else None),
                  ficha_version_final=ficha_version)


def _huella_cambio(vieja: dict, nueva: dict) -> bool:
    """True si algún fundamental clave cambió >10% (hay evidencia nueva que justifica re-mirar)."""
    for k in ("ventas_ttm", "acciones", "rpo"):
        v, n = vieja.get(k), (nueva or {}).get(k)
        if v and n and abs(n - v) / abs(v) > _PCT_CAMBIO_MATERIAL:
            return True
        if bool(v) != bool(n):                       # apareció/desapareció un dato (p.ej. RPO)
            return True
    return False


def evaluar_reingreso(lapida: Lapida, *, precio: float | None = None, metricas_actuales: dict | None = None,
                      score_percentil: float | None = None) -> tuple[bool, str]:
    """¿Vuelve al RADAR? Devuelve (reingresa, motivo). Determinista, pre-filtro ANTES del LLM de discovery."""
    tipo = lapida.reingreso_tipo
    if tipo == "NUNCA":
        return False, "cuello resuelto / no reingresa salvo evidencia manual"
    if tipo == "PRECIO":
        if precio is not None and lapida.reingreso_condicion is not None and precio <= lapida.reingreso_condicion:
            return True, f"precio {precio} ≤ gatillo congelado {lapida.reingreso_condicion} (se abarató)"
        return False, "aún por encima del gatillo de compra"
    if tipo == "FUNDAMENTAL":
        if metricas_actuales is not None and _huella_cambio(lapida.huella, huella_de_metricas(metricas_actuales)):
            return True, "la huella de fundamentals cambió (evidencia nueva)"
        return False, "misma huella que al salir → suprimido (no re-investigar)"
    if tipo == "SCORE":
        if score_percentil is not None and score_percentil >= 0.75:
            return True, f"score al cuartil superior ({score_percentil:.2f})"
        return False, "score fuera del cuartil superior"
    return False, "sin política de reingreso"


class StoreLapidas:
    _PATH = Path(__file__).resolve().parent.parent.parent / "data" / "lapidas_v2.json"

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else self._PATH
        self._l: dict[str, Lapida] = {}
        if self.path.exists():
            try:
                self._l = {tk.upper(): Lapida(**d) for tk, d in json.loads(self.path.read_text()).items()}
            except (OSError, json.JSONDecodeError, TypeError):
                self._l = {}

    def guardar(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({tk: l.to_dict() for tk, l in self._l.items()}, ensure_ascii=False,
                                        indent=2), encoding="utf-8")

    def set(self, lapida: Lapida) -> None:
        self._l[lapida.ticker.upper()] = lapida

    def get(self, ticker: str) -> Lapida | None:
        return self._l.get(ticker.upper())

    def todas(self) -> dict[str, Lapida]:
        return dict(self._l)
