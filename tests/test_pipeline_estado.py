"""Dead man's switch + event monitor (doc 85 F1)."""
from datetime import datetime, timedelta, timezone

from backend.agentes.event_monitor import clasificar_filing, clasificar_filings
from backend.agentes.pipeline_estado import PipelineEstado


def test_dead_man_switch(tmp_path):
    pe = PipelineEstado(tmp_path / "pe.json")
    assert pe.fresco("poller") is False                      # nunca corrió → fail-closed
    pe.marcar("poller")
    assert pe.fresco("poller") is True                       # recién corrido → vivo
    # corrió hace 30h → muerto
    pe.marcar("poller", cuando=datetime.now(timezone.utc) - timedelta(hours=30))
    assert pe.fresco("poller", max_horas=26) is False
    # persiste entre instancias
    assert PipelineEstado(tmp_path / "pe.json").fresco("poller", max_horas=26) is False


def test_clasificar_filing():
    assert clasificar_filing("10-Q")[0] == "REVISION"        # periódico → invalida vigencia
    assert clasificar_filing("8-K", "1.03")[0] == "DURO"     # quiebra → regla de salida
    assert clasificar_filing("8-K", "4.02,9.01")[0] == "DURO"  # non-reliance
    assert clasificar_filing("8-K", "2.02")[0] == "REVISION"   # earnings → cola
    assert clasificar_filing("8-K", "3.02")[0] == "DILUCION"   # venta de equity → recalcular zona
    assert clasificar_filing("8-K", "8.01")[0] == "TRIAGE"     # otros eventos → triage
    assert clasificar_filing("8-K", "9.01")[0] == "IGNORAR"    # solo exhibits → nada
    assert clasificar_filing("S-3")[0] == "DILUCION"
    assert clasificar_filing("20-F")[0] == "REVISION"          # emisor extranjero


class _F:
    def __init__(self, tipo, items, accn="a1"):
        self.tipo, self.items, self.fecha, self.accession_number = tipo, items, "2026-11-10", accn


def test_clasificar_filings_ordena_por_severidad():
    filings = [_F("8-K", "2.02"), _F("8-K", "1.03"), _F("8-K", "9.01"), _F("10-Q", "")]
    ev = clasificar_filings("MP", filings)
    assert [e.tier for e in ev] == ["DURO", "REVISION", "REVISION"]   # 9.01 (IGNORAR) se filtra, DURO primero
    assert ev[0].items == ["1.03"]


def test_poller_invalida_vigencia_y_junta_duros():
    from dataclasses import dataclass as _dc

    from backend.agentes.poller import pollear

    @_dc
    class _Ficha:
        ticker: str
        estado: str
        conocido_hasta: str
        latido: object = None

    class _FF:
        def __init__(self, tipo, items, fecha):
            self.tipo, self.items, self.fecha, self.accession_number = tipo, items, fecha, "a"

    fichas = {"MP": _Ficha("MP", "VIGENTE", "2026-07-31"),      # 10-Q nuevo (oct) > julio → EN_REVISION
              "OK": _Ficha("OK", "VIGENTE", "2026-10-01"),      # nada material → sigue VIGENTE
              "WOLF": _Ficha("WOLF", "VIGENTE", "2026-07-31")}  # 8-K 1.03 (quiebra) → DURO
    filings = {"MP": [_FF("10-Q", "", "2026-10-15")], "OK": [_FF("8-K", "9.01", "2026-11-01")],
               "WOLF": [_FF("8-K", "1.03", "2026-11-01")]}
    res = pollear(fichas, filings_fn=lambda tk: filings.get(tk, []))
    assert "MP" in res.en_revision and fichas["MP"].estado == "EN_REVISION"
    assert fichas["OK"].estado == "VIGENTE"                     # 9.01 se ignora
    assert len(res.duros) == 1 and res.duros[0].ticker == "WOLF" and res.duros[0].items == ["1.03"]
