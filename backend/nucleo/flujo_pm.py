"""Orquestación del canal de JUICIO (doc 39 §2.6, Bloque 3 — la última milla del PM).

Conecta la superficie DETERMINISTA (candidatos con su cap) con la máquina del PM que ya existe:
    candidato (cap) → Banda(piso, base, techo)          [determinismo pone el techo]
    hoja + mapa + web → PM-LLM → etiqueta discreta        [juicio, dentro de la banda]
    etiqueta + banda → allocator (presupuesto + falsador) [tamaño final DENTRO del techo]
    → libro final + ledger de hit-rate

Invariantes (heredados de juicio.py): el juicio NUNCA supera el techo; VETO/THESIS_BROKEN→0 sin presupuesto;
las promociones consumen presupuesto y exigen falsador escrito. `base = piso` (decisión del operador 2026-09-04):
el determinismo despliega el PISO por defecto y el PM GANA el tramo hasta el techo con convicción (PRIORITY,
presupuestada + falsable). El contexto del PM es SISTEMA + MAPA + WEB (el hype lo contiene el cap, no la censura).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.nucleo import fact_store as FS
from backend.nucleo import juicio, juicio_llm, politica


def banda_desde_candidato(c) -> juicio.Banda:
    """Banda [piso, base, techo] desde el cap determinista del candidato (doc 39 §2.5). techo = cap (INVIOLABLE);
    base = piso = min(CAP_FLOOR, techo) — el determinismo despliega el piso; el PM sube con convicción (opción A)."""
    techo = round(getattr(c, "cap", None) or 0.0, 4)
    base = round(min(politica.CAP_FLOOR_BURN, techo), 4)
    return juicio.Banda(piso=0.0, base=base, techo=techo)


def _red_flags(c, hoja) -> str:
    flags = []
    if not getattr(c, "elegible", True):
        flags.append("veto de supervivencia (no elegible)")
    for f in (getattr(hoja, "flags", None) or []):
        fl = str(f).lower()
        if any(k in fl for k in ("restatement", "material weakness", "going concern", "dilución tóxica", "up-c")):
            flags.append(str(f))
    return "; ".join(flags) if flags else "ninguno"


def _mapa_contexto(session, ticker: str) -> dict:
    """Contexto del MAPA sectorial (nodo/cuello, posición en cadena, estado). Best-effort: el mapa (nx_nodo) puede
    estar vacío hasta que Discovery lo pueble — degrada a {} sin romper. Cuando haya nodos, se enciende solo."""
    if session is None:
        return {}
    try:
        from sqlalchemy import text
        row = session.execute(text(
            "SELECT n.nombre_cuello, en.posicion_cadena, n.estado "
            "FROM nx_empresa_nodo en JOIN nx_nodo n ON n.id = en.nodo_id "
            "WHERE en.ticker = :t LIMIT 1"), {"t": ticker}).fetchone()
        if not row:
            return {}
        return {"mapa_nodo": row[0], "mapa_posicion": row[1], "mapa_estado": row[2]}
    except Exception:  # noqa: BLE001 — el mapa no debe tumbar el juicio
        return {}


def evidencia_desde_candidato(c, hoja, *, session=None) -> dict:
    """Arma la evidencia CRUDA para el PM-LLM (sin nuestro veredicto — anti-anchoring): fundamentals del sistema
    + concentración del fact store + contexto del mapa. La web la trae el propio PM."""
    ticker = getattr(c, "ticker", None) or getattr(hoja, "ticker", "")
    conc = None
    if session is not None:
        try:
            snap = FS.snapshot_vigente(session, ticker) or {}
            f = snap.get("customer_concentration_pct")
            if f is not None and getattr(f, "support_type", None) in ("DIRECT", "DERIVED"):
                conc = FS._dec(f.value)
        except Exception:  # noqa: BLE001
            pass
    ev = {
        "ruteo": getattr(hoja, "estado_ruteo", None) or "s/d",
        "revenue_ttm": getattr(hoja, "revenue_ttm", None),
        "gross_margin": getattr(hoja, "gross_margin", None),
        "g_D": getattr(hoja, "g_D_reverse", None),
        "owner_fcf": getattr(hoja, "owner_fcf", None),
        "sbc_rev": getattr(hoja, "sbc_over_revenue", None),
        "dilucion": getattr(hoja, "shares_growth_24m", None),
        "insider": getattr(hoja, "insider_net_usd", None),
        "rpo": getattr(hoja, "revenue_contratado", None),
        "concentracion": conc,
        "demanda_quote": getattr(hoja, "demanda_quote", None),
        "runway": getattr(hoja, "runway_anos", None),
        "red_flags": _red_flags(c, hoja),
    }
    ev.update(_mapa_contexto(session, ticker))
    return ev


@dataclass
class DecisionPM:
    ticker: str
    etiqueta: str
    banda: juicio.Banda
    size_final: float
    memo: juicio_llm.MemoJuicio
    intervencion: juicio.Intervencion
    motivo: str = ""


@dataclass
class LibroPM:
    decisiones: list = field(default_factory=list)   # [DecisionPM] ordenadas por size_final desc
    promos_usadas: int = 0
    presupuesto: int = 0
    fecha: str = ""

    def sizes(self) -> dict:
        return {d.ticker: d.size_final for d in self.decisiones}


def orquestar_pm(items: list, fecha: str, *, session=None, usar_web: bool = True, max_searches: int = 5,
                 presupuesto: int | None = None, model: str | None = None, dry_run: bool = False,
                 judge=None) -> LibroPM:
    """Corre el PM end-to-end sobre `items` = lista de (candidato, hoja). Devuelve el LibroPM con el tamaño final
    de cada nombre DENTRO de su banda. `judge` inyectable para tests (default: juicio_llm.evaluar_juicio).
    Los CARRIL (a_carril / cap 0) se saltean acá: van por la vía base-rate del carril (doc 29), no por el PM."""
    judge = judge or juicio_llm.evaluar_juicio
    presupuesto = presupuesto if presupuesto is not None else politica.PRESUPUESTO_PROMOCIONES
    bandas: dict = {}
    intervenciones = []
    memos: dict = {}
    for c, hoja in items:
        ticker = getattr(c, "ticker", None) or getattr(hoja, "ticker", "")
        if getattr(hoja, "a_carril_burden", False) or (getattr(c, "cap", 0) or 0) <= 0:
            continue                                  # carril / sin techo → no pasa por el PM (vía aparte)
        bandas[ticker] = banda_desde_candidato(c)
        ev = evidencia_desde_candidato(c, hoja, session=session)
        memo = judge(ticker, ev, model=model, usar_web=usar_web, max_searches=max_searches, dry_run=dry_run)
        memos[ticker] = memo
        intervenciones.append(juicio_llm.a_intervencion(memo, fecha))
    aplicadas = juicio.aplicar_juicio(intervenciones, bandas, presupuesto=presupuesto)
    decisiones = []
    for iv in aplicadas:
        decisiones.append(DecisionPM(
            ticker=iv.ticker, etiqueta=iv.etiqueta, banda=bandas[iv.ticker],
            size_final=iv.size_asignado or 0.0, memo=memos[iv.ticker], intervencion=iv, motivo=iv.motivo))
    decisiones.sort(key=lambda d: -d.size_final)
    promos = sum(1 for d in decisiones if d.etiqueta in juicio.PROMOCIONES
                 and (d.size_final or 0) > (d.banda.base + 1e-9))
    return LibroPM(decisiones=decisiones, promos_usadas=promos, presupuesto=presupuesto, fecha=fecha)
