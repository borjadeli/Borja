"""Bundle AUTOCONTENIDO para auditar BORJA con IAs independientes (operador 2026-11-26). Concatena en UN archivo:
(A) el doc de orientación de la auditoría (4 ejes), (B) el backup de la última corrida (dossiers completos +
decisiones del PM), (C) el CÓDIGO core del pipeline de decisión (prompts + agentes + ingreso + ledger).

El resultado es grande (~0.7MB): sirve para IAs que aceptan subir archivos. Para chat, pegá solo la parte (A)
+ (B) y compartí el repo para (C). $0, no corre LLM.

  .venv/bin/python -m ops.backup_auditoria        # (A) primero, genera el doc de orientación
  .venv/bin/python -m ops.bundle_auditoria        # (B)+(C), arma el bundle
"""
from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_OUT = _REPO / "data" / "corridas"

# (C) el código del PIPELINE DE DECISIÓN, en orden de lectura. NO incluye tests ni _archivo. nucleo/ (calculadoras)
# queda en el repo (grande); se referencia.
_CODIGO = [
    "prompts/analista_v1.md", "prompts/pm_v1.md", "prompts/auditor_v1.md", "prompts/triage_v1.md",
    "backend/agentes/universo.py", "backend/ingreso/universo.py", "backend/ingreso/filtro0.py",
    "backend/ingreso/flujo.py", "backend/agentes/orquestador.py", "backend/agentes/analista.py",
    "backend/agentes/verificador.py", "backend/agentes/pm.py", "backend/agentes/runner_semanal.py",
    "backend/agentes/orquestador_decision.py", "backend/agentes/research_queue.py", "backend/agentes/drenaje.py",
    "backend/agentes/ficha_store.py", "backend/agentes/event_monitor.py", "backend/agentes/schemas.py",
    # capa de decisión fail-closed (P1, sombra)
    "backend/agentes/permiso_ejecucion.py", "backend/agentes/banda.py", "backend/agentes/arquetipo.py",
    "backend/agentes/caps_posicion.py", "backend/agentes/comparacion_rotacion.py", "backend/agentes/numeros.py",
    "backend/agentes/evaluar_sombra.py", "backend/agentes/harness_sombra.py", "backend/agentes/shadow_log.py",
    "backend/ledger/core.py", "backend/ledger/models.py", "backend/ledger/entidades.py",
]


def _ultimo_backup_corrida() -> Path | None:
    cands = sorted(_OUT.glob("backup_comite_*.md"))
    return cands[-1] if cands else None


def construir() -> str:
    L: list[str] = []
    L.append("# BORJA — BUNDLE DE AUDITORÍA (autocontenido)\n")
    L.append("Tres partes: **(A)** orientación de la auditoría · **(B)** última corrida (dossiers + decisiones) · "
             "**(C)** código del pipeline de decisión. El código es la fuente de verdad.\n\n---\n")

    # (A) orientación
    doc = _OUT / "auditoria_sistema_latest.md"
    L.append("# PARTE A — ORIENTACIÓN\n")
    L.append(doc.read_text(encoding="utf-8") if doc.exists()
             else "_(correr `ops.backup_auditoria` primero)_")
    L.append("\n\n---\n")

    # (B) última corrida
    L.append("# PARTE B — ÚLTIMA CORRIDA (dossiers completos + decisiones)\n")
    b = _ultimo_backup_corrida()
    L.append(b.read_text(encoding="utf-8") if b else "_(sin backup de corrida; correr `ops.backup_corrida`)_")
    L.append("\n\n---\n")

    # (C) código
    L.append("# PARTE C — CÓDIGO DEL PIPELINE DE DECISIÓN\n")
    L.append("> Orden de lectura: prompts → universo/ingreso → orquestador/agentes → PM/runner/gate → "
             "capa fail-closed (sombra) → ledger. (Las calculadoras `backend/nucleo/` quedan en el repo.)\n")
    for rel in _CODIGO:
        p = _REPO / rel
        L.append(f"\n\n{'='*100}\n### FILE: {rel}\n{'='*100}\n")
        if p.exists():
            lang = "python" if rel.endswith(".py") else "markdown"
            L.append(f"```{lang}\n{p.read_text(encoding='utf-8')}\n```")
        else:
            L.append("_(no encontrado)_")
    return "\n".join(L)


def main() -> int:
    md = construir()
    _OUT.mkdir(parents=True, exist_ok=True)
    out = _OUT / "bundle_auditoria.md"
    out.write_text(md, encoding="utf-8")
    print(f"bundle escrito: {out} ({len(md):,} chars ≈ {len(md)//4:,} tokens aprox)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
