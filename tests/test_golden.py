"""Set dorado (r5 item 3): el pack debe reproducir los valores capturados dentro de tolerancia.

Network-gated: pega a EDGAR (companyfacts). Si no hay red o no hay golden file → SKIP (la suite hermética
no depende de red). En el server, con red, es la regresión que habría atrapado el bug de MP.
"""
import json
from datetime import date
from pathlib import Path

import pytest

from backend.agentes import data_pack as dp

_GOLDEN = Path(__file__).resolve().parent / "golden" / "golden_pack.json"


def _pack_metricas(tk: str, as_of: date) -> dict:
    pts = {p.metric: p for p in dp.fuente_xbrl(tk, as_of)}
    pts.update({p.metric: p for p in dp.fuente_calculadoras(tk, as_of, list(pts.values()))})
    return {m: p.value for m, p in pts.items() if p.value is not None}


@pytest.mark.network
def test_pack_reproduce_el_golden():
    if not _GOLDEN.exists():
        pytest.skip("sin golden_pack.json (correr ops.golden_snapshot en el server)")
    golden = json.loads(_GOLDEN.read_text())
    tol = float(golden.get("tolerancia_rel", 0.001))
    try:
        # sanity: una llamada; si EDGAR no responde, skip (suite hermética)
        probe = _pack_metricas(next(iter(golden["nombres"])), date.today())
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"EDGAR no accesible ({e})")
    if not probe:
        pytest.skip("EDGAR no devolvió datos")

    fallas = []
    for tk, e in golden["nombres"].items():
        actual = _pack_metricas(tk, date.today())
        for m, v in e["metricas"].items():
            esperado = v["valor"]
            got = actual.get(m)
            if got is None:
                fallas.append(f"{tk}.{m}: falta en el pack (esperado {esperado})")
            elif abs(got - esperado) > max(abs(esperado) * tol, 0.01):
                fallas.append(f"{tk}.{m}: {got} vs golden {esperado} (>tol {tol})")
    assert not fallas, "el pack dejó de reproducir el golden:\n" + "\n".join(fallas)
