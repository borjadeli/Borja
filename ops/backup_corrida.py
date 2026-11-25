"""Arma un BACKUP autocontenido de una corrida del comité, para evaluarla con otras IAs.

Junta, para un `ciclo` (fecha ISO, default hoy): los dossiers verificados (cache), las decisiones del PM con su
razonamiento (ledger), los costos de la corrida (llm_calls) y, si se pasa, el log crudo del comité (narrativa +
objeciones del Auditor). Salida: un .md autocontenido en data/corridas/.

Uso:
  .venv/bin/python -m ops.backup_corrida                         # ciclo = hoy
  .venv/bin/python -m ops.backup_corrida --ciclo 2026-11-25 --log data/corridas/comite_2026-11-25.log
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_CACHE = _REPO / "data" / "cache_dossiers_v2.json"
_LEDGER = _REPO / "data" / "ledger_decisiones_v2.jsonl"
_DB = _REPO / "data" / "borja.db"
_OUT_DIR = _REPO / "data" / "corridas"


def _cargar_decisiones(ciclo: str) -> list[dict]:
    if not _LEDGER.exists():
        return []
    out = []
    for ln in _LEDGER.read_text().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if r.get("tipo") == "decision" and r.get("ciclo") == ciclo:
            out.append(r)
    return out


def _cargar_dossiers() -> dict:
    return json.loads(_CACHE.read_text()) if _CACHE.exists() else {}


def _costos(desde_ts: str | None) -> tuple[float, list[tuple]]:
    """Costos de la corrida: llm_calls desde `desde_ts` (o desde el inicio del día del ciclo)."""
    if not _DB.exists():
        return 0.0, []
    con = sqlite3.connect(str(_DB))
    try:
        rows = con.execute(
            "SELECT agent, COUNT(*), ROUND(SUM(cost_usd),4), ROUND(SUM(web_searches),0) "
            "FROM llm_calls WHERE timestamp >= ? GROUP BY agent ORDER BY SUM(cost_usd) DESC",
            (desde_ts,)).fetchall()
        total = con.execute("SELECT ROUND(SUM(cost_usd),4) FROM llm_calls WHERE timestamp >= ?",
                            (desde_ts,)).fetchone()[0] or 0.0
        mes = con.execute("SELECT ROUND(SUM(cost_usd),2) FROM llm_calls "
                          "WHERE timestamp >= datetime('now','start of month')").fetchone()[0] or 0.0
    finally:
        con.close()
    return float(total), [("__MES__", 0, mes, 0)] + rows


def _fmt_tesis(lado: dict | str) -> str:
    """Bull/Bear salen como dict {tesis, supuestos, contraste_con_calculadoras, ...}; render legible."""
    if not isinstance(lado, dict):
        return str(lado)
    partes = [str(lado.get("tesis", ""))]
    sup = lado.get("supuestos") or []
    if sup:
        partes.append("Supuestos: " + "; ".join(str(s) for s in sup))
    if lado.get("contraste_con_calculadoras"):
        partes.append("Contraste con calculadoras: " + str(lado["contraste_con_calculadoras"]))
    return " — ".join(partes)


def _fmt_catalizador(c: dict | str) -> str:
    if not isinstance(c, dict):
        return str(c)
    return f"{c.get('descripcion','')} ({c.get('fecha_esperada','?')}, {c.get('tipo','')})"


def _fmt_dossier(tk: str, e: dict) -> list[str]:
    d = e.get("dossier") or {}
    v = e.get("verif") or {}
    L = [f"### {tk}  —  dossier {e.get('fecha','?')}  ·  veredicto **{v.get('veredicto','?').upper()}**"]
    if v.get("flags_supervivencia"):
        L.append(f"- ⚑ flags supervivencia: {', '.join(v['flags_supervivencia'])}")
    L.append(f"- **Negocio / posición en el cuello:** {d.get('negocio_y_posicion_cuello','')}")
    L.append(f"- **Valuación que exige el precio:** {d.get('valuacion_que_exige_el_precio','')}")
    L.append(f"- **Bull:** {_fmt_tesis(d.get('bull',''))}")
    L.append(f"- **Bear:** {_fmt_tesis(d.get('bear',''))}")
    cat = d.get("catalizadores") or []
    if cat:
        L.append(f"- **Catalizadores:** {'; '.join(_fmt_catalizador(c) for c in cat)}")
    rf = d.get("red_flags") or []
    if rf:
        L.append(f"- **Red flags:** {'; '.join(str(c) for c in rf)}")
    L.append(f"- **Falsador del analista:** {d.get('falsador','')}")
    L.append(f"- **Convicción:** {d.get('conviccion_0_1','?')} · dilución esp. {d.get('dilucion_esperada_pct','?')}% "
             f"· caja neta terminal {d.get('caja_neta_terminal','?')}")
    if v.get("motivos"):
        L.append(f"- **Motivos del verificador:** {'; '.join(str(m) for m in v['motivos'])}")
    return L


def _fmt_decision(r: dict) -> list[str]:
    zona = f" · zona al entrar: {r.get('zona_al_entrar')}" if r.get("zona_al_entrar") else ""
    fz = " · **FUERA DE ZONA**" if r.get("fuera_de_zona") else ""
    aud = " · re-decidido tras objeción del Auditor" if r.get("reevaluado_por_auditor") else ""
    L = [f"### {r.get('ticker')} — **{r.get('accion','?').upper()}**  peso {r.get('peso_resultante','?')}"
         f" (objetivo {r.get('peso_objetivo','?')}, clip={r.get('clip','none')}){fz}{aud}"]
    L.append(f"- **Convicción:** {r.get('conviccion_0_1','?')} · ejecutada: {r.get('ejecutada')}{zona}")
    L.append(f"- **Tesis:** {r.get('tesis','')}")
    L.append(f"- **Falsador:** {r.get('falsador_afirmacion','')} (límite {r.get('falsador_fecha_limite','?')})")
    if r.get("justificacion_zona"):
        L.append(f"- **Justificación fuera de zona:** {r['justificacion_zona']}")
    return L


def main() -> int:
    ap = argparse.ArgumentParser(description="Backup autocontenido de una corrida del comité")
    ap.add_argument("--ciclo", default=date.today().isoformat(), help="fecha del ciclo (ISO, default hoy)")
    ap.add_argument("--log", default=None, help="ruta al log crudo del comité (narrativa + Auditor)")
    ap.add_argument("--desde", default=None, help="timestamp desde el que sumar costos (default: inicio del día del ciclo)")
    args = ap.parse_args()

    desde = args.desde or f"{args.ciclo} 00:00:00"
    decisiones = _cargar_decisiones(args.ciclo)
    dossiers = _cargar_dossiers()
    total, por_agente = _costos(desde)

    # nombres tocados: los de las decisiones ∪ los dossiers con fecha == ciclo
    tks_dec = [r.get("ticker", "").upper() for r in decisiones]
    tks_dos = [tk for tk, e in dossiers.items() if e.get("fecha") == args.ciclo]
    tickers = sorted(set(tks_dec) | set(tks_dos))

    out = [f"# BACKUP comité — ciclo {args.ciclo}",
           f"_generado {datetime.now().isoformat(timespec='seconds')}_",
           "",
           "## Resumen de costos",
           f"- **Costo de la corrida** (desde {desde}): **${total:.2f}**"]
    for ag, n, c, ws in por_agente:
        if ag == "__MES__":
            out.append(f"- Gasto del mes a la fecha: ${c}")
        else:
            out.append(f"  - {ag}: {n} llamadas · ${c} · ~{int(ws)} web searches")
    out += ["", f"## Decisiones del PM ({len(decisiones)})"]
    if not decisiones:
        out.append("_(sin decisiones registradas para este ciclo)_")
    for r in decisiones:
        out += _fmt_decision(r) + [""]

    out += [f"## Dossiers verificados ({len(tickers)} nombres tocados)"]
    for tk in tickers:
        if tk in dossiers:
            out += _fmt_dossier(tk, dossiers[tk]) + [""]
        else:
            out += [f"### {tk} — (sin dossier en cache)", ""]

    if args.log and Path(args.log).exists():
        out += ["## Narrativa cruda del comité (incluye objeciones del Auditor)", "", "```",
                Path(args.log).read_text(), "```"]

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = _OUT_DIR / f"backup_comite_{args.ciclo}.md"
    dest.write_text("\n".join(out))
    print(f"✓ backup escrito: {dest}  ({len(tickers)} nombres · {len(decisiones)} decisiones · ${total:.2f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
