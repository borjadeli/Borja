"""Discovery (doc 76 §4) — motor de alpha + write-back al mapa. El operador NO elige nombres.

`--explorar` corre el agente discovery (Sonnet+web): propone EMPRESAS que ocupan cuellos del mapa y CUELLOS
nuevos que el mapa no tiene. El filtro NO es el operador nombre-por-nombre: lo validan el MAPA (una empresa
entra al universo sola si encaja en un cuello real) y un AGENTE CURADOR (un cuello entra al mapa solo si él lo
valida). Aguas abajo filtran el embudo + el presupuesto + el PM (advisory). El humano solo ejecuta la orden
final del PM — en ningún lado cura el universo.

Uso:
  .venv/bin/python -m ops.cola_propuestas                         # estado (universo discovery + nodos + pendientes)
  .venv/bin/python -m ops.cola_propuestas --explorar ["foco"]     # corre discovery + curador (GASTA API)
  .venv/bin/python -m ops.cola_propuestas --vencer                # marca vencidas las que pasaron su vigencia
  .venv/bin/python -m ops.cola_propuestas --rechazar TICKER       # override manual (raro; el flujo es automático)
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from backend.agentes.descubrimiento import ColaNodos, ColaPropuestas
from backend.agentes.ips import IPS

_MODELO_DISCOVERY = "claude-sonnet-5-5"       # doc 76 §4: discovery y curador corren en Sonnet + web
_CURSOR_PATH = Path(__file__).resolve().parent.parent / "data" / "discovery_cursor.json"


def _leer_cursor() -> int:
    try:
        return int(json.loads(_CURSOR_PATH.read_text(encoding="utf-8")).get("idx", 0))
    except Exception:  # noqa: BLE001 — sin cursor todavía → empieza en 0
        return 0


def _guardar_cursor(idx: int) -> None:
    _CURSOR_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CURSOR_PATH.write_text(json.dumps({"idx": idx}), encoding="utf-8")


def _universo_actual() -> set[str]:
    from backend.agentes.universo import tickers_universo
    from backend.database import session_scope
    with session_scope() as s:
        return {t.upper() for t in tickers_universo(s)}


def _nodos_mapa() -> list[dict]:
    """Los cuellos reales de la brújula (activos+overlay+watchlist) para el agente: `nombre` canónico (para el
    encaje determinista) + `info` (display con cluster/factor/subnodos/nota). Así discovery no 'inventa': trabaja
    el mapa curado + lo que el sistema ya descubrió."""
    from backend.mapa.brujula import BRUJULA_WATCHLIST, territorios_activos

    def _info(t) -> str:
        extra = []
        if t.factor_macro:
            extra.append(f"factor: {t.factor_macro}")
        if t.subnodos:
            extra.append("subnodos: " + "; ".join(t.subnodos))
        if t.nota:
            extra.append(t.nota)
        return f"[{t.cluster}] {t.nombre}" + (f" ({' · '.join(extra)})" if extra else "")

    terrs = list(territorios_activos()) + list(BRUJULA_WATCHLIST)
    return [{"nombre": t.nombre, "info": _info(t)} for t in terrs]


def _prioridad_cuello(s, tk: str) -> int:
    """0-2 del cuello primario del ticker en nx (confirmado=2 · vigilancia=1 · promesa/otro=0)."""
    from sqlalchemy import select
    from backend.ledger.models import NxEmpresaNodo, NxNodo
    row = s.execute(select(NxNodo.estado_confirmacion).join(NxEmpresaNodo, NxEmpresaNodo.nodo_id == NxNodo.id)
                    .where(NxEmpresaNodo.ticker == tk)).first()
    return {"confirmado": 2, "vigilancia": 1}.get(row[0], 0) if row else 0


def _reemplazo_directo_si_lleno(s, nuevo: str) -> str | None:
    """r6 #2: si el universo está en el tope, ARCHIVA directo al peor no-posición para que entre `nuevo` (nada
    espera afuera). Devuelve el ticker archivado (o None). Posiciones del paper nunca se archivan."""
    from backend.agentes.descubrimiento import elegir_a_archivar
    from backend.agentes.universo import tickers_universo
    from backend.ledger.entidades import Estado, transicionar

    cap = int(IPS.cargar().cfg.get("universo_max", 160))
    actuales = [t.upper() for t in tickers_universo(s)]
    if nuevo.upper() in actuales or len(actuales) < cap:
        return None
    from backend.ledger import core
    paper = abrir_paper()
    try:
        posiciones = {t for t, p in core.proyectar(paper, {})["posiciones"].items() if p.shares > 0}
    finally:
        paper.close()
    dossiers = _cache_dossiers().todos()
    fechas = {tk: e.fecha for tk, e in dossiers.items()}
    # descartado = dossier FAIL o el PM lo mandó a caja/vender; tiene_valor = proxy desde el dossier
    # (satélite/core o convicción ≥0.6); alta_nueva = alta de discovery todavía sin analizar (r7a #2).
    from backend.agentes.ledger_decisiones import LedgerDecisiones
    from backend.ledger.models import NxEmpresa
    ult_dec: dict[str, str] = {}
    for reg in LedgerDecisiones().decisiones():
        ult_dec[reg.ticker.upper()] = reg.accion
    fuente = {e.ticker.upper(): (e.fuente_ingreso or "") for e in s.query(NxEmpresa).all()}

    def _fail(e) -> bool:
        return str(getattr(getattr(e, "verif", None), "veredicto", "") or "").lower() == "fail"

    def _tiene_valor(e) -> bool:
        inv = getattr(e.dossier, "invertibilidad", None)
        clasif = (getattr(inv, "analyst_classification", "") or "").lower()
        return clasif in ("satelite", "core") or (getattr(e.dossier, "conviccion_0_1", 0) or 0) >= 0.6

    universo = []
    for t in actuales:
        tu = t.upper()
        e = dossiers.get(tu)
        descartado = (e is not None and _fail(e)) or ult_dec.get(tu) in ("caja", "vender")
        universo.append({"ticker": t, "cuello_prio": _prioridad_cuello(s, t), "dossier_fecha": fechas.get(t),
                         "analizado": e is not None, "descartado": descartado,
                         "tiene_valor": bool(e is not None and _tiene_valor(e)),
                         "alta_nueva": fuente.get(tu) == "discovery" and tu not in fechas})
    peor = elegir_a_archivar(universo, posiciones=posiciones)
    if peor:
        transicionar(s, ticker=peor, estado_nuevo=Estado.ARCHIVADA, disparado_por="discovery:reemplazo_directo",
                     fecha=date.today(), motivo=f"archivada para dar lugar a {nuevo.upper()} (universo en tope {cap})")
    return peor


def _cache_dossiers():
    from backend.agentes.orquestador import CacheDossiers, _CACHE_PATH
    return CacheDossiers(path=_CACHE_PATH)


def _alta_empresa(ticker: str, propuesta) -> None:
    """Inserta la empresa validada en nx_empresa como Candidata (fuente discovery). Si el universo está lleno,
    archiva directo al peor no-posición (reemplazo directo, r6 #2). `propuesta` es PropuestaEmpresa."""
    from backend.database import session_scope
    from backend.ledger.entidades import crear_candidata
    cuello = propuesta.cuello if hasattr(propuesta, "cuello") else (propuesta or {}).get("cuello", "")
    with session_scope() as s:
        archivado = _reemplazo_directo_si_lleno(s, ticker)
        if archivado:
            print(f"  (universo en tope → archivada {archivado} para dar lugar a {ticker.upper()})")
        crear_candidata(s, ticker=ticker, fecha=date.today(), fuente_ingreso="discovery",
                        motivo=f"discovery: {cuello}".strip())


def _alta_nodo(prop: dict) -> None:
    """Agrega el cuello validado por el curador al overlay del mapa. `prop` es el dict de la PropuestaNodo."""
    from backend.mapa.overlay import agregar_overlay
    agregar_overlay(nombre=prop["nombre"], cluster=prop.get("cluster") or "descubierto",
                    factor_macro=prop.get("factor_macro"), subnodos=prop.get("subnodos") or [],
                    nota=(prop.get("tesis_cuello") or "")[:200])


def _ctx() -> dict:
    """Arma el contexto de una sesión de discovery (agentes + colas + universo + mapa). Una vez por invocación;
    el barrido lo reusa para no re-instanciar en cada nodo."""
    from backend.agentes.base import Agente
    from backend.agentes.descubrimiento import AgenteCurador, AgenteDiscovery
    return {
        "ips": IPS.cargar(), "cola_emp": ColaPropuestas(), "cola_nodos": ColaNodos(),
        "universo": _universo_actual(), "nodos_mapa": _nodos_mapa(),
        "discovery": AgenteDiscovery(Agente("discovery", "discovery_v1", _MODELO_DISCOVERY)),
        "curador": AgenteCurador(Agente("curador", "curador_mapa_v1", _MODELO_DISCOVERY)),
    }


def _verificar_caps(props) -> None:
    """Reemplaza el market_cap del LLM por el DETERMINISTA en USD (yfinance + FX). Cierra el gap del null,
    corrige mal-escalados y hace que el gate de banda funcione con extranjeros. Fail-safe: si no hay dato, deja
    lo que vino (queda 'a verificar')."""
    from backend.services.market_data import market_cap_usd
    for p in props:
        mc = market_cap_usd(p.ticker)
        if mc is not None:
            p.market_cap = mc


def _una_corrida(ctx: dict, foco: str, max_prop: int) -> dict:
    """Una exploración (empresas→universo por encaje, cuellos→mapa por curador). NO imprime; devuelve el resumen.
    El filtro es el mapa + validadores + curador — el humano no decide."""
    from backend.agentes.descubrimiento import encolar_nodos, encolar_propuestas
    from backend.mapa.brujula import nodos_conocidos

    cola_emp = ctx["cola_emp"]
    obs = {v["propuesta"]["ticker"].upper() for v in cola_emp.en_observacion()}
    r = ctx["discovery"].explorar(universo_actual=ctx["universo"], en_observacion=obs,
                                  nodos_mapa=ctx["nodos_mapa"], foco=foco, max_propuestas=max_prop)
    _verificar_caps(r.empresas)         # market cap determinista en USD antes del gate de banda
    costo_cur, res_n = 0.0, []
    if r.cuellos_nuevos:   # cuellos nuevos → curador → overlay (el mapa crece antes de buscarle jugadores)
        res_n, costo_cur = encolar_nodos(ctx["cola_nodos"], r.cuellos_nuevos, ctx["curador"],
                                         nodos_conocidos=nodos_conocidos(), alta_fn=_alta_nodo)
    res = encolar_propuestas(cola_emp, r.empresas, ips_cfg=ctx["ips"].cfg, universo_actual=ctx["universo"],
                             nodos_conocidos=nodos_conocidos(), alta_fn=_alta_empresa)
    for x in res:          # las que entraron: al universo en memoria, para no re-proponerlas en la misma tanda
        if x["estado"] == "aprobada":
            ctx["universo"].add(x["ticker"])
    return {"empresas": res, "cuellos": res_n, "descartes": r.descartes,
            "costo": round(r.meta.cost_usd + costo_cur, 6), "busquedas": r.meta.web_searches}


def _imprimir(s: dict) -> None:
    if s["descartes"]:
        print("  descartadas: " + ", ".join(f"{d['ticker']} ({d['motivo'].split(':')[0]})" for d in s["descartes"]))
    for r in s["cuellos"]:
        print(f"  cuello «{r['nombre']}» → {r['estado']}" + (f" — {r['veredicto']}" if r.get("veredicto") else ""))
    for r in s["empresas"]:
        marca = "→ UNIVERSO" if r["estado"] == "aprobada" else f"→ {r['estado']}"
        print(f"  {r['ticker']} [{r['cuello'][:45]}] {marca}")
    if not (s["empresas"] or s["cuellos"]):
        print("  (nada nuevo)")


def _explorar(foco: str, max_prop: int) -> int:
    ctx = _ctx()
    print(f"explorando (foco: {foco or 'libre'}) — Sonnet+web, {len(ctx['nodos_mapa'])} cuellos del mapa, "
          f"hasta {max_prop} propuestas…")
    s = _una_corrida(ctx, foco, max_prop)
    _imprimir(s)
    print(f"\ncosto ${s['costo']:.4f} · {s['busquedas']} búsquedas")
    return 0


def _barrer(n: int, max_prop: int, tope_usd: float) -> int:
    """Recorre N cuellos del mapa (cursor que avanza entre tandas → en pocas pasadas cubrís los 38), con tope
    de gasto. Esto es discovery 'buceando el mapa' — manual y acotado (el proyecto no cronea gasto LLM todavía)."""
    ctx = _ctx()
    nodos = ctx["nodos_mapa"]
    total = len(nodos)
    idx = _leer_cursor() % total if total else 0
    print(f"barriendo {min(n, total)} cuellos (desde #{idx}/{total}), tope ${tope_usd:.2f}…")
    gastado, hechos = 0.0, 0
    for _ in range(min(n, total)):
        if gastado >= tope_usd:
            print(f"\n(tope de ${tope_usd:.2f} alcanzado — freno antes de gastar más)")
            break
        nodo = nodos[idx]
        print(f"\n[{idx}] {nodo['nombre']}")
        s = _una_corrida(ctx, nodo["nombre"], max_prop)
        _imprimir(s)
        gastado += s["costo"]
        hechos += 1
        idx = (idx + 1) % total
    _guardar_cursor(idx)
    print(f"\nbarrido: {hechos} cuellos · gasto ${gastado:.4f} · próximo cursor #{idx}")
    return 0


def _universo_estado_discovery() -> dict:
    """{ticker: estado} de las empresas de nx_empresa cuya fuente de ingreso es discovery (para el hit-rate)."""
    from backend.database import session_scope
    from backend.ledger.models import NxEmpresa
    with session_scope() as s:
        filas = s.query(NxEmpresa).filter(NxEmpresa.fuente_ingreso == "discovery").all()
        return {e.ticker.upper(): e.estado for e in filas}


def _hitrate() -> int:
    from backend.agentes.discovery_hitrate import embudo_discovery, embudo_nodos
    from backend.agentes.orquestador import _CACHE_PATH, CacheDossiers

    cache = CacheDossiers(path=_CACHE_PATH)

    def _dossier(tk):
        e = cache.ultimo(tk)
        return e.dossier if e else None

    emp = embudo_discovery(propuestas=ColaPropuestas()._estado_actual(),
                           universo_estado=_universo_estado_discovery(), dossier_fn=_dossier)
    nod = embudo_nodos(ColaNodos()._estado_actual())
    f = emp["funnel"]
    print("EMBUDO DE DISCOVERY (empresas)")
    print(f"  propuestas {f['propuestas']} → al universo {f['al_universo']} → analizadas {f['analizadas']} "
          f"→ convicción≥0.6 {f['conviccion_alta']}  (rechazadas {f['rechazadas']})")
    for fila in emp["filas"]:
        conv = f"{fila.conviccion:.2f}" if fila.conviccion is not None else "—"
        clas = fila.clasificacion or "—"
        print(f"  · {fila.ticker:10} [{fila.cuello[:38]:38}] cola={fila.estado_cola:11} "
              f"univ={fila.estado_universo or '—':10} conv={conv:4} {clas}")
    print(f"\nEMBUDO DE CUELLOS (mapa): propuestos {nod['propuestos']} → al mapa {nod['al_mapa']} "
          f"(rechazados {nod['rechazados']})")
    for d in nod["detalle"]:
        print(f"  · {d['nombre']} → {d['estado']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Discovery (doc 76 §4) — motor de alpha + write-back al mapa")
    ap.add_argument("--explorar", nargs="?", const="", metavar="FOCO",
                    help="corre discovery + curador (Sonnet+web, GASTA API): empresas→universo, cuellos→mapa")
    ap.add_argument("--barrer", type=int, metavar="N",
                    help="recorre N cuellos del mapa (el cursor avanza entre tandas; GASTA API, con tope)")
    ap.add_argument("--tope-usd", type=float, default=2.0, help="tope de gasto por tanda de --barrer (default 2)")
    ap.add_argument("--max", type=int, default=6, help="tope de empresas por corrida (default 6; en barrido, menos)")
    ap.add_argument("--hitrate", action="store_true", help="embudo de discovery: propuesto→universo→analizado (sin API)")
    ap.add_argument("--rechazar", metavar="TICKER", help="override manual (el flujo es automático)")
    ap.add_argument("--vencer", action="store_true", help="marca vencidas las que pasaron su vigencia")
    args = ap.parse_args()

    if args.barrer is not None:
        return _barrer(args.barrer, args.max, args.tope_usd)
    if args.explorar is not None:
        return _explorar(args.explorar, args.max)
    if args.hitrate:
        return _hitrate()

    cola = ColaPropuestas()
    if args.rechazar:
        cola.resolver(args.rechazar, "rechazada", nota="override manual del operador")
        print(f"{args.rechazar.upper()} rechazada (override).")
        return 0

    if args.vencer:
        v = cola.vencer_pendientes(date.today())   # los nodos los resuelve el curador en el acto; no quedan colgados
        print(f"empresas vencidas ({len(v)}): {v}" if v else "sin propuestas vencidas.")
        return 0

    # estado: lo que discovery metió al universo + pendientes
    estados = cola._estado_actual()
    universo = sorted(t for t, v in estados.items() if v["estado"] == "aprobada")
    obs = cola.en_observacion()
    nodos_obs = ColaNodos().en_observacion()
    print(f"EMPRESAS QUE DISCOVERY METIÓ AL UNIVERSO ({len(universo)}): {', '.join(universo) or '—'}")
    if obs:
        print(f"\nempresas en observación ({len(obs)}) — no entraron (sin encaje aprobado):")
        for v in obs:
            p = v["propuesta"]
            print(f"  · {p['ticker']} [{p['cuello'][:50]}]  {p['por_que_ahora'][:70]}")
    if nodos_obs:
        print(f"\ncuellos en observación ({len(nodos_obs)}):")
        for v in nodos_obs:
            print(f"  · {v['propuesta']['nombre']}")
    print("\n(--explorar para correr el agente · --vencer · --rechazar TICKER para override manual)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
