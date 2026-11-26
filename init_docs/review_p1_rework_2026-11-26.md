# Review 2 — implementamos su devolución (fail-closed). ¿Lo hicimos bien?

Ustedes dos corrieron/leyeron el código de P1 y encontraron un defecto SISTÉMICO (fail-OPEN: un dato faltante
AGRANDABA el permiso/cap) + problemas de diseño. Reescribimos todo contra su devolución. Antes de gastar budget en
que el Analista emita los campos y correr la sombra real, queremos su confirmación de que lo implementamos bien.

## Qué cambió (su feedback → nuestro fix)

| Su hallazgo | Fix |
|---|---|
| **Fail-open** (None agranda el permiso/cap) | Todos los módulos reciben HECHOS CRUDOS y tratan None como el caso MÁS restrictivo. |
| caps: `(CORE,None,None)=10%` · case `OPTIONALITY`/`opcionalidad` · pre_revenue mata la manga | cap_posicion fail-closed; OPTIONALITY NO usa caps de núcleo; case canónico. **De 1/7 a 7/7 de su spec.** |
| permiso: acción/motivo desconocido→EJECUTAR · mecánica saltea todo · defaults permisivos | enum CERRADO (desconocido→BLOQUEAR); mecánica exige `evidencia_mecanica` + controles operativos; el módulo computa peso>cap y la elegibilidad de tier (REVIEW no entra a núcleo). |
| arquetipo: depende del precio (circularidad) · clave revenue · signo capex · ausencia≠cero | clave de revenue unificada · capex en valor absoluto · `contratado_firme=None`→UNEVALUABLE→UNCLASSIFIED (no cae a pre_revenue). *Circularidad infra/EV: documentada, pendiente del campo estructural.* |
| banda: rango invertido daba COMPRA_FUERTE | rango invertido/NaN → None. |
| rotación: 3 condiciones no-compensatorias = VETO al mérito (mata la power-law) | **el código valida que la comparación sea POSIBLE (fail-closed); el MÉRITO lo decide el PM.** |
| el demo era circular (inputs a mano) · faltaba Doosan | demo HONESTO: sin inputs inventados, con Doosan; con dossiers históricos (sin campos estructurados) P1 fail-closed bloquea compras / difiere ventas sin comparación — correcto. |

**Los 24 tests fail-closed de IA1 ahora PASAN (antes fallaban 23). 1073 tests verdes en total.**

También adoptamos: no-compensatorio para supervivencia/riesgo, COMPENSATORIO para la economía (el PM decide el mérito);
tabla de autoridad (doc 91 §8); "stub=sacar pieza" se cayó → rechazar+reformular; REVIEW ruidoso → TRANSICIÓN, no venta.

## El harness (lado determinista, listo; el Analista todavía no emite los campos)
Agregamos el CONTRATO que el Analista va a EMITIR y el harness CONSUME (no se extrae de narrativa — su consejo):
`Underwriting{arquetipo_confirmado, metrica_obligatoria[rango], banda_inputs, financing_gap, status}`. Mapeo
dossier→orquestador + registro de la decisión en sombra (qué cambiaría + missing_fields + contrafactual de bloqueadas).

## Lo que les pedimos revisar
1. **¿Implementamos bien su feedback?** ¿Queda algún camino fail-open o bug en los 6 módulos reescritos?
2. **¿El contrato `Underwriting` es el correcto** para que el Analista lo emita (arquetipo confirmado, métrica, insumos de
   banda por arquetipo, financing_gap)? ¿Le falta o le sobra algo?
3. **La rotación VALIDEZ-vs-MÉRITO**: ¿la línea entre lo que valida el código y lo que decide el PM quedó bien?
4. **¿Qué verificarían ANTES de correr la sombra real** (gastar budget en que el Analista emita)? 
5. Sabiendo que lo próximo es: Analista emite → wiring al run → 2-3 semanas de sombra → revisión de 20 decisiones →
   autoridad → freeze 90d. ¿Cambiarían ese orden o agregarían un gate?

Abajo va el código completo de los 6 módulos reescritos + el harness.

## backend/agentes/tiers.py
```python
"""P1.3 (doc 91 §7) — IPS por TIERS: 4 categorías ECONÓMICAS que reemplazan al piso rígido de 5%.

IA1 it.2: OPTIONALITY 1-3% · CORE 5-10% · HIGH_CONVICTION >10-15% · EXCEPTIONAL >15-20% · EXIT 0%. SIN tier 3-5%
(la opcionalidad es una categoría económica distinta, no un CORE chico → evita que toda posición chica sea una
excepción al piso). El tier NO da derecho a usar todo su rango: aguas arriba siempre gana el cap más restrictivo
(liquidez/supervivencia/sector/cuello). Determinista, $0. Los números viven en `ips.yaml` (`tiers:`).
"""
from __future__ import annotations

TIERS_ORDEN = ("OPTIONALITY", "CORE", "HIGH_CONVICTION", "EXCEPTIONAL")
_EPS = 1e-9


def _en_banda(weight: float, banda: dict) -> bool:
    """¿`weight` cae en la banda? Soporta `min` (inclusivo), `min_exclusive` (exclusivo) y `max` (inclusivo)."""
    hi = banda.get("max")
    if hi is None or weight > hi + _EPS:
        return False
    if banda.get("min") is not None:
        return weight >= banda["min"] - _EPS
    if banda.get("min_exclusive") is not None:
        return weight > banda["min_exclusive"] + _EPS
    return False


def valid_target_weight(weight: float, tier: str, tiers_cfg: dict) -> bool:
    """¿`weight` es un peso objetivo VÁLIDO para el `tier` declarado? (regla exacta de IA1 §1.2). EXIT → 0."""
    if tier == "EXIT":
        return abs(weight) < _EPS
    banda = (tiers_cfg or {}).get(tier)
    return _en_banda(weight, banda) if banda else False


def tier_de_peso(weight: float, tiers_cfg: dict) -> str | None:
    """El tier al que pertenece `weight`, o None si cae en una zona INVÁLIDA (p.ej. 4% o 3.5% — entre tiers)."""
    if abs(weight) < _EPS:
        return "EXIT"
    for t in TIERS_ORDEN:
        if valid_target_weight(weight, t, tiers_cfg):
            return t
    return None


def peso_valido(weight: float, tiers_cfg: dict) -> bool:
    """¿`weight` cae en ALGÚN tier válido (o es 0)? Lo que reemplaza al chequeo del piso rígido."""
    return tier_de_peso(weight, tiers_cfg) is not None
```

## backend/agentes/arquetipo.py
```python
"""P1 (doc 91 §8, review IA1+IA2) — clasificador de ARQUETIPO económico. MODO SOMBRA: computa el arquetipo
PROPUESTO desde señales deterministas del pack; NO aplica nada. El Analista confirma o hace override con fuente.

Precedencia: infra → pre_revenue → ciclica → compounder (primera señal true gana). Robustez (review):
- Clave de revenue UNIFICADA (`revenue_ltm` o `revenue`): antes infra leía una y pre_revenue otra → CIFR caía en pre_revenue.
- El capex se toma en VALOR ABSOLUTO (muchos feeds lo traen negativo = salida de caja) → no apaga la señal de infra.
- AUSENCIA ≠ CERO: si `contratado_firme` es None (el scanner no corrió), la señal de infra es UNEVALUABLE → NO se deja
  caer la vía OCF<0+runway (que solapa con infra) a pre_revenue; queda UNCLASSIFIED y lo resuelve el Analista.

CAVEAT (IA2, pendiente para la fase del schema del Analista): la señal de infra usa `contratado/EV`, que depende del
PRECIO (circularidad: una empresa cambiaría de arquetipo si sube la acción). El fix estructural (controla activos de
larga vida + revenue contratado material) necesita un campo estructural del dossier. Determinista, $0.
"""
from __future__ import annotations

import math

ARQUETIPOS = ("infra", "pre_revenue", "ciclica", "compounder")
SECTORES_CICLICOS = {"e&p", "mineria", "minería", "ipp", "quimica", "química", "shipping", "semis_equipos",
                     "oil_gas", "gas", "uranio", "cobre", "commodities"}


def _num(x):
    """Valor numérico finito o None (rechaza NaN/inf y no-números)."""
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _rev(d: dict):
    r = _num(d.get("revenue_ltm"))
    return r if r is not None else _num(d.get("revenue"))


def _frac(a, b):
    a, b = _num(a), _num(b)
    if a is None or b is None or b <= 0:
        return None
    return a / b


def _señal_infra(d: dict):
    """True/False/None. None = UNEVALUABLE (no se escaneó `contratado_firme`) → no es "no-infra"."""
    if d.get("contratado_firme") is None:
        return None
    cob = _frac(d.get("contratado_firme"), d.get("ev"))
    capex = _num(d.get("capex"))
    capint = _frac(abs(capex) if capex is not None else None, _rev(d))   # capex en valor absoluto
    if cob is None or capint is None:
        return None
    return cob >= 0.5 and capint >= 0.5


def _señal_pre_revenue(d: dict, *, infra_evaluable: bool) -> bool:
    rev = _rev(d)
    if rev is not None and rev < 50e6:
        return True                                   # señal definitiva
    gm = _num(d.get("margen_bruto_ltm"))
    if gm is not None and gm <= 0:
        return True                                   # señal definitiva
    # vía OCF<0 + runway corto: SOLAPA con infra → solo si infra pudo evaluarse (y dio no-infra)
    ocf, runway = _num(d.get("ocf_ltm")), _num(d.get("runway_meses"))
    if infra_evaluable and ocf is not None and ocf < 0 and runway is not None and runway < 36:
        return True
    return False


def _señal_ciclica(d: dict) -> bool:
    if (d.get("sector") or "").strip().lower() in SECTORES_CICLICOS:
        return True
    cv = _num(d.get("cv_margen_op_10a"))
    if cv is not None and cv > 0.5:
        return True
    m_ltm, m_med = _num(d.get("margen_op_ltm")), _num(d.get("margen_op_mediana_10a"))
    return m_ltm is not None and m_med is not None and m_med > 0 and m_ltm > 1.5 * m_med


def _señal_compounder(d: dict) -> bool:
    fcf_a, roic_a = _num(d.get("fcf_pos_anios_de5")), _num(d.get("roic_gt15_anios_de5"))
    return fcf_a is not None and roic_a is not None and fcf_a >= 4 and roic_a >= 4


def clasificar_arquetipo(datos: dict) -> str | None:
    """Arquetipo PROPUESTO (precedencia infra→pre_revenue→ciclica→compounder) o None (UNCLASSIFIED)."""
    infra = _señal_infra(datos)
    if infra is True:
        return "infra"
    if _señal_pre_revenue(datos, infra_evaluable=(infra is not None)):
        return "pre_revenue"
    if _señal_ciclica(datos):
        return "ciclica"
    if _señal_compounder(datos):
        return "compounder"
    return None
```

## backend/agentes/banda.py
```python
"""P1 (doc 91 §7, blueprint IA2 §2) — BANDA por arquetipo. MODO SOMBRA: computa COMPRA_FUERTE/COMPRA/MANTENER/
RECORTE desde la métrica del arquetipo (rango del dossier) + el precio del día; NO aplica nada. Se recalcula CADA
ciclo y NUNCA se persiste → mata de raíz las "zonas viejas" (el bug que hizo que el PM operara sobre fichas de
días previos). Usa SIEMPRE el extremo DESFAVORABLE del rango del analista. Bordes versionados (cambiarlos = cambio
de sistema). Determinista, $0.

- infra        → cobertura del EV con contratos IG (extremo BAJO del rango).
- ciclica      → precio vs valor de mitad de ciclo / a la curva [bajo, alto].
- compounder   → g exigido por el precio vs g sostenible [bajo, alto].
- pre_revenue  → NO tiene banda de núcleo; elegible a opcionalidad si p_implícita.alto < p_razonada.bajo.
"""
from __future__ import annotations

import math

BANDAS = ("COMPRA_FUERTE", "COMPRA", "MANTENER", "RECORTE")
_G_HOLGURA = 0.03   # 3pp: margen extra de COMPRA_FUERTE del compounder (versionado)


def _rango_valido(bajo, alto) -> bool:
    """El rango del analista debe ser finito y bajo ≤ alto (un rango invertido/NaN daría una banda falsa)."""
    for v in (bajo, alto):
        if v is None or not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
            return False
    return bajo <= alto


def banda_infra(cobertura_ig_bajo: float | None) -> str | None:
    c = cobertura_ig_bajo                       # extremo BAJO (desfavorable) del rango de cobertura
    if c is None:
        return None
    if c >= 1.0:
        return "COMPRA_FUERTE"
    if c >= 0.8:
        return "COMPRA"
    if c >= 0.5:
        return "MANTENER"
    return "RECORTE"


def banda_ciclica(precio: float | None, valor_bajo: float | None, valor_alto: float | None) -> str | None:
    if precio is None or not _rango_valido(valor_bajo, valor_alto):
        return None                               # rango invertido / NaN / incompleto → sin banda (no inventa)
    medio = (valor_bajo + valor_alto) / 2.0
    if precio < valor_bajo:
        return "COMPRA_FUERTE"
    if precio <= medio:
        return "COMPRA"
    if precio <= valor_alto:
        return "MANTENER"
    return "RECORTE"                            # precio por ENCIMA del rango de mitad de ciclo (caso EXE a la curva)


def banda_compounder(g_exigido: float | None, g_sost_bajo: float | None, g_sost_alto: float | None) -> str | None:
    if g_exigido is None or not isinstance(g_exigido, (int, float)) or not _rango_valido(g_sost_bajo, g_sost_alto):
        return None
    if g_exigido < g_sost_bajo - _G_HOLGURA:
        return "COMPRA_FUERTE"
    if g_exigido < g_sost_bajo:
        return "COMPRA"
    if g_exigido <= g_sost_alto:
        return "MANTENER"
    return "RECORTE"                            # el precio exige MÁS crecimiento del que el negocio sostiene


def pre_revenue_elegible_opcionalidad(p_implicita_alto: float | None, p_razonada_bajo: float | None) -> bool:
    """pre_revenue NO va a núcleo; solo a opcionalidad si el precio implica MENOS éxito del razonado (margen)."""
    if p_implicita_alto is None or p_razonada_bajo is None:
        return False
    return p_implicita_alto < p_razonada_bajo


def calcular_banda(arquetipo: str, datos: dict) -> str | None:
    """Dispatcher. `datos` trae los insumos del dossier (rangos) + precio del día. pre_revenue → None (no hay banda
    de núcleo); su elegibilidad a opcionalidad se evalúa con `pre_revenue_elegible_opcionalidad`."""
    if arquetipo == "infra":
        return banda_infra(datos.get("cobertura_ig_bajo"))
    if arquetipo == "ciclica":
        return banda_ciclica(datos.get("precio"), datos.get("valor_mitad_ciclo_bajo"), datos.get("valor_mitad_ciclo_alto"))
    if arquetipo == "compounder":
        return banda_compounder(datos.get("g_exigido"), datos.get("g_sost_bajo"), datos.get("g_sost_alto"))
    return None   # pre_revenue o arquetipo desconocido: sin banda de núcleo
```

## backend/agentes/permiso_ejecucion.py
```python
"""P1 (doc 91 §8, review IA1+IA2) — execution_permission FAIL-CLOSED. MODO SOMBRA: lo CALCULA el código desde
HECHOS CRUDOS (verificación, tier, peso_objetivo, cap, falsador, comparación), NO desde booleanos pre-digeridos con
defaults permisivos. Un dato faltante/desconocido NUNCA habilita una transacción.

Tres estados (IA2): EJECUTAR · DIFERIR (solo ventas discrecionales con dependencia sin resolver) · BLOQUEAR.

Principios (review):
- Enum CERRADO de acciones: una acción o motivo desconocido → BLOQUEAR (antes caía a EJECUTAR por el default).
- La salida MECÁNICA puede saltear los gates ECONÓMICOS de compra, pero exige EVIDENCIA (id de la resolución/regla
  disparada) y pasa los controles OPERATIVOS universales (no saltea TODO). "falsador_duro" declarado no es autoridad.
- Apertura/aumento: el módulo computa él mismo peso>cap y la elegibilidad de tier (REVIEW no entra a núcleo); sin
  verificación / sin cap / sin falsador ligado a la métrica → BLOQUEAR.
- Venta discrecional: sin comparación computada → DIFERIR; si la métrica de A es desconocida (no se puede mostrar que
  A está en RECORTE, caso IESC) → DIFERIR; comparación BLOQUEADA → BLOQUEAR.
Determinista, $0.
"""
from __future__ import annotations

_APERTURAS = ("abrir", "aumentar")
_REDUCCIONES = ("reducir", "salir")
_MECANICOS = ("falsador_duro", "techo_ips", "regla_ips")
_NUCLEO = ("CORE", "HIGH_CONVICTION", "EXCEPTIONAL")
_ACCIONES = _APERTURAS + _REDUCCIONES + ("mantener",)
_VERIF_VALIDAS = ("PASS", "REVIEW", "FAIL")
_EPS = 1e-9


def _blockers_apertura(ctx: dict) -> list[str]:
    """Blockers DUROS de una apertura/aumento/compra-de-par, computados desde hechos crudos (fail-closed)."""
    m: list[str] = []
    verif = (ctx.get("verificacion") or "").upper()
    if verif not in _VERIF_VALIDAS:
        m.append("sin verificación (fail-closed: ausencia ≠ PASS)")
    elif verif == "FAIL":
        m.append("verificación FAIL")
    tier = ctx.get("tier")
    if tier in _NUCLEO and verif != "PASS":
        m.append("tier de núcleo requiere verificación PASS (REVIEW no entra a núcleo)")
    if ctx.get("metrica_obligatoria_null"):
        m.append("métrica obligatoria del arquetipo = null")
    if not ctx.get("falsador_id") or not ctx.get("falsador_sobre_metrica"):
        m.append("falsador ausente o no ligado a la métrica del arquetipo")
    peso, cap = ctx.get("peso_objetivo"), ctx.get("cap")
    if peso is None or cap is None:
        m.append("peso objetivo o cap no computado (fail-closed)")
    elif peso > cap + _EPS:
        m.append(f"peso objetivo {peso:.1%} > cap {cap:.1%}")
    if ctx.get("flags_alta_sin_responder"):
        m.append("flags ALTA sin responder")
    if ctx.get("bloqueo_datos"):
        m.append("bloqueo de datos (reconciliación / precio sin 2ª fuente)")
    if ctx.get("crea_stub_o_viola_ips"):
        m.append("el estado resultante crea un stub o viola el IPS por esta decisión")
    return m


def execution_permission(ctx: dict) -> tuple[str, list[str]]:
    accion = (ctx.get("accion") or "").strip().lower()
    motivo = (ctx.get("motivo_accion") or "").strip().lower()

    # 0. Enum CERRADO: acción desconocida/typo/vacía → BLOQUEAR (antes: EJECUTAR por default).
    if accion not in _ACCIONES:
        return "BLOQUEAR", ["acción no reconocida"]

    # 1. Mantener = ausencia de transacción.
    if accion == "mantener":
        return "EJECUTAR", []

    # 2. Salida MECÁNICA: exige evidencia + controles operativos; puede saltear gates ECONÓMICOS, no los operativos.
    if accion in _REDUCCIONES and motivo in _MECANICOS:
        if not ctx.get("evidencia_mecanica"):
            return "BLOQUEAR", ["salida mecánica declarada SIN evidencia (id de resolución/regla disparada)"]
        if ctx.get("ejecucion_insegura"):
            return "BLOQUEAR", ["controles operativos: datos de ejecución inseguros"]
        return "EJECUTAR", ["salida mecánica validada"]

    # 3. Apertura / aumento / compra de un par → fail-closed blockers.
    if accion in _APERTURAS or ctx.get("es_compra_de_par"):
        bloq = _blockers_apertura(ctx)
        return ("BLOQUEAR", bloq) if bloq else ("EJECUTAR", [])

    # 4. Reducción / venta DISCRECIONAL.
    if accion in _REDUCCIONES:
        if motivo != "discrecional":
            return "BLOQUEAR", ["motivo de reducción no reconocido"]       # fail-closed
        comp = ctx.get("comparacion")
        if comp is None:
            return "DIFERIR", ["venta discrecional sin comparación computada (A vs B o A vs caja)"]
        if comp == "BLOQUEADA":
            return "BLOQUEAR", ["la comparación de la venta dio BLOQUEADA"]
        if ctx.get("metrica_A_null"):
            return "DIFERIR", ["la banda/métrica de A es desconocida — no se puede mostrar que A está en RECORTE"]
        if not ctx.get("dossier_del_ciclo", True) or ctx.get("bloqueo_datos"):
            return "DIFERIR", ["datos viejos/bloqueados"]
        if ctx.get("par_compra_bloqueada"):
            return "DIFERIR", ["par de rotación cuya compra quedó bloqueada/pendiente"]
        return "EJECUTAR", []

    return "BLOQUEAR", ["caso no cubierto"]       # fail-closed default
```

## backend/agentes/caps_posicion.py
```python
"""P1 (doc 91 §7, blueprint IA2 §1 + review fail-closed IA1) — CAP de posición. MODO SOMBRA: computa el techo
económico y REGISTRA qué cap ligó; no aplica nada.

**FAIL-CLOSED (review IA1):** un dato faltante/desconocido NUNCA agranda el cap. En NÚCLEO, un arquetipo o una banda
desconocidos → cap 0 (no "cap ausente"). En OPTIONALITY NO aplican los caps de NÚCLEO (arquetipo/banda de dinero
nuevo): la manga es la razón de existir del tamaño chico — pre_revenue es elegible, y la banda actúa como GATE de
elegibilidad (RECORTE o desconocida → no elegible), no como cap de dinero nuevo. El tier se nombra con UNA
representación canónica (las claves del IPS, p.ej. "OPTIONALITY"). Determinista, $0.

OJO (IA2): esto es un cap de DINERO NUEVO / techo de concentración, NO un piso de tenencia — un activo no-comprable
NO es un activo que haya que vender (eso lo decide la ficha viva / el PM, no este módulo).
"""
from __future__ import annotations


def cap_posicion(*, tier: str, arquetipo: str | None, banda: str | None, verificacion: str | None,
                 cfg: dict) -> tuple[float, str]:
    """Devuelve (cap, liga). `liga` = el cap más restrictivo o el motivo del 0 (fail-closed)."""
    tiers = cfg.get("tiers") or {}
    tier_max = (tiers.get(tier) or {}).get("max")
    if tier_max is None:
        return 0.0, "tier_desconocido"                      # fail-closed: tier no reconocido

    # ── OPTIONALITY: NO usa los caps de núcleo. Elegibilidad + cap por evidencia. ──
    if tier == "OPTIONALITY":
        ev = (cfg.get("cap_por_evidencia_opcionalidad") or {}).get((verificacion or "").upper())
        if ev is None:
            return 0.0, "sin_evidencia"                     # fail-closed: sin verificación no hay cap de opcionalidad
        cap = min(tier_max, ev)
        liga = "evidencia" if ev <= tier_max else "tier"
        if arquetipo == "pre_revenue":
            return cap, liga                                # pre_revenue es elegible por p_implícita, no por banda
        if banda in (None, "RECORTE"):
            return 0.0, "banda_no_elegible_opcionalidad"    # fail-closed: sin banda elegible, no entra
        return cap, liga

    # ── NÚCLEO: cap = min(tier, arquetipo, banda de dinero nuevo). Desconocido → 0. ──
    ca = (cfg.get("cap_por_arquetipo") or {}).get(arquetipo)
    if ca is None:
        return 0.0, "arquetipo_desconocido"
    cb = (cfg.get("cap_por_banda") or {}).get(banda)
    if cb is None:
        return 0.0, "banda_desconocida"
    caps = {"tier": tier_max, "arquetipo": ca, "banda": cb}
    liga = min(caps, key=lambda k: caps[k])
    return caps[liga], liga
```

## backend/agentes/comparacion_rotacion.py
```python
"""P1 (doc 91 §8, review IA2 §1.6) — COMPARACIÓN antes de rotar. REDISEÑO: el código valida que la comparación sea
POSIBLE y fail-closed; el MÉRITO económico (si el upside compensa el riesgo) lo decide el PM. MODO SOMBRA.

Por qué cambió: la versión anterior exigía SIMULTÁNEAMENTE mejor banda + igual/mejor evidencia + igual/menor riesgo
→ convertía una evaluación multidimensional en un VETO determinista, y eso contradice la razón de ser de un PM-LLM y
mata la power-law (una B con E[R] 137% vs 25% pero bear más severo quedaba rechazada). Las restricciones de
SUPERVIVENCIA/liquidez/concentración SÍ son no-compensatorias (las aplica el IPS aguas arriba); los ATRIBUTOS
ECONÓMICOS de la inversión NO (los compensa el PM: mayor incertidumbre ↔ mayor upside ↔ posición menor).

Resultado: PERMITIDA = la comparación es VÁLIDA (el PM decide si rota) · BLOQUEADA = la comparación es inválida
(fail-closed: destino sin verificar, nulls portantes, dossier viejo, banda de A o B desconocida → NO se premia la
ausencia de info). Determinista, $0.
"""
from __future__ import annotations


def comparar_rotacion(a: dict, b: dict) -> tuple[str, list[str]]:
    # ── Venta a CAJA: válida solo si A perdió el capital por una razón CLARA (no por ruido de REVIEW). ──
    if b.get("es_caja"):
        if a.get("banda") == "RECORTE" or a.get("flag_alta_no_opera"):
            return "PERMITIDA", ["A en RECORTE / flag ALTA respondido no_opera"]
        # perder elegibilidad por REVIEW (ruidoso — marcó el 10-K de IESC como no primario) → TRANSICIÓN, no venta
        return "BLOQUEADA", ["A no está en RECORTE ni perdió elegibilidad por una razón clara "
                             "(un REVIEW ruidoso NO habilita vender a caja → TRANSICIÓN)"]

    # ── Rotación A→B: VALIDEZ de la comparación (fail-closed). El mérito lo decide el PM, no el código. ──
    motivos: list[str] = []
    if (b.get("verificacion") or "").upper() not in ("PASS", "REVIEW"):
        motivos.append("destino B sin verificación válida (FAIL o ausente)")
    if b.get("nulls_portantes"):
        motivos.append("B tiene nulls portantes")
    if not b.get("dossier_del_ciclo", False):                 # fail-closed: debe ser del ciclo explícitamente
        motivos.append("el dossier de B no es del ciclo")
    if a.get("banda") is None or b.get("banda") is None:
        motivos.append("banda de A o B desconocida — comparación inválida (no se premia la ausencia de info)")
    if motivos:
        return "BLOQUEADA", motivos
    # Comparación VÁLIDA: el PM juzga si la ventaja económica compensa el costo/riesgo (dentro de los límites del IPS).
    return "PERMITIDA", ["comparación válida — el MÉRITO lo decide el PM (atributos económicos compensatorios)"]
```

## backend/agentes/evaluar_sombra.py
```python
"""P1 (doc 91 §8) — ORQUESTADOR en sombra: encadena los 6 módulos fail-closed (arquetipo→banda→cap→permiso) para
UNA decisión y devuelve el veredicto + los campos PORTANTES que faltan. MODO SOMBRA: computa, NO aplica.

Honesto por diseño: NO inventa rangos de banda, ids de falsador ni métricas. Si el dossier (histórico) no trae el
campo estructurado, queda en missing_fields y el permiso lo trata fail-closed (una apertura sin falsador/métrica/banda
→ BLOQUEAR). Eso es lo CORRECTO: no se autoriza sobre datos incompletos. El harness REAL (pendiente, gated por el
operador) extiende el schema del Analista para que DEVUELVA esos campos; este orquestador los CONSUME, no los reinterpreta.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.agentes.arquetipo import clasificar_arquetipo
from backend.agentes.banda import calcular_banda
from backend.agentes.caps_posicion import cap_posicion
from backend.agentes.permiso_ejecucion import execution_permission

_NUCLEO_DEFAULT = "CORE"


@dataclass
class VeredictoSombra:
    arquetipo: str | None
    banda: str | None
    tier: str
    cap: float
    liga: str
    permiso: str
    motivos: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)


def evaluar_sombra(d: dict, *, cfg: dict) -> VeredictoSombra:
    """`d` = una decisión con lo que el sistema REALMENTE sabe (señales de arquetipo, verif, acción propuesta, etc.).
    No se completan defaults permisivos: lo que falta queda None → el permiso lo trata fail-closed."""
    # el arquetipo CONFIRMADO por el Analista define el método; si no, lo PROPONE el código desde las señales.
    arq = d.get("arquetipo_confirmado") or clasificar_arquetipo(d.get("sig") or {})
    banda = calcular_banda(arq, d.get("banda_in") or {}) if arq else None
    # tier: IA2 — es una propiedad DECLARADA por el PM, no se infiere del peso. Para el histórico se propone y se marca.
    tier = d.get("tier_declarado") or ("OPTIONALITY" if (arq == "pre_revenue" or d.get("flag_alta")) else _NUCLEO_DEFAULT)
    cap, liga = cap_posicion(tier=tier, arquetipo=arq, banda=banda, verificacion=d.get("verif"), cfg=cfg)

    missing: list[str] = []
    if arq is None:
        missing.append("arquetipo")
    if banda is None and arq != "pre_revenue":
        missing.append("banda (rango de valuación del dossier)")
    if not d.get("falsador_estructurado"):
        missing.append("falsador estructurado")
    if not d.get("metrica_obligatoria_presente"):
        missing.append("métrica obligatoria del arquetipo")
    if d.get("tier_declarado") is None:
        missing.append("tier declarado por el PM")

    ctx = {
        "accion": d.get("accion"), "motivo_accion": d.get("motivo"),
        "verificacion": d.get("verif"), "tier": tier,
        "peso_objetivo": d.get("peso_objetivo"), "cap": cap,
        "falsador_id": d.get("falsador_id"),
        "falsador_sobre_metrica": bool(d.get("falsador_sobre_metrica")),
        "metrica_obligatoria_null": not d.get("metrica_obligatoria_presente", False),
        "flags_alta_sin_responder": d.get("flags_alta_sin_responder", False),
        "bloqueo_datos": d.get("bloqueo_datos"),
        "comparacion": d.get("comparacion"),
        "metrica_A_null": banda is None,
        "dossier_del_ciclo": d.get("dossier_del_ciclo", True),
        "evidencia_mecanica": d.get("evidencia_mecanica"),
    }
    permiso, motivos = execution_permission(ctx)
    return VeredictoSombra(arquetipo=arq, banda=banda, tier=tier, cap=cap, liga=liga,
                           permiso=permiso, motivos=motivos, missing_fields=missing)
```

## backend/agentes/harness_sombra.py
```python
"""P1 (doc 91 §8) — HARNESS de sombra: mapea un Dossier (+ la decisión del PM + el pack) a los insumos del
orquestador `evaluar_sombra`, CONSUMIENDO el bloque económico estructurado del Analista (`dossier.underwriting`) —
no lo reinterpreta de la narrativa (IA2 §3.2). Lo que el Analista no emitió queda None → fail-closed.

Esta es la pieza que conecta el circuito real con la capa P1 en sombra: dada una decisión del comité, computa "qué
habría decidido P1" sin aplicarlo. Determinista, $0. (El logging del shadow_decision + el registro de contrafactuales
bloqueados — IA2 §3.5/3.6 — es el siguiente paso; este módulo es el consumidor.)
"""
from __future__ import annotations

from backend.agentes.evaluar_sombra import VeredictoSombra, evaluar_sombra


def _falsador_liga_metrica(dossier, uw) -> bool:
    """¿El falsador DURO mide la métrica obligatoria del arquetipo o un insumo? (IA2: no exigir la métrica EXACTA,
    sí que esté ligado al mecanismo.) Aproximación: hay vara externa con una métrica declarada."""
    fals = getattr(dossier, "falsador", None)
    vara = getattr(fals, "vara_externa", None) if fals else None
    return bool(vara and getattr(vara, "metrica", None))


def insumos_de_dossier(dossier, *, verif: str, accion: str, motivo: str = "discrecional",
                       peso_objetivo: float | None = None, tier_declarado: str | None = None,
                       comparacion: str | None = None, bloqueo_datos=None, sig_pack: dict | None = None) -> dict:
    """Arma el `d` que consume `evaluar_sombra` desde un Dossier verificado + la decisión del PM. `sig_pack` =
    señales de arquetipo del data pack (fallback si el Analista no confirmó el arquetipo)."""
    uw = getattr(dossier, "underwriting", None)
    banda_inputs = dict(getattr(uw, "banda_inputs", None) or {})
    metrica_presente = bool(uw and getattr(uw, "metrica_obligatoria_bajo", None) is not None)
    falsador_ok = _falsador_liga_metrica(dossier, uw)
    return {
        "arquetipo_confirmado": getattr(uw, "arquetipo_confirmado", None) if uw else None,
        "sig": sig_pack or {},                     # fallback: el código propone desde el pack si no hay confirmado
        "banda_in": banda_inputs,
        "verif": verif,
        "accion": accion,
        "motivo": motivo,
        "peso_objetivo": peso_objetivo,
        "tier_declarado": tier_declarado,
        "metrica_obligatoria_presente": metrica_presente,
        "falsador_estructurado": falsador_ok,
        "falsador_id": (getattr(getattr(dossier, "falsador", None), "afirmacion", None) or None) if falsador_ok else None,
        "falsador_sobre_metrica": falsador_ok,
        "comparacion": comparacion,
        "bloqueo_datos": list(bloqueo_datos) if bloqueo_datos else None,
    }


def evaluar_decision_sombra(dossier, *, cfg: dict, verif: str, accion: str, **kw) -> VeredictoSombra:
    """Conveniencia: mapea el dossier y corre el orquestador en un paso."""
    return evaluar_sombra(insumos_de_dossier(dossier, verif=verif, accion=accion, **kw), cfg=cfg)
```

## backend/agentes/shadow_log.py
```python
"""P1 (doc 91 §8, IA2 §3.5/3.6) — registro de la decisión en SOMBRA. Por cada decisión del comité guarda qué habría
decidido P1 (el VeredictoSombra), si eso CAMBIARÍA la propuesta del PM, y qué campos portantes faltaron. Append-only
a `data/shadow_p1.jsonl`. NO aplica nada. Es lo que se observa durante la sombra antes de darle autoridad.

Mide (IA2 §3.6): % bloqueado por P1, % por datos desconocidos, % por mérito, y —clave— registra también las
propuestas BLOQUEADAS (para medir el costo de oportunidad, no solo las permitidas). Determinista, $0.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "shadow_p1.jsonl"

# ¿la acción del PM BUSCA desplegar/mover capital? (si P1 la bloquea/difiere, cambia la decisión)
_ACCIONES_QUE_MUEVEN = {"abrir", "aumentar", "reducir", "salir"}


def _cambiaria(accion_pm: str, permiso: str) -> bool:
    """La decisión del PM cambiaría si propuso mover capital y P1 no la deja EJECUTAR."""
    return (accion_pm or "").strip().lower() in _ACCIONES_QUE_MUEVEN and permiso != "EJECUTAR"


def construir_shadow_decision(*, ciclo: str, ticker: str, accion_pm: str, veredicto, dossier_ref: str | None = None,
                              ips_version: str = "p1-v1") -> dict:
    """`veredicto` = VeredictoSombra (de evaluar_sombra/harness)."""
    return {
        "tipo": "shadow_p1",
        "ts": datetime.now(timezone.utc).isoformat(),
        "ciclo": ciclo,
        "ips_version": ips_version,
        "ticker": ticker.upper(),
        "evidence_ref": dossier_ref,
        "propuesta_pm": accion_pm,
        "shadow": {
            "arquetipo": veredicto.arquetipo,
            "banda": veredicto.banda,
            "tier": veredicto.tier,
            "cap": veredicto.cap,
            "permiso": veredicto.permiso,
            "motivos": list(veredicto.motivos),
        },
        "cambiaria_la_decision": _cambiaria(accion_pm, veredicto.permiso),
        "data_quality": {"missing_fields": list(veredicto.missing_fields)},
    }


def registrar_shadow(record: dict, *, path: Path | str | None = None) -> None:
    """Append best-effort (la sombra NUNCA debe tumbar el run)."""
    p = Path(path or _PATH)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 — logging de sombra, no crítico
        pass


def resumen_sombra(records: list[dict]) -> dict:
    """Agregados de IA2 §3.6 sobre los registros de un período (para el monitor)."""
    n = len(records) or 1
    cambios = sum(1 for r in records if r.get("cambiaria_la_decision"))
    bloqueadas = sum(1 for r in records if r.get("shadow", {}).get("permiso") == "BLOQUEAR")
    por_datos = sum(1 for r in records if r.get("data_quality", {}).get("missing_fields"))
    return {"n": len(records), "cambiaria_%": round(100 * cambios / n, 1),
            "bloqueadas_%": round(100 * bloqueadas / n, 1),
            "con_datos_faltantes_%": round(100 * por_datos / n, 1),
            "fecha": date.today().isoformat()}
```

## backend/agentes/schemas.py — clase Underwriting (el contrato que emitirá el Analista)
```python
class Underwriting(BaseModel):
    """P1 (doc 91 §8) — bloque económico ESTRUCTURADO que el Analista EMITE y el harness CONSUME (no lo extrae de
    narrativa). El código PROPONE el arquetipo (clasificar_arquetipo); el Analista CONFIRMA/override con fuente y
    emite la métrica obligatoria + los insumos de banda del arquetipo. None en cualquier campo portante → fail-closed
    (no se autoriza). `banda_inputs` lleva las claves que consume `calcular_banda` por arquetipo (cobertura_ig_bajo ·
    valor_mitad_ciclo_bajo/alto + precio · g_exigido + g_sost_bajo/alto · p_implicita_alto + p_razonada_bajo).
    Todo opcional = dossier legacy (sin bloque → el harness lo marca incompleto)."""
    arquetipo_propuesto: str | None = None             # lo pone el código (informativo)
    arquetipo_confirmado: str | None = None            # el Analista confirma/override → DEFINE el método
    override_razon: str | None = None
    metrica_obligatoria_nombre: str | None = None      # incremental_roic / normalized_owner_fcf_per_share / stabilized_fcfe_per_share / funding_gap
    metrica_obligatoria_bajo: float | None = None      # rango [bajo, alto] (se usa el extremo desfavorable)
    metrica_obligatoria_alto: float | None = None
    banda_inputs: dict[str, float] = Field(default_factory=dict)
    financing_gap: float | None = None                 # pre_revenue: capital hasta breakeven de caja
    permanent_loss_mechanism: str | None = None
    status: Literal["COMPLETE", "INCOMPLETE", "UNKNOWN"] = "INCOMPLETE"
```
