"""Discovery — frecuencia de vigilancia por estado + nodos calientes (Bloque B §6, §7).

Dos modos (§6):
  - Vigilancia (barato, frecuente): refresca el ESTADO de los nodos existentes.
    Frecuencia POR ESTADO, no uniforme. Latencia de hasta una quincena ACEPTADA
    para el caso normal (la jugada es sobre el rezagado aguas arriba).
  - Exploración (caro, esporádico): busca cuellos que TODAVÍA no son nodo,
    disparado por FIRMAS DE HECHOS (no por sectores), con presupuesto reservado.
    [El barrido LLM + scheduler es wiring — pendiente, como el extractor.]

Nodos calientes (§7): frecuencia rápida para el rezagado veloz. Un nodo es
caliente por DEFINICIÓN FÁCTICA (catalizador fechado tipo orden/PO/partnership
con hyperscaler/soberano en los últimos X días), no por juicio del LLM. Expira
solo: vuelve a frecuencia normal al confirmarse o al vencer la ventana.

Esta capa es determinista y pura: decide CUÁNDO se mira, nunca CON QUÉ se compra
(eso es el gate del núcleo). Constantes calibrables (§9.2).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from backend.mapa.nodo import EstadoConfirmacion, Nodo

# Frecuencia de vigilancia por estado (días) — calibrable (§9.2).
FRECUENCIA_VIGILANCIA_DIAS = {
    EstadoConfirmacion.CONFIRMADO: 14,           # estable, espaciado (~2 semanas).
    EstadoConfirmacion.PROMESA: 10,              # más seguido (1-2 semanas).
    EstadoConfirmacion.RENTA_DEBILITANDOSE: 10,  # más seguido.
}
FRECUENCIA_CALIENTE_DIAS = 2                      # nodos calientes: vigilancia rápida.
VENTANA_CATALIZADOR_CALIENTE_DIAS = 30           # "últimos X días" del catalizador (§7).


def _parse(fecha: str | None) -> datetime | None:
    if not fecha:
        return None
    try:
        return datetime.fromisoformat(fecha[:10])
    except ValueError:
        return None


def es_nodo_caliente(nodo: Nodo, hoy: datetime | None = None) -> bool:
    """§7 — caliente por definición fáctica: tiene un catalizador (orden/PO/
    partnership con hyperscaler/soberano) fechado dentro de la ventana. Expira
    solo al vencer la ventana. La tabla lo prende/apaga; el LLM nunca lo declara."""
    hoy = hoy or datetime.utcnow()
    corte = hoy - timedelta(days=VENTANA_CATALIZADOR_CALIENTE_DIAS)
    for h in nodo.hechos:
        if not h.es_catalizador_caliente:
            continue
        f = _parse(h.fecha)
        if f is not None and f >= corte:
            return True
    return False


def frecuencia_revision_dias(nodo: Nodo, hoy: datetime | None = None) -> int:
    """Días entre revisiones para este nodo: rápida si está caliente; si no, por
    estado. Un nodo archivado no se vigila (devuelve un número grande)."""
    from backend.mapa.nodo import EstadoArchivo
    if nodo.estado_archivo == EstadoArchivo.ARCHIVADO:
        return 10_000
    if es_nodo_caliente(nodo, hoy):
        return FRECUENCIA_CALIENTE_DIAS
    return FRECUENCIA_VIGILANCIA_DIAS.get(nodo.estado_confirmacion, 14)


def debe_vigilar(nodo: Nodo, hoy: datetime | None = None) -> bool:
    """¿Toca re-vigilar el nodo? (días desde la última vigilancia ≥ frecuencia).
    Si nunca se vigiló, toca."""
    hoy = hoy or datetime.utcnow()
    ultima = _parse(nodo.fecha_ultima_vigilancia)
    if ultima is None:
        return True
    return (hoy - ultima).days >= frecuencia_revision_dias(nodo, hoy)


def nodos_a_vigilar(nodos: list[Nodo], hoy: datetime | None = None) -> list[Nodo]:
    """Cola de vigilancia: los nodos vivos cuya frecuencia venció. El barrido es
    barato (§5); el costo escala con candidatas investigadas a profundidad, no
    con la cantidad de nodos."""
    hoy = hoy or datetime.utcnow()
    return [n for n in nodos if debe_vigilar(n, hoy)]
