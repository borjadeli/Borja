"""Falsadores estructurados (doc 85 F2/§6) — la pieza clave de las salidas crujientes.

Cada falsador es un OBJETO, no una frase: {métrica, fuente, operador, umbral, fecha_límite, tipo DURO|BLANDO,
consecuencia SALIDA|RECORTE_50|REVISION, línea_base}. La consecuencia se PRE-COMPROMETE al escribir la tesis (en
frío) y no se negocia cuando la posición pierde. El evaluador es DETERMINISTA:
- numérico → compara el valor (del XBRL del filing nuevo) con el umbral, $0;
- hito con fecha → si venció sin cumplirse → CONFIRMED (corta la plata muerta: el catalizador que nunca llega);
- evidencia AMBIGUA (textual, p.ej. going concern dudoso) → SUSPECTED, no CONFIRMED (un error de extracción no
  puede volverse una orden de liquidación).
El Verificador RECHAZA la ficha si un falsador DURO no es verificable por máquina (`es_verificable`).
"""
from __future__ import annotations

import operator
from dataclasses import asdict, dataclass
from datetime import date

_OPS = {"<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge,
        "==": operator.eq, "!=": operator.ne}
TIPOS = ("DURO", "BLANDO")
CONSECUENCIAS = ("SALIDA", "RECORTE_50", "REVISION")
ESTADOS = ("OK", "SUSPECTED", "CONFIRMED")


@dataclass
class Falsador:
    id: str
    metrica: str                      # p.ej. "revenue_2027" | "aurora_online" | "going_concern"
    fuente: str = "evento"            # xbrl_tag | campo | tipo_evento
    operador: str | None = None       # < <= > >= == !=  (None = hito/evento sin comparación numérica)
    umbral: float | None = None
    fecha_limite: str | None = None   # YYYY-MM-DD (hito que debe cumplirse antes de esta fecha)
    tipo: str = "BLANDO"              # DURO | BLANDO
    consecuencia: str = "REVISION"    # SALIDA | RECORTE_50 | REVISION
    linea_base: str | None = None     # bandera que YA estaba al deep (going concern/material weakness) → no dispara
    estado: str = "OK"

    def to_dict(self) -> dict:
        return asdict(self)


def es_verificable(f: Falsador) -> bool:
    """¿Se puede chequear por máquina? Numérico (operador+umbral+métrica) o hito con fecha_limite. El Verificador
    rechaza una ficha con un falsador DURO que NO sea verificable (doc 85: 'toda ficha ≥1 DURO verificable')."""
    if f.operador in _OPS and f.umbral is not None and f.metrica:
        return True
    return bool(f.fecha_limite and f.metrica)


def evaluar(f: Falsador, *, valor: float | None = None, hoy: date | None = None,
            evidencia_ambigua: bool = False, cumplido: bool | None = None) -> str:
    """Devuelve el estado (OK/SUSPECTED/CONFIRMED). `valor` = métrica del filing nuevo (numérico). `cumplido` =
    para hitos: ¿el hito ya se cumplió? (True → OK aunque venza). `evidencia_ambigua` → SUSPECTED (textual dudoso)."""
    hoy = hoy or date.today()
    if evidencia_ambigua:
        return "SUSPECTED"
    # numérico: si la condición de KILL se cumple → CONFIRMED
    op = _OPS.get(f.operador or "")
    if valor is not None and op is not None and f.umbral is not None:
        return "CONFIRMED" if op(valor, f.umbral) else "OK"
    # hito con fecha: venció sin cumplirse → CONFIRMED (plata muerta)
    if f.fecha_limite and hoy.isoformat() > f.fecha_limite and not cumplido:
        return "CONFIRMED"
    return "OK"


def confirmados_para_salida(fichas: dict, *, valor_fn=None, hoy: date | None = None) -> dict[str, list[dict]]:
    """Evalúa los falsadores DUROS de cada ficha → el dict {ticker: [{id,tipo,consecuencia}]} que consume
    `reglas_salida.evaluar_reglas_salida` (tier B). `valor_fn(ticker, metrica)` → valor actual (o None).
    Solo DURO CONFIRMED dispara una regla; BLANDO/SUSPECTED van a juicio del PM, no a regla."""
    hoy = hoy or date.today()
    out: dict[str, list[dict]] = {}
    for tk, f in (fichas or {}).items():
        for raw in (getattr(f, "falsadores", None) or []):
            fal = raw if isinstance(raw, Falsador) else _desde_dict(raw)
            if fal is None or fal.tipo != "DURO":
                continue
            valor = valor_fn(tk, fal.metrica) if valor_fn else None
            if evaluar(fal, valor=valor, hoy=hoy) == "CONFIRMED":
                out.setdefault(tk.upper(), []).append(
                    {"id": fal.id, "tipo": "DURO", "consecuencia": fal.consecuencia})
    return out


def _desde_dict(d: dict) -> Falsador | None:
    """Tolera el falsador LEGACY (texto libre: {afirmacion, fecha_limite, estado}) → Falsador BLANDO no numérico."""
    try:
        if "metrica" in d:
            return Falsador(**{k: d.get(k) for k in Falsador.__dataclass_fields__ if k in d})
        # legacy: sin estructura → BLANDO con solo fecha (no verificable por máquina)
        return Falsador(id=(d.get("afirmacion") or "legacy")[:40], metrica=(d.get("afirmacion") or "")[:60],
                        fecha_limite=d.get("fecha_limite"), tipo="BLANDO")
    except Exception:  # noqa: BLE001
        return None
