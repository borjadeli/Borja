"""Gate 0 (doc 91 §8.ter) — SEAM: el tipo REAL que emite el Analista (`Dossier` pydantic con `underwriting` +
`falsador` estructurado) fluye por harness→orquestador→shadow_log sin SimpleNamespace. De-risquea el piloto del 1-dic:
un Dossier COMPLETO ejecuta; uno con `underwriting` INCOMPLETE (sin bloque económico) fail-closed BLOQUEA."""
from backend.agentes.harness_sombra import evaluar_decision_sombra
from backend.agentes.shadow_log import construir_shadow_decision
from backend.agentes.schemas import (AgentMeta, Dossier, Escenario, Falsador, Underwriting, VaraExterna)

_CFG = {"tiers": {"OPTIONALITY": {"min": 0.015, "max": 0.025}, "CORE": {"min": 0.05, "max": 0.10}},
        "cap_por_arquetipo": {"compounder": 0.15, "ciclica": 0.10, "infra": 0.10, "pre_revenue": 0.0},
        "cap_por_banda": {"COMPRA_FUERTE": 0.15, "COMPRA": 0.10, "MANTENER": 0.0, "RECORTE": 0.0},
        "cap_por_evidencia_opcionalidad": {"PASS": 0.025, "REVIEW": 0.015, "FAIL": 0.0}}

_META = AgentMeta(agent="analista", prompt_version="analista_v1", model="claude-opus-5-5")


def _escenario(tesis):
    return Escenario(tesis=tesis, supuestos=["s1"], contraste_con_calculadoras="vs T*/owner-FCF")


def _dossier(underwriting, *, con_vara="normalized_owner_fcf_per_share", fid="F-CYC-1"):
    vara = VaraExterna(tipo="economico", metrica=con_vara, umbral="HH<3", comparador="curva EIA",
                       fuente_medicion="EIA STEO") if con_vara else None
    falsador = Falsador(afirmacion="texto que el PM reescribe", fecha_limite="2027-12-31",
                        que_lo_mataria="owner-FCF normalizado no llega", id=fid, vara_externa=vara)
    return Dossier(meta=_META, ticker="CYC", negocio_y_posicion_cuello="cuello X",
                   valuacion_que_exige_el_precio="exige g 8%", bull=_escenario("bull"), bear=_escenario("bear"),
                   falsador=falsador, underwriting=underwriting, conviccion_0_1=0.6)


def test_dossier_real_completo_ejecuta():
    uw = Underwriting(arquetipo_confirmado="ciclica", metrica_obligatoria_nombre="normalized_owner_fcf_per_share",
                      metrica_obligatoria_bajo=1.8e9, metrica_obligatoria_alto=2.2e9,
                      banda_inputs={"valor_mitad_ciclo_bajo": 40, "valor_mitad_ciclo_alto": 80}, status="COMPLETE")
    r = evaluar_decision_sombra(_dossier(uw), cfg=_CFG, verif="PASS", accion="abrir",
                                peso_objetivo=0.07, tier_declarado="CORE", precio_pack=30)
    assert r.arquetipo == "ciclica" and r.banda == "COMPRA_FUERTE" and r.permiso == "EJECUTAR"
    rec = construir_shadow_decision(ciclo="piloto", ticker="CYC", accion_pm="abrir", veredicto=r, peso_propuesto=0.07)
    assert rec["cambiaria_la_decision"] is False and rec["shadow"]["peso_permitido"] == 0.10


def test_dossier_real_sin_underwriting_bloquea():
    r = evaluar_decision_sombra(_dossier(None, con_vara=None, fid=None), cfg=_CFG, verif="PASS", accion="abrir",
                                peso_objetivo=0.07, tier_declarado="CORE", precio_pack=30,
                                sig_pack={"sector": "E&P", "revenue_ltm": 7e9})
    assert r.permiso == "BLOQUEAR" and r.missing_fields


def test_falsador_real_tiene_id_y_liga_el_arquetipo():
    # el gap que tapaban los fixtures: el Falsador real ahora tiene `id` → el harness lo toma como falsador_id.
    uw = Underwriting(arquetipo_confirmado="ciclica", metrica_obligatoria_bajo=1.0,
                      banda_inputs={"valor_mitad_ciclo_bajo": 40, "valor_mitad_ciclo_alto": 80}, status="COMPLETE")
    from backend.agentes.harness_sombra import insumos_de_dossier
    d = insumos_de_dossier(_dossier(uw), verif="PASS", accion="abrir", precio_pack=30)
    assert d["falsador_id"] == "F-CYC-1" and d["falsador_sobre_metrica"] is True
