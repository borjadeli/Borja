"""Pedido del operador: el digest muestra, por decisión, los comentarios del Auditor y si el PM modificó/reconfirmó."""
from types import SimpleNamespace

from backend.agentes.resumen_v2 import render_digest


def _dec(**over):
    base = dict(accion="comprar", ticker="OKLO", peso_resultante=0.05, conviccion_0_1=0.7,
                verif_veredicto="pass", ejecutada=True, tesis="t", falsador_afirmacion="f",
                falsador_fecha_limite="2027-01-01", objeciones_auditor=[], reevaluado_por_auditor=False)
    base.update(over)
    return SimpleNamespace(**base)


def _render(decs):
    return render_digest(ciclo="c", equity=100_000.0, caja_pct=0.5, posiciones=[], decisiones=decs,
                         dossiers={}, gasto_mes=0.0, tope_mes=100.0, sombras={})


def test_digest_muestra_auditor_y_reeval():
    d = _dec(objeciones_auditor=[{"tipo": "concentracion", "severidad": "media", "detalle": "todo un factor"}],
             reevaluado_por_auditor=True)
    txt = _render([d])
    assert "auditor [media] concentracion" in txt
    assert "REEVALUÓ" in txt


def test_digest_objecion_mantenida():
    d = _dec(objeciones_auditor=[{"tipo": "coherencia", "severidad": "baja", "detalle": "menor"}],
             reevaluado_por_auditor=False)
    txt = _render([d])
    assert "auditor [baja] coherencia" in txt and "MANTUVO" in txt


def test_digest_sin_objeciones_no_muestra_bloque():
    assert "auditor" not in _render([_dec()])
