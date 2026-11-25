"""P1 (doc 91 §7, blueprint IA2 §3) — execution_permission. MODO SOMBRA: lo CALCULA el código (el PM no lo
escribe) integrando verificación + arquetipo + banda + tier + flags + datos; por ahora se LOGUEA, no se aplica.

Tres estados (IA2):
  EJECUTAR  — salidas mecánicas (falsador DURO / techo / regla IPS); y todo lo que pasa los gates.
  BLOQUEAR  — apertura/aumento/compra-de-par o venta discrecional que choca con un blocker DURO.
  DIFERIR   — SOLO ventas discrecionales: datos viejos/bloqueados, o par de rotación cuya compra quedó bloqueada.

Principio (doc 91): una falla de valuación o un dossier FAIL NO debe impedir VENDER una posición — por eso la
salida mecánica siempre EJECUTA y la discrecional, en el peor caso, DIFIERE (no se traba una salida de riesgo).
Determinista, $0.
"""
from __future__ import annotations

_APERTURAS = ("abrir", "aumentar")
_REDUCCIONES = ("reducir", "salir")
_MECANICOS = ("falsador_duro", "techo_ips", "regla_ips")


def _blockers_apertura(ctx: dict) -> list[str]:
    """Blockers DUROS de una apertura/aumento/compra-de-par (IA2 §3.BLOQUEAR)."""
    m: list[str] = []
    if (ctx.get("verificacion") or "").upper() == "FAIL":
        m.append("verificación FAIL")
    if ctx.get("metrica_obligatoria_null"):
        m.append("métrica obligatoria del arquetipo = null")
    if not ctx.get("falsador_id") or not ctx.get("falsador_sobre_metrica"):
        m.append("falsador ausente o no mide la métrica del arquetipo")
    if not ctx.get("peso_en_grilla", True):
        m.append("peso objetivo fuera de la grilla del tier")
    if ctx.get("peso_sobre_min_caps"):
        m.append("peso objetivo > min(caps): tier/arquetipo/banda/evidencia")
    if not ctx.get("tier_elegible", True):
        m.append("tier no elegible (arquetipo/verificación/banda/flags)")
    if ctx.get("flags_alta_sin_responder"):
        m.append("flags ALTA sin responder")
    if ctx.get("bloqueo_datos"):
        m.append("bloqueo de datos (reconciliación / precio sin 2ª fuente)")
    if ctx.get("opcionalidad_sin_plaza_o_congelada"):
        m.append("opcionalidad sin plaza o manga congelada")
    if ctx.get("crea_stub_o_viola_ips"):
        m.append("el estado resultante crea un stub o viola el IPS por esta decisión")
    return m


def execution_permission(ctx: dict) -> tuple[str, list[str]]:
    """Devuelve (permiso, motivos). `ctx` = contexto de UNA decisión (acción/motivo + evidencia computada)."""
    accion = (ctx.get("accion") or "").lower()
    motivo = (ctx.get("motivo_accion") or "").lower()

    # 1. Salida MECÁNICA → EJECUTAR siempre (no la traba nada; no consume clip).
    if accion in _REDUCCIONES and motivo in _MECANICOS:
        return "EJECUTAR", ["salida mecánica"]

    # 2. Apertura / aumento / compra de un par → BLOQUEAR si choca con un blocker duro.
    if accion in _APERTURAS or ctx.get("es_compra_de_par"):
        bloq = _blockers_apertura(ctx)
        if bloq:
            return "BLOQUEAR", bloq
        return "EJECUTAR", []

    # 3. Venta/reducción DISCRECIONAL → DIFERIR con datos viejos/bloqueados o par trabado; BLOQUEAR sin motivo válido.
    if accion in _REDUCCIONES and motivo == "discrecional":
        difs: list[str] = []
        if not ctx.get("dossier_del_ciclo", True):
            difs.append("dossier no es del ciclo")
        if ctx.get("bloqueo_datos"):
            difs.append("datos bloqueados")
        if ctx.get("par_compra_bloqueada"):
            difs.append("par de rotación cuya compra quedó bloqueada/pendiente")
        if difs:
            return "DIFERIR", difs
        if ctx.get("venta_a_caja_sin_motivo_valido"):
            return "BLOQUEAR", ["venta discrecional a caja sin motivo válido (comparación vs caja)"]
        return "EJECUTAR", []

    # 4. Mantener u otros → EJECUTAR (ausencia de transacción; HOLD no aprueba economía, pero no se traba).
    return "EJECUTAR", []
