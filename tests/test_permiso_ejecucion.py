"""P1 (doc 91 §7) — execution_permission (blueprint IA2 §3). Determinista, sin LLM."""
from backend.agentes.permiso_ejecucion import execution_permission


def _ctx(**kw):
    base = {"accion": "aumentar", "motivo_accion": "discrecional", "verificacion": "PASS",
            "metrica_obligatoria_null": False, "falsador_id": "f1", "falsador_sobre_metrica": True,
            "peso_en_grilla": True, "peso_sobre_min_caps": False, "tier_elegible": True,
            "flags_alta_sin_responder": False, "bloqueo_datos": False,
            "opcionalidad_sin_plaza_o_congelada": False, "crea_stub_o_viola_ips": False,
            "dossier_del_ciclo": True, "par_compra_bloqueada": False, "venta_a_caja_sin_motivo_valido": False}
    base.update(kw)
    return base


def test_salida_mecanica_siempre_ejecuta():
    # un falsador DURO / techo / regla IPS NO se traba por datos/valuación — se vende.
    p, _ = execution_permission(_ctx(accion="salir", motivo_accion="falsador_duro",
                                     verificacion="FAIL", bloqueo_datos=["precio"]))
    assert p == "EJECUTAR"


def test_aumento_con_fail_bloquea():
    p, m = execution_permission(_ctx(accion="aumentar", verificacion="FAIL"))
    assert p == "BLOQUEAR" and any("FAIL" in x for x in m)


def test_aumento_con_review_bloquea_por_tier_no_elegible():
    # REVIEW no habilita núcleo (requiere PASS) → tier_elegible=False → BLOQUEAR (caso VST/EXE).
    p, m = execution_permission(_ctx(accion="aumentar", verificacion="REVIEW", tier_elegible=False))
    assert p == "BLOQUEAR" and any("tier no elegible" in x for x in m)


def test_aumento_sin_metrica_o_sin_falsador_sobre_metrica_bloquea():
    assert execution_permission(_ctx(accion="aumentar", metrica_obligatoria_null=True))[0] == "BLOQUEAR"
    assert execution_permission(_ctx(accion="aumentar", falsador_sobre_metrica=False))[0] == "BLOQUEAR"


def test_aumento_limpio_ejecuta():
    assert execution_permission(_ctx(accion="aumentar"))[0] == "EJECUTAR"


def test_venta_discrecional_con_datos_viejos_difiere():
    # IESC: venta discrecional pero el dossier no es del ciclo (zonas viejas) → DIFERIR, no ejecutar a ciegas.
    p, m = execution_permission(_ctx(accion="salir", motivo_accion="discrecional", dossier_del_ciclo=False))
    assert p == "DIFERIR" and any("no es del ciclo" in x for x in m)


def test_venta_discrecional_a_caja_sin_motivo_bloquea():
    p, _ = execution_permission(_ctx(accion="reducir", motivo_accion="discrecional",
                                     venta_a_caja_sin_motivo_valido=True))
    assert p == "BLOQUEAR"


def test_venta_discrecional_limpia_ejecuta():
    assert execution_permission(_ctx(accion="salir", motivo_accion="discrecional"))[0] == "EJECUTAR"


def test_compra_de_par_usa_blockers_de_apertura():
    p, _ = execution_permission(_ctx(accion="reducir", motivo_accion="discrecional",
                                     es_compra_de_par=True, verificacion="FAIL"))
    assert p == "BLOQUEAR"
