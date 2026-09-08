"""Estado stateful por posición del núcleo (§5.4, §6.2, §5.5, §13).

El núcleo determinista es puro; pero algunas reglas son inherentemente STATEFUL
porque cuentan eventos a través del tiempo y viajan CON la posición:

  - Contador de corridas de vía 1 (§5.4): un trigger puede correrse de fecha (o
    bajarse el umbral) UNA vez con razón registrada; la SEGUNDA corrida es el
    disparo. Se cuenta por compromiso económico, viaja con la posición, y la
    migración de arquetipo NO lo reinicia.
  - Fecha congelada del catalizador (§5.4 anti-gaming): P2/B2 se congela al
    entrar; moverla oficialmente CONSUME una corrida.
  - Re-entrada post-trigger (§13.1 Candado B, VIDAS_REENTRADA=1): una sola vida.
  - Ventanas sin progreso (§13.1 stop de progreso): earnings sin hecho a favor.
  - Migración-no-expulsa (§6.2): cambia régimen sin reiniciar contadores; recorte
    inmediato sin banda 1.25 si el peso excede el nuevo Hard Cap.
  - Watchlist «todavía no» (§5.5): re-evaluar cuando el catalizador entra en
    ventana.

Durante la SOMBRA se persiste a JSON (data/nucleo_estado/<TICKER>.json) — cero
schema nuevo en la DB viva. En el corte (Fase 4) migra a tabla.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from backend.nucleo.constantes import VENTANA_P2_MESES, VIDAS_REENTRADA
from backend.utils import get_logger

log = get_logger(__name__)

ESTADO_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "nucleo_estado"


@dataclass
class EstadoNucleoPosicion:
    """Estado vivo del núcleo para una posición. Viaja con la posición."""
    ticker: str
    arquetipo: str | None = None
    fragility_score: int | None = None
    hardcap_vigente: float | None = None

    # §5.4 — catalizador definitorio (P2/B2), fecha congelada al entrar.
    catalizador_fecha_congelada: str | None = None   # ISO date.
    # §5.4 — contador de corridas de vía 1 (date-move + threshold-lower).
    corridas_via1: int = 0
    historial_corridas: list[dict] = field(default_factory=list)

    # §13.1 — re-entrada post-trigger (Candado B).
    reentradas_usadas: int = 0

    # §13.1 — stop de progreso: ventanas de earnings sin hecho a favor.
    ventanas_sin_progreso: int = 0

    # §5.5 — watchlist «todavía no».
    en_watchlist_todavia_no: bool = False
    reeval_fecha: str | None = None   # ISO date en que vuelve a correr el gate.

    historial_migraciones: list[dict] = field(default_factory=list)


# ----------------------------- Contador de corridas (§5.4) -----------------------------

def registrar_corrida(estado: EstadoNucleoPosicion, tipo: str, motivo: str,
                      cuando: str | None = None) -> dict:
    """Registra una corrida de vía 1 (correr_fecha | bajar_umbral). Devuelve
    {disparo: bool}. La PRIMERA corrida se permite con razón; la SEGUNDA dispara
    (anti-LAZR). Bajar un umbral cuenta igual que correr una fecha.
    """
    assert tipo in ("correr_fecha", "bajar_umbral"), f"tipo inválido: {tipo}"
    estado.corridas_via1 += 1
    estado.historial_corridas.append(
        {"tipo": tipo, "motivo": motivo, "cuando": cuando or _hoy_iso(), "n": estado.corridas_via1}
    )
    disparo = estado.corridas_via1 >= 2   # la segunda corrida es el disparo.
    return {"disparo": disparo, "corridas": estado.corridas_via1}


def mover_fecha_catalizador(estado: EstadoNucleoPosicion, nueva_fecha: str,
                            motivo: str) -> dict:
    """Mover oficialmente la fecha del catalizador CONSUME una corrida (§5.4).
    Devuelve {disparo}."""
    r = registrar_corrida(estado, "correr_fecha", motivo)
    estado.catalizador_fecha_congelada = nueva_fecha
    return r


# ----------------------------- Re-entrada (§13.1 Candado B) -----------------------------

def puede_reentrar(estado: EstadoNucleoPosicion) -> bool:
    return estado.reentradas_usadas < VIDAS_REENTRADA


def registrar_reentrada(estado: EstadoNucleoPosicion) -> None:
    estado.reentradas_usadas += 1


# ----------------------------- Stop de progreso (§13.1) -----------------------------

def registrar_ventana_earnings(estado: EstadoNucleoPosicion, hubo_hecho_a_favor: bool) -> None:
    """Al cerrar una ventana de earnings: si hubo hecho a favor, resetea el
    contador; si no, lo incrementa (alimenta vía 1 / salida.evaluar_salida)."""
    if hubo_hecho_a_favor:
        estado.ventanas_sin_progreso = 0
    else:
        estado.ventanas_sin_progreso += 1


# ----------------------------- Migración-no-expulsa (§6.2) -----------------------------

def aplicar_migracion(estado: EstadoNucleoPosicion, nuevo_arquetipo: str,
                      nuevo_fragility: int, nuevo_hardcap: float,
                      peso_vivo: float | None = None) -> dict:
    """Migración de arquetipo sobre posición viva (§6.2): cambia el régimen, NO
    expulsa, NO reinicia contadores. Recorte INMEDIATO sin banda 1.25 si el peso
    excede el nuevo Hard Cap (la banda 1.25 es solo para desborde por PRECIO).

    Devuelve {recorte_inmediato: bool, recortar_a, revisar_cubo: bool}.
    """
    anterior = {"arquetipo": estado.arquetipo, "fragility": estado.fragility_score,
                "hardcap": estado.hardcap_vigente}
    estado.arquetipo = nuevo_arquetipo
    estado.fragility_score = nuevo_fragility
    estado.hardcap_vigente = nuevo_hardcap
    estado.historial_migraciones.append(
        {"cuando": _hoy_iso(), "de": anterior,
         "a": {"arquetipo": nuevo_arquetipo, "fragility": nuevo_fragility, "hardcap": nuevo_hardcap}}
    )
    # Los contadores (corridas_via1, ventanas_sin_progreso) NO se reinician: viajan
    # con la posición (§5.4 llave única / §6.2).
    recorte = False
    recortar_a = None
    if peso_vivo is not None and peso_vivo > nuevo_hardcap:
        recorte = True            # sin banda 1.25: es baja de cap por migración.
        recortar_a = nuevo_hardcap
    return {"recorte_inmediato": recorte, "recortar_a": recortar_a,
            "revisar_cubo": True, "anterior": anterior}


# ----------------------------- Watchlist «todavía no» (§5.5) -----------------------------

def programar_reeval_todavia_no(estado: EstadoNucleoPosicion, catalizador_meses: float,
                                desde: datetime | None = None,
                                ventana_meses: int = VENTANA_P2_MESES) -> None:
    """Programa la re-evaluación: el catalizador está a `catalizador_meses`; vuelve
    a correr el gate cuando entre en la ventana de `ventana_meses` (§5.5)."""
    desde = desde or datetime.utcnow()
    meses_hasta_ventana = max(0.0, catalizador_meses - ventana_meses)
    reeval = _sumar_meses(desde, meses_hasta_ventana)
    estado.en_watchlist_todavia_no = True
    estado.reeval_fecha = reeval.date().isoformat()


def debe_reevaluar(estado: EstadoNucleoPosicion, hoy: datetime | None = None) -> bool:
    """¿Llegó la fecha de re-evaluación de la watchlist «todavía no»?"""
    if not estado.en_watchlist_todavia_no or not estado.reeval_fecha:
        return False
    hoy = hoy or datetime.utcnow()
    return hoy.date().isoformat() >= estado.reeval_fecha


# ----------------------------- Persistencia JSON (sombra) -----------------------------

def cargar_estado(ticker: str) -> EstadoNucleoPosicion:
    """Carga el estado del ticker, o uno nuevo si no existe."""
    f = ESTADO_DIR / f"{ticker.upper()}.json"
    if f.exists():
        try:
            return EstadoNucleoPosicion(**json.loads(f.read_text(encoding="utf-8")))
        except Exception as e:  # noqa: BLE001
            log.warning("estado — %s ilegible, se crea nuevo: %s", ticker, e)
    return EstadoNucleoPosicion(ticker=ticker.upper())


def guardar_estado(estado: EstadoNucleoPosicion) -> None:
    ESTADO_DIR.mkdir(parents=True, exist_ok=True)
    f = ESTADO_DIR / f"{estado.ticker.upper()}.json"
    f.write_text(json.dumps(asdict(estado), indent=2, default=str), encoding="utf-8")


# ----------------------------- Helpers de fecha -----------------------------

def _hoy_iso() -> str:
    return datetime.utcnow().date().isoformat()


def _sumar_meses(d: datetime, meses: float) -> datetime:
    """Suma meses (float) aproximando 1 mes = 30.44 días. Suficiente para fijar
    una fecha de re-evaluación (calibrable; el catalizador real la corrige)."""
    from datetime import timedelta
    return d + timedelta(days=meses * 30.44)
