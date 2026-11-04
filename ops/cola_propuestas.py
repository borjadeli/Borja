"""Cola de propuestas de discovery (doc 76 §4) — entrypoint del operador. NO gasta API.

Hoy la cola se alimenta a mano (o, cuando exista, por el agente de discovery). El operador LISTA las
propuestas en observación (ya pasaron los validadores duros) y PROMUEVE las que quiere al universo
investible (nx_empresa como Candidata, fuente_ingreso='discovery'). El filtro no es el operador
nombre-por-nombre: los validadores + el pipeline (embudo→IPS→PM) filtran; el operador solo promueve.

Uso:
  .venv/bin/python -m ops.cola_propuestas                         # lista observación + rechazadas recientes
  .venv/bin/python -m ops.cola_propuestas --explorar ["foco"]     # corre el AGENTE discovery (Sonnet+web, GASTA API)
  .venv/bin/python -m ops.cola_propuestas --proponer TICKER CUELLO "tesis" "por_que_ahora" URL [MARKET_CAP]
  .venv/bin/python -m ops.cola_propuestas --aprobar TICKER        # promueve al universo (nx_empresa)
  .venv/bin/python -m ops.cola_propuestas --rechazar TICKER
  .venv/bin/python -m ops.cola_propuestas --vencer                # marca vencidas las que pasaron su vigencia
"""
from __future__ import annotations

import argparse
from datetime import date

from backend.agentes.descubrimiento import ColaPropuestas, PropuestaEmpresa
from backend.agentes.ips import IPS

_MODELO_DISCOVERY = "claude-sonnet-5-5"       # doc 76 §4: el agente de discovery corre en Sonnet + web


def _universo_actual() -> set[str]:
    from backend.agentes.universo import tickers_universo
    from backend.database import session_scope
    with session_scope() as s:
        return {t.upper() for t in tickers_universo(s)}


def _alta(ticker: str, propuesta: dict) -> None:
    """Inserta la propuesta aprobada en nx_empresa como Candidata (fuente discovery)."""
    from backend.database import session_scope
    from backend.ledger.entidades import crear_candidata
    with session_scope() as s:
        crear_candidata(s, ticker=ticker, fecha=date.today(), fuente_ingreso="discovery",
                        motivo=f"discovery: {propuesta.get('cuello', '')}".strip())


def main() -> int:
    ap = argparse.ArgumentParser(description="Cola de propuestas de discovery (doc 76 §4)")
    ap.add_argument("--explorar", nargs="?", const="", metavar="FOCO",
                    help="corre el agente discovery (Sonnet+web, GASTA API) → encola lo que encuentre")
    ap.add_argument("--max", type=int, default=6, help="tope de propuestas del agente (default 6)")
    ap.add_argument("--proponer", nargs="*", metavar="ARG",
                    help="TICKER CUELLO TESIS POR_QUE_AHORA URL [MARKET_CAP]")
    ap.add_argument("--aprobar", metavar="TICKER", help="promueve una propuesta en observación al universo")
    ap.add_argument("--rechazar", metavar="TICKER")
    ap.add_argument("--vencer", action="store_true", help="marca vencidas las que pasaron su vigencia")
    args = ap.parse_args()

    ips = IPS.cargar()
    cola = ColaPropuestas()

    if args.explorar is not None:
        from backend.agentes.base import Agente
        from backend.agentes.descubrimiento import AgenteDiscovery, encolar_propuestas
        universo = _universo_actual()
        agente = AgenteDiscovery(Agente("discovery", "discovery_v1", _MODELO_DISCOVERY))
        print(f"explorando (foco: {args.explorar or 'libre'}) — Sonnet+web, hasta {args.max} propuestas…")
        props, meta = agente.explorar(universo_actual=universo, foco=args.explorar, max_propuestas=args.max)
        res = encolar_propuestas(cola, props, ips_cfg=ips.cfg, universo_actual=universo)
        print(f"costo ${meta.cost_usd:.4f} · {meta.web_searches} búsquedas · {len(props)} propuestas:")
        for r in res:
            print(f"  · {r['ticker']} → {r['estado']}" + (f"  ({r['motivos']})" if r["motivos"] else ""))
        print("\n(--aprobar TICKER para promover las que estén en observación)")
        return 0

    if args.proponer:
        a = args.proponer
        if len(a) < 5:
            print("faltan args: TICKER CUELLO TESIS POR_QUE_AHORA URL [MARKET_CAP]")
            return 2
        mc = float(a[5]) if len(a) > 5 else None
        p = PropuestaEmpresa(ticker=a[0], cuello=a[1], tesis_corta=a[2], por_que_ahora=a[3],
                             fuentes=[a[4]], market_cap=mc)
        estado, motivos = cola.registrar(p, ips_cfg=ips.cfg, universo_actual=_universo_actual())
        print(f"{a[0].upper()} → {estado}" + (f" · motivos: {motivos}" if motivos else ""))
        return 0

    if args.aprobar:
        cola.promover(args.aprobar, alta_fn=_alta, nota="promovida por el operador")
        print(f"{args.aprobar.upper()} PROMOVIDA → nx_empresa (Candidata, discovery). Entra al universo.")
        return 0

    if args.rechazar:
        cola.resolver(args.rechazar, "rechazada", nota="rechazada por el operador")
        print(f"{args.rechazar.upper()} rechazada.")
        return 0

    if args.vencer:
        v = cola.vencer_pendientes(date.today())
        print(f"vencidas ({len(v)}): {v}" if v else "sin propuestas vencidas.")
        return 0

    obs = cola.en_observacion()
    print(f"EN OBSERVACIÓN ({len(obs)}) — esperan tu promoción:")
    for v in obs:
        p = v["propuesta"]
        print(f"  · {p['ticker']} [{p['cuello']}] mc={p.get('market_cap')}  {p['por_que_ahora'][:80]}")
    print("\n(--aprobar TICKER para promover al universo · --rechazar TICKER · --vencer)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
