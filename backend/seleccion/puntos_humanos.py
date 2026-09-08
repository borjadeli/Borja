"""Los dos puntos humanos + freno endurecido + ruteo relevar-nodo (Bloque C §3, §4;
núcleo §15; traspaso §3.7).

Dos puntos humanos obligatorios, ambos decisión de capital que el operador firma:
  1. Confirmar la cartera que el PM propone (entrada) — ver preflight.py.
  2. Aprobar o FRENAR cada venta que el núcleo recomienda (salida) — acá.

Freno endurecido (núcleo §15): para frenar un disparo de venta, el operador debe
aportar un hecho OCURRIDO y de fuente INDEPENDIENTE de la empresa. Guidance y
press releases propios NO frenan nada. El freno no mata el trigger: pasa a
'frenado' con re-evaluación obligatoria a fecha fija. Frenos acumulados visibles.

PM sidecar (§4): cada disparo de salida gatilla una llamada liviana del PM para
dar contexto al operador. Es FLUJO DE CAPITAL (prioridad, no sujeto al freno de
presupuesto). El PM acompaña; NO decide la venta.

Ruteo relevar-nodo (§3.7): el pedido del PM va al bucket de exploración RESERVADO
de B, no al deep research general. Solo nodo 'confirmado' sin candidata al final
del embudo.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HechoFreno:
    """Hecho con el que el operador intenta frenar una venta (§15)."""
    descripcion: str
    es_ocurrido: bool                 # hecho ocurrido, no promesa/guidance.
    fuente_independiente: bool        # independiente de la empresa (no press release propio).


def evaluar_freno_venta(hecho: HechoFreno) -> dict:
    """¿El hecho alcanza para frenar la venta? (§15). Devuelve {permitido, motivo}.
    Guidance/press releases propios (no independientes) o promesas (no ocurridos)
    NO frenan."""
    if not hecho.es_ocurrido:
        return {"permitido": False, "motivo": "el hecho no ocurrió (promesa/guidance no frena)"}
    if not hecho.fuente_independiente:
        return {"permitido": False, "motivo": "fuente no independiente (la empresa defendiéndose no frena)"}
    return {"permitido": True, "motivo": "hecho ocurrido de fuente independiente"}


@dataclass
class TriggerFrenado:
    """Un trigger de venta frenado por el operador (§15). No se mata: re-evalúa a
    fecha fija; los frenos acumulados quedan visibles."""
    ticker: str
    reeval_fecha: str                 # próximo earnings o +30 días.
    frenos_acumulados: int = 1
    hechos_freno: list[str] = field(default_factory=list)


def frenar_venta(ticker: str, hecho: HechoFreno, reeval_fecha: str,
                 frenado_previo: TriggerFrenado | None = None) -> dict:
    """Aplica el freno endurecido. Si ya estaba frenado, incrementa el contador
    acumulado (huella imposible de no ver, §15). Devuelve {permitido, trigger}."""
    ev = evaluar_freno_venta(hecho)
    if not ev["permitido"]:
        return {"permitido": False, "motivo": ev["motivo"], "trigger": frenado_previo}
    if frenado_previo is None:
        tf = TriggerFrenado(ticker=ticker.upper(), reeval_fecha=reeval_fecha,
                            frenos_acumulados=1, hechos_freno=[hecho.descripcion])
    else:
        tf = frenado_previo
        tf.frenos_acumulados += 1
        tf.reeval_fecha = reeval_fecha
        tf.hechos_freno.append(hecho.descripcion)
    return {"permitido": True, "motivo": ev["motivo"], "trigger": tf}


def rutear_relevar_nodo(pm_relevar: dict, estado_nodo: str,
                        candidata_al_final_del_embudo: bool) -> dict:
    """§3.7 — el pedido de relevar-nodo del PM va al bucket de exploración reservado
    de B, NO al deep research general. Condición: nodo 'confirmado' y sin candidata
    que haya llegado al final del embudo (no se releva un 'promesa' por corazonada).

    Devuelve {ruteado, destino, motivo}.
    """
    if not pm_relevar.get("pedir"):
        return {"ruteado": False, "destino": None, "motivo": "el PM no pidió relevar nodo"}
    if estado_nodo != "confirmado":
        return {"ruteado": False, "destino": None,
                "motivo": f"nodo en '{estado_nodo}': solo se releva un 'confirmado'"}
    if candidata_al_final_del_embudo:
        return {"ruteado": False, "destino": None,
                "motivo": "ya hay candidata al final del embudo para ese nodo"}
    return {"ruteado": True, "destino": "bucket_exploracion_reservado",
            "motivo": "asíncrono: dispara Discovery exploración sin frenar la cartera de hoy"}


def pm_sidecar_en_venta(ticker: str) -> dict:
    """§4 — cada disparo de salida gatilla una llamada liviana del PM para contexto.
    Es FLUJO DE CAPITAL (prioridad sobre deep research; no sujeto al freno de
    presupuesto). El PM acompaña, NO decide la venta."""
    return {"ticker": ticker.upper(), "tipo": "pm_sidecar", "flujo_capital": True,
            "decide_venta": False}
