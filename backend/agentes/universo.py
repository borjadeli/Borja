"""Candidatos desde el universo (v2 embudo, doc 61 §A) — la parte DETERMINISTA y barata del embudo.

Computa las `SenalesTriage` de cada empresa de `nx_empresa` desde EDGAR (filings nuevos) + precio + el cache
de dossiers + la cartera — SIN LLM. Con esas señales, el Triage (Haiku, ~gratis) filtra TODO el universo y
solo los nombres con algo nuevo (filing/evento/posición/movimiento) pasan al Analista caro. Es el embudo que
"cuida la plata": screenear cientos por casi nada, pagar profundidad solo donde se movió algo.

Los UMBRALES finos (qué % de precio, cuántos días a earnings) viven en la lógica del Triage y se afinan en la
triangulación del doc 61; acá solo se computan las señales crudas, fielmente.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.agentes.embudo import es_evento_fuerte, eventos_materiales_desde, precio_z
from backend.agentes.triage import SenalesTriage
from backend.ledger.models import NxEmpresa

# Estados de nx_empresa que NO entran al embudo (fuera de juego). El resto (Candidata, etc.) se screenea.
_ESTADOS_INACTIVOS = {"descartada", "cerrada", "salida", "vendida"}


def tickers_universo(session: Session) -> list[str]:
    rows = session.execute(select(NxEmpresa.ticker, NxEmpresa.estado)).all()
    return [t for t, e in rows if (e or "").lower() not in _ESTADOS_INACTIVOS]


def asegurar_candidata(session: Session, ticker: str, *, fuente: str = "solicitud") -> bool:
    """Garantiza que `ticker` sea una Candidata en nx_empresa (auditoría 2026-11-27: un alta del operador/PM iba a la
    cola→ficha pero NO al universo → tres registros que no se hablan; hubo fichas huérfanas, p.ej. MRVL/RXRX). El alta
    explícita del operador/PM es un OVERRIDE del screening (el gate de admisión/IPS igual aplica para COMPRAR).
    Idempotente: devuelve True solo si la creó."""
    from datetime import date

    from backend.ledger.entidades import crear_candidata
    tk = ticker.upper()
    if session.get(NxEmpresa, tk) is not None:
        return False
    crear_candidata(session, ticker=tk, fecha=date.today(), fuente_ingreso=fuente)
    return True


def fichas_huerfanas(fichas_tickers, universo_tickers) -> set[str]:
    """Invariante (auditoría): toda ficha debe estar en el universo activo. Devuelve las que NO (huérfanas)."""
    return {t.upper() for t in fichas_tickers} - {t.upper() for t in universo_tickers}


def contexto_mapa(session: Session, ticker: str) -> str:
    """Contexto del CUELLO desde `nx_*` para el Analista (r3 #5): nodo primario (nombre, cluster, factor
    macro, estado de confirmación) + las empresas vinculadas al mismo nodo (dependencias/competencia).
    Texto plano; "" si el nombre no está mapeado. NO inventa — sale del mapa poblado en Fase 2."""
    from backend.ledger.models import NxEmpresaNodo, NxNodo
    tk = ticker.upper()
    fila = session.execute(
        select(NxNodo).join(NxEmpresaNodo, NxEmpresaNodo.nodo_id == NxNodo.id)
        .where(NxEmpresaNodo.ticker == tk)
        .order_by(NxEmpresaNodo.es_primario.desc(), NxNodo.id)).scalars().first()
    if fila is None:
        return ""
    vinculadas = session.execute(
        select(NxEmpresaNodo.ticker).where(NxEmpresaNodo.nodo_id == fila.id,
                                           NxEmpresaNodo.ticker != tk)).scalars().all()
    partes = [f"CUELLO: {fila.nombre}"]
    if fila.cluster:
        partes.append(f"cluster={fila.cluster}")
    if fila.factor_macro:
        partes.append(f"factor macro={fila.factor_macro}")
    partes.append(f"estado del cuello={fila.estado_confirmacion}")
    if vinculadas:
        partes.append(f"empresas en el mismo cuello (competencia/dependencia): {', '.join(vinculadas[:12])}")
    return " · ".join(partes)


# Cursor de monitoreo inicial para empresas NUNCA analizadas (doc 64 §A1 bug): known_at=null NO puede
# significar "todo el historial es nuevo" (dispararía el universo entero). Un nombre nuevo mira solo los
# eventos materiales de los últimos N días, no toda su vida de filings.
VENTANA_MONITOREO_INICIAL_DIAS = 30


def señales_ticker(ticker: str, *, hoy: date, fecha_dossier: date | None, filings: list,
                   precio_hist: list[float] | None, es_posicion: bool,
                   prioridad_cuello: int = 0, mercado_hist: list[float] | None = None,
                   valor_percentil: float | None = None) -> tuple[SenalesTriage, str]:
    """Señales DETERMINISTAS + resumen de eventos materiales nuevos. `filings` = RecentFiling (.tipo/.fecha/
    .items); `precio_hist` = serie de cierres. Usa la whitelist de materialidad del embudo (no todo filing)."""
    dias_dossier = (hoy - fecha_dossier).days if fecha_dossier else None
    # Cursor: si ya hubo dossier, eventos POSTERIORES a él; si nunca se analizó, solo la ventana reciente.
    cursor = fecha_dossier if fecha_dossier is not None else hoy - timedelta(days=VENTANA_MONITOREO_INICIAL_DIAS)
    nuevos = eventos_materiales_desde(filings, desde=cursor)
    # tiene_evento_fuerte (fuerza análisis + saltea caché): un evento fuerte de verdad (red flag/dilución/
    # SC 13D/8-K material) para CUALQUIERA; un 10-Q/10-K de rutina SOLO si es posición (r4 #1a). El resto de
    # los materiales suman a hechos_nuevos (→ el Triage juzga su materialidad), no fuerzan.
    tiene_evento = any(es_evento_fuerte(f) for f in nuevos) or (es_posicion and len(nuevos) > 0)

    periodicos = sorted((f for f in (filings or []) if f.tipo in ("10-Q", "10-K")), key=lambda f: f.fecha)
    dias_a_evento = None
    if periodicos:
        prox = periodicos[-1].fecha.date() + timedelta(days=90)   # aprox por ciclo (solo para DIFERIR, doc 64 A4)
        dias_a_evento = max(0, (prox - hoy).days)

    # precio_vs_tesis_pct = movimiento residual normalizado |z| (doc 64 A1), no el % crudo. El % absoluto
    # va como respaldo en el resumen. El Triage/embudo usa este z (más bajo para posiciones).
    precio_vs = precio_z(precio_hist, mercado_hist=mercado_hist)
    pct_abs = (round(abs(precio_hist[-1] / precio_hist[0] - 1.0) * 100, 1)
               if precio_hist and len(precio_hist) >= 2 and precio_hist[0] else None)

    s = SenalesTriage(dias_desde_dossier=dias_dossier, hechos_nuevos=len(nuevos),
                      dias_a_evento=dias_a_evento, precio_vs_tesis_pct=precio_vs,
                      es_posicion=es_posicion, tiene_evento_fuerte=tiene_evento,
                      prioridad_cuello=prioridad_cuello, valor_percentil_cuello=valor_percentil)
    partes = [f"{f.tipo}{'/' + f.items if getattr(f, 'items', '') else ''} {f.fecha.date()}"
              for f in nuevos[:6]]
    if precio_vs is not None and pct_abs is not None:
        partes.append(f"precio z={precio_vs} ({pct_abs:+.0f}%)")
    return s, " · ".join(partes)


def cuello_primario(session: Session, ticker: str) -> str | None:
    """Nombre del cuello (nodo) PRIMARIO de la empresa en nx_* — la unidad de comparación de la señal de
    valor (r7 §3). None si el nombre no está mapeado."""
    from backend.ledger.models import NxEmpresaNodo, NxNodo
    fila = session.execute(
        select(NxNodo.nombre).join(NxEmpresaNodo, NxEmpresaNodo.nodo_id == NxNodo.id)
        .where(NxEmpresaNodo.ticker == ticker.upper())
        .order_by(NxEmpresaNodo.es_primario.desc(), NxNodo.id)).first()
    return fila[0] if fila else None


def valor_del_universo(tickers: list[str], *, pack_fn, cuello_fn,
                       hoy: date | None = None) -> tuple[dict, dict, dict, dict]:
    """Señal de valor del universo (r7 §3): assembla la lente de valuación por nombre y computa el percentil
    de valor DENTRO de su cuello (lo barato sube en la fila). `pack_fn(tk)->DataPack` (hits de red en real,
    inyectable), `cuello_fn(tk)->str|None`. Best-effort: un nombre que falla queda sin señal. Devuelve
    (percentiles, metricas_por_tk, ratios, cuellos)."""
    from backend.agentes.embudo import percentiles_valor_por_cuello, ratio_valor
    metricas_por_tk: dict[str, dict] = {}
    ratios: dict[str, float | None] = {}
    cuellos: dict[str, str | None] = {}
    for tk in tickers:
        tk = tk.upper()
        cuellos[tk] = cuello_fn(tk)
        try:
            pack = pack_fn(tk)
            m = {p.metric: p.value for p in pack.puntos if p.value is not None}
        except Exception:  # noqa: BLE001 — un nombre sin pack queda sin señal, no tumba la corrida
            m = {}
        metricas_por_tk[tk] = m
        ratios[tk] = ratio_valor(m)
    return percentiles_valor_por_cuello(ratios, cuellos), metricas_por_tk, ratios, cuellos


def candidatos_del_universo(session: Session, *, hoy: date | None = None,
                            fechas_dossier: dict[str, date] | None = None,
                            posiciones: set[str] | None = None,
                            filings_fn=None, precio_hist_fn=None,
                            prioridad_fn=None,
                            valor_percentiles: dict[str, float | None] | None = None,
                            ) -> list[tuple[str, SenalesTriage, str]]:
    """Arma los `candidatos` (ticker, SenalesTriage, resumen) para `orquestador.correr_semana` desde todo el
    universo. Fuentes reales por default (EDGAR + market_data), inyectables para tests. `valor_percentiles`
    (r7 §3): percentil de valor por cuello precomputado (lo barato sube en la fila); None = sin señal."""
    hoy = hoy or date.today()
    fechas_dossier = fechas_dossier or {}
    posiciones = {t.upper() for t in (posiciones or set())}
    valor_percentiles = {k.upper(): v for k, v in (valor_percentiles or {}).items()}
    if filings_fn is None:
        from backend.services.edgar import get_recent_filings
        # Se traen TODOS los tipos candidatos a material; la whitelist fina por ÍTEM la aplica el embudo.
        filings_fn = lambda tk: get_recent_filings(  # noqa: E731
            tk, tipos=("10-K", "10-Q", "10-K/A", "10-Q/A", "8-K", "S-1", "S-3", "424B5", "SC 13D",
                       "NT 10-K", "NT 10-Q", "6-K", "20-F"), dias=120)
    if precio_hist_fn is None:
        from backend.services.market_data import get_price_history
        precio_hist_fn = lambda tk: [d.get("close") for d in (get_price_history(tk, period="3mo") or [])  # noqa: E731
                                     if d.get("close")]
    prioridad_fn = prioridad_fn or (lambda _tk: 0)

    # Serie de mercado (IWM = small caps) UNA vez por corrida, para el residual del precio (β). Si falla → None.
    mercado = None
    try:
        mercado = precio_hist_fn("IWM") or None
    except Exception:  # noqa: BLE001
        mercado = None

    out: list[tuple[str, SenalesTriage, str]] = []
    for tk in tickers_universo(session):
        try:
            ph = precio_hist_fn(tk)
            merc = mercado if (mercado and ph and len(mercado) == len(ph)) else None
            s, resumen = señales_ticker(
                tk, hoy=hoy, fecha_dossier=fechas_dossier.get(tk.upper()),
                filings=filings_fn(tk), precio_hist=ph, mercado_hist=merc,
                es_posicion=tk.upper() in posiciones, prioridad_cuello=prioridad_fn(tk),
                valor_percentil=valor_percentiles.get(tk.upper()))
            out.append((tk.upper(), s, resumen))
        except Exception:  # noqa: BLE001 — un nombre que falla al traer señales no tumba el screening
            continue
    return out
