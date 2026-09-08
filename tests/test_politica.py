"""Archivo de política versionado (doc 28 §0/§6)."""
from backend.nucleo import politica


def test_sello_tiene_version_y_hash():
    s = politica.sello()
    assert s["politica_version"] == politica.VERSION
    assert isinstance(s["politica_hash"], str) and len(s["politica_hash"]) == 12


def test_hash_es_determinista():
    assert politica._hash() == politica._hash() == politica.HASH


def test_idiq_ceiling_va_al_ledger():
    r = politica.retencion_contrato("idiq_ceiling")
    assert r["destino"] == "ledger_O3"
    assert r["retencion"] == 0.0


def test_take_or_pay_entra_operable():
    r = politica.retencion_contrato("take_or_pay_min")
    assert r["destino"] == "operable"
    assert r["retencion"] == 0.90


def test_tipo_desconocido_cae_al_piso():
    r = politica.retencion_contrato("algo_raro")
    assert r["retencion"] == politica.PISO_UNIVERSAL
    assert r.get("fallback") is True


def test_r_por_arquetipo():
    assert politica.r_efectiva("Madura") == 0.12
    assert politica.r_efectiva("Pre-revenue") == 0.25
    assert politica.r_efectiva("desconocido") == politica.R_ARQUETIPO["Growth"]
