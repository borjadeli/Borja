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
from datetime import date

from backend.agentes.descubrimiento import ColaNodos, ColaPropuestas
from backend.agentes.ips import IPS

_MODELO_DISCOVERY = "claude-sonnet-5-5"       # doc 76 §4: discovery y curador corren en Sonnet + web


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


def _alta_empresa(ticker: str, propuesta) -> None:
    """Inserta la empresa validada en nx_empresa como Candidata (fuente discovery). `propuesta` es PropuestaEmpresa."""
    from backend.database import session_scope
    from backend.ledger.entidades import crear_candidata
    cuello = propuesta.cuello if hasattr(propuesta, "cuello") else (propuesta or {}).get("cuello", "")
    with session_scope() as s:
        crear_candidata(s, ticker=ticker, fecha=date.today(), fuente_ingreso="discovery",
                        motivo=f"discovery: {cuello}".strip())


def _alta_nodo(prop: dict) -> None:
    """Agrega el cuello validado por el curador al overlay del mapa. `prop` es el dict de la PropuestaNodo."""
    from backend.mapa.overlay import agregar_overlay
    agregar_overlay(nombre=prop["nombre"], cluster=prop.get("cluster") or "descubierto",
                    factor_macro=prop.get("factor_macro"), subnodos=prop.get("subnodos") or [],
                    nota=(prop.get("tesis_cuello") or "")[:200])


def _explorar(foco: str, max_prop: int) -> int:
    from backend.agentes.base import Agente
    from backend.agentes.descubrimiento import (AgenteCurador, AgenteDiscovery,
                                                 encolar_nodos, encolar_propuestas)
    from backend.mapa.brujula import nodos_conocidos

    ips = IPS.cargar()
    cola_emp, cola_nodos = ColaPropuestas(), ColaNodos()
    universo = _universo_actual()
    obs = {v["propuesta"]["ticker"].upper() for v in cola_emp.en_observacion()}
    nodos_mapa = _nodos_mapa()

    discovery = AgenteDiscovery(Agente("discovery", "discovery_v1", _MODELO_DISCOVERY))
    curador = AgenteCurador(Agente("curador", "curador_mapa_v1", _MODELO_DISCOVERY))

    print(f"explorando (foco: {foco or 'libre'}) — Sonnet+web, {len(nodos_mapa)} cuellos del mapa, "
          f"hasta {max_prop} propuestas…")
    props, nodos_nuevos, meta = discovery.explorar(
        universo_actual=universo, en_observacion=obs, nodos_mapa=nodos_mapa, foco=foco, max_propuestas=max_prop)

    # 1) cuellos nuevos → curador → overlay del mapa (el mapa crece antes de buscarle jugadores)
    costo_cur = 0.0
    if nodos_nuevos:
        res_n, costo_cur = encolar_nodos(cola_nodos, nodos_nuevos, curador,
                                         nodos_conocidos=nodos_conocidos(), alta_fn=_alta_nodo)
        print(f"\ncuellos nuevos ({len(res_n)}):")
        for r in res_n:
            print(f"  · {r['nombre']} → {r['estado']}" + (f"  — {r['veredicto']}" if r["veredicto"] else
                                                           (f"  {r['motivos']}" if r["motivos"] else "")))

    # 2) empresas → valida facts + ENCAJE EN EL MAPA → entra sola al universo (el mapa valida, no el humano)
    res = encolar_propuestas(cola_emp, props, ips_cfg=ips.cfg, universo_actual=universo,
                             nodos_conocidos=nodos_conocidos(), alta_fn=_alta_empresa)
    print(f"\nempresas ({len(res)}):")
    for r in res:
        marca = "→ UNIVERSO" if r["estado"] == "aprobada" else f"→ {r['estado']}"
        print(f"  · {r['ticker']} [{r['cuello']}] {marca}" + (f"  ({r['motivos']})" if r["motivos"] else ""))

    print(f"\ncosto total ${meta.cost_usd + costo_cur:.4f} "
          f"(discovery ${meta.cost_usd:.4f}/{meta.web_searches} búsq + curador ${costo_cur:.4f})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Discovery (doc 76 §4) — motor de alpha + write-back al mapa")
    ap.add_argument("--explorar", nargs="?", const="", metavar="FOCO",
                    help="corre discovery + curador (Sonnet+web, GASTA API): empresas→universo, cuellos→mapa")
    ap.add_argument("--max", type=int, default=6, help="tope de empresas del agente (default 6)")
    ap.add_argument("--rechazar", metavar="TICKER", help="override manual (el flujo es automático)")
    ap.add_argument("--vencer", action="store_true", help="marca vencidas las que pasaron su vigencia")
    args = ap.parse_args()

    if args.explorar is not None:
        return _explorar(args.explorar, args.max)

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
