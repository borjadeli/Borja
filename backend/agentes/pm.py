"""Agente PM — Portfolio Manager (v2 Fase 4, doc 55 §1.2 + §4).

Opus 5.5. Ve dossiers vigentes (PASS/REVIEW) + cartera + memo macro + su hit-rate de falsadores + flags de
supervivencia, y decide la cartera. **El PM sizea; el determinismo NO impone tamaño** (doc 51). Recibe el
IPS como **tool de dry-run** (`validar_ips` → violaciones + holguras exactas) durante su razonamiento; el
gate final (duro) y el clip a cash los aplica el orquestador, no este agente. Su única salida es la tool
`emitir_decision` → `PMDecision`.

Sin web: el PM decide sobre evidencia ya verificada (el research agéntico lo hizo el Analista).
"""
from __future__ import annotations

import json
from pathlib import Path

from backend.agentes.base import Agente
from backend.agentes.ips import IPS, ContextoTicker
from backend.agentes.schemas import AgentMeta, Dossier, PMDecision, VerificationReport

PROMPT_VERSION = "pm_v1"
_PROMPT = (Path(__file__).resolve().parent.parent.parent / "prompts" / "pm_v1.md").read_text()

_ACCION = ["comprar", "vender", "recortar", "aumentar", "mantener", "caja"]
_FLAG_ACCION = ["acepta", "reduce", "no_opera"]
_S = {"type": "string"}
_N = {"type": "number"}


def _obj(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": required or list(props),
            "additionalProperties": False}


def _emitir_decision_schema() -> dict:
    falsador = _obj({"afirmacion": _S, "fecha_limite": _S, "que_lo_mataria": _S})
    # Sin `dossier_hash`: el PM referencia por ticker; el orquestador rellena el hash al escribir el ledger
    # (que el LLM copie un hex de 16 chars es frágil e innecesario).
    accion = _obj({
        "ticker": _S, "accion": {"type": "string", "enum": _ACCION},
        "peso_objetivo": _N, "conviccion_0_1": _N, "por_que_ese_tamano": _S,
        "tesis": _S, "falsador": falsador, "que_me_haria_vender": _S,
    })
    respuesta_flag = _obj({"flag_id": _S, "accion": {"type": "string", "enum": _FLAG_ACCION}, "motivo": _S})
    return _obj({
        "acciones": {"type": "array", "items": accion},
        "respuestas_flags": {"type": "array", "items": respuesta_flag},
        "operar_ahora": {"type": "boolean"},
        "razon_timing": _S,
    })


EMITIR_DECISION_TOOL = {
    "name": "emitir_decision",
    "description": "Emití la decisión de cartera final. Es tu única salida; llamala cuando terminaste.",
    "strict": True,
    "input_schema": _emitir_decision_schema(),
}

# Dry-run del IPS: pesos es un mapa dinámico ticker→fracción → tool NO-strict (additionalProperties number).
VALIDAR_IPS_TOOL = {
    "name": "validar_ips",
    "description": ("Validá una cartera-objetivo contra el IPS ANTES de emitir. Pasá `pesos` (ticker→fracción "
                    "0-1) y `ops_semana`. Devuelve caja resultante + violaciones con holgura exacta."),
    "input_schema": {
        "type": "object",
        "properties": {
            "pesos": {"type": "object", "additionalProperties": {"type": "number"}},
            "ops_semana": {"type": "integer"},
        },
        "required": ["pesos"],
    },
}


def _render_dossiers(dossiers: list[tuple[Dossier, VerificationReport]]) -> str:
    if not dossiers:
        return "(sin dossiers vigentes)"
    out = []
    for d, v in dossiers:
        out.append(
            f"### {d.ticker}  [{v.veredicto.upper()}]  (convicción analista {d.conviccion_0_1:.2f})\n"
            f"- Negocio/cuello: {d.negocio_y_posicion_cuello}\n"
            f"- Valuación que exige el precio: {d.valuacion_que_exige_el_precio}\n"
            f"- Bull: {d.bull.tesis}\n- Bear: {d.bear.tesis}\n"
            f"- Falsador del analista: {d.falsador.afirmacion} (límite {d.falsador.fecha_limite})\n"
            f"- Red flags: {', '.join(f'{r.tipo}[{r.severidad}]' for r in d.red_flags) or 'ninguna'}")
    return "\n\n".join(out)


def _render_flags(dossiers: list[tuple[Dossier, VerificationReport]]) -> tuple[str, list[str]]:
    flags: list[str] = []
    lineas: list[str] = []
    for _d, v in dossiers:
        for f in v.flags_supervivencia:
            fid = f"{v.ticker}:{f}"
            flags.append(fid)
            lineas.append(f"- {fid}")
    return ("\n".join(lineas) if lineas else "(sin flags de supervivencia)"), flags


class PM:
    def __init__(self, agente: Agente, ips: IPS):
        self.ag = agente
        self.ips = ips

    def _handler_validar(self, contexto: dict[str, ContextoTicker]):
        def _validar(entrada: dict) -> str:
            pesos = {k.upper(): float(val) for k, val in (entrada.get("pesos") or {}).items()
                     if _finito(val) and float(val) > 0}
            ops = int(entrada.get("ops_semana", 0) or 0)
            caja = round(1.0 - sum(pesos.values()), 6)
            viol = self.ips.validar(pesos, contexto, caja=caja, ops_semana=ops)
            return json.dumps({
                "caja_resultante": caja,
                "admisible": self.ips.admisible(viol),
                "violaciones": [{"regla": x.regla, "detalle": x.detalle, "holgura": x.holgura, "tipo": x.tipo}
                                for x in viol],
            }, ensure_ascii=False)
        return _validar

    def decidir(self, *, dossiers: list[tuple[Dossier, VerificationReport]],
                cartera_actual: dict[str, float], caja_actual: float,
                contexto: dict[str, ContextoTicker], memo_macro: str = "",
                hit_rate_resumen: str = "", max_tokens: int = 4096) -> PMDecision:
        flags_txt, _flags = _render_flags(dossiers)
        cartera_txt = ("\n".join(f"- {t}: {w:.1%}" for t, w in sorted(cartera_actual.items()))
                       or "(cartera vacía)")
        user = (
            f"=== CARTERA ACTUAL (caja {caja_actual:.1%}) ===\n{cartera_txt}\n\n"
            f"=== MEMO MACRO ===\n{memo_macro or '(sin memo)'}\n\n"
            f"=== TU TRACK RECORD (información, no instrucción) ===\n{hit_rate_resumen or '(sin histórico aún)'}\n\n"
            f"=== DOSSIERS VIGENTES ===\n{_render_dossiers(dossiers)}\n\n"
            f"=== FLAGS DE SUPERVIVENCIA (respondé a cada uno) ===\n{flags_txt}\n\n"
            f"Usá validar_ips para chequear tu propuesta y después llamá a emitir_decision."
        )
        payload, meta = self.ag.conversacion_tools(
            system=_PROMPT, user=user, tools=[VALIDAR_IPS_TOOL, EMITIR_DECISION_TOOL],
            emisor="emitir_decision", manejadores={"validar_ips": self._handler_validar(contexto)},
            max_tokens=max_tokens,
        )
        if payload is None:                         # no emitió ni tras el empujón → NO_ACTION explícito
            return PMDecision(meta=meta, acciones=[], respuestas_flags=[], operar_ahora=False,
                              razon_timing="el PM no emitió una decisión (sin acción)")
        for a in payload.get("acciones", []):       # acotar numéricos (el schema no fija rango)
            a["peso_objetivo"] = _clamp(a.get("peso_objetivo", 0.0))
            a["conviccion_0_1"] = _clamp(a.get("conviccion_0_1", 0.0))
        return PMDecision.model_validate({"meta": meta.model_dump(), **payload})


def _finito(x) -> bool:
    try:
        f = float(x)
        return f == f and f not in (float("inf"), float("-inf"))
    except (TypeError, ValueError):
        return False


def _clamp(x, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(x))) if _finito(x) else lo
