"""Tests de la columna de DEMANDA citada (display-only) y el cache-guard de extraer_demanda.
Todo mockeado — cero LLM/red. Verifica: aislamiento (no toca ranking), derivación de tier+quote,
y que el cache no re-gaste LLM si el filing no cambió (doc 32 §5, Bloque 1a)."""
from __future__ import annotations

import types

from backend.nucleo import analisis
from backend.nucleo import hoja_evidencia as HE


class _F:
    """Fake NxFact mínimo."""
    def __init__(self, quote=None, source_accession=None, value=True, support_type="DIRECT", fuente="A"):
        self.quote = quote
        self.source_accession = source_accession
        self.value = value
        self.support_type = support_type
        self.fuente = fuente


# --- _demanda_display: tier + quote gobernante (reusa ranking._demanda_de_snapshot) ---
def _mock_rp(monkeypatch, pct=None):
    monkeypatch.setattr(HE.edgar, "get_related_party_pct", lambda t: {"pct": pct})


def test_demanda_display_quote_por_tier(monkeypatch):
    snap = {"cliente_nombrado": _F(quote="Transaction Agreement with a named customer")}
    monkeypatch.setattr(HE.FS, "snapshot_vigente", lambda s, t: snap)
    _mock_rp(monkeypatch)
    monkeypatch.setattr(HE.ranking, "_demanda_de_snapshot", lambda sn, rp_pct=None: (1, "UNKNOWN", []))
    tier, quote, _ = HE._demanda_display(object(), "AAOI")
    assert tier == 1 and quote == "Transaction Agreement with a named customer"


def test_demanda_display_realized_toma_su_quote(monkeypatch):
    snap = {"demanda_realizada": _F(quote="revenue from customer X recognized"),
            "cliente_nombrado": _F(quote="agreement with X")}
    monkeypatch.setattr(HE.FS, "snapshot_vigente", lambda s, t: snap)
    _mock_rp(monkeypatch)
    monkeypatch.setattr(HE.ranking, "_demanda_de_snapshot", lambda sn, rp_pct=None: (3, "UNKNOWN", []))
    tier, quote, _ = HE._demanda_display(object(), "TENB")
    assert tier == 3 and quote == "revenue from customer X recognized"   # el gobernante, no el de menor tier


def test_demanda_display_sin_evidencia(monkeypatch):
    monkeypatch.setattr(HE.FS, "snapshot_vigente", lambda s, t: {})
    assert HE._demanda_display(object(), "XXX") == (None, None, None)


def test_demanda_display_tier0_es_none(monkeypatch):
    monkeypatch.setattr(HE.FS, "snapshot_vigente", lambda s, t: {"cliente_nombrado": _F(quote="x")})
    _mock_rp(monkeypatch)
    monkeypatch.setattr(HE.ranking, "_demanda_de_snapshot", lambda sn, rp_pct=None: (0, "UNKNOWN", []))
    tier, quote, _ = HE._demanda_display(object(), "AAOI")
    assert tier is None                                   # tier 0 → 's/d', nunca 0 en display


# --- extraer_demanda: cache-guard (no re-gasta LLM si el filing no cambió) ---
def test_extraer_demanda_cachea_si_filing_igual(monkeypatch):
    monkeypatch.setattr(analisis.retrieval, "resolver_corpus",
                        lambda t, **k: types.SimpleNamespace(accession="ACC-1"))
    snap = {fk: _F(source_accession="ACC-1") for fk in analisis.DEMANDA_FACT_KEYS}
    monkeypatch.setattr(analisis.FS, "snapshot_vigente", lambda s, t: snap)
    llamado = []
    monkeypatch.setattr(analisis, "analizar_ticker", lambda *a, **k: llamado.append(1) or {})
    out = analisis.extraer_demanda(object(), "AAOI")
    assert llamado == [] and out is snap                  # cache hit → NO llama al extractor


def test_extraer_demanda_reextrae_si_cambia_filing(monkeypatch):
    monkeypatch.setattr(analisis.retrieval, "resolver_corpus",
                        lambda t, **k: types.SimpleNamespace(accession="ACC-2"))
    snap = {fk: _F(source_accession="ACC-1") for fk in analisis.DEMANDA_FACT_KEYS}   # stale
    monkeypatch.setattr(analisis.FS, "snapshot_vigente", lambda s, t: snap)
    llamado = []
    monkeypatch.setattr(analisis, "analizar_ticker", lambda *a, **k: llamado.append(1) or {"x": 1})
    analisis.extraer_demanda(object(), "AAOI")
    assert llamado == [1]                                 # filing nuevo → re-extrae


# --- extraer_e1: guard PROPIO de backlog_no_cancelable (doc 14 §E1), independiente de la demanda ---
def test_extraer_e1_cachea_si_ya_extraido(monkeypatch):
    monkeypatch.setattr(analisis.retrieval, "resolver_corpus",
                        lambda t, **k: types.SimpleNamespace(accession="ACC-1"))
    snap = {"backlog_no_cancelable": _F(source_accession="ACC-1")}
    monkeypatch.setattr(analisis.FS, "snapshot_vigente", lambda s, t: snap)
    llamado = []
    monkeypatch.setattr(analisis, "analizar_ticker", lambda *a, **k: llamado.append(1) or {})
    out = analisis.extraer_e1(object(), "LEU")
    assert llamado == [] and out is snap                   # ya extraído p/ este filing → no re-gasta


def test_extraer_e1_extrae_solo_backlog_key(monkeypatch):
    # falta backlog_no_cancelable (aunque estén los de demanda) → extrae, y SOLO ese fact_key
    monkeypatch.setattr(analisis.retrieval, "resolver_corpus",
                        lambda t, **k: types.SimpleNamespace(accession="ACC-1"))
    monkeypatch.setattr(analisis.FS, "snapshot_vigente",
                        lambda s, t: {fk: _F(source_accession="ACC-1") for fk in analisis.DEMANDA_FACT_KEYS})
    specs_vistos = []
    monkeypatch.setattr(analisis, "analizar_ticker",
                        lambda *a, specs=None, **k: specs_vistos.append([s.fact_key for s in specs]) or {})
    analisis.extraer_e1(object(), "LEU")
    assert specs_vistos == [["backlog_no_cancelable"]]     # targeted: NO re-corre los 3 de demanda


def test_extraer_e1_reextrae_si_cambia_filing(monkeypatch):
    monkeypatch.setattr(analisis.retrieval, "resolver_corpus",
                        lambda t, **k: types.SimpleNamespace(accession="ACC-2"))
    monkeypatch.setattr(analisis.FS, "snapshot_vigente",
                        lambda s, t: {"backlog_no_cancelable": _F(source_accession="ACC-1")})   # stale
    llamado = []
    monkeypatch.setattr(analisis, "analizar_ticker", lambda *a, **k: llamado.append(1) or {})
    analisis.extraer_e1(object(), "LEU")
    assert llamado == [1]


# --- rp_pct (XBRL determinista) es FLAG informativo, NO veto (el PM/humano juzga) ---
def test_rp_pct_dominante_flaggea_no_veta(monkeypatch):
    from backend.nucleo import ranking
    # rp dominante (92%) → el tier NO se auto-excluye (REALIZED se conserva) + se agrega el flag para revisar
    monkeypatch.setattr(ranking, "_snap", lambda snap, k: {"demanda_realizada": True}.get(k))
    tier, _, hechos = ranking._demanda_de_snapshot({}, rp_pct=0.92)
    assert tier == 3 and any("related_party_pct" in h["claim"] for h in hechos)


def test_rp_pct_inmaterial_sin_flag(monkeypatch):
    from backend.nucleo import ranking
    # rp 6% < umbral → sin flag, tier normal
    monkeypatch.setattr(ranking, "_snap", lambda snap, k: {"demanda_realizada": True}.get(k))
    tier, _, hechos = ranking._demanda_de_snapshot({}, rp_pct=0.06)
    assert tier == 3 and not any("related_party_pct" in h["claim"] for h in hechos)


def test_gate_sin_rp_comportamiento_normal(monkeypatch):
    from backend.nucleo import ranking
    monkeypatch.setattr(ranking, "_snap", lambda snap, k: {"demanda_minimo": True}.get(k))
    tier, _, _ = ranking._demanda_de_snapshot({}, rp_pct=None)
    assert tier == 2


def test_demanda_display_nota_parte_relacionada(monkeypatch):
    # rp dominante → tier 0 (excluido) + nota visible con el %
    monkeypatch.setattr(HE.FS, "snapshot_vigente", lambda s, t: {"x": _F()})
    monkeypatch.setattr(HE.edgar, "get_related_party_pct", lambda t: {"pct": 0.92})
    monkeypatch.setattr(HE.ranking, "_demanda_de_snapshot", lambda sn, rp_pct=None: (3, "UNKNOWN", []))
    tier, quote, nota = HE._demanda_display(object(), "SMR")
    assert tier == 3 and nota == "parte_relacionada=92%:revisar"


def test_extraer_demanda_sin_corpus_no_llama(monkeypatch):
    monkeypatch.setattr(analisis.retrieval, "resolver_corpus", lambda t, **k: None)
    monkeypatch.setattr(analisis.FS, "snapshot_vigente", lambda s, t: {})
    llamado = []
    monkeypatch.setattr(analisis, "analizar_ticker", lambda *a, **k: llamado.append(1) or {})
    out = analisis.extraer_demanda(object(), "RKLB")
    assert llamado == [] and out == {}                    # sin filing → no inventa, no gasta
