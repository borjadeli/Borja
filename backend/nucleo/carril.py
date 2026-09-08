"""Carril especulativo (doc 29) — la opcionalidad influye en la SELECCIÓN sin contaminar el número duro.

Las empresas de PURA OPCIONALIDAD (fuera del libro duro por valuación) tienen su sizing ACÁ, no en el
duro: libro y presupuesto PROPIOS. La especulación NUNCA desplaza un nombre contratado del ranking
principal (§1). Estructura:
  - Gate estricto (§2, todas obligatorias): supervivencia · evidencia externa real · hito cercano ·
    materialidad relativa al revenue · falsabilidad escrita. "No cualquier historia entra."
  - Orden por rúbrica ordinal citada (§3) — PENDIENTE PM-LLM; acá placeholder (grado + cobertura).
  - Sizing y budget CONTENIDOS (§4/§5): cap 8%/pos, máx 2 plazas, presupuesto piso 10% → techo 25%.
  - Log = interruptor de APAGADO (§6): sin hit-rate history, el presupuesto queda en el piso.

ESTADO (doc 29 §9): arranca en SHADOW. Los hechos del gate (evidencia externa FECHADA, hito, materialidad,
falsabilidad) todavía NO se extraen → hoy el gate admite poco/nada, y es HONESTO: sin la rúbrica, no hay
opcionalidad corroborada que dimensionar. El gate + sizing quedan listos para cuando la extracción exista
(mismo patrón que los pilares: la lógica primero, el sourcing de inputs después).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.nucleo import politica
from backend.nucleo.ranking_lexicografico import CandidatoLex


@dataclass
class HechosCarril:
    """Los hechos del gate del carril (doc 29 §2), todos CITADOS cuando existan. None = no extraído (falla
    conservador: sin la rúbrica no se admite). Distinto del libro duro: acá el upside es NO contratado."""
    ticker: str
    # §2 — gate (todas obligatorias):
    runway_anos: float | None = None                 # supervivencia hasta el hito
    dilucion_capturada_en_fragilidad: bool = False    # alternativa a runway (la dilución ya pesa en fragilidad)
    evidencia_externa: bool | None = None             # design-win/piloto pago/RFP/cliente/permiso (NO TAM/deck/ceiling)
    hito_meses: float | None = None                   # meses al hito (≤ HITO_MAX_MESES_CARRIL)
    materialidad_relativa: bool | None = None         # si ocurre, cambia la ESCALA (hito ≥X% del revenue actual)
    falsabilidad_escrita: bool | None = None          # qué / antes de qué fecha / verificable en qué documento
    # §3 — orden (rúbrica ordinal citada; PENDIENTE PM-LLM):
    grado_opcionalidad: int | None = None             # grado de la tabla versionada (None = sin rúbrica → placeholder)
    catalizador: str | None = None                    # catalizador/cuello (para el cap "máx 1 por catalizador")


def _b(snap: dict, key: str):
    """Lee un hecho booleano CITADO del snapshot (DIRECT/DERIVED → su valor; si no está o UNKNOWN → None)."""
    from backend.nucleo import fact_store as FS
    f = snap.get(key)
    if f is None or getattr(f, "support_type", None) not in ("DIRECT", "DERIVED"):
        return None
    return FS._dec(f.value)


def construir_hechos_carril(ticker: str, snap: dict, *, runway_anos: float | None = None,
                            dilucion_capturada: bool = False, catalizador: str | None = None) -> HechosCarril:
    """Arma `HechosCarril` desde el fact_store (doc 29 §2/§3), determinista. Los booleanos del gate salen de los
    fact_keys `opcion_*` (FACT_KEYS_CARRIL) citados; el grado §3 de la rúbrica (contraparte/dinero/precedente).
    supervivencia (runway/dilución) se pasa (viene de dilucion.py / fragilidad). Hecho ausente → None (no pasa)."""
    from backend.nucleo import politica
    cf = _b(snap, "opcion_contraparte_financiada")
    da = _b(snap, "opcion_dinero_autorizado")
    tp = _b(snap, "opcion_transaccion_precedente")
    grado = politica.grado_opcionalidad(bool(cf), bool(da), bool(tp)) if any(x is not None for x in (cf, da, tp)) else None
    return HechosCarril(
        ticker=ticker,
        runway_anos=runway_anos,
        dilucion_capturada_en_fragilidad=dilucion_capturada,
        evidencia_externa=_b(snap, "opcion_evidencia_externa"),
        hito_meses=(12.0 if _b(snap, "opcion_hito_cercano") is True else None),   # proxy bool→meses (dentro de ventana)
        materialidad_relativa=_b(snap, "opcion_materialidad"),
        falsabilidad_escrita=_b(snap, "opcion_falsador_documento"),
        grado_opcionalidad=grado,
        catalizador=catalizador,
    )


def gate_carril(h: HechosCarril) -> dict:
    """Gate de entrada al carril (doc 29 §2) — todas obligatorias. Devuelve {pasa, motivos}. Conservador:
    un hecho None (no extraído) NO pasa (sin evidencia citada, la historia no entra)."""
    motivos: list[str] = []
    superviv = (h.runway_anos is not None and h.runway_anos >= politica.RUNWAY_MIN_CARRIL) \
        or h.dilucion_capturada_en_fragilidad
    if not superviv:
        motivos.append("supervivencia: runway < mínimo y dilución no capturada en fragilidad")
    if h.evidencia_externa is not True:
        motivos.append("sin evidencia externa real (design-win/RFP/piloto/cliente/permiso) — TAM/deck/ceiling no cuentan")
    if not (h.hito_meses is not None and h.hito_meses <= politica.HITO_MAX_MESES_CARRIL):
        motivos.append(f"hito no cercano (>{politica.HITO_MAX_MESES_CARRIL}m o sin fecha)")
    if h.materialidad_relativa is not True:
        motivos.append("materialidad relativa al revenue no establecida (¿el hito cambia la escala?)")
    if h.falsabilidad_escrita is not True:
        motivos.append("falsabilidad escrita ausente (qué / antes de qué fecha / en qué documento)")
    return {"pasa": not motivos, "motivos": motivos}


@dataclass
class PosicionCarril:
    ticker: str
    size: float
    cap: float
    grado_opcionalidad: int | None
    catalizador: str | None


@dataclass
class Carril:
    posiciones: list[PosicionCarril] = field(default_factory=list)
    invertido: float = 0.0
    presupuesto: float = 0.0
    rechazados: list[dict] = field(default_factory=list)     # candidato → por qué no entró (gate/plazas/catalizador/piso)
    politica_version: str = ""
    politica_hash: str = ""
    orden_placeholder: bool = True                            # True = sin rúbrica §3 (orden por cobertura), NO definitivo


def _clave_orden(c: CandidatoLex, h: HechosCarril) -> tuple:
    """Orden dentro del carril (doc 29 §3). DEFINITIVO = rúbrica ordinal citada (PENDIENTE). Placeholder: por
    grado_opcionalidad si existe, luego cobertura (proxy de densidad de evidencia). Menor = mejor."""
    return (-(h.grado_opcionalidad or 0), -round(c.cobertura or 0.0, 6))


def construir_carril(candidatos: list[CandidatoLex], hechos: dict[str, HechosCarril], *,
                     presupuesto: float | None = None, max_plazas: int | None = None) -> Carril:
    """Arma el libro del carril (doc 29 §2/§4/§5). Toma los candidatos de OPCIONALIDAD (elegibles fuera del
    libro duro por valuación), aplica el gate §2, ordena (§3 placeholder) y dimensiona con las guardas §4:
    cap 8%/pos, máx 2 plazas, máx 1 por catalizador, dentro del presupuesto (piso 10%, §5). No fuerza."""
    presupuesto = presupuesto if presupuesto is not None else politica.PISO_CARRIL
    max_plazas = max_plazas if max_plazas is not None else politica.MAX_PLAZAS_CARRIL
    sello = politica.sello()
    car = Carril(presupuesto=presupuesto, politica_version=sello["politica_version"],
                 politica_hash=sello["politica_hash"])

    admitidos, con_grado = [], False
    for c in candidatos:
        h = hechos.get(c.ticker) or HechosCarril(c.ticker)
        g = gate_carril(h)
        if not g["pasa"]:
            car.rechazados.append({"ticker": c.ticker, "motivo": "gate §2: " + "; ".join(g["motivos"])})
            continue
        con_grado = con_grado or (h.grado_opcionalidad is not None)
        admitidos.append((c, h))
    car.orden_placeholder = not con_grado                     # si NINGÚN admitido trae rúbrica → orden es placeholder

    admitidos.sort(key=lambda ch: _clave_orden(ch[0], ch[1]))
    catalizadores_usados: set[str] = set()
    for c, h in admitidos:
        if len(car.posiciones) >= max_plazas:
            car.rechazados.append({"ticker": c.ticker, "motivo": "max_plazas (2) del carril"})
            continue
        if h.catalizador and h.catalizador in catalizadores_usados:   # §4: máx 1 por catalizador/cuello
            car.rechazados.append({"ticker": c.ticker, "motivo": f"ya hay una opcional por catalizador '{h.catalizador}'"})
            continue
        cap = min(c.cap if c.cap is not None else politica.CAP_CARRIL_POS, politica.CAP_CARRIL_POS)
        size = min(cap, presupuesto - car.invertido)
        if size < politica.MIN_VIABLE:
            car.rechazados.append({"ticker": c.ticker, "motivo": "sin espacio en el presupuesto del carril para el piso"})
            continue
        car.posiciones.append(PosicionCarril(c.ticker, round(size, 4), cap, h.grado_opcionalidad, h.catalizador))
        car.invertido += size
        if h.catalizador:
            catalizadores_usados.add(h.catalizador)
    car.invertido = round(car.invertido, 4)
    return car
