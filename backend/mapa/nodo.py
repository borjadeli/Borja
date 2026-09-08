"""Estructura del nodo del mapa de cuellos — Bloque B, §3.

Los campos NO son una lista plana: son tres bloques que cambian a velocidades
distintas. Esa separación es lo que evita que el mapa se pudra.

  3.1 Identidad estructural (lento, casi nunca cambia): id, nombre_cuello,
      condicion_apertura (incl. hipótesis de captura OBSERVABLE), factor_macro
      (etiqueta visible y NO-decisoria — no entra a ninguna fórmula).
  3.2 Estado vivo (rápido, lo actualiza el Discovery con hechos): estado_confirmacion,
      hechos (fechados, con fuente A-F), fecha_ultimo_hecho, candidatas_enganchadas.
  3.3 Gobierno: fecha_apertura, estado_archivo, y timestamp_revision por vínculo
      candidata↔nodo (la ÚNICA pieza nueva aceptada de toda la triangulación).
  3.4 cadena_de_valor vive en el VÍNCULO, no en el nodo (la misma empresa ocupa
      posiciones distintas según el producto).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class EstadoConfirmacion(str, Enum):
    PROMESA = "promesa"                     # el cuello existe pero nadie monetiza aún.
    CONFIRMADO = "confirmado"               # hay hecho fechado de monetización real.
    RENTA_DEBILITANDOSE = "renta_debilitandose"  # estuvo confirmado y los observables se dieron vuelta.


class EstadoArchivo(str, Enum):
    VIVO = "vivo"
    ARCHIVADO = "archivado"                 # archivado ≠ borrado: reabrible, conserva histórico.


class PosicionCadena(str, Enum):
    """§3.4 — propiedad del VÍNCULO empresa↔nodo, no del nodo."""
    AGUAS_ARRIBA = "aguas_arriba"           # la pala (proveedor del proveedor).
    ESTRANGULAMIENTO = "estrangulamiento"   # el punto que captura renta.
    AGUAS_ABAJO = "aguas_abajo"


class ClaseHecho(str, Enum):
    """Clase del hecho que el Discovery cuelga del nodo (la tabla §4 decide qué
    transición dispara). El LLM trae el hecho con su observable; nunca el juicio."""
    ESTRANGULAMIENTO = "estrangulamiento"   # lead-time/precio spot/take-or-pay/shortage → abre.
    MONETIZACION = "monetizacion"           # revenue contratado/PO/delivery/take-or-pay → confirma.
    REVERSION = "reversion"                 # observable de captura se da vuelta → debilita.
    NORMALIZACION = "normalizacion"         # observables vuelven a normal y se quedan → archiva.


# Jerarquía de fuentes A-F del núcleo (A = filing/regulador; B = primaria verificable;
# C = prensa con contraparte). Apertura exige A o B.
FUENTES_DURAS = ("A", "B")


@dataclass
class Hecho:
    """Hecho fechado colgado de un nodo (§3.2). El LLM lo trae con fuente; la tabla
    decide. cruza_umbral / es_monetizacion_real / mide_captura / normalizado_sostenido
    son ETIQUETAS del observable, no juicios de resultado."""
    clase: ClaseHecho
    descripcion: str
    fecha: str                              # ISO date.
    fuente_nivel: str                       # 'A'..'F'.
    cruza_umbral: bool = False              # el observable cruzó el umbral configurado.
    es_monetizacion_real: bool = False      # revenue/PO/delivery/take-or-pay (NO mou/up-to/warrant/framework).
    mide_captura: bool = False              # la reversión mide el observable de captura (no "quiebra del proveedor").
    normalizado_sostenido: bool = False     # los observables volvieron a normal y se quedaron.
    es_catalizador_caliente: bool = False   # §7: orden/PO/partnership con hyperscaler/comprador soberano (def. fáctica).
    observable: dict = field(default_factory=dict)  # {tipo, valor, ...} para auditoría.


@dataclass
class Vinculo:
    """Vínculo candidata↔nodo (§3.2/§3.3/§3.4). Lleva DOS cosas propias: la
    posición en la cadena y el timestamp_revision (la única pieza nueva de B)."""
    ticker: str
    posicion_cadena: PosicionCadena
    timestamp_revision: str | None = None   # cuándo se revisó por última vez (ISO). NO guarda veredicto.


@dataclass
class Nodo:
    """Un cuello de botella. Se nombra por su POSICIÓN ESTRUCTURAL, nunca por su
    estado (SiC power no muere cuando Wolfspeed quiebra; cambia su captura)."""
    # 3.1 Identidad estructural (lento)
    id: str
    nombre_cuello: str                      # angosto y transable (filtro de granularidad §2.2).
    condicion_apertura: str                 # qué hecho-umbral abrió + hipótesis de captura observable.
    factor_macro: str | None = None         # etiqueta visible y NO-decisoria (§3.1).

    # 3.2 Estado vivo (rápido)
    estado_confirmacion: EstadoConfirmacion = EstadoConfirmacion.PROMESA
    hechos: list[Hecho] = field(default_factory=list)
    fecha_ultimo_hecho: str | None = None
    candidatas_enganchadas: list[Vinculo] = field(default_factory=list)

    # 3.3 Gobierno
    fecha_apertura: str | None = None
    estado_archivo: EstadoArchivo = EstadoArchivo.VIVO
    fecha_ultima_vigilancia: str | None = None   # clock de la vigilancia §6.1 (distinto de fecha_ultimo_hecho).

    def enganchar_candidata(self, ticker: str, posicion: PosicionCadena,
                            timestamp: str | None = None) -> Vinculo:
        """Cuelga una candidata del nodo (§3.2). NO decide nada sobre ella: cada
        una corre el núcleo por su cuenta."""
        v = Vinculo(ticker=ticker.upper(), posicion_cadena=posicion, timestamp_revision=timestamp)
        self.candidatas_enganchadas.append(v)
        return v

    def candidatas_a_remirar(self, fecha_hecho: str) -> list[Vinculo]:
        """§3.3 / traspaso §7.4 — vínculos cuyo timestamp_revision es anterior al
        hecho nuevo: hay que re-evaluarlas (el resto NO se re-mira: ese es el
        ahorro del timestamp_revision)."""
        return [v for v in self.candidatas_enganchadas
                if v.timestamp_revision is None or v.timestamp_revision < fecha_hecho]
