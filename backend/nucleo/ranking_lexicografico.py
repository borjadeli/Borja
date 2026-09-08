"""Ranking lexicográfico (doc 27 §10 / doc 34 §6) — el reemplazo de `merito = Quality × Asimetría`.

Orden ESTRICTO por prioridad, SIN score cardinal (doc 33: "no hay score cardinal 0-10 que mezcle
todo = narrativa encubierta"). Cada clave desempata a la anterior:

    gate → tier de capital → cobertura → asimetría operable (cap 5×) → catalizador → liquidez

Es ORDINAL (quién va antes), no un número que se multiplica y se normaliza a capital. El sizing es
aparte (min de caps), no proporcional al ranking.

SHADOW (doc 34 §4 paso 2): este módulo NO reemplaza todavía a `selector`/`flujo` (que corren el
paper con el merito viejo). Se construye y testea en aislamiento; el cutover se hace cuando la
superficie nueva esté verde en shadow (comparada contra la vieja). NO tocar el paper vivo aún.
"""
from __future__ import annotations

from dataclasses import dataclass

_TIER_ORD = {"A": 0, "B": 1, "C": 2}
ASIMETRIA_CAP = 5.0   # doc 27 §10: la asimetría operable se capa a 5× (evita que un outlier domine)


@dataclass
class CandidatoLex:
    ticker: str
    elegible: bool                     # gate 1: pasó los 3 pilares conjuntivos (sin banda crítica)
    valuacion_ok: bool                 # gate 2: el falsador NO la marcó ya-priceada (doc 28 §4)
    tier_capital: str                  # A|B|C — riesgo de capital (¿financiada hasta el hito?)
    cobertura: float                   # 0-1: fracción del registry con hecho fundado (doc 27 §4)
    asimetria_operable: float | None   # (bull−precio)/(precio−bear); significativa SOLO en FCFE_OPERABLE
    catalizador: bool = False          # hay catalizador fechado y cercano
    liquidez_adv: float | None = None  # $/día (ADV) — última prioridad de desempate
    route: str = "FCFE_OPERABLE"       # FCFE_OPERABLE | NON_FCFE | CASH_POSITIVE... (define gate + métrica econ)
    burden: float | None = None        # reverse burden (NON_FCFE): parte de la llave económica local (doc 31)
    price_anchor: str = "NA"           # ANCHORED | PURE_OPTION | NA (gate de valuación para NON_FCFE)
    cap: float | None = None           # techo de sizing = min(arquetipo×fragilidad, tier-capital, valuación) (doc 34 §3ter/§7)
    estado_valuacion: str = "?"        # COVERED|STRETCH|OPTION_PRICED|NON_UNDERWRITABLE — eje VALUACIÓN→tamaño (§3ter)
    cap_reason: str = ""               # qué cap LIGÓ el min() (tier|arquetipo|valuacion) — reason code de sizing (§3ter)
    arquetipo: str = "?"               # Madura|Growth|Tracción|Pre-revenue|Binary — define la CELDA (arquetipo×tier)
    runway: float | None = None        # años de pista (supervivencia) — 1ª componente de la burden-tupla pre-revenue
    abstenido: bool = False            # EVIDENCIA_INSUFICIENTE (doc 34 §3bis): no se decide, va a cola de investigación
    motivo_abstencion: str = ""        # por qué se abstuvo (cobertura baja / hecho decisivo UNKNOWN)

    @property
    def gate_ok(self) -> bool:
        # gate del libro duro: elegible + valuación ok Y con evidencia suficiente (si se abstuvo, NO decide).
        return self.elegible and self.valuacion_ok and not self.abstenido


def clave_lexicografica(c: CandidatoLex) -> tuple:
    """Tupla de orden ASCENDENTE (menor = mejor). Lexicográfico puro: la clave k solo importa si
    todas las anteriores empataron. Los que no pasan el gate caen al final."""
    return (
        0 if c.gate_ok else 1,                                 # 1) gate: los que pasan, primero
        _TIER_ORD.get(c.tier_capital, 9),                      # 2) tier de capital A<B<C
        -round(c.cobertura or 0.0, 6),                         # 3) más cobertura, primero
        -min(c.asimetria_operable if c.asimetria_operable is not None else 0.0, ASIMETRIA_CAP),  # 4) asimetría cap 5×
        0 if c.catalizador else 1,                             # 5) con catalizador, primero
        -(c.liquidez_adv or 0.0),                              # 6) más líquido, primero
    )


def rankear_lexicografico(candidatos: list[CandidatoLex]) -> list[CandidatoLex]:
    """Ordena por prioridad lexicográfica (estable). SIN score cardinal. Los gate-fail quedan al final."""
    return sorted(candidatos, key=clave_lexicografica)


def elegibles_ordenados(candidatos: list[CandidatoLex]) -> list[CandidatoLex]:
    """Solo los que pasan AMBOS gates (elegibilidad + valuación), ya ordenados. Es la cola de selección."""
    return [c for c in rankear_lexicografico(candidatos) if c.gate_ok]


def clave_economica_local(c: CandidatoLex) -> tuple:
    """Llave económica LOCAL, por route (doc 34 §3bis — asimetría y burden NO son comparables cross-arquetipo:
    responden preguntas distintas). Menor = mejor. FCFE con ancla → asimetría (cap 5×). Pre-revenue/NON_FCFE →
    **burden-TUPLA**: runway → burden. (funded-to-milestone · dilución-al-hito · cobertura-de-backlog =
    componentes pendientes de sourcing; se suman a la tupla al extraerlos, doc 14 §G/E)."""
    if c.route == "FCFE_OPERABLE" and c.asimetria_operable is not None:
        return (-min(c.asimetria_operable, ASIMETRIA_CAP), 0.0)      # más asimetría = mejor (2-tupla p/ comparar)
    runway = c.runway if c.runway is not None else -1.0             # más runway (supervivencia) primero
    burden = c.burden if c.burden is not None else 1e18            # luego menos burden
    return (-runway, burden)


def _clave_intra_celda(c: CandidatoLex) -> tuple:
    """Orden DENTRO de una celda (arquetipo×tier ya fijos): cobertura → llave económica local → catalizador → liquidez."""
    return (-round(c.cobertura or 0.0, 6), clave_economica_local(c),
            0 if c.catalizador else 1, -(c.liquidez_adv or 0.0))


def rankear_por_celda(candidatos: list[CandidatoLex]) -> dict[tuple[str, str], list[CandidatoLex]]:
    """Ranking por CELDA (arquetipo × tier de capital), solo elegibles (gate ok). Cada celda ordenada por su
    llave económica local. **NO hay orden económico cross-celda** (doc 34 §3bis): la cartera se arma con cuotas
    ex-ante llenando cada celda con su tope. Devuelve {(arquetipo, tier_capital): [ordenados]}."""
    celdas: dict[tuple[str, str], list[CandidatoLex]] = {}
    for c in candidatos:
        if c.gate_ok:
            celdas.setdefault((c.arquetipo, c.tier_capital), []).append(c)
    for k in celdas:
        celdas[k] = sorted(celdas[k], key=_clave_intra_celda)
    return celdas


def cola_operativa(por_celda: dict[tuple[str, str], list[CandidatoLex]]) -> list[CandidatoLex]:
    """Cola OPERATIVA para mostrar, NO un ranking económico (doc 34 §3bis): respeta el prefijo global TIER
    (A→B→C) y hace round-robin entre celdas del mismo tier. El puesto NO implica superioridad económica entre
    celdas distintas — eso lo decide la cuota ex-ante de cartera, no el orden."""
    cola: list[CandidatoLex] = []
    for tier in ("A", "B", "C"):
        cells = sorted([k for k in por_celda if k[1] == tier], key=lambda k: k[0])
        rest = {k: list(por_celda[k]) for k in cells}
        while any(rest.values()):
            for k in cells:
                if rest[k]:
                    cola.append(rest[k].pop(0))
    return cola


def candidato_desde(ev, hoja, *, cobertura: float, liquidez_adv: float | None = None,
                    catalizador: bool = False) -> CandidatoLex:
    """Arma un `CandidatoLex` desde las DOS superficies reales (doc 34 §2): la ELEGIBILIDAD (`Evaluacion`
    de los 3 pilares) + los NÚMEROS (`HojaEvidencia` cohort-free). Duck-typed (no acopla módulos).

    - `ev.tier` ∈ {A,B,C}: elegible = A|B (C = no elegible por los 3 pilares).
    - **Gate de valuación ruteado por owner-FCF (doc 14 §G8, comparación 2 niveles de doc 33):**
      `FCFE_OPERABLE` → gate = el falsador (`falsador_ya_priceado` True → fuera); `NON_FCFE`/owner-FCF<0 → gate =
      `price_anchor_status` (PURE_OPTION → fuera del libro duro / carril; el falsador es no_evaluable ahí).
    - `hoja.capital_risk_tier`: tier de riesgo de capital (A/B/C). "NA" (cash-generative) → A (riesgo bajo).

    `cobertura`/`liquidez_adv`/`catalizador` se pasan (fuentes: fact store / ADV / catalizador citado; doc 14 §G7).
    """
    from backend.nucleo import politica                      # import diferido (evita acoplar el módulo puro)
    # ABSTENCIÓN (doc 34 §3bis): evidencia insuficiente → no se decide (≠ veto). Va a cola de investigación.
    # Dos gatillos: (a) cobertura agregada baja; (b) FALTA un hecho de VETO de supervivencia (restatement…) —
    # guarda SYM (2026-08-31): sin el veto-fact extraído no se puede descartar el veto ⇒ no se compromete capital.
    # Es un piso NO-compensatorio: aunque la cobertura agregada sea alta, un veto-fact UNKNOWN abstiene igual.
    veto_facts_completos = getattr(ev, "veto_facts_completos", True)
    abst_cobertura = cobertura < politica.UMBRAL_COBERTURA_ABSTENCION
    abstenido = abst_cobertura or not veto_facts_completos
    if not veto_facts_completos:
        motivo_abst = ("hecho de veto de supervivencia (restatement/integridad) NO extraído: no se puede "
                       "descartar el veto → abstención hasta tener la evidencia (lección SYM)")
    elif abst_cobertura:
        motivo_abst = (f"cobertura {cobertura:.0%} < umbral {politica.UMBRAL_COBERTURA_ABSTENCION:.0%}: "
                       "evidencia insuficiente para decidir")
    else:
        motivo_abst = ""
    tc = getattr(hoja, "capital_risk_tier", "NA")
    tier_capital = tc if tc in ("A", "B", "C") else "A"      # cash-generative / NA → riesgo de capital bajo
    route = getattr(hoja, "route", "FCFE_OPERABLE")
    anchor = getattr(hoja, "price_anchor_status", "NA")
    burden = getattr(hoja, "burden_gp", None)
    # Gate de valuación ruteado por si el FALSADOR pudo evaluar (NO por route — bug cazado en validación
    # 2026-08-14: S/CASH_POSITIVE tenía falsador evaluable pero se ignoraba por caer en la rama del anchor).
    # --- Reverse-DCF unificado (doc 36/37, Bloque 1.2): si la hoja trae `estado_reverse` (nombre COMERCIAL,
    # owner-FCF+, growth-aware con r_mkt), MANDA sobre el binario g=0 viejo. Los NON-comerciales (pre-revenue/
    # burn) siguen el path burden/anchor de abajo. Esto arregla el g=0 en vivo: un growth probado ya no cae a 2%.
    estado_reverse = getattr(hoja, "estado_reverse", None)
    # --- Eje VALUACIÓN → tamaño (doc 34 §3ter): el precio decide el TAMAÑO (estado), NO la membresía al libro.
    # El falsador ya-priceada ⇒ OPTION_PRICED (chico, EN el duro), NO expulsión. Solo la PURA OPCIÓN sin puente
    # falsable (NON_UNDERWRITABLE) sale al carril. Caso canónico: RKLB = HARD_EVIDENCE / OPTION_PRICED (en el duro,
    # piso). (Fix 2026-08-18: la impl anterior `valuacion_ok = not ya_priceado` expulsaba growth ya-priceados —
    # STRETCH/OPTION_PRICED— al carril de 2 plazas, contra el diseño; achicaba el libro a la nada.)
    ya_priceado = getattr(hoja, "falsador_ya_priceado", False)
    falsador_evaluable = "no_evaluable" not in (getattr(hoja, "falsador_veredicto", "") or "")
    if estado_reverse is not None:
        estado_val = estado_reverse                                        # reverse-DCF growth-aware manda (comercial)
    elif falsador_evaluable:
        # el falsador evaluó (FCFE/CASH_POSITIVE): ya-priceada → OPTION_PRICED (2%, EN el duro); sino COVERED
        estado_val = "OPTION_PRICED" if ya_priceado else "COVERED"
    elif burden is not None:
        estado_val = politica.estado_valuacion_por_burden(burden)         # NON_FCFE con burden → bandas (incl. OPTION_PRICED)
    elif anchor == "PURE_OPTION":
        estado_val = "NON_UNDERWRITABLE"                                  # sin puente falsable → carril (única salida por precio)
    else:
        estado_val = "OPTION_PRICED"                                      # NON_FCFE anclada sin burden computable → conservador
    # Cap por RUTEO=BURDEN (doc 42 §2, fix #25 comparativa n=10): un nombre ruteado a BURDEN (owner-FCF<0 sin
    # escala demostrada, o SBC>25% = motor comercial ficticio) NO puede salir UNDERWRITTEN pleno por el path viejo
    # de anchor — es alto riesgo (S 29% SBC, LEU +31% dilución salían UNDERWRITTEN, el analista decía esperar/evitar).
    # Se capa a OPTION_PRICED (posición chica). No aplica a MADURO/ESCALANDO (que ya tienen estado_reverse propio).
    estado_ruteo = getattr(hoja, "estado_ruteo", None)
    if estado_reverse is None and estado_ruteo == "BURDEN":
        _ORD = {"COVERED": 0, "STRETCH": 1, "OPTION_PRICED": 2, "NON_UNDERWRITABLE": 3}
        if _ORD.get(estado_val, 0) < _ORD["OPTION_PRICED"]:      # peor(estado, OPTION_PRICED)
            estado_val = "OPTION_PRICED"
    # PURA OPCIÓN PRE-REVENUE (fix #26, fresh-10): una empresa con revenue TTM PRE-REVENUE (< base-chica) NO puede
    # salir UNDERWRITTEN por un ancla INMATERIAL (SMR: $10.7M rev, $8B valuación, backlog de frameworks no vinculantes
    # → ANCHORED → underwritten). El ancla de una pre-revenue es inmaterial → es pura opción → NON_UNDERWRITABLE
    # (carril/probe). No aplica a comerciales (estado_reverse ya seteado) ni a revenue material.
    rev_ttm = getattr(hoja, "revenue_ttm", None)
    if estado_reverse is None and rev_ttm is not None and rev_ttm < politica.UMBRAL_BASE_CHICA:
        estado_val = "NON_UNDERWRITABLE"
    # Sizing CONTINUO del bucket growth/BURDEN (doc 47, Fase 1): si la hoja trajo un `size_burden` (comercial
    # owner-FCF<0), REEMPLAZA el estado discreto por el tamaño continuo. a_carril_burden (quema pre-SBC → pura
    # opción) → NON_UNDERWRITABLE (sale al carril, base-rate). Los owner-FCF>0 (MADURO) no traen size_burden:
    # siguen su reverse-DCF de siempre.
    size_burden_frac = getattr(hoja, "size_burden", None)
    if getattr(hoja, "a_carril_burden", False):
        estado_val = "NON_UNDERWRITABLE"
    # El PRECIO no saca del libro duro: solo NON_UNDERWRITABLE (sin ancla falsable) va al carril.
    valuacion_ok = estado_val != "NON_UNDERWRITABLE"
    # Cap de sizing = min de caps INDEPENDIENTES no-compensatorio (doc 34 §3ter/§7): arquetipo×fragilidad ∧
    # tier-capital ∧ valuación. (liquidez/sector se suman en cartera.) reason code = qué cap LIGÓ el min.
    caps = {
        "arquetipo": getattr(ev, "hard_cap", None) or 0.40,              # ev.hard_cap (arquetipo×fragilidad); 0.40 si falta
        "tier": politica.cap_tier_capital(tier_capital),
        # cap de valuación: si hay size_burden (bucket growth/BURDEN, doc 47) manda el tamaño continuo; si no, el
        # cap discreto por estado. size_burden ya incorpora CAP × T × GM × apal × acretividad × SBC (no-compensatorio).
        "valuacion": size_burden_frac if size_burden_frac is not None else politica.cap_valuacion(estado_val),
    }
    cap = min(caps.values())
    cap_reason = min(caps, key=caps.get)                                  # el cap más restrictivo (empate → orden de dict)
    # Elegibilidad = SOBREVIVIÓ (no veto de supervivencia), NO 'score alto' (doc 39 §2.1: gates→scoring). Un
    # tier C sin veto sigue siendo candidato (débil→PROBE). Fallback al esquema viejo si no hay flag de veto.
    veto = getattr(ev, "veto_supervivencia", None)
    elegible = (not veto) if veto is not None else (getattr(ev, "tier", "C") in ("A", "B"))
    return CandidatoLex(
        ticker=getattr(ev, "ticker", None) or getattr(hoja, "ticker", ""),
        elegible=elegible,
        valuacion_ok=valuacion_ok,
        tier_capital=tier_capital,
        cobertura=cobertura,
        asimetria_operable=getattr(hoja, "asimetria_operable", None),
        catalizador=catalizador,
        liquidez_adv=liquidez_adv,
        route=route,
        burden=burden,
        price_anchor=anchor,
        cap=cap,
        estado_valuacion=estado_val,
        cap_reason=cap_reason,
        arquetipo=getattr(ev, "arquetipo", None) or getattr(hoja, "arquetipo", "?"),
        runway=getattr(hoja, "runway_anos", None),
        abstenido=abstenido,
        motivo_abstencion=motivo_abst,
    )


def clasificacion_2ejes(c: CandidatoLex) -> dict:
    """Clasificación en los DOS ejes ORTOGONALES del sizing (doc 34 §3ter, [[sizing-dos-ejes-evidencia-valuacion]]).
    - eje EVIDENCIA → de qué LIBRO forma parte (inmutable):
      · HARD_EVIDENCE  → pasó el gate (elegible + valuación ok) → libro duro.
      · INVESTIGACION  → se abstuvo (evidencia insuficiente) → cola de investigación.
      · CARRIL         → ELEGIBLE (3 pilares OK) pero la valuación lo saca del libro duro (ya-priceada /
        pura opción): su upside es OPCIONALIDAD → carril especulativo (doc 29), NO cash.
      · DESCARTE       → no elegible (falla los 3 pilares) → fuera.
    - eje VALUACIÓN → cuánto CAPITAL (variable): el estado_valuacion.
    RKLB = HARD_EVIDENCE / OPTION_PRICED_CAPITAL: en el libro duro por su demanda, piso por su precio. Ninguno
    compensa al otro — el precio NUNCA saca del libro (solo lo re-rutea a carril), la evidencia NUNCA agranda el tamaño."""
    if c.gate_ok:
        libro = "HARD_EVIDENCE"
    elif c.abstenido:
        libro = "INVESTIGACION"
    elif c.elegible:
        libro = "CARRIL"            # elegible pero valuación lo saca → opcionalidad (doc 29), no descarte
    else:
        libro = "DESCARTE"
    return {"eje_evidencia": libro, "eje_valuacion": c.estado_valuacion,
            "etiqueta": f"{libro} / {c.estado_valuacion}"}


ESTADOS_DECISION = ("UNDERWRITTEN", "PROBE", "WATCH", "REJECT")


def estado_decision(c: CandidatoLex) -> str:
    """Los 4 estados de decisión de doc 39 §2.7 (rebalanceo) — reemplazan el binario abstención→cash. Es el
    vocabulario que consume el canal de juicio (Bloque 3). Mapea 1:1 al eje EVIDENCIA de `clasificacion_2ejes`:
      · REJECT       → no sobrevivió (veto de supervivencia / no elegible). Fuera.
      · WATCH        → se abstuvo (evidencia insuficiente, sin milestone invertible aún). Cola de investigación.
      · UNDERWRITTEN → sobrevivió + evidencia suficiente + valuación underwritable → tamaño CORE (libro duro).
      · PROBE        → elegible pero la valuación es pura opcionalidad (NON_UNDERWRITABLE) → probe CHICO / carril.
    (La distinción fina PROBE-vs-REJECT por 'burden inalcanzable aun favorable' la refina el gate del carril, B3.)"""
    if not c.elegible:
        return "REJECT"
    if c.abstenido:
        return "WATCH"
    if c.gate_ok:                    # elegible + no abstenido + valuación underwritable (no NON_UNDERWRITABLE)
        return "UNDERWRITTEN"
    return "PROBE"                   # elegible pero opcionalidad → candidato a probe chico (doc 29/39)


def cola_investigacion(candidatos: list[CandidatoLex]) -> list[CandidatoLex]:
    """Los que ABSTUVIERON (evidencia insuficiente) → cola de investigación, con el motivo/hecho faltante nombrado
    (doc 34 §3bis). NO son un veto: se re-evalúan cuando la evidencia mejore."""
    return [c for c in candidatos if c.abstenido]


def tasa_abstencion(candidatos: list[CandidatoLex]) -> float:
    """Fracción abstenida — MÉTRICA DE SALUD de 1ª línea (doc 34 §3bis): si no baja en el tiempo, el cuello es
    la extracción de evidencia, no los gates."""
    return round(sum(1 for c in candidatos if c.abstenido) / len(candidatos), 3) if candidatos else 0.0
