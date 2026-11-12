"""Gold set de contratos (r7 Bloque 2 / Gate B): el scaffold que arma el set a etiquetar + valida las labels."""
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from ops.gold_contratos import capturar

_GOLD = Path(__file__).resolve().parent / "gold_contratos" / "gold_contratos.json"
_LABELS = {"firme", "condicional", "no_cuenta"}


def _filing(accn, items):
    return SimpleNamespace(accession_number=accn, items=items, url=f"http://x/{accn}",
                           fecha=datetime(2026, 5, 1))


def test_capturar_filtra_solo_item_101():
    def filings_fn(tk, *, tipos, dias):
        return [_filing("A1", "1.01,9.01"), _filing("A2", "2.02,9.01"), _filing("A3", "1.01")]
    out = capturar(["BWXT"], filings_fn=filings_fn, fetch_text=lambda u: "Item 1.01 Entry into a Material...")
    ents = out["nombres"]["BWXT"]
    assert {e["accession"] for e in ents} == {"A1", "A3"}        # solo los que tienen 1.01
    assert all(e["label"] is None for e in ents)                 # recién capturados, sin etiquetar
    assert out["labels_validos"] == ["firme", "condicional", "no_cuenta"]


def test_capturar_entrada_tiene_campos_para_etiquetar():
    def filings_fn(tk, *, tipos, dias):
        return [_filing("A1", "1.01")]
    e = capturar(["LEU"], filings_fn=filings_fn, fetch_text=lambda u: "texto")["nombres"]["LEU"][0]
    for campo in ("contraparte", "monto_usd", "vinculante", "condiciones_precedentes", "tipo_contrato"):
        assert campo in e
    assert e["excerpt"] == "texto" and e["url"] == "http://x/A1"


def test_labels_del_gold_son_validas_si_existe():
    # si el operador ya etiquetó, las labels deben ser del set válido (sanity del etiquetado)
    if not _GOLD.exists():
        pytest.skip("sin gold_contratos.json todavía (correr ops.gold_contratos en el server)")
    data = json.loads(_GOLD.read_text())
    for tk, ents in (data.get("nombres") or {}).items():
        for e in ents:
            if e.get("label") is not None:
                assert e["label"] in _LABELS, f"{tk}/{e['accession']}: label inválida {e['label']!r}"
