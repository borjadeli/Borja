"""Paquete de AUDITORÍA del sistema completo (doc 91 / pedido del operador 2026-11-26) — para mandar a IAs
independientes a auditar en 4 ejes: (1) código/¿funciona?, (2) sistema de inversión/¿la estructura de agentes sirve?,
(3) análisis de empresas/¿es bueno?, (4) selección/¿el PM optimiza la cartera en el tiempo?.

Arma UN markdown autocontenido desde los datos REALES (DB + dossiers cacheados + ledger de decisiones + fichas + cola
de research) + un replay en SOMBRA (qué habría decidido la capa P1 fail-closed). NO corre LLM, NO aplica nada. $0.

  .venv/bin/python -m ops.backup_auditoria                 # ciclo = el más reciente del ledger
  .venv/bin/python -m ops.backup_auditoria --ciclo 2026-11-25
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_DB = _REPO / "data" / "borja.db"
_CACHE = _REPO / "data" / "cache_dossiers_v2.json"
_FICHAS = _REPO / "data" / "fichas_v2.json"
_QUEUE = _REPO / "data" / "research_queue.json"
_LEDGER = _REPO / "data" / "ledger_decisiones_v2.jsonl"
_OUT = _REPO / "data" / "corridas"


def _load(p, default):
    try:
        return json.loads(Path(p).read_text())
    except Exception:  # noqa: BLE001
        return default


def _decisiones(ciclo: str | None) -> tuple[str, list[dict]]:
    regs = []
    if _LEDGER.exists():
        for ln in _LEDGER.read_text().splitlines():
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if r.get("tipo") == "decision":
                regs.append(r)
    if ciclo is None:
        ciclos = sorted({r.get("ciclo") for r in regs if r.get("ciclo")})
        ciclo = ciclos[-1] if ciclos else date.today().isoformat()
    return ciclo, [r for r in regs if r.get("ciclo") == ciclo]


def _universo() -> dict:
    out = {"total": 0, "por_estado": {}, "nombres": []}
    if not _DB.exists():
        return out
    c = sqlite3.connect(str(_DB))
    try:
        out["total"] = c.execute("select count(*) from nx_empresa").fetchone()[0]
        out["por_estado"] = dict(c.execute("select estado, count(*) from nx_empresa group by estado").fetchall())
        out["nombres"] = [r[0] for r in c.execute("select ticker from nx_empresa order by ticker")]
    except Exception:  # noqa: BLE001
        pass
    c.close()
    return out


def _shadow(dossiers: dict, decisiones: list[dict]) -> list[dict]:
    """Replay en sombra: por cada decisión con dossier cacheado, qué habría decidido la capa P1 fail-closed."""
    try:
        from backend.agentes.ips import IPS
        from backend.agentes.schemas import Dossier
        from backend.agentes.harness_sombra import evaluar_decision_sombra, ACCION_PM_A_PERMISO
        cfg = IPS.cargar().cfg
    except Exception as e:  # noqa: BLE001
        return [{"error": f"no se pudo cargar la capa de sombra: {e}"}]
    out = []
    for d in decisiones:
        tk = (d.get("ticker") or "").upper()
        ent = dossiers.get(tk)
        if not ent:
            continue
        try:
            dossier = Dossier.model_validate(ent["dossier"])
            accion = ACCION_PM_A_PERMISO.get(d.get("accion", ""), d.get("accion", ""))
            ver = evaluar_decision_sombra(dossier, cfg=cfg, verif=(ent.get("verif") or {}).get("veredicto"),
                                          accion=accion, peso_objetivo=d.get("peso_objetivo"),
                                          precio_pack=d.get("precio"))
            out.append({"ticker": tk, "accion_pm": d.get("accion"), "permiso_p1": ver.permiso,
                        "arquetipo": ver.arquetipo, "banda": ver.banda, "cap": ver.cap,
                        "faltan": ver.missing_fields[:4]})
        except Exception as e:  # noqa: BLE001
            out.append({"ticker": tk, "error": str(e)[:120]})
    return out


def construir(ciclo: str | None = None) -> str:
    ciclo, decs = _decisiones(ciclo)
    uni = _universo()
    dossiers = _load(_CACHE, {})
    fichas = _load(_FICHAS, {})
    queue = _load(_QUEUE, [])
    shadow = _shadow(dossiers, decs)

    L: list[str] = []
    L.append(f"# BORJA — Auditoría del UNIVERSO y del MODUS OPERANDI del PM · ciclo {ciclo}\n")
    L.append("> **Foco acotado (NO re-auditar todo).** La calidad del comité (Analista/Verificador/dossiers) y las "
             "decisiones de UNA corrida ya se triangularon (doc 91). Acá queremos auditar la capa que NO revisamos: "
             "**cómo se administra el universo** y **cómo opera el PM** — en particular, **¿el PM tiene acceso a toda "
             "la información que necesita para elegir bien?**. Preguntas concretas para el auditor:\n")
    L.append("- **Universo**: ¿tiene sentido cómo entran/salen las empresas? ¿El pool que el PM 've' es el correcto, "
             "o hay buenas oportunidades que nunca llegan a su mesa? ¿La ambigüedad nx_empresa vs fichas es un problema?")
    L.append("- **Selección de deep**: ¿el Triage (señales deterministas) + el score de oportunidad eligen bien a "
             "quién investigar, o dejan afuera nombres que deberían subir?")
    L.append("- **Insumo del PM**: ¿ve lo suficiente (dossiers deepeados + fichas + shortlist con score + cartera), o "
             "le falta contexto para comparar oportunidades entre sí y no derivar a value cíclico?")
    L.append("- **Alertas**: ¿es razonable que las mejoras (precio a zona COMPRA, filing material) disparen revisión, "
             "pero una mejora de fundamentals fuera de un filing no? ¿Falta algo?\n")
    L.append("> El código es la fuente de verdad (repo en GitHub); esto orienta. Lo de abajo son DATOS REALES del sistema.\n")

    L.append("## 0. Arquitectura del pipeline (dónde mirar en el código)\n")
    L.append("```\nUNIVERSO (nx_empresa) → señales deterministas → TRIAGE (elige deep) → comité "
             "[Analista(Opus+web)→Verificador] → dossier+verif (cache) → PM decide → gate IPS → Auditor → paper\n"
             "                                            ↘ cola de research (operador/PM/discovery) → ficha\n"
             "                                                                        ↘ SOMBRA P1 (fail-closed, loguea, no aplica)\n```")
    L.append("- Universo + señales: `backend/agentes/universo.py` · entrada: `backend/ingreso/` (gate: market cap "
             "≥$50M, liquidez, jurisdicción; el nodo del mapa YA NO gatea — es insumo).")
    L.append("- Triage/comité: `backend/agentes/orquestador.py` · Analista: `backend/agentes/analista.py` + "
             "`prompts/analista_v1.md` · Verificador: `backend/agentes/verificador.py`.")
    L.append("- PM: `backend/agentes/pm.py` + `prompts/pm_v1.md` · runner: `backend/agentes/runner_semanal.py` · "
             "gate IPS: `backend/agentes/orquestador_decision.py` · ledger: `backend/ledger/`.")
    L.append("- Capa de decisión fail-closed (P1, en sombra): `backend/agentes/{permiso_ejecucion,banda,arquetipo,"
             "caps_posicion,comparacion_rotacion,evaluar_sombra,harness_sombra}.py` (doc 91 §8.ter).\n")

    L.append("## 1. Universo (el pool que el Triage recorre)\n")
    L.append(f"- **{uni['total']} empresas** · por estado: {uni['por_estado']}")
    L.append(f"- **OJO (hallazgo):** todas en un solo estado → la máquina de estados no promueve/retira. "
             f"Además 'universo' es ambiguo: `nx_empresa` ({uni['total']}) ≠ los nombres con **ficha** "
             f"({len(fichas)}, lo que el PM realmente ve). Las altas del operador van a la **cola** → ficha, NO a nx_empresa.")
    L.append(f"- Nombres: {', '.join(uni['nombres'][:60])}{' …' if len(uni['nombres'])>60 else ''}\n")

    L.append("## 2. Cola de research (cómo el operador/PM/discovery piden deep)\n")
    from collections import Counter
    est = dict(Counter(i.get("estado") for i in queue))
    orig = dict(Counter(tuple(i.get("origen")) if isinstance(i.get("origen"), list) else i.get("origen") for i in queue))
    L.append(f"- {len(queue)} items · por estado: {est} · por origen: {orig}")
    pend = [i for i in queue if i.get("estado") == "PENDIENTE"]
    L.append(f"- Pendientes (drenan con presupuesto, P0 primero): {', '.join(i['ticker'] for i in pend[:40])}\n")

    L.append("## 3. Qué VE el PM (su insumo real)\n")
    L.append(f"- **Dossiers deepeados este ciclo** (investigación completa): {len(dossiers)} nombres.")
    L.append("- **Fichas vivas** (memoria: zona/tesis de nombres ya analizados) + **cartera** + lista con SCORE de "
             "oportunidades ficha-less que puede pedir a deep. **NO ve las " + str(uni['total']) + " en detalle.**")
    L.append("- Convicción del Analista por nombre (del cache):")
    for tk, ent in list(dossiers.items())[:30]:
        dd = ent.get("dossier", {})
        L.append(f"  - {tk}: convicción {dd.get('conviccion_0_1')} · verif {(ent.get('verif') or {}).get('veredicto')}"
                 f" · zona ficha: {_zona_ficha(fichas.get(tk))}")
    L.append("")

    L.append("## 4. Decisiones del PM (ciclo " + ciclo + ")\n")
    if decs:
        for d in decs:
            L.append(f"- **{d.get('ticker')}** → {d.get('accion')} (peso {d.get('peso_objetivo')}) · "
                     f"{(d.get('tesis') or '')[:120]}")
    else:
        L.append("- (sin decisiones registradas para este ciclo en el ledger v2)")
    L.append("")

    L.append("## 5. SOMBRA P1 — qué habría decidido la capa fail-closed (NO aplica)\n")
    L.append("> 'Lo que *debería* suceder' según la capa determinista que limita al PM. Hoy la mayoría BLOQUEA porque "
             "los dossiers cacheados son PREVIOS al bloque económico `underwriting` (el Analista recién ahora lo emite) "
             "→ fail-closed correcto: no autoriza sobre datos incompletos. Mide el circuito, no todavía la calidad.")
    for s in shadow:
        if s.get("error"):
            L.append(f"  - {s.get('ticker','?')}: error — {s['error']}")
        else:
            L.append(f"  - {s['ticker']}: PM={s['accion_pm']} → P1={s['permiso_p1']} "
                     f"(arq {s['arquetipo']}, banda {s['banda']}, cap {s['cap']:.1%}) · faltan: {s['faltan']}")
    L.append("")

    L.append("## 6. Lo que YA sabemos (para que el auditor NO lo repita) y lo que queremos de él\n")
    L.append("**Ya triangulado (doc 91) — no hace falta re-auditar:** el comité no le gana a un Opus+web solo; falta "
             "comparación económica entre oportunidades; deriva a value cíclico; falsadores mal diseñados; el edge no "
             "está demostrado. Eso ya lo tenemos.\n")
    L.append("**Lo que SÍ queremos auditar acá (nuevo):**")
    for h in [
        "ADMINISTRACIÓN DEL UNIVERSO: entrada (gate), salida (estados), costo, y la ambigüedad nx_empresa vs fichas. "
        "¿La máquina de estados que no se mueve (todo 'Candidata') es un bug o es inocuo?",
        "VISIBILIDAD DEL PM: ¿el PM ve lo suficiente para decidir bien? Un nombre nunca-deepeado y que el score no "
        "sube a la shortlist es INVISIBLE para él. ¿Ese filtro (Triage + score) es el cuello de botella de la calidad?",
        "FLUJO operador→universo: las altas del operador van a la cola→ficha, NO a nx_empresa. ¿Deberían conectarse?",
        "ALERTAS: simétricas en precio (zona COMPRA alerta) pero una mejora de fundamentals fuera de un filing no "
        "dispara nada. ¿Falta un gatillo de mejora fundamental?",
    ]:
        L.append(f"- {h}")
    L.append("")
    return "\n".join(L)


def _zona_ficha(f) -> str:
    if not isinstance(f, dict):
        return "—"
    lat = f.get("latido") or {}
    return lat.get("zona") or f.get("zona") or "—"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ciclo", default=None)
    a = ap.parse_args()
    md = construir(a.ciclo)
    _OUT.mkdir(parents=True, exist_ok=True)
    ciclo = a.ciclo or "latest"
    out = _OUT / f"auditoria_sistema_{ciclo}.md"
    out.write_text(md, encoding="utf-8")
    print(f"paquete de auditoría escrito: {out} ({len(md)} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
