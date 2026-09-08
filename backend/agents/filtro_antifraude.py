"""Filtro anti-fraude pre-scoring (v4.2 sec 7).

Ejecuta 7 chequeos determinísticos antes del scoring del Analista. Bloquea
empresas que muestran señales tempranas de fraude o capital raise riesgoso.

Filosofía: NO mueve el estado automáticamente. Detecta violaciones y las
escribe en el campo `filtro_antifraude_violaciones` (JSON). El humano decide
si elimina, mueve a Bucket o ignora con justificación.

Las 7 condiciones según el doc:
  1. <2 años desde IPO/reverse merger
  2. >1 cambio de auditor en 5 años (no implementado en Fase 1 — flag manual)
  3. >3 S-1/S-3 en 24 meses
  4. Dilución >40% en 3y sin crecimiento revenue
  5. Class actions abiertas (no implementado en Fase 1 — flag manual)
  6. Going concern en 10-K → cableado en CRR (traspaso Fase 0): se detecta en
     edgar.detect_going_concern y fuerza CRR-crítico. Ya no es flag manual.
  7. ATM activo >15% del float (proxy: 424B + shelf en 6m)
"""
from __future__ import annotations

from datetime import timedelta

from backend.database import session_scope
from backend.models import EstadoFicha, Ficha
from backend.services import edgar
from backend.utils import get_logger, utcnow

log = get_logger(__name__)


ESTADOS_A_EVALUAR = [
    EstadoFicha.PORTFOLIO_ACTIVO.value,
    EstadoFicha.WL_PRIORITARIA.value,
    EstadoFicha.WL_ACTIVA.value,
    EstadoFicha.WL_SEGUIMIENTO.value,
    EstadoFicha.UNIVERSO.value,
    EstadoFicha.CANDIDATA.value,
    EstadoFicha.BUCKET_EXPLORATORIO.value,
]


def evaluar_filtro_antifraude(ticker: str) -> dict:
    """Ejecuta los chequeos automatizables y devuelve dict con violaciones.

    Output:
      {
        "ticker": str,
        "violaciones": list[str],     # condiciones disparadas
        "advertencias": list[str],    # cosas a verificar a mano (auditor, class actions, etc.)
        "datos": dict,                # números crudos
      }
    """
    violaciones: list[str] = []
    advertencias: list[str] = []
    datos: dict = {}
    now = utcnow()

    # Cond 1 — IPO < 2 años
    ipo = edgar.get_ipo_date(ticker)
    if ipo:
        dias_ipo = (now - ipo).days
        datos["dias_desde_primer_filing"] = dias_ipo
        if dias_ipo < 2 * 365:
            violaciones.append(
                f"Primer filing hace {dias_ipo} días (<2 años) — proxy IPO/reverse merger reciente"
            )

    # Cond 3 — >3 S-1/S-3 en 24m
    shelf = edgar.count_capital_raise_filings(ticker, dias=730)
    datos["shelf_24m"] = shelf.get("shelf_total")
    if shelf.get("shelf_total", 0) > 3:
        violaciones.append(f"{shelf['shelf_total']} shelf registrations en 24m (>3)")

    # Cond 4 — dilución >40% en 3y sin crecimiento
    fin = edgar.get_financials_quarterly(ticker, periodos=8)
    dilution = edgar.get_dilution_pct_3y(ticker)
    growth = fin.organic_growth_yoy
    datos["dilucion_3y_pct"] = dilution
    datos["revenue_growth_yoy"] = growth
    if dilution is not None and dilution > 40.0:
        sin_growth = growth is None or growth < 10.0
        if sin_growth:
            violaciones.append(
                f"Dilución 3y {dilution:.1f}% (>40%) sin crecimiento revenue ({growth or 'N/D'}%)"
            )

    # Cond 7 — ATM activo (proxy: 424B en 6m post shelf)
    prospectus_24m = shelf.get("prospectus_total", 0)
    datos["prospectus_24m"] = prospectus_24m
    if prospectus_24m >= 2:
        # Más de 2 prospectus supplements en 24m = oferta secundaria activa
        advertencias.append(
            f"{prospectus_24m} prospectus supplements (424B) en 24m — verificar ATM% del float"
        )

    # Cond 2, 5 — no automatizables en Fase 1. Cond 6 (going concern) ya se
    # cablea en CRR (traspaso Fase 0); acá solo se deja la nota de respaldo.
    advertencias.extend([
        "Cambio de auditor en 5 años (cond 2): verificar 8-K item 4.01 manualmente",
        "Class actions abiertas (cond 5): verificar Stanford SCAC manualmente",
    ])

    return {
        "ticker": ticker.upper(),
        "violaciones": violaciones,
        "advertencias": advertencias,
        "datos": datos,
        "evaluado_en": now.isoformat(),
    }


def correr_filtro_antifraude_universo() -> dict:
    """Corre el filtro sobre todas las fichas activas y persiste en Ficha.

    No mueve estados — solo flagea. El humano decide qué hacer con cada uno.
    """
    with session_scope() as s:
        tickers = [
            f.ticker for f in s.query(Ficha)
            .filter(Ficha.estado.in_(ESTADOS_A_EVALUAR)).all()
        ]
    log.info("filtro_antifraude — arrancando — %d tickers", len(tickers))

    resumen = {"evaluados": 0, "con_violaciones": [], "errores": 0, "detalle": []}
    now = utcnow()

    for t in tickers:
        try:
            res = evaluar_filtro_antifraude(t)
        except Exception as e:  # noqa: BLE001
            log.warning("filtro_antifraude — %s falló: %s", t, e)
            resumen["errores"] += 1
            continue

        with session_scope() as s:
            f = s.query(Ficha).filter_by(ticker=t).first()
            if f is None:
                continue
            f.filtro_antifraude_violaciones = (
                " | ".join(res["violaciones"]) if res["violaciones"] else None
            )
            f.filtro_antifraude_at = now

        resumen["evaluados"] += 1
        if res["violaciones"]:
            resumen["con_violaciones"].append(t)
        resumen["detalle"].append(res)

    log.info(
        "filtro_antifraude — completado — evaluados=%d con_violaciones=%d",
        resumen["evaluados"], len(resumen["con_violaciones"]),
    )
    return resumen
