"""Canal de JUICIO acotado (doc 39 §2.6, doc 40 Bloque 3) — el rebalanceo real: recuperar falsos negativos.

El determinismo produce **hard exclusions + bandas + techos, NO una cartera obligatoria**. El PM-LLM (aparte)
emite SOLO **etiquetas discretas**; este allocator DETERMINISTA las traduce a un tamaño DENTRO de la banda. El
LLM NUNCA emite un número. Invariantes DUROS (no negociables, doc 39):
  · el juicio se mueve dentro de [piso, techo]; **NUNCA supera el techo** (cap de supervivencia).
  · VETO / THESIS_BROKEN → 0 (siempre permitido, sin presupuesto).
  · las PROMOCIONES (subir tamaño / admitir probe) están PRESUPUESTADAS (N por ciclo) y van a un LEDGER con
    hit-rate; si el juicio no le gana al baseline, el presupuesto se achica solo (ledger_juicio, aparte).
  · toda promoción exige un FALSADOR ESCRITO + fecha antes de ejecutar (auditable ≠ reproducible).
Prohibido (NO se codifica acá porque no debe existir): pisar un veto de supervivencia, tocar un número de una
tabla, re-correr hasta que dé lindo, excepciones por nombre. El allocator solo mueve DENTRO de la banda.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.nucleo import politica

ETIQUETAS = ("ADMIT_PROBE", "PASS", "PRIORITY_HIGH", "PRIORITY_MEDIUM", "PRIORITY_LOW",
             "HOLD", "THESIS_BROKEN", "VETO")
PROMOCIONES = ("ADMIT_PROBE", "PRIORITY_HIGH", "PRIORITY_MEDIUM", "PRIORITY_LOW")  # consumen presupuesto


@dataclass
class Banda:
    """El rango de sizing que el determinista deja para el juicio (doc 39 §2.5, entrega 1.4). El juicio se mueve
    dentro; NUNCA supera `techo` (cap de supervivencia = min de caps). `base` = lo que el determinista asigna."""
    piso: float                    # mínimo viable (0 = fuera del libro duro / probe)
    base: float                    # asignación determinista (asimetría/valuación)
    techo: float                   # min(caps) — cap de supervivencia, INVIOLABLE

    def clamp(self, x: float) -> float:
        return max(0.0, min(x, self.techo))


@dataclass
class Intervencion:
    """Una intervención de juicio FECHADA y falsable (doc 39 §2.6). Va al ledger de hit-rate. `falsador` +
    `fecha_falsador` son OBLIGATORIOS para promociones (sin falsador escrito no hay promoción)."""
    ticker: str
    etiqueta: str
    fecha: str                     # ISO — se pasa desde afuera (no Date.now)
    falsador: str = ""             # qué la falsaría (obligatorio si es promoción)
    fecha_falsador: str = ""       # antes de qué fecha
    memo_hash: str = ""            # hash del memo estructurado (bull+bear independientes)
    size_base: float | None = None
    size_asignado: float | None = None
    motivo: str = ""


def asignar_size(banda: Banda, etiqueta: str, *, es_probe_candidato: bool = False) -> tuple[float, str]:
    """Traduce una etiqueta de juicio → tamaño DENTRO de la banda (doc 39 §2.6). Determinista. Devuelve
    (size, motivo). NUNCA supera el techo. Etiqueta desconocida → PASS (conservador: no mueve)."""
    if etiqueta in ("VETO", "THESIS_BROKEN"):
        return 0.0, f"{etiqueta}: juicio excluye (siempre permitido)"
    if etiqueta in ("PASS", "HOLD"):
        return banda.clamp(banda.base), f"{etiqueta}: sin cambio (base determinista)"
    if etiqueta in politica.FACTOR_PRIORITY:                         # PRIORITY_*: subir DENTRO de la banda
        f = politica.FACTOR_PRIORITY[etiqueta]
        size = banda.base + f * (banda.techo - banda.base)          # gap base→techo, nunca lo pasa
        return banda.clamp(size), f"{etiqueta}: +{f:.0%} del gap base→techo (dentro de banda)"
    if etiqueta == "ADMIT_PROBE":                                   # rescate de FALSO NEGATIVO determinista
        if banda.base >= politica.SIZE_PROBE_JUICIO:
            return banda.clamp(banda.base), "ADMIT_PROBE: ya tenía tamaño ≥ probe (sin cambio)"
        return banda.clamp(politica.SIZE_PROBE_JUICIO), "ADMIT_PROBE: probe chico (rescata falso-negativo)"
    return banda.clamp(banda.base), f"etiqueta desconocida {etiqueta!r} → PASS"


def aplicar_juicio(intervenciones: list[Intervencion], bandas: dict[str, Banda], *,
                   presupuesto: int | None = None) -> list[Intervencion]:
    """Aplica las intervenciones respetando el PRESUPUESTO de promociones (doc 39 §2.6): los VETO/THESIS_BROKEN
    y PASS/HOLD son ilimitados; las PROMOCIONES (ADMIT_PROBE/PRIORITY_*) consumen presupuesto (máx N por ciclo).
    Una promoción SIN falsador escrito NO se ejecuta (cae a PASS). Devuelve las intervenciones con size asignado.

    ⚠️ Decisión abierta (doc 39 §2.7, IA1↔IA2): sin PISO obligatorio de despliegue — el presupuesto es un MÁXIMO,
    no un target. El ledger de rechazos vigila que no nos abstengamos en masa (en vez de forzar un piso)."""
    presupuesto = presupuesto if presupuesto is not None else politica.PRESUPUESTO_PROMOCIONES
    usadas = 0
    out = []
    for iv in intervenciones:
        banda = bandas.get(iv.ticker, Banda(0.0, 0.0, 0.0))
        iv.size_base = banda.base
        es_promo = iv.etiqueta in PROMOCIONES
        if es_promo and not (iv.falsador and iv.fecha_falsador):
            iv.size_asignado, iv.motivo = banda.clamp(banda.base), "promoción SIN falsador escrito → NO se ejecuta (PASS)"
            out.append(iv)
            continue
        if es_promo and usadas >= presupuesto:
            iv.size_asignado, iv.motivo = banda.clamp(banda.base), f"presupuesto de promociones agotado ({presupuesto}) → PASS"
            out.append(iv)
            continue
        size, motivo = asignar_size(banda, iv.etiqueta)
        iv.size_asignado, iv.motivo = size, motivo
        if es_promo and size > (banda.base + 1e-9):     # contó como promoción solo si efectivamente subió
            usadas += 1
        out.append(iv)
    return out
