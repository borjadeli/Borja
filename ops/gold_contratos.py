"""Gold set de CONTRATOS (r7 Bloque 2 / Gate B, doc 78) — la red de medición del parser de 8-K ítem 1.01.

Antes de que un contrato FIRME mueva un tamaño (sizing), el parser que lo clasifica (firme/condicional/no-cuenta)
tiene que estar MEDIDO: un falso FIRME infla el margen de seguridad y sizea de más (el modo de falla del doc 72).
Este ops arma el set para etiquetar a mano (igual que `ops.golden_snapshot` con los datos duros):

  1. `ops.gold_contratos BWXT LEU RKLB ...`  → baja los 8-K con ítem 1.01 (EDGAR) y escribe el excerpt +
     campos VACÍOS en `tests/gold_contratos/gold_contratos.json`.
  2. El OPERADOR (o una IA) ETIQUETA cada entrada contra el filing: `label` (firme|condicional|no_cuenta),
     contraparte, monto_usd, vinculante, condiciones_precedentes, tipo_contrato.
  3. Cuando exista el parser (§2), `tests/test_gold_contratos.py` mide su precisión contra estas etiquetas.

Definiciones (doc 78 §2):
- FIRME: take-or-pay / orden firme / vinculante no cancelable (o con penalidad relevante); contrato de gobierno
  SOLO por el monto obligado (nunca el techo del IDIQ); contraparte con capacidad de pago.
- CONDICIONAL: vinculante con condiciones precedentes de un tercero (licencia, financiación, FID del cliente).
- NO CUENTA: MOU, LOI, acuerdo marco sin volúmenes, "de hasta X", techo de IDIQ, opción no ejercida, selección
  en negociación, partnership sin condiciones de pago.

Hits de red (EDGAR) → lo corre el operador en el server. No gasta API de LLM.
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

from backend.services.edgar import _fetch_text, get_recent_filings

_GOLD = Path(__file__).resolve().parent.parent / "tests" / "gold_contratos" / "gold_contratos.json"
# Nombres del universo que típicamente anuncian contratos materiales (defensa/nuclear/espacio/gobierno/offtake).
_DEFAULT = ["BWXT", "LEU", "RKLB", "OKLO", "KTOS", "MP", "LUNR", "UUUU"]
_LABEL_VACIO = {"label": None, "contraparte": None, "monto_usd": None, "vinculante": None,
                "condiciones_precedentes": None, "tipo_contrato": None}


def _excerpt(url: str, *, maxlen: int = 2500) -> str:
    """Texto del 8-K alrededor del 'Item 1.01' (HTML → plano). Vacío si no se pudo bajar."""
    raw = _fetch_text(url)
    if not raw:
        return ""
    txt = re.sub(r"<[^>]+>", " ", raw)                 # saca tags
    txt = re.sub(r"&#?\w+;", " ", txt)                 # entidades html (nombradas y numéricas: &amp; &#8220;)
    txt = re.sub(r"\s+", " ", txt).strip()
    m = re.search(r"item\s*1\.01", txt, flags=re.I)
    inicio = m.start() if m else 0
    return txt[inicio:inicio + maxlen]


def capturar(tickers: list[str], *, dias: int = 540, fetch_text=_excerpt,
             filings_fn=get_recent_filings) -> dict:
    """Arma el set a etiquetar. Preserva las etiquetas ya puestas (merge por accession). `fetch_text` y
    `filings_fn` son inyectables para test offline."""
    import json
    prev = json.loads(_GOLD.read_text()) if _GOLD.exists() else {}
    prev_por_accn = {}
    for tk, ents in (prev.get("nombres") or {}).items():
        for e in ents:
            prev_por_accn[(tk.upper(), e.get("accession"))] = e

    nombres: dict[str, list] = {}
    for tk in tickers:
        tk = tk.upper()
        ents = []
        for f in filings_fn(tk, tipos=("8-K",), dias=dias):
            if "1.01" not in (f.items or ""):
                continue
            prev_e = prev_por_accn.get((tk, f.accession_number))
            etiquetas = {k: prev_e.get(k) for k in _LABEL_VACIO} if prev_e else dict(_LABEL_VACIO)
            ents.append({"accession": f.accession_number, "fecha": f.fecha.date().isoformat(),
                         "url": f.url, "items": f.items, "excerpt": fetch_text(f.url), **etiquetas})
        if ents:
            nombres[tk] = ents
    return {"capturado": date.today().isoformat(),
            "labels_validos": ["firme", "condicional", "no_cuenta"], "nombres": nombres}


def main() -> int:
    import json
    tickers = sys.argv[1:] or _DEFAULT
    print(f"bajando 8-K ítem 1.01 de {len(tickers)} nombres (hits de red)…")
    out = capturar(tickers)
    _GOLD.parent.mkdir(parents=True, exist_ok=True)
    _GOLD.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    n = sum(len(v) for v in out["nombres"].values())
    sin = sum(1 for v in out["nombres"].values() for e in v if e["label"] is None)
    print(f"gold de contratos escrito en {_GOLD}: {n} filings 1.01 en {len(out['nombres'])} nombres")
    for tk, v in out["nombres"].items():
        print(f"  {tk}: {len(v)} filings 1.01")
    print(f"\nSIN etiquetar: {sin}/{n}. Paso siguiente: poné label (firme|condicional|no_cuenta) + los campos "
          f"en {_GOLD.name}, leyendo cada filing por su url.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
