"""Interfaz PM-LLM del canal de juicio (doc 39 §2.6/§3.2, Bloque 3 — la última milla).

El determinismo produce banda+techo (juicio.py); ACÁ el PM-LLM lee la evidencia y emite SOLO una ETIQUETA
discreta (nunca un número). El allocator determinista (`juicio.aplicar_juicio`) la traduce a un tamaño DENTRO
de la banda. Esto mete el JUICIO sobre lo cualitativo/forward (calidad de revenue, moat, catalizador, calidad
de management) que el frame determinista NO ve — con guardrails:
  · el LLM emite etiqueta + memo (bull/bear independientes + falsador), NUNCA un número ni un peso.
  · anti-anchoring: NO ve nuestro veredicto/ranking previo (solo la evidencia cruda + el mapa + la web).
  · toda promoción exige un FALSADOR escrito + fecha (lo exige el allocator).
  · temperature=0 (la lección del extractor: 0 es el win de estabilidad).
Contexto del PM (decisión del operador 2026-09-04): SISTEMA (fundamentals) + MAPA (nodo/cuello sectorial) +
WEB SEARCH LIBRE. La web es donde se construye el edge forward; la contención del hype NO es censurar la
entrada sino ESTRUCTURAL — el techo (cap sobre números demostrados) + presupuesto de promociones + falsador +
el ledger de hit-rate que achica el presupuesto si el juicio no le gana al baseline. Para que la web sea
AUDITABLE (fuente puede mutar/desaparecer) el PM DEBE snapshotear en `fuentes` qué leyó y qué hecho sacó.
Auditabilidad = reconstruibilidad (qué se supo, el mecanismo, el falsador, por qué esa etiqueta), NO
reproducibilidad de la opinión (doc 39 §2.6).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.nucleo.juicio import ETIQUETAS, Intervencion
from backend.services import llm

PROMPT_VERSION = "juicio_pm_v1"

_SYSTEM = """Sos un PM de inversiones disciplinado evaluando una small/mid cap de industrias del futuro. Un
sistema DETERMINISTA ya midió los fundamentals duros (valuación, crecimiento demostrado, dilución, supervivencia).
Tu trabajo NO es repetir eso — es aportar el JUICIO sobre lo que los fundamentals NO capturan: calidad y
DURABILIDAD del revenue (recurrente vs cíclico vs one-off), foso competitivo, calidad del management y del cap
table, catalizadores forward creíbles, y opcionalidad no contratada.

REGLAS DURAS:
- NO emitís números, pesos ni tamaños. El sistema determinista dimensiona; vos solo emitís UNA etiqueta.
- Escribí un BULL y un BEAR INDEPENDIENTES (no un promedio; los dos casos honestos por separado) ANTES de decidir.
- Toda PROMOCIÓN (subir tamaño / admitir) exige un FALSADOR: qué hecho concreto, verificable en un documento,
  antes de qué fecha, te haría cambiar de opinión. Sin falsador escrito, no promovés.

WEB SEARCH (tenés la herramienta habilitada — acá se construye el edge forward):
- Usala para HECHOS y desarrollos frescos: contratos/pedidos nuevos, cambios de management/insiders, dinámica
  competitiva, avance de hitos, salud de la cadena de suministro, señales de demanda del cliente final.
- DESCONTÁ agresivamente: price targets sell-side, TAM de la empresa, comunicados promocionales, hype de foros.
  La web es fuente de HECHOS a verificar, NO de opiniones a adoptar. No persigas el consenso: tu valor es el
  juicio INDEPENDIENTE sobre esos hechos.
- AUDITORÍA OBLIGATORIA: en `fuentes` listá cada fuente concreta que usaste (URL o publicación + fecha) y el
  HECHO puntual que sacaste de ella. Si no citás la fuente, el hecho no cuenta.

ETIQUETAS (elegí EXACTAMENTE una):
- PRIORITY_HIGH / PRIORITY_MEDIUM / PRIORITY_LOW: la calidad/durabilidad JUSTIFICA subir el tamaño dentro de la
  banda (HIGH = calidad excepcional + catalizador; requiere falsador).
- ADMIT_PROBE: el determinista lo puso chico/afuera, pero hay mecanismo causal + evidencia real + hito próximo →
  merece una posición probe (requiere falsador).
- PASS: la evidencia cualitativa no cambia lo que el determinista ya decidió (sin cambio).
- HOLD: mantener una posición existente sin cambio.
- THESIS_BROKEN / VETO: hay un problema cualitativo grave (tesis rota / red flag) → reducir a 0.

Devolvé JSON: {"bull": "...", "bear": "...", "falsador": "...", "fecha_falsador": "YYYY-MM-DD o null",
"etiqueta": "UNA_DE_LAS_ETIQUETAS", "razon": "1-2 líneas: por qué esa etiqueta, qué ve el juicio que el
determinista no", "fuentes": [{"fuente": "URL o publicación + fecha", "hecho": "qué sacaste de ahí"}]}."""


@dataclass
class MemoJuicio:
    ticker: str
    etiqueta: str
    bull: str = ""
    bear: str = ""
    falsador: str = ""
    fecha_falsador: str = ""
    razon: str = ""
    fuentes: list = field(default_factory=list)   # [{fuente, hecho}] — snapshot web para auditoría (fuente muta)
    web_searches: int = 0                          # nº de búsquedas usadas (costo/traza)
    valido: bool = True
    flags: list = field(default_factory=list)


def _evidencia_texto(ticker: str, ev: dict) -> str:
    """Arma el bloque de evidencia CRUDA para el PM-LLM. NO incluye nuestro veredicto/estado de decisión
    (anti-anchoring): solo hechos + la naturaleza del negocio."""
    lineas = [f"Empresa: {ticker}", f"Ruteo (naturaleza): {ev.get('ruteo', 's/d')}",
              f"Revenue TTM: {ev.get('revenue_ttm', 's/d')} · gross margin: {ev.get('gross_margin', 's/d')}",
              f"Crecimiento demostrado (g_D): {ev.get('g_D', 's/d')} · owner-FCF: {ev.get('owner_fcf', 's/d')}",
              f"SBC/revenue: {ev.get('sbc_rev', 's/d')} · dilución 3y: {ev.get('dilucion', 's/d')} · "
              f"insider neto 12m: {ev.get('insider', 's/d')}",
              f"RPO/backlog contratado: {ev.get('rpo', 's/d')} · concentración cliente: {ev.get('concentracion', 's/d')}",
              f"Demanda citada: {ev.get('demanda_quote', 's/d')}",
              f"Runway: {ev.get('runway', 's/d')} · red flags: {ev.get('red_flags', 'ninguno')}"]
    # Mapa sectorial (contexto forward/estructural — dominio del juicio): dónde está en la cadena de cuellos.
    if ev.get("mapa_nodo") or ev.get("mapa_posicion") or ev.get("mapa_estado"):
        lineas.append(f"MAPA — cuello: {ev.get('mapa_nodo', 's/d')} · posición en cadena: "
                      f"{ev.get('mapa_posicion', 's/d')} · estado del cuello: {ev.get('mapa_estado', 's/d')}")
        if ev.get("mapa_hechos"):
            lineas.append(f"MAPA — hechos del cuello: {ev.get('mapa_hechos')}")
    lineas.append("\nUsá WEB SEARCH para desarrollos frescos y hechos verificables (contratos, management, "
                  "competencia, hitos). Citá cada fuente en `fuentes`. Descontá price targets / TAM / hype.")
    return "\n".join(lineas)


def evaluar_juicio(ticker: str, evidencia: dict, *, model: str | None = None,
                   usar_web: bool = True, max_searches: int = 5, dry_run: bool = False) -> MemoJuicio:
    """Corre el PM-LLM sobre la evidencia cruda + mapa → MemoJuicio (etiqueta validada). temperature=0. El memo
    (bull/bear/falsador/fuentes) es el registro auditable; la etiqueta alimenta el allocator (`a_intervencion` →
    `juicio.aplicar_juicio`). `usar_web`=True habilita web search server-side (el edge forward; el hype lo contiene
    el cap + presupuesto + ledger, no la censura de la entrada). max_searches capa el costo por nombre."""
    user = _evidencia_texto(ticker, evidencia)
    meta = {"agent": "juicio_pm", "ticker": ticker, "prompt_version": PROMPT_VERSION}
    try:
        if usar_web:
            r = llm.call_llm_json_with_web_search(_SYSTEM, user, model=model, temperature=0.0,
                                                  max_searches=max_searches, dry_run=dry_run, extra_metadata=meta)
        else:
            r = llm.call_llm_json(_SYSTEM, user, model=model, temperature=0.0, dry_run=dry_run, extra_metadata=meta)
    except Exception as e:  # noqa: BLE001 — el juicio no debe tumbar el pipeline; ausencia = PASS
        return MemoJuicio(ticker=ticker, etiqueta="PASS", valido=False, flags=[f"LLM error: {type(e).__name__}"])
    j = r.parsed_json or {}
    web_n = (r.metadata or {}).get("web_searches_usadas", 0) or 0
    fuentes = j.get("fuentes") or []
    etq = (j.get("etiqueta") or "").strip().upper()
    if etq not in ETIQUETAS:                      # etiqueta inválida → PASS conservador (no promueve)
        return MemoJuicio(ticker=ticker, etiqueta="PASS", bull=j.get("bull", ""), bear=j.get("bear", ""),
                          razon=j.get("razon", ""), fuentes=fuentes, web_searches=web_n,
                          valido=False, flags=[f"etiqueta inválida: {etq!r}"])
    return MemoJuicio(ticker=ticker, etiqueta=etq, bull=j.get("bull", ""), bear=j.get("bear", ""),
                      falsador=j.get("falsador", ""), fecha_falsador=(j.get("fecha_falsador") or ""),
                      razon=j.get("razon", ""), fuentes=fuentes, web_searches=web_n)


def a_intervencion(memo: MemoJuicio, fecha: str) -> Intervencion:
    """Convierte el MemoJuicio en la `Intervencion` que consume el allocator (`juicio.aplicar_juicio`). El
    memo_hash es la traza auditable (bull+bear+falsador)."""
    import hashlib
    import json as _json
    blob = f"{memo.bull}|{memo.bear}|{memo.falsador}|{memo.razon}|{_json.dumps(memo.fuentes, sort_keys=True)}"
    memo_hash = hashlib.sha256(blob.encode()).hexdigest()[:12]
    return Intervencion(ticker=memo.ticker, etiqueta=memo.etiqueta, fecha=fecha,
                        falsador=memo.falsador, fecha_falsador=memo.fecha_falsador, memo_hash=memo_hash)
