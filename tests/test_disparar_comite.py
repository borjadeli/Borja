"""Disparador del comité (doc 85, última milla): subproceso + fail-safe."""
import subprocess

from backend.agentes import disparar_comite as dc


def test_disparar_ok(monkeypatch):
    class _P:
        returncode = 0
        stdout = "linea1\nlinea2\ndecisión del PM: operar=False\n"
        stderr = ""
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _P())
    r = dc.disparar_comite(universo=True, contratos=True)
    assert r["ok"] is True and r["returncode"] == 0 and "operar=False" in r["resumen"]


def test_disparar_falla_no_lanza(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("no pude lanzar el proceso")
    monkeypatch.setattr(subprocess, "run", _boom)
    r = dc.disparar_comite()
    assert r["ok"] is False and "no pude lanzar" in r["resumen"]   # fail-safe: devuelve, no tumba


def test_disparar_timeout(monkeypatch):
    def _timeout(*a, **k):
        raise subprocess.TimeoutExpired(cmd="x", timeout=1)
    monkeypatch.setattr(subprocess, "run", _timeout)
    assert dc.disparar_comite(timeout=1)["resumen"] == "timeout"


def test_cmd_incluye_flags(monkeypatch):
    capt = {}
    class _P:
        returncode = 0; stdout = ""; stderr = ""
    def _run(cmd, **k):
        capt["cmd"] = cmd
        return _P()
    monkeypatch.setattr(subprocess, "run", _run)
    dc.disparar_comite(universo=True, contratos=False)
    assert "--universo" in capt["cmd"] and "--contratos" not in capt["cmd"]
    assert "ops.correr_semana_v2" in capt["cmd"]
