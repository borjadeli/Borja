"""P1 MODO SOMBRA — aplica el kit de cómputo (arquetipo→banda→cap→permiso→rotación) a los 7 nombres de la corrida
del 25-nov y muestra "qué habría decidido P1", para contrastar con el trato esperado por IA1/IA2.

NO aplica nada — es el demo de sombra (computa + loguea). Insumos derivados del backup `backup_comite_2026-11-25.md`;
donde falta un rango numérico (valor mitad-de-ciclo, cobertura IG), la banda queda en None y se marca "[falta insumo:
lo extrae el harness real del dossier]". Determinista, $0.

  .venv/bin/python -m ops.sombra_run
"""
from __future__ import annotations

from backend.agentes.arquetipo import clasificar_arquetipo
from backend.agentes.banda import calcular_banda
from backend.agentes.caps_posicion import cap_posicion
from backend.agentes.ips import IPS
from backend.agentes.permiso_ejecucion import execution_permission

# Insumos por nombre, derivados del backup del 25-nov (señales de arquetipo + lo que haya para la banda).
# accion/motivo = lo que PROPUSO el PM esa corrida. verif = veredicto ciego/principal.
NOMBRES = {
    "EXE":  {"sig": {"sector": "E&P", "revenue_ltm": 7.5e9}, "verif": "REVIEW",
             "banda_in": {"precio": 95, "valor_mitad_ciclo_bajo": 40, "valor_mitad_ciclo_alto": 80},  # a la curva <$3
             "accion": "aumentar", "motivo": "discrecional", "esperado": "cíclica · precio sobre el rango → RECORTE · no aumentar"},
    "VST":  {"sig": {"sector": "IPP"}, "verif": "FAIL",   # verificación ciega FAIL
             "banda_in": {}, "accion": "aumentar", "motivo": "discrecional",
             "esperado": "cíclica · FAIL → bloquear hasta reconciliar (verif + FCF normalizado)"},
    "IESC": {"sig": {"sector": "contratista_electrico", "margen_op_ltm": 0.156, "margen_op_mediana_10a": 0.09},
             "verif": "REVIEW", "banda_in": {}, "accion": "salir", "motivo": "discrecional", "dossier_del_ciclo": False,
             "esperado": "cíclica (margen 1.5×+ mediana) · venta discrecional con datos viejos → DIFERIR"},
    "CIFR": {"sig": {"contratado_firme": 14.6e9, "ev": 7.8e9, "capex": 2.0e9, "revenue": 0.27e9, "ocf_ltm": -10e6},
             "verif": "PASS", "banda_in": {"cobertura_ig_bajo": 0.3}, "flag_alta": True,
             "accion": "salir", "motivo": "discrecional", "esperado": "infra · flag ALTA → salida independiente OK"},
    "GLXY": {"sig": {"contratado_firme": 30e9, "ev": 7.0e9, "capex": 3.5e9, "revenue": 0.5e9, "ocf_ltm": -5e6},
             "verif": "PASS", "banda_in": {"cobertura_ig_bajo": 0.0},  # CoreWeave no-IG → cobertura ~0
             "accion": "mantener", "motivo": "discrecional", "esperado": "infra · cobertura ~0 → RECORTE · no entra"},
    "WOLF": {"sig": {"revenue_ltm": 620e6, "margen_bruto_ltm": -0.22}, "verif": "REVIEW", "banda_in": {},
             "accion": "mantener", "motivo": "discrecional", "esperado": "pre_revenue · solo opcionalidad si p_impl<p_razon"},
    "EME":  {"sig": {}, "verif": "REVIEW", "banda_in": {}, "sin_dossier": True,
             "accion": "abrir", "motivo": "discrecional", "esperado": "sin dossier → BLOQUEAR"},
}


def _evaluar(cfg: dict, d: dict) -> dict:
    arq = clasificar_arquetipo(d["sig"])
    banda = calcular_banda(arq, {**d.get("banda_in", {})}) if arq else None
    tier = "opcionalidad" if (arq == "pre_revenue" or d.get("flag_alta")) else "nucleo"
    tier_cfg = "OPTIONALITY" if tier == "opcionalidad" else "CORE"
    cap, liga = cap_posicion(tier=tier_cfg, arquetipo=arq, banda=banda, verificacion=d["verif"], cfg=cfg)
    # contexto del permiso (shadow): tier no elegible si núcleo con verif != PASS; métrica/falsador asumidos presentes
    # salvo sin_dossier; banda RECORTE/None o cap 0 → no apto para apertura.
    ctx = {"accion": d["accion"], "motivo_accion": d["motivo"], "verificacion": d["verif"],
           "metrica_obligatoria_null": d.get("sin_dossier", False),
           "falsador_id": None if d.get("sin_dossier") else "f", "falsador_sobre_metrica": not d.get("sin_dossier"),
           "tier_elegible": (d["verif"] == "PASS") if tier == "nucleo" else True,
           "peso_sobre_min_caps": False, "crea_stub_o_viola_ips": False,
           "dossier_del_ciclo": d.get("dossier_del_ciclo", True)}
    permiso, motivos = execution_permission(ctx)
    return {"arquetipo": arq or "UNCLASSIFIED", "banda": banda or "—", "cap": cap, "liga": liga,
            "permiso": permiso, "motivos": motivos}


def main() -> int:
    cfg = IPS.cargar().cfg
    print("=== P1 EN SOMBRA — qué habría decidido sobre la corrida del 25-nov (NO aplica, solo computa) ===\n")
    for tk, d in NOMBRES.items():
        r = _evaluar(cfg, d)
        banda_nota = r["banda"] if r["banda"] != "—" else "— [falta rango: lo extrae el harness real del dossier]"
        print(f"{tk}  (PM propuso: {d['accion']})")
        print(f"   arquetipo={r['arquetipo']} · banda={banda_nota} · cap={r['cap']:.1%} (liga: {r['liga']}) · "
              f"PERMISO={r['permiso']}")
        if r["motivos"]:
            print(f"   motivos: {'; '.join(r['motivos'])}")
        print(f"   esperado (IA1/IA2): {d['esperado']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
