"""Pre-flight de confirmación de cartera + visibilidad factor_macro (Bloque C §3.4,
§3.6, traspaso §7.4).

Aplicación directa de «no congelar conclusiones» al mix del PM. Entre que el PM
arma el mix y el operador confirma puede cambiar el estado (migra un arquetipo y
baja el HardCap, se enfría un nodo, muere una vía 4 por precio, o el núcleo
recomienda vender un ticker del mix). Sin pre-flight, el operador confirmaría una
foto podrida.

NO es pieza nueva (traspaso §7.5): es una VISTA de confirmación. Revalida con las
piezas que el Reloj 1 ya re-deriva. Lo genuinamente nuevo es el GATILLO
(«operador-va-a-confirmar») y el ORDEN DE RESOLUCIÓN ventas-antes-de-entradas,
extendido al CONTEO DE SLOTS (§7.4).

Incluye la visibilidad forzada de factor_macro (§3.6): el operador no puede
confirmar sin ver la concentración. Regenerar el mix re-dispara esa visibilidad.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.nucleo.constantes import MAX_POSICIONES


@dataclass
class LineaMixSnapshot:
    """El «recibo» de lo que el PM vio por línea (traspaso §7.4). El pre-flight
    compara esto contra el estado actual."""
    ticker: str
    es_entrada: bool                       # True = entrada nueva; False = posición viva.
    precio: float | None = None
    hardcap: float | None = None
    estado_nodo: str | None = None
    fecha_ultimo_hecho: str | None = None
    recomendacion_salida_vigente: str | None = None
    factor_macro: str | None = None
    sizing: float | None = None


@dataclass
class EstadoLineaActual:
    """Estado vigente al momento de confirmar (lo trae el Reloj 1 / monitor / mapa)."""
    ticker: str
    precio: float | None = None
    hardcap: float | None = None
    estado_nodo: str | None = None
    fecha_ultimo_hecho: str | None = None
    recomendacion_salida_vigente: str | None = None


# Campos cuyo cambio entre snapshot y actual marca la línea STALE.
_CAMPOS_STALE = ("hardcap", "estado_nodo", "fecha_ultimo_hecho", "recomendacion_salida_vigente")


def _linea_stale(snap: LineaMixSnapshot, actual: EstadoLineaActual) -> list[str]:
    cambios = []
    for campo in _CAMPOS_STALE:
        if getattr(snap, campo) != getattr(actual, campo):
            cambios.append(f"{campo}: {getattr(snap, campo)} → {getattr(actual, campo)}")
    # Precio: stale solo si cambió de forma material (la vía 4/5 lo recalcula).
    if snap.precio and actual.precio:
        if abs(actual.precio - snap.precio) / snap.precio >= 0.05:
            cambios.append(f"precio: {snap.precio} → {actual.precio}")
    return cambios


def factor_macro_concentracion(lineas: list[LineaMixSnapshot]) -> dict[str, float]:
    """§3.6 — concentración de factor_macro entre las posiciones del mix (por sizing).
    Etiqueta NO-decisoria: solo se muestra. NO introduce umbral."""
    conc: dict[str, float] = {}
    for l in lineas:
        if l.factor_macro and l.sizing:
            conc[l.factor_macro] = conc.get(l.factor_macro, 0.0) + l.sizing
    return dict(sorted(conc.items(), key=lambda kv: -kv[1]))


def chequear_preflight(snapshot: list[LineaMixSnapshot], actuales: dict[str, EstadoLineaActual],
                       slots_ocupados: int = 0, max_posiciones: int = MAX_POSICIONES) -> dict:
    """Revalida el mix propuesto contra el estado vigente. Devuelve:

      lineas: [{ticker, es_entrada, stale, cambios, bloqueada_por_slot}]
      ventas_pendientes: tickers con recomendación de salida vigente.
      requiere_regenerar: bool — hay líneas stale → la propuesta debe regenerarse.
      visibilidad_factor_macro: la concentración que el operador DEBE ver (§3.6).
      slots_disponibles_tras_ventas: int.

    Orden de resolución (§7.4): las ventas se resuelven ANTES que las entradas, y
    el acople de SLOTS se respeta — una entrada solo se confirma si su slot sigue
    disponible tras resolver TODAS las ventas pendientes (no solo las del mismo
    ticker). sale_pending bloquea entrada/aumento del mismo ticker.
    """
    ventas_pendientes = [a.ticker for a in actuales.values() if a.recomendacion_salida_vigente]
    # Slots que se liberarían si se ejecutan todas las ventas pendientes que están EN el mix
    # o son posiciones vivas. Conservador: cada venta libera un slot.
    slots_liberados = len(ventas_pendientes)
    slots_disponibles = max_posiciones - slots_ocupados + slots_liberados

    lineas = []
    requiere_regenerar = False
    entradas_confirmables = 0
    for snap in snapshot:
        actual = actuales.get(snap.ticker.upper())
        cambios = _linea_stale(snap, actual) if actual else ["sin estado actual (no comparable)"]
        stale = bool(cambios)
        if stale:
            requiere_regenerar = True

        bloqueada = False
        if snap.es_entrada:
            # sale_pending del mismo ticker bloquea su entrada/aumento (§7.4).
            if snap.ticker in ventas_pendientes:
                bloqueada = True
            # Acople de slots: solo confirma si queda slot tras resolver TODAS las ventas.
            elif entradas_confirmables >= slots_disponibles:
                bloqueada = True
            else:
                entradas_confirmables += 1
        lineas.append({
            "ticker": snap.ticker, "es_entrada": snap.es_entrada,
            "stale": stale, "cambios": cambios, "bloqueada_por_slot": bloqueada,
        })

    return {
        "lineas": lineas,
        "ventas_pendientes": ventas_pendientes,
        "requiere_regenerar": requiere_regenerar,
        "visibilidad_factor_macro": factor_macro_concentracion(snapshot),
        "slots_disponibles_tras_ventas": slots_disponibles,
        # §3.6/§7.4: la confirmación exige haber visto la concentración; si se
        # regenera el mix, se re-dispara esta visibilidad.
        "confirmacion_requiere_ver_factor_macro": True,
    }


@dataclass
class Confirmacion:
    """Estado del paso humano de confirmación. No se confirma sin ver factor_macro
    (§3.6) y resolviendo ventas antes que entradas (§7.4)."""
    factor_macro_visto: bool = False
    ventas_resueltas: bool = False
    notas: list[str] = field(default_factory=list)

    def puede_confirmar(self, preflight: dict) -> dict:
        razones = []
        if not self.factor_macro_visto:
            razones.append("falta ver la concentración de factor_macro (§3.6)")
        if preflight.get("requiere_regenerar"):
            razones.append("hay líneas stale: regenerar el mix (y re-ver factor_macro)")
        if preflight.get("ventas_pendientes") and not self.ventas_resueltas:
            razones.append("resolver las ventas pendientes antes de confirmar entradas (§7.4)")
        if any(l["bloqueada_por_slot"] for l in preflight.get("lineas", [])):
            razones.append("hay entradas bloqueadas por acople de slots (§7.4)")
        return {"puede": not razones, "razones": razones}
