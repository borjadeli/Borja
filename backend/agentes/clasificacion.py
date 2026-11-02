"""D4 — sizing por clasificación (doc 74): la clasificación de invertibilidad tiene consecuencia en el TAMAÑO.

Dos piezas deterministas (el PM sizea DENTRO; el código LIMITA, no decide — principio rector):
  1. TECHO de clasificación por hechos duros → el Analista (pro-tesis) no puede inflar la etiqueta para
     habilitar más peso. La clasificación efectiva = min(lo que pide el analista, lo que permiten los hechos).
  2. BANDA de peso por clasificación efectiva + caps AGREGADOS (bucket especulativo + cluster temático): la
     banda por nombre no controla el riesgo correlacionado (10 especulativas a 1,5% = 15% de apuestas binarias
     del mismo tema).

Arranca en MODO SOMBRA (reporta al Auditor; no gatea) hasta confiar en la clasificación — doc 74 §5.
Funciones PURAS y testeables. NO hay fórmula de sizing por convicción (sería trasladar la decisión al código).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# orden de MENOS a MÁS peso permitido; el "techo" es el máximo que los hechos habilitan.
ORDEN = ["watchlist", "especulativa", "satelite", "core"]
_BANDAS_DEFAULT = {"especulativa": 0.015, "satelite": 0.05}   # watchlist=0 · core=peso_max_nombre (IPS)


@dataclass
class ClasifTicker:
    """Lo que el caller sabe de un nombre para clasificarlo (de la ficha + pack). Sin peso."""
    analyst_clasif: str                      # analyst_classification de la ficha de invertibilidad
    revenue_recurrente: bool                 # tracción 4 (revenue recurrente en el mercado de la tesis)
    tiene_puente: bool                       # D1: hay escenarios/puente económico (si no → UNKNOWN)
    fcf_negativo: bool | None = None         # opcional (del pack); si None, la regla de runway no corre
    runway_meses: float | None = None        # opcional (del pack)


@dataclass
class FilaSizing:
    ticker: str
    peso: float
    analyst: str
    techo: str
    efectiva: str
    banda: float
    exceso: bool                             # peso > banda de la clasificación efectiva
    inflada: bool                            # el analista pidió una clasificación mayor que el techo de hechos


@dataclass
class AnalisisSizing:
    filas: list[FilaSizing] = field(default_factory=list)
    bucket_especulativo: float = 0.0
    viol_bucket: bool = False
    clusters: dict[str, float] = field(default_factory=dict)
    viol_cluster: list[str] = field(default_factory=list)


def _rank(c: str) -> int:
    return ORDEN.index(c) if c in ORDEN else 0


def _min_clasif(a: str, b: str) -> str:
    return a if _rank(a) <= _rank(b) else b


def techo_clasificacion(c: ClasifTicker) -> str:
    """Máxima clasificación que PERMITEN los hechos duros (doc 74 D4). El analista no puede superarlo."""
    techo = "core"
    if c.fcf_negativo and c.runway_meses is not None and c.runway_meses < 24:
        techo = _min_clasif(techo, "satelite")          # quema con pista corta: no es core
    if not c.revenue_recurrente:
        techo = _min_clasif(techo, "especulativa")       # sin revenue recurrente: tope especulativa
    if not c.tiene_puente:
        techo = _min_clasif(techo, "especulativa")       # D1 UNKNOWN: solo tamaño de opción
    return techo


def clasificacion_efectiva(c: ClasifTicker) -> str:
    """min(lo que pide el analista, lo que permiten los hechos). El analista puede ir MÁS BAJO, nunca más alto."""
    return _min_clasif(c.analyst_clasif, techo_clasificacion(c))


def banda_de(clasif: str, bandas: dict | None, peso_max_nombre: float) -> float:
    """Techo de peso por nombre según la clasificación efectiva. watchlist=0 · core=peso_max del IPS."""
    b = {**_BANDAS_DEFAULT, **(bandas or {})}
    if clasif == "core":
        return peso_max_nombre
    if clasif == "watchlist":
        return 0.0
    return float(b.get(clasif, peso_max_nombre))


def analisis_sizing(pesos: dict[str, float], clasif: dict[str, ClasifTicker],
                    clusters: dict[str, str | None] | None = None, *, bandas: dict | None = None,
                    cap_bucket: float = 1.0, cap_cluster: float = 1.0,
                    peso_max_nombre: float = 1.0) -> AnalisisSizing:
    """Compara la cartera objetivo contra las bandas por clasificación + caps agregados. SOLO análisis — no
    modifica pesos (el gate duro vendrá cuando se active el modo 'duro'). `pesos` ticker→fracción."""
    clusters = clusters or {}
    out = AnalisisSizing()
    bucket = 0.0
    cl_sum: dict[str, float] = {}
    for tk, w in pesos.items():
        c = clasif.get(tk)
        if c is None:                                    # sin clasificación → no se evalúa (no se inventa)
            continue
        ef = clasificacion_efectiva(c)
        banda = banda_de(ef, bandas, peso_max_nombre)
        out.filas.append(FilaSizing(
            ticker=tk, peso=round(w, 4), analyst=c.analyst_clasif, techo=techo_clasificacion(c),
            efectiva=ef, banda=banda, exceso=w > banda + 1e-9,
            inflada=_rank(c.analyst_clasif) > _rank(techo_clasificacion(c))))
        if ef == "especulativa":
            bucket += w
        cl = clusters.get(tk)
        if cl:
            cl_sum[cl] = cl_sum.get(cl, 0.0) + w
    out.bucket_especulativo = round(bucket, 4)
    out.viol_bucket = bucket > cap_bucket + 1e-9
    out.clusters = {k: round(v, 4) for k, v in cl_sum.items()}
    out.viol_cluster = [k for k, v in cl_sum.items() if v > cap_cluster + 1e-9]
    return out


def render_sizing(a: AnalisisSizing, modo: str = "sombra", *, cap_bucket: float = 1.0,
                  cap_cluster: float = 1.0) -> str:
    """Texto para el Auditor. En 'sombra' avisa que NO se gatea (todavía)."""
    pre = "[SOMBRA] " if modo != "duro" else ""
    L = [f"{pre}SIZING POR CLASIFICACIÓN (D4, modo {modo}):"]
    excesos = [f for f in a.filas if f.exceso]
    infladas = [f for f in a.filas if f.inflada]
    for f in excesos:
        L.append(f"  · {f.ticker}: {f.peso:.1%} > banda {f.efectiva} {f.banda:.1%}"
                 f"{' (clasif. INFLADA: analista pidió ' + f.analyst + ' vs techo ' + f.techo + ')' if f.inflada else ''}")
    for f in infladas:
        if not f.exceso:
            L.append(f"  · {f.ticker}: clasif. INFLADA — analista {f.analyst} vs techo de hechos {f.techo} "
                     f"(efectiva {f.efectiva})")
    if a.viol_bucket:
        L.append(f"  · bucket especulativo {a.bucket_especulativo:.1%} > cap {cap_bucket:.1%}")
    for cl in a.viol_cluster:
        L.append(f"  · cluster '{cl}' {a.clusters[cl]:.1%} > cap {cap_cluster:.1%}")
    if len(L) == 1:
        L.append("  · sin violaciones de banda/bucket/cluster")
    return "\n".join(L)
