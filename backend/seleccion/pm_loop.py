"""Orquestador del PM (Etapa 6): propone → valida → re-propone → mix aprobado.

El PM-LLM decide **inclusión + peso dentro de [piso, hard cap]**; el validador
determinista (rechaza-e-informa, Art. 4.4) es la última palabra. Loop acotado: si la
propuesta viola un límite, los errores vuelven al PM y re-propone.

`proponer` es INYECTABLE → la orquestación se testea sin API. El LLM real es el edge
(`crear_proponente_llm`), que reusa el servicio de LLM existente.
"""
from __future__ import annotations

from typing import Callable

from backend.nucleo.constantes import PISO_POSICION
from backend.seleccion.validador import Candidata, LineaPropuesta, validar_propuesta

# (candidatas, errores_previos) -> list[LineaPropuesta]  (solo las líneas a INCLUIR)
Proponente = Callable[[list, list], list]


def correr_pm(candidatas: list[Candidata], *, cash_objetivo: float, proponer: Proponente,
              piso: float = PISO_POSICION, max_posiciones: int = 10,
              max_intentos: int = 3) -> dict:
    """Corre el loop del PM. Devuelve {ok, mix, intentos, validacion, historial}.
    `mix` es dict ticker->peso (listo para desplegar) o None si no logró una propuesta
    válida en max_intentos."""
    errores_previos: list[str] = []
    historial: list[dict] = []
    r = {"ok": False, "errores": ["sin intento"]}

    for intento in range(1, max_intentos + 1):
        lineas = proponer(candidatas, errores_previos)
        r = validar_propuesta(lineas, candidatas, cash_objetivo=cash_objetivo, piso=piso,
                              max_posiciones=max_posiciones)
        historial.append({"intento": intento, "n_lineas": len(lineas),
                          "ok": r["ok"], "errores": r["errores"]})
        if r["ok"]:
            mix = {l.ticker.upper(): l.peso for l in lineas}
            return {"ok": True, "mix": mix, "intentos": intento,
                    "validacion": r, "historial": historial}
        errores_previos = r["errores"]

    return {"ok": False, "mix": None, "intentos": max_intentos,
            "validacion": r, "historial": historial}


# --------------------------- Edge LLM (no testeado en vivo acá) ---------------------------

_SYSTEM = """Sos un Portfolio Manager worldclass de small/mid caps de industrias del \
futuro (cuellos de botella: AI infra, energía/nuclear, defensa, minerales críticos, \
fotónica, robótica). Filosofía: DISCIPLINA SOBRE ACTIVIDAD — preferís cash y slots \
vacíos a forzar entradas mediocres.

Recibís empresas ELEGIBLES ya filtradas. De cada una: arquetipo, mérito (calidad × \
asimetría), hard_cap (peso MÁXIMO permitido por su riesgo — es un TECHO, NO un objetivo), \
sector, factores macro, hechos citados.

TU TRABAJO: construir la MEJOR cartera posible — elegir cuáles incluir y con qué peso.

CRITERIO (juicio de PM, no ranking):
- Construí la CARTERA como conjunto, no nombre por nombre. Máximo 10 posiciones.
- Concentrá en las mejores asimetrías. NO diversifiques por diversificar.
- Sé AGRESIVO en las de ALTA CONVICCIÓN (mérito alto + fragilidad baja): acercate a su \
hard_cap. En las de menor convicción o más frágiles: bajá el peso bien por debajo del techo.
- NO apiles la misma apuesta económica (mismo factor macro / driver) aunque sean tickers \
distintos.
- El macro/sector es viento a favor o en contra: úsalo para priorizar y desempatar, NUNCA \
para romper un límite.
- Costo de oportunidad: un nombre marginalmente mejor NO justifica rotar. Ante la duda, mantené.
- Si NADA te convence lo suficiente, quedate en CASH (proponé pocas posiciones, o ninguna). \
El cash es una decisión válida, no un fracaso.

LÍMITES DUROS (un validador los chequea; respetalos para no perder intentos):
- Solo tickers de la lista de elegibles. NUNCA inventes uno.
- Peso de cada posición en [piso, hard_cap].
- Máx 10 posiciones; máx por sector; cap por factor macro.
- El cash lo fija el operador: invertís el resto, SALVO que no haya con qué (dejás más cash).

EXPLICÁ: por cada incluida, la tesis + driver; por cada excluida, su driver y por qué queda \
afuera — para que el operador pueda intervenir.

Devolvé SOLO JSON:
{"mix":[{"ticker":"XXX","incluir":true,"peso":0.NN,"motivo":"..."}], \
"excluidas":[{"ticker":"YYY","driver":"...","motivo":"..."}]}

Si te paso errores de una propuesta anterior, corregilos exactamente."""


def _fmt_candidata(c: Candidata, ficha: dict) -> str:
    return (f"- {c.ticker} [{ficha.get('arquetipo', '?')}] mérito={ficha.get('merito', '?')} "
            f"hard_cap={c.hard_cap:.0%} sector={c.sector or 'N/D'} "
            f"factores={','.join(c.factores) or '—'} | {ficha.get('resumen', '')}")


def _construir_user(candidatas: list[Candidata], fichas: dict, contexto: str,
                    piso: float, cash_objetivo: float, errores_previos: list[str]) -> str:
    cuerpo = "\n".join(_fmt_candidata(c, fichas.get(c.ticker.upper(), {})) for c in candidatas)
    partes = [
        f"=== CONTEXTO (macro/sectores) ===\n{contexto or '—'}",
        f"=== REGLAS ===\npiso por posición: {piso:.0%} · cash objetivo: {cash_objetivo:.0%}",
        f"=== CANDIDATAS ELEGIBLES ===\n{cuerpo}",
    ]
    if errores_previos:
        partes.append("=== TU PROPUESTA ANTERIOR FUE RECHAZADA. CORREGÍ ===\n- "
                      + "\n- ".join(errores_previos))
    partes.append("Devolvé el JSON pedido.")
    return "\n\n".join(partes)


def _ficha_ctx(session, ticker: str) -> dict:
    """Contexto de la ficha para el prompt (arquetipo, mérito, escenarios/fragilidad)."""
    from sqlalchemy import select

    from backend.ledger.models import NxFichaVersion
    fv = session.execute(
        select(NxFichaVersion).where(NxFichaVersion.ticker == ticker.upper())
        .order_by(NxFichaVersion.version.desc())
    ).scalars().first()
    if fv is None:
        return {}
    return {"arquetipo": fv.arquetipo,
            "merito": round(fv.merito, 2) if fv.merito is not None else None,
            "resumen": f"asimetría={round(fv.asimetria, 2) if fv.asimetria else '?'} "
                       f"bull={fv.bull} bear={fv.bear} fragilidad={fv.fragility_score}"}


def crear_proponente_llm(session, *, contexto: str = "", piso: float = PISO_POSICION,
                         cash_objetivo: float = 0.0, model: str | None = None,
                         dry_run: bool = False) -> Proponente:
    """Devuelve un `proponer` que llama al LLM real, armando el contexto desde las fichas
    del ledger. Solo devuelve las líneas incluir=True; el validador rechaza lo que viole
    un límite."""
    from backend.services.llm import call_llm_json

    def _proponer(candidatas: list[Candidata], errores_previos: list[str]) -> list[LineaPropuesta]:
        fichas = {c.ticker.upper(): _ficha_ctx(session, c.ticker) for c in candidatas}
        user = _construir_user(candidatas, fichas, contexto, piso, cash_objetivo, errores_previos)
        res = call_llm_json(system_prompt=_SYSTEM, user_message=user, model=model,
                            max_tokens=4096, dry_run=dry_run,
                            extra_metadata={"agent": "pm_loop"})
        data = res.parsed_json if isinstance(res.parsed_json, dict) else {}
        _proponer.ultima = data          # razonamiento crudo (mix + excluidas) para inspección
        lineas = []
        for l in (data.get("mix") or []):
            if l.get("incluir"):
                try:
                    lineas.append(LineaPropuesta(str(l.get("ticker", "")).upper(),
                                                 float(l.get("peso") or 0.0)))
                except (TypeError, ValueError):
                    continue
        return lineas

    _proponer.ultima = None
    return _proponer
