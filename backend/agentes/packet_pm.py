"""PM Decision Packet (r9, doc 80 §G · P2) — lo que el PM-LLM recibe en cada sesión, SIN web.

Determinista: arma —con un CORTE DE DATOS CONGELADO— la cartera + una ficha de 1 página por tenencia + las
oportunidades (banca en zona + top score) + las alertas (recorte/rotación/deterioro/falsador) + las decisiones
previas (con el POR QUÉ) + el presupuesto. Así el PM tiene memoria entre decisiones y comparación entre
alternativas sin re-correr dossiers ni acceder a internet.

El packet NO decide: es el contexto. El PM sizea sobre él (doc 80 §H). Puro y testeable (inyectable)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date


@dataclass
class ResumenPosicion:
    """Una página por tenencia/banca: tesis + valuación viva + riesgo dominante + estado de falsador + cambio."""
    ticker: str
    peso: float
    nivel: str
    estado_tesis: str                   # VIGENTE | EN_REVISION | VENCIDA | ROTA
    zona: str | None                    # COMPRA | MANTENER | RECORTE | SALIDA
    retorno_esperado: float | None
    perdida_bear: float | None
    exige_el_precio: str | None
    precio: float | None
    gatillo_compra: float | None
    gatillo_recorte: float | None
    falsador: str | None = None
    falsador_estado: str | None = None
    tesis: str | None = None


@dataclass
class PaquetePM:
    as_of: str
    data_cutoff: str                    # corte CONGELADO (una sola foto por sesión)
    equity: float
    caja_pct: float
    etf_pct: float
    posiciones: list[ResumenPosicion] = field(default_factory=list)
    concentraciones: dict = field(default_factory=dict)        # eje → {clave: peso}
    banca_en_zona: list[ResumenPosicion] = field(default_factory=list)   # candidatas a ENTRADA (ficha en COMPRA)
    oportunidades_top: list[dict] = field(default_factory=list)          # top score ficha-less (nuevas)
    alertas: list[dict] = field(default_factory=list)                    # recorte/rotación/deterioro/falsador
    decisiones_previas: list[dict] = field(default_factory=list)         # última acción del PM + por qué
    presupuesto: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _resumen_de_ficha(f, *, peso: float) -> ResumenPosicion:
    p = f.puente
    g = f.gatillos
    lat = f.latido
    fals = (f.falsadores[0] if f.falsadores else {}) or {}
    return ResumenPosicion(
        ticker=f.ticker, peso=round(peso, 4), nivel=f.nivel, estado_tesis=f.estado,
        zona=(lat.zona if lat else None),
        retorno_esperado=(p.retorno_esperado if p else None), perdida_bear=(p.perdida_bear if p else None),
        exige_el_precio=(p.exige_el_precio if p else None), precio=(p.precio if p else None),
        gatillo_compra=(g.compra if g else None), gatillo_recorte=(g.recorte if g else None),
        falsador=fals.get("afirmacion"), falsador_estado=fals.get("estado"),
        tesis=(f.tesis_resumen or "")[:240])


def construir_packet(*, fichas: dict, posiciones: dict[str, float], caja_pct: float, equity: float,
                     scores=None, memo_macro: str = "", decisiones_previas: list[dict] | None = None,
                     presupuesto: dict | None = None, concentraciones: dict | None = None,
                     tickers_etf: set[str] | None = None, as_of: date | None = None,
                     data_cutoff: str | None = None) -> PaquetePM:
    """Arma el packet. `fichas`: {ticker: Ficha}. `posiciones`: {ticker: peso} del ledger. `scores`: FilaScore
    de P1 (oportunidades ficha-less). TODO con un solo corte (`data_cutoff`)."""
    as_of = as_of or date.today()
    etf = {t.upper() for t in (tickers_etf or set())}
    pos_u = {t.upper(): w for t, w in posiciones.items()}
    etf_pct = round(sum(w for t, w in pos_u.items() if t in etf), 4)

    pack = PaquetePM(as_of=as_of.isoformat(), data_cutoff=(data_cutoff or as_of.isoformat()),
                     equity=round(equity, 2), caja_pct=round(caja_pct, 4), etf_pct=etf_pct,
                     concentraciones=concentraciones or {},
                     decisiones_previas=list(decisiones_previas or []), presupuesto=presupuesto or {})

    # 1 página por TENENCIA (con ficha) + alertas de posición.
    for tk, w in sorted(pos_u.items(), key=lambda x: -x[1]):
        if tk in etf:
            continue
        f = fichas.get(tk)
        if f is None:
            pack.alertas.append({"ticker": tk, "tipo": "sin_ficha", "detalle": "tenencia sin ficha viva"})
            continue
        r = _resumen_de_ficha(f, peso=w)
        pack.posiciones.append(r)
        if r.zona in ("RECORTE", "SALIDA"):
            pack.alertas.append({"ticker": tk, "tipo": "recorte", "zona": r.zona,
                                 "detalle": f"{tk} en zona {r.zona} (retorno esperado {r.retorno_esperado})"})
        if f.estado in ("EN_REVISION", "VENCIDA", "ROTA"):
            pack.alertas.append({"ticker": tk, "tipo": "tesis", "detalle": f"{tk} tesis {f.estado}"})

    # BANCA en zona de compra (candidatas a ENTRADA) — fichas vigentes, no tenencias, en COMPRA.
    for tk, f in fichas.items():
        tku = tk.upper()
        if tku in pos_u or f.estado != "VIGENTE":
            continue
        if f.latido and f.latido.zona == "COMPRA":
            pack.banca_en_zona.append(_resumen_de_ficha(f, peso=0.0))
            pack.alertas.append({"ticker": tku, "tipo": "entrada", "detalle": f"{tku} ficha en zona COMPRA"})

    # Oportunidades NUEVAS (ficha-less) — top del score de P1.
    con_ficha = {t.upper() for t in fichas}
    for fs in (scores or []):
        if fs.score is None or fs.ticker.upper() in con_ficha or fs.ticker.upper() in pos_u:
            continue
        pack.oportunidades_top.append({"ticker": fs.ticker.upper(), "score": fs.score, "cluster": fs.cluster,
                                       "v": fs.v, "m": fs.m, "c": fs.c, "a": fs.a})
        if len(pack.oportunidades_top) >= 10:
            break
    return pack


def render_packet(pack: PaquetePM) -> str:
    """Texto compacto del packet para el prompt del PM (sin volcar dossiers crudos)."""
    L = [f"PAQUETE DE DECISIÓN — corte {pack.data_cutoff} (una sola foto)",
         f"Equity ${pack.equity:,.0f} · caja {pack.caja_pct:.0%} · ETFs estacionamiento {pack.etf_pct:.0%}", ""]
    L.append("TENENCIAS (1 línea c/u — tesis / zona / retorno esperado / pérdida bear / falsador):")
    for r in pack.posiciones:
        L.append(f"- {r.ticker} {r.peso:.1%} [{r.estado_tesis}/{r.zona}] ret_esp "
                 f"{r.retorno_esperado if r.retorno_esperado is not None else '—'} · bear "
                 f"{r.perdida_bear if r.perdida_bear is not None else '—'} · {r.exige_el_precio or ''}"
                 + (f" · falsador: {r.falsador}" if r.falsador else ""))
    if pack.banca_en_zona:
        L.append("\nBANCA EN ZONA DE COMPRA (candidatas a entrada, tesis vigente):")
        for r in pack.banca_en_zona:
            L.append(f"- {r.ticker} precio {r.precio} ≤ compra {r.gatillo_compra} · ret_esp {r.retorno_esperado}")
    if pack.oportunidades_top:
        L.append("\nOPORTUNIDADES NUEVAS (top score, sin ficha — necesitan deep si competirían por capital):")
        for o in pack.oportunidades_top[:8]:
            L.append(f"- {o['ticker']} score {o['score']} [{o['cluster']}]")
    if pack.alertas:
        L.append("\nALERTAS:")
        for a in pack.alertas:
            L.append(f"- [{a['tipo']}] {a.get('detalle', a['ticker'])}")
    if pack.decisiones_previas:
        L.append("\nDECISIONES PREVIAS (última por nombre — por qué + qué revisar):")
        for d in pack.decisiones_previas[:12]:
            L.append(f"- {d.get('ticker')}: {d.get('accion')} ({d.get('tesis', '')[:80]})")
    if pack.presupuesto:
        L.append(f"\nPresupuesto: {pack.presupuesto}")
    return "\n".join(L)
