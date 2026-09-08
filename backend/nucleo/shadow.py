"""Shadow-runner — núcleo nuevo vs Portfolio viejo, lado a lado (traspaso §5/§6.1).

Corre el núcleo determinista NUEVO en sombra contra el Portfolio VIEJO sobre las
mismas fichas, sin poder de ejecución, y compara las decisiones de ENTRADA. Es
el paso previo al corte: el traspaso decide cortarle el paso al score viejo
cuando el núcleo nuevo pase el PASS_RATE_BACKTEST 80%.

Fuente de hechos para el núcleo nuevo (sin gastar API por defecto):
  1. Override en data/nucleo_hechos/<TICKER>.json (operador/cache) — preferido.
  2. Si no hay override y usar_llm=True, llama al extractor LLM.
  3. Si no hay ninguno, la ficha se marca 'sin_hechos' (no se inventa nada).

Comparación de ENTRADA: el viejo decide por score; el nuevo por gate+mérito.
  viejo ENTRA  = accion ∈ {entrar, aumentar, piramidacion, bucket}
  nuevo ENTRA  = decision == 'candidata' (pasó las dos vías de rechazo, tiene mérito)
Coinciden si ambos ENTRA o ambos NO-ENTRA. (La comparación de SALIDA sobre
posiciones vivas es un follow-up: usa salida.evaluar_salida con hechos de
posición viva, no el flujo de entrada.)
"""
from __future__ import annotations

import json
from pathlib import Path

from backend.agents import portfolio
from backend.database import session_scope
from backend.models import EstadoFicha, Ficha
from backend.nucleo import estado as st
from backend.nucleo.arquetipo import clasificar_arquetipo
from backend.nucleo.extractor import construir_entrada_empresa
from backend.nucleo.flujo import evaluar_empresa
from backend.nucleo.salida import EstadoPosicion, evaluar_salida
from backend.utils import get_logger

log = get_logger(__name__)

HECHOS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "nucleo_hechos"

ACCIONES_ENTRA = {
    portfolio.Accion.ENTRAR, portfolio.Accion.AUMENTAR,
    portfolio.Accion.PIRAMIDACION, portfolio.Accion.BUCKET,
}

# Salida: el viejo VENDE con salir/rotar (rotar = sacar a la incumbente).
ACCIONES_SALE_VIEJO = {portfolio.Accion.SALIR, portfolio.Accion.ROTAR}
# El nuevo VENDE con estas acciones de las 5 vías (recortar/no_aumentar NO son venta).
ACCIONES_SALE_NUEVO = {"venta_directa", "salir_urgente", "recomendar_salir"}

# Estados de fichas sobre los que tiene sentido la comparación de entrada.
ESTADOS_SHADOW = [
    EstadoFicha.PORTFOLIO_ACTIVO.value,
    EstadoFicha.WL_PRIORITARIA.value,
    EstadoFicha.WL_ACTIVA.value,
    EstadoFicha.WL_SEGUIMIENTO.value,
    EstadoFicha.BUCKET_EXPLORATORIO.value,
    EstadoFicha.CANDIDATA.value,
]


def cargar_hechos_override(ticker: str) -> dict | None:
    """Lee data/nucleo_hechos/<TICKER>.json si existe (hechos cargados a mano o
    cacheados de una corrida previa del extractor). Permite el shadow sin API."""
    f = HECHOS_DIR / f"{ticker.upper()}.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        log.warning("shadow — override %s ilegible: %s", ticker, e)
        return None


def comparar_entrada(ticker: str, *, usar_llm: bool = False) -> dict:
    """Compara la decisión de entrada vieja vs nueva para un ticker."""
    ticker = ticker.upper()
    fila: dict = {"ticker": ticker}

    # Decisión vieja (score-based). Abre su propia sesión.
    try:
        old = portfolio.generar_recomendacion(ticker)
        fila["old_accion"] = old.accion
        fila["old_entra"] = old.accion in ACCIONES_ENTRA
        fila["old_justificacion"] = (old.justificacion or "")[:200]
    except Exception as e:  # noqa: BLE001
        fila["old_accion"] = None
        fila["old_entra"] = None
        fila["error_old"] = str(e)

    # Decisión nueva (núcleo determinista). Hechos: override → LLM → sin_hechos.
    hechos = cargar_hechos_override(ticker)
    fila["fuente_hechos"] = "override" if hechos is not None else ("llm" if usar_llm else "ninguna")
    try:
        entrada = None
        if hechos is not None or usar_llm:
            entrada = construir_entrada_empresa(ticker, hechos_llm=hechos)
        if entrada is None:
            fila["new_decision"] = "sin_hechos"
            fila["new_entra"] = None
        else:
            r = evaluar_empresa(entrada)
            fila["new_decision"] = r["decision"]
            fila["new_entra"] = (r["decision"] == "candidata")
            fila["new_arquetipo"] = (r.get("arquetipo") or {}).get("arquetipo")
            fila["new_merito"] = r.get("merito")
            fila["new_motivo"] = r.get("motivo") or (r.get("gate") or {}).get("estado")
    except Exception as e:  # noqa: BLE001
        fila["new_decision"] = "error"
        fila["new_entra"] = None
        fila["error_new"] = str(e)

    if fila.get("old_entra") is None or fila.get("new_entra") is None:
        fila["coinciden"] = None
    else:
        fila["coinciden"] = (fila["old_entra"] == fila["new_entra"])
    return fila


def construir_estado_posicion(ticker: str, entrada, *, eventos: dict | None = None) -> EstadoPosicion:
    """Arma el EstadoPosicion (input de las 5 vías) para una posición viva.

    Combina: arquetipo + bull/bear/precio del extractor; contadores del estado
    stateful (ventanas sin progreso, re-entradas, segunda corrida); y `eventos`
    (override de hechos EVENT-DRIVEN que no están en la ficha estática: trigger
    disparado, governance, CRR-crítico sobreviniente, peso/HardCap vigentes). En
    producción esos eventos los traen Research/RedFlags/CRR; en sombra, override.
    """
    eventos = eventos or {}
    arq = clasificar_arquetipo(entrada.hechos_arquetipo)["arquetipo"]
    e = st.cargar_estado(ticker)
    return EstadoPosicion(
        ticker=ticker.upper(),
        arquetipo=arq,
        trigger_disparado=bool(eventos.get("trigger_disparado")),
        trigger_vencido_sin_catalizador=bool(eventos.get("trigger_vencido_sin_catalizador")),
        segunda_corrida_de_fecha=(e.corridas_via1 >= 2) or bool(eventos.get("segunda_corrida_de_fecha")),
        earnings_sin_hecho_a_favor=eventos.get("earnings_sin_hecho_a_favor", e.ventanas_sin_progreso),
        crr_critico=bool(eventos.get("crr_critico")),
        hard_governance_events=list(eventos.get("hard_governance_events") or []),
        soft_red_flags=int(eventos.get("soft_red_flags") or 0),
        bull=entrada.bull, precio=entrada.precio, bear=entrada.bear,
        bull_bear_anclado_en_hechos_ocurridos=bool(eventos.get("bull_bear_anclado_en_hechos_ocurridos")),
        peso_vivo=eventos.get("peso_vivo"),
        hardcap_vigente=eventos.get("hardcap_vigente"),
        reentradas_usadas=e.reentradas_usadas,
    )


def comparar_salida(ticker: str, *, eventos: dict | None = None, usar_llm: bool = False) -> dict:
    """Compara la decisión de SALIDA vieja (rotación) vs nueva (5 vías)."""
    ticker = ticker.upper()
    fila: dict = {"ticker": ticker}

    try:
        old = portfolio.generar_recomendacion(ticker)
        fila["old_accion"] = old.accion
        fila["old_sale"] = old.accion in ACCIONES_SALE_VIEJO
    except Exception as e:  # noqa: BLE001
        fila["old_accion"], fila["old_sale"], fila["error_old"] = None, None, str(e)

    hechos = cargar_hechos_override(ticker)
    fila["fuente_hechos"] = "override" if hechos is not None else ("llm" if usar_llm else "ninguna")
    try:
        entrada = None
        if hechos is not None or usar_llm:
            entrada = construir_entrada_empresa(ticker, hechos_llm=hechos)
        if entrada is None:
            fila["new_accion"], fila["new_sale"] = "sin_hechos", None
        else:
            ep = construir_estado_posicion(ticker, entrada, eventos=eventos)
            r = evaluar_salida(ep)
            fila["new_accion"] = r["accion"]
            fila["new_sale"] = r["accion"] in ACCIONES_SALE_NUEVO
            fila["new_via"] = (r.get("via_ganadora") or {}).get("via")
    except Exception as e:  # noqa: BLE001
        fila["new_accion"], fila["new_sale"], fila["error_new"] = "error", None, str(e)

    if fila.get("old_sale") is None or fila.get("new_sale") is None:
        fila["coinciden"] = None
    else:
        fila["coinciden"] = (fila["old_sale"] == fila["new_sale"])
    return fila


def clasificar_posiciones_vivas(usar_llm: bool = False) -> list[dict]:
    """Riesgo de migración §6.1: clasifica el arquetipo de las posiciones VIVAS al
    entrar al núcleo nuevo (abiertas bajo score 0-10, sin arquetipo). Corre en
    sombra para que el operador revise las 8 a mano antes del corte."""
    with session_scope() as s:
        tickers = [f.ticker for f in s.query(Ficha)
                   .filter(Ficha.estado == EstadoFicha.PORTFOLIO_ACTIVO.value).all()]
    salida = []
    for t in tickers:
        hechos = cargar_hechos_override(t)
        fila = {"ticker": t, "fuente_hechos": "override" if hechos is not None else ("llm" if usar_llm else "ninguna")}
        if hechos is None and not usar_llm:
            fila["arquetipo"] = "sin_hechos"
        else:
            entrada = construir_entrada_empresa(t, hechos_llm=hechos)
            arq = clasificar_arquetipo(entrada.hechos_arquetipo) if entrada else None
            fila["arquetipo"] = arq["arquetipo"] if arq else "sin_hechos"
            fila["traza"] = arq["traza"] if arq else None
        salida.append(fila)
    return salida


def _tickers_vivos() -> list[str]:
    with session_scope() as s:
        return [f.ticker for f in s.query(Ficha).filter(Ficha.estado.in_(ESTADOS_SHADOW)).all()]


def correr_shadow(tickers: list[str] | None = None, *, usar_llm: bool = False,
                  modo: str = "entrada") -> dict:
    """Corre el shadow sobre `tickers` (o todas las fichas vivas). modo='entrada'
    compara gate+mérito vs score; modo='salida' compara las 5 vías vs rotación.
    Devuelve las comparaciones + un resumen con la tasa de acuerdo (proxy PASS_RATE)."""
    if tickers is None:
        tickers = _tickers_vivos()
    comparar = comparar_salida if modo == "salida" else comparar_entrada
    comparaciones = [comparar(t, usar_llm=usar_llm) for t in tickers]

    comparables = [c for c in comparaciones if c.get("coinciden") is not None]
    coinciden = [c for c in comparables if c["coinciden"]]
    sin_hechos = [c for c in comparaciones
                  if c.get("new_decision") == "sin_hechos" or c.get("new_accion") == "sin_hechos"]

    resumen = {
        "total": len(comparaciones),
        "comparables": len(comparables),
        "coinciden": len(coinciden),
        "discrepan": len(comparables) - len(coinciden),
        "sin_hechos": len(sin_hechos),
        "tasa_acuerdo": (len(coinciden) / len(comparables)) if comparables else None,
    }
    log.info("shadow — total=%d comparables=%d acuerdo=%s sin_hechos=%d",
             resumen["total"], resumen["comparables"],
             f"{resumen['tasa_acuerdo']:.0%}" if resumen["tasa_acuerdo"] is not None else "N/A",
             resumen["sin_hechos"])
    return {"resumen": resumen, "comparaciones": comparaciones}
