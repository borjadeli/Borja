"""P0-2 (review r11): el despertar del PM no debe dispararse a diario por falsadores no resueltos ni motivos repetidos."""
from datetime import date
from types import SimpleNamespace

import ops.ciclo_diario as cd
from backend.agentes.falsadores import Falsador, confirmados_para_salida, evaluar
from backend.agentes.reglas_salida import evaluar_reglas_salida


def _fal():
    return Falsador(id="liq", metrica="liquidez", operador="<", umbral=1e9, tipo="DURO", fuente="xbrl:liquidez")


def test_p0_2a_numerico_ok_con_valor_no_despierta():
    f = _fal()
    assert evaluar(f, valor=3e9) == "OK"          # 3e9 no cruza <1e9 → OK
    assert evaluar(f, valor=None) == "SUSPECTED"  # sin dato → SUSPECTED (el bug sin valor_fn)


def test_p0_2a_confirmados_usa_valor_fn():
    fichas = {"MP": SimpleNamespace(falsadores=[_fal()])}
    assert "MP" not in confirmados_para_salida(fichas, valor_fn=lambda tk, m: 3e9)  # OK → no despierta
    assert confirmados_para_salida(fichas).get("MP")                                # sin valor_fn → SUSPECTED → despierta


def test_p0_2b_dedup_motivos(tmp_path, monkeypatch):
    monkeypatch.setattr(cd, "_MOTIVOS_NOTIF", tmp_path / "m.json")
    m = ["MP entró a RECORTE"]
    assert cd._dedup_motivos(m, date(2026, 1, 1)) == m     # primera vez → despierta
    assert cd._dedup_motivos(m, date(2026, 1, 3)) == []    # 2 días → no repite
    assert cd._dedup_motivos(m, date(2026, 1, 10)) == m    # 9 días → recordatorio


def test_p0_2c_texto_refleja_estado():
    fc = {"MP": [{"tipo": "DURO", "id": "liq", "consecuencia": "REVISION", "estado": "SUSPECTED"}]}
    out = evaluar_reglas_salida([], posiciones={"MP"}, falsadores_confirmados=fc)
    assert out and any("SIN VERIFICAR" in a.motivo for a in out)
    assert not any("cumplido" in a.motivo for a in out)
