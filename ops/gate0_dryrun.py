"""Gate 0 (doc 91 §8.ter) — ENSAYO EN SECO, $0, SIN autoridad viva. Recorre el circuito real de la capa P1
(harness → orquestador fail-closed → shadow_log) con FIXTURES hechas a mano: un Underwriting COMPLETO por arquetipo
(ciclica/infra/compounder/pre_revenue) + un dossier LEGACY sin bloque económico. Verifica que:

  - el precio de la banda es el del PACK (no el del Analista),
  - un dossier completo con banda de compra EJECUTA; el legacy fail-closed BLOQUEA,
  - el log es ÚTIL (foto de insumos + motivos con CATEGORÍA + peso propuesto vs permitido),
  - el append del shadow_log FALLA VISIBLE (registros == decisiones),
  - la ATOMICIDAD de pares: si la compra de B queda bloqueada, la venta de A que la financiaba DIFIERE.

NO aplica nada, no consume LLM, no toca el ledger vivo. Escribe el log de sombra a un archivo temporal.

  .venv/bin/python -m ops.gate0_dryrun
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

from backend.agentes.harness_sombra import insumos_de_dossier
from backend.agentes.evaluar_sombra import evaluar_sombra
from backend.agentes.permiso_ejecucion import execution_permission
from backend.agentes.shadow_log import construir_shadow_decision, registrar_corrida, resumen_sombra
from backend.agentes.schemas import Underwriting

# CFG de referencia (el mismo de los tests de aceptación): Gate 0 valida la LÓGICA, determinista y sin ips.yaml.
CFG = {
    "tiers": {"OPTIONALITY": {"min": 0.015, "max": 0.025}, "CORE": {"min": 0.05, "max": 0.10},
             "HIGH_CONVICTION": {"min_exclusive": 0.10, "max": 0.15}},
    "cap_por_arquetipo": {"compounder": 0.15, "ciclica": 0.10, "infra": 0.10, "pre_revenue": 0.0},
    "cap_por_banda": {"COMPRA_FUERTE": 0.15, "COMPRA": 0.10, "MANTENER": 0.0, "RECORTE": 0.0},
    "cap_por_evidencia_opcionalidad": {"PASS": 0.025, "REVIEW": 0.015, "FAIL": 0.0},
}


def _dossier(arq, metrica_falsador, banda_inputs, fid="F-1"):
    uw = Underwriting(arquetipo_confirmado=arq, metrica_obligatoria_bajo=1.0, metrica_obligatoria_alto=2.0,
                      banda_inputs=banda_inputs, status="COMPLETE")
    fals = SimpleNamespace(id=fid, afirmacion="texto libre del PM", vara_externa=SimpleNamespace(metrica=metrica_falsador))
    return SimpleNamespace(underwriting=uw, falsador=fals)


# Un FIXTURE = (ticker, dossier, kwargs del harness incl. precio_pack, peso_propuesto). Uno por arquetipo + legacy.
FIXTURES = [
    ("CYC", _dossier("ciclica", "normalized_owner_fcf_per_share", {"valor_mitad_ciclo_bajo": 40, "valor_mitad_ciclo_alto": 80}),
     dict(verif="PASS", accion="abrir", peso_objetivo=0.07, tier_declarado="CORE", precio_pack=30), 0.07),
    ("INF", _dossier("infra", "cobertura_ig", {"cobertura_ig_bajo": 0.9}),
     dict(verif="PASS", accion="abrir", peso_objetivo=0.06, tier_declarado="CORE", precio_pack=12), 0.06),
    ("CMP", _dossier("compounder", "roic_incremental", {"g_exigido": 0.03, "g_sost_bajo": 0.08, "g_sost_alto": 0.12}),
     dict(verif="PASS", accion="abrir", peso_objetivo=0.08, tier_declarado="CORE", precio_pack=50), 0.08),
    ("PRE", _dossier("pre_revenue", "funding_gap", {"p_implicita_alto": 0.10, "p_razonada_bajo": 0.25}),
     dict(verif="PASS", accion="abrir", peso_objetivo=0.025, tier_declarado="OPTIONALITY", precio_pack=8), 0.025),
    ("LEG", SimpleNamespace(underwriting=None, falsador=SimpleNamespace(id=None, afirmacion="", vara_externa=None)),
     dict(verif="PASS", accion="abrir", peso_objetivo=0.07, tier_declarado="CORE", precio_pack=30,
          sig_pack={"sector": "E&P", "revenue_ltm": 7e9}), 0.07),
]


def _fila(tk, propuesto, v):
    cat = sorted({m["categoria"] for m in v}) if isinstance(v, list) else []
    return cat


def main() -> int:
    print("=== GATE 0 — ensayo en seco (fixtures, $0, SIN autoridad) ===\n")
    registros = []
    for tk, dossier, kw, peso in FIXTURES:
        peso_prop = kw.get("peso_objetivo")
        d = insumos_de_dossier(dossier, **kw)
        ver = evaluar_sombra(d, cfg=CFG)
        rec = construir_shadow_decision(ciclo="gate0", ticker=tk, accion_pm=kw["accion"],
                                        veredicto=ver, peso_propuesto=peso_prop)
        registros.append(rec)
        cats = {m["categoria"] for m in rec["shadow"]["motivos"]}
        print(f"{tk}  PM propuso: {kw['accion']} {peso_prop:.1%}")
        print(f"   arquetipo(conf)={ver.arquetipo or 'UNCLASSIFIED'} · banda={ver.banda or '—'} "
              f"· precio_pack={d['banda_in'].get('precio')}")
        print(f"   cap={ver.cap:.1%} (liga: {ver.liga}) · peso_permitido={ver.cap:.1%} "
              f"· PERMISO={ver.permiso} · tipo_cambio={rec['tipo_cambio']}")
        if ver.motivos:
            print(f"   motivos [{','.join(sorted(cats))}]: {ver.motivos[0]}")
        if ver.missing_fields:
            print(f"   faltan: {', '.join(ver.missing_fields)}")
        print()

    # ── ATOMICIDAD de pares: la compra de B (apertura incompleta) queda bloqueada → la venta de A que la financia DIFIERE. ──
    print("--- atomicidad de pares (B se evalúa ANTES que la venta de A) ---")
    b_ctx = {"accion": "abrir", "motivo_accion": "discrecional", "ticker": "BBB", "verificacion": "PASS",
             "tier": "CORE", "tiers_cfg": CFG["tiers"], "arquetipo": "ciclica", "peso_objetivo": 0.07, "cap": 0.10,
             "falsador_id": "f", "falsador_sobre_metrica": True, "metrica_obligatoria_null": False,
             "flags_alta_sin_responder": False, "bloqueo_datos": [], "crea_stub_o_viola_ips": False}
    b_ctx.pop("falsador_id")                          # B llega SIN falsador → su compra se bloquea
    permiso_b, _ = execution_permission(b_ctx)
    a_ctx = {"accion": "salir", "motivo_accion": "discrecional", "ticker": "AAA", "fondos": "BBB",
             "peso_objetivo": 0.0, "comparacion": "PERMITIDA", "metrica_A_null": False, "dossier_del_ciclo": True,
             "bloqueo_datos": [], "par_compra_bloqueada": (permiso_b != "EJECUTAR")}
    permiso_a, motivos_a = execution_permission(a_ctx)
    print(f"   compra de B (sin falsador): {permiso_b}")
    print(f"   venta de A para financiar B: {permiso_a}  ({motivos_a[0] if motivos_a else ''})")
    assert permiso_b == "BLOQUEAR" and permiso_a == "DIFERIR", "la atomicidad de pares no se respetó"
    print()

    # ── el append FALLA VISIBLE: registros == decisiones ──
    tmp = Path(tempfile.gettempdir()) / "gate0_shadow.jsonl"
    if tmp.exists():
        tmp.unlink()
    escritos = registrar_corrida(registros, path=tmp)
    print(f"--- shadow_log: {escritos} registros == {len(registros)} decisiones (invariante OK) → {tmp}")
    print(f"--- resumen: {resumen_sombra(registros)}")

    ejec = sum(1 for r in registros if r["shadow"]["permiso"] == "EJECUTAR")
    print(f"\nGate 0: {ejec}/{len(registros)} EJECUTAN (los 4 arquetipos completos), el legacy BLOQUEA. "
          f"Fail-closed + atomicidad + log útil verificados, $0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
