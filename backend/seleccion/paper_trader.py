"""Trader automático en PAPER del núcleo nuevo — opera sin confirmación humana.

Plata SIMULADA. El núcleo nuevo opera su PROPIO libro paper (separado del libro
del sistema viejo) para evitar el "doble decisor" sobre el mismo libro (migración
§6.1) y para poder comparar performance vieja vs nueva lado a lado.

Decisión 100% DETERMINISTA (el núcleo manda, sin juicio blando del PM):
  SALIDA (primero, §7.4 ventas-antes-de-entradas): por cada posición viva corre
    salida.evaluar_salida; si una vía recomienda salir → cierra; si recorta → ajusta.
  DESPLIEGUE: el 70% es PISO, no techo — se despliega capital hacia el TECHO de 100%
    (§7, §9) guiado por mérito: (a) abre slots libres (hasta MAX_POSICIONES) con las
    mejores candidatas por mérito (Selector), y (b) si PERMITIR_PIRAMIDAR, topea
    posiciones vivas hacia su Hard Cap con el capital que falte. Hard Caps + piso 5% +
    cubo son el límite real; si no hay candidatas claras, el cash residual emerge solo
    (no se fuerza el despliegue).

NO hay confirmación humana (es paper, por diseño del operador 2026-06-24). Todo
queda en un journal append-only y se persiste a JSON (data/nucleo_paper/).

Eventos no-precio (trigger disparado, governance, CRR-crítico) vendrían del
pipeline de Research/RedFlags; mientras no esté cableado, la salida en paper opera
con las vías de PRECIO (vía 4 asimetría, vía 5 tamaño) + lo que haya en `eventos`.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from backend.nucleo.constantes import (
    CUBO_RESIDUAL_CERO,
    INCREMENTO_MIN_TOPEO,
    MAX_POR_SUBSECTOR,
    MAX_POSICIONES,
    OBJETIVO_INVERTIDO,
    PERMITIR_PIRAMIDAR,
    PISO_POSICION,
    TOPE_INVERTIDO,
)
from backend.nucleo.salida import EstadoPosicion, evaluar_salida
from backend.nucleo.selector import normalizar_merito
from backend.nucleo.sizing import sizing_final
from backend.seleccion.challenger import (
    CHALLENGER_ACTIVO,
    MAX_SWAPS_POR_CICLO,
    Titular,
    evaluar_desafio,
)
from backend.utils import get_logger

log = get_logger(__name__)

LIBRO_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "nucleo_paper" / "libro.json"

ACCIONES_SALIDA_CIERRE = {"venta_directa", "salir_urgente", "recomendar_salir"}


@dataclass
class LibroPaper:
    posiciones: dict = field(default_factory=dict)   # ticker -> {sizing, precio_entrada, fecha, arquetipo, merito}
    journal: list = field(default_factory=list)       # append-only: {fecha, accion, ticker, ...}
    actualizado: str | None = None
    snapshots: list = field(default_factory=list)     # curva de equity: [{fecha, equity, pnl_pct}]
    last_mtm: dict | None = None                      # último mark-to-market (para la home, sin red)

    def invertido(self) -> float:
        return sum(p["sizing"] for p in self.posiciones.values())


def cargar_libro() -> LibroPaper:
    if LIBRO_PATH.exists():
        try:
            return LibroPaper(**json.loads(LIBRO_PATH.read_text(encoding="utf-8")))
        except Exception as e:  # noqa: BLE001
            log.warning("paper — libro ilegible, se crea nuevo: %s", e)
    return LibroPaper()


def guardar_libro(libro: LibroPaper) -> None:
    LIBRO_PATH.parent.mkdir(parents=True, exist_ok=True)
    LIBRO_PATH.write_text(json.dumps(asdict(libro), indent=2, ensure_ascii=False, default=str),
                          encoding="utf-8")


def _hoy() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _log(libro: LibroPaper, accion: str, ticker: str, **extra) -> dict:
    ev = {"fecha": _hoy(), "accion": accion, "ticker": ticker, **extra}
    libro.journal.append(ev)
    return ev


def _sectores_por_ticker(tickers: list[str]) -> dict:
    """Lee Ficha.sector (taxonomía curada del sistema viejo) para el cap de
    concentración del deploy. Tolerante: si la DB falla, devuelve {}."""
    if not tickers:
        return {}
    try:
        from backend.database import session_scope
        from backend.models import Ficha
        ups = [t.upper() for t in tickers]
        with session_scope() as s:
            return {row.ticker: row.sector
                    for row in s.query(Ficha.ticker, Ficha.sector).filter(Ficha.ticker.in_(ups)).all()}
    except Exception as e:  # noqa: BLE001
        log.warning("paper — lectura de sectores falló: %s", e)
        return {}


def evaluaciones_desde_cache(tickers: list[str]) -> list[dict]:
    """Construye las evaluaciones del núcleo desde los hechos cacheados (SIN LLM)
    y les adjunta precio/bull/bear (que viven en EntradaEmpresa, no en el resultado).

    Lee los hechos de data/nucleo_hechos/<TICKER>.json (los escribe la reextracción
    semanal) y los INYECTA como hechos_llm → cero gasto de API en el ciclo diario.
    La capa determinista (EDGAR/precio) sí se refresca cada ciclo dentro de
    construir_entrada_empresa. Un ticker sin cache se saltea: no se gasta LLM en el
    ciclo diario (el cache lo puebla el job semanal `paper_reextraccion`).
    """
    import json as _json

    from backend.nucleo.extractor import HECHOS_DIR, construir_entrada_empresa
    from backend.nucleo.flujo import evaluar_empresa

    sectores = _sectores_por_ticker(tickers)  # para el cap de concentración del deploy.
    out = []
    for t in tickers:
        cache_file = HECHOS_DIR / f"{t.upper()}.json"
        if not cache_file.exists():
            continue  # sin hechos cacheados → no evaluar (no gastar LLM en el ciclo diario).
        try:
            hechos = _json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            log.warning("paper — hechos cacheados ilegibles para %s: %s", t, e)
            continue
        entrada = construir_entrada_empresa(t, hechos_llm=hechos)  # inyectado → SIN LLM.
        if entrada is None:
            continue
        ev = evaluar_empresa(entrada)
        ev["_precio"], ev["_bull"], ev["_bear"] = entrada.precio, entrada.bull, entrada.bear
        ev["_sector"] = sectores.get(t.upper())
        out.append(ev)
    return out


def eventos_red_flags(tickers: list[str]) -> dict:
    """Eventos DETERMINISTAS (sin LLM) para las vías 2 y 3 de salida, por ticker.

    - Vía 2 (CRR-crítico): going concern / muro de deuda / dilución fatal vía
      `calcular_crr_ticker` (Fase 0) → crr_critico=True si nivel 'Crítico'.
    - Vía 3 (red flags blandos): `Ficha.red_flags_count` del sistema viejo
      (≥3 dispara salir_urgente).

    NO cubre governance hard (auditor/SEC/delisting) ni la vía 1 (triggers/progreso):
    esas necesitan el pipeline de noticias/monitor (no determinista todavía).
    Pensada para correr sobre las posiciones VIVAS (pocas) — hace EDGAR por ticker.
    """
    if not tickers:
        return {}
    from backend.agents.capital_raise_risk import calcular_crr_ticker
    from backend.database import session_scope
    from backend.models import Ficha

    red_flags: dict[str, int] = {}
    try:
        with session_scope() as s:
            for row in (s.query(Ficha.ticker, Ficha.red_flags_count)
                        .filter(Ficha.ticker.in_(tickers)).all()):
                red_flags[row.ticker] = row.red_flags_count or 0
    except Exception as e:  # noqa: BLE001
        log.warning("paper — lectura de red_flags falló: %s", e)

    eventos: dict[str, dict] = {}
    for t in tickers:
        ev: dict = {}
        try:
            crr = calcular_crr_ticker(t)
            if crr and crr.get("nivel") == "Crítico":
                ev["crr_critico"] = True
        except Exception as e:  # noqa: BLE001
            log.warning("paper — CRR falló para %s: %s", t, e)
        if red_flags.get(t, 0):
            ev["soft_red_flags"] = red_flags[t]
        if ev:
            eventos[t] = ev
    return eventos


PROMOCIONES_PM = ("ADMIT_PROBE", "PRIORITY_HIGH", "PRIORITY_MEDIUM", "PRIORITY_LOW")  # etiquetas que suben tamaño


def _pm_targets(pm_libro) -> dict:
    """ticker -> {'size', 'promovido', 'etiqueta'} desde un LibroPM (objeto) o su dict serializado (libro_pm.json).

    Vacío si pm_libro es None → el ciclo cae al sizing determinista por mérito (comportamiento previo, intacto).
    Cuando hay targets, el PM manda el TAMAÑO (dentro del hard_cap): VETO/THESIS_BROKEN → size 0 → no entra;
    PASS/HOLD → base (piso, el determinismo despliega el piso); PRIORITY_* promovido → sube hacia el techo."""
    if not pm_libro:
        return {}
    decis = pm_libro.get("decisiones") if isinstance(pm_libro, dict) else getattr(pm_libro, "decisiones", [])
    out = {}
    for d in decis or []:
        if isinstance(d, dict):
            if d.get("valido") is False:
                continue  # llamada al PM fallida (fallback) → NO sizea el libro (cae al mérito, no posición-piso fantasma).
            tk, size, etq, promo = d.get("ticker"), d.get("size_final") or 0.0, d.get("etiqueta", ""), bool(d.get("promovido"))
        else:
            if getattr(getattr(d, "memo", None), "valido", True) is False:
                continue  # ídem para el LibroPM objeto (DecisionPM.memo.valido).
            tk, size, etq = d.ticker, d.size_final or 0.0, d.etiqueta
            promo = etq in PROMOCIONES_PM and size > (d.banda.base + 1e-9)
        if tk:
            out[tk] = {"size": size, "promovido": promo, "etiqueta": etq}
    return out


def correr_ciclo(evaluaciones: list[dict], *, eventos: dict | None = None,
                 libro: LibroPaper | None = None, persistir: bool = True, pm_libro=None) -> dict:
    """Corre un ciclo completo de trading automático en paper.

    evaluaciones: salidas de flujo.evaluar_empresa() (con ticker, decision, merito,
      hard_cap, arquetipo, asimetria, y bull/bear/precio en el sub-dict si están).
    eventos: dict ticker -> hechos event-driven para la salida (opcional).
    pm_libro: LibroPM (objeto o dict serializado) del canal de juicio. Si se pasa, el PM manda el TAMAÑO
      DENTRO del hard_cap determinista (el determinismo pone el techo/veto; el juicio elige adentro, doc 39).
      Si es None → sizing por mérito como antes.

    Devuelve {ventas, recortes, compras, topeos, invertido, subinvertido, ...}.
    """
    eventos = eventos or {}
    libro = libro or cargar_libro()
    pm_t = _pm_targets(pm_libro)   # vacío → sizing por mérito (comportamiento previo)
    por_ticker = {e["ticker"]: e for e in evaluaciones}
    ventas, recortes, compras, topeos, swaps = [], [], [], [], []
    vendidos_este_ciclo: set[str] = set()    # no se re-compran en el mismo ciclo (§13.1 re-entrada).
    recortados_este_ciclo: set[str] = set()  # recortados por una vía de salida → no topear el mismo ciclo.

    # ---- 1. SALIDA (antes que entradas, §7.4) ----
    for ticker in list(libro.posiciones.keys()):
        pos = libro.posiciones[ticker]
        ev = por_ticker.get(ticker)
        if ev is None:
            continue  # sin datos frescos este ciclo → no se toca.
        ep = EstadoPosicion(
            ticker=ticker, arquetipo=pos.get("arquetipo") or ev.get("arquetipo", {}).get("arquetipo", ""),
            bull=ev.get("_bull"), precio=ev.get("_precio"), bear=ev.get("_bear"),
            bull_bear_anclado_en_hechos_ocurridos=True,
            peso_vivo=pos["sizing"], hardcap_vigente=ev.get("hard_cap"),
            **(eventos.get(ticker) or {}),
        )
        r = evaluar_salida(ep)
        if r["accion"] in ACCIONES_SALIDA_CIERRE:
            via = (r.get("via_ganadora") or {}).get("nombre", "?")
            ventas.append(_log(libro, "vender", ticker, sizing=pos["sizing"], via=via, motivo=r["accion"]))
            del libro.posiciones[ticker]
            vendidos_este_ciclo.add(ticker)
        elif r["accion"] == "recortar":
            nuevo = r["via_ganadora"]["recortar_a"]
            recortes.append(_log(libro, "recortar", ticker, de=pos["sizing"], a=nuevo))
            pos["sizing"] = nuevo
            recortados_este_ciclo.add(ticker)

    # ---- 2. DESPLIEGUE DE CAPITAL — piso 70% / techo 100% (§7, §9) ----
    # El 70% es PISO, no techo: se despliega hacia TOPE_INVERTIDO guiado por mérito.
    # Hard Caps + piso 5% + cubo de fragilidad son el límite real; si no hay
    # candidatas claras el cash residual emerge solo (no se fuerza).
    #
    # 2a. NOMBRES NUEVOS en slots libres, hacia el techo.
    slots_libres = MAX_POSICIONES - len(libro.posiciones)
    capital_disponible = TOPE_INVERTIDO - libro.invertido()
    if slots_libres > 0 and capital_disponible > PISO_POSICION:
        candidatas = [
            e for e in evaluaciones
            if e.get("decision") == "candidata" and e.get("merito") is not None
            and e["ticker"] not in libro.posiciones
            and e["ticker"] not in vendidos_este_ciclo   # no recomprar lo vendido este ciclo.
        ]
        # Conteos vigentes para concentración y cubo (grandfather §6.2: las posiciones
        # ya tenidas CUENTAN pero NO se expulsan; el cap aplica solo a entradas nuevas).
        por_sector: dict = {}
        cubo_residual = 0.0
        for tk, pos in libro.posiciones.items():
            sec_h = (por_ticker.get(tk) or {}).get("_sector") or pos.get("sector")
            if sec_h:
                por_sector[sec_h] = por_sector.get(sec_h, 0) + 1
            if (por_ticker.get(tk) or {}).get("residual_cero") or pos.get("residual_cero"):
                cubo_residual += pos.get("sizing") or 0.0
        if pm_t:
            # PM oficial: cada nombre BENDECIDO se sizea a su TARGET del PM (dentro del hard_cap determinista);
            # NO se normaliza-para-llenar → si el PM no tiene convicción, el cash emerge (disciplina sobre actividad).
            pm_cands = sorted(
                [c for c in candidatas if (pm_t.get(c["ticker"]) or {}).get("size", 0) > 0],
                key=lambda c: -pm_t[c["ticker"]]["size"],
            )
            ranked = [{"_ev": c, "bruto": pm_t[c["ticker"]]["size"], "en_top_n": True}
                      for c in pm_cands[:slots_libres]]
        else:
            # Selector: top-N por mérito, normalizado al capital bruto disponible hasta el techo.
            ranked = normalizar_merito(
                [{"ticker": c["ticker"], "merito": c["merito"], "_ev": c} for c in candidatas],
                n=slots_libres, target=capital_disponible,
            )
        restante = capital_disponible
        for r in ranked:
            if not r["en_top_n"]:
                continue
            ev = r["_ev"]
            s = sizing_final(r["bruto"], ev["hard_cap"])
            if not s["entra"]:
                continue
            if s["sizing"] > restante + 1e-9:
                continue  # no exceder el capital disponible (en modo PM no hay normalización que lo garantice).
            sec = ev.get("_sector")
            if sec and por_sector.get(sec, 0) >= MAX_POR_SUBSECTOR:
                continue  # cap de concentración por sector (no expulsa las vigentes).
            es_rc = bool(ev.get("residual_cero"))
            if es_rc and cubo_residual + s["sizing"] > CUBO_RESIDUAL_CERO:
                continue  # cubo agregado de residual-cero (§11.2): máx 8% en ruptura ~total.
            libro.posiciones[ev["ticker"]] = {
                "sizing": s["sizing"], "precio_entrada": ev.get("_precio"),
                "fecha": _hoy(), "arquetipo": ev.get("arquetipo", {}).get("arquetipo"),
                "merito": ev["merito"], "sector": sec, "residual_cero": es_rc,
            }
            compras.append(_log(libro, "comprar", ev["ticker"], sizing=s["sizing"],
                                merito=ev["merito"], arquetipo=libro.posiciones[ev["ticker"]]["arquetipo"]))
            restante -= s["sizing"]
            if sec:
                por_sector[sec] = por_sector.get(sec, 0) + 1
            if es_rc:
                cubo_residual += s["sizing"]

    # 2b. PIRAMIDAR posiciones vivas hacia su Hard Cap con el capital que falte (§9).
    # Sube posiciones existentes con mérito sano y headroom; NUNCA recorta acá (eso
    # es de las vías de salida). Reparte el capital restante por mérito relativo.
    capital_disponible = TOPE_INVERTIDO - libro.invertido()
    if PERMITIR_PIRAMIDAR and capital_disponible > INCREMENTO_MIN_TOPEO:
        topeables = []
        for ticker, pos in libro.posiciones.items():
            if ticker in recortados_este_ciclo:
                continue  # se recortó este ciclo por una razón; no refillear.
            ev = por_ticker.get(ticker)
            if ev is None or ev.get("merito") is None or ev.get("hard_cap") is None:
                continue  # sin datos frescos → no se topea a ciegas.
            if ev.get("decision") != "candidata":
                continue  # si el gate ya no pasa, no se le agrega capital.
            cap_efectivo = ev["hard_cap"]
            if pm_t:
                tgt = pm_t.get(ticker)
                if not tgt or tgt["size"] <= 0:
                    continue  # PM oficial: no piramidar nombres que el PM no bendijo.
                cap_efectivo = min(ev["hard_cap"], tgt["size"])  # el techo del topeo es el target del PM.
            headroom = cap_efectivo - pos["sizing"]
            if headroom > INCREMENTO_MIN_TOPEO:
                topeables.append({"ticker": ticker, "merito": ev["merito"], "_pos": pos,
                                  "_headroom": headroom, "_precio": ev.get("_precio")})
        ranked = normalizar_merito(
            [{"ticker": t["ticker"], "merito": t["merito"], "_t": t} for t in topeables],
            n=len(topeables), target=capital_disponible,
        )
        for r in ranked:
            if not r["en_top_n"]:
                continue
            t = r["_t"]
            incremento = min(r["bruto"], t["_headroom"])
            if incremento < INCREMENTO_MIN_TOPEO:
                continue
            pos = t["_pos"]
            antes = pos["sizing"]
            # Las acciones del topeo se compran al precio ACTUAL, no al de entrada
            # original → mezclar el precio de entrada (promedio ponderado por shares)
            # para no inflar el P&L del incremento.
            pe_old, precio_now = pos.get("precio_entrada"), t["_precio"]
            if pe_old and precio_now:
                shares_tot = antes / pe_old + incremento / precio_now
                if shares_tot > 0:
                    pos["precio_entrada"] = (antes + incremento) / shares_tot
            pos["sizing"] = antes + incremento
            topeos.append(_log(libro, "topear", t["ticker"], de=antes, a=pos["sizing"],
                               incremento=incremento, merito=t["merito"]))

    # ---- 2c. CHALLENGER — recambio por mérito con histéresis (Borja, §challenger) ----
    # Cierra el hueco de "cartera llena + candidata mejor no entra": la mejor
    # candidata FUERA del libro desafía a la peor titular ELEGIBLE y la desplaza si
    # supera la banda de histéresis (vertical ≥20% o horizontal ≥3 titulares + margen).
    # APAGADO por defecto (CHALLENGER_ACTIVO=False) → no toca el ciclo vivo.
    if CHALLENGER_ACTIVO:
        _correr_challenger(libro, evaluaciones, por_ticker, vendidos_este_ciclo, swaps)

    libro.actualizado = _hoy()
    if persistir:
        guardar_libro(libro)

    invertido_final = libro.invertido()
    return {"ventas": ventas, "recortes": recortes, "compras": compras, "topeos": topeos,
            "swaps": swaps, "invertido": invertido_final, "n_posiciones": len(libro.posiciones),
            "subinvertido": invertido_final < OBJETIVO_INVERTIDO, "libro": libro}


def _correr_challenger(libro: LibroPaper, evaluaciones: list[dict], por_ticker: dict,
                       vendidos_este_ciclo: set, swaps: list) -> None:
    """Pasada de challenger (§challenger). Hasta MAX_SWAPS_POR_CICLO desplazamientos:
    la mejor candidata fuera del libro desafía a la peor titular elegible; el módulo
    `challenger` decide la histéresis, acá se enforcean Gate, límites y sizing."""
    for _ in range(MAX_SWAPS_POR_CICLO):
        # Candidatas FUERA del libro que pasan Gate, ordenadas por mérito.
        fuera = sorted(
            (e for e in evaluaciones
             if e.get("decision") == "candidata" and e.get("merito") is not None
             and e["ticker"] not in libro.posiciones
             and e["ticker"] not in vendidos_este_ciclo),
            key=lambda e: -e["merito"],
        )
        if not fuera:
            return
        retador = fuera[0]

        # Titulares vivos con mérito re-derivado hoy. Sin mérito fresco → no elegible
        # para ser desplazado a ciegas (se lo excluye del set de desafío).
        titulares = []
        for tk, pos in libro.posiciones.items():
            ev = por_ticker.get(tk)
            m = ev.get("merito") if ev else None
            if m is None:
                continue
            sec = (ev.get("_sector") if ev else None) or pos.get("sector")
            titulares.append(Titular(ticker=tk, merito=m, catalizador_dias=None, sector=sec))
        if not titulares:
            return

        d = evaluar_desafio(retador["merito"], titulares)
        if not d["swap"]:
            return  # el mejor retador no supera la histéresis → ninguno lo hará.

        sale = d["sale"]
        pos_sale = libro.posiciones[sale]
        # Límite de sector DESPUÉS del swap (grandfather §6.2: cuentan las vigentes
        # menos la que sale; el cap aplica a la entrante).
        sec_ret = retador.get("_sector")
        if sec_ret:
            cuenta = sum(1 for tk, p in libro.posiciones.items() if tk != sale
                         and ((por_ticker.get(tk) or {}).get("_sector") or p.get("sector")) == sec_ret)
            if cuenta >= MAX_POR_SUBSECTOR:
                return  # el swap violaría el cap de concentración → no se hace.

        # Sizing del retador con el capital que libera la desplazada, recortado a
        # [piso 5%, Hard Cap]. Si no llega al piso, el swap no vale la pena.
        s = sizing_final(pos_sale["sizing"], retador["hard_cap"])
        if not s["entra"]:
            return

        del libro.posiciones[sale]
        vendidos_este_ciclo.add(sale)
        libro.posiciones[retador["ticker"]] = {
            "sizing": s["sizing"], "precio_entrada": retador.get("_precio"),
            "fecha": _hoy(), "arquetipo": retador.get("arquetipo", {}).get("arquetipo"),
            "merito": retador["merito"], "sector": sec_ret,
            "residual_cero": bool(retador.get("residual_cero")),
        }
        swaps.append(_log(libro, "swap", retador["ticker"], sale=sale, entra=retador["ticker"],
                          sizing=s["sizing"], condicion=d["condicion"], merito=retador["merito"],
                          motivo=d["motivo"]))
