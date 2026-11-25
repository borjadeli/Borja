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
