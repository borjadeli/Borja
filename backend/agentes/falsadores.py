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


# una métrica es NUMÉRICA-verificable solo si su `fuente` apunta a un tag XBRL (no un nombre inventado como
# "revenue_2027" o "aurora_online", que nadie puede chequear por máquina).
def _es_numerico(f: Falsador) -> bool:
    fuente = (f.fuente or "").lower()
    tiene_tag = "xbrl" in fuente or ":" in fuente or fuente.startswith("tag")
    return f.operador in _OPS and f.umbral is not None and bool(f.metrica) and tiene_tag


def es_verificable(f: Falsador) -> bool:
    """¿Se puede chequear por máquina? SOLO numérico con tag XBRL (operador+umbral+métrica+fuente=tag). Un hito
    textual ('aurora_online') NO es verificable por máquina → no puede ser DURO (el Verificador lo rechaza)."""
    return _es_numerico(f)


def evaluar(f: Falsador, *, valor: float | None = None, hoy: date | None = None,
            evidencia_ambigua: bool = False, cumplido: bool | None = None) -> str:
    """Estado (OK/SUSPECTED/CONFIRMED). r10: NUNCA CONFIRMED por ausencia de dato.
    - numérico con tag XBRL: necesita `valor`; si cruza el umbral → CONFIRMED; si no → OK; sin valor → SUSPECTED
      (pide el dato, no vende). Si además tiene fecha y venció sin cruzar el umbral → EXPIRED (renovar, no vender).
    - hito/textual: solo CONFIRMED con evidencia explícita de que NO se cumplió (`cumplido=False`); ambiguo o sin
      resolver → SUSPECTED (despierta al PM). Vencer la fecha SIN evidencia NO confirma."""
    hoy = hoy or date.today()
    if evidencia_ambigua:
        return "SUSPECTED"
    vencido = bool(f.fecha_limite and hoy.isoformat() > f.fecha_limite)
    if _es_numerico(f):
        if valor is None:
            return "SUSPECTED"                         # falta el dato → pide, no vende (nunca CONFIRMED por ausencia)
        if _OPS[f.operador](float(valor), f.umbral):
            return "CONFIRMED"
        return "EXPIRED" if vencido else "OK"          # ventana vencida sin cruzar → renovar, no vender
    # hito/textual: CONFIRMED solo con evidencia explícita de incumplimiento
    if cumplido is False:
        return "CONFIRMED"
    if vencido and cumplido is None:
        return "SUSPECTED"                             # venció pero no se puede resolver → al PM, no auto-venta
    return "OK"


def confirmados_para_salida(fichas: dict, *, valor_fn=None, hoy: date | None = None) -> dict[str, list[dict]]:
    """Evalúa los falsadores DUROS de cada ficha → {ticker: [{id,tipo,consecuencia,estado}]} que consume
    `reglas_salida` (tier B → DESPERTAR al PM). `valor_fn(ticker, metrica)` → valor actual (o None). r10: un DURO
    CONFIRMED o SUSPECTED despierta al PM; NUNCA auto-vende (eso lo decide el PM + Auditor)."""
    hoy = hoy or date.today()
    out: dict[str, list[dict]] = {}
    for tk, f in (fichas or {}).items():
        for raw in (getattr(f, "falsadores", None) or []):
            fal = raw if isinstance(raw, Falsador) else _desde_dict(raw)
            if fal is None or fal.tipo != "DURO":
                continue
            valor = valor_fn(tk, fal.metrica) if valor_fn else None
            estado = evaluar(fal, valor=valor, hoy=hoy)
            if estado in ("CONFIRMED", "SUSPECTED"):
                out.setdefault(tk.upper(), []).append(
                    {"id": fal.id, "tipo": "DURO", "consecuencia": fal.consecuencia, "estado": estado})
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
