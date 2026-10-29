"""Agente Auditor (v2 Fase 4, doc 55 §1.3 + §4.4) — cuestiona al PM, SIN veto.

Opus 5.5, contexto separado, sin web. Revisa una `PMDecision` y emite objeciones como **predicciones
falsables** (se puntúan ex-post en el ledger; tras N desacuerdos se decide con datos si merece veto —no a
priori). El Auditor NO reescribe la cartera ni impone tamaños. Lo que es número (turnover/holding/
concentración) lo maneja el IPS; el Auditor aporta el juicio que el número no captura (p.ej. "N nombres =
1 apuesta macro"). La demora de 1 ciclo ante objeción alta sobre un AUMENTO la aplica el orquestador.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from backend.agentes.base import Agente
from backend.agentes.ips import Violacion
from backend.agentes.schemas import AuditReport, PMDecision

PROMPT_VERSION = "auditor_v1"
_PROMPT = (Path(__file__).resolve().parent.parent.parent / "prompts" / "auditor_v1.md").read_text()

_TIPO = ["concentracion", "coherencia_memo_peso", "rotacion", "verificacion_fallida", "violacion_ips"]
_SEV = ["alta", "media", "baja"]
_S = {"type": "string"}


def _obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


_PAYLOAD_SCHEMA = _obj({
    "objeciones": {"type": "array", "items": _obj({
        "tipo": {"type": "string", "enum": _TIPO},
        "detalle": _S,
        "severidad": {"type": "string", "enum": _SEV},
    })},
    "devuelve_al_pm": {"type": "boolean"},
})


def _render_decision(decision: PMDecision) -> str:
    if not decision.acciones:
        return "(sin acciones — el PM no opera)"
    return "\n".join(
        f"- {a.ticker}: {a.accion} → peso_objetivo {a.peso_objetivo:.1%} (convicción {a.conviccion_0_1:.2f}); "
        f"tesis: {a.tesis}" for a in decision.acciones)


class Auditor:
    def __init__(self, agente: Agente):
        self.ag = agente

    def auditar(self, decision: PMDecision, *, cartera_actual: dict[str, float], caja_actual: float,
                memo_macro: str = "", verif_por_ticker: dict[str, str] | None = None,
                ips_violaciones: list[Violacion] | None = None, max_tokens: int = 1024) -> AuditReport:
        cartera_txt = ("\n".join(f"- {t}: {w:.1%}" for t, w in sorted(cartera_actual.items()))
                       or "(cartera vacía)")
        fails = [t for t, v in (verif_por_ticker or {}).items() if v == "fail"]
        fails_txt = ", ".join(fails) if fails else "(ninguno con FAIL)"
        viol_txt = ("\n".join(f"- {x.regla}: {x.detalle} ({x.tipo})" for x in ips_violaciones)
                    if ips_violaciones else "(sin violaciones del IPS)")
        user = (
            f"Fecha de hoy: {date.today().isoformat()}\n\n"
            f"=== CARTERA ACTUAL (caja {caja_actual:.1%}) ===\n{cartera_txt}\n\n"
            f"=== MEMO MACRO ===\n{memo_macro or '(sin memo)'}\n\n"
            f"=== DECISIÓN DEL PM (operar_ahora={decision.operar_ahora}) ===\n{_render_decision(decision)}\n"
            f"Timing: {decision.razon_timing}\n\n"
            f"=== NOMBRES CON VERIFICACIÓN FALLIDA (FAIL) ===\n{fails_txt}\n\n"
            f"=== VIOLACIONES DEL IPS DETECTADAS POR EL CÓDIGO ===\n{viol_txt}\n\n"
            f"Revisá y emití tus objeciones (o ninguna). Recordá: no vetás, objetás con predicciones falsables."
        )
        payload, meta = self.ag.estructurado(system=_PROMPT, user=user,
                                              payload_schema=_PAYLOAD_SCHEMA, max_tokens=max_tokens)
        return AuditReport.model_validate({"meta": meta.model_dump(), **payload})
