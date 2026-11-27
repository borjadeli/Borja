"""r12 #5: UN solo camino de creación de ficha (comité + cola). PASS→ficha vigente; FAIL→ROTA."""
from backend.agentes.ficha_store import StoreFichas, escribir_ficha_desde_dossier
from tests.test_packet_pm import _ficha  # reusa el stub de dossier (backfill_desde_dossier)


def test_pass_crea_ficha_vigente(tmp_path):
    from backend.agentes.ficha import backfill_desde_dossier  # noqa: F401  (asegura import del módulo)
    store = StoreFichas(tmp_path / "f.json")
    # dossier stub: usamos el mismo _Dossier del test de packet vía un pequeño armado
    from tests.test_packet_pm import _Dossier, _Inv, _E, _Fals, _ESC
    dossier = _Dossier(_Inv("satelite"), [_E(**e) for e in _ESC], _Fals("x", "2027-06-30"))
    f = escribir_ficha_desde_dossier("MP", dossier, "pass",
                                     datos={"acciones": 100e6, "deuda_neta": 0.0, "precio": 18.0}, store=store)
    assert f is not None and f.estado == "VIGENTE"
    assert StoreFichas(tmp_path / "f.json").get("MP") is not None    # persistió


def test_pass_preserva_conocido_hasta(tmp_path):
    # 4b (auditoría): sin conocido_hasta el poller marca EN_REVISION espuriamente ante el mismo 10-Q que el dossier leyó.
    from tests.test_packet_pm import _Dossier, _Inv, _E, _Fals, _ESC
    store = StoreFichas(tmp_path / "f.json")
    dossier = _Dossier(_Inv("satelite"), [_E(**e) for e in _ESC], _Fals("x", "2027-06-30"))
    f = escribir_ficha_desde_dossier("MP", dossier, "pass", store=store,
                                     datos={"acciones": 100e6, "deuda_neta": 0.0, "precio": 18.0,
                                            "conocido_hasta": "2026-11-20"})
    assert f is not None and f.conocido_hasta == "2026-11-20"


def test_fail_marca_rota_la_ficha_previa(tmp_path):
    store = StoreFichas(tmp_path / "f.json")
    held = _ficha("MP", 18.0)                       # ficha previa VIGENTE
    store.set(held); store.guardar()
    f = escribir_ficha_desde_dossier("MP", None, "fail", store=store)
    assert f is not None and f.estado == "ROTA"
    assert StoreFichas(tmp_path / "f.json").get("MP").estado == "ROTA"   # persistió la ROTA


def test_fail_sin_ficha_previa_no_crea(tmp_path):
    store = StoreFichas(tmp_path / "f.json")
    assert escribir_ficha_desde_dossier("ZZZ", None, "fail", store=store) is None
