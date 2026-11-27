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
    L.append(f"# BORJA — Triangulación del NÚCLEO: ¿es la MEJOR manera de operar? · ciclo {ciclo}\n")
    L.append("> **Esto es el CORAZÓN del sistema y queremos que esté óptimo — no solo que 'funcione'.** El flujo es: "
             "universo → se monitorea → se prioriza quién se investiga a fondo (deep) → el PM decide. Una review previa "
             "(una sola IA) cazó HUECOS; ahora queremos una 2ª voz que juzgue la **CALIDAD DEL DISEÑO** y valide el "
             "camino feliz. Sé escéptico y concreto; el código es la fuente de verdad (repo en GitHub).\n")
    L.append("**Las preguntas que importan (respondé cada una con 'sí/no, por qué, y qué haría distinto'):**")
    L.append("1. **¿Es la MEJOR manera de ADMINISTRAR el universo?** Entrada ($150M–$60B + whitelist de países), salida, "
             "tamaño (hoy ~191, tope 500), costo. ¿El pool que llega al PM es el correcto o se pierden oportunidades?")
    L.append("2. **¿Es la MEJOR manera de MONITOREAR las empresas?** Precio (z-score) + filings nuevos para TODO el "
             "universo cada ciclo; ZONA de compra/venta solo para las que tienen ficha (deep). ¿Alcanza? ¿Qué falta?")
    L.append("3. **¿Es la MEJOR manera de PRIORIZAR quién va a deep?** Triage (señales deterministas + Haiku) → embudo → "
             "cupo + presupuesto. ¿Elige bien a quién gastar el Opus caro, o deja afuera lo que debería subir?")
    L.append("4. **¿El PM tiene la MEJOR información posible para decidir?** Ve: dossiers deepeados + fichas vivas + RADAR "
             "(fichas fuera de zona) + shortlist con score de las sin-ficha + cartera. Compra SOLO con ficha (candado). "
             "¿Le falta algo para comparar oportunidades entre sí y no derivar a value cíclico?")
    L.append("5. **Validá el CAMINO FELIZ (no solo los huecos):** ¿el candado (comprar exige ficha VIGENTE) y el tope de "
             "presupuesto son correctos y robustos? ¿Hay un mejor diseño del control?\n")
    L.append("> **Ya aplicamos 7 fixes de la 1ª review** (abajo, §7) — revisalos: ¿están bien?, ¿rompen algo?\n")

    L.append("## 0. Arquitectura del pipeline (dónde mirar en el código)\n")
    L.append("```\nUNIVERSO (nx_empresa) → señales deterministas → TRIAGE (elige deep) → comité "
             "[Analista(Opus+web)→Verificador] → dossier+verif (cache) → PM decide → gate IPS → Auditor → paper\n"
             "                                            ↘ cola de research (operador/PM/discovery) → ficha\n"
             "                                                                        ↘ SOMBRA P1 (fail-closed, loguea, no aplica)\n```")
    L.append("- Universo + señales: `backend/agentes/universo.py` · entrada: `backend/ingreso/universo.py` (REGLA ÚNICA: "
             "market cap $150M–$60B + whitelist de jurisdicciones; el nodo del mapa es insumo, no gatea).")
    L.append("- Triage/comité: `backend/agentes/orquestador.py` · Analista: `backend/agentes/analista.py` + "
             "`prompts/analista_v1.md` · Verificador: `backend/agentes/verificador.py`.")
    L.append("- PM: `backend/agentes/pm.py` + `prompts/pm_v1.md` · runner: `backend/agentes/runner_semanal.py` · "
             "gate IPS: `backend/agentes/orquestador_decision.py` · ledger: `backend/ledger/`.")
    L.append("- Capa de decisión fail-closed (P1, en sombra): `backend/agentes/{permiso_ejecucion,banda,arquetipo,"
             "caps_posicion,comparacion_rotacion,evaluar_sombra,harness_sombra}.py` (doc 91 §8.ter).\n")

    L.append("## 0.bis Mecánica del núcleo — VERIFICADA en código (lo que el auditor debe juzgar si es ÓPTIMO)\n")
    L.append("1. **MONITOREO (todas las del universo, cada ciclo):** `universo.py:189` → `for tk in tickers_universo(): "
             "ph = precio_hist_fn(tk); señales_ticker(..., precio_hist=ph, filings=filings_fn(tk))`. O sea: baja "
             "precio (z-score) + filings de EDGAR de **CADA** nombre, cada ciclo. Costo = RED (no LLM). ¿Escala? ¿mejor forma?")
    L.append("2. **PRIORIZACIÓN:** `orquestador.py:204-240` → el Triage (Haiku) juzga TODOS → `seleccionar_para_deep()` "
             "(embudo) elige quién va a deep → el ledger de presupuesto lo capea (`modo=='corte'` → se saltea). El deep "
             "(Opus, lo CARO) se hace sobre un puñado/semana. ¿Es la mejor forma de gastar el Opus?")
    L.append("3. **DEEP → FICHA:** el comité (Analista+Verificador) produce un dossier → `escribir_ficha_desde_dossier` "
             "arma la FICHA (tesis + escenarios + zonas de compra/venta). 'Tener deep' = 'tener ficha'.")
    L.append("4. **ZONA (compra/venta) solo de las que tienen ficha:** `poller.py:30` → `pollear(fichas, ...)` itera SOLO "
             "fichas. La zona (COMPRA/RECORTE → alertas al PM) se computa de los escenarios del dossier. Las sin-ficha no "
             "tienen zona. **Dos relojes:** la tesis (lenta, del deep) + el precio del día (rápido, recalcula la zona).")
    L.append("5. **EL PM:** `pm.py` recibe: dossiers deepeados + fichas vivas + RADAR (fichas fuera de zona) + shortlist "
             "con score de las sin-ficha (puede pedir SOLICITAR_DEEP) + cartera. **Candado** (`orquestador_decision.py:"
             "253`): para COMPRAR exige ficha VIGENTE + datos limpios (sin deep NO compra); la zona COMPRA es BLANDA "
             "(entra fuera de zona, marcado). Las VENTAS nunca se bloquean (risk-off).")
    L.append("6. **COSTO:** el $ (Opus) NO escala con el tamaño del universo — lo capea el presupuesto ($100/mes) + cupos. "
             "Lo que escala con el tamaño es la RED del monitoreo (punto 1).\n")

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

    L.append("## 6. Contexto ya triangulado (doc 91) — NO lo repitas\n")
    L.append("El comité no le gana a un Opus+web solo; falta comparación económica entre oportunidades; deriva a value "
             "cíclico; falsadores mal diseñados; el edge no está demostrado. Eso ya lo tenemos. Acá el foco es el NÚCLEO "
             "(universo/monitoreo/priorización/información del PM), no la calidad del dossier individual.\n")

    L.append("## 7. Los 7 fixes de la 1ª review YA aplicados (revisá si están bien y si rompen algo)\n")
    for h in [
        "4b: la ficha conservaba mal `conocido_hasta` → 18/28 fichas EN_REVISION espurio → invisibles al PM. Corregido.",
        "Revalidación: una ficha no-tenencia que pasa a EN_REVISION ahora se re-encola (antes nadie la re-analizaba).",
        "RADAR: el packet ahora muestra fichas VIGENTE fuera de zona COMPRA (el prompt lo prometía, no existía).",
        "Pre-revenue: un nombre con backlog (RPO) pero sin ventas ahora entra al score (margen supuesto declarado) — "
        "antes era invisible (la cola power-law: SMR/espacio/biotech).",
        "Extranjeros: revalidación por TIEMPO (TTL) — el poller es EDGAR-only y nunca revalidaba a los no-US (42% de las "
        "altas del operador).",
        "mult_ref por mediana del cuello (antes 4x fijo para todo sector → empujaba a value cíclico).",
        "Universo: regla ÚNICA de admisión ($150M–$60B + whitelist) + las altas del operador/PM ahora entran a nx_empresa "
        "(antes iban solo a la cola→ficha → fichas huérfanas). universo_max 160→500.",
    ]:
        L.append(f"- {h}")
    L.append("\n**Pregunta final para el auditor:** con TODO esto a la vista, ¿este núcleo es la MEJOR manera de operar "
             "para un fondo de small/mid caps de industrias del futuro, o hay un diseño claramente superior? Priorizá lo "
             "que cambia una DECISIÓN, no lo cosmético.")
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
