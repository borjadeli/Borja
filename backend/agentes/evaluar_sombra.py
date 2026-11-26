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
    Es el ÚNICO lugar que arma el ExecutionContext tipado y lo COMPUTA desde el dossier; un input malformado NUNCA
    tumba la corrida (se atrapa → BLOQUEAR). No se completan defaults permisivos en los hechos portantes."""
    try:
        return _evaluar_sombra(d, cfg)
    except Exception as e:                         # un string donde va un número no debe tumbar la corrida → BLOQUEAR
        return VeredictoSombra(arquetipo=None, banda=None, tier="?", cap=0.0, liga="error",
                               permiso="BLOQUEAR", motivos=[f"excepción evaluando en sombra: {type(e).__name__}"],
                               missing_fields=["input malformado"])


def _evaluar_sombra(d: dict, cfg: dict) -> VeredictoSombra:
    # el arquetipo CONFIRMADO por el Analista define el método; si no, lo PROPONE el código desde las señales.
    arq_pack = clasificar_arquetipo(d.get("sig") or {})
    arq_conf = d.get("arquetipo_confirmado")
    arq = arq_conf or arq_pack
    banda = calcular_banda(arq, d.get("banda_in") or {}) if arq else None
    # tier: IA2 — es una propiedad DECLARADA por el PM, no se infiere del peso. Para el histórico se propone y se marca.
    tier = d.get("tier_declarado") or ("OPTIONALITY" if (arq == "pre_revenue" or d.get("flag_alta")) else _NUCLEO_DEFAULT)
    cap, liga = cap_posicion(tier=tier, arquetipo=arq, banda=banda, verificacion=d.get("verif"), cfg=cfg)
    # un OVERRIDE de arquetipo del Analista NO puede AGRANDAR el cap respecto del que soporta la señal del pack
    # (caso E&P cíclica → 'compounder': el tope sigue siendo el de la cíclica). Liga el más restrictivo.
    if arq_conf and arq_pack and arq_conf != arq_pack:
        cap_pack, _ = cap_posicion(tier=tier, arquetipo=arq_pack, banda=banda, verificacion=d.get("verif"), cfg=cfg)
        if cap_pack < cap:
            cap, liga = cap_pack, "override_arquetipo_no_agranda_cap"

    banda_in = d.get("banda_in") or {}
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
    if arq == "pre_revenue" and (banda_in.get("p_implicita_alto") is None or banda_in.get("p_razonada_bajo") is None):
        missing.append("p_implícita/p_razonada (margen de la opcionalidad pre_revenue)")

    ctx = {
        "accion": d.get("accion"), "motivo_accion": d.get("motivo"),
        "verificacion": d.get("verif"), "tier": tier, "tiers_cfg": cfg.get("tiers"),
        "arquetipo": arq, "peso_objetivo": d.get("peso_objetivo"), "cap": cap,
        "falsador_id": d.get("falsador_id"),
        "falsador_sobre_metrica": bool(d.get("falsador_sobre_metrica")),
        "metrica_obligatoria_null": not d.get("metrica_obligatoria_presente", False),
        "flags_alta_sin_responder": bool(d.get("flags_alta_sin_responder", False)),
        "crea_stub_o_viola_ips": bool(d.get("crea_stub_o_viola_ips", False)),
        "bloqueo_datos": d.get("bloqueo_datos") if "bloqueo_datos" in d else [],
        "p_implicita_alto": banda_in.get("p_implicita_alto"),
        "p_razonada_bajo": banda_in.get("p_razonada_bajo"),
        "comparacion": d.get("comparacion"),
        "metrica_A_null": banda is None,
        "dossier_del_ciclo": d.get("dossier_del_ciclo", True),
        "evidencia_mecanica": d.get("evidencia_mecanica"),
    }
    permiso, motivos = execution_permission(ctx)
    return VeredictoSombra(arquetipo=arq, banda=banda, tier=tier, cap=cap, liga=liga,
                           permiso=permiso, motivos=motivos, missing_fields=missing)
