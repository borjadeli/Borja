"""Gate 0 (doc 91 §8.ter) — el HOOK listo para el runner: registrar_decision_en_sombra mapea las acciones del PM
(comprar/vender) a las del permiso (abrir/salir), corre el shadow por cada una y loguea con el invariante
registros==decisiones. NO toca autoridad. Determinista."""
import json
from types import SimpleNamespace

from backend.agentes.harness_sombra import ACCION_PM_A_PERMISO, registrar_decision_en_sombra
from backend.agentes.schemas import AgentMeta, Dossier, Escenario, Falsador, Underwriting, VaraExterna

_CFG = {"tiers": {"OPTIONALITY": {"min": 0.015, "max": 0.025}, "CORE": {"min": 0.05, "max": 0.10}},
        "cap_por_arquetipo": {"compounder": 0.15, "ciclica": 0.10, "infra": 0.10, "pre_revenue": 0.0},
        "cap_por_banda": {"COMPRA_FUERTE": 0.15, "COMPRA": 0.10, "MANTENER": 0.0, "RECORTE": 0.0},
        "cap_por_evidencia_opcionalidad": {"PASS": 0.025, "REVIEW": 0.015, "FAIL": 0.0}}
_META = AgentMeta(agent="analista", prompt_version="analista_v1", model="m")


def _esc(t):
    return Escenario(tesis=t, supuestos=["s"], contraste_con_calculadoras="c")


def _dossier(tk, arq, metrica, banda_inputs):
    vara = VaraExterna(tipo="economico", metrica=metrica, umbral="u", comparador="c", fuente_medicion="f")
    fals = Falsador(afirmacion="t", fecha_limite="2027-12-31", que_lo_mataria="q", id=f"F-{tk}", vara_externa=vara)
    uw = Underwriting(arquetipo_confirmado=arq, metrica_obligatoria_bajo=1.0, banda_inputs=banda_inputs, status="COMPLETE")
    return Dossier(meta=_META, ticker=tk, negocio_y_posicion_cuello="x", valuacion_que_exige_el_precio="x",
                   bull=_esc("b"), bear=_esc("be"), falsador=fals, underwriting=uw, conviccion_0_1=0.5)


def test_mapeo_de_acciones_pm():
    assert ACCION_PM_A_PERMISO["comprar"] == "abrir" and ACCION_PM_A_PERMISO["vender"] == "salir"
    assert ACCION_PM_A_PERMISO["recortar"] == "reducir"


def test_hook_registra_y_mapea(tmp_path):
    p = tmp_path / "shadow.jsonl"
    dossiers = {
        "CYC": _dossier("CYC", "ciclica", "normalized_owner_fcf_per_share",
                        {"valor_mitad_ciclo_bajo": 40, "valor_mitad_ciclo_alto": 80}),
        "INF": _dossier("INF", "infra", "cobertura_ig", {"cobertura_ig_bajo": 0.9}),
    }
    acciones = [SimpleNamespace(ticker="CYC", accion="comprar", peso_objetivo=0.07),
                SimpleNamespace(ticker="INF", accion="vender", peso_objetivo=0.0)]
    out = registrar_decision_en_sombra(ciclo="2026-12-01", acciones=acciones, dossier_por_ticker=dossiers,
                                       verif_por_ticker={"CYC": "pass", "INF": "pass"},
                                       precios={"CYC": 30, "INF": 12}, cfg=_CFG, path=p)
    recs = [json.loads(l) for l in p.read_text().splitlines()]
    assert len(recs) == 2 and out["resumen"]["n"] == 2
    cyc = next(r for r in recs if r["ticker"] == "CYC")
    assert cyc["propuesta_pm"] == "abrir" and cyc["shadow"]["banda"] == "COMPRA_FUERTE"   # comprar→abrir, ejecuta
    assert cyc["shadow"]["permiso"] == "EJECUTAR"


def test_hook_sin_dossier_se_saltea_sin_romper(tmp_path):
    p = tmp_path / "s.jsonl"
    acciones = [SimpleNamespace(ticker="ZZZ", accion="comprar", peso_objetivo=0.07)]
    out = registrar_decision_en_sombra(ciclo="c", acciones=acciones, dossier_por_ticker={},
                                       verif_por_ticker={}, precios={}, cfg=_CFG, path=p)
    assert out["resumen"]["n"] == 0 and (not p.exists() or p.read_text() == "")
