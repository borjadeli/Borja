"""Generador de reporte HTML del backtest."""
from __future__ import annotations

from typing import Any


def confusion_matrix(report_data: dict) -> dict:
    """Calcula matriz de confusión binaria: winner/loser × correcto/incorrecto.

    TP = winner correctamente identificado (score arriba del min)
    TN = loser correctamente rechazado (score debajo del max)
    FP = loser clasificado como si fuera winner
    FN = winner clasificado como si fuera loser
    """
    tp = fp = fn = tn = 0
    for r in report_data["resultados"]:
        if r["outcome_esperado"] == "winner":
            if r["correcto"]:
                tp += 1
            else:
                fn += 1
        elif r["outcome_esperado"] == "loser":
            if r["correcto"]:
                tn += 1
            else:
                fp += 1

    total = tp + fp + fn + tn
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
    accuracy = (tp + tn) / total if total > 0 else 0
    return {
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "specificity": round(specificity, 3),
        "accuracy": round(accuracy, 3),
    }


def render_report_html(report_data: dict) -> str:
    """Genera HTML del reporte. Incluye matriz de confusión + tabla detallada."""
    cm = confusion_matrix(report_data)
    gate_passed = report_data["gate_passed"]
    gate_color = "#059669" if gate_passed else "#dc2626"
    gate_label = "PASS — autorizado para go-live" if gate_passed else "FAIL — calibración requerida"

    rows_html = []
    for r in report_data["resultados"]:
        row_color = "#ecfdf5" if r["correcto"] else "#fef2f2"
        status_badge = (
            '<span style="background:#059669;color:white;padding:2px 8px;border-radius:3px;font-size:10px;">OK</span>'
            if r["correcto"] else
            '<span style="background:#dc2626;color:white;padding:2px 8px;border-radius:3px;font-size:10px;">FAIL</span>'
        )
        outcome_badge = (
            '<span style="background:#6366f1;color:white;padding:2px 6px;border-radius:3px;font-size:10px;">WINNER</span>'
            if r["outcome_esperado"] == "winner" else
            '<span style="background:#64748b;color:white;padding:2px 6px;border-radius:3px;font-size:10px;">LOSER</span>'
        )
        motivo = r.get("motivo_fail") or r.get("error") or ""
        rows_html.append(f"""
        <tr style="background:{row_color};">
          <td><strong style="font-family:monospace;">{r['ticker']}</strong></td>
          <td>{outcome_badge}</td>
          <td style="text-align:center;">{status_badge}</td>
          <td style="text-align:right; font-family:monospace;">{r.get('score_resultante') or '—'}</td>
          <td>{r.get('nivel_r_resultante') or '—'}</td>
          <td>{r.get('estado_sugerido') or '—'}</td>
          <td style="font-size:11px; color:#64748b;">{motivo}</td>
        </tr>
        """)

    gate_razones = ""
    if report_data["gate_razones"]:
        gate_razones = "<ul>" + "".join(f"<li>{m}</li>" for m in report_data["gate_razones"]) + "</ul>"

    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<title>Backtest Report · BORJA</title>
<style>
  body {{ font-family: -apple-system,'Segoe UI',Arial,sans-serif; background:#f1f5f9; color:#0f172a; margin:20px; }}
  .wrap {{ max-width: 960px; margin: 0 auto; }}
  h1 {{ font-family: Georgia, serif; font-size: 28px; margin-bottom: 4px; }}
  .sub {{ color:#64748b; font-size:13px; margin-bottom:20px; }}
  .gate {{ background:{gate_color}; color:white; padding:20px; border-radius:8px; text-align:center; font-size:20px; font-weight:700; margin:20px 0; }}
  .card {{ background:white; border:1px solid #e2e8f0; border-radius:8px; padding:20px; margin-bottom:20px; }}
  .grid {{ display:grid; grid-template-columns: repeat(4, 1fr); gap:12px; margin-bottom:16px; }}
  .kpi {{ background:#f8fafc; padding:14px; border-radius:6px; }}
  .kpi .label {{ font-size:10px; text-transform:uppercase; letter-spacing:0.08em; color:#64748b; font-weight:600; }}
  .kpi .value {{ font-family: Georgia, serif; font-size:28px; font-weight:700; color:#0f172a; margin-top:4px; }}
  table {{ width:100%; border-collapse:collapse; }}
  th {{ background:#0f172a; color:#cbd5e1; font-size:11px; text-transform:uppercase; letter-spacing:0.05em; padding:10px; text-align:left; }}
  td {{ padding:10px; border-bottom:1px solid #e2e8f0; font-size:13px; }}
  .cm {{ display:grid; grid-template-columns: 80px 1fr 1fr; gap:0; font-size:13px; text-align:center; }}
  .cm > div {{ padding: 12px; border: 1px solid #e2e8f0; }}
  .cm .h {{ background:#0f172a; color:white; font-weight:600; }}
  .cm .tp {{ background:#ecfdf5; color:#065f46; font-weight:600; }}
  .cm .tn {{ background:#ecfdf5; color:#065f46; font-weight:600; }}
  .cm .fp {{ background:#fef2f2; color:#991b1b; font-weight:600; }}
  .cm .fn {{ background:#fef2f2; color:#991b1b; font-weight:600; }}
</style></head>
<body><div class="wrap">
  <h1>Backtest Report</h1>
  <div class="sub">{report_data['timestamp'][:19].replace('T',' ')} · modo: {'MOCK' if report_data['mock'] else 'REAL (Opus 4.7)'} · costo: ${report_data['cost_usd_total']}</div>

  <div class="gate">{gate_label}</div>

  <div class="grid">
    <div class="kpi"><div class="label">Correctos</div><div class="value">{report_data['correctos']}/{report_data['total']}</div></div>
    <div class="kpi"><div class="label">Pass rate</div><div class="value">{report_data['pass_rate']*100:.0f}%</div></div>
    <div class="kpi"><div class="label">Winners identificados</div><div class="value">{report_data['winners_correct']}/{report_data['winners_total']}</div></div>
    <div class="kpi"><div class="label">Losers rechazados</div><div class="value">{report_data['losers_correct']}/{report_data['losers_total']}</div></div>
  </div>

  {f'<div class="card"><strong>Motivos de falla del gate:</strong>{gate_razones}</div>' if not gate_passed else ''}

  <div class="card">
    <h2 style="font-family:Georgia,serif;margin-top:0;">Matriz de confusión</h2>
    <div class="cm">
      <div class="h"></div><div class="h">Predicho ≥ threshold (acepta)</div><div class="h">Predicho &lt; threshold (rechaza)</div>
      <div class="h">Real winner</div><div class="tp">TP = {cm['tp']}</div><div class="fn">FN = {cm['fn']}</div>
      <div class="h">Real loser</div><div class="fp">FP = {cm['fp']}</div><div class="tn">TN = {cm['tn']}</div>
    </div>
    <div style="margin-top:12px; font-size:12px; color:#475569;">
      Precision (winners detectados correctos): <strong>{cm['precision']*100:.0f}%</strong> ·
      Recall (winners no perdidos): <strong>{cm['recall']*100:.0f}%</strong> ·
      Specificity (losers rechazados): <strong>{cm['specificity']*100:.0f}%</strong> ·
      Accuracy: <strong>{cm['accuracy']*100:.0f}%</strong>
    </div>
  </div>

  <div class="card">
    <h2 style="font-family:Georgia,serif;margin-top:0;">Detalle por ticker</h2>
    <table>
      <tr><th>Ticker</th><th>Outcome</th><th>Status</th><th>Score</th><th>Nivel R</th><th>Estado</th><th>Diagnóstico</th></tr>
      {''.join(rows_html)}
    </table>
  </div>

  <div class="card" style="font-size:11px; color:#64748b;">
    <strong>Criterio go-live:</strong> pass rate ≥80% (8/10) · ≥4 winners identificados · ≥4 losers rechazados.
    Umbrales calibrados por ticker en <code>dataset.yaml</code> según expectativas realistas del scoring ponderado (divisor 12.5).
  </div>
</div></body></html>"""
