"""P1 MODO SOMBRA — aplica el orquestador fail-closed a los nombres de la corrida del 25-nov con lo que el sistema
REALMENTE sabía ese día (señales de arquetipo + verif + propuesta del PM). NO inventa rangos de banda, falsadores ni
métricas: lo que falta queda en 'faltan' y el permiso lo trata fail-closed.

Esto NO es un replay de autoridad (IA2): es el demo honesto. Con los dossiers HISTÓRICOS (sin los campos económicos
estructurados) P1 fail-closed BLOQUEA casi todo — que es lo correcto: no se autoriza sobre datos incompletos. El
harness REAL (pendiente, gated por el operador) extiende el schema del Analista para que devuelva esos campos.

  .venv/bin/python -m ops.sombra_run
"""
from __future__ import annotations

from backend.agentes.evaluar_sombra import evaluar_sombra
from backend.agentes.ips import IPS

# Lo que el sistema sabía: señales de arquetipo + verif + la propuesta del PM. SIN rangos de banda / falsador / métrica
# estructurados (los dossiers históricos no los tienen → faltan → fail-closed). Incluye Doosan (descartado por evidencia).
NOMBRES = {
    "EXE":  {"sig": {"sector": "E&P", "revenue_ltm": 7.5e9}, "verif": "REVIEW", "accion": "aumentar", "motivo": "discrecional", "peso_objetivo": 0.08},
    "VST":  {"sig": {"sector": "IPP"}, "verif": "FAIL", "accion": "aumentar", "motivo": "discrecional", "peso_objetivo": 0.10},
    "IESC": {"sig": {"sector": "contratista_electrico", "revenue_ltm": 4.48e9}, "verif": "REVIEW", "accion": "salir", "motivo": "discrecional"},
    "CIFR": {"sig": {"contratado_firme": 14.6e9, "ev": 7.8e9, "capex": 2.0e9, "revenue_ltm": 0.27e9, "ocf_ltm": -10e6, "runway_meses": 14},
             "verif": "PASS", "flag_alta": True, "accion": "salir", "motivo": "discrecional"},
    "GLXY": {"sig": {"contratado_firme": 30e9, "ev": 7.0e9, "capex": 3.5e9, "revenue_ltm": 0.5e9, "ocf_ltm": -5e6, "runway_meses": 20},
             "verif": "PASS", "bloqueo_datos": ["equity sin reconciliar"], "accion": "mantener", "motivo": "discrecional"},
    "WOLF": {"sig": {"revenue_ltm": 620e6, "margen_bruto_ltm": -0.22}, "verif": "REVIEW", "accion": "mantener", "motivo": "discrecional"},
    "EME":  {"sig": {}, "verif": "REVIEW", "accion": "abrir", "motivo": "discrecional", "peso_objetivo": 0.06},
    "DOOSAN": {"sig": {"sector": "fabricacion_industrial"}, "verif": "REVIEW", "bloqueo_datos": ["precio sin 2ª fuente (extranjera)"],
               "accion": "mantener", "motivo": "discrecional"},
}


def main() -> int:
    cfg = IPS.cargar().cfg
    print("=== P1 EN SOMBRA (fail-closed, honesto) — 25-nov. NO aplica; computa con lo que el sistema sabía. ===\n")
    for tk, d in NOMBRES.items():
        r = evaluar_sombra(d, cfg=cfg)
        print(f"{tk}  (PM propuso: {d['accion']})")
        print(f"   arquetipo={r.arquetipo or 'UNCLASSIFIED'} · banda={r.banda or '—'} · cap={r.cap:.1%} (liga: {r.liga}) · PERMISO={r.permiso}")
        if r.motivos:
            print(f"   motivos: {'; '.join(r.motivos)}")
        if r.missing_fields:
            print(f"   faltan (los provee el harness real desde el schema del Analista): {', '.join(r.missing_fields)}")
        print()
    print("Lectura: con los dossiers históricos (sin campos económicos estructurados) P1 fail-closed bloquea casi todo.")
    print("Eso es lo CORRECTO — no se autoriza sobre datos incompletos. El edge se mide cuando el Analista emite los campos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
