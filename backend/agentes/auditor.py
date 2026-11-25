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

# D5 (doc 74): tipos de concentración/coherencia + los 4 hallazgos de la búsqueda web adversarial.
_TIPO = ["concentracion", "coherencia_memo_peso", "coherencia", "rotacion", "verificacion_fallida",
         "violacion_ips", "omision_material", "evento_proximo", "clausula_filing", "competidor"]
_SEV = ["alta", "media", "baja"]
_S = {"type": "string"}
_MAX_OBJECIONES = 3                   # materialidad (IA2): máx 3/nombre, o el PM aprende a ignorarlas

# web acotada (IA2): búsqueda PARA REFUTAR, no para entender → pocas, dirigidas por checklist.
WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 5}


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

EMITIR_AUDITORIA_TOOL = {
    "name": "emitir_auditoria",
    "description": "Emití tus objeciones (máx 3, materiales). Es tu única salida; llamala cuando terminaste.",
    "input_schema": _PAYLOAD_SCHEMA,
}


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
                ips_violaciones: list[Violacion] | None = None, cartera_analisis: str = "",
                controles_deterministas: list[str] | None = None, max_tokens: int = 2048) -> AuditReport:
        cartera_txt = ("\n".join(f"- {t}: {w:.1%}" for t, w in sorted(cartera_actual.items()))
                       or "(cartera vacía)")
        _v = {t: (v or "").lower() for t, v in (verif_por_ticker or {}).items()}
        fails = [t for t, v in _v.items() if v == "fail"]
        fails_txt = ", ".join(fails) if fails else "(ninguno con FAIL)"
        # P1.4 (doc 91): surface los REVIEW (parcial) — el PM NO debe tratarlos como PASS (caso EXE/VST/EME).
        reviews = [t for t, v in _v.items() if v == "review"]
        reviews_txt = ", ".join(reviews) if reviews else "(ninguno en REVIEW)"
        # P1.4 — CONTROLES DETERMINISTAS (capa 1): lo que el código YA detectó en el gate (bloqueos por verificación,
        # stubs sub-piso, datos no reconciliados, entradas fuera de zona). El auditor NO debe ignorarlos.
        ctrl_txt = ("\n".join(f"- {c}" for c in controles_deterministas)
                    if controles_deterministas else "(el código no reportó controles disparados)")
        viol_txt = ("\n".join(f"- {x.regla}: {x.detalle} ({x.tipo})" for x in ips_violaciones)
                    if ips_violaciones else "(sin violaciones del IPS)")
        user = (
            f"Fecha de hoy: {date.today().isoformat()}\n\n"
            f"=== CARTERA ACTUAL (caja {caja_actual:.1%}) ===\n{cartera_txt}\n\n"
            f"=== MEMO MACRO ===\n{memo_macro or '(sin memo)'}\n\n"
            f"=== DECISIÓN DEL PM (operar_ahora={decision.operar_ahora}) ===\n{_render_decision(decision)}\n"
            f"Timing: {decision.razon_timing}\n\n"
            f"=== NOMBRES CON VERIFICACIÓN FALLIDA (FAIL) ===\n{fails_txt}\n\n"
            f"=== NOMBRES EN REVIEW (verificación PARCIAL — el PM NO debe tratarlos como PASS) ===\n{reviews_txt}\n\n"
            f"=== CONTROLES DETERMINISTAS (capa 1 — el código YA los detectó; NO los ignores) ===\n{ctrl_txt}\n\n"
            f"=== VIOLACIONES DEL IPS DETECTADAS POR EL CÓDIGO ===\n{viol_txt}\n\n"
            f"=== ANÁLISIS DE CARTERA (concentración por factor de tesis · tesis cambiadas) ===\n"
            f"{cartera_analisis or '(sin señales de cartera)'}\n\n"
            f"ANTES de concluir 'sin objeciones', confirmá que revisaste los CONTROLES DETERMINISTAS y los REVIEW: "
            f"si el PM actuó (abrió/aumentó) sobre un nombre en FAIL/REVIEW, o lo llamó PASS, o dejó un control "
            f"disparado sin justificar, ESO es una objeción material. Aplicá la MISMA vara económica a todos los "
            f"nombres (no normalices agresivo a uno y no a otro).\n"
            f"Buscá en la web PARA REFUTAR (checklist: eventos vinculantes ≤90d, cláusulas de filings, cambios "
            f"de guidance/capex, acuerdos/competidor). Después llamá a emitir_auditoria. No vetás: objetás con "
            f"predicciones falsables; máx {_MAX_OBJECIONES}, cada una material (cambia un número de D1, un "
            f"falsador o una clasificación), con evidencia (url) y consecuencia."
        )
        payload, _fuentes, meta = self.ag.agentico(
            system=_PROMPT, user=user, tools=[WEB_SEARCH_TOOL, EMITIR_AUDITORIA_TOOL],
            emisor="emitir_auditoria", max_tokens=max_tokens)
        payload = payload or {}
        payload["objeciones"] = (payload.get("objeciones") or [])[:_MAX_OBJECIONES]   # materialidad: cap duro
        payload.setdefault("devuelve_al_pm", bool(payload["objeciones"]))  # robustez: vacío/truncado → sin objeciones
        return AuditReport.model_validate({"meta": meta.model_dump(), **payload})
