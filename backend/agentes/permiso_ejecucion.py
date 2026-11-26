"""P1 (doc 91 §8, review-2 IA1+IA2) — execution_permission FAIL-CLOSED **por CONFIRMACIÓN POSITIVA**.

El bug de la review-1: los chequeos eran NEGATIVOS (`if ctx.get("campo_malo"): bloquear`). Una clave AUSENTE es
falsy → no bloqueaba → "bloquear todo" se volvía "ejecutar todo" en cuanto el caller olvidaba un campo. La review-2
(ambas IAs, ejecutando el código) lo confirmó: `execution_permission({abrir, PASS, CORE, peso 6%})` → EJECUTAR.

Rediseño: una APERTURA ejecuta SOLO si TODOS los hechos materiales están PRESENTES y confirmados por el código
(verificación, tier con su banda de peso vía `tiers_cfg`, falsador ligado a la métrica, y los 4 hechos operativos
`metrica_obligatoria_null/flags_alta_sin_responder/bloqueo_datos/crea_stub_o_viola_ips`). Clave ausente = "no se
chequeó" = BLOQUEAR (no "está bien"). `bloqueo_datos: []` = chequeado sin bloqueos; `None`/ausente = no chequeado.

Asimetría FAIL-CLOSED (IA2): lo que AUMENTA riesgo (abrir/aumentar) → BLOQUEAR ante info faltante; lo que lo REDUCE
(reducir/salir) → DIFERIR (temporal), nunca BLOQUEAR permanente — "fail-closed" en una venta sería quedar atrapado.

Tres estados: EJECUTAR · DIFERIR (ventas con dependencia sin resolver) · BLOQUEAR. Determinista, $0.
"""
from __future__ import annotations

from backend.agentes.numeros import finito

_APERTURAS = ("abrir", "aumentar")
_REDUCCIONES = ("reducir", "salir")
_MECANICOS = ("falsador_duro", "techo_ips", "regla_ips")
_NUCLEO = ("CORE", "HIGH_CONVICTION", "EXCEPTIONAL")
_ACCIONES = _APERTURAS + _REDUCCIONES + ("mantener",)
_VERIF_VALIDAS = ("PASS", "REVIEW", "FAIL")
# los 4 hechos operativos que deben venir EXPLÍCITOS en una apertura (confirmación positiva)
_HECHOS_BOOL = {"metrica_obligatoria_null": "métrica obligatoria del arquetipo = null",
                "flags_alta_sin_responder": "flags ALTA sin responder",
                "crea_stub_o_viola_ips": "el estado resultante crea un stub o viola el IPS"}
_EPS = 1e-9


def _banda_de_tier(tier: str, tiers_cfg) -> dict | None:
    if not isinstance(tiers_cfg, dict):
        return None
    b = tiers_cfg.get(tier)
    return b if isinstance(b, dict) else None


def _peso_en_banda_de_tier(peso, tier, tiers_cfg) -> list[str]:
    """El peso objetivo debe caer DENTRO de la banda [min, max] del tier (fail-closed: sin tiers_cfg → BLOQUEAR).
    Un peso por debajo del mínimo crea un stub; por encima del máximo viola la concentración del tier."""
    band = _banda_de_tier(tier, tiers_cfg)
    if band is None:
        return ["tiers_cfg ausente o tier no definido (fail-closed: no se puede validar la banda de peso)"]
    p = finito(peso)
    if p is None:
        return [f"peso objetivo no finito ({peso!r})"]
    lo = band.get("min", band.get("min_exclusive"))
    hi = band.get("max")
    if lo is None or hi is None:
        return ["banda de peso del tier incompleta en tiers_cfg"]
    bajo_ok = (p > lo + _EPS) if "min_exclusive" in band else (p >= lo - _EPS)
    m: list[str] = []
    if not bajo_ok:
        m.append(f"peso {p:.1%} por debajo del mínimo del tier {tier} (crea stub)")
    if p > hi + _EPS:
        m.append(f"peso {p:.1%} por encima del máximo del tier {tier}")
    return m


def _hechos_explicitos_faltan(ctx: dict) -> list[str]:
    """Confirmación POSITIVA: cada hecho operativo tiene que venir en el ctx y con el valor 'limpio'. Ausente → bloquea."""
    m: list[str] = []
    for k, msg in _HECHOS_BOOL.items():
        if k not in ctx:
            m.append(f"hecho '{k}' no chequeado (clave ausente ≠ está bien)")
        elif ctx[k]:                               # True = hay problema
            m.append(msg)
    if "bloqueo_datos" not in ctx or ctx["bloqueo_datos"] is None:
        m.append("bloqueo_datos no chequeado (None/ausente = no se verificó la reconciliación/2ª fuente)")
    elif ctx["bloqueo_datos"]:
        m.append("bloqueo de datos (reconciliación / precio sin 2ª fuente)")
    return m


def _blockers_apertura(ctx: dict) -> list[str]:
    """Blockers DUROS de una apertura/aumento, computados desde hechos crudos (confirmación positiva, fail-closed)."""
    m: list[str] = []
    verif = (ctx.get("verificacion") or "").upper()
    if verif not in _VERIF_VALIDAS:
        m.append("sin verificación (fail-closed: ausencia ≠ PASS)")
    elif verif == "FAIL":
        m.append("verificación FAIL")
    tier = ctx.get("tier")
    if tier in _NUCLEO and verif != "PASS":
        m.append("tier de núcleo requiere verificación PASS (REVIEW no entra a núcleo)")
    if not ctx.get("falsador_id") or not ctx.get("falsador_sobre_metrica"):
        m.append("falsador ausente o no ligado a la métrica del arquetipo")
    # peso vs cap (ambos finitos; NaN/None no habilita)
    pf, cf = finito(ctx.get("peso_objetivo")), finito(ctx.get("cap"))
    if pf is None or cf is None:
        m.append("peso objetivo o cap no computado/finito (fail-closed)")
    elif pf > cf + _EPS:
        m.append(f"peso objetivo {pf:.1%} > cap {cf:.1%}")
    # peso dentro de la banda del tier (tiers_cfg OBLIGATORIO)
    m += _peso_en_banda_de_tier(ctx.get("peso_objetivo"), tier, ctx.get("tiers_cfg"))
    # los 4 hechos operativos, por confirmación positiva
    m += _hechos_explicitos_faltan(ctx)
    # pre_revenue: solo entra a opcionalidad si el precio implica MENOS éxito del razonado (margen de seguridad)
    if ctx.get("arquetipo") == "pre_revenue":
        pi, pr = finito(ctx.get("p_implicita_alto")), finito(ctx.get("p_razonada_bajo"))
        if pi is None or pr is None:
            m.append("pre_revenue sin p_implícita/p_razonada computadas (fail-closed: no se evaluó el margen)")
        elif not (pi < pr):
            m.append("pre_revenue sin margen (p_implícita.alto ≥ p_razonada.bajo)")
    return m


def _evidencia_mecanica_valida(ctx: dict, accion: str) -> bool:
    """La salida MECÁNICA se PRUEBA, no se declara: dict {id, ticker, gatillado, consecuencia} del mismo ticker, con
    la regla gatillada y una consecuencia que AUTORIZA esta acción (SALIDA cubre salir/reducir; RECORTE_* solo reduce)."""
    ev = ctx.get("evidencia_mecanica")
    if not isinstance(ev, dict) or not ev.get("gatillado"):
        return False
    if ev.get("ticker") != ctx.get("ticker"):
        return False
    cons = str(ev.get("consecuencia") or "").upper()
    if accion == "salir":
        return cons == "SALIDA"
    if accion == "reducir":
        return cons == "SALIDA" or cons.startswith("RECORTE")
    return False


def _reduccion_deja_stub(ctx: dict) -> bool:
    """Reducir a un peso >0 pero por debajo del mínimo del tier deja un stub → reformular como salida total."""
    pf = finito(ctx.get("peso_objetivo"))
    if pf is None or pf <= _EPS or ctx.get("tier") not in _NUCLEO:
        return False
    band = _banda_de_tier(ctx.get("tier"), ctx.get("tiers_cfg"))
    lo = band.get("min", band.get("min_exclusive")) if band else None
    return lo is not None and pf < lo - _EPS


def execution_permission(ctx: dict) -> tuple[str, list[str]]:
    accion = (ctx.get("accion") or "").strip().lower()
    motivo = (ctx.get("motivo_accion") or "").strip().lower()

    # 0. Enum CERRADO: acción desconocida/typo/vacía → BLOQUEAR.
    if accion not in _ACCIONES:
        return "BLOQUEAR", ["acción no reconocida"]

    # 1. Mantener = ausencia de transacción.
    if accion == "mantener":
        return "EJECUTAR", []

    # 2. Salida MECÁNICA: exige EVIDENCIA verificable + controles operativos (puede saltear los gates económicos).
    if accion in _REDUCCIONES and motivo in _MECANICOS:
        if not _evidencia_mecanica_valida(ctx, accion):
            return "BLOQUEAR", ["salida mecánica sin evidencia verificable {id,ticker,gatillado,consecuencia}"]
        if ctx.get("ejecucion_insegura"):
            return "BLOQUEAR", ["controles operativos: datos de ejecución inseguros"]
        return "EJECUTAR", ["salida mecánica validada"]

    # 3. Apertura / aumento / compra de un par → fail-closed por confirmación positiva.
    if accion in _APERTURAS or ctx.get("es_compra_de_par"):
        bloq = _blockers_apertura(ctx)
        return ("BLOQUEAR", bloq) if bloq else ("EJECUTAR", [])

    # 4. Reducción / venta DISCRECIONAL (lo que REDUCE riesgo → DIFERIR ante info faltante, no BLOQUEAR permanente).
    if accion in _REDUCCIONES:
        if motivo != "discrecional":
            return "BLOQUEAR", ["motivo de reducción no reconocido"]       # fail-closed del enum de motivo
        comp = ctx.get("comparacion")
        if comp == "BLOQUEADA":                                            # comparación conocida-inválida → bloquea
            return "BLOQUEAR", ["la comparación de la venta dio BLOQUEADA"]
        if "peso_objetivo" not in ctx:
            return "DIFERIR", ["reducción sin peso objetivo (no se sabe a qué nivel se reduce)"]
        if _reduccion_deja_stub(ctx):
            return "BLOQUEAR", ["la reducción deja un stub (< mínimo del tier) — reformular como salida total"]
        if comp is None:
            return "DIFERIR", ["venta discrecional sin comparación computada (A vs B o A vs caja)"]
        if comp != "PERMITIDA":                                           # enum CERRADO: solo 'PERMITIDA' ejecuta
            return "DIFERIR", [f"comparación '{comp}' no es PERMITIDA (falta info / inválida → diferir)"]
        if ctx.get("metrica_A_null"):
            return "DIFERIR", ["la banda/métrica de A es desconocida — no se puede mostrar que A está en RECORTE"]
        if "dossier_del_ciclo" not in ctx or not ctx.get("dossier_del_ciclo"):
            return "DIFERIR", ["dossier del ciclo ausente/viejo (fail-closed: ausente = no se verificó)"]
        if ctx.get("bloqueo_datos"):
            return "DIFERIR", ["datos bloqueados"]
        # ROTACIÓN (fondos = un ticker, no caja): la compra del par tiene que estar confirmada NO bloqueada (atomicidad).
        fondos = ctx.get("fondos")
        if fondos is not None and str(fondos).strip().lower() != "caja":
            if ctx.get("par_compra_bloqueada") is not False:
                return "DIFERIR", ["rotación: el estado de la compra del par no vino confirmado como no-bloqueado"]
        return "EJECUTAR", []

    return "BLOQUEAR", ["caso no cubierto"]       # fail-closed default
