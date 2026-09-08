"""Resolución atómica de eventos — traspaso §7.1 (convergencia de las 4 IAs).

El hallazgo más fuerte de la triangulación: «los agentes se comunican por estado
duro» nunca definió la frontera atómica de commit ni el orden cuando varios
eventos/vías tocan la misma posición. En single-thread sobre SQLite, escrituras
parciales dejan leer estado a mitad (arquetipo nuevo con HardCap viejo).

resolve_event() re-deriva TODO en UN paso, en orden fijo:
  hechos → arquetipo (+ migración) → CRR/red flags → gate/re-gate →
  bull-bear/HardCap → vías de salida/recorte → journal.

Orden total de precedencia cuando un evento dispara varias vías (lo aplica
salida.evaluar_salida): governance hard → CRR-crítico → vía 1/re-gate → vía 4 →
vía 5. Migración de arquetipo ANTES que CRR y que el stop de progreso (§7.1): CRR
aplica su cap sobre el arquetipo YA nuevo; el contador de ventanas viaja con la
posición y no se reinicia.

Reusa todas las piezas ya cerradas; no agrega motor. SQLite ya alcanza: esto es
la frontera de transacción que faltaba declarar (el caller persiste el estado en
un solo commit tras llamar).
"""
from __future__ import annotations

from backend.nucleo.arquetipo import clasificar_arquetipo
from backend.nucleo.estado import EstadoNucleoPosicion, aplicar_migracion
from backend.nucleo.fragility import calcular_fragility_score, cap_celda, es_residual_cero
from backend.nucleo.flujo import EntradaEmpresa
from backend.nucleo.salida import EstadoPosicion, evaluar_salida
from backend.nucleo.sizing import hard_cap


def dedupe_eventos(eventos: list[dict]) -> list[dict]:
    """Dedupe por (ticker, tipo, fecha_hecho/source) — §7.1. Si el mismo earnings
    llega por EDGAR, RSS y noticia a la vez, se consolida en un evento canónico
    con varias fuentes; NO tres recomendaciones ni tres llamadas al PM."""
    canonicos: dict[tuple, dict] = {}
    for ev in eventos:
        clave = (str(ev.get("ticker", "")).upper(), ev.get("tipo"),
                 ev.get("fecha_hecho") or ev.get("source_id"))
        if clave not in canonicos:
            canonicos[clave] = {**ev, "fuentes": list(ev.get("fuentes") or ([ev["fuente"]] if ev.get("fuente") else []))}
        else:
            f = ev.get("fuente")
            if f and f not in canonicos[clave]["fuentes"]:
                canonicos[clave]["fuentes"].append(f)
    return list(canonicos.values())


def resolve_event(entrada: EntradaEmpresa, estado: EstadoNucleoPosicion,
                  eventos: dict | None = None) -> dict:
    """Re-deriva una posición viva ante un evento, atómicamente y en orden fijo.

    MUTA `estado` (arquetipo/fragility/hardcap; migración no reinicia contadores);
    el caller persiste en UN commit. Devuelve el registro para el journal.

    eventos: hechos EVENT-DRIVEN no contenidos en los hechos estáticos
    (trigger_disparado, crr_critico, hard_governance_events, soft_red_flags,
    peso_vivo, bull_bear_anclado_en_hechos_ocurridos).
    """
    eventos = eventos or {}
    registro: dict = {"ticker": entrada.ticker}

    # 1. Hechos → arquetipo.
    arq = clasificar_arquetipo(entrada.hechos_arquetipo)
    arquetipo = arq["arquetipo"]
    registro["arquetipo"] = arquetipo

    # 5b. Fragility + HardCap re-derivados (se necesitan para la migración y la vía 5).
    frag = calcular_fragility_score(entrada.hechos_fragility)["score"]
    hc = hard_cap(cap_celda(arquetipo, frag), entrada.cap_crr)

    # 2. Migración de arquetipo ANTES que CRR/stop (§7.1). Solo si cambió por hecho
    #    contable y NO disparó trigger (si disparó, es vía 1, no migración).
    trigger_disparado = bool(eventos.get("trigger_disparado"))
    migracion = None
    if (estado.arquetipo and arquetipo != estado.arquetipo and not trigger_disparado):
        migracion = aplicar_migracion(estado, arquetipo, frag, hc, peso_vivo=eventos.get("peso_vivo"))
    else:
        estado.arquetipo = arquetipo
        estado.fragility_score = frag
        estado.hardcap_vigente = hc
    registro["migracion"] = migracion
    registro["fragility"] = frag
    registro["hard_cap"] = hc
    registro["residual_cero"] = es_residual_cero(arquetipo, frag)

    # 3-6. CRR/governance + gate/re-gate + bull-bear + vías de salida, con precedencia
    #      total (governance → CRR → vía1 → vía4 → vía5) dentro de evaluar_salida.
    ep = EstadoPosicion(
        ticker=entrada.ticker,
        arquetipo=arquetipo,
        trigger_disparado=trigger_disparado,
        trigger_vencido_sin_catalizador=bool(eventos.get("trigger_vencido_sin_catalizador")),
        segunda_corrida_de_fecha=(estado.corridas_via1 >= 2) or bool(eventos.get("segunda_corrida_de_fecha")),
        earnings_sin_hecho_a_favor=eventos.get("earnings_sin_hecho_a_favor", estado.ventanas_sin_progreso),
        crr_critico=bool(eventos.get("crr_critico")),
        hard_governance_events=list(eventos.get("hard_governance_events") or []),
        soft_red_flags=int(eventos.get("soft_red_flags") or 0),
        bull=entrada.bull, precio=entrada.precio, bear=entrada.bear,
        bull_bear_anclado_en_hechos_ocurridos=bool(eventos.get("bull_bear_anclado_en_hechos_ocurridos")),
        peso_vivo=eventos.get("peso_vivo"),
        hardcap_vigente=hc,
        reentradas_usadas=estado.reentradas_usadas,
    )
    decision = evaluar_salida(ep)
    registro["decision"] = decision

    # 7. Journal (el caller lo persiste junto con el estado, en un commit).
    return registro
