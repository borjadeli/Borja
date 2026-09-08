"""Ledger de rechazos (doc 40 Bloque 0.1): registro dedup + retorno forward + separación compra/rechazo."""
from backend.nucleo import registro_decisiones as RD
from backend.nucleo.registro_decisiones import Decision


def _dec(t, precio, estado, fecha="2026-01-01", ver="v1"):
    return Decision(ticker=t, fecha=fecha, precio=precio, estado=estado, politica_version=ver)


def test_registrar_y_dedup(tmp_path):
    p = tmp_path / "l.json"
    decs = [_dec("A", 10, "COVERED"), _dec("B", 20, "DESCARTE")]
    assert RD.registrar(decs, path=p) == 2
    assert RD.registrar(decs, path=p) == 0                 # idempotente: mismo snapshot no duplica
    assert RD.registrar([_dec("A", 10, "COVERED", ver="v2")], path=p) == 1   # otra versión = nueva decisión


def test_marcar_forward(tmp_path):
    p = tmp_path / "l.json"
    RD.registrar([_dec("A", 10, "COVERED"), _dec("B", 20, "DESCARTE")], path=p)
    m = {x["ticker"]: x for x in RD.marcar_forward({"A": 15, "B": 10}, "2026-04-01", path=p)}
    assert abs(m["A"]["retorno_fwd"] - 0.5) < 1e-9        # 15/10−1
    assert abs(m["B"]["retorno_fwd"] + 0.5) < 1e-9        # 10/20−1
    assert m["A"]["dias"] == 90


def test_marca_none_sin_precio(tmp_path):
    p = tmp_path / "l.json"
    RD.registrar([_dec("A", 10, "COVERED")], path=p)
    assert RD.marcar_forward({}, "2026-04-01", path=p)[0]["retorno_fwd"] is None


def test_separacion_compra_vs_rechazo(tmp_path):
    p = tmp_path / "l.json"
    # las que compramos suben, las que rechazamos bajan → separación positiva (el frame discrimina)
    RD.registrar([_dec("A", 10, "COVERED"), _dec("B", 10, "STRETCH"),
                  _dec("C", 10, "DESCARTE"), _dec("D", 10, "NON_UNDERWRITABLE")], path=p)
    met = RD.metricas_por_clase({"A": 20, "B": 15, "C": 8, "D": 5}, "2026-04-01", path=p)
    assert met["compra"]["n"] == 2 and met["rechazo"]["n"] == 2
    assert met["separacion_media"] > 0                    # compra (media +0.75) > rechazo (media −0.35)
    assert "COVERED" in met["por_estado"]


def test_separacion_negativa_detecta_ceguera(tmp_path):
    p = tmp_path / "l.json"
    # el caso que buscamos cazar: RECHAZAMOS los que subieron (falsos negativos) → separación NEGATIVA
    RD.registrar([_dec("W", 10, "COVERED"), _dec("X", 10, "DESCARTE")], path=p)
    met = RD.metricas_por_clase({"W": 9, "X": 30}, "2026-04-01", path=p)   # el rechazado hizo 3x
    assert met["separacion_media"] < 0                    # alarma: compramos el que bajó, rechazamos el 3x


def test_desde_candidatos(tmp_path):
    from backend.nucleo.ranking_lexicografico import CandidatoLex
    c = CandidatoLex(ticker="Z", elegible=True, valuacion_ok=True, tier_capital="A", cobertura=0.5,
                     asimetria_operable=1.0, arquetipo="Growth", cap=0.08, estado_valuacion="COVERED",
                     cap_reason="tier")
    decs = RD.desde_candidatos([c], {"Z": 42.0}, "2026-08-21")
    assert len(decs) == 1 and decs[0].ticker == "Z" and decs[0].precio == 42.0
    assert decs[0].estado == "HARD_EVIDENCE" and decs[0].politica_version
