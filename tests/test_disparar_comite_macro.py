"""r12 #7: el comité semanal dispara con --con-macro (el memo llega al PM y al Auditor)."""
import backend.agentes.disparar_comite as dc


def _capturar(monkeypatch):
    cmds = {}
    class _P:
        returncode = 0; stdout = "ok"; stderr = ""
    monkeypatch.setattr(dc.subprocess, "run", lambda cmd, **k: cmds.setdefault("cmd", cmd) or _P())
    return cmds


def test_semanal_con_macro(monkeypatch):
    cmds = _capturar(monkeypatch)
    dc.disparar_comite(universo=True, contratos=True, con_macro=True)
    assert "--con-macro" in cmds["cmd"]


def test_sin_macro_por_default(monkeypatch):
    cmds = _capturar(monkeypatch)
    dc.disparar_comite(universo=True, contratos=True)
    assert "--con-macro" not in cmds["cmd"]


def test_solo_pm_no_lleva_macro(monkeypatch):
    cmds = _capturar(monkeypatch)
    dc.disparar_comite(solo_pm=True, con_macro=True)       # el wake es barato, sin comité ni macro
    assert "--con-macro" not in cmds["cmd"] and "--solo-pm" in cmds["cmd"]
