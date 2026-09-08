"""Tabla determinista de apertura/transición/archivo — Bloque B, §4.

REGLA MADRE: toda transición de estado, en los DOS sentidos, se define por un
observable numérico con umbral. Si una transición solo se puede describir con
palabras ("demanda frenada", "resuelto", "caliente"), NO está terminada. El LLM
trae el observable; la tabla compara contra el umbral; el LLM nunca emite el
juicio compuesto.

  ABRE en promesa         — hecho de estrangulamiento cruza umbral (lead-time > X,
                            precio spot +Y% sostenido, take-or-pay > Z, shortage
                            doc. por fuente A/B). Un solo hecho fuerte abre.
  promesa → confirmado    — primer hecho de monetización REAL (revenue contratado,
                            PO, delivery, take-or-pay). NO confirman: up to $X,
                            warrants, MOU, framework, compras discrecionales.
  confirmado → debilitándose — la INVERSIÓN de la apertura (lead-time < X_normal,
                            precio revierte, backlog se contrae). Se mide contra la
                            CAPTURA. "Quiebra del proveedor" NO es input válido
                            (puede FORTALECER el nodo).
  → ARCHIVA               — observables vuelven a normal y se quedan, o el cuello
                            migró. Archivado ≠ borrado: reabrible.
"""
from __future__ import annotations

from backend.mapa.nodo import (
    ClaseHecho,
    EstadoArchivo,
    EstadoConfirmacion,
    FUENTES_DURAS,
    Hecho,
    Nodo,
)


def evaluar_apertura(hecho: Hecho) -> dict:
    """¿Un hecho suelto ABRE un nodo nuevo en 'promesa'? (§4, fila ABRE).

    Exige: clase ESTRANGULAMIENTO + cruza umbral + fuente dura (A/B). Un solo
    hecho fuerte abre. Devuelve {abre, estado_inicial, motivo}.
    """
    if hecho.clase != ClaseHecho.ESTRANGULAMIENTO:
        return {"abre": False, "motivo": f"hecho no es de estrangulamiento ({hecho.clase.value})"}
    if not hecho.cruza_umbral:
        return {"abre": False, "motivo": "el observable no cruza el umbral de apertura"}
    if hecho.fuente_nivel not in FUENTES_DURAS:
        return {"abre": False, "motivo": f"fuente {hecho.fuente_nivel} insuficiente (se exige A/B)"}
    return {"abre": True, "estado_inicial": EstadoConfirmacion.PROMESA,
            "motivo": f"estrangulamiento cruza umbral ({hecho.descripcion})"}


def evaluar_transicion(nodo: Nodo, hecho: Hecho) -> dict:
    """Aplica la tabla §4 a un nodo EXISTENTE ante un hecho nuevo. Devuelve
    {accion, nuevo_estado, nuevo_archivo, motivo}. accion ∈
    {confirmar, debilitar, archivar, reconfirmar, sin_cambio}.

    No muta el nodo; el caller persiste si corresponde (aplicar()).
    """
    e = nodo.estado_confirmacion

    # ARCHIVA (desde cualquier estado vivo): normalización sostenida.
    if hecho.clase == ClaseHecho.NORMALIZACION and hecho.normalizado_sostenido:
        return {"accion": "archivar", "nuevo_estado": e, "nuevo_archivo": EstadoArchivo.ARCHIVADO,
                "motivo": "observables volvieron a normal y se quedaron (estrangulamiento resuelto)"}

    if e == EstadoConfirmacion.PROMESA:
        # promesa → confirmado: primer hecho de monetización REAL.
        if hecho.clase == ClaseHecho.MONETIZACION and hecho.es_monetizacion_real:
            return {"accion": "confirmar", "nuevo_estado": EstadoConfirmacion.CONFIRMADO,
                    "nuevo_archivo": EstadoArchivo.VIVO,
                    "motivo": f"monetización real enganchada ({hecho.descripcion})"}
        return {"accion": "sin_cambio", "nuevo_estado": e, "nuevo_archivo": nodo.estado_archivo,
                "motivo": "sin monetización real (up-to/MOU/warrant/framework/discrecional no confirman)"}

    if e == EstadoConfirmacion.CONFIRMADO:
        # confirmado → renta_debilitándose: inversión de la apertura, medida sobre la captura.
        if hecho.clase == ClaseHecho.REVERSION and hecho.cruza_umbral and hecho.mide_captura:
            return {"accion": "debilitar", "nuevo_estado": EstadoConfirmacion.RENTA_DEBILITANDOSE,
                    "nuevo_archivo": EstadoArchivo.VIVO,
                    "motivo": f"observable de captura se dio vuelta ({hecho.descripcion})"}
        return {"accion": "sin_cambio", "nuevo_estado": e, "nuevo_archivo": nodo.estado_archivo,
                "motivo": "sin reversión válida del observable de captura"}

    if e == EstadoConfirmacion.RENTA_DEBILITANDOSE:
        # Puede REVIVIR a confirmado con nueva monetización real (el nodo nunca se borra por debilitarse).
        if hecho.clase == ClaseHecho.MONETIZACION and hecho.es_monetizacion_real:
            return {"accion": "reconfirmar", "nuevo_estado": EstadoConfirmacion.CONFIRMADO,
                    "nuevo_archivo": EstadoArchivo.VIVO,
                    "motivo": f"nueva monetización real revive la captura ({hecho.descripcion})"}
        return {"accion": "sin_cambio", "nuevo_estado": e, "nuevo_archivo": nodo.estado_archivo,
                "motivo": "sigue debilitándose"}

    return {"accion": "sin_cambio", "nuevo_estado": e, "nuevo_archivo": nodo.estado_archivo,
            "motivo": "estado no contemplado"}


def aplicar(nodo: Nodo, hecho: Hecho) -> dict:
    """Evalúa la transición y MUTA el nodo (estado + archivo + hechos +
    fecha_ultimo_hecho). Devuelve el resultado de evaluar_transicion."""
    r = evaluar_transicion(nodo, hecho)
    nodo.estado_confirmacion = r["nuevo_estado"]
    nodo.estado_archivo = r["nuevo_archivo"]
    nodo.hechos.append(hecho)
    if nodo.fecha_ultimo_hecho is None or hecho.fecha > nodo.fecha_ultimo_hecho:
        nodo.fecha_ultimo_hecho = hecho.fecha
    return r
