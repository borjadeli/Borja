"""Congela los BYTES CRUDOS del filing más reciente de un ticker como fixture del gold set.

    .venv/bin/python -m ops.gold_freeze AAOI [TENB ...]

Guarda el HTML crudo del primary del 10-Q/10-K en `data/gold/corpus/<TICKER>_<accession>.html`
(+ imprime accession y sha). Se congela el CRUDO, no el texto extraído: el extractor HTML→texto
también está bajo test, así una mejora del extractor puede arreglar/romper retrieval y se ve
(IA2). El harness extrae en runtime con el mismo `retrieval._limpiar` del pipeline. La red se usa
SOLO acá; la medición corre offline contra estos fixtures.
"""
from __future__ import annotations

import hashlib
import sys

from backend.nucleo import retrieval
from backend.nucleo.gold_retrieval import CORPUS_DIR
from backend.services import edgar


def freezar(ticker: str) -> str | None:
    # resolver_corpus sin bajar texto: nos da url + accession del primary más reciente
    corpus = retrieval.resolver_corpus(ticker, forms=("10-Q", "10-K"),
                                       con_exhibits=False, bajar_texto=False)
    if corpus is None or not corpus.primary:
        print(f"  {ticker}: sin corpus")
        return None
    crudo = edgar._fetch_text(corpus.primary.url)
    if not crudo:
        print(f"  {ticker}: no se pudo bajar el crudo ({corpus.primary.url})")
        return None
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    path = CORPUS_DIR / f"{ticker.upper()}_{corpus.accession}.html"
    path.write_text(crudo, encoding="utf-8")
    sha = hashlib.sha256(crudo.encode("utf-8", "ignore")).hexdigest()[:12]
    texto = retrieval._limpiar(crudo)
    print(f"  {ticker}: {corpus.form} accession={corpus.accession} crudo={len(crudo):,}ch "
          f"extraído={len(texto):,}ch sha={sha} -> {path.name}")
    return corpus.accession


def main(argv: list[str]) -> int:
    if not argv:
        print("uso: python -m ops.gold_freeze TICKER [TICKER ...]")
        return 2
    for t in argv:
        freezar(t.upper())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
