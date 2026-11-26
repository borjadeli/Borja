"""P1 (doc 91 §8) — HARNESS de sombra: mapea un Dossier (+ la decisión del PM + el pack) a los insumos del
orquestador `evaluar_sombra`, CONSUMIENDO el bloque económico estructurado del Analista (`dossier.underwriting`) —
no lo reinterpreta de la narrativa (IA2 §3.2). Lo que el Analista no emitió queda None → fail-closed.

Esta es la pieza que conecta el circuito real con la capa P1 en sombra: dada una decisión del comité, computa "qué
habría decidido P1" sin aplicarlo. Determinista, $0. (El logging del shadow_decision + el registro de contrafactuales
bloqueados — IA2 §3.5/3.6 — es el siguiente paso; este módulo es el consumidor.)
"""
from __future__ import annotations

from backend.agentes.evaluar_sombra import VeredictoSombra, evaluar_sombra

# insumos (por keyword) que es válido que el falsador DURO mida, POR arquetipo. Un falsador que mide el PPA de VST
# (power/infra) NO liga la métrica de una cíclica (IA2 review-2: la 'opción gratis' pasaba como ligada).
_INSUMOS_ARQUETIPO = {
    "ciclica": ("owner_fcf", "fcf_a_curva", "mitad_ciclo", "normalized_owner", "fcf_normal", "curva", "margen_op"),
    "infra": ("cobertura", "contratado", "fcfe", "ppa", "backlog", "ig"),
    "compounder": ("roic", "g_sost", "g_exigido", "reinvers", "incremental"),
    "pre_revenue": ("funding", "runway", "p_implicita", "p_razonada", "dilucion", "burn", "caja"),
}
# insumos de banda que DEPENDEN del precio: si el precio se movió desde que el Analista los escribió, se descartan.
_PRECIO_DEPENDIENTES = ("g_exigido", "cobertura_ig_bajo", "p_implicita_alto", "p_implicita_bajo", "p_razonada_bajo")
_DERIVA_MAX = 0.10


def _falsador_liga_metrica(metrica, arquetipo) -> bool:
    """¿El falsador mide un INSUMO del arquetipo (no solo 'tiene una vara con una métrica')?"""
    if not metrica or not arquetipo:
        return False
    m = str(metrica).lower()
    return any(k in m for k in _INSUMOS_ARQUETIPO.get(arquetipo, ()))


def insumos_de_dossier(dossier, *, verif: str, accion: str, motivo: str = "discrecional",
                       peso_objetivo: float | None = None, tier_declarado: str | None = None,
                       comparacion: str | None = None, bloqueo_datos=None, sig_pack: dict | None = None,
                       precio_pack: float | None = None) -> dict:
    """Arma el `d` que consume `evaluar_sombra` desde un Dossier verificado + la decisión del PM. `sig_pack` =
    señales de arquetipo del data pack (fallback si el Analista no confirmó el arquetipo). `precio_pack` = el precio
    del DÍA: la banda se recalcula con éste, NUNCA con el que escribió el Analista (mata las 'zonas viejas')."""
    uw = getattr(dossier, "underwriting", None)
    arq_conf = getattr(uw, "arquetipo_confirmado", None) if uw else None

    banda_inputs = dict(getattr(uw, "banda_inputs", None) or {})
    banda_inputs.pop("precio", None)               # el precio del Analista NO se usa
    # si el precio se movió >10% desde la referencia del Analista, los insumos dependientes del precio no sirven.
    precio_ref = getattr(uw, "precio_referencia", None) if uw else None
    if precio_ref and precio_pack is not None and precio_ref > 0 and abs(precio_pack / precio_ref - 1) > _DERIVA_MAX:
        for k in _PRECIO_DEPENDIENTES:
            banda_inputs.pop(k, None)
    if precio_pack is not None:
        banda_inputs["precio"] = precio_pack       # el precio del día

    metrica_presente = bool(uw and getattr(uw, "metrica_obligatoria_bajo", None) is not None)
    fals = getattr(dossier, "falsador", None)
    vara = getattr(fals, "vara_externa", None) if fals else None
    metrica_falsador = getattr(vara, "metrica", None) if vara else None
    liga = _falsador_liga_metrica(metrica_falsador, arq_conf)
    fals_id = getattr(fals, "id", None) if fals else None      # el id ESTRUCTURADO, no el texto libre de la afirmación
    return {
        "arquetipo_confirmado": arq_conf,
        "sig": sig_pack or {},                     # fallback: el código propone desde el pack si no hay confirmado
        "banda_in": banda_inputs,
        "verif": verif,
        "accion": accion,
        "motivo": motivo,
        "peso_objetivo": peso_objetivo,
        "tier_declarado": tier_declarado,
        "metrica_obligatoria_presente": metrica_presente,
        "falsador_estructurado": bool(liga and fals_id),
        "falsador_id": fals_id if liga else None,
        "falsador_sobre_metrica": bool(liga),
        "comparacion": comparacion,
        # [] = chequeado sin bloqueos (confirmación positiva); el caller pasa la lista si detectó reconciliaciones.
        "bloqueo_datos": list(bloqueo_datos) if bloqueo_datos else [],
    }


def evaluar_decision_sombra(dossier, *, cfg: dict, verif: str, accion: str, **kw) -> VeredictoSombra:
    """Conveniencia: mapea el dossier y corre el orquestador en un paso."""
    return evaluar_sombra(insumos_de_dossier(dossier, verif=verif, accion=accion, **kw), cfg=cfg)


# El PM habla en comprar/vender/recortar/caja; el permiso en abrir/aumentar/reducir/salir. Sin este mapeo el
# shadow vería una acción desconocida y BLOQUEARÍA todo.
ACCION_PM_A_PERMISO = {"comprar": "abrir", "aumentar": "aumentar", "vender": "salir",
                       "recortar": "reducir", "mantener": "mantener", "caja": "salir"}


def registrar_decision_en_sombra(*, ciclo: str, acciones, dossier_por_ticker: dict, verif_por_ticker: dict,
                                 precios: dict, cfg: dict, path=None) -> dict:
    """HOOK listo para el runner (doc 91 §8.ter): por cada PMAccion construye el veredicto P1 en sombra
    (harness→orquestador) y lo loguea append-only. NO toca autoridad; NO aplica nada. Pensado para llamarse
    best-effort (envolver en try/except en el runner: la sombra no debe tumbar el ciclo). Devuelve resumen + registros.

    `acciones` = iterable de PMAccion (usa .ticker/.accion/.peso_objetivo) · `dossier_por_ticker` = {TK: Dossier} ·
    `verif_por_ticker` = {TK: 'pass'/'review'/'fail'} · `precios` = {TK: precio del día}."""
    # import local para no crear ciclo (shadow_log no importa nada de agentes)
    from backend.agentes.shadow_log import construir_shadow_decision, registrar_corrida, resumen_sombra

    registros: list[dict] = []
    for a in acciones:
        tk = str(getattr(a, "ticker", "") or "").upper()
        dossier = dossier_por_ticker.get(tk)
        if dossier is None:                               # sin dossier no hay nada que evaluar en sombra
            continue
        accion = ACCION_PM_A_PERMISO.get(getattr(a, "accion", ""), getattr(a, "accion", ""))
        peso = getattr(a, "peso_objetivo", None)
        ver = evaluar_decision_sombra(dossier, cfg=cfg, verif=verif_por_ticker.get(tk), accion=accion,
                                      motivo="discrecional", peso_objetivo=peso, precio_pack=precios.get(tk))
        registros.append(construir_shadow_decision(ciclo=ciclo, ticker=tk, accion_pm=accion, veredicto=ver,
                                                   peso_propuesto=peso))
    registrar_corrida(registros, path=path)               # invariante registros==decisiones (falla VISIBLE)
    return {"resumen": resumen_sombra(registros), "registros": registros}
